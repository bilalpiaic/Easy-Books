"""Tenant form schema hide/show/required with API enforcement (#373)."""
from __future__ import annotations

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


def _put_schema(client, headers, entity, fields, role="*"):
    return client.put(
        f"/api/studio/forms/{entity}",
        headers=headers,
        json={"role": role, "schema": {"version": 1, "fields": fields}},
    )


def test_studio_forms_resource_registered():
    assert "studio.forms" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["studio.forms"]["category"] == "System"


def test_get_form_schema_default_empty(client, admin_headers):
    r = client.get("/api/studio/forms/invoice", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["entity"] == "invoice"
    assert body["schema"]["version"] == 1
    assert body["schema"]["fields"] == {}
    assert "customer_id" in body["locked"]
    assert "issue_date" in body["locked"]


def test_hide_notes_ok_hide_customer_id_rejected(client, admin_headers):
    ok = _put_schema(client, admin_headers, "invoice", {"notes": {"visible": False}})
    assert ok.status_code == 200, ok.text
    assert ok.json()["schema"]["fields"]["notes"]["visible"] is False

    bad = _put_schema(client, admin_headers, "invoice", {"customer_id": {"visible": False}})
    assert bad.status_code == 400, bad.text
    assert "locked" in bad.json()["detail"].lower() or "customer_id" in bad.json()["detail"]

    totals = _put_schema(client, admin_headers, "invoice", {"total": {"visible": False}})
    assert totals.status_code == 400, totals.text


def test_unknown_core_field_rejected(client, admin_headers):
    r = _put_schema(client, admin_headers, "invoice", {"not_a_field": {"visible": False}})
    assert r.status_code == 400, r.text


def test_tenant_isolation_on_form_schema(client):
    a = _signup(client, "mill-a@fs.test", "Mill A")
    b = _signup(client, "clinic-b@fs.test", "Clinic B")
    put = _put_schema(client, a, "invoice", {"notes": {"visible": False}})
    assert put.status_code == 200, put.text
    a_get = client.get("/api/studio/forms/invoice", headers=a)
    assert a_get.json()["schema"]["fields"]["notes"]["visible"] is False
    b_get = client.get("/api/studio/forms/invoice", headers=b)
    assert b_get.status_code == 200
    assert b_get.json()["schema"]["fields"] == {}


def test_hidden_notes_dropped_on_create_and_update(client, admin_headers):
    hid = _put_schema(client, admin_headers, "invoice", {"notes": {"visible": False}})
    assert hid.status_code == 200, hid.text

    created = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "notes": "should-be-dropped",
        "lines": [{"description": "Yarn", "qty": 1, "rate": 100}],
    })
    assert created.status_code == 201, created.text
    inv_id = created.json()["id"]
    assert created.json().get("notes") in (None, "")

    # Store a note, then hide and try to overwrite via API.
    shown = _put_schema(client, admin_headers, "invoice", {"notes": {"visible": True}})
    assert shown.status_code == 200
    # Unhide, set notes via update, re-hide, crafted PUT must not stick.
    with_note = client.put(f"/api/invoices/{inv_id}", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "notes": "keep-me",
        "lines": [{"description": "Yarn", "qty": 1, "rate": 100}],
    })
    assert with_note.status_code == 200, with_note.text
    assert with_note.json()["notes"] == "keep-me"

    hid2 = _put_schema(client, admin_headers, "invoice", {"notes": {"visible": False}})
    assert hid2.status_code == 200
    hacked = client.put(f"/api/invoices/{inv_id}", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "notes": "hacked",
        "lines": [{"description": "Yarn", "qty": 1, "rate": 100}],
    })
    assert hacked.status_code == 200, hacked.text
    assert hacked.json()["notes"] == "keep-me"


def test_required_custom_field_via_schema(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice",
        "key": "x.gate_pass_no",
        "label": "Gate pass",
        "type": "text",
        "required": False,
    })
    assert field.status_code == 201, field.text
    sch = _put_schema(client, admin_headers, "invoice", {
        "x.gate_pass_no": {"visible": True, "required": True, "order": 40},
    })
    assert sch.status_code == 200, sch.text

    missing = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"description": "Yarn", "qty": 1, "rate": 50}],
    })
    assert missing.status_code == 400, missing.text
    assert "x.gate_pass_no" in missing.json()["detail"]

    ok = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "GP-42"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 50}],
    })
    assert ok.status_code == 201, ok.text
    assert ok.json()["custom_fields"]["x.gate_pass_no"] == "GP-42"
    txn_id = ok.json()["transaction_id"]
    txn = client.get(f"/api/transactions/{txn_id}", headers=admin_headers)
    entries = txn.json()["entries"]
    debits = sum(float(e["debit"] or 0) for e in entries)
    credits = sum(float(e["credit"] or 0) for e in entries)
    assert abs(debits - credits) < 0.0001


def test_hidden_custom_field_write_dropped(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice",
        "key": "x.mill_code",
        "label": "Mill code",
        "type": "text",
    })
    assert field.status_code == 201, field.text
    hid = _put_schema(client, admin_headers, "invoice", {
        "x.mill_code": {"visible": False},
    })
    assert hid.status_code == 200, hid.text
    inv = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.mill_code": "secret"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 201, inv.text
    assert inv.json()["custom_fields"].get("x.mill_code") in (None, "")


def test_x_dot_key_allowed_on_schema(client, admin_headers):
    r = _put_schema(client, admin_headers, "invoice", {
        "x.gate_pass_no": {"visible": True, "required": True},
        "analytic_2_id": {"visible": True, "required": True},
    })
    assert r.status_code == 200, r.text
    fields = r.json()["schema"]["fields"]
    assert fields["x.gate_pass_no"]["required"] is True
    assert fields["analytic_2_id"]["required"] is True
