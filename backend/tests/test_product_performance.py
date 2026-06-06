"""Opening + Purchased - Sold = Closing, from StockMovement."""
import io
from sqlmodel import Session
import db as _db_module
from models import StockMovement, Product, Invoice, InvoiceLine, ProductCategory
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


# ── Export tests ──────────────────────────────────────────────────────────────

def _seed_export_product(client, admin_headers):
    """Create a stock product with a RECEIPT and sell movement + invoice line.
    Returns (headers, product_id, tenant_id)."""
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "ExportWidget", "product_type": "stock",
                          "code": "EW-001"}).json()
    with Session(_db_module.engine) as s:
        tid = s.get(Product, p["id"]).tenant_id
    _set_avg_cost(p["id"], 10)
    _mv(tid, p["id"], "RECEIPT", 50, "2026-01-05T10:00", unit_cost=10)
    _mv(tid, p["id"], "SHIPMENT", 10, "2026-01-20T10:00")
    _add_invoice_line(tid, p["id"], qty=10, rate=25, issue_date="2026-01-20",
                      number="EXP-INV-1")
    return h, p["id"], tid


def test_product_performance_export_csv(client, admin_headers):
    """GET /export?format=csv returns 200, attachment header, non-empty body
    with the column headers and the seeded product name."""
    h, pid, _ = _seed_export_product(client, admin_headers)
    r = client.get(
        "/api/reports/product-performance/export?format=csv&start=2026-01-01&end=2026-01-31",
        headers=h,
    )
    assert r.status_code == 200, r.text
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    body = r.text
    assert len(body) > 0
    # column headers present
    assert "Opening Qty" in body
    assert "Closing Qty" in body
    assert "GP" in body
    # seeded product name present
    assert "ExportWidget" in body


def test_product_performance_export_xlsx(client, admin_headers):
    """GET /export?format=xlsx returns 200, attachment header, non-empty body."""
    h, pid, _ = _seed_export_product(client, admin_headers)
    r = client.get(
        "/api/reports/product-performance/export?format=xlsx&start=2026-01-01&end=2026-01-31",
        headers=h,
    )
    assert r.status_code == 200, r.text
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert len(r.content) > 0
    # XLSX magic bytes (PK zip header)
    assert r.content[:2] == b"PK"


def test_product_performance_export_formula_safe(client, admin_headers):
    """A product whose name starts with '=' is neutralised in CSV output."""
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "=cmd()", "product_type": "stock"}).json()
    with Session(_db_module.engine) as s:
        tid = s.get(Product, p["id"]).tenant_id
    _mv(tid, p["id"], "RECEIPT", 5, "2026-01-05T10:00")
    r = client.get(
        "/api/reports/product-performance/export?format=csv&start=2026-01-01&end=2026-01-31",
        headers=h,
    )
    assert r.status_code == 200
    # The neutralised form (prefixed with single-quote) should be present in
    # the CSV body, meaning the raw formula trigger was escaped.
    assert "'=cmd()" in r.text
    # No CSV row should begin a field with the bare formula trigger =cmd()\n or =cmd(),
    # i.e. it must not appear as the very start of a field (after newline or comma).
    import re
    assert not re.search(r'(?:^|,)=cmd\(\)', r.text, re.MULTILINE)


# ── Category grouping tests ───────────────────────────────────────────────────

def _make_category(tenant_id, name, parent_id=None):
    with Session(_db_module.engine) as s:
        cat = ProductCategory(tenant_id=tenant_id, name=name, parent_id=parent_id)
        s.add(cat)
        s.commit()
        s.refresh(cat)
        return cat.id


def test_product_performance_group_by_category(client, admin_headers):
    """group_by=category returns subtotal rows that reconcile to flat totals."""
    h = admin_headers
    # create two products in different categories
    p1 = client.post("/api/products", headers=h,
                     json={"name": "ProdA", "product_type": "stock"}).json()
    p2 = client.post("/api/products", headers=h,
                     json={"name": "ProdB", "product_type": "stock"}).json()
    with Session(_db_module.engine) as s:
        prod1 = s.get(Product, p1["id"])
        prod2 = s.get(Product, p2["id"])
        tid = prod1.tenant_id
        cat_id = _make_category(tid, "Electronics")
        # assign categories
        prod1.category_id = cat_id
        prod2.category_id = cat_id
        s.add(prod1); s.add(prod2); s.commit()
    _set_avg_cost(p1["id"], 5)
    _set_avg_cost(p2["id"], 10)
    _mv(tid, p1["id"], "RECEIPT", 20, "2026-01-05T10:00", unit_cost=5)
    _mv(tid, p2["id"], "RECEIPT", 10, "2026-01-05T10:00", unit_cost=10)
    _mv(tid, p1["id"], "SHIPMENT", 5, "2026-01-20T10:00")
    _mv(tid, p2["id"], "SHIPMENT", 3, "2026-01-20T10:00")
    _add_invoice_line(tid, p1["id"], qty=5, rate=15, issue_date="2026-01-20", number="GRP-INV-1")
    _add_invoice_line(tid, p2["id"], qty=3, rate=30, issue_date="2026-01-20", number="GRP-INV-2")

    # flat totals
    flat = client.get(
        "/api/reports/product-performance?start=2026-01-01&end=2026-01-31",
        headers=h,
    ).json()
    flat_rows = [r for r in flat["items"] if r["product_id"] in (p1["id"], p2["id"])]
    flat_total_gp = sum(r["gp"] for r in flat_rows)
    flat_total_closing = sum(r["closing_qty"] for r in flat_rows)

    # grouped response
    grp = client.get(
        "/api/reports/product-performance?start=2026-01-01&end=2026-01-31&group_by=category",
        headers=h,
    ).json()
    assert "groups" in grp, "grouped response must have 'groups' key"
    # find the Electronics group
    elec = next((g for g in grp["groups"] if g["name"] == "Electronics"), None)
    assert elec is not None, "Electronics group not found"
    # subtotals reconcile
    assert abs(elec["total_gp"] - flat_total_gp) < 0.01
    assert abs(elec["total_closing_qty"] - flat_total_closing) < 0.01
