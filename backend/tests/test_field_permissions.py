"""Field-level UserPermission overlay on custom fields (#375)."""
from __future__ import annotations

from services.permissions import FIELD_KEY_RE, is_known_resource_key


def test_field_key_regex_and_unknown_rejected():
    assert FIELD_KEY_RE.match("invoices.field.x.gate_pass_no")
    assert not FIELD_KEY_RE.match("invoices.field.discount_pct")
    assert not FIELD_KEY_RE.match("studio.field.invoice.x.gate_pass_no")
    assert is_known_resource_key("invoices")
    assert is_known_resource_key("invoices.field.x.gate_pass_no")
    assert not is_known_resource_key("invoices.field.nope")


def test_accountant_edit_writes_custom_fields(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice", "key": "x.gate_pass_no", "label": "Gate pass", "type": "text",
    })
    assert field.status_code == 201, field.text
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})

    created = client.post("/api/users", headers=admin_headers, json={
        "email": "acct-fr@co.test", "password": "pw12345678",
        "role": "accountant", "full_name": "Acct",
    })
    assert created.status_code == 201, created.text
    tok = client.post("/api/auth/login", data={"username": "acct-fr@co.test", "password": "pw12345678"})
    assert tok.status_code == 200, tok.text
    client.cookies.clear()
    acct = {"Authorization": f"Bearer {tok.json()['access_token']}"}

    inv = client.post("/api/invoices", headers=acct, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "GP-ACCT"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 201, inv.text
    assert inv.json()["custom_fields"]["x.gate_pass_no"] == "GP-ACCT"


def test_viewer_writing_invoice_is_403(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice", "key": "x.gate_pass_no", "label": "Gate pass", "type": "text",
    })
    assert field.status_code == 201, field.text
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    created = client.post("/api/users", headers=admin_headers, json={
        "email": "view-fr@co.test", "password": "pw12345678",
        "role": "viewer", "full_name": "View",
    })
    assert created.status_code == 201, created.text
    tok = client.post("/api/auth/login", data={"username": "view-fr@co.test", "password": "pw12345678"})
    client.cookies.clear()
    viewer = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    schema = client.get("/api/studio/forms/invoice", headers=viewer)
    assert schema.status_code == 200, schema.text
    assert schema.json()["field_access"]["x.gate_pass_no"] == "view"
    inv = client.post("/api/invoices", headers=viewer, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "NO"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 403, inv.text


def test_view_field_overlay_strips_custom_fields(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice", "key": "x.gate_pass_no", "label": "Gate pass",
        "type": "text", "required": True,
    })
    assert field.status_code == 201, field.text
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    created = client.post("/api/users", headers=admin_headers, json={
        "email": "acct-viewf@co.test", "password": "pw12345678",
        "role": "accountant", "full_name": "Acct view-field",
    })
    uid = created.json()["id"]
    put = client.put(f"/api/permissions/users/{uid}", headers=admin_headers, json=[
        {"resource_key": "invoices.field.x.gate_pass_no", "access_level": "view"},
    ])
    assert put.status_code == 200, put.text
    tok = client.post("/api/auth/login", data={"username": "acct-viewf@co.test", "password": "pw12345678"})
    client.cookies.clear()
    hdr = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    schema = client.get("/api/studio/forms/invoice", headers=hdr)
    assert schema.json()["field_access"]["x.gate_pass_no"] == "view"
    inv = client.post("/api/invoices", headers=hdr, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "SHOULD-DROP"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 201, inv.text
    assert inv.json().get("custom_fields", {}).get("x.gate_pass_no") in (None, "")


def test_none_on_field_hides_even_if_schema_visible(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice", "key": "x.gate_pass_no", "label": "Gate pass", "type": "text",
    })
    assert field.status_code == 201, field.text
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    created = client.post("/api/users", headers=admin_headers, json={
        "email": "hide-fr@co.test", "password": "pw12345678",
        "role": "accountant", "full_name": "Hide",
    })
    uid = created.json()["id"]
    put = client.put(f"/api/permissions/users/{uid}", headers=admin_headers, json=[
        {"resource_key": "invoices.field.x.gate_pass_no", "access_level": "none"},
    ])
    assert put.status_code == 200, put.text

    tok = client.post("/api/auth/login", data={"username": "hide-fr@co.test", "password": "pw12345678"})
    client.cookies.clear()
    hdr = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    schema = client.get("/api/studio/forms/invoice", headers=hdr)
    assert schema.json()["schema"]["fields"].get("x.gate_pass_no", {}).get("visible") is not False
    assert schema.json()["field_access"]["x.gate_pass_no"] == "none"

    inv = client.post("/api/invoices", headers=hdr, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "NOPE"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 201, inv.text
    assert inv.json().get("custom_fields", {}).get("x.gate_pass_no") in (None, "")


def test_field_overlay_noop_when_rights_disabled(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice", "key": "x.gate_pass_no", "label": "Gate pass", "type": "text",
    })
    assert field.status_code == 201, field.text
    created = client.post("/api/users", headers=admin_headers, json={
        "email": "off-fr@co.test", "password": "pw12345678",
        "role": "accountant", "full_name": "Off",
    })
    uid = created.json()["id"]
    client.put(f"/api/permissions/users/{uid}", headers=admin_headers, json=[
        {"resource_key": "invoices.field.x.gate_pass_no", "access_level": "none"},
    ])
    tok = client.post("/api/auth/login", data={"username": "off-fr@co.test", "password": "pw12345678"})
    client.cookies.clear()
    hdr = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    schema = client.get("/api/studio/forms/invoice", headers=hdr)
    assert schema.json()["field_access"]["x.gate_pass_no"] == "edit"

    inv = client.post("/api/invoices", headers=hdr, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "KEPT"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    # invoices POST may 403 for viewer even with rights off? perm_dep is no-op when off
    assert inv.status_code == 201, inv.text
    assert inv.json()["custom_fields"]["x.gate_pass_no"] == "KEPT"


def test_put_rejects_non_x_field_key(client, admin_headers):
    created = client.post("/api/users", headers=admin_headers, json={
        "email": "badkey-fr@co.test", "password": "pw12345678",
        "role": "accountant", "full_name": "Bad",
    })
    uid = created.json()["id"]
    r = client.put(f"/api/permissions/users/{uid}", headers=admin_headers, json=[
        {"resource_key": "invoices.field.notes", "access_level": "none"},
    ])
    assert r.status_code == 400, r.text
