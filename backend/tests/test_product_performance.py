"""Opening + Purchased - Sold = Closing, from StockMovement."""
from sqlmodel import Session
import db as _db_module
from models import StockMovement, Product, Invoice, InvoiceLine
from datetime import datetime


def _mv(tid, pid, direction, qty, when, unit_cost=0):
    with Session(_db_module.engine) as s:
        s.add(StockMovement(tenant_id=tid, product_id=pid, direction=direction,
                            qty=qty, unit_cost=unit_cost,
                            occurred_at=datetime.fromisoformat(when)))
        s.commit()


def _set_avg_cost(pid, avg_cost):
    with Session(_db_module.engine) as s:
        p = s.get(Product, pid)
        p.avg_cost = avg_cost
        s.add(p)
        s.commit()


def _add_invoice_line(tid, pid, qty, rate, issue_date, number):
    """Insert an Invoice + line directly (no posting / no stock consumption) so
    revenue can be controlled independently of the StockMovement fixtures."""
    with Session(_db_module.engine) as s:
        inv = Invoice(tenant_id=tid, number=number, issue_date=issue_date,
                      due_date=issue_date)
        s.add(inv)
        s.commit()
        s.refresh(inv)
        s.add(InvoiceLine(invoice_id=inv.id, product_id=pid, description="x",
                          qty=qty, rate=rate, amount=qty * rate))
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


def test_adjustment_is_purchase_return(client, admin_headers):
    """ADJUSTMENT (return_to_vendor) reduces stock — it nets against purchases
    and is signed negative in opening, so reconciliation still matches reality."""
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "Washer", "product_type": "stock"}).json()
    with Session(_db_module.engine) as s:
        tid = s.get(Product, p["id"]).tenant_id
    _mv(tid, p["id"], "RECEIPT", 20, "2025-12-01T10:00")     # opening receipt
    _mv(tid, p["id"], "ADJUSTMENT", 5, "2025-12-05T10:00")   # opening vendor return → -5
    _mv(tid, p["id"], "RECEIPT", 10, "2026-01-10T10:00")     # period purchase
    _mv(tid, p["id"], "ADJUSTMENT", 3, "2026-01-12T10:00")   # period vendor return
    _mv(tid, p["id"], "SHIPMENT", 6, "2026-01-15T10:00")     # period sale
    data = client.get(
        "/api/reports/product-performance?start=2026-01-01&end=2026-01-31",
        headers=h,
    ).json()
    row = next(r for r in data["items"] if r["product_id"] == p["id"])
    assert row["opening_qty"] == 15        # 20 - 5
    assert row["purchased_qty"] == 7       # 10 - 3 (net of return)
    assert row["sold_qty"] == 6
    assert row["closing_qty"] == 16        # 15 + 7 - 6  == net of all movements


def test_gp_uses_avg_cost(client, admin_headers):
    """GP = period sales revenue - COGS, where COGS = sold_qty * avg_cost."""
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "Bearing", "product_type": "stock"}).json()
    with Session(_db_module.engine) as s:
        tid = s.get(Product, p["id"]).tenant_id
    _set_avg_cost(p["id"], 5)
    _mv(tid, p["id"], "SHIPMENT", 6, "2026-01-15T10:00")     # sold 6 → COGS 30
    _add_invoice_line(tid, p["id"], qty=6, rate=20, issue_date="2026-01-15",
                      number="GP-INV-1")                       # revenue 120
    data = client.get(
        "/api/reports/product-performance?start=2026-01-01&end=2026-01-31",
        headers=h,
    ).json()
    row = next(r for r in data["items"] if r["product_id"] == p["id"])
    assert row["revenue"] == 120
    assert row["gp"] == 90                  # 120 - (6 * 5)


def test_empty_period_and_no_movement(client, admin_headers):
    """A product with movements only OUTSIDE the window shows them as opening
    with zero in-period activity; a product with no movements is all zeros."""
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "Spacer", "product_type": "stock"}).json()
    q = client.post("/api/products", headers=h,
                    json={"name": "Shim", "product_type": "stock"}).json()
    with Session(_db_module.engine) as s:
        tid = s.get(Product, p["id"]).tenant_id
    _mv(tid, p["id"], "RECEIPT", 10, "2025-11-01T10:00")     # before window
    data = client.get(
        "/api/reports/product-performance?start=2026-01-01&end=2026-01-31",
        headers=h,
    ).json()
    rp = next(r for r in data["items"] if r["product_id"] == p["id"])
    assert rp["opening_qty"] == 10 and rp["purchased_qty"] == 0
    assert rp["sold_qty"] == 0 and rp["closing_qty"] == 10
    rq = next(r for r in data["items"] if r["product_id"] == q["id"])
    assert rq["opening_qty"] == 0 and rq["purchased_qty"] == 0
    assert rq["sold_qty"] == 0 and rq["closing_qty"] == 0 and rq["gp"] == 0
