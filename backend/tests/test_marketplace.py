"""Marketplace catalog + extension install (#227)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.marketplace.catalog import bundled_catalog, resolve_catalog
from services.marketplace.manifest import CatalogEntry, ExtensionManifest

def test_forbidden_tag_rejected():
    with pytest.raises(ValidationError):
        CatalogEntry(
            manifest=ExtensionManifest(
                id="partner.acme.mill-pack",
                name="X",
                version="1.0.0",
                description="d",
                publisher="p",
            ),
            tags=["customized-tenant"],
        )


def test_client_tag_rejected():
    with pytest.raises(ValidationError):
        CatalogEntry(
            manifest=ExtensionManifest(
                id="partner.acme.mill-pack",
                name="X",
                version="1.0.0",
                description="d",
                publisher="p",
            ),
            tags=["client-acme"],
        )


def _signup(client, email, company="Co"):
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Owner", "company_name": company, "business_model": "simple",
    })
    assert r.status_code == 200, r.text
    tenant_id = r.json()["tenant_id"]
    tok = client.post("/api/auth/login", data={
        "username": email, "password": "password123",
    })
    assert tok.status_code == 200, tok.text
    client.cookies.clear()
    return tenant_id, {"Authorization": f"Bearer {tok.json()['access_token']}"}


def _extra_entries(mill_tid: int) -> list[CatalogEntry]:
    mill = ExtensionManifest(
        id="partner.easybooks.mill-private",
        name="Mill private listing",
        version="1.0.0",
        description="Private spinning overlay for one mill.",
        publisher="Easy-Books",
        requires_modules=["base"],
    )
    spin = ExtensionManifest(
        id="partner.easybooks.spinning-entitled",
        name="Spinning mill pack",
        version="1.0.0",
        description="Shown when spinning is entitled or installed.",
        publisher="Easy-Books",
        requires_modules=["spinning"],
    )
    return [
        CatalogEntry(
            manifest=mill,
            summary="Private mill card",
            tags=["spinning", "private"],
            audience="private",
            visible_to_tenant_ids=[mill_tid],
        ),
        CatalogEntry(
            manifest=spin,
            summary="Entitled spinning card",
            tags=["spinning", "first-party"],
            audience="entitled",
            entitled_module="spinning",
            first_party_module="spinning",
        ),
    ]


def test_private_listing_isolated_between_tenants(client, monkeypatch):
    a_id, a_auth = _signup(client, "mill-a@mp.test", "Mill A")
    _b_id, b_auth = _signup(client, "hosp-b@mp.test", "Hospital B")

    extras = _extra_entries(a_id)

    def fake_resolve(*, remote_url=None, allow_env=True):
        return list(bundled_catalog()) + extras

    monkeypatch.setattr("services.marketplace.catalog.resolve_catalog", fake_resolve)

    cat_a = client.get("/api/marketplace/catalog", headers=a_auth)
    assert cat_a.status_code == 200, cat_a.text
    ids_a = {e["id"] for e in cat_a.json()["entries"]}
    assert "partner.easybooks.mill-private" in ids_a
    row = next(e for e in cat_a.json()["entries"] if e["id"] == "partner.easybooks.mill-private")
    assert row["for_you"] is True
    assert row["audience"] == "private"
    assert "spinning" in row["tags"]

    cat_b = client.get("/api/marketplace/catalog", headers=b_auth)
    assert cat_b.status_code == 200, cat_b.text
    ids_b = {e["id"] for e in cat_b.json()["entries"]}
    assert "partner.easybooks.mill-private" not in ids_b
    assert "partner.easybooks.invoice-csv-export" in ids_b

    leak = client.post(
        "/api/marketplace/extensions/partner.easybooks.mill-private/install",
        headers=b_auth,
    )
    assert leak.status_code == 404, leak.text


def test_entitled_listing_hidden_until_entitled(client, monkeypatch):
    from services.entitlements import set_entitled
    from sqlmodel import Session
    import db as db_mod
    from models import Tenant

    a_id, a_auth = _signup(client, "spin-a@mp.test", "Spin Co")
    extras = _extra_entries(a_id)

    def fake_resolve(*, remote_url=None, allow_env=True):
        return list(bundled_catalog()) + extras

    monkeypatch.setattr("services.marketplace.catalog.resolve_catalog", fake_resolve)

    before = client.get("/api/marketplace/catalog", headers=a_auth).json()["entries"]
    assert all(e["id"] != "partner.easybooks.spinning-entitled" for e in before)

    with Session(db_mod.engine) as s:
        tenant = s.get(Tenant, a_id)
        set_entitled(tenant, ["spinning"])
        s.add(tenant)
        s.commit()

    after = client.get("/api/marketplace/catalog", headers=a_auth).json()["entries"]
    row = next(e for e in after if e["id"] == "partner.easybooks.spinning-entitled")
    assert row["for_you"] is True
    assert row["audience"] == "entitled"


def test_public_listings_default_audience(client, admin_headers):
    cat = client.get("/api/marketplace/catalog", headers=admin_headers)
    assert cat.status_code == 200, cat.text
    for e in cat.json()["entries"]:
        assert e["audience"] == "public"
        assert e["for_you"] is False
        assert "tags" in e


def test_bundled_catalog_validates():
    bundled_catalog.cache_clear()
    entries = bundled_catalog()
    assert len(entries) >= 2
    ids = {e.manifest.id for e in entries}
    assert "partner.easybooks.invoice-csv-export" in ids
    assert all(e.manifest.id.startswith("partner.") for e in entries)
    wb = next(e for e in entries if e.manifest.id == "partner.easybooks.weighbridge")
    assert wb.audience == "private"
    assert wb.visible_to_tenant_ids == []
    assert "spinning" in wb.tags and "private" in wb.tags
    assert not any("client-" in t or t == "customized-tenant" for t in wb.tags)
    assert wb.studio is not None
    keys = {f.key for f in wb.studio.custom_fields}
    assert "x.gate_pass_no" in keys


def test_weighbridge_hidden_from_ungranted_tenant(client, admin_headers):
    cat = client.get("/api/marketplace/catalog", headers=admin_headers)
    assert cat.status_code == 200, cat.text
    ids = {e["id"] for e in cat.json()["entries"]}
    assert "partner.easybooks.weighbridge" not in ids
    leak = client.post(
        "/api/marketplace/extensions/partner.easybooks.weighbridge/install",
        headers=admin_headers,
    )
    assert leak.status_code == 404, leak.text


def test_weighbridge_for_you_on_granted_mill_not_hospital(client, monkeypatch):
    from sqlmodel import Session
    import db as db_mod
    from models import Tenant
    from services.marketplace.catalog import WEIGHBRIDGE_ID, grant_private_listing

    mill_id, mill_auth = _signup(client, "mill-wb@mp.test", "Mill Weigh")
    hosp_id, hosp_auth = _signup(client, "hosp-wb@mp.test", "Hospital Weigh")

    with Session(db_mod.engine) as s:
        mill = s.get(Tenant, mill_id)
        grant_private_listing(mill, WEIGHBRIDGE_ID)
        s.add(mill)
        s.commit()

    cat_m = client.get("/api/marketplace/catalog", headers=mill_auth)
    assert cat_m.status_code == 200, cat_m.text
    ids_m = {e["id"] for e in cat_m.json()["entries"]}
    assert WEIGHBRIDGE_ID in ids_m
    row = next(e for e in cat_m.json()["entries"] if e["id"] == WEIGHBRIDGE_ID)
    assert row["for_you"] is True
    assert row["audience"] == "private"
    assert row["name"] == "Weighbridge"
    assert "spinning" in row["tags"]

    cat_h = client.get("/api/marketplace/catalog", headers=hosp_auth)
    assert cat_h.status_code == 200, cat_h.text
    ids_h = {e["id"] for e in cat_h.json()["entries"]}
    assert WEIGHBRIDGE_ID not in ids_h

    leak = client.post(
        f"/api/marketplace/extensions/{WEIGHBRIDGE_ID}/install",
        headers=hosp_auth,
    )
    assert leak.status_code == 404, leak.text

    inst = client.post(
        f"/api/marketplace/extensions/{WEIGHBRIDGE_ID}/install",
        headers=mill_auth,
    )
    assert inst.status_code == 200, inst.text
    assert "no partner code was executed" in inst.json()["message"].lower()

    fields = client.get("/api/studio/fields?entity=invoice", headers=mill_auth)
    assert fields.status_code == 200, fields.text
    keys = {f["key"] for f in fields.json()}
    assert "x.gate_pass_no" in keys
    assert "x.lot_ref" in keys

    hosp_fields = client.get("/api/studio/fields?entity=invoice", headers=hosp_auth)
    assert hosp_fields.status_code == 200, hosp_fields.text
    assert "x.gate_pass_no" not in {f["key"] for f in hosp_fields.json()}


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
