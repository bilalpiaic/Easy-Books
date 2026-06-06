"""Audit trail for posted-invoice / posted-bill edits.

Each UPDATE on an invoice or bill should record a ``changes`` dict in the
audit-log detail that captures before/after values for every header field or
total that changed (header + totals level only; no per-line diff per the
locked decision).
"""
import json


# ── helpers ──────────────────────────────────────────────────────────────────

def _signup_login(client, email="audit@test.com", pw="pw12345678", company="AuditCo"):
    r = client.post("/api/auth/signup", json={
        "email": email, "password": pw,
        "full_name": "Audit User", "company_name": company,
    })
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login", data={"username": email, "password": pw}).json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def _create_customer(client, h, name="Acme"):
    return client.post("/api/customers", headers=h, json={"name": name}).json()


def _create_vendor(client, h, name="Bolt Supplies"):
    return client.post("/api/vendors", headers=h, json={"name": name}).json()


def _create_product(client, h, name="Widget"):
    return client.post("/api/products", headers=h,
                       json={"name": name, "product_type": "service"}).json()


def _post_invoice(client, h, customer_id, product_id, rate=100, qty=2, date="2026-03-01"):
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": customer_id,
        "issue_date": date,
        "gst_rate": 0,
        "lines": [{"product_id": product_id, "description": "x", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    return inv


def _post_bill(client, h, vendor_id, product_id, rate=50, qty=4, date="2026-03-01"):
    bill = client.post("/api/bills", headers=h, json={
        "vendor_id": vendor_id,
        "bill_date": date,
        "gst_rate": 0,
        "lines": [{"product_id": product_id, "description": "y", "qty": qty, "rate": rate}],
    }).json()
    # Bills start as 'received' once posted; set explicitly to allow editing
    return bill


def _audit_for(client, h, entity_type, entity_id):
    r = client.get(
        f"/api/audit-log?entity_type={entity_type}&entity_id={entity_id}&limit=50",
        headers=h,
    )
    assert r.status_code == 200, r.text
    return r.json()["items"]


# ── invoice audit-trail tests ─────────────────────────────────────────────────

def test_invoice_edit_records_changes_in_audit_log(client, admin_headers):
    """Editing a posted invoice writes a changes dict with before/after values."""
    h = admin_headers
    c = _create_customer(client, h)
    c2 = _create_customer(client, h, name="Globex")
    p = _create_product(client, h)

    inv = _post_invoice(client, h, c["id"], p["id"], rate=100, qty=2)  # total=200

    # Edit: change customer + bump qty/rate so total changes 200 → 360
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c2["id"],
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "x", "qty": 3, "rate": 120}],
    })
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 360

    audit = _audit_for(client, h, "invoice", inv["id"])
    update_rows = [a for a in audit if a["action"] == "UPDATE"]
    assert update_rows, "Expected at least one UPDATE audit row for the invoice"

    # Find the row that carries a `changes` dict (the edit row)
    edit_rows = [
        a for a in update_rows
        if json.loads(a["detail"]).get("changes")
    ]
    assert edit_rows, "Expected an UPDATE row with non-empty 'changes'"
    row = edit_rows[0]

    detail = json.loads(row["detail"])
    changes = detail["changes"]

    # Total changed 200 → 360 (values stored as 2-dp strings e.g. "200.00")
    assert "total" in changes, f"Expected 'total' in changes, got {list(changes)}"
    assert float(changes["total"]["before"]) == 200.0
    assert float(changes["total"]["after"]) == 360.0

    # Customer changed
    assert "customer_name" in changes
    assert changes["customer_name"]["before"] == "Acme"
    assert changes["customer_name"]["after"] == "Globex"

    # Audit row has user_id and timestamp
    assert row["user_id"] is not None
    assert row["timestamp"] is not None


def test_invoice_edit_no_changes_records_empty_changes(client, admin_headers):
    """Editing with identical values produces an empty changes dict."""
    h = admin_headers
    c = _create_customer(client, h)
    p = _create_product(client, h)
    inv = _post_invoice(client, h, c["id"], p["id"], rate=100, qty=2)

    # Edit with same customer + same line values
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"],
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "x", "qty": 2, "rate": 100}],
    })
    assert r.status_code == 200, r.text

    audit = _audit_for(client, h, "invoice", inv["id"])
    edit_row = next(
        (a for a in audit if a["action"] == "UPDATE" and json.loads(a["detail"]).get("changes") == {}),
        None,
    )
    assert edit_row is not None, "Expected an UPDATE row with empty changes when nothing changed"


def test_invoice_edit_entity_id_filter(client, admin_headers):
    """audit-log entity_id filter returns only rows for the requested invoice."""
    h = admin_headers
    c = _create_customer(client, h)
    p = _create_product(client, h)

    inv1 = _post_invoice(client, h, c["id"], p["id"], rate=100, qty=1)
    inv2 = _post_invoice(client, h, c["id"], p["id"], rate=200, qty=1)

    # Edit inv1 only
    client.put(f"/api/invoices/{inv1['id']}", headers=h, json={
        "customer_id": c["id"],
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "x", "qty": 1, "rate": 150}],
    })

    rows_inv1 = _audit_for(client, h, "invoice", inv1["id"])
    rows_inv2 = _audit_for(client, h, "invoice", inv2["id"])

    assert all(r["entity_id"] == inv1["id"] for r in rows_inv1)
    assert all(r["entity_id"] == inv2["id"] for r in rows_inv2)
    update_ids = {r["entity_id"] for r in rows_inv1 if r["action"] == "UPDATE"}
    assert inv2["id"] not in update_ids


# ── bill audit-trail tests ────────────────────────────────────────────────────

def test_bill_edit_records_changes_in_audit_log(client, admin_headers):
    """Editing a posted bill writes a changes dict with before/after values."""
    h = admin_headers
    v = _create_vendor(client, h)
    v2 = _create_vendor(client, h, name="MegaCorp Supplies")
    p = _create_product(client, h)

    bill = _post_bill(client, h, v["id"], p["id"], rate=50, qty=4)  # total=200

    # Edit: change vendor + amounts so total changes 200 → 300
    r = client.put(f"/api/bills/{bill['id']}", headers=h, json={
        "vendor_id": v2["id"],
        "bill_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "y", "qty": 3, "rate": 100}],
    })
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 300

    audit = _audit_for(client, h, "bill", bill["id"])
    update_rows = [a for a in audit if a["action"] == "UPDATE"]
    assert update_rows, "Expected at least one UPDATE audit row for the bill"

    edit_rows = [
        a for a in update_rows
        if json.loads(a["detail"]).get("changes")
    ]
    assert edit_rows, "Expected an UPDATE row with non-empty 'changes'"
    row = edit_rows[0]

    detail = json.loads(row["detail"])
    changes = detail["changes"]

    # Total changed 200 → 300 (values stored as 2-dp strings e.g. "200.00")
    assert "total" in changes
    assert float(changes["total"]["before"]) == 200.0
    assert float(changes["total"]["after"]) == 300.0

    # Vendor changed
    assert "vendor_name" in changes
    assert changes["vendor_name"]["before"] == "Bolt Supplies"
    assert changes["vendor_name"]["after"] == "MegaCorp Supplies"

    # Audit row has user_id and timestamp
    assert row["user_id"] is not None
    assert row["timestamp"] is not None
