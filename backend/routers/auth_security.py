"""TOTP 2FA + OAuth SSO helpers attached to auth router (#118)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
import pyotp
from fastapi import APIRouter, HTTPException, Request, Response
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlmodel import select

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
)
from models import Tenant, User
from services.crypto_secrets import decrypt_secret, encrypt_secret

from .common import CurrentUserDep, SessionDep
from .auth import (
    _set_access_cookie,
    _set_csrf_cookie,
    router as auth_router,
)
import secrets as _secrets
import json as _json

# Mounted via include in auth — we add routes onto the same auth_router.


class TotpCode(BaseModel):
    code: str


class TotpVerify(BaseModel):
    partial_token: str
    code: str


def _issue_full_token(user: User, response: Response) -> dict:
    token = create_access_token(
        data={
            "sub": user.email,
            "tenant_id": user.tenant_id,
            "full_name": user.full_name,
            "role": user.role,
            "jti": str(uuid.uuid4()),
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    _set_access_cookie(response, token)
    csrf = _secrets.token_urlsafe(32)
    _set_csrf_cookie(response, csrf)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "csrf_token": csrf,
        "must_change_password": user.must_change_password,
        "onboarding_required": False,
        "addons_suggested": False,
    }


@auth_router.post("/totp/setup")
def totp_setup(session: SessionDep, user: CurrentUserDep):
    secret = pyotp.random_base32()
    user.totp_secret = encrypt_secret(secret)
    user.totp_enabled = False
    session.add(user)
    session.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Easy-Books")
    return {"secret": secret, "otpauth_url": uri}


@auth_router.post("/totp/enable")
def totp_enable(body: TotpCode, session: SessionDep, user: CurrentUserDep):
    if not user.totp_secret:
        raise HTTPException(400, "Call /totp/setup first")
    plain = decrypt_secret(user.totp_secret)
    if not pyotp.TOTP(plain).verify(body.code, valid_window=1):
        raise HTTPException(401, "Invalid OTP code")
    user.totp_enabled = True
    user.totp_verified_at = datetime.utcnow()
    session.add(user)
    session.commit()
    return {"ok": True, "totp_enabled": True}


@auth_router.post("/totp/disable")
def totp_disable(body: TotpCode, session: SessionDep, user: CurrentUserDep):
    if not user.totp_enabled or not user.totp_secret:
        user.totp_enabled = False
        user.totp_secret = None
        session.add(user)
        session.commit()
        return {"ok": True}
    plain = decrypt_secret(user.totp_secret)
    if not pyotp.TOTP(plain).verify(body.code, valid_window=1):
        raise HTTPException(401, "Invalid OTP code")
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_verified_at = None
    session.add(user)
    session.commit()
    return {"ok": True, "totp_enabled": False}


@auth_router.post("/totp/verify")
def totp_verify(body: TotpVerify, session: SessionDep, response: Response):
    try:
        payload = jwt.decode(body.partial_token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Invalid or expired partial token")
    if not payload.get("totp_pending"):
        raise HTTPException(401, "Not a TOTP pending token")
    email = payload.get("sub")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not user.totp_enabled or not user.totp_secret:
        raise HTTPException(401, "2FA not enabled for this user")
    plain = decrypt_secret(user.totp_secret)
    if not pyotp.TOTP(plain).verify(body.code, valid_window=1):
        raise HTTPException(401, "Invalid OTP code")
    user.last_login_at = datetime.utcnow()
    session.add(user)
    session.commit()
    return _issue_full_token(user, response)


@auth_router.get("/oauth/providers")
def oauth_providers():
    return {
        "google": bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET")),
        "microsoft": bool(
            os.environ.get("MICROSOFT_CLIENT_ID") and os.environ.get("MICROSOFT_CLIENT_SECRET")
        ),
    }


def _oauth_redirect_base() -> str:
    return os.environ.get(
        "OAUTH_REDIRECT_BASE",
        os.environ.get("FRONTEND_ORIGIN", "http://localhost:8000"),
    ).rstrip("/")


@auth_router.get("/oauth/google")
def oauth_google_start():
    cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not cid:
        raise HTTPException(503, "Google OAuth not configured")
    params = urlencode({
        "client_id": cid,
        "redirect_uri": f"{_oauth_redirect_base()}/api/auth/oauth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    })
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@auth_router.get("/oauth/google/callback")
def oauth_google_callback(
    session: SessionDep, response: Response, code: Optional[str] = None
):
    if not code:
        raise HTTPException(400, "Missing code")
    token_resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": f"{_oauth_redirect_base()}/api/auth/oauth/google/callback",
            "grant_type": "authorization_code",
        },
        timeout=15.0,
    )
    token_resp.raise_for_status()
    access = token_resp.json().get("access_token")
    info = httpx.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access}"},
        timeout=15.0,
    )
    info.raise_for_status()
    profile = info.json()
    return _finish_oauth(session, response, "google", profile.get("id"), profile.get("email"), profile.get("name"))


@auth_router.get("/oauth/microsoft")
def oauth_microsoft_start():
    cid = os.environ.get("MICROSOFT_CLIENT_ID", "").strip()
    if not cid:
        raise HTTPException(503, "Microsoft OAuth not configured")
    params = urlencode({
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": f"{_oauth_redirect_base()}/api/auth/oauth/microsoft/callback",
        "response_mode": "query",
        "scope": "openid email profile User.Read",
    })
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{params}"
    )


@auth_router.get("/oauth/microsoft/callback")
def oauth_microsoft_callback(
    session: SessionDep, response: Response, code: Optional[str] = None
):
    if not code:
        raise HTTPException(400, "Missing code")
    token_resp = httpx.post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data={
            "code": code,
            "client_id": os.environ["MICROSOFT_CLIENT_ID"],
            "client_secret": os.environ["MICROSOFT_CLIENT_SECRET"],
            "redirect_uri": f"{_oauth_redirect_base()}/api/auth/oauth/microsoft/callback",
            "grant_type": "authorization_code",
        },
        timeout=15.0,
    )
    token_resp.raise_for_status()
    access = token_resp.json().get("access_token")
    info = httpx.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {access}"},
        timeout=15.0,
    )
    info.raise_for_status()
    profile = info.json()
    email = profile.get("mail") or profile.get("userPrincipalName")
    return _finish_oauth(
        session, response, "microsoft", profile.get("id"), email, profile.get("displayName")
    )


def _finish_oauth(session, response, provider, sub, email, full_name):
    from fastapi.responses import RedirectResponse
    from auth import get_password_hash

    if not email:
        raise HTTPException(400, "OAuth provider did not return an email")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        if os.environ.get("ALLOW_SSO_SIGNUP", "false").lower() != "true":
            raise HTTPException(403, "No account for this email; SSO signup disabled")
        # Create a personal tenant for first-time SSO
        tenant = Tenant(name=f"{full_name or email}'s Company")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        from db import seed_data
        seed_data(tenant.id, session=session)
        user = User(
            email=email,
            hashed_password=get_password_hash(_secrets.token_urlsafe(24)),
            full_name=full_name,
            tenant_id=tenant.id,
            role="owner",
            oauth_provider=provider,
            oauth_sub=str(sub) if sub else None,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    else:
        user.oauth_provider = provider
        user.oauth_sub = str(sub) if sub else user.oauth_sub
        user.last_login_at = datetime.utcnow()
        session.add(user)
        session.commit()

    if user.totp_enabled:
        # Still require TOTP after SSO
        partial = create_access_token(
            data={"sub": user.email, "tenant_id": user.tenant_id, "totp_pending": True},
            expires_delta=timedelta(minutes=5),
        )
        front = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").rstrip("/")
        return RedirectResponse(f"{front}/login?totp=1&partial={partial}")

    result = _issue_full_token(user, response)
    front = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").rstrip("/")
    # Pass token via fragment for SPA to pick up (cookie also set)
    return RedirectResponse(f"{front}/login?sso=1&token={result['access_token']}")
