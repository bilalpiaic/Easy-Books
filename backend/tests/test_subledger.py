"""Sub-ledger endpoints: customer ledger, vendor ledger, product stock card,
transaction source-doc resolution."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from db import get_session
from main import app


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


def _signup(c, model="trader", email="t@t.test"):
    c.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": model,
        },
    )
    r = c.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _stock_product(c, auth, code, sale=100):
    return c.post(
        "/api/products", headers=auth,
        json={"code": code, "name": code, "unit": "ea",
              "product_type": "stock", "default_rate": sale},
    ).json()


# ── Customer ledger ─────────────────────────────────────────────────────────


def test_customer_ledger_basic(client):
    c, _ = client
    auth = _signup(c, "trader", "cl1@t.test")
    cust = c.post("/api/customers", headers=auth, json={"name": "Acme Buyer"}).json()
    vendor = c.post("/api/vendors", headers=auth, json={"name": "Supply Co"}).json()
    prod = _stock_product(c, auth, "SKU1", sale=100)

    # Buy some stock so we can sell it (otherwise consume_stock skips)
    c.post(
        "/api/bills", headers=auth,
        json={"vendor_id": vendor["id"], "bill_date": "2026-01-01",
              "due_date": "2026-01-31", "gst_rate": 0,
              "lines": [{"product_id": prod["id"], "description": "buy",
                         "qty": 50, "rate": 40}]},
    )

    # Issue an invoice
    inv = c.post(
        "/api/invoices", headers=auth,
        json={"customer_id": cust["id"], "issue_date": "2026-02-10",
              "due_date": "2026-03-10", "gst_rate": 0,
              "lines": [{"product_id": prod["id"], "description": "sell",
                         "qty": 5, "rate": 100}]},
    ).json()

    # Receive a partial payment
    c.post(
        "/api/payments-received", headers=auth,
        json={"invoice_id": inv["id"], "customer_name": "Acme Buyer",
              "payment_date": "2026-02-20", "amount": 300, "method": "bank"},
    )

    r = c.get(f"/api/customers/{cust['id']}/ledger?start=2026-01-01&end=2026-12-31", headers=auth).json()
    assert r["customer"]["name"] == "Acme Buyer"
    types = [e["doc_type"] for e in r["entries"]]
    assert "invoice" in types
    assert "payment_received" in types
    # Closing balance = 500 (invoice) - 300 (payment) = 200
    assert Decimal(r["closing_balance"]) == Decimal("200")
    # Qty out shows the 5 stock units sold
    invoice_row = next(e for e in r["entries"] if e["doc_type"] == "invoice")
    assert Decimal(invoice_row["qty_out"]) == Decimal("5")


def test_customer_ledger_404_other_tenant(client):
    c, _ = client
    auth_a = _signup(c, "trader", "ta@t.test")
    auth_b = _signup(c, "trader", "tb@t.test")
    cust_a = c.post("/api/customers", headers=auth_a, json={"name": "A's cust"}).json()
    r = c.get(f"/api/customers/{cust_a['id']}/ledger", headers=auth_b)
    assert r.status_code == 404


def test_customer_ledger_period_filter(client):
    c, _ = client
    auth = _signup(c, "trader", "cl2@t.test")
    cust = c.post("/api/customers", headers=auth, json={"name": "X"}).json()
    prod = _stock_product(c, auth, "P", sale=200)
    vendor = c.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    c.post(
        "/api/bills", headers=auth,
        json={"vendor_id": vendor["id"], "bill_date": "2025-12-01",
              "due_date": "2025-12-31", "gst_rate": 0,
              "lines": [{"product_id": prod["id"], "description": "buy",
                         "qty": 100, "rate": 50}]},
    )
    c.post(
        "/api/invoices", headers=auth,
        json={"customer_id": cust["id"], "issue_date": "2025-12-15",
              "due_date": "2026-01-15", "gst_rate": 0,
              "lines": [{"product_id": prod["id"], "description": "old sale",
                         "qty": 2, "rate": 200}]},
    )
    c.post(
        "/api/invoices", headers=auth,
        json={"customer_id": cust["id"], "issue_date": "2026-02-15",
              "due_date": "2026-03-15", "gst_rate": 0,
              "lines": [{"product_id": prod["id"], "description": "new sale",
                         "qty": 3, "rate": 200}]},
    )
    r = c.get(f"/api/customers/{cust['id']}/ledger?start=2026-01-01&end=2026-12-31", headers=auth).json()
    # Period opening should reflect the Dec-2025 invoice
    assert Decimal(r["opening_balance"]) == Decimal("400")
    # Only the Feb-2026 invoice is in-period
    in_period_invoices = [e for e in r["entries"] if e["doc_type"] == "invoice"]
    assert len(in_period_invoices) == 1


# ── Vendor ledger ───────────────────────────────────────────────────────────


def test_vendor_ledger_basic(client):
    c, _ = client
    auth = _signup(c, "trader", "vl1@t.test")
    vendor = c.post("/api/vendors", headers=auth, json={"name": "Acme Supplier"}).json()
    prod = _stock_product(c, auth, "S1")

    b = c.post(
        "/api/bills", headers=auth,
        json={"vendor_id": vendor["id"], "bill_date": "2026-03-01",
              "due_date": "2026-03-31", "gst_rate": 0,
              "lines": [{"product_id": prod["id"], "description": "buy",
                         "qty": 10, "rate": 30}]},
    ).json()
    c.post(
        "/api/bill-payments", headers=auth,
        json={"bill_id": b["id"], "vendor_name": "Acme Supplier",
              "payment_date": "2026-03-10", "amount": 200, "method": "bank"},
    )

    r = c.get(f"/api/vendors/{vendor['id']}/ledger?start=2026-01-01&end=2026-12-31", headers=auth).json()
    assert r["vendor"]["name"] == "Acme Supplier"
    # Closing = 300 (bill) - 200 (payment) = 100 owed to vendor
    assert Decimal(r["closing_balance"]) == Decimal("100")
    bill_row = next(e for e in r["entries"] if e["doc_type"] == "bill")
    assert Decimal(bill_row["qty_in"]) == Decimal("10")


# ── Product stock card ─────────────────────────────────────────────────────


def test_product_stock_card(client):
    c, _ = client
    auth = _signup(c, "trader", "sc1@t.test")
    prod = _stock_product(c, auth, "SC1")
    vendor = c.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    cust = c.post("/api/customers", headers=auth, json={"name": "C"}).json()

    c.post(
        "/api/bills", headers=auth,
        json={"vendor_id": vendor["id"], "bill_date": "2026-04-01",
              "due_date": "2026-04-30", "gst_rate": 0,
              "lines": [{"product_id": prod["id"], "description": "buy",
                         "qty": 20, "rate": 5}]},
    )
    c.post(
        "/api/invoices", headers=auth,
        json={"customer_id": cust["id"], "issue_date": "2026-04-05",
              "due_date": "2026-05-05", "gst_rate": 0,
              "lines": [{"product_id": prod["id"], "description": "sell",
                         "qty": 8, "rate": 12}]},
    )

    r = c.get(f"/api/products/{prod['id']}/stock-card?start=2026-01-01&end=2026-12-31", headers=auth).json()
    assert r["product"]["code"] == "SC1"
    assert Decimal(r["closing_qty"]) == Decimal("12")  # 20 in - 8 out
    directions = [e["direction"] for e in r["entries"]]
    assert "RECEIPT" in directions
    assert "SHIPMENT" in directions


# ── Transaction source-docs ─────────────────────────────────────────────────


def test_transaction_source_docs(client):
    c, _ = client
    auth = _signup(c, "trader", "td1@t.test")
    cust = c.post("/api/customers", headers=auth, json={"name": "X"}).json()
    prod = c.post(
        "/api/products", headers=auth,
        json={"code": "SVC", "name": "Service", "unit": "hr",
              "product_type": "service", "default_rate": 100},
    ).json()
    inv = c.post(
        "/api/invoices", headers=auth,
        json={"customer_id": cust["id"], "issue_date": "2026-05-01",
              "due_date": "2026-05-31", "gst_rate": 0,
              "lines": [{"product_id": prod["id"], "description": "work",
                         "qty": 2, "rate": 100}]},
    ).json()
    # The invoice should have linked a transaction_id
    txn_id = inv["transaction_id"]
    assert txn_id is not None
    r = c.get(f"/api/transactions/{txn_id}", headers=auth).json()
    assert r["jv_number"]
    assert any(d["type"] == "invoice" and d["id"] == inv["id"] for d in r["source_docs"])
