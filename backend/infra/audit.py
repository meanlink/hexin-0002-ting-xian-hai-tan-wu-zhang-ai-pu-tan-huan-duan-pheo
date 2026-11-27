import logging

from infra.db import tx
from infra.security import claims

logger = logging.getLogger("hexin.audit")


def record(request, request_id, status):
    user = "anonymous"
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            user = claims(auth[7:])["sub"]
        except Exception:
            pass
    try:
        with tx() as db:
            db.execute("""INSERT INTO audit_events(request_id,actor,verb,path,status_code)
                          VALUES (%s,%s,%s,%s,%s)""",
                       (request_id, user, request.method, request.url.path[:500], status))
    except Exception:
        logger.exception("Could not persist audit event %s", request_id)
