import os
import warnings
import bcrypt
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional

_DEFAULT_SECRET = "super-secret-key-change-in-prod"
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", _DEFAULT_SECRET)
if SECRET_KEY == _DEFAULT_SECRET:
    _environment = os.environ.get("ENVIRONMENT", "development").lower()
    if _environment == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a secure random value in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    warnings.warn("JWT_SECRET_KEY is not set — using insecure default. Set this env var before deploying.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 60 minutes

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
