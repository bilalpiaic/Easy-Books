"""Signup, login, and current-user endpoints.

Login issues a JWT and also sets it as an HttpOnly cookie so SPA frontends
can stop storing tokens in localStorage. The cookie reader and the
Authorization header reader coexist (see routers/common.py).
"""
import os
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlmodel import select

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from db import seed_data
from models import Tenant, User

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_COOKIE_NAME = "eb_access"
_LOGIN_ATTEMPT_WINDOW_SEC = 60
_LOGIN_ATTEMPT_MAX = 10
_login_attempts: dict[str, deque[float]] = defaultdict(deque)


def _cookie_secure() -> bool:
    return os.environ.get("APP_ENV", "dev").lower() in ("production", "prod")


def _set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _throttle(request: Request) -> None:
    """Sliding-window per-IP throttle on /login. In-memory; sufficient for
    single-process dev and small deployments. Swap for Redis when scaling out.
    """
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _login_attempts[ip]
    while window and now - window[0] > _LOGIN_ATTEMPT_WINDOW_SEC:
        window.popleft()
    if len(window) >= _LOGIN_ATTEMPT_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Wait a minute and try again.",
        )
    window.append(now)


class UserSignup(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str
    company_name: str


@router.post("/signup")
def signup(data: UserSignup, session: SessionDep, response: Response):
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    tenant = Tenant(name=data.company_name)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    seed_data(tenant.id, session=session)

    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        tenant_id=tenant.id,
        role="owner",  # first user of a tenant is its owner
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"success": True, "tenant_id": tenant.id}


@router.post("/login")
def login(
    session: SessionDep,
    response: Response,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    _throttle(request)
    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        data={
            "sub": user.email,
            "tenant_id": user.tenant_id,
            "full_name": user.full_name,
            "role": user.role,
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    _set_access_cookie(response, token)
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    return {"success": True}


@router.get("/me")
def get_me(user: CurrentUserDep):
    return {"email": user.email, "full_name": user.full_name, "role": user.role}
