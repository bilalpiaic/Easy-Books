"""Editing a posted invoice restores original stock then re-applies the new qty."""
from sqlmodel import Session
import db as _db_module
from models import Product


def _onhand(pid):
    with Session(_db_module.engine) as s:
        return float(s.get(Product, pid).stock_qty)


def test_edit_restores_then_reapplies_stock(client, admin_headers):
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    # receive 100 via a bill so there is stock to relieve
    client.post("/api/bills", headers=h, json={
        "vendor_name": "Sup", "issue_date": "2026-02-01",
        "bill_date": "2026-02-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 100, "rate": 5}],
    })
    start = _onhand(p["id"])               # 100
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 10, "rate": 20}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    assert _onhand(p["id"]) == start - 10   # 90 after selling 10
    # edit: now sell 4 instead of 10 → on-hand should be 96, not double-counted
    client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 20}],
    })
    assert _onhand(p["id"]) == start - 4    # 96
