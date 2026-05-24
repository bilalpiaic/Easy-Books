"""Signup, login, and current-user endpoints.

Login issues a JWT and also sets it as an HttpOnly cookie so SPA frontends
can stop storing tokens in localStorage. The cookie reader and the
Authorization header reader coexist (see routers/common.py).

Login throttling lives in the database (LoginAttempt table) so the counter
is shared across uvicorn workers. The accompanying CSRF cookie is set on
successful login; cookie-authenticated mutations are checked against it by
services.csrf middleware.
"""
import json as _json
import os
import secrets
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from db import MODULES_BY_MODEL, seed_data
from models import LoginAttempt, Tenant, User, UserInvite

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_COOKIE_NAME = "eb_access"
CSRF_COOKIE_NAME = "eb_csrf"

# Avatar storage — reuses the same UPLOAD_ROOT as document attachments,
# under <root>/<tenant_id>/avatars/<user_id>.<ext>.
_UPLOAD_ROOT = Path(os.environ.get("UPLOAD_ROOT", "uploads")).resolve()
_AVATAR_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_AVATAR_MIME = {
    "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg",
    "image/gif": "gif", "image/webp": "webp",
}
_LOGIN_ATTEMPT_WINDOW_SEC = 60
_LOGIN_ATTEMPT_MAX = 10
# Kept as an alias for tests that still clear the legacy in-memory dict.
_login_attempts: dict[str, deque] = {}


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


def _set_csrf_cookie(response: Response, token: str) -> None:
    """Non-HttpOnly so the SPA can read it and echo in X-CSRF-Token."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=False,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _throttle(session: Session, request: Request) -> None:
    """Sliding-window per-IP throttle backed by LoginAttempt rows.

    Counts attempts in the last window. Prunes older rows in the same call
    so the table stays bounded without a cron job. Shared across workers
    because state is in the DB, not a process-local dict.
    """
    ip = request.client.host if request.client else "unknown"
    cutoff = datetime.utcnow() - timedelta(seconds=_LOGIN_ATTEMPT_WINDOW_SEC)
    # Prune
    old = session.exec(
        select(LoginAttempt).where(LoginAttempt.attempted_at < cutoff)
    ).all()
    for row in old:
        session.delete(row)
    if old:
        session.flush()
    # Count
    count = session.exec(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.ip == ip,
            LoginAttempt.attempted_at >= cutoff,
        )
    ).one()
    if count >= _LOGIN_ATTEMPT_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Wait a minute and try again.",
        )
    session.add(LoginAttempt(ip=ip))
    session.flush()


_VALID_MODELS = {"simple", "services", "trader", "manufacturing", "telecom_franchise"}


class UserSignup(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str
    company_name: str
    business_model: Optional[str] = "simple"


@router.post("/signup")
def signup(data: UserSignup, session: SessionDep, response: Response):
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    model = (data.business_model or "simple").lower()
    if model not in _VALID_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"business_model must be one of {sorted(_VALID_MODELS)}",
        )

    tenant = Tenant(
        name=data.company_name,
        business_model=model,
        enabled_modules=_json.dumps(MODULES_BY_MODEL.get(model, [])),
    )
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
    _throttle(session, request)
    # Commit the throttle row even if credentials fail, so brute-force
    # attempts count toward the limit.
    session.commit()

    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account has been deactivated. Contact an administrator.",
        )
    user.last_login_at = datetime.utcnow()
    session.add(user)
    session.commit()
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
    csrf = secrets.token_urlsafe(32)
    _set_csrf_cookie(response, csrf)
    return {
        "access_token": token, "token_type": "bearer", "role": user.role,
        "csrf_token": csrf, "must_change_password": user.must_change_password,
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    return {"success": True}


@router.get("/me")
def get_me(session: SessionDep, user: CurrentUserDep):
    tenant = session.get(Tenant, user.tenant_id)
    try:
        enabled = _json.loads(tenant.enabled_modules) if tenant else []
    except (TypeError, ValueError):
        enabled = []
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "tenant": {
            "id": tenant.id if tenant else user.tenant_id,
            "name": tenant.name if tenant else "",
            "business_model": tenant.business_model if tenant else "simple",
            "enabled_modules": enabled,
            "base_currency": tenant.base_currency if tenant else "USD",
        },
    }


# ── Profile self-service ──────────────────────────────────────────────────────


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


@router.patch("/me")
def update_me(data: ProfileUpdate, session: SessionDep, user: CurrentUserDep):
    """Update the caller's own profile (name + phone). Email and role are
    intentionally not editable here — role changes go through /api/users."""
    if data.full_name is not None:
        user.full_name = data.full_name.strip() or user.full_name
    if data.phone is not None:
        user.phone = data.phone.strip() or None
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"full_name": user.full_name, "phone": user.phone}


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/change-password")
def change_password(data: PasswordChange, session: SessionDep, user: CurrentUserDep):
    """Self-service password change. Verifies the current password, sets the
    new one, and clears the must_change_password flag."""
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="New password must differ from the current one")
    user.hashed_password = get_password_hash(data.new_password)
    user.must_change_password = False
    session.add(user)
    session.commit()
    return {"success": True}


# ── Accept invite (public) ────────────────────────────────────────────────────


class AcceptInvite(BaseModel):
    token: str
    full_name: str
    password: str = Field(min_length=8)


@router.get("/invite/{token}")
def inspect_invite(token: str, session: SessionDep):
    """Public — lets the accept-invite page show who/what the invite is for
    before the recipient sets a password. Never reveals other invites."""
    invite = session.exec(select(UserInvite).where(UserInvite.token == token)).first()
    if invite is None or invite.accepted_at is not None or invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Invite is invalid or has expired")
    tenant = session.get(Tenant, invite.tenant_id)
    return {
        "email": invite.email,
        "role": invite.role,
        "company_name": tenant.name if tenant else "",
    }


@router.post("/accept-invite")
def accept_invite(data: AcceptInvite, session: SessionDep, response: Response):
    """Public — materialises an active User from a pending invite and logs
    them in (sets the same cookies as /login)."""
    invite = session.exec(select(UserInvite).where(UserInvite.token == data.token)).first()
    if invite is None or invite.accepted_at is not None or invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Invite is invalid or has expired")
    if session.exec(select(User).where(User.email == invite.email)).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    user = User(
        email=invite.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        tenant_id=invite.tenant_id,
        role=invite.role,
        is_active=True,
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    invite.accepted_at = datetime.utcnow()
    session.add(invite)
    session.commit()
    session.refresh(user)

    token = create_access_token(
        data={"sub": user.email, "tenant_id": user.tenant_id,
              "full_name": user.full_name, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    _set_access_cookie(response, token)
    csrf = secrets.token_urlsafe(32)
    _set_csrf_cookie(response, csrf)
    return {"access_token": token, "token_type": "bearer", "role": user.role, "csrf_token": csrf}


# ── Avatar ────────────────────────────────────────────────────────────────────


def _avatar_dir(tenant_id: int) -> Path:
    return _UPLOAD_ROOT / str(tenant_id) / "avatars"


def _find_avatar(tenant_id: int, user_id: int) -> Optional[Path]:
    d = _avatar_dir(tenant_id)
    if not d.exists():
        return None
    for f in d.glob(f"{user_id}.*"):
        return f
    return None


@router.post("/me/avatar")
async def upload_avatar(session: SessionDep, user: CurrentUserDep, file: UploadFile = File(...)):
    ext = _AVATAR_MIME.get((file.content_type or "").lower())
    if ext is None:
        raise HTTPException(status_code=400, detail="Avatar must be a PNG, JPEG, GIF or WebP image")
    contents = await file.read()
    if len(contents) > _AVATAR_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (5 MB limit)")

    d = _avatar_dir(user.tenant_id)
    d.mkdir(parents=True, exist_ok=True)
    # Remove any prior avatar for this user (extension may differ).
    for old in d.glob(f"{user.id}.*"):
        old.unlink(missing_ok=True)
    (d / f"{user.id}.{ext}").write_bytes(contents)

    # Cache-busting query so the browser re-fetches after a change.
    user.avatar_url = f"/api/auth/users/{user.id}/avatar?v={int(datetime.utcnow().timestamp())}"
    session.add(user)
    session.commit()
    return {"avatar_url": user.avatar_url}


@router.delete("/me/avatar", status_code=204)
def delete_avatar(session: SessionDep, user: CurrentUserDep):
    for old in _avatar_dir(user.tenant_id).glob(f"{user.id}.*"):
        old.unlink(missing_ok=True)
    user.avatar_url = None
    session.add(user)
    session.commit()


@router.get("/users/{user_id}/avatar")
def get_avatar(user_id: int, session: SessionDep, user: CurrentUserDep):
    """Serve a tenant member's avatar. Tenant-scoped: you can only fetch
    avatars of users in your own tenant."""
    target = session.get(User, user_id)
    if target is None or target.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Avatar not found")
    path = _find_avatar(target.tenant_id, user_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(path)
