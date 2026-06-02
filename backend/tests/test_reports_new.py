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


# ── D3: Inventory Performance ────────────────────────────────────────────────

def test_inventory_performance_value(client, admin_headers):
    from sqlmodel import Session
    import db as _db_module
    from models import Product
    h = admin_headers
    p = client.post("/api/products", headers=h, json={"name": "Gizmo", "product_type": "stock"}).json()
    with Session(_db_module.engine) as s:
        prod = s.get(Product, p["id"]); prod.stock_qty = 10; prod.avg_cost = 3; s.add(prod); s.commit()
    data = client.get("/api/reports/inventory-performance", headers=h).json()
    row = next(r for r in data["items"] if r["name"] == "Gizmo")
    assert float(row["stock_value"]) == 30.0


# ── D4: Customer Performance ─────────────────────────────────────────────────

def test_customer_performance_revenue(client, admin_headers):
    h = admin_headers
    for amt in (100, 200):
        client.post("/api/invoices", headers=h, json={
            "customer_name": "Acme", "issue_date": "2026-04-01", "due_date": "2026-04-30",
            "gst_rate": 0,
            "lines": [{"description": "svc", "qty": 1, "rate": amt}]})
    data = client.get("/api/reports/customer-performance?start=2026-01-01&end=2026-12-31",
                      headers=h).json()
    row = next(r for r in data["items"] if r["name"] == "Acme")
    assert float(row["revenue"]) == 300.0
    assert row["invoice_count"] == 2


# ── E1: Demo seed assigns product categories ─────────────────────────────────

def test_demo_seed_assigns_categories(client, admin_headers):
    import db as _db_module
    from sqlmodel import Session, select as _select
    from models import Product, Tenant
    from scripts.seed_demo import seed_one_tenant
    seed_one_tenant("demo.trader@easy-books.app", "Demo Trading Co.", "trader")
    with Session(_db_module.engine) as s:
        t = s.exec(_select(Tenant).where(Tenant.name == "Demo Trading Co.")).first()
        prods = s.exec(_select(Product).where(Product.tenant_id == t.id)).all()
    assert prods, "demo tenant should have products"
    assert any(p.category_id is not None for p in prods), "products should be categorised"
