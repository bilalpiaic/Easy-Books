"""Module management — install, uninstall, and list available modules.

Each tenant maintains an `enabled_modules` JSON list (module IDs) and a
`module_meta` JSON dict (per-module billing/tier metadata).

Rules:
  - `base` is always enabled and cannot be uninstalled.
  - Installing a module installs its deps first (recursively).
  - Uninstalling a module is blocked when any installed module depends on it.
  - Only admin/owner can install or uninstall.
"""
import json
from datetime import datetime, timezone
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from db import get_session, MODULE_REGISTRY
from routers.common import CurrentUserDep

router = APIRouter(tags=["modules"])

SessionDep = Annotated[Session, Depends(get_session)]


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_enabled(tenant) -> list[str]:
    """Return the tenant's enabled module IDs.
    If enabled_modules contains legacy strings (pre-module-system format) that
    are not valid module IDs, fall back to deriving modules from business_model.
    """
    try:
        stored = json.loads(tenant.enabled_modules or "[]")
    except Exception:
        stored = []

    # Legacy check: old format had strings like "invoicing", "billing", etc.
    # If ALL stored values are unrecognised, derive from business_model.
    known = set(MODULE_REGISTRY.keys())
    if stored and not any(m in known for m in stored):
        from db import MODULES_BY_MODEL
        return MODULES_BY_MODEL.get(getattr(tenant, "business_model", "simple"), ["base"])

    return stored if stored else ["base"]


def _get_meta(tenant) -> dict:
    try:
        return json.loads(tenant.module_meta or "{}")
    except Exception:
        return {}


def _set_enabled(tenant, mods: list[str], session: Session) -> None:
    tenant.enabled_modules = json.dumps(sorted(set(mods)))
    session.add(tenant)
    session.commit()


def _set_meta(tenant, meta: dict, session: Session) -> None:
    tenant.module_meta = json.dumps(meta)
    session.add(tenant)
    session.commit()


def _all_deps(module_id: str, visited: set[str] | None = None) -> list[str]:
    """Return all transitive deps for module_id, deepest-first."""
    if visited is None:
        visited = set()
    if module_id in visited:
        return []
    visited.add(module_id)
    result: list[str] = []
    for dep in MODULE_REGISTRY.get(module_id, {}).get("deps", []):
        result.extend(_all_deps(dep, visited))
        if dep not in result:
            result.append(dep)
    return result


def _dependents_of(module_id: str, installed: list[str]) -> list[str]:
    """Return installed modules that have module_id in their dep tree."""
    return [
        m for m in installed
        if m != module_id and module_id in _all_deps(m)
    ]


def _purchase_store_docs(session: Session, tenant_id: int) -> dict[str, int]:
    """Blocking document counts for purchase_store uninstall."""
    from sqlalchemy import func
    from sqlmodel import select
    from models import (ComparativeStatement, GateInward, GateOutward,
                        PurchaseDemand, StoreIssue, VendorQuotation)
    counts = {}
    for label, model in (
        ("purchase demands", PurchaseDemand),
        ("vendor quotations", VendorQuotation),
        ("comparative statements", ComparativeStatement),
        ("gate inwards", GateInward),
        ("gate outwards", GateOutward),
        ("store issues", StoreIssue),
    ):
        n = session.exec(
            select(func.count(model.id)).where(model.tenant_id == tenant_id)
        ).one()
        if n:
            counts[label] = n
    return counts


# module_id → callable(session, tenant_id) → {doc label: count}; non-empty blocks uninstall
MODULE_UNINSTALL_GUARDS = {
    "purchase_store": _purchase_store_docs,
}


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/modules")
def list_modules(current_user: CurrentUserDep, session: SessionDep):
    """List all available modules with install status for the current tenant."""
    from sqlmodel import select
    from models import Tenant
    tenant = session.get(Tenant, current_user.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    enabled = set(_get_enabled(tenant))
    meta = _get_meta(tenant)

    result = []
    for mod_id, info in MODULE_REGISTRY.items():
        installed = mod_id in enabled
        mod_meta = meta.get(mod_id, {})
        result.append({
            "id":           mod_id,
            "label":        info["label"],
            "description":  info["description"],
            "category":     info["category"],
            "icon":         info["icon"],
            "deps":         info["deps"],
            "always":       info.get("always", False),
            "tier":         info.get("tier", "free"),
            "nav_sections": info.get("nav_sections", []),
            "installed":    installed,
            "installed_at": mod_meta.get("installed_at"),
            "expires_at":   mod_meta.get("expires_at"),
        })

    # Stable order: Core first, then alphabetical within category
    cat_order = {"Core": 0, "Accounting": 1, "Operations": 2, "HR": 3, "Industry": 4}
    result.sort(key=lambda m: (cat_order.get(m["category"], 99), m["label"]))
    return result


@router.post("/api/modules/{module_id}/install")
def install_module(
    module_id: str,
    current_user: CurrentUserDep,
    session: SessionDep,
    seed_sample: bool = Query(
        False,
        description="When true, seed idempotent sample rows for newly installed modules.",
    ),
):
    """Install a module (and its transitive deps) for the current tenant.
    Only admin/owner may install modules.
    """
    if current_user.role not in ("admin", "owner"):
        raise HTTPException(403, "Only admin or owner can install modules")
    if module_id not in MODULE_REGISTRY:
        raise HTTPException(404, f"Unknown module: {module_id!r}")

    from models import Tenant
    tenant = session.get(Tenant, current_user.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    enabled = _get_enabled(tenant)
    meta = _get_meta(tenant)

    if module_id in enabled:
        return {"enabled_modules": enabled, "message": f"{module_id} is already installed"}

    # Install all transitive deps first (deepest → shallowest → module itself)
    to_install = [d for d in _all_deps(module_id) if d not in enabled]
    to_install.append(module_id)

    now = datetime.now(timezone.utc).isoformat()
    for mid in to_install:
        if mid not in enabled:
            enabled.append(mid)
        meta.setdefault(mid, {})
        meta[mid]["tier"] = MODULE_REGISTRY[mid].get("tier", "free")
        meta[mid]["installed_at"] = meta[mid].get("installed_at", now)
        meta[mid].pop("expires_at", None)

    _set_enabled(tenant, enabled, session)
    _set_meta(tenant, meta, session)

    sample_results: list[dict] = []
    if "pra" in to_install:
        from services.module_sample_data import enable_pra_settings
        enable_pra_settings(session, current_user.tenant_id)

    if seed_sample:
        from services.module_sample_data import seed_module_sample
        for mid in to_install:
            sample_results.append(seed_module_sample(session, current_user, mid))

    return {
        "enabled_modules": sorted(set(enabled)),
        "installed": to_install,
        "message": f"Installed: {', '.join(to_install)}",
        "sample_data": sample_results,
    }


@router.post("/api/modules/{module_id}/uninstall")
def uninstall_module(module_id: str, current_user: CurrentUserDep, session: SessionDep):
    """Uninstall a module. Blocked if other installed modules depend on it,
    or if the module is marked `always` (e.g. base).
    Only admin/owner may uninstall modules.
    """
    if current_user.role not in ("admin", "owner"):
        raise HTTPException(403, "Only admin or owner can uninstall modules")
    if module_id not in MODULE_REGISTRY:
        raise HTTPException(404, f"Unknown module: {module_id!r}")
    if MODULE_REGISTRY[module_id].get("always"):
        raise HTTPException(400, f"Module {module_id!r} is a core module and cannot be uninstalled")

    from models import Tenant
    tenant = session.get(Tenant, current_user.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    enabled = _get_enabled(tenant)
    if module_id not in enabled:
        return {"enabled_modules": enabled, "message": f"{module_id} is not installed"}

    # Block if another installed module depends on this one
    blocking = _dependents_of(module_id, enabled)
    if blocking:
        names = [MODULE_REGISTRY.get(m, {}).get("label", m) for m in blocking]
        raise HTTPException(
            400,
            f"Cannot uninstall {module_id!r}: the following installed modules depend on it: "
            + ", ".join(names) + ". Uninstall those first."
        )

    guard = MODULE_UNINSTALL_GUARDS.get(module_id)
    if guard:
        blocking_docs = guard(session, current_user.tenant_id)
        if blocking_docs:
            detail = ", ".join(f"{n} {label}" for label, n in blocking_docs.items())
            raise HTTPException(
                400,
                f"Cannot uninstall {module_id!r}: this company has {detail}. "
                "The document trail must be kept — uninstall is only possible "
                "on a company with no purchase-chain documents."
            )

    enabled = [m for m in enabled if m != module_id]
    meta = _get_meta(tenant)
    meta.pop(module_id, None)

    _set_enabled(tenant, enabled, session)
    _set_meta(tenant, meta, session)

    return {
        "enabled_modules": sorted(enabled),
        "uninstalled": [module_id],
        "message": f"Uninstalled: {module_id}",
    }
