"""Marketplace studio bundle apply/archive (#376)."""
from __future__ import annotations

from services.marketplace.manifest import CatalogEntry, ExtensionManifest, StudioBundle, StudioFieldSpec


def _mill_entry() -> CatalogEntry:
    return CatalogEntry(
        manifest=ExtensionManifest(
            id="partner.test.mill-pack",
            name="Mill packing overlay",
            version="1.0.0",
            description="Declarative mill invoice fields. No partner code.",
            publisher="test",
        ),
        studio=StudioBundle(
            custom_fields=[
                StudioFieldSpec(
                    entity="invoice",
                    key="x.gate_pass_no",
                    label="Gate pass",
                    type="text",
                    show_on_form=True,
                    show_on_print=True,
                )
            ],
            form_schema_patch={
                "invoice": {"fields": {"x.gate_pass_no": {"visible": True, "required": True}}}
            },
            print_template_key="standard",
        ),
    )


def test_install_bundle_creates_field_uninstall_archives(client, admin_headers, monkeypatch):
    entry = _mill_entry()

    def _catalog(**_kw):
        return [entry]

    monkeypatch.setattr("services.marketplace.catalog.resolve_catalog", _catalog)
    monkeypatch.setattr("services.marketplace.install.resolve_catalog", _catalog)
    monkeypatch.setattr("routers.marketplace.resolve_catalog", _catalog)

    inst = client.post(
        "/api/marketplace/extensions/partner.test.mill-pack/install",
        headers=admin_headers,
    )
    assert inst.status_code == 200, inst.text
    assert "no partner code was executed" in inst.json()["message"].lower()

    fields = client.get("/api/studio/fields?entity=invoice", headers=admin_headers)
    assert fields.status_code == 200, fields.text
    keys = {f["key"] for f in fields.json()}
    assert "x.gate_pass_no" in keys
    row = next(f for f in fields.json() if f["key"] == "x.gate_pass_no")
    assert row["source_extension_id"] == "partner.test.mill-pack"

    schema = client.get("/api/studio/forms/invoice", headers=admin_headers)
    assert schema.json()["schema"]["fields"]["x.gate_pass_no"]["required"] is True

    cat = client.get("/api/marketplace/catalog", headers=admin_headers)
    listed = next(e for e in cat.json()["entries"] if e["id"] == "partner.test.mill-pack")
    assert listed["installed"] is True

    inv = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "GP-KEEP"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 201, inv.text
    iid = inv.json()["id"]

    un = client.post(
        "/api/marketplace/extensions/partner.test.mill-pack/uninstall",
        headers=admin_headers,
    )
    assert un.status_code == 200, un.text
    after = client.get("/api/studio/fields?entity=invoice", headers=admin_headers)
    assert after.json() == []
    archived = client.get(
        "/api/studio/fields?entity=invoice&include_archived=true",
        headers=admin_headers,
    )
    assert any(f["key"] == "x.gate_pass_no" and f["archived_at"] for f in archived.json())

    got = client.get(f"/api/invoices/{iid}", headers=admin_headers)
    assert got.status_code == 200, got.text
    assert got.json()["custom_fields"]["x.gate_pass_no"] == "GP-KEEP"


def test_227_boundary_text_unchanged(client, admin_headers):
    r = client.get("/api/marketplace/boundary", headers=admin_headers)
    assert r.status_code == 200
    summary = r.json()["summary"].lower()
    assert "never" in summary or "declarative" in summary
    assert "execute" in summary or "code" in summary
