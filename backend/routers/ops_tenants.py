"""Platform-ops tenant entitle API (#370).

Gated by ``OPS_ADMIN_EMAILS`` (comma-separated, fail-closed when empty).
Tenant ``role=owner`` is not enough — this is Easy-Books staff, not a
customer admin. Entitlements are written on the *target* tenant's audit log.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import select

from models import Tenant, User
from routers.common import CurrentUserDep, SessionDep, log_audit
from routers.modules import _get_enabled, install_module_for_tenant
from services.entitlements import entitled_ids, is_platform_ops, set_entitled

router = APIRouter(prefix="/api/ops", tags=["ops"])


def require_platform_ops(user: CurrentUserDep) -> User:
    if not is_platform_ops(user.email):
        raise HTTPException(403, "Platform ops only")
    return user


class EntitleBody(BaseModel):
    modules: List[str] = Field(default_factory=list)
    install: bool = False


def _tenant_row(session, tenant: Tenant) -> dict:
    owner = session.exec(
        select(User).where(User.tenant_id == tenant.id, User.role == "owner")
    ).first()
    return {
        "id": tenant.id,
        "name": tenant.name,
        "plan": tenant.plan,
        "business_model": tenant.business_model,
        "enabled_modules": _get_enabled(tenant),
        "entitled_modules": entitled_ids(tenant),
        "owner_email": owner.email if owner else None,
    }


@router.get("/tenants")
def list_tenants(
    session: SessionDep,
    user: CurrentUserDep,
    q: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    require_platform_ops(user)
    filters = []
    if q and q.strip():
        filters.append(Tenant.name.ilike(f"%{q.strip()}%"))
    total_n = session.exec(
        select(func.count(Tenant.id)).where(*filters) if filters else select(func.count(Tenant.id))
    ).one()
    query = select(Tenant)
    if filters:
        query = query.where(*filters)
    rows = session.exec(query.order_by(Tenant.id).offset(skip).limit(limit)).all()
    return {"total": int(total_n or 0), "items": [_tenant_row(session, t) for t in rows]}


@router.get("/tenants/{tenant_id}")
def get_tenant(tenant_id: int, session: SessionDep, user: CurrentUserDep):
    require_platform_ops(user)
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return _tenant_row(session, tenant)


@router.put("/tenants/{tenant_id}/entitled")
def put_entitled(
    tenant_id: int,
    body: EntitleBody,
    session: SessionDep,
    user: CurrentUserDep,
):
    require_platform_ops(user)
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    before = set(entitled_ids(tenant))
    set_entitled(tenant, body.modules)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    after = set(entitled_ids(tenant))
    added = sorted(after - before)
    removed = sorted(before - after)

    installed: list[dict] = []
    if body.install:
        for mid in sorted(after):
            if mid == "base":
                continue
            result = install_module_for_tenant(
                session, tenant, user, mid, seed_sample=False, check_entitlement=True,
            )
            session.refresh(tenant)
            installed.append({
                "module_id": mid,
                "message": result.get("message"),
                "installed": result.get("installed"),
            })

    action = "ops.revoke" if removed and not added else "ops.entitle"
    log_audit(
        session,
        user,
        action="UPDATE",
        entity_type=action,
        entity_id=tenant.id,
        detail={
            "modules": sorted(after),
            "added": added,
            "removed": removed,
            "install": body.install,
        },
        tenant_id=tenant.id,
    )
    session.commit()
    row = _tenant_row(session, tenant)
    row["added"] = added
    row["removed"] = removed
    row["installed"] = installed
    return row
