import logging
from uuid import uuid4

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from infra.audit import record

logger = logging.getLogger("hexin.api")


async def audit_requests(request, call_next):
    request_id = uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        await run_in_threadpool(record, request, request_id, response.status_code)
    return response


async def handle_unexpected_errors(request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "操作暂未完成，请稍后重试"})
