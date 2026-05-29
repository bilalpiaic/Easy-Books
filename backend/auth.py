import os
import warnings
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import jwt

_DEFAULT_SECRET = "super-secret-key-change-in-prod"
_ENV = (os.environ.get("APP_ENV") or os.environ.get("ENV") or "development").lower()

_env_secret = os.environ.get("JWT_SECRET_KEY", "")
if _env_secret:
    SECRET_KEY = _env_secret
elif _ENV in ("production", "prod"):
    # Hard-fail at import time: a production process must never sign tokens
    # with a public default key.
    raise SystemExit(
        "FATAL: JWT_SECRET_KEY is unset while APP_ENV=production. "
        "Set a strong random secret in the environment before starting. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
else:
    # Local/dev: stable per-install key persisted in the data dir, so tokens
    # remain valid across restarts (no shared insecure default).
    from local_config import resolve_secret
    SECRET_KEY = resolve_secret()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours for prototype


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
