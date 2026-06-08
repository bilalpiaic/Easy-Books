"""Commit A tests: dashboard outstanding net of allocations + 'partial';
reversal unwinds allocations/status/inventory/COGS; delete safety."""
from datetime import date as DateType, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import Invoice, InventoryLayer, PaymentAllocation, Product


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    app.state.engine = engine
    app.dependency_overrides[get_session] = _override
    client = TestClient(app)
    yield client, engine
    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _auth(client: TestClient, email: str = "ca@ca.test") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "U",
            "company_name": "Commit A Co",
        },
    )
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── B1: dashboard ────────────────────────────────────────────────────────────


def test_dashboard_ar_outstanding_uses_outstanding_not_gross(client):
    c, _ = client
    auth = _auth(c)
    cust = c.post("/api/customers", headers=auth, json={"name": "Alice"}).json()
    inv = c.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": DateType.today().isoformat(),
            "due_date": DateType.today().isoformat(),
            "gst_rate": 0,
            "lines": [{"description": "S", "qty": 1, "rate": 1000}],
        },
    ).json()
    # Partial payment of 700 → invoice becomes 'partial'
    c.post(
        "/api/payments-received",
        headers=auth,
        json={
            "customer_name": "Alice",
            "payment_date": DateType.today().isoformat(),
            "amount": 700,
            "allocations": [{"invoice_id": inv["id"], "amount": 700}],
        },
    )
    dash = c.get("/api/reports/dashboard", headers=auth).json()
    # Outstanding should be 300, not 1000, AND the 'partial' invoice
    # must be counted (it wouldn't be before this fix).
    assert Decimal(str(dash["summary"]["ar_outstanding"])) == Decimal("300")


# ── B2: reversal unwinds derived state ──────────────────────────────────────


def test_payment_reversal_clears_allocations_and_status(client):
    c, engine = client
    auth = _auth(c)
    cust = c.post("/api/customers", headers=auth, json={"name": "Bob"}).json()
    inv = c.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": DateType.today().isoformat(),
            "due_date": DateType.today().isoformat(),
            "gst_rate": 0,
            "lines": [{"description": "S", "qty": 1, "rate": 500}],
        },
    ).json()
    pmt = c.post(
        "/api/payments-received",
        headers=auth,
        json={
            "customer_name": "Bob",
            "payment_date": DateType.today().isoformat(),
            "amount": 500,
            "allocations": [{"invoice_id": inv["id"], "amount": 500}],
        },
    ).json()
    # Invoice should be 'paid'
    assert c.get("/api/invoices", headers=auth).json()["items"][0]["status"] == "paid"

    # Reverse the payment's transaction
    r = c.post(f"/api/transactions/{pmt['transaction_id']}/reverse", headers=auth)
    assert r.status_code == 200, r.text

    # Allocations gone
    with Session(engine) as s:
        rows = s.exec(select(PaymentAllocation)).all()
        assert rows == []

    # Invoice status fell back to 'sent' (allocated = 0)
    inv2 = c.get("/api/invoices", headers=auth).json()["items"][0]
    assert inv2["status"] == "sent"


def test_invoice_reversal_restores_stock_and_reverses_cogs(client):
    c, engine = client
    auth = _auth(c)
    # Set up a stock product
    accounts = c.get("/api/accounts", headers=auth).json()["items"]
    cust = c.post("/api/customers", headers=auth, json={"name": "C"}).json()
    prod = c.post(
        "/api/products",
        headers=auth,
        json={
            "code": "WIDGET",
            "name": "Widget",
            "unit": "ea",
            "product_type": "stock",
            "default_rate": 100,
        },
    ).json()
    # Purchase 10 units at 6 each via bill — populates stock
    vendor = c.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    c.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "bill_date": DateType.today().isoformat(),
            "due_date": DateType.today().isoformat(),
            "gst_rate": 0,
            "lines": [
                {"product_id": prod["id"], "description": "buy", "qty": 10, "rate": 6}
            ],
        },
    )

    # Sell 3 units at 100 each → COGS 18 at avg 6
    inv = c.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": DateType.today().isoformat(),
            "due_date": DateType.today().isoformat(),
            "gst_rate": 0,
            "lines": [
                {"product_id": prod["id"], "description": "sell", "qty": 3, "rate": 100}
            ],
        },
    ).json()
    # Stock now 7
    with Session(engine) as s:
        p = s.exec(select(Product).where(Product.code == "WIDGET")).first()
        assert Decimal(str(p.stock_qty)) == Decimal("7")

    # Reverse the invoice JV
    r = c.post(f"/api/transactions/{inv['transaction_id']}/reverse", headers=auth)
    assert r.status_code == 200, r.text
    # Stock restored to 10 (3 returned)
    with Session(engine) as s:
        p = s.exec(select(Product).where(Product.code == "WIDGET")).first()
        assert Decimal(str(p.stock_qty)) == Decimal("10")

    # Trial balance must remain balanced (Dr == Cr) after the double-reversal
    tb_body = c.get("/api/reports/trial-balance", headers=auth).json()
    total_dr = Decimal(str(tb_body["totals"]["debit"]))
    total_cr = Decimal(str(tb_body["totals"]["credit"]))
    assert total_dr == total_cr


def test_bill_reversal_removes_inventory_layer(client):
    c, engine = client
    auth = _auth(c)
    prod = c.post(
        "/api/products",
        headers=auth,
        json={
            "code": "GADGET",
            "name": "Gadget",
            "unit": "ea",
            "product_type": "stock",
            "default_rate": 100,
        },
    ).json()
    vendor = c.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    bill = c.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "bill_date": DateType.today().isoformat(),
            "due_date": DateType.today().isoformat(),
            "gst_rate": 0,
            "lines": [
                {"product_id": prod["id"], "description": "stock-up", "qty": 20, "rate": 5}
            ],
        },
    ).json()
    with Session(engine) as s:
        p = s.exec(select(Product).where(Product.code == "GADGET")).first()
        assert Decimal(str(p.stock_qty)) == Decimal("20")
        layers = s.exec(select(InventoryLayer)).all()
        assert len(layers) == 1

    # Reverse the bill's transaction
    r = c.post(f"/api/transactions/{bill['transaction_id']}/reverse", headers=auth)
    assert r.status_code == 200, r.text
    with Session(engine) as s:
        p = s.exec(select(Product).where(Product.code == "GADGET")).first()
        assert Decimal(str(p.stock_qty)) == Decimal("0")
        layers = s.exec(select(InventoryLayer)).all()
        assert layers == []


# ── B3: delete safety ───────────────────────────────────────────────────────


def test_customer_with_invoices_cannot_be_hard_deleted(client):
    c, _ = client
    auth = _auth(c)
    cust = c.post("/api/customers", headers=auth, json={"name": "Nope"}).json()
    c.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": DateType.today().isoformat(),
            "due_date": DateType.today().isoformat(),
            "gst_rate": 0,
            "lines": [{"description": "S", "qty": 1, "rate": 100}],
        },
    )
    r = c.delete(f"/api/customers/{cust['id']}", headers=auth)
    assert r.status_code == 400
    assert "deactivate" in r.json()["detail"].lower()

    # Soft-delete (PUT is_active=False) works
    r = c.put(
        f"/api/customers/{cust['id']}", headers=auth, json={"is_active": False}
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_vendor_with_bills_cannot_be_hard_deleted(client):
    c, _ = client
    auth = _auth(c)
    vendor = c.post("/api/vendors", headers=auth, json={"name": "Nope V"}).json()
    c.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "bill_date": DateType.today().isoformat(),
            "due_date": DateType.today().isoformat(),
            "gst_rate": 0,
            "lines": [{"description": "X", "qty": 1, "rate": 50}],
        },
    )
    r = c.delete(f"/api/vendors/{vendor['id']}", headers=auth)
    assert r.status_code == 400
