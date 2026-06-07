"""Editing a posted invoice must honor block_negative_stock (issue #48).

create_invoice reads the block_negative_stock setting and passes it to
consume_stock; update_invoice's re-consume must do the same, or an edit can
silently drive stock negative even when the tenant enabled the guard.
"""
from sqlmodel import Session

import db as _db_module
from models import Product


def _set_onhand(pid, qty):
    with Session(_db_module.engine) as s:
        prod = s.get(Product, pid)
        prod.stock_qty = qty
        s.add(prod)
        s.commit()


def _onhand(pid):
    with Session(_db_module.engine) as s:
        return float(s.get(Product, pid).stock_qty)


def _post_invoice_selling(client, h, cid, pid, qty):
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": cid, "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": pid, "description": "Bolt", "qty": qty, "rate": 10}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    return inv


def test_edit_posted_invoice_blocks_oversell_when_setting_on(client, admin_headers):
    h = admin_headers
    client.patch("/api/settings", headers=h, json={"block_negative_stock": "true"})
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock", "default_rate": 10}).json()
    _set_onhand(p["id"], 5)

    inv = _post_invoice_selling(client, h, c["id"], p["id"], qty=2)  # on-hand 3
    assert _onhand(p["id"]) == 3.0

    # Edit to sell 9 — exceeds the 5 originally on hand → must be blocked.
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 9, "rate": 10}],
    })
    assert r.status_code == 400, r.text
    assert "stock" in r.json()["detail"].lower()
    # Stock must never go negative; the blocked edit rolls back to its prior state.
    assert _onhand(p["id"]) == 3.0


def test_edit_posted_invoice_within_stock_still_succeeds_when_setting_on(client, admin_headers):
    h = admin_headers
    client.patch("/api/settings", headers=h, json={"block_negative_stock": "true"})
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock", "default_rate": 10}).json()
    _set_onhand(p["id"], 5)

    inv = _post_invoice_selling(client, h, c["id"], p["id"], qty=2)  # on-hand 3

    # Edit to sell 4 (≤ 5 available after restore) — allowed → on-hand 1.
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 10}],
    })
    assert r.status_code in (200, 201), r.text
    assert _onhand(p["id"]) == 1.0
