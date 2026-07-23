"""TenantMembership helpers for practice multi-client switcher (#220)."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from models import Settings, Tenant, TenantMembership, User


def ensure_membership(
    session: Session,
    *,
    user_id: int,
    tenant_id: int,
    role: str,
    invited_by_id: Optional[int] = None,
) -> TenantMembership:
    """Idempotent create/update of a membership row."""
    row = session.exec(
        select(TenantMembership).where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
        )
    ).first()
    if row:
        if role and row.role != role:
            row.role = role
            session.add(row)
        return row
    row = TenantMembership(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        invited_by_id=invited_by_id,
    )
    session.add(row)
    session.flush()
    return row


def get_membership(
    session: Session, user_id: int, tenant_id: int
) -> Optional[TenantMembership]:
    return session.exec(
        select(TenantMembership).where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
        )
    ).first()


def list_user_memberships(session: Session, user_id: int) -> list[dict]:
    """Serialize memberships with tenant display info for the switcher."""
    rows = session.exec(
        select(TenantMembership).where(TenantMembership.user_id == user_id)
        .order_by(TenantMembership.id)
    ).all()
    out: list[dict] = []
    for m in rows:
        tenant = session.get(Tenant, m.tenant_id)
        company = None
        if tenant:
            s = session.exec(
                select(Settings).where(
                    Settings.tenant_id == tenant.id,
                    Settings.key == "company_name",
                )
            ).first()
            company = (s.value if s and s.value else None) or tenant.name
        out.append({
            "tenant_id": m.tenant_id,
            "name": tenant.name if tenant else "",
            "company_name": company or "",
            "role": m.role,
            "plan": tenant.plan if tenant else "free",
            "is_suspended": bool(tenant.is_suspended) if tenant else False,
            "is_active": False,  # filled by caller against user.tenant_id
        })
    return out


def active_owner_count(session: Session, tenant_id: int) -> int:
    """Count active users with owner membership on this tenant."""
    rows = session.exec(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.role == "owner",
        )
    ).all()
    count = 0
    for m in rows:
        u = session.get(User, m.user_id)
        if u and u.is_active:
            count += 1
    return count
