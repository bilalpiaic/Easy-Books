"""Opening + Purchased - Sold = Closing, from StockMovement."""
from sqlmodel import Session
import db as _db_module
from models import StockMovement, Product
from datetime import datetime


def _mv(tid, pid, direction, qty, when, unit_cost=0):
    with Session(_db_module.engine) as s:
        s.add(StockMovement(tenant_id=tid, product_id=pid, direction=direction,
                            qty=qty, unit_cost=unit_cost,
                            occurred_at=datetime.fromisoformat(when)))
        s.commit()


def test_opening_purchased_sold_closing(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "Nut", "product_type": "stock"}).json()
    with Session(_db_module.engine) as s:
        tid = s.get(Product, p["id"]).tenant_id
    _mv(tid, p["id"], "RECEIPT", 20, "2025-12-01T10:00", unit_cost=5)   # before period → opening
    _mv(tid, p["id"], "RECEIPT", 10, "2026-01-10T10:00", unit_cost=5)   # purchased in period
    _mv(tid, p["id"], "SHIPMENT", 6, "2026-01-15T10:00")                # sold in period
    data = client.get(
        "/api/reports/product-performance?start=2026-01-01&end=2026-01-31",
        headers=h,
    ).json()
    row = next(r for r in data["items"] if r["product_id"] == p["id"])
    assert row["opening_qty"] == 20
    assert row["purchased_qty"] == 10
    assert row["sold_qty"] == 6
    assert row["closing_qty"] == 24    # 20 + 10 - 6
