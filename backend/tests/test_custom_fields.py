"""Tenant custom fields (x.*) on documents (#372)."""
from __future__ import annotations

from pathlib import Path

from services.permissions import PERMISSION_RESOURCES


def _signup(client, email, company="Co"):
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Owner", "company_name": company, "business_model": "simple",
    })
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login", data={
        "username": email, "password": "password123",
    })
    assert tok.status_code == 200, tok.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


def test_studio_fields_resource_registered():
    assert "studio.fields" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["studio.fields"]["category"] == "System"


def test_posting_py_never_reads_custom_fields():
    src = (Path(__file__).resolve().parents[1] / "services" / "posting.py").read_text()
    assert "custom_fields" not in src
    assert "CustomFieldDef" not in src


def test_thirteenth_def_rejected(client, admin_headers):
    for i in range(12):
        r = client.post("/api/studio/fields", headers=admin_headers, json={
            "entity": "invoice",
            "key": f"x.field_{i}",
            "label": f"Field {i}",
            "type": "text",
        })
        assert r.status_code == 201, r.text
    r = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice",
        "key": "x.field_12",
        "label": "Too many",
        "type": "text",
    })
    assert r.status_code == 400, r.text
    assert "12" in r.json()["detail"]


def test_key_must_be_x_dot_ident(client, admin_headers):
    for key in ("discount_pct", "ext.foo", "x.Bad", "x.", "gate_pass"):
        r = client.post("/api/studio/fields", headers=admin_headers, json={
            "entity": "invoice", "key": key, "label": "Nope", "type": "text",
        })
        assert r.status_code == 400, (key, r.text)


def test_enum_mismatch_on_invoice(client, admin_headers):
    d = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice",
        "key": "x.shift",
        "label": "Shift",
        "type": "enum",
        "enum_values": ["day", "night"],
    })
    assert d.status_code == 201, d.text
    cust = client.post("/api/customers", headers=admin_headers, json={"name": "Mill"}).json()
    bad = client.post("/api/invoices", headers=admin_headers, json={
        "customer_id": cust["id"],
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.shift": "swing"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 50}],
    })
    assert bad.status_code == 400, bad.text


def test_tenant_isolation_on_defs(client):
    a = _signup(client, "mill-a@cf.test", "Mill A")
    b = _signup(client, "clinic-b@cf.test", "Clinic B")
    created = client.post("/api/studio/fields", headers=a, json={
        "entity": "invoice",
        "key": "x.gate_pass_no",
        "label": "Gate pass",
        "type": "text",
        "show_on_form": True,
        "show_on_list": True,
    })
    assert created.status_code == 201, created.text
    a_list = client.get("/api/studio/fields?entity=invoice", headers=a)
    assert a_list.status_code == 200
    assert any(f["key"] == "x.gate_pass_no" for f in a_list.json())
    b_list = client.get("/api/studio/fields?entity=invoice", headers=b)
    assert b_list.status_code == 200
    assert b_list.json() == []
    leak = client.get(f"/api/studio/fields/{created.json()['id']}", headers=b)
    assert leak.status_code in (404, 405)


def test_invoice_custom_fields_round_trip_gl_unchanged(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice",
        "key": "x.gate_pass_no",
        "label": "Gate pass",
        "type": "text",
        "required": True,
        "show_on_list": True,
    })
    assert field.status_code == 201, field.text
    missing = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"description": "Yarn", "qty": 1, "rate": 100}],
    })
    assert missing.status_code == 400, missing.text

    inv = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "GP-99", "unknown": "strip-me"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 100}],
    })
    assert inv.status_code == 201, inv.text
    body = inv.json()
    assert body["custom_fields"]["x.gate_pass_no"] == "GP-99"
    assert "unknown" not in body["custom_fields"]
    assert float(body["total"]) == 100
    txn_id = body["transaction_id"]
    assert txn_id
    txn = client.get(f"/api/transactions/{txn_id}", headers=admin_headers)
    assert txn.status_code == 200, txn.text
    entries = txn.json()["entries"]
    debits = sum(float(e["debit"] or 0) for e in entries)
    credits = sum(float(e["credit"] or 0) for e in entries)
    assert abs(debits - credits) < 0.0001
    assert abs(debits - 100) < 0.0001 or abs(credits - 100) < 0.0001


def test_archive_keeps_historical_values(client, admin_headers):
    d = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "customer",
        "key": "x.mrn",
        "label": "MRN",
        "type": "text",
    })
    assert d.status_code == 201, d.text
    cust = client.post("/api/customers", headers=admin_headers, json={
        "name": "Patient",
        "custom_fields": {"x.mrn": "MR-1"},
    })
    assert cust.status_code == 201, cust.text
    assert cust.json()["custom_fields"]["x.mrn"] == "MR-1"
    arch = client.delete(f"/api/studio/fields/{d.json()['id']}", headers=admin_headers)
    assert arch.status_code == 200
    listed = client.get("/api/studio/fields?entity=customer", headers=admin_headers)
    assert listed.json() == []
    got = client.get(f"/api/customers/{cust.json()['id']}", headers=admin_headers)
    assert got.json()["custom_fields"]["x.mrn"] == "MR-1"
    write_archived = client.put(
        f"/api/customers/{cust.json()['id']}",
        headers=admin_headers,
        json={"custom_fields": {"x.mrn": "MR-2"}},
    )
    assert write_archived.status_code == 400, write_archived.text


def test_list_bills_keeps_id_when_auto_marked_overdue(client, admin_headers):
    """GET /api/bills used to commit() overdue flips, which expired the
    SQLModel instance so model_dump() returned {} and list items had no id."""
    from datetime import date, timedelta

    past = (date.today() - timedelta(days=10)).isoformat()
    created = client.post("/api/bills", headers=admin_headers, json={
        "vendor_name": "Overdue Vendor",
        "bill_date": past,
        "due_date": past,
        "gst_rate": 0,
        "lines": [{"description": "Widget", "qty": 1, "rate": 25}],
    })
    assert created.status_code in (200, 201), created.text
    bill_id = created.json()["id"]
    listed = client.get("/api/bills", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert all("id" in row for row in items), items
    row = next(b for b in items if b["id"] == bill_id)
    assert row["status"] == "overdue"
    assert row["vendor_name"] == "Overdue Vendor"
