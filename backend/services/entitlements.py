"""Module plan allowlists + per-tenant entitle flags (#370).

Install is allowed when ENFORCE_MODULE_PLANS is off (pytest / rollback), or
when the *requested* module is always-on, in the tenant plan allowlist, or
flagged ``module_meta[id].entitled``. Transitive deps ride along with an
allowed requested module so entitling ``spinning`` can install ``inventory``.
Uninstall never clears ``entitled``.

Commercial catalog (single source for Billing & Add-ons):

* **Free** — Base Accounting only (signup / unpaid).
* **Starter** — shop books: stock, POS, weighbridge.
* **Pro** — operations SME: purchases, manufacturing, payroll, eCommerce,
  shop-floor PLC, AI, and every country pack (incl. Pakistan FBR).
* **Enterprise** — all first-party modules, including industry verticals.

Industry verticals are **add-on SKUs** on Starter/Pro (ops-entitle or a
standalone license ``addons`` list) and **included** on Enterprise.
Country packs are add-on SKUs on Starter and included from Pro.
Horizontal Pro modules (HR, manufacturing, …) are not sold à-la-carte —
upgrade the plan. Standalone copies settle plan + add-ons in the signed
install license, not via Stripe self-checkout.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from models import Tenant

from db import MODULE_REGISTRY


PLAN_ORDER = ("free", "starter", "pro", "enterprise")

# None = every MODULE_REGISTRY id.
PLAN_MODULES: dict[str, list[str] | None] = {
    "free": ["base"],
    "starter": ["base", "inventory", "pos", "weighbridge"],
    "pro": [
        "base",
        "inventory",
        "pos",
        "purchase_store",
        "production",
        "hrm",
        "ai_assistant",
        "ecommerce",
        "weighbridge",
        "shop_floor",
        "sa_zatca",
        "in_gst",
        "eu_peppol",
        "uae_vat",
        "uk_mtd",
        "my_invois",
        "pra",
    ],
    "enterprise": None,
}

PLAN_SUMMARIES: dict[str, str] = {
    "free": "Base accounting only",
    "starter": "Books, stock, POS, and weighbridge",
    "pro": "Operations, payroll, AI, and country packs",
    "enterprise": "All first-party add-ons, including industry verticals",
}

# Not on free/starter/pro unless module_meta[id].entitled or plan is enterprise.
INDUSTRY_PACKS: frozenset[str] = frozenset(
    {
        "spinning",
        "healthcare",
        "weaving",
        "telecom",
        "textile_processing",
    }
)

LOCALIZATION_PACKS: frozenset[str] = frozenset(
    {
        "pra",
        "uae_vat",
        "sa_zatca",
        "in_gst",
        "eu_peppol",
        "uk_mtd",
        "my_invois",
    }
)

ADDON_PRICE_INDUSTRY = 49
ADDON_PRICE_LOCALIZATION = 19


def enforce_module_plans() -> bool:
    raw = (os.environ.get("ENFORCE_MODULE_PLANS") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def settlement_mode() -> str:
    """``standalone`` (signed license) vs ``saas`` (Stripe checkout)."""
    raw = (os.environ.get("EB_STANDALONE") or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return "standalone"
    return "saas"


def _meta(tenant: Tenant) -> dict[str, Any]:
    try:
        data = json.loads(tenant.module_meta or "{}")
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def is_entitled(tenant: Tenant, module_id: str) -> bool:
    blob = _meta(tenant).get(module_id)
    if not isinstance(blob, dict):
        return False
    return blob.get("entitled") is True


def included_module_ids(plan: str) -> list[str]:
    key = (plan or "free").strip().lower()
    allow = PLAN_MODULES.get(key, PLAN_MODULES["free"])
    if allow is None:
        return sorted(MODULE_REGISTRY.keys())
    return list(allow)


def plan_allows_id(plan: str, module_id: str) -> bool:
    if module_id not in MODULE_REGISTRY:
        return False
    key = (plan or "free").strip().lower()
    allow = PLAN_MODULES.get(key, PLAN_MODULES["free"])
    if allow is None:
        return True
    if module_id in INDUSTRY_PACKS and key != "enterprise":
        return False
    return module_id in allow


def plan_allows(tenant: Tenant, module_id: str) -> bool:
    return plan_allows_id(tenant.plan or "free", module_id)


def min_plan_for(module_id: str) -> str:
    """Lowest plan that includes this module without an entitle override."""
    if module_id not in MODULE_REGISTRY:
        return "enterprise"
    if MODULE_REGISTRY[module_id].get("always"):
        return "free"
    for plan in PLAN_ORDER:
        if plan_allows_id(plan, module_id):
            return plan
    return "enterprise"


def addon_sku(module_id: str) -> dict[str, Any] | None:
    """Priced add-on (industry, or country pack on Starter). None = upgrade the plan."""
    if module_id not in MODULE_REGISTRY or MODULE_REGISTRY[module_id].get("always"):
        return None
    included_from = min_plan_for(module_id)
    if module_id in INDUSTRY_PACKS:
        return {
            "id": module_id,
            "label": MODULE_REGISTRY[module_id]["label"],
            "kind": "industry",
            "price": ADDON_PRICE_INDUSTRY,
            "included_from": included_from,
            "category": MODULE_REGISTRY[module_id].get("category", "Industry"),
        }
    if module_id in LOCALIZATION_PACKS:
        return {
            "id": module_id,
            "label": MODULE_REGISTRY[module_id]["label"],
            "kind": "localization",
            "price": ADDON_PRICE_LOCALIZATION,
            "included_from": included_from,
            "category": MODULE_REGISTRY[module_id].get("category", "Localization"),
        }
    return None


def module_commercial(module_id: str) -> dict[str, Any]:
    sku = addon_sku(module_id)
    included_from = min_plan_for(module_id)
    return {
        "included_from": included_from,
        "addon_price": sku["price"] if sku else None,
        "addon_kind": sku["kind"] if sku else None,
    }


PLAN_DENIED = "Not included in this plan. Contact Easy-Books."
STANDALONE_CHECKOUT_DENIED = (
    "Standalone copies settle the plan and add-ons through a signed install "
    "license. Send your Install ID to Easy-Books — do not self-upgrade here."
)


def is_allowed(tenant: Tenant, module_id: str) -> bool:
    """Commercial right to this module (plan allowlist, entitle flag, or always-on)."""
    if module_id not in MODULE_REGISTRY:
        return False
    if MODULE_REGISTRY[module_id].get("always"):
        return True
    return plan_allows(tenant, module_id) or is_entitled(tenant, module_id)


def can_install(tenant: Tenant, module_id: str) -> bool:
    """Whether the tenant may *request* install of this module id."""
    if module_id not in MODULE_REGISTRY:
        return False
    if MODULE_REGISTRY[module_id].get("always"):
        return True
    if not enforce_module_plans():
        return True
    return is_allowed(tenant, module_id)


def entitled_ids(tenant: Tenant) -> list[str]:
    meta = _meta(tenant)
    ids = [mid for mid, blob in meta.items() if isinstance(blob, dict) and blob.get("entitled") is True]
    if "base" not in ids:
        ids.append("base")
    return sorted({m for m in ids if m in MODULE_REGISTRY or m == "base"})


def extra_addon_ids(tenant: Tenant) -> list[str]:
    """Entitled modules that the current plan does not already include."""
    plan = tenant.plan or "free"
    return sorted(
        mid
        for mid in entitled_ids(tenant)
        if mid != "base" and not plan_allows_id(plan, mid)
    )


def set_entitled(tenant: Tenant, module_ids: list[str]) -> dict[str, Any]:
    """Replace the entitled set. ``base`` is always entitled. Unknown ids dropped."""
    wanted = {m for m in module_ids if m in MODULE_REGISTRY}
    wanted.add("base")
    meta = _meta(tenant)
    now = datetime.now(timezone.utc).isoformat()
    for mid in list(meta.keys()):
        blob = meta.get(mid)
        if not isinstance(blob, dict):
            continue
        if mid not in wanted and blob.get("entitled"):
            blob = dict(blob)
            blob.pop("entitled", None)
            blob.pop("entitled_at", None)
            if blob:
                meta[mid] = blob
            else:
                meta.pop(mid, None)
    for mid in wanted:
        blob = meta.get(mid)
        if not isinstance(blob, dict):
            blob = {}
        else:
            blob = dict(blob)
        if not blob.get("entitled"):
            blob["entitled_at"] = now
        blob["entitled"] = True
        meta[mid] = blob
    tenant.module_meta = json.dumps(meta)
    return meta


def grant_addons(tenant: Tenant, module_ids: list[str]) -> list[str]:
    """Union ``module_ids`` onto the existing entitled set. Returns the new set."""
    current = entitled_ids(tenant)
    wanted = [m for m in module_ids if m in MODULE_REGISTRY]
    set_entitled(tenant, current + wanted)
    return entitled_ids(tenant)


def commercial_catalog() -> dict[str, Any]:
    """Public Billing catalog: plans, included modules, priced add-on SKUs."""
    from services.saas import PLAN_LIMITS

    plans: dict[str, Any] = {}
    for plan in PLAN_ORDER:
        limits = PLAN_LIMITS.get(plan) or PLAN_LIMITS["free"]
        ids = included_module_ids(plan)
        plans[plan] = {
            **limits,
            "id": plan,
            "label": plan.capitalize(),
            "summary": PLAN_SUMMARIES.get(plan, ""),
            "includes": ids,
            "include_labels": [MODULE_REGISTRY[m]["label"] for m in ids if m in MODULE_REGISTRY],
        }
    addons = []
    for mid in sorted(MODULE_REGISTRY.keys()):
        sku = addon_sku(mid)
        if sku:
            addons.append(sku)
    return {
        "settlement": settlement_mode(),
        "plans": plans,
        "addons": addons,
    }


def apply_commercial(tenant: Tenant, plan: str, addons: list[str] | None = None) -> None:
    """Set plan limits and union extra add-on entitlements onto the tenant."""
    from services.saas import apply_plan_defaults

    apply_plan_defaults(tenant, plan)
    if addons:
        grant_addons(tenant, addons)


def apply_licensed_commercial(session) -> dict[str, Any]:
    """Apply the on-disk license ``plan`` + ``addons`` to the matching owner tenant."""
    from sqlmodel import select

    from models import User
    from services.standalone_license import licensed_commercial

    commercial = licensed_commercial()
    plan = commercial.get("plan")
    addons = commercial.get("addons") or []
    email = (commercial.get("email") or "").strip().lower()
    if not plan:
        return {"applied": False, "reason": "no_plan"}
    if not email:
        return {"applied": False, "reason": "no_email"}
    users = session.exec(select(User)).all()
    match = next(
        (u for u in users if str(u.email or "").strip().lower() == email),
        None,
    )
    if match is None:
        return {"applied": False, "reason": "no_user", "email": email}
    tenant = session.get(Tenant, match.tenant_id)
    if tenant is None:
        return {"applied": False, "reason": "no_tenant"}
    apply_commercial(tenant, plan, addons)
    session.add(tenant)
    return {
        "applied": True,
        "tenant_id": tenant.id,
        "plan": tenant.plan,
        "addons": extra_addon_ids(tenant),
    }


def ops_admin_emails() -> set[str]:
    raw = os.environ.get("OPS_ADMIN_EMAILS") or ""
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def is_platform_ops(email: str | None) -> bool:
    if not email:
        return False
    return email.strip().lower() in ops_admin_emails()
