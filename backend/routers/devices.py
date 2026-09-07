"""Device token registration for the Capacitor shell (#307).

POST   /api/devices          — upsert the current user's push token
GET    /api/devices          — list this user's tokens (hint only)
DELETE /api/devices/{id}     — deactivate (logout / uninstall)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from models import DeviceToken
from routers.common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/devices", tags=["devices"])

_PLATFORMS = ("ios", "android", "web")


class DeviceRegister(BaseModel):
    token: str = Field(min_length=8, max_length=4096)
    platform: str
    device_name: Optional[str] = Field(default=None, max_length=120)


def _serialize(row: DeviceToken) -> dict:
    hint = row.token[-8:] if row.token else ""
    return {
        "id": row.id,
        "platform": row.platform,
        "token_hint": hint,
        "device_name": row.device_name,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
    }


@router.get("")
def list_devices(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(DeviceToken).where(
            DeviceToken.tenant_id == user.tenant_id,
            DeviceToken.user_id == user.id,
            DeviceToken.is_active == True,  # noqa: E712
        )
    ).all()
    return {"items": [_serialize(r) for r in rows]}


@router.post("")
def register_device(body: DeviceRegister, session: SessionDep, user: CurrentUserDep):
    platform = (body.platform or "").strip().lower()
    if platform not in _PLATFORMS:
        raise HTTPException(400, f"platform must be one of {list(_PLATFORMS)}")
    token = body.token.strip()
    existing = session.exec(select(DeviceToken).where(DeviceToken.token == token)).first()
    now = datetime.utcnow()
    if existing:
        if existing.tenant_id != user.tenant_id:
            raise HTTPException(409, "This device token is already registered")
        existing.user_id = user.id
        existing.platform = platform
        existing.device_name = body.device_name or existing.device_name
        existing.is_active = True
        existing.last_seen_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return _serialize(existing)
    row = DeviceToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        platform=platform,
        token=token,
        device_name=body.device_name,
        is_active=True,
        created_at=now,
        last_seen_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize(row)


@router.delete("/{device_id}")
def deactivate_device(device_id: int, session: SessionDep, user: CurrentUserDep):
    row = session.get(DeviceToken, device_id)
    if row is None or row.tenant_id != user.tenant_id or row.user_id != user.id:
        raise HTTPException(404, "Device not found")
    row.is_active = False
    session.add(row)
    session.commit()
    return {"ok": True, "id": device_id}
