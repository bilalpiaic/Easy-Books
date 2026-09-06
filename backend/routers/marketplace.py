"""Marketplace catalog + extension install API (#227).

GET  /api/marketplace/catalog
GET  /api/marketplace/extensions
POST /api/marketplace/extensions/{extension_id}/install
POST /api/marketplace/extensions/{extension_id}/uninstall
GET  /api/marketplace/boundary   — sandbox / permission docs payload for the UI
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from db import MODULE_REGISTRY
from models import Settings, Tenant
from routers.common import CurrentUserDep, SessionDep
from services.marketplace.catalog import resolve_catalog
from services.marketplace.install import (
    find_catalog_entry,
    installed_extensions,
    record_install,
    record_uninstall,
)

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

BOUNDARY_DOC = {
    "title": "Marketplace sandbox & permission boundary",
    "summary": (
        "Third-party listings are declarative manifests. Install never downloads "
        "or executes partner code inside the Easy-Books process."
    ),
    "rules": [
        "Manifest IDs must be partner.<publisher>.<slug>.",
        "Partner settings keys must be namespaced under ext.* — core keys are forbidden.",
        "requested_permissions are recorded for audit; they do not grant silent API access in v1.",
        "requires_modules may install first-party MODULE_REGISTRY packs only.",
        "Remote catalogs are allowlisted via MARKETPLACE_CATALOG_URL or Settings → marketplace_catalog_url (curated JSON only).",
        "No public unvetted upload path and no payments in v1.",
    ],
    "docs_path": "docs/MARKETPLACE.md",
}


def _tenant(session, user) -> Tenant:
    t = session.get(Tenant, user.tenant_id)
    if not t:
        raise HTTPException(404, "Tenant not found")
    return t


def _remote_url(session, tenant_id: int) -> str | None:
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id, Settings.key == "marketplace_catalog_url"
        )
    ).first()
    return row.value if row and row.value else None


@router.get("/boundary")
def get_boundary():
    return BOUNDARY_DOC


@router.get("/catalog")
def get_catalog(user: CurrentUserDep, session: SessionDep):
    tenant = _tenant(session, user)
    installed = {e.id for e in installed_extensions(tenant)}
    enabled = set()
    try:
        import json
        enabled = set(json.loads(tenant.enabled_modules or "[]"))
    except Exception:
        enabled = {"base"}
    enabled.add("base")

    entries = []
    try:
        catalog = resolve_catalog(remote_url=_remote_url(session, user.tenant_id))
    except Exception as exc:
        raise HTTPException(502, f"Remote catalog failed: {exc}") from exc

    for entry in catalog:
        m = entry.manifest
        fp = entry.first_party_module
        if fp:
            is_installed = fp in enabled
        else:
            is_installed = m.id in installed
        entries.append(
            {
                "id": m.id,
                "name": m.name,
                "version": m.version,
                "description": m.description,
                "publisher": m.publisher,
                "category": m.category,
                "icon": m.icon,
                "homepage": m.homepage,
                "docs_url": m.docs_url,
                "summary": entry.summary or m.description,
                "tags": entry.tags,
                "requires_modules": m.requires_modules,
                "requested_permissions": m.requested_permissions,
                "first_party_module": fp,
                "curated": m.curated,
                "installed": is_installed,
            }
        )
    return {"boundary": BOUNDARY_DOC, "entries": entries}


@router.get("/extensions")
def list_extensions(user: CurrentUserDep, session: SessionDep):
    tenant = _tenant(session, user)
    return [e.model_dump() for e in installed_extensions(tenant)]


@router.post("/extensions/{extension_id}/install")
def install_extension(extension_id: str, user: CurrentUserDep, session: SessionDep):
    if user.role not in ("admin", "owner"):
        raise HTTPException(403, "Only admin or owner can install marketplace extensions")

    tenant = _tenant(session, user)
    entry = find_catalog_entry(session, user.tenant_id, extension_id)
    if not entry:
        raise HTTPException(404, f"Unknown catalog entry: {extension_id!r}")

    # First-party bridge — reuse MODULE_REGISTRY install path
    if entry.first_party_module:
        fp = entry.first_party_module
        if fp not in MODULE_REGISTRY:
            raise HTTPException(400, f"first_party_module {fp!r} is not in MODULE_REGISTRY")
        from routers.modules import install_module as _install_fp

        # Call the same logic by invoking the dependency-injected function body
        # via a thin internal helper to avoid duplicating dep resolution.
        from routers import modules as modules_router

        result = modules_router.install_module(
            module_id=fp,
            current_user=user,
            session=session,
            seed_sample=False,
        )
        # Also record a marketplace bookmark so the catalog shows Installed
        record_install(session, tenant, entry.manifest, source="curated")
        return {
            "extension": entry.manifest.id,
            "first_party": result,
            "message": f"Installed first-party module {fp} via marketplace",
        }

    # Ensure required first-party modules exist
    missing = [m for m in entry.manifest.requires_modules if m not in MODULE_REGISTRY]
    if missing:
        raise HTTPException(400, f"Unknown requires_modules: {missing}")

    from routers import modules as modules_router
    import json

    enabled = set(json.loads(tenant.enabled_modules or "[]") or ["base"])
    for mid in entry.manifest.requires_modules:
        if mid not in enabled and mid != "base":
            modules_router.install_module(
                module_id=mid, current_user=user, session=session, seed_sample=False
            )
            # refresh tenant after nested commits
            session.refresh(tenant)

    installed = record_install(session, tenant, entry.manifest, source="curated")
    if entry.studio:
        from services.studio_bundle import apply_studio_bundle

        apply_studio_bundle(session, user, entry.manifest.id, entry.studio)
    return {
        "extension": installed.model_dump(),
        "message": (
            f"Installed {installed.name}. Permissions recorded; "
            "no partner code was executed."
        ),
        "boundary": BOUNDARY_DOC["summary"],
    }


@router.post("/extensions/{extension_id}/uninstall")
def uninstall_extension(extension_id: str, user: CurrentUserDep, session: SessionDep):
    if user.role not in ("admin", "owner"):
        raise HTTPException(403, "Only admin or owner can uninstall marketplace extensions")

    tenant = _tenant(session, user)
    entry = find_catalog_entry(session, user.tenant_id, extension_id)

    if entry and entry.first_party_module:
        from routers import modules as modules_router

        try:
            modules_router.uninstall_module(
                module_id=entry.first_party_module,
                current_user=user,
                session=session,
            )
        except HTTPException as exc:
            # If first-party uninstall is blocked (deps), still try to drop bookmark
            if exc.status_code not in (400, 409):
                raise

    ok = record_uninstall(session, tenant, extension_id)
    if not ok and not (entry and entry.first_party_module):
        raise HTTPException(404, f"Extension not installed: {extension_id!r}")
    from services.studio_bundle import archive_studio_bundle

    archive_studio_bundle(session, user.tenant_id, extension_id)
    return {"uninstalled": extension_id}
