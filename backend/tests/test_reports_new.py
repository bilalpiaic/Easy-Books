"""Tests for new report endpoints added in D2 (product ledger)."""
from sqlmodel import Session

import db as _db_module
from models import StockMovement, Product


def _mk_movement(engine, tenant_id, product_id, direction, qty):
    with Session(engine) as s:
        s.add(StockMovement(
            tenant_id=tenant_id,
            product_id=product_id,
            direction=direction,
            qty=qty,
        ))
        s.commit()


def test_product_ledger_running_qty(client, admin_headers):
    h = admin_headers
    p = client.post(
        "/api/products", headers=h,
        json={"name": "Bolt", "product_type": "stock"},
    ).json()
    # find tenant_id from the product
    with Session(_db_module.engine) as s:
        tid = s.get(Product, p["id"]).tenant_id
    _mk_movement(_db_module.engine, tid, p["id"], "RECEIPT", 10)
    _mk_movement(_db_module.engine, tid, p["id"], "SHIPMENT", 4)
    data = client.get(
        f"/api/reports/product-ledger?product_id={p['id']}", headers=h,
    ).json()
    assert data["items"][-1]["running_qty"] == 6   # 10 in − 4 out
