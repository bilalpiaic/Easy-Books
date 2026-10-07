"""Platform-ops tenant entitle API (#370 / #430).

Gated by ``OPS_ADMIN_EMAILS`` (comma-separated, fail-closed when empty).
Tenant ``role=owner`` is not enough — this is Easy-Books staff, not a
customer admin. Entitlements are written on the *target* tenant's audit log.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import select

from models import Tenant, User
from routers.common import CurrentUserDep, SessionDep, log_audit
from routers.modules import _get_enabled, install_module_for_tenant
from services.disabled_modules import is_module_disabled
from services.entitlements import entitled_ids, is_platform_ops, set_entitled
from services.marketplace.catalog import private_listing_ids, set_private_listings
from services.ops_provision import (
    apply_complimentary_plan,
    create_owner_invite,
    provision_tenant,
)
from services.security_policy import require_ops_totp
from services.tenant_import import import_tenant_from_sqlite

router = APIRouter(prefix="/api/ops", tags=["ops"])


def require_platform_ops(user: CurrentUserDep) -> User:
    if not is_platform_ops(user.email):
        raise HTTPException(403, "Platform ops only")
    if require_ops_totp() and not bool(getattr(user, "totp_enabled", False)):
        raise HTTPException(403, "Ops users must enable authenticator 2FA")
    return user


class EntitleBody(BaseModel):
    modules: List[str] = Field(default_factory=list)
    install: bool = False


class PrivateListingsBody(BaseModel):
    extension_ids: List[str] = Field(default_factory=list)


class ProvisionBody(BaseModel):
    company_name: str
    owner_email: str
    owner_name: str = ""
    plan: str = "starter"
    business_model: str = "simple"
    no_email: bool = False
    modules: List[str] = Field(default_factory=list)


class CompPlanBody(BaseModel):
    plan: str
    reason: str = Field(min_length=3)


class OpsInviteBody(BaseModel):
    email: str
    role: str = "owner"
    no_email: bool = False


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
        "marketplace_private": sorted(private_listing_ids(tenant)),
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

    blocked = [m for m in body.modules if is_module_disabled(m)]
    if blocked:
        raise HTTPException(403, f"Disabled on this server: {', '.join(blocked)}")

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


@router.put("/tenants/{tenant_id}/marketplace-private")
def put_marketplace_private(
    tenant_id: int,
    body: PrivateListingsBody,
    session: SessionDep,
    user: CurrentUserDep,
):
    """Grant private catalog listings (e.g. Weighbridge) to one tenant."""
    require_platform_ops(user)
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    before = private_listing_ids(tenant)
    granted = set_private_listings(tenant, body.extension_ids)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    after = set(granted)
    log_audit(
        session,
        user,
        action="UPDATE",
        entity_type="ops.marketplace_private",
        entity_id=tenant.id,
        detail={
            "extension_ids": granted,
            "added": sorted(after - before),
            "removed": sorted(before - after),
        },
        tenant_id=tenant.id,
    )
    session.commit()
    return _tenant_row(session, tenant)


@router.post("/tenants", status_code=201)
def post_tenant(body: ProvisionBody, session: SessionDep, user: CurrentUserDep):
    require_platform_ops(user)
    result = provision_tenant(
        session,
        company_name=body.company_name,
        owner_email=body.owner_email,
        owner_name=body.owner_name,
        plan=body.plan,
        business_model=body.business_model,
        no_email=body.no_email,
        modules=body.modules,
        invited_by_id=user.id,
    )
    log_audit(
        session,
        user,
        action="CREATE",
        entity_type="ops.provision",
        entity_id=result["id"],
        detail={
            "plan": result["plan"],
            "owner_email": result["owner_email"],
            "no_email": body.no_email,
            "modules": body.modules,
        },
        tenant_id=result["id"],
    )
    session.commit()
    tenant = session.get(Tenant, result["id"])
    row = _tenant_row(session, tenant)
    row["invite"] = result["invite"]
    row["subscription_status"] = result["subscription_status"]
    return row


@router.put("/tenants/{tenant_id}/plan")
def put_comp_plan(
    tenant_id: int,
    body: CompPlanBody,
    session: SessionDep,
    user: CurrentUserDep,
):
    """Complimentary plan — audited PUT, never a silent Stripe offline upgrade."""
    require_platform_ops(user)
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    before = tenant.plan
    apply_complimentary_plan(session, tenant, body.plan)
    log_audit(
        session,
        user,
        action="UPDATE",
        entity_type="ops.plan",
        entity_id=tenant.id,
        detail={"from": before, "to": tenant.plan, "reason": body.reason},
        tenant_id=tenant.id,
    )
    session.commit()
    row = _tenant_row(session, tenant)
    row["reason"] = body.reason
    return row


@router.post("/tenants/{tenant_id}/invite", status_code=201)
def post_ops_invite(
    tenant_id: int,
    body: OpsInviteBody,
    session: SessionDep,
    user: CurrentUserDep,
):
    require_platform_ops(user)
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    invite = create_owner_invite(
        session,
        tenant=tenant,
        email=body.email,
        role=body.role,
        invited_by_id=user.id,
        no_email=body.no_email,
        company_name=tenant.name,
    )
    log_audit(
        session,
        user,
        action="CREATE",
        entity_type="ops.invite",
        entity_id=tenant.id,
        detail={"email": body.email.strip().lower(), "role": body.role, "no_email": body.no_email},
        tenant_id=tenant.id,
    )
    session.commit()
    return invite


@router.post("/tenants/{tenant_id}/import")
def post_tenant_import(
    tenant_id: int,
    session: SessionDep,
    user: CurrentUserDep,
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    source_tenant_id: Optional[int] = Query(None),
):
    require_platform_ops(user)
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    suffix = Path(file.filename or "database.db").suffix or ".db"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = Path(tmp.name)
    try:
        result = import_tenant_from_sqlite(
            session,
            dest=tenant,
            sqlite_path=tmp_path,
            source_tenant_id=source_tenant_id,
            dry_run=dry_run,
            remap_user_id=user.id,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    log_audit(
        session,
        user,
        action="CREATE" if not dry_run else "VIEW",
        entity_type="ops.import",
        entity_id=tenant.id,
        detail={
            "dry_run": dry_run,
            "invoice_count_match": result.get("invoice_count_match"),
            "trial_balance_match": result.get("trial_balance_match"),
            "users_skipped": result.get("users_skipped"),
        },
        tenant_id=tenant.id,
    )
    session.commit()
    return result

