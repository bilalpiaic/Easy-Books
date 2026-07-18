"""API key management (#113 part 2) — machine-to-machine auth.

Admin/owner only (AdminUserDep, matching the GET /api/ai/key-status
precedent — not the fine-grained perm_dep() system). The raw key is
returned exactly once from POST and never retrievable again: only its
SHA-256 hash is stored, plus a 4-char hint for the Settings list.
"""
import hashlib
import json
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import ApiKey
from .common import AdminUserDep, SessionDep, log_audit

router = APIRouter(prefix="/api/auth/keys", tags=["api-keys"])

KEY_PREFIX = "eb_live_"


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class ApiKeyCreate(BaseModel):
    name: str
    expires_at: Optional[datetime] = None
    scopes: list[str] = []


def _serialize(k: ApiKey) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "key_hint": k.key_hint,
        "scopes": json.loads(k.scopes or "[]"),
        "last_used": k.last_used,
        "expires_at": k.expires_at,
        "is_active": k.is_active,
        "created_at": k.created_at,
    }


@router.get("")
def list_keys(session: SessionDep, user: AdminUserDep):
    rows = session.exec(
        select(ApiKey)
        .where(ApiKey.tenant_id == user.tenant_id)
        .order_by(ApiKey.created_at.desc())
    ).all()
    return [_serialize(k) for k in rows]


@router.post("", status_code=201)
def create_key(session: SessionDep, user: AdminUserDep, body: ApiKeyCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Key name cannot be empty")
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    row = ApiKey(
        tenant_id=user.tenant_id,
        user_id=user.id,
        key_hash=hash_key(raw),
        key_hint=raw[-4:],
        name=name,
        scopes=json.dumps(body.scopes),
        expires_at=body.expires_at,
    )
    session.add(row)
    log_audit(session, user, "create", "api_key", detail={"name": name})
    session.commit()
    session.refresh(row)
    # The ONE place the raw key ever leaves the server. It is not persisted,
    # not logged, and cannot be shown again.
    return {**_serialize(row), "key": raw}


@router.delete("/{key_id}")
def revoke_key(session: SessionDep, user: AdminUserDep, key_id: int):
    row = session.exec(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "API key not found")
    # Soft revoke — the row stays for the audit trail; get_current_user
    # rejects inactive keys on every request, so this takes effect
    # immediately.
    row.is_active = False
    session.add(row)
    log_audit(session, user, "revoke", "api_key", entity_id=row.id, detail={"name": row.name})
    session.commit()
    return {"success": True}
