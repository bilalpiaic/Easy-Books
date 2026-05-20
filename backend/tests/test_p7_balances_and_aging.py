"""P7 tests: materialised balances on period close + correct aging."""
from datetime import date as DateType, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import AccountBalance


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


def _auth(client: TestClient) -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": "p7@p7.test",
            "password": "password123",
            "full_name": "U",
            "company_name": "P7 Co",
        },
    )
    r = client.post(
        "/api/auth/login", data={"username": "p7@p7.test", "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _invoice(client: TestClient, auth, cust_id: int, total: int, days_overdue: int):
    """Create an invoice whose due_date is N days ago. issue_date stays current."""
    due = (DateType.today() - timedelta(days=days_overdue)).isoformat()
    issue = (DateType.today() - timedelta(days=days_overdue + 30)).isoformat()
    return client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust_id,
            "issue_date": issue,
            "due_date": due,
            "gst_rate": 0,
            "lines": [{"description": "S", "qty": 1, "rate": total}],
        },
    ).json()


def test_period_close_writes_materialised_balances(client):
    c, engine = client
    auth = _auth(c)
    cust = c.post("/api/customers", headers=auth, json={"name": "C"}).json()
    # An invoice inside the period (use today() for simplicity)
    c.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": DateType.today().isoformat(),
            "due_date": DateType.today().isoformat(),
            "gst_rate": 0,
            "lines": [{"description": "X", "qty": 1, "rate": 800}],
        },
    )
    # Close a period that spans today
    today_iso = DateType.today().isoformat()
    p = c.post(
        "/api/periods",
        headers=auth,
        json={"name": "Current", "period_start": "2026-01-01", "period_end": today_iso},
    ).json()
    r = c.post(f"/api/periods/{p['id']}/close", headers=auth)
    assert r.status_code == 200

    # AccountBalance rows must exist for the closed period
    with Session(engine) as s:
        rows = s.exec(
            select(AccountBalance).where(AccountBalance.period_id == p["id"])
        ).all()
        assert len(rows) > 0
        # AR (code 1100) should have a 800 debit
        ar_rows = [r for r in rows if Decimal(str(r.debit_total)) == Decimal("800")]
        assert len(ar_rows) >= 1


def test_reopen_period_invalidates_materialised_balances(client):
    c, engine = client
    auth = _auth(c)
    cust = c.post("/api/customers", headers=auth, json={"name": "C"}).json()
    c.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": DateType.today().isoformat(),
            "due_date": DateType.today().isoformat(),
            "gst_rate": 0,
            "lines": [{"description": "X", "qty": 1, "rate": 100}],
        },
    )
    today_iso = DateType.today().isoformat()
    p = c.post(
        "/api/periods", headers=auth,
        json={"name": "X", "period_start": "2026-01-01", "period_end": today_iso},
    ).json()
    c.post(f"/api/periods/{p['id']}/close", headers=auth)

    with Session(engine) as s:
        before = s.exec(
            select(AccountBalance).where(AccountBalance.period_id == p["id"])
        ).all()
        assert len(before) > 0

    r = c.post(f"/api/periods/{p['id']}/reopen", headers=auth)
    assert r.status_code == 200
    assert r.json()["is_locked"] is False

    with Session(engine) as s:
        after = s.exec(
            select(AccountBalance).where(AccountBalance.period_id == p["id"])
        ).all()
        assert after == []


def test_aging_uses_outstanding_balance_not_gross_total(client):
    c, _ = client
    auth = _auth(c)
    cust = c.post("/api/customers", headers=auth, json={"name": "Alice"}).json()
    # $1000 invoice, due 45 days ago → would land in 31-60 bucket
    inv = _invoice(c, auth, cust["id"], total=1000, days_overdue=45)
    # Partial payment of $700
    r = c.post(
        "/api/payments-received",
        headers=auth,
        json={
            "customer_name": "Alice",
            "payment_date": DateType.today().isoformat(),
            "amount": 700,
            "allocations": [{"invoice_id": inv["id"], "amount": 700}],
        },
    )
    assert r.status_code == 201

    aging = c.get("/api/invoices/aging", headers=auth).json()
    # Outstanding is 300, not 1000; lands in 31-60 (45 days past)
    assert Decimal(str(aging["31_60"])) == Decimal("300")
    assert len(aging["items"]) == 1
    assert Decimal(str(aging["items"][0]["amount"])) == Decimal("300")


def test_aging_skips_fully_paid_invoices(client):
    c, _ = client
    auth = _auth(c)
    cust = c.post("/api/customers", headers=auth, json={"name": "Bob"}).json()
    inv = _invoice(c, auth, cust["id"], total=500, days_overdue=10)
    # Pay the full amount
    c.post(
        "/api/payments-received",
        headers=auth,
        json={
            "customer_name": "Bob",
            "payment_date": DateType.today().isoformat(),
            "amount": 500,
            "allocations": [{"invoice_id": inv["id"], "amount": 500}],
        },
    )
    aging = c.get("/api/invoices/aging", headers=auth).json()
    assert aging["items"] == []
    assert Decimal(str(aging["1_30"])) == Decimal("0")
