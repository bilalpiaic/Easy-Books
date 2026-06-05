"""Editing a posted bill: allowed when unpaid+open; restores receipt stock."""
from sqlmodel import Session
import db as _db_module
from models import Product


def _onhand(pid):
    with Session(_db_module.engine) as s:
        return float(s.get(Product, pid).stock_qty)


def test_edit_posted_bill_adjusts_stock(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "Nut", "product_type": "stock"}).json()
    bill = client.post("/api/bills", headers=h, json={
        "vendor_name": "Sup", "bill_date": "2026-02-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Nut", "qty": 50, "rate": 4}],
    }).json()
    client.patch(f"/api/bills/{bill['id']}/status?status=received", headers=h)
    assert _onhand(p["id"]) == 50
    client.put(f"/api/bills/{bill['id']}", headers=h, json={
        "vendor_name": "Sup", "bill_date": "2026-02-01",
        "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Nut", "qty": 30, "rate": 4}],
    })
    assert _onhand(p["id"]) == 30   # not 80
