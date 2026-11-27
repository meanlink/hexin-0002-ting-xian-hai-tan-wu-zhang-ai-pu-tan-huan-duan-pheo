from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, Field

from infra.db import tx
from infra.roles import Role
from infra.security import claims, issue, verify

router = APIRouter(prefix="/auth")
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=150)


def access(*roles):
    def require(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None:
            raise HTTPException(401, "请先登录", headers={"WWW-Authenticate": "Bearer"})
        try:
            data = claims(credentials.credentials)
            role = Role(data["role"]).value
        except (InvalidTokenError, ValueError):
            raise HTTPException(401, "会话已失效，请重新登录") from None
        if roles and role not in roles:
            raise HTTPException(403, "当前账号没有此操作权限")
        return {"email": data["sub"], "role": role}
    return require


@router.post("/login")
def login(body: Credentials):
    with tx() as db:
        row = db.one("SELECT email, password_hash, role FROM users WHERE email=%s",
                     (body.email.lower().strip(),))
    if not row or not verify(body.password, row["password_hash"]):
        raise HTTPException(401, "账号或密码不匹配")
    return {"token": issue(row["email"], row["role"]), "email": row["email"], "role": row["role"]}


@router.get("/me")
def identity(user=Depends(access())):
    return user
