"""Company settings (single key/value table per tenant) + business-model
switching + module activation."""
import json as _json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from db import MODULES_BY_MODEL, _coa_for
from models import Account, Settings, Tenant

from .common import AdminUserDep, CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
    fiscal_year_start: Optional[str] = None
    currency: Optional[str] = None
    email_notifications: Optional[str] = None
    invoice_prefix: Optional[str] = None
    bill_prefix: Optional[str] = None
    financial_statement_date: Optional[str] = None
    business_tagline: Optional[str] = None


@router.get("")
def get_settings(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id)).all()
    return {s.key: s.value for s in rows}


@router.patch("")
def update_settings(session: SessionDep, user: WriteUserDep, body: SettingsUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    for key, value in updates.items():
        row = session.exec(
            select(Settings).where(Settings.tenant_id == user.tenant_id, Settings.key == key)
        ).first()
        if row:
            row.value = value
        else:
            row = Settings(key=key, value=value, tenant_id=user.tenant_id)
        session.add(row)
    session.commit()
    return {"success": True}


# ── Business-model switching ─────────────────────────────────────────────────

_VALID_MODELS = {"simple", "services", "trader", "manufacturing", "telecom_franchise"}


class BusinessModelUpdate(BaseModel):
    business_model: str


@router.patch("/business-model")
def update_business_model(
    session: SessionDep, user: AdminUserDep, body: BusinessModelUpdate
):
    """Switch the tenant's business model. Admin-only.

    Behaviour:
      * Upgrade path (e.g. simple → manufacturing): adds the new CoA accounts
        that don't already exist for this tenant; never modifies or removes
        existing accounts (so historical reports stay valid).
      * Downgrade path (e.g. manufacturing → simple): updates the flag and
        enabled_modules list but LEAVES existing accounts in place — they
        still hold historical balances. Operator can manually deactivate.
      * Updates Tenant.enabled_modules to the new model's default modules.

    The currently-enabled modules can be customised separately via PATCH
    /api/settings/modules (manufacturing tenant can disable BoM, etc.).
    """
    model = (body.business_model or "").lower()
    if model not in _VALID_MODELS:
        raise HTTPException(
            400, f"business_model must be one of {sorted(_VALID_MODELS)}"
        )
    tenant = session.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    # Add any CoA accounts from the new template that don't already exist
    desired = _coa_for(model)
    existing_codes = {
        a.code for a in session.exec(
            select(Account).where(Account.tenant_id == tenant.id)
        ).all()
    }
    added: list[str] = []
    for code, name, atype, is_memo in desired:
        if code in existing_codes:
            continue
        session.add(Account(
            code=code, name=name, type=atype, is_memo=is_memo,
            tenant_id=tenant.id,
        ))
        added.append(code)

    tenant.business_model = model
    tenant.enabled_modules = _json.dumps(MODULES_BY_MODEL.get(model, []))
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return {
        "success": True,
        "business_model": model,
        "enabled_modules": _json.loads(tenant.enabled_modules),
        "accounts_added": added,
    }


# ── Module activation (independent of business_model) ───────────────────────


class ModulesUpdate(BaseModel):
    enabled_modules: List[str]


@router.patch("/modules")
def update_modules(
    session: SessionDep, user: AdminUserDep, body: ModulesUpdate
):
    """Override the enabled-modules list independent of business_model.

    Lets a 'simple' tenant turn on 'inventory' without becoming a 'trader',
    or a 'manufacturing' tenant disable 'bom' if they don't use it.
    """
    tenant = session.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    tenant.enabled_modules = _json.dumps(list(body.enabled_modules))
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return {"enabled_modules": _json.loads(tenant.enabled_modules)}
