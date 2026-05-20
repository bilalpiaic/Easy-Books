"""P5 tests: multi-currency posting + exchange rate fallback."""
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
    yield client
    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _auth(client: TestClient) -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": "fx@fx.test",
            "password": "password123",
            "full_name": "U",
            "company_name": "FX Co",
        },
    )
    r = client.post(
        "/api/auth/login", data={"username": "fx@fx.test", "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sum_dec(rows, key):
    return sum((Decimal(str(r.get(key))) for r in rows if r.get(key) is not None), start=Decimal("0"))


def test_exchange_rate_crud(client: TestClient):
    auth = _auth(client)
    r = client.post(
        "/api/exchange-rates",
        headers=auth,
        json={"date": "2026-05-01", "from_currency": "EUR", "to_currency": "USD", "rate": 1.10},
    )
    assert r.status_code == 201, r.text
    items = client.get("/api/exchange-rates", headers=auth).json()["items"]
    assert len(items) == 1
    assert items[0]["from_currency"] == "EUR"

    # Upsert: same triple returns the existing row with updated rate
    r = client.post(
        "/api/exchange-rates",
        headers=auth,
        json={"date": "2026-05-01", "from_currency": "EUR", "to_currency": "USD", "rate": 1.15},
    )
    assert r.status_code == 201
    assert Decimal(str(r.json()["rate"])) == Decimal("1.15")
    items = client.get("/api/exchange-rates", headers=auth).json()["items"]
    assert len(items) == 1  # not duplicated


def test_eur_invoice_posts_at_base_currency_in_gl(client: TestClient):
    auth = _auth(client)
    client.post(
        "/api/exchange-rates",
        headers=auth,
        json={"date": "2026-05-01", "from_currency": "EUR", "to_currency": "USD", "rate": 1.10},
    )
    cust = client.post("/api/customers", headers=auth, json={"name": "Alice"}).json()
    r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-05-02",      # uses 2026-05-01 rate via fallback
            "due_date": "2026-05-31",
            "gst_rate": 0,
            "currency": "EUR",
            "lines": [{"description": "Service", "qty": 1, "rate": 1000}],
        },
    )
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["currency"] == "EUR"
    assert Decimal(str(inv["exchange_rate"])) == Decimal("1.10")
    assert Decimal(str(inv["total"])) == Decimal("1000")  # document stays in EUR

    # Trial balance is in base currency (USD). The AR debit must be 1100.
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    ar_row = next(r for r in rows if r["code"] == "1100")
    assert Decimal(str(ar_row["total_debit"])) == Decimal("1100")
    # Σdebit == Σcredit (balanced)
    assert _sum_dec(rows, "total_debit") == _sum_dec(rows, "total_credit")


def test_invoice_in_base_currency_uses_rate_1(client: TestClient):
    auth = _auth(client)
    cust = client.post("/api/customers", headers=auth, json={"name": "Bob"}).json()
    r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-05-02",
            "due_date": "2026-05-31",
            "gst_rate": 0,
            # No currency → defaults to tenant base
            "lines": [{"description": "S", "qty": 1, "rate": 500}],
        },
    )
    assert r.status_code == 201
    inv = r.json()
    assert inv["currency"] == "USD"
    assert Decimal(str(inv["exchange_rate"])) == Decimal("1")
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    ar = next(r for r in rows if r["code"] == "1100")
    assert Decimal(str(ar["total_debit"])) == Decimal("500")


def test_missing_fx_rate_rejects_invoice(client: TestClient):
    auth = _auth(client)
    cust = client.post("/api/customers", headers=auth, json={"name": "C"}).json()
    r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-05-02",
            "due_date": "2026-05-31",
            "gst_rate": 0,
            "currency": "GBP",   # no rate configured
            "lines": [{"description": "S", "qty": 1, "rate": 100}],
        },
    )
    assert r.status_code == 400
    assert "GBP" in r.json()["detail"]
