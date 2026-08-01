"""Marketplace catalog + extension install (#227)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.marketplace.catalog import bundled_catalog, resolve_catalog
from services.marketplace.manifest import ExtensionManifest


def test_bundled_catalog_validates():
    entries = bundled_catalog()
    assert len(entries) >= 2
    ids = {e.manifest.id for e in entries}
    assert "partner.easybooks.invoice-csv-export" in ids
    assert all(e.manifest.id.startswith("partner.") for e in entries)


def test_manifest_rejects_bad_id():
    with pytest.raises(ValidationError):
        ExtensionManifest(
            id="not-a-partner-id",
            name="X",
            version="1.0.0",
            description="d",
            publisher="p",
        )


def test_manifest_rejects_core_settings_key():
    with pytest.raises(ValidationError):
        ExtensionManifest(
            id="partner.acme.demo",
            name="X",
            version="1.0.0",
            description="d",
            publisher="p",
            settings_keys=["currency"],  # must be ext.*
        )


def test_catalog_and_install_extension(client, admin_headers):
    cat = client.get("/api/marketplace/catalog", headers=admin_headers)
    assert cat.status_code == 200, cat.text
    body = cat.json()
    assert "boundary" in body
    assert body["boundary"]["docs_path"] == "docs/MARKETPLACE.md"
    entries = body["entries"]
    assert any(e["id"] == "partner.easybooks.invoice-csv-export" for e in entries)

    ext_id = "partner.easybooks.invoice-csv-export"
    inst = client.post(
        f"/api/marketplace/extensions/{ext_id}/install",
        headers=admin_headers,
    )
    assert inst.status_code == 200, inst.text
    assert "no partner code was executed" in inst.json()["message"].lower() or \
        "Permissions recorded" in inst.json()["message"]

    listed = client.get("/api/marketplace/extensions", headers=admin_headers)
    assert listed.status_code == 200
    assert any(e["id"] == ext_id for e in listed.json())

    # Catalog marks installed
    cat2 = client.get("/api/marketplace/catalog", headers=admin_headers).json()
    row = next(e for e in cat2["entries"] if e["id"] == ext_id)
    assert row["installed"] is True

    un = client.post(
        f"/api/marketplace/extensions/{ext_id}/uninstall",
        headers=admin_headers,
    )
    assert un.status_code == 200, un.text


def test_boundary_endpoint(client, admin_headers):
    r = client.get("/api/marketplace/boundary", headers=admin_headers)
    assert r.status_code == 200
    assert "never" in r.json()["summary"].lower() or "declarative" in r.json()["summary"].lower()


def test_resolve_catalog_uses_bundled_when_no_remote():
    assert resolve_catalog(remote_url=None, allow_env=False) == list(bundled_catalog())
