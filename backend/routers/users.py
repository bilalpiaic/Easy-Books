"""Tenant user management — mounted at /api/users/*.

Admin+ only. Lets owners/admins list members, create accounts (with a
temporary password), change roles, activate/deactivate, and manage email
invitations. All operations are tenant-scoped: a caller can never see or
touch a user in another tenant.

Role guard rules:
  - Only an owner may grant or modify the `owner` role.
  - You cannot change your own role or deactivate yourself (prevents lockout).
  - The last active owner cannot be demoted or deactivated.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import func, select

from auth import get_password_hash
from models import Tenant, User, UserInvite

from .common import AdminUserDep, SessionDep

router = APIRouter(prefix="/api/users", tags=["users"])

_ROLES = ("viewer", "accountant", "admin", "owner")
_INVITE_TTL_DAYS = 7


# ── Helpers ───────────────────────────────────────────────────────────────────


def _serialize(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "phone": u.phone,
        "avatar_url": u.avatar_url,
        "role": u.role,
        "is_active": u.is_active,
        "must_change_password": u.must_change_password,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


def _validate_role(role: str) -> None:
    if role not in _ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {list(_ROLES)}")


def _guard_owner_grant(actor: User, role: str) -> None:
    """Only an owner may create/grant the owner role."""
    if role == "owner" and actor.role != "owner":
        raise HTTPException(status_code=403, detail="Only an owner can grant the owner role")


def _active_owner_count(session, tenant_id: int) -> int:
    return session.exec(
        select(func.count(User.id)).where(
            User.tenant_id == tenant_id, User.role == "owner", User.is_active == True,  # noqa: E712
        )
    ).one()


def _get_member(session, user_id: int, tenant_id: int) -> User:
    u = session.get(User, user_id)
    if u is None or u.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    return u


# ── Members ───────────────────────────────────────────────────────────────────


@router.get("")
def list_users(session: SessionDep, actor: AdminUserDep):
    users = session.exec(
        select(User).where(User.tenant_id == actor.tenant_id).order_by(User.created_at)
    ).all()
    return {"items": [_serialize(u) for u in users], "total": len(users)}


class UserCreate(BaseModel):
    email: str
    full_name: str
    role: str = "viewer"
    # Optional — if omitted, a temporary password is generated and returned once.
    password: Optional[str] = None


@router.post("", status_code=201)
def create_user(data: UserCreate, session: SessionDep, actor: AdminUserDep):
    _validate_role(data.role)
    _guard_owner_grant(actor, data.role)
    email = data.email.strip().lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    temp_password = data.password or secrets.token_urlsafe(9)
    if len(temp_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = User(
        email=email,
        hashed_password=get_password_hash(temp_password),
        full_name=data.full_name.strip(),
        tenant_id=actor.tenant_id,
        role=data.role,
        is_active=True,
        must_change_password=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    # Surface the temp password exactly once so the admin can relay it.
    return {**_serialize(user), "temporary_password": temp_password}


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.patch("/{user_id}")
def update_user(user_id: int, data: UserUpdate, session: SessionDep, actor: AdminUserDep):
    target = _get_member(session, user_id, actor.tenant_id)

    if data.full_name is not None:
        target.full_name = data.full_name.strip() or target.full_name

    if data.role is not None and data.role != target.role:
        _validate_role(data.role)
        if target.id == actor.id:
            raise HTTPException(status_code=400, detail="You cannot change your own role")
        # Granting owner, or changing an existing owner's role, requires owner.
        _guard_owner_grant(actor, data.role)
        if target.role == "owner" and actor.role != "owner":
            raise HTTPException(status_code=403, detail="Only an owner can change an owner's role")
        if target.role == "owner" and _active_owner_count(session, actor.tenant_id) <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last active owner")
        target.role = data.role

    if data.is_active is not None and data.is_active != target.is_active:
        if target.id == actor.id:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        if not data.is_active and target.role == "owner" and _active_owner_count(session, actor.tenant_id) <= 1:
            raise HTTPException(status_code=400, detail="Cannot deactivate the last active owner")
        target.is_active = data.is_active

    session.add(target)
    session.commit()
    session.refresh(target)
    return _serialize(target)


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, session: SessionDep, actor: AdminUserDep):
    """Issue a new temporary password for a member; forces a change at next login."""
    target = _get_member(session, user_id, actor.tenant_id)
    if target.role == "owner" and actor.role != "owner":
        raise HTTPException(status_code=403, detail="Only an owner can reset an owner's password")
    temp_password = secrets.token_urlsafe(9)
    target.hashed_password = get_password_hash(temp_password)
    target.must_change_password = True
    session.add(target)
    session.commit()
    return {"temporary_password": temp_password}


@router.delete("/{user_id}", status_code=200)
def deactivate_user(user_id: int, session: SessionDep, actor: AdminUserDep):
    """Soft-delete: deactivate the member. Hard deletion is avoided because
    audit-log and document rows reference the user id."""
    target = _get_member(session, user_id, actor.tenant_id)
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if target.role == "owner" and _active_owner_count(session, actor.tenant_id) <= 1:
        raise HTTPException(status_code=400, detail="Cannot deactivate the last active owner")
    target.is_active = False
    session.add(target)
    session.commit()
    return _serialize(target)


# ── Invites ───────────────────────────────────────────────────────────────────


class InviteCreate(BaseModel):
    email: str
    role: str = "viewer"


@router.get("/invites")
def list_invites(session: SessionDep, actor: AdminUserDep):
    now = datetime.utcnow()
    invites = session.exec(
        select(UserInvite).where(
            UserInvite.tenant_id == actor.tenant_id,
            UserInvite.accepted_at == None,  # noqa: E711
        ).order_by(UserInvite.created_at.desc())
    ).all()
    return {
        "items": [
            {
                "id": iv.id, "email": iv.email, "role": iv.role,
                "token": iv.token,
                "expires_at": iv.expires_at.isoformat(),
                "expired": iv.expires_at < now,
                "created_at": iv.created_at.isoformat() if iv.created_at else None,
            }
            for iv in invites
        ],
        "total": len(invites),
    }


@router.post("/invites", status_code=201)
def create_invite(data: InviteCreate, session: SessionDep, actor: AdminUserDep):
    _validate_role(data.role)
    _guard_owner_grant(actor, data.role)
    email = data.email.strip().lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    # Replace any prior pending invite for the same email in this tenant.
    prior = session.exec(
        select(UserInvite).where(
            UserInvite.tenant_id == actor.tenant_id,
            UserInvite.email == email,
            UserInvite.accepted_at == None,  # noqa: E711
        )
    ).all()
    for p in prior:
        session.delete(p)

    token = secrets.token_urlsafe(32)
    invite = UserInvite(
        tenant_id=actor.tenant_id, email=email, role=data.role, token=token,
        invited_by_id=actor.id,
        expires_at=datetime.utcnow() + timedelta(days=_INVITE_TTL_DAYS),
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)

    # Send invite email if SMTP is configured
    from services.email import send_email
    frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
    invite_url = f"{frontend_origin}/accept-invite?token={token}"
    tenant = session.get(Tenant, actor.tenant_id)
    company = tenant.name if tenant else "Easy-Books"
    send_email(
        to=email,
        subject=f"You're invited to join {company} on Easy-Books",
        html_body=(
            f"<p>Hi,</p>"
            f"<p>You've been invited to join <strong>{company}</strong> on Easy-Books as {data.role}.</p>"
            f"<p><a href='{invite_url}'>Accept your invitation</a></p>"
            f"<p>This link expires in {_INVITE_TTL_DAYS} days.</p>"
        ),
    )

    # Frontend composes the absolute URL; we return the relative accept path.
    return {
        "id": invite.id, "email": invite.email, "role": invite.role,
        "token": token, "accept_path": f"/accept-invite?token={token}",
        "expires_at": invite.expires_at.isoformat(),
    }


@router.delete("/invites/{invite_id}", status_code=204)
def revoke_invite(invite_id: int, session: SessionDep, actor: AdminUserDep):
    invite = session.get(UserInvite, invite_id)
    if invite is None or invite.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    session.delete(invite)
    session.commit()
