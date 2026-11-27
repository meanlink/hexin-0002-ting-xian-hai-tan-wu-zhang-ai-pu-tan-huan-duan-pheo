import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from redis import Redis

from infra.auth import access
from infra.config import REDIS_URL
from infra.roles import JobState

PENDING = "jobs:pending"
PROCESSING = "jobs:processing"
TTL = 24 * 60 * 60
redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
router = APIRouter(prefix="/jobs")


def enqueue(kind, payload):
    job_id = uuid4().hex
    message = {"id": job_id, "kind": kind, "payload": payload}
    with redis.pipeline() as pipe:
        pipe.set(f"job:{job_id}", json.dumps({"id": job_id, "status": JobState.QUEUED}), ex=TTL)
        pipe.lpush(PENDING, json.dumps(message, ensure_ascii=False))
        pipe.execute()
    return job_id


def state(job_id, status, **data):
    row = {"id": job_id, "status": status, **data}
    redis.set(f"job:{job_id}", json.dumps(row, ensure_ascii=False, allow_nan=False), ex=TTL)


@router.get("/{job_id}")
def read(job_id: str, user=Depends(access())):
    result = redis.get(f"job:{job_id}")
    if not result:
        raise HTTPException(404, "任务不存在或已过期")
    return json.loads(result)
