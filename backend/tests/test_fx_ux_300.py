"""#300 Multi-currency document/payment UX polish — inherit + aging + realised FX."""
from datetime import date as DateType, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, StaticPool, create_engine

from db import get_session
from main import app


def _mk_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _override(engine):
    def _inner():
        with Session(engine) as s:
            yield s
    return _inner


def _auth(client, email="fxux@co.test", company="FxUxCo"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Tester",
            "company_name": company,
        },
    )
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_credit_note_inherits_currency_from_invoice():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)
    auth = _auth(client, "cn-inherit@co.test", "CnInheritCo")
    client.patch("/api/settings", headers=auth, json={"currency": "PKR"})

    cust = client.post("/api/customers", headers=auth, json={"name": "Euro Cust"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "issue_date": "2026-02-01",
        "due_date": "2026-02-28",
        "gst_rate": 0,
        "currency": "EUR",
        "exchange_rate": 300,
        "lines": [{"description": "Svc", "qty": 1, "rate": 50}],
    }).json()
    assert inv["currency"] == "EUR"

    # Omit currency/exchange_rate → inherit from invoice
    r = client.post("/api/credit-notes", headers=auth, json={
        "invoice_id": inv["id"],
        "customer_id": cust["id"],
        "issue_date": "2026-02-10",
        "description": "Partial return",
        "lines": [{"description": "Return", "qty": 1, "rate": 10}],
    })
    assert r.status_code == 201, r.text
    cn = r.json()
    assert cn["currency"] == "EUR"
    assert Decimal(str(cn["exchange_rate"])) == Decimal("300")

    # Explicit override wins
    r2 = client.post("/api/credit-notes", headers=auth, json={
        "invoice_id": inv["id"],
        "customer_id": cust["id"],
        "issue_date": "2026-02-11",
        "currency": "USD",
        "exchange_rate": 280,
        "lines": [{"description": "Return USD", "qty": 1, "rate": 5}],
    })
    assert r2.status_code == 201, r2.text
    assert r2.json()["currency"] == "USD"
    assert Decimal(str(r2.json()["exchange_rate"])) == Decimal("280")

    app.dependency_overrides.clear()


def test_debit_note_inherits_currency_from_bill():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)
    auth = _auth(client, "dn-inherit@co.test", "DnInheritCo")
    client.patch("/api/settings", headers=auth, json={"currency": "PKR"})

    vendor = client.post("/api/vendors", headers=auth, json={"name": "USD Vendor"}).json()
    bill = client.post("/api/bills", headers=auth, json={
        "vendor_id": vendor["id"],
        "bill_date": "2026-02-01",
        "due_date": "2026-02-28",
        "gst_rate": 0,
        "currency": "USD",
        "exchange_rate": 280,
        "lines": [{"description": "Parts", "qty": 1, "rate": 100}],
    }).json()

    r = client.post("/api/debit-notes", headers=auth, json={
        "bill_id": bill["id"],
        "vendor_id": vendor["id"],
        "issue_date": "2026-02-12",
        "description": "Return parts",
        "lines": [{"description": "Parts return", "qty": 1, "rate": 20}],
    })
    assert r.status_code == 201, r.text
    dn = r.json()
    assert dn["currency"] == "USD"
    assert Decimal(str(dn["exchange_rate"])) == Decimal("280")

    app.dependency_overrides.clear()


def test_aging_includes_currency_and_base_equivalent():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)
    auth = _auth(client, "aging-fx@co.test", "AgingFxCo")
    client.patch("/api/settings", headers=auth, json={"currency": "PKR"})

    cust = client.post("/api/customers", headers=auth, json={"name": "FX Alice"}).json()
    due = (DateType.today() - timedelta(days=45)).isoformat()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "issue_date": (DateType.today() - timedelta(days=60)).isoformat(),
        "due_date": due,
        "gst_rate": 0,
        "currency": "USD",
        "exchange_rate": 280,
        "lines": [{"description": "Svc", "qty": 1, "rate": 10}],
    }).json()

    aging = client.get("/api/invoices/aging", headers=auth).json()
    assert aging["base_currency"] == "PKR"
    assert len(aging["items"]) == 1
    item = aging["items"][0]
    assert item["id"] == inv["id"]
    assert item["currency"] == "USD"
    assert Decimal(str(item["amount"])) == Decimal("10")
    assert Decimal(str(item["amount_base"])) == Decimal("2800")
    # Bucket totals are in base
    assert Decimal(str(aging["31_60"])) == Decimal("2800")

    app.dependency_overrides.clear()


def test_payment_create_returns_realised_fx_fields():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)
    auth = _auth(client, "pay-fx-ret@co.test", "PayFxRetCo")
    client.patch("/api/settings", headers=auth, json={"currency": "PKR"})

    cust = client.post("/api/customers", headers=auth, json={"name": "Settle"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "issue_date": "2026-01-01",
        "due_date": "2026-01-31",
        "gst_rate": 0,
        "currency": "USD",
        "exchange_rate": 280,
        "lines": [{"description": "Svc", "qty": 1, "rate": 100}],
    }).json()

    r = client.post("/api/payments-received", headers=auth, json={
        "customer_id": cust["id"],
        "payment_date": "2026-01-15",
        "amount": 100,
        "currency": "USD",
        "exchange_rate": 290,
        "method": "bank_transfer",
        "allocations": [{"invoice_id": inv["id"], "amount": 100}],
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_fx"] is True
    assert Decimal(str(body["cash_base"])) == Decimal("29000")
    assert Decimal(str(body["cleared_base"])) == Decimal("28000")
    assert Decimal(str(body["realised_fx"])) == Decimal("1000")

    detail = client.get(f"/api/payments-received/{body['id']}", headers=auth).json()
    assert Decimal(str(detail["realised_fx"])) == Decimal("1000")
    assert Decimal(str(detail["cash_base"])) == Decimal("29000")

    app.dependency_overrides.clear()
