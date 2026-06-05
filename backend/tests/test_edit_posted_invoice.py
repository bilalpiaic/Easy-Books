"""Editing a posted invoice: allowed when unpaid+open, blocked otherwise."""
from sqlmodel import Session
import db as _db_module
from models import Invoice


def _post_invoice(client, h, customer_id, product_id, rate=100, qty=2, date="2026-03-01"):
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": customer_id, "issue_date": date,
        "gst_rate": 0,
        "lines": [{"product_id": product_id, "description": "x", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    return inv


def _setup(client, h):
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    return c, p


def test_edit_posted_unpaid_succeeds(client, admin_headers):
    h = admin_headers
    c, p = _setup(client, h)
    inv = _post_invoice(client, h, c["id"], p["id"], rate=100, qty=2)
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "x", "qty": 3, "rate": 120}],
    })
    assert r.status_code == 200
    assert r.json()["total"] == 360            # 3 * 120
    assert r.json()["number"] == inv["number"]  # number preserved


def test_edit_blocked_when_paid(client, admin_headers):
    h = admin_headers
    c, p = _setup(client, h)
    inv = _post_invoice(client, h, c["id"], p["id"], rate=100, qty=2)
    client.post("/api/payments-received", headers=h, json={
        "customer_id": c["id"], "amount": 50, "method": "cash",
        "payment_date": "2026-03-02",
        "allocations": [{"invoice_id": inv["id"], "amount": 50}],
    })
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "x", "qty": 3, "rate": 120}],
    })
    assert r.status_code == 400
    assert "payment" in r.json()["detail"].lower()
