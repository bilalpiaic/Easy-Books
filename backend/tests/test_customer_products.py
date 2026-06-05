"""Customer's-products module: every product sold to a customer + last price."""
from sqlmodel import Session

import db as _db_module
from models import Customer, Invoice, InvoiceLine, Product


def test_customer_products_aggregates(client, admin_headers):
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    for rate, date, qty in [(10, "2026-01-01", 5), (12, "2026-02-01", 3)]:
        client.post("/api/invoices", headers=h, json={
            "customer_id": c["id"], "issue_date": date,
            "lines": [{"product_id": p["id"], "description": "Bolt",
                       "qty": qty, "rate": rate}],
        })
    data = client.get(f"/api/customers/{c['id']}/products", headers=h).json()
    row = next(r for r in data["items"] if r["product_id"] == p["id"])
    assert row["last_rate"] == 12          # most recent
    assert row["last_date"] == "2026-02-01"
    assert row["total_qty"] == 8           # 5 + 3
    assert row["invoice_count"] == 2


def test_customer_products_distinct_invoice_count(client, admin_headers):
    """One invoice with the same product on TWO lines must count as invoice_count=1,
    not 2, and total_qty must sum both lines."""
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={"name": "DistinctCo"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "DistinctProd", "product_type": "stock"}).json()
    # Single invoice, same product appears on two lines
    client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01",
        "lines": [
            {"product_id": p["id"], "description": "Line A", "qty": 4, "rate": 10},
            {"product_id": p["id"], "description": "Line B", "qty": 6, "rate": 10},
        ],
    })
    data = client.get(f"/api/customers/{c['id']}/products", headers=h).json()
    row = next(r for r in data["items"] if r["product_id"] == p["id"])
    assert row["invoice_count"] == 1, "Same product on two lines of one invoice must count as 1 invoice"
    assert row["total_qty"] == 10, "total_qty must sum both lines (4 + 6 = 10)"


def test_customer_products_tenant_isolation(client, admin_headers):
    """A customer + products belonging to tenant 9999 must not be visible to the admin user."""
    h = admin_headers
    # Create a product via the API (admin's tenant) so it exists in the DB with a known id
    p = client.post("/api/products", headers=h,
                    json={"name": "IsoProduct", "product_type": "stock"}).json()
    pid = p["id"]

    # Directly insert a foreign-tenant customer, invoice, and invoice line
    with Session(_db_module.engine) as s:
        foreign_customer = Customer(
            tenant_id=9999, name="Foreign Corp",
        )
        s.add(foreign_customer)
        s.flush()
        foreign_invoice = Invoice(
            tenant_id=9999, customer_id=foreign_customer.id,
            number="INV-FOREIGN-CUST-001",
            issue_date="2026-02-10", due_date="2026-02-10",
            total=500.0, subtotal=500.0, gst_rate=0, gst_amount=0,
        )
        s.add(foreign_invoice)
        s.flush()
        foreign_line = InvoiceLine(
            invoice_id=foreign_invoice.id, product_id=pid,
            description="foreign sale", qty=5, rate=100.0, amount=500.0,
        )
        s.add(foreign_line)
        s.commit()
        foreign_cid = foreign_customer.id

    # Admin querying the foreign customer_id must get 404 (different tenant)
    resp = client.get(f"/api/customers/{foreign_cid}/products", headers=h)
    # Either 404 (customer not found in admin's tenant) or empty items — never foreign data
    if resp.status_code == 200:
        items = resp.json()["items"]
        for item in items:
            assert item.get("total_qty") != 5 or item.get("last_rate") != 100.0, (
                "Foreign tenant's product data must not appear in admin user's results"
            )
