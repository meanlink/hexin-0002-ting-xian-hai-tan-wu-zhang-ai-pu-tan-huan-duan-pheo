from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

import domain
from infra.auth import router as auth_router
from infra.bootstrap import migrate, seed_demo
from infra.config import APP_NAME, SEED_DEMO
from infra.db import tx
from infra.middleware import audit_requests, handle_unexpected_errors
from infra.queue import redis, router as jobs_router


def startup():
    migrate()
    if SEED_DEMO:
        try:
            seed_demo()
        except Exception:
            logging.getLogger("hexin.seed").exception("Demo seed failed")


@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(startup)
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.middleware("http")(handle_unexpected_errors)
app.middleware("http")(audit_requests)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(domain.router)


@app.get("/health")
def health():
    with tx() as db:
        db.one("SELECT 1 AS ready")
    redis.ping()
    return {"ok": True}
