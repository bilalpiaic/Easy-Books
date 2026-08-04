"""Accountant practice depth (#299) — firm dashboard, client onboarding, cross-client permissions.

Builds on TenantMembership / switch-tenant (#220). Snapshots are computed per
membership tenant_id without mutating the caller's active User.tenant_id.
"""
from __future__ import annotations

from datetime import date as DateType
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from db import seed_data
from models import (
    Bill,
    Invoice,
    PaymentAllocation,
    Tenant,
    TenantMembership,
    User,
    UserPermission,
)
from routers.common import CurrentUserDep, SessionDep, log_audit
from services.memberships import ensure_membership, get_membership, list_user_memberships
from services.money import D, ZERO, money
from services.permissions import PERMISSION_RESOURCES, _ROLE_DEFAULT, _rights_enabled

router = APIRouter(prefix="/api/practice", tags=["practice"])


def _outstanding_sum(session: Session, tenant_id: int, *, side: str, overdue_only: bool = False) -> Decimal:
    """Sum document outstanding (total − allocations) for a tenant."""
    today = DateType.today().isoformat()
    if side == "ar":
        open_statuses = ["draft", "sent", "overdue", "partial"]
        q = select(
            func.coalesce(
                func.sum(
                    Invoice.total
                    - func.coalesce(
                        select(func.sum(PaymentAllocation.amount))
                        .where(PaymentAllocation.invoice_id == Invoice.id)
                        .correlate(Invoice)
                        .scalar_subquery(),
                        0,
                    )
                ),
                0,
            )
        ).where(Invoice.tenant_id == tenant_id, Invoice.status.in_(open_statuses))
        if overdue_only:
            q = q.where((Invoice.status == "overdue") | (Invoice.due_date < today))
        return D(session.exec(q).one() or ZERO)
    open_statuses = ["draft", "received", "overdue", "partial"]
    q = select(
        func.coalesce(
            func.sum(
                Bill.total
                - func.coalesce(
                    select(func.sum(PaymentAllocation.amount))
                    .where(PaymentAllocation.bill_id == Bill.id)
                    .correlate(Bill)
                    .scalar_subquery(),
                    0,
                )
            ),
            0,
        )
    ).where(Bill.tenant_id == tenant_id, Bill.status.in_(open_statuses))
    if overdue_only:
        q = q.where((Bill.status == "overdue") | (Bill.due_date < today))
    return D(session.exec(q).one() or ZERO)


def _require_membership(session: Session, user_id: int, tenant_id: int) -> TenantMembership:
    m = get_membership(session, user_id, tenant_id)
    if not m:
        raise HTTPException(403, "Not a member of that client")
    return m


def _require_admin_membership(session: Session, user_id: int, tenant_id: int) -> TenantMembership:
    m = _require_membership(session, user_id, tenant_id)
    if m.role not in ("owner", "admin"):
        raise HTTPException(403, "Admin or owner membership required for this client")
    return m


@router.get("/dashboard")
def practice_dashboard(session: SessionDep, user: CurrentUserDep):
    """AR/AP/overdue snapshot for every client the user can access (#299)."""
    memberships = list_user_memberships(session, user.id)
    items = []
    for m in memberships:
        tid = m["tenant_id"]
        tenant = session.get(Tenant, tid)
        base = (tenant.base_currency if tenant else None) or "USD"
        ar = money(_outstanding_sum(session, tid, side="ar"))
        ap = money(_outstanding_sum(session, tid, side="ap"))
        ar_od = money(_outstanding_sum(session, tid, side="ar", overdue_only=True))
        ap_od = money(_outstanding_sum(session, tid, side="ap", overdue_only=True))
        items.append({
            **m,
            "is_active": tid == user.tenant_id,
            "currency": base,
            "ar_outstanding": ar,
            "ap_outstanding": ap,
            "ar_overdue": ar_od,
            "ap_overdue": ap_od,
        })
    return {"items": items, "total": len(items)}


class CreateClientBody(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    admin_email: Optional[str] = None
    business_model: str = "simple"


@router.post("/clients", status_code=201)
def create_client(session: SessionDep, user: CurrentUserDep, body: CreateClientBody):
    """Create a new client company, seed CoA, attach the caller as admin (#299)."""
    model = (body.business_model or "simple").lower()
    if model not in {"simple", "services", "trader", "manufacturing", "telecom_franchise"}:
        raise HTTPException(400, "Invalid business_model")

    name = body.company_name.strip()
    if not name:
        raise HTTPException(400, "company_name is required")

    import json as _json
    tenant = Tenant(
        name=name,
        business_model=model,
        enabled_modules=_json.dumps(["base"]),
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    seed_data(tenant.id, session=session)

    # Caller becomes admin of the new client (not owner — reserved for client staff)
    ensure_membership(
        session,
        user_id=user.id,
        tenant_id=tenant.id,
        role="admin",
        invited_by_id=user.id,
    )

    attached_user_id = None
    if body.admin_email:
        email = body.admin_email.strip().lower()
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            ensure_membership(
                session,
                user_id=existing.id,
                tenant_id=tenant.id,
                role="owner",
                invited_by_id=user.id,
            )
            attached_user_id = existing.id
        else:
            # Pending invite into the new tenant (reuse UserInvite via users router pattern)
            from models import UserInvite
            from datetime import datetime, timedelta
            import secrets
            inv = UserInvite(
                tenant_id=tenant.id,
                email=email,
                role="owner",
                token=secrets.token_urlsafe(32),
                invited_by_id=user.id,
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            session.add(inv)

    session.commit()
    log_audit(session, user, "CREATE", "practice_client", tenant.id, {"company_name": name})
    session.commit()

    return {
        "tenant_id": tenant.id,
        "name": tenant.name,
        "role": "admin",
        "attached_user_id": attached_user_id,
        "invited_email": body.admin_email.strip().lower() if body.admin_email and not attached_user_id else None,
    }


class PermissionUpdate(BaseModel):
    resource_key: str
    access_level: str  # none|view|edit|default


@router.get("/clients/{tenant_id}/permissions/{user_id}")
def get_client_permissions(
    tenant_id: int,
    user_id: int,
    session: SessionDep,
    user: CurrentUserDep,
):
    """Permission matrix for a user on a specific client (#299)."""
    _require_admin_membership(session, user.id, tenant_id)
    target_m = get_membership(session, user_id, tenant_id)
    if not target_m:
        raise HTTPException(404, "User is not a member of this client")
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")

    # Build effective map using membership role + tenant-scoped overrides
    module_on = _rights_enabled(tenant_id, session)
    perms = {}
    for key in PERMISSION_RESOURCES:
        override = session.exec(
            select(UserPermission).where(
                UserPermission.tenant_id == tenant_id,
                UserPermission.user_id == user_id,
                UserPermission.resource_key == key,
            )
        ).first()
        if override:
            perms[key] = override.access_level
        else:
            perms[key] = _ROLE_DEFAULT.get(target_m.role, "view")
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": target_m.role,
        "permissions": perms,
        "module_enabled": module_on,
        "my_data_only": target.my_data_only,
    }


@router.put("/clients/{tenant_id}/permissions/{user_id}")
def set_client_permissions(
    tenant_id: int,
    user_id: int,
    updates: List[PermissionUpdate],
    session: SessionDep,
    user: CurrentUserDep,
):
    """Upsert tenant-scoped permission overrides for a client member (#299)."""
    actor_m = _require_admin_membership(session, user.id, tenant_id)
    target_m = get_membership(session, user_id, tenant_id)
    if not target_m:
        raise HTTPException(404, "User is not a member of this client")
    if target_m.role == "owner" and actor_m.role != "owner":
        raise HTTPException(403, "Cannot modify owner permissions")

    for upd in updates:
        if upd.resource_key not in PERMISSION_RESOURCES:
            raise HTTPException(400, f"Unknown resource key: {upd.resource_key}")
        if upd.access_level not in ("none", "view", "edit", "default"):
            raise HTTPException(400, f"Invalid access_level: {upd.access_level}")

        existing = session.exec(
            select(UserPermission).where(
                UserPermission.tenant_id == tenant_id,
                UserPermission.user_id == user_id,
                UserPermission.resource_key == upd.resource_key,
            )
        ).first()

        if upd.access_level == "default":
            if existing:
                session.delete(existing)
        elif existing:
            existing.access_level = upd.access_level
            session.add(existing)
        else:
            session.add(UserPermission(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_key=upd.resource_key,
                access_level=upd.access_level,
            ))

    session.commit()
    log_audit(
        session, user, "UPDATE", "practice_permissions", user_id,
        {"tenant_id": tenant_id, "changes": len(updates)},
    )
    session.commit()
    return {"updated": len(updates), "tenant_id": tenant_id, "user_id": user_id}


@router.get("/clients/{tenant_id}/members")
def list_client_members(tenant_id: int, session: SessionDep, user: CurrentUserDep):
    """Members of a client company (for the practice permission matrix)."""
    _require_admin_membership(session, user.id, tenant_id)
    rows = session.exec(
        select(TenantMembership, User)
        .join(User, User.id == TenantMembership.user_id)
        .where(TenantMembership.tenant_id == tenant_id)
    ).all()
    return {
        "items": [
            {
                "user_id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": m.role,
            }
            for m, u in rows
        ]
    }
