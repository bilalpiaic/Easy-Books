"""Tenant-side install / uninstall for marketplace extensions (#227)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from models import Settings, Tenant
from services.marketplace.catalog import CatalogEntry, resolve_catalog
from services.marketplace.manifest import ExtensionManifest, InstalledExtension

_EXT_META_KEY = "_extensions"


def _get_setting(session: Session, tenant_id: int, key: str, default: str = "") -> str:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row else default


def _meta(tenant: Tenant) -> dict[str, Any]:
    try:
        return json.loads(tenant.module_meta or "{}")
    except Exception:
        return {}


def _save_meta(session: Session, tenant: Tenant, meta: dict[str, Any]) -> None:
    tenant.module_meta = json.dumps(meta)
    session.add(tenant)
    session.commit()


def installed_extensions(tenant: Tenant) -> list[InstalledExtension]:
    meta = _meta(tenant)
    raw = meta.get(_EXT_META_KEY) or {}
    out: list[InstalledExtension] = []
    for ext_id, blob in raw.items():
        if not isinstance(blob, dict):
            continue
        try:
            out.append(
                InstalledExtension(
                    id=ext_id,
                    version=blob.get("version", "0.0.0"),
                    installed_at=blob.get("installed_at", ""),
                    publisher=blob.get("publisher", ""),
                    name=blob.get("name", ext_id),
                    requested_permissions=list(blob.get("requested_permissions") or []),
                    requires_modules=list(blob.get("requires_modules") or []),
                    docs_url=blob.get("docs_url"),
                    source=blob.get("source", "curated"),
                )
            )
        except Exception:
            continue
    out.sort(key=lambda e: e.name.lower())
    return out


def find_catalog_entry(
    session: Session, tenant_id: int, extension_id: str
) -> CatalogEntry | None:
    remote = _get_setting(session, tenant_id, "marketplace_catalog_url")
    for entry in resolve_catalog(remote_url=remote or None):
        if entry.manifest.id == extension_id:
            return entry
    return None


def record_install(
    session: Session,
    tenant: Tenant,
    manifest: ExtensionManifest,
    *,
    source: str = "curated",
) -> InstalledExtension:
    """Persist extension snapshot. Does not execute partner code."""
    meta = _meta(tenant)
    exts = dict(meta.get(_EXT_META_KEY) or {})
    now = datetime.now(timezone.utc).isoformat()
    exts[manifest.id] = {
        "version": manifest.version,
        "installed_at": now,
        "publisher": manifest.publisher,
        "name": manifest.name,
        "requested_permissions": list(manifest.requested_permissions),
        "requires_modules": list(manifest.requires_modules),
        "settings_keys": list(manifest.settings_keys),
        "webhook_events": list(manifest.webhook_events),
        "docs_url": manifest.docs_url,
        "source": source,
        "manifest": manifest.model_dump(),
    }
    meta[_EXT_META_KEY] = exts
    _save_meta(session, tenant, meta)
    return InstalledExtension(
        id=manifest.id,
        version=manifest.version,
        installed_at=now,
        publisher=manifest.publisher,
        name=manifest.name,
        requested_permissions=list(manifest.requested_permissions),
        requires_modules=list(manifest.requires_modules),
        docs_url=manifest.docs_url,
        source=source,  # type: ignore[arg-type]
    )


def record_uninstall(session: Session, tenant: Tenant, extension_id: str) -> bool:
    meta = _meta(tenant)
    exts = dict(meta.get(_EXT_META_KEY) or {})
    if extension_id not in exts:
        return False
    del exts[extension_id]
    meta[_EXT_META_KEY] = exts
    _save_meta(session, tenant, meta)
    return True
