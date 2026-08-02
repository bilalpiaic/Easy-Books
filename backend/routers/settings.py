"""Company settings (single key/value table per tenant) + business-model
switching + module activation."""
import json as _json
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import select

from db import MODULES_BY_MODEL, _coa_for
from models import Account, Settings, Tenant
from services.ai_providers import AI_SECRET_SETTINGS_KEYS
from services.whatsapp import WA_SECRET_SETTINGS_KEYS, status_payload as wa_status_payload

from .common import AdminUserDep, CurrentUserDep, SessionDep, WriteUserDep, mark_onboarding_step

# Secrets that must never leave GET /api/settings unredacted.
SECRET_SETTINGS_KEYS = AI_SECRET_SETTINGS_KEYS | WA_SECRET_SETTINGS_KEYS | {"uae_api_key"}

router = APIRouter(prefix="/api/settings", tags=["settings"])

from local_config import uploads_dir
UPLOADS_DIR = uploads_dir()


class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
    fiscal_year_start: Optional[str] = None
    # Report period presets (#141): first day of week for This/Last/Next Week
    week_start_day: Optional[str] = None
    currency: Optional[str] = None
    email_notifications: Optional[str] = None
    # Days between automated overdue-invoice reminder emails per tenant
    # (services/overdue.py); only takes effect when email_notifications="true"
    overdue_reminder_interval_days: Optional[str] = None
    # In-app Alerts bell (ops alerts for staff). Default on when unset.
    in_app_alerts: Optional[str] = None
    invoice_prefix: Optional[str] = None
    bill_prefix: Optional[str] = None
    financial_statement_date: Optional[str] = None
    business_tagline: Optional[str] = None
    # Company profile / address
    logo_url: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    # Default GL accounts (stored as account codes e.g. "1100")
    default_ar_account: Optional[str] = None
    default_ap_account: Optional[str] = None
    default_revenue_account: Optional[str] = None
    default_cogs_account: Optional[str] = None
    default_mfg_labour_account: Optional[str] = None
    default_mfg_overhead_account: Optional[str] = None
    default_scrap_expense_account: Optional[str] = None
    # Document number formats (tokens: {prefix} {seq:04d} {YYYY} {MM})
    invoice_number_format: Optional[str] = None
    bill_number_format: Optional[str] = None
    # Onboarding
    onboarding_dismissed: Optional[str] = None
    # IAS 2.25: inventory cost method — "wavg" or "fifo"
    cost_method: Optional[str] = None
    # Inventory: block sales that would drive stock negative ("true"/"false")
    block_negative_stock: Optional[str] = None
    # Inventory depth (#257)
    inventory_landed_cost_enabled: Optional[str] = None  # "true" | "false"
    inventory_lot_tracking_enabled: Optional[str] = None
    inventory_nrv_enabled: Optional[str] = None
    # Purchases: require Demand → Comparative chain before a PO ("true"/"false")
    require_purchase_chain: Optional[str] = None
    # Purchases: require Gate Inward coverage before billing a PO ("true"/"false")
    require_gate_inward: Optional[str] = None
    # UI density preference ("comfortable" or "compact")
    ui_density: Optional[str] = None
    # Amount display precision ("2" or "4")
    decimal_places: Optional[str] = None
    user_rights_enabled: Optional[str] = None  # "true" | "false"
    # Approvals SoD (#269) — default on when unset; creator cannot approve own submit
    approvals_block_self_approval: Optional[str] = None  # "true" | "false"
    # Customer/vendor portal custom domain (#270) — e.g. portal.acme.com or full https URL
    portal_custom_domain: Optional[str] = None
    # Appearance
    app_theme: Optional[str] = None   # "light" | "dark" | "system"
    color_theme: Optional[str] = None  # "gold" | "blue" | "green" | "rose" | "slate"
    app_language: Optional[str] = None  # "en" | "ur" | "zh"
    # PRA e-Invoice (Punjab Revenue Authority) — Pakistan tax compliance
    pra_enabled: Optional[str] = None        # "true" | "false"
    pra_ntn: Optional[str] = None            # Business PNTN / NTN
    pra_pos_id: Optional[str] = None         # 6-digit POS ID from PRA portal
    pra_api_token: Optional[str] = None      # Production Bearer token (kept secret)
    pra_sandbox_mode: Optional[str] = None   # "true" = use sandbox endpoint
    # UAE VAT e-Invoice — FTA localization pack
    uae_vat_enabled: Optional[str] = None
    uae_trn: Optional[str] = None            # 15-digit Tax Registration Number
    uae_legal_name: Optional[str] = None
    uae_api_key: Optional[str] = None        # future live connector (write-only)
    uae_sandbox_mode: Optional[str] = None
    # Marketplace (#227) — optional curated remote catalog URL (https only)
    marketplace_catalog_url: Optional[str] = None
    # AI assistant (#117) — key values are write-only; GET redacts them
    ai_api_key_anthropic: Optional[str] = None
    ai_api_key_openai: Optional[str] = None
    ai_api_key_gemini: Optional[str] = None
    ai_default_model: Optional[str] = None
    ai_rate_limit_per_hour: Optional[str] = None
    # Ollama (self-hosted, #163 follow-up) -- not a secret, no redaction needed
    ai_ollama_base_url: Optional[str] = None
    ai_ollama_models: Optional[str] = None  # comma-separated tags
    # WhatsApp Business API — Meta Cloud (#237); token is write-only
    wa_meta_access_token: Optional[str] = None
    wa_meta_phone_number_id: Optional[str] = None
    wa_meta_template_name: Optional[str] = None
    wa_meta_template_lang: Optional[str] = None


@router.get("")
def get_settings(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id)).all()
    out = {s.key: s.value for s in rows}
    tenant = session.get(Tenant, user.tenant_id)
    if tenant:
        out["business_model"] = tenant.business_model
        out["cost_method"] = tenant.cost_method or "wavg"
    # Redact secret AI / WhatsApp keys
    for k in SECRET_SETTINGS_KEYS:
        out.pop(k, None)
    return out


@router.get("/whatsapp-status")
def get_whatsapp_status(session: SessionDep, user: AdminUserDep):
    """Masked Meta WhatsApp config for Settings UI (admin/owner). Never returns the raw token."""
    return wa_status_payload(session, user.tenant_id)


@router.patch("")
def update_settings(session: SessionDep, user: WriteUserDep, body: SettingsUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}

    # AI / WhatsApp credentials — restrict writes to admin/owner even though the
    # rest of this endpoint is accountant+.
    if any(k in SECRET_SETTINGS_KEYS for k in updates) and user.role not in ("admin", "owner"):
        raise HTTPException(403, "Only admin or owner can set integration API credentials")

    # Some settings also live on the Tenant model (not just the KV table)
    tenant = session.get(Tenant, user.tenant_id)

    if "cost_method" in updates:
        cm = updates.pop("cost_method")
        if cm not in ("wavg", "fifo"):
            raise HTTPException(400, "cost_method must be 'wavg' or 'fifo'")
        if tenant:
            tenant.cost_method = cm
            session.add(tenant)

    if "ui_density" in updates:
        ud = updates["ui_density"]
        if ud not in ("comfortable", "compact"):
            raise HTTPException(400, "ui_density must be 'comfortable' or 'compact'")
        # (No pop — ui_density is stored in the KV settings table, not on Tenant)

    if "decimal_places" in updates:
        dp = updates["decimal_places"]
        if dp not in ("2", "4"):
            raise HTTPException(400, "decimal_places must be '2' or '4'")

    if "user_rights_enabled" in updates:
        if updates["user_rights_enabled"] not in ("true", "false"):
            raise HTTPException(400, "user_rights_enabled must be 'true' or 'false'")

    if "app_theme" in updates:
        if updates["app_theme"] not in ("light", "dark", "system"):
            raise HTTPException(400, "app_theme must be 'light', 'dark', or 'system'")

    if "color_theme" in updates:
        if updates["color_theme"] not in ("gold", "blue", "green", "rose", "slate"):
            raise HTTPException(400, "color_theme must be one of: gold, blue, green, rose, slate")

    if "app_language" in updates:
        if updates["app_language"] not in ("en", "ur", "zh"):
            raise HTTPException(400, "app_language must be 'en', 'ur', or 'zh'")

    # Keep Tenant.base_currency in sync with the "currency" KV setting
    if "currency" in updates and tenant:
        tenant.base_currency = updates["currency"]
        session.add(tenant)

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


@router.post("/logo")
async def upload_logo(session: SessionDep, user: WriteUserDep, file: UploadFile = File(...)):
    """Upload a company logo. Stores as /uploads/{tenant_id}/{uuid}.{ext}."""
    allowed = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Only PNG, JPEG, GIF, WebP, SVG allowed")
    ext = Path(file.filename or "logo.png").suffix or ".png"
    tenant_dir = UPLOADS_DIR / str(user.tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = tenant_dir / fname
    contents = await file.read()
    dest.write_bytes(contents)
    logo_url = f"/uploads/{user.tenant_id}/{fname}"
    # Persist logo_url in settings
    row = session.exec(
        select(Settings).where(Settings.tenant_id == user.tenant_id, Settings.key == "logo_url")
    ).first()
    if row:
        row.value = logo_url
    else:
        row = Settings(key="logo_url", value=logo_url, tenant_id=user.tenant_id)
    session.add(row)
    mark_onboarding_step(session, user.tenant_id, "company_profile")
    session.commit()
    return {"logo_url": logo_url}


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

    # Add any CoA accounts from the new template that don't already exist.
    # _coa_for now yields 6-tuples (incl. parent_code + is_group); wire parents
    # in a second pass (new leaves reference group parents that already exist).
    desired = _coa_for(model)
    by_code = {
        a.code: a for a in session.exec(
            select(Account).where(Account.tenant_id == tenant.id)
        ).all()
    }
    added: list[str] = []
    for code, name, atype, is_memo, parent_code, is_group in desired:
        if code in by_code:
            continue
        acc = Account(
            code=code, name=name, type=atype, is_memo=is_memo,
            is_group=is_group, tenant_id=tenant.id,
        )
        session.add(acc)
        by_code[code] = acc
        added.append(code)
    session.flush()
    for code, name, atype, is_memo, parent_code, is_group in desired:
        if parent_code and code in by_code and by_code[code].parent_id is None:
            parent = by_code.get(parent_code)
            if parent is not None:
                by_code[code].parent_id = parent.id

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
