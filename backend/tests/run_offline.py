"""Stdlib-only test entry point.

Run from backend/:  python3 tests/run_offline.py
Stubs the third-party web packages that are absent in this offline sandbox but
uninvolved in the domain logic under test.
"""

import sys
import types
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def _install_stubs():
    # fastapi.HTTPException is the only symbol the domain modules touch at
    # import time in these code paths.
    fastapi = types.ModuleType('fastapi')

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi.HTTPException = HTTPException

    class _APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda fn: fn

        post = get

    fastapi.APIRouter = _APIRouter

    def _depends(*args, **kwargs):
        return None

    fastapi.Depends = _depends

    def _annotated_marker(*args, **kwargs):
        return args[0] if args else None

    typing_extensions = types.ModuleType('typing_extensions')
    pydantic = types.ModuleType('pydantic')

    class BaseModel:
        pass

    def Field(*args, **kwargs):
        return None

    def StringConstraints(*args, **kwargs):
        return None

    pydantic.BaseModel = BaseModel
    pydantic.Field = Field
    pydantic.StringConstraints = StringConstraints

    infra = types.ModuleType('infra')
    infra_db = types.ModuleType('infra.db')
    infra_queue = types.ModuleType('infra.queue')

    class _TxPlaceholder:
        def __call__(self):
            raise RuntimeError('tx must be patched')

    infra_db.tx = _TxPlaceholder()

    def _enqueue(*args, **kwargs):
        raise RuntimeError('enqueue must be patched')

    infra_queue.enqueue = _enqueue

    sys.modules.update({
        'fastapi': fastapi,
        'pydantic': pydantic,
        'typing_extensions': typing_extensions,
        'infra': infra,
        'infra.db': infra_db,
        'infra.queue': infra_queue,
    })


def main():
    _install_stubs()
    loader = unittest.TestLoader()
    suite = loader.discover(str(BACKEND / 'tests'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
