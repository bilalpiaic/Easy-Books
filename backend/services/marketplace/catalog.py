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

from services.marketplace.manifest import CatalogEntry, ExtensionManifest

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
                "manifest": e.manifest.model_dump(),
            }
            for e in bundled_catalog()
        ],
        indent=2,
    )
