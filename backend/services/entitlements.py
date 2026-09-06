"""Module plan allowlists + per-tenant entitle flags (#370).

Install is allowed when ENFORCE_MODULE_PLANS is off (pytest / rollback), or
when the *requested* module is always-on, in the tenant plan allowlist, or
flagged ``module_meta[id].entitled``. Transitive deps ride along with an
allowed requested module so entitling ``spinning`` can install ``inventory``.
Uninstall never clears ``entitled``.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from models import Tenant

from db import MODULE_REGISTRY


# None = every MODULE_REGISTRY id.
PLAN_MODULES: dict[str, list[str] | None] = {
    "free": ["base"],
    "starter": ["base", "inventory", "pos"],
    "pro": [
        "base",
        "inventory",
        "pos",
        "purchase_store",
        "production",
        "hrm",
        "ai_assistant",
        "ecommerce",
        "sa_zatca",
        "in_gst",
        "eu_peppol",
        "uae_vat",
    ],
    "enterprise": None,
}

# Not on free/starter/pro unless module_meta[id].entitled or plan is enterprise.
INDUSTRY_PACKS: frozenset[str] = frozenset(
    {
        "spinning",
        "healthcare",
        "weaving",
        "weighbridge",
        "telecom",
        "textile_processing",
        "pra",
    }
)


def enforce_module_plans() -> bool:
    raw = (os.environ.get("ENFORCE_MODULE_PLANS") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


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


def plan_allows(tenant: Tenant, module_id: str) -> bool:
    plan = (tenant.plan or "free").strip().lower()
    allow = PLAN_MODULES.get(plan, PLAN_MODULES["free"])
    if allow is None:
        return module_id in MODULE_REGISTRY
    if module_id in INDUSTRY_PACKS and plan != "enterprise":
        return False
    return module_id in allow


PLAN_DENIED = "Not included in this plan. Contact Easy-Books."


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


def ops_admin_emails() -> set[str]:
    raw = os.environ.get("OPS_ADMIN_EMAILS") or ""
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def is_platform_ops(email: str | None) -> bool:
    if not email:
        return False
    return email.strip().lower() in ops_admin_emails()
