import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from infra.config import APP_NAME, JWT_SECRET


def derive(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000).hex()


def password_hash(password):
    salt = secrets.token_bytes(16)
    return salt.hex() + ":" + derive(password, salt)


def verify(password, digest):
    salt, expected = digest.split(":")
    return hmac.compare_digest(derive(password, bytes.fromhex(salt)), expected)


def issue(email, role):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": email, "role": role, "iss": APP_NAME,
                       "iat": now, "exp": now + timedelta(hours=8)}, JWT_SECRET,
                      algorithm="HS256")


def claims(token):
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer=APP_NAME,
                      options={"require": ["sub", "role", "iat", "exp"]})
