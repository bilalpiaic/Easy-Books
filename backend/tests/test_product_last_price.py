"""Last-price lookup: per-customer first, global fallback."""
from sqlmodel import Session

import db as _db_module
from models import Customer, Invoice, InvoiceLine, Product


def _make_invoice(client, h, customer_id, product_id, rate, date):
    return client.post("/api/invoices", headers=h, json={
        "customer_id": customer_id, "issue_date": date,
        "lines": [{"product_id": product_id, "description": "x",
                   "qty": 1, "rate": rate}],
    })


def test_last_price_prefers_this_customer(client, admin_headers):
    h = admin_headers
    a = client.post("/api/customers", headers=h, json={"name": "A"}).json()
    b = client.post("/api/customers", headers=h, json={"name": "B"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Widget", "product_type": "stock"}).json()
    _make_invoice(client, h, a["id"], p["id"], 100, "2026-01-01")
    _make_invoice(client, h, b["id"], p["id"], 250, "2026-02-01")  # later, other cust
    r = client.get(
        f"/api/products/{p['id']}/last-price?customer_id={a['id']}&kind=sale",
        headers=h,
    ).json()
    assert r["rate"] == 100
    assert r["scope"] == "customer"


def test_last_price_global_fallback(client, admin_headers):
    h = admin_headers
    a = client.post("/api/customers", headers=h, json={"name": "A"}).json()
    b = client.post("/api/customers", headers=h, json={"name": "B"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Gadget", "product_type": "stock"}).json()
    _make_invoice(client, h, b["id"], p["id"], 77, "2026-03-01")
    r = client.get(
        f"/api/products/{p['id']}/last-price?customer_id={a['id']}&kind=sale",
        headers=h,
    ).json()
    assert r["rate"] == 77
    assert r["scope"] == "global"


def test_last_price_none_when_never_sold(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "New", "product_type": "stock"}).json()
    r = client.get(f"/api/products/{p['id']}/last-price?kind=sale", headers=h).json()
    assert r["rate"] is None
    assert r["scope"] is None


def test_last_price_party_name_customer(client, admin_headers):
    """scope=customer returns party_name equal to that customer's name."""
    h = admin_headers
    a = client.post("/api/customers", headers=h, json={"name": "PartyAlpha"}).json()
    b = client.post("/api/customers", headers=h, json={"name": "PartyBeta"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "PartyProd", "product_type": "stock"}).json()
    _make_invoice(client, h, a["id"], p["id"], 150, "2026-04-01")
    _make_invoice(client, h, b["id"], p["id"], 200, "2026-04-15")
    # Per-customer for A → scope=customer, party_name=PartyAlpha
    r = client.get(
        f"/api/products/{p['id']}/last-price?customer_id={a['id']}&kind=sale",
        headers=h,
    ).json()
    assert r["scope"] == "customer"
    assert r["party_name"] == "PartyAlpha"


def test_last_price_party_name_global_fallback(client, admin_headers):
    """scope=global returns party_name of whichever customer had the latest sale."""
    h = admin_headers
    c_new = client.post("/api/customers", headers=h, json={"name": "FallbackCo"}).json()
    c_other = client.post("/api/customers", headers=h, json={"name": "OtherCo"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "FallbackProd", "product_type": "stock"}).json()
    _make_invoice(client, h, c_other["id"], p["id"], 99, "2026-05-01")
    # c_new has never bought this product → global fallback → party_name=OtherCo
    r = client.get(
        f"/api/products/{p['id']}/last-price?customer_id={c_new['id']}&kind=sale",
        headers=h,
    ).json()
    assert r["scope"] == "global"
    assert r["party_name"] == "OtherCo"


def test_last_price_party_name_none_when_no_history(client, admin_headers):
    """No sales history → party_name is None."""
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "BrandNew", "product_type": "stock"}).json()
    r = client.get(f"/api/products/{p['id']}/last-price?kind=sale", headers=h).json()
    assert r["rate"] is None
    assert r["party_name"] is None


def test_last_price_tenant_isolation(client, admin_headers):
    """Data belonging to tenant 9999 must never leak into the admin user's results."""
    h = admin_headers
    # Create a product in the admin's tenant so we have a valid product_id to query
    p = client.post("/api/products", headers=h,
                    json={"name": "IsolatedWidget", "product_type": "stock"}).json()
    pid = p["id"]

    # Directly insert a foreign-tenant customer, invoice, and invoice line
    with Session(_db_module.engine) as s:
        foreign_customer = Customer(
            tenant_id=9999, name="Foreign Customer",
        )
        s.add(foreign_customer)
        s.flush()
        foreign_invoice = Invoice(
            tenant_id=9999, customer_id=foreign_customer.id,
            number="INV-FOREIGN-001",
            issue_date="2026-01-15", due_date="2026-01-15",
            total=999.0, subtotal=999.0, gst_rate=0, gst_amount=0,
        )
        s.add(foreign_invoice)
        s.flush()
        foreign_line = InvoiceLine(
            invoice_id=foreign_invoice.id, product_id=pid,
            description="foreign", qty=1, rate=999.0, amount=999.0,
        )
        s.add(foreign_line)
        s.commit()

    # Admin (different tenant) must NOT see the foreign rate
    r = client.get(f"/api/products/{pid}/last-price?kind=sale", headers=h).json()
    assert r["rate"] != 999.0 or r["rate"] is None, (
        "Foreign tenant's last price must not leak to admin user"
    )
    assert r["scope"] is None or r["rate"] != 999.0
