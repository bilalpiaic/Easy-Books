"""Curated third-party marketplace catalog (#227).

The default catalog is shipped in-repo (vetted). Operators may point
``MARKETPLACE_CATALOG_URL`` (env) or tenant setting ``marketplace_catalog_url``
at a JSON array of CatalogEntry objects — still curated by whoever hosts it;
there is no public unvetted upload path.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

import httpx

from models import Tenant
from services.marketplace.manifest import CatalogEntry, ExtensionManifest

WEIGHBRIDGE_ID = "partner.easybooks.weighbridge"
_PRIVATE_META_KEY = "_marketplace_private"
# Mill models see the bundled Weighbridge card without a seed/ops grant
# (demo mills created by db.py never got module_meta until this backfill).
MILL_WEIGHBRIDGE_MODELS = frozenset({"manufacturing", "yarn_spinning"})


def mill_tenant_sees_weighbridge(tenant: Tenant) -> bool:
    """True for mill companies (and anyone who installed spinning)."""
    if (tenant.business_model or "") in MILL_WEIGHBRIDGE_MODELS:
        return True
    try:
        from routers.modules import _get_enabled
        return "spinning" in _get_enabled(tenant)
    except Exception:
        return False


def private_listing_ids(tenant: Tenant) -> set[str]:
    """Ops/seed grants stored on tenant.module_meta (not owner-writable)."""
    try:
        meta = json.loads(tenant.module_meta or "{}")
    except Exception:
        return set()
    if not isinstance(meta, dict):
        return set()
    raw = meta.get(_PRIVATE_META_KEY) or []
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if x}


def grant_private_listing(tenant: Tenant, extension_id: str) -> None:
    """Record that this tenant may see a private catalog row. Idempotent."""
    try:
        meta = json.loads(tenant.module_meta or "{}")
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    ids = [str(x) for x in (meta.get(_PRIVATE_META_KEY) or []) if x]
    if extension_id not in ids:
        ids.append(extension_id)
    meta[_PRIVATE_META_KEY] = ids
    tenant.module_meta = json.dumps(meta)


def set_private_listings(tenant: Tenant, extension_ids: list[str]) -> list[str]:
    """Replace the private-listing grant set (ops)."""
    try:
        meta = json.loads(tenant.module_meta or "{}")
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    cleaned = sorted({str(x) for x in extension_ids if x})
    if cleaned:
        meta[_PRIVATE_META_KEY] = cleaned
    else:
        meta.pop(_PRIVATE_META_KEY, None)
    tenant.module_meta = json.dumps(meta)
    return cleaned


def _env_private_tenant_ids(extension_id: str) -> set[int]:
    raw = (os.environ.get("MARKETPLACE_PRIVATE_AUDIENCE") or "").strip()
    if not raw:
        return set()
    try:
        data = json.loads(raw)
    except Exception:
        return set()
    if not isinstance(data, dict):
        return set()
    ids = data.get(extension_id) or []
    out: set[int] = set()
    for i in ids:
        try:
            out.add(int(i))
        except (TypeError, ValueError):
            continue
    return out


def visible_to(entry: CatalogEntry, tenant: Tenant) -> bool:
    """Server-side catalog gate (#371). Never rely on the React tab alone."""
    audience = entry.audience or "public"
    if audience == "public":
        return True
    if audience == "private":
        tid = tenant.id
        if tid is None:
            return False
        allowed = {int(i) for i in (entry.visible_to_tenant_ids or [])}
        allowed |= _env_private_tenant_ids(entry.manifest.id)
        if int(tid) in allowed:
            return True
        if entry.manifest.id == WEIGHBRIDGE_ID and mill_tenant_sees_weighbridge(tenant):
            return True
        return entry.manifest.id in private_listing_ids(tenant)
    if audience == "entitled":
        mid = entry.entitled_module
        if not mid:
            return False
        return _entitled_or_installed(tenant, mid)
    return False


def _entitled_or_installed(tenant: Tenant, module_id: str) -> bool:
    from routers.modules import _get_enabled
    from services.entitlements import is_allowed, is_entitled

    if module_id in _get_enabled(tenant):
        return True
    return is_entitled(tenant, module_id) or is_allowed(tenant, module_id)

# ── shipped curated listings ──────────────────────────────────────────────────

_CURATED: list[dict[str, Any]] = [
    {
        "summary": "Nightly CSV export of posted invoices to an SFTP drop (metadata-only v1).",
        "tags": ["export", "csv", "accountant"],
        "manifest": {
            "id": "partner.easybooks.invoice-csv-export",
            "name": "Invoice CSV Export",
            "version": "1.0.0",
            "description": (
                "Registers a partner export profile for posted invoices. "
                "v1 records the install + requested permissions; the scheduled "
                "runner lands in a follow-up."
            ),
            "publisher": "Easy-Books Partners",
            "category": "Integrations",
            "icon": "FileText",
            "homepage": "https://github.com/bilalpiaic/Easy-Books",
            "docs_url": "https://github.com/bilalpiaic/Easy-Books/blob/main/docs/MARKETPLACE.md",
            "requires_modules": ["base"],
            "requested_permissions": ["read_invoices", "read_customers"],
            "settings_keys": ["ext.invoice_csv.sftp_host", "ext.invoice_csv.path"],
            "webhook_events": [],
            "curated": True,
        },
    },
    {
        "summary": "Receive payment.received / invoice.posted webhooks into your middleware.",
        "tags": ["webhooks", "automation"],
        "manifest": {
            "id": "partner.easybooks.webhook-bridge",
            "name": "Webhook Bridge",
            "version": "1.0.0",
            "description": (
                "Marks the tenant as opted-in for partner webhook delivery. "
                "Configure endpoints under Settings → Webhooks; this listing "
                "documents the permission boundary for external consumers."
            ),
            "publisher": "Easy-Books Partners",
            "category": "Integrations",
            "icon": "Radio",
            "homepage": "https://github.com/bilalpiaic/Easy-Books",
            "docs_url": "https://github.com/bilalpiaic/Easy-Books/blob/main/docs/MARKETPLACE.md",
            "requires_modules": ["base"],
            "requested_permissions": ["write_webhooks", "read_invoices", "read_bills"],
            "settings_keys": ["ext.webhook_bridge.note"],
            "webhook_events": ["invoice.posted", "payment.received", "bill.posted"],
            "curated": True,
        },
    },
    {
        "summary": "Surface the PRA e-Invoice first-party module from the marketplace.",
        "tags": ["pakistan", "tax", "first-party"],
        "first_party_module": "pra",
        "manifest": {
            "id": "partner.easybooks.pra-bridge",
            "name": "PRA e-Invoice (first-party)",
            "version": "1.0.0",
            "description": (
                "Installs the built-in Punjab Revenue Authority module. "
                "Listed here so the marketplace can deep-link first-party packs."
            ),
            "publisher": "Easy-Books",
            "category": "Industry",
            "icon": "FileCheck",
            "requires_modules": ["pra"],
            "requested_permissions": ["read_invoices"],
            "settings_keys": [],
            "curated": True,
        },
    },
    {
        "summary": "Surface the UAE VAT first-party localization pack.",
        "tags": ["uae", "tax", "first-party"],
        "first_party_module": "uae_vat",
        "manifest": {
            "id": "partner.easybooks.uae-vat-bridge",
            "name": "UAE VAT e-Invoice (first-party)",
            "version": "1.0.0",
            "description": (
                "Installs the built-in UAE VAT localization module "
                "(tax codes, CoA leaves, sandbox FTA stub)."
            ),
            "publisher": "Easy-Books",
            "category": "Industry",
            "icon": "Landmark",
            "requires_modules": ["uae_vat"],
            "requested_permissions": ["read_invoices"],
            "settings_keys": [],
            "curated": True,
        },
    },
    {
        "summary": "Surface the Saudi ZATCA first-party localization pack.",
        "tags": ["saudi", "zatca", "tax", "first-party"],
        "first_party_module": "sa_zatca",
        "manifest": {
            "id": "partner.easybooks.sa-zatca-bridge",
            "name": "Saudi ZATCA e-Invoice (first-party)",
            "version": "1.0.0",
            "description": (
                "Installs the built-in KSA ZATCA Phase 2 sandbox clear/report pack."
            ),
            "publisher": "Easy-Books",
            "category": "Localization",
            "icon": "Landmark",
            "requires_modules": ["sa_zatca"],
            "requested_permissions": ["read_invoices"],
            "settings_keys": [],
            "curated": True,
        },
    },
    {
        "summary": "Surface the Peppol / EU VAT first-party localization pack.",
        "tags": ["eu", "peppol", "vat", "ubl", "first-party"],
        "first_party_module": "eu_peppol",
        "manifest": {
            "id": "partner.easybooks.eu-peppol-bridge",
            "name": "Peppol / EU VAT e-Invoice (first-party)",
            "version": "1.0.0",
            "description": (
                "Installs the built-in Peppol BIS Billing 3.0 UBL export + Access Point sandbox pack."
            ),
            "publisher": "Easy-Books",
            "category": "Localization",
            "icon": "Globe",
            "requires_modules": ["eu_peppol"],
            "requested_permissions": ["read_invoices"],
            "settings_keys": [],
            "curated": True,
        },
    },
    {
        "summary": "Mill weighbridge overlay: gate-pass + lot on invoices. Declarative Studio bundle; no partner code.",
        "tags": ["spinning", "private"],
        "audience": "private",
        "visible_to_tenant_ids": [],
        "studio": {
            "custom_fields": [
                {
                    "entity": "invoice",
                    "key": "x.gate_pass_no",
                    "label": "Gate pass",
                    "type": "text",
                    "required": True,
                    "show_on_form": True,
                    "show_on_print": True,
                    "show_on_list": True,
                    "sort_order": 10,
                },
                {
                    "entity": "invoice",
                    "key": "x.lot_ref",
                    "label": "Lot ref",
                    "type": "text",
                    "show_on_form": True,
                    "show_on_print": False,
                    "show_on_list": False,
                    "sort_order": 20,
                },
            ],
            "form_schema_patch": {
                "invoice": {
                    "fields": {
                        "x.gate_pass_no": {"visible": True, "required": True},
                        "x.lot_ref": {"visible": True, "required": False},
                    }
                }
            },
            "print_template_key": "standard",
        },
        "manifest": {
            "id": "partner.easybooks.weighbridge",
            "name": "Weighbridge",
            "version": "1.0.0",
            "description": (
                "Private mill listing: installs invoice custom fields "
                "(gate pass, lot ref) via a Studio bundle. Install never "
                "executes partner code."
            ),
            "publisher": "Easy-Books Partners",
            "category": "Industry",
            "icon": "Scale",
            "homepage": "https://github.com/bilalpiaic/Easy-Books",
            "docs_url": "https://github.com/bilalpiaic/Easy-Books/blob/main/docs/MARKETPLACE.md",
            "requires_modules": ["base"],
            "requested_permissions": ["read_invoices"],
            "settings_keys": ["ext.weighbridge.note"],
            "webhook_events": [],
            "curated": True,
        },
    },
]


def _parse_entries(raw: list[dict[str, Any]]) -> list[CatalogEntry]:
    out: list[CatalogEntry] = []
    for row in raw:
        manifest = ExtensionManifest.model_validate(row["manifest"])
        out.append(
            CatalogEntry(
                manifest=manifest,
                first_party_module=row.get("first_party_module"),
                summary=row.get("summary"),
                tags=list(row.get("tags") or []),
                audience=row.get("audience") or "public",
                visible_to_tenant_ids=list(row.get("visible_to_tenant_ids") or []),
                entitled_module=row.get("entitled_module"),
                studio=row.get("studio"),
            )
        )
    return out


@lru_cache(maxsize=1)
def bundled_catalog() -> tuple[CatalogEntry, ...]:
    return tuple(_parse_entries(_CURATED))


def fetch_remote_catalog(url: str, *, timeout: float = 8.0) -> list[CatalogEntry]:
    """Fetch + validate a remote curated catalog. Raises on HTTP/schema errors."""
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "entries" in data:
        data = data["entries"]
    if not isinstance(data, list):
        raise ValueError("catalog JSON must be a list or {entries: [...]}")
    return _parse_entries(data)


def catalog_for_tenant(
    tenant: Tenant,
    *,
    remote_url: str | None = None,
    allow_env: bool = True,
) -> list[CatalogEntry]:
    """Resolved catalog rows this tenant is allowed to see (#371)."""
    return [
        e for e in resolve_catalog(remote_url=remote_url, allow_env=allow_env)
        if visible_to(e, tenant)
    ]


def resolve_catalog(
    *,
    remote_url: str | None = None,
    allow_env: bool = True,
) -> list[CatalogEntry]:
    """Bundled catalog, optionally extended/replaced by a remote curated URL."""
    url = (remote_url or "").strip()
    if not url and allow_env:
        url = (os.environ.get("MARKETPLACE_CATALOG_URL") or "").strip()

    bundled = list(bundled_catalog())
    if not url:
        return bundled

    remote = fetch_remote_catalog(url)
    # Remote entries win on id collision
    by_id = {e.manifest.id: e for e in bundled}
    for e in remote:
        by_id[e.manifest.id] = e
    return list(by_id.values())


def catalog_as_json() -> str:
    """Helper for tests / docs snapshots."""
    return json.dumps(
        [
            {
                "summary": e.summary,
                "tags": e.tags,
                "first_party_module": e.first_party_module,
                "audience": e.audience,
                "visible_to_tenant_ids": e.visible_to_tenant_ids,
                "entitled_module": e.entitled_module,
                "manifest": e.manifest.model_dump(),
            }
            for e in bundled_catalog()
        ],
        indent=2,
    )
