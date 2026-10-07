"""Platform-ops tenant provision + complimentary plan (#430)."""
from __future__ import annotations

import html
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from db import seed_data
from models import Tenant, User, UserInvite
from services.disabled_modules import is_module_disabled
from services.email import send_email, smtp_configured
from services.entitlements import set_entitled
from services.memberships import ensure_membership
from services.saas import PLAN_LIMITS, apply_plan_defaults

_INVITE_TTL_DAYS = 7
_VALID_MODELS = {
    "simple", "services", "trader", "manufacturing", "telecom_franchise",
    "pra_einvoice", "hospital", "yarn_spinning", "textile_processing",
}


def _invite_url(token: str) -> str:
    origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").rstrip("/")
    return f"{origin}/accept-invite?token={token}"


def create_owner_invite(
    session: Session,
    *,
    tenant: Tenant,
    email: str,
    role: str = "owner",
    invited_by_id: Optional[int] = None,
    no_email: bool = False,
    company_name: str = "",
) -> dict:
    email = email.strip().lower()
    if not no_email and not smtp_configured():
        raise HTTPException(
            400,
            "SMTP_HOST is required to send the invite. Pass no_email=true for a dry hand-off.",
        )
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        ensure_membership(
            session,
            user_id=existing.id,
            tenant_id=tenant.id,
            role=role,
            invited_by_id=invited_by_id,
        )
        if existing.tenant_id is None or role == "owner":
            existing.tenant_id = tenant.id
            existing.role = role
            session.add(existing)
        session.commit()
        return {
            "attached": True,
            "user_id": existing.id,
            "email": existing.email,
            "role": role,
            "invite_token": None,
            "accept_path": None,
        }

    prior = session.exec(
        select(UserInvite).where(
            UserInvite.tenant_id == tenant.id,
            UserInvite.email == email,
            UserInvite.accepted_at == None,  # noqa: E711
        )
    ).all()
    for p in prior:
        session.delete(p)

    token = secrets.token_urlsafe(32)
    invite = UserInvite(
        tenant_id=tenant.id,
        email=email,
        role=role,
        token=token,
        invited_by_id=invited_by_id,
        expires_at=datetime.utcnow() + timedelta(days=_INVITE_TTL_DAYS),
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)

    if not no_email:
        company = html.escape(company_name or tenant.name)
        url_s = html.escape(_invite_url(token), quote=True)
        send_email(
            to=email,
            subject=f"You're invited to join {company} on Easy-Books",
            html_body=(
                f"<p>Hi,</p>"
                f"<p>You've been invited to join <strong>{company}</strong> "
                f"on Easy-Books as {html.escape(role)}.</p>"
                f"<p><a href='{url_s}'>Accept your invitation</a></p>"
                f"<p>This link expires in {_INVITE_TTL_DAYS} days.</p>"
            ),
        )
    return {
        "attached": False,
        "user_id": None,
        "email": email,
        "role": role,
        "invite_token": token,
        "accept_path": f"/accept-invite?token={token}",
        "expires_at": invite.expires_at.isoformat(),
    }


def provision_tenant(
    session: Session,
    *,
    company_name: str,
    owner_email: str,
    owner_name: str = "",
    plan: str = "starter",
    business_model: str = "simple",
    no_email: bool = False,
    modules: list[str] | None = None,
    invited_by_id: Optional[int] = None,
) -> dict:
    plan = (plan or "starter").lower()
    if plan not in PLAN_LIMITS:
        raise HTTPException(400, f"Unknown plan: {plan}")
    model = (business_model or "simple").lower()
    if model not in _VALID_MODELS:
        raise HTTPException(400, f"business_model must be one of {sorted(_VALID_MODELS)}")

    blocked = [m for m in (modules or []) if is_module_disabled(m)]
    if blocked:
        raise HTTPException(403, f"Disabled on this server: {', '.join(blocked)}")

    tenant = Tenant(
        name=company_name.strip(),
        business_model=model,
        enabled_modules=json.dumps(["base"]),
    )
    apply_plan_defaults(tenant, plan)
    tenant.subscription_status = "complimentary"
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    seed_data(tenant.id, session=session)

    if modules:
        set_entitled(tenant, modules)
        session.add(tenant)
        session.commit()
        session.refresh(tenant)

    invite = create_owner_invite(
        session,
        tenant=tenant,
        email=owner_email,
        role="owner",
        invited_by_id=invited_by_id,
        no_email=no_email,
        company_name=company_name,
    )
    return {
        "id": tenant.id,
        "name": tenant.name,
        "plan": tenant.plan,
        "business_model": tenant.business_model,
        "subscription_status": tenant.subscription_status,
        "owner_email": owner_email.strip().lower(),
        "owner_name": owner_name,
        "invite": invite,
    }


def apply_complimentary_plan(session: Session, tenant: Tenant, plan: str) -> Tenant:
    plan = (plan or "").lower()
    if plan not in PLAN_LIMITS:
        raise HTTPException(400, f"Unknown plan: {plan}")
    apply_plan_defaults(tenant, plan)
    tenant.subscription_status = "complimentary"
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant
