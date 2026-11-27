import json
import logging
from pathlib import Path

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

import domain
from infra.queue import PENDING, PROCESSING, redis, state
from infra.roles import JobState

HEARTBEAT = Path("/tmp/hexin-heartbeat")
logger = logging.getLogger(__name__)


def run():
    handlers = getattr(domain, "JOBS", {})
    # One worker per standalone stack. Recover interrupted read-only calculations.
    while redis.rpoplpush(PROCESSING, PENDING):
        continue
    while True:
        HEARTBEAT.touch()
        item = redis.brpoplpush(PENDING, PROCESSING, timeout=2)
        if item is None:
            continue
        job = json.loads(item)
        try:
            state(job["id"], JobState.RUNNING)
            result = handlers[job["kind"]](job["payload"])
            state(job["id"], JobState.DONE, result=jsonable_encoder(result))
        except HTTPException as error:
            state(job["id"], JobState.FAILED, error=str(error.detail))
        except Exception:
            logger.exception("Calculation failed for %s", job["id"])
            state(job["id"], JobState.FAILED, error="模型计算失败，请核对输入后重试")
        redis.lrem(PROCESSING, 1, item)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
