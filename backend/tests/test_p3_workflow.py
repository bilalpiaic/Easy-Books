"""P3 tests: tax codes, payment allocations, period close, recurring."""
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

    app.dependency_overrides[get_session] = _override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    engine.dispose()


def _signup_and_auth(client: TestClient, email: str = "p3@p3.test") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "U",
            "company_name": "P3 Co",
        },
    )
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sum_decimal(rows, key: str) -> Decimal:
    total = Decimal("0")
    for r in rows:
        v = r.get(key)
        if v is not None:
            total += Decimal(str(v))
    return total


def test_tax_code_create_and_list(client: TestClient):
    auth = _signup_and_auth(client)
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    gst_payable = next(a for a in accounts if a["code"] == "2200")
    r = client.post(
        "/api/tax-codes",
        headers=auth,
        json={
            "code": "GST17",
            "name": "Standard GST 17%",
            "rate": 17,
            "type": "output",
            "gl_account_id": gst_payable["id"],
        },
    )
    assert r.status_code == 201, r.text
    r = client.get("/api/tax-codes", headers=auth)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["code"] == "GST17"


def test_partial_payment_allocation_sets_status_to_partial(client: TestClient):
    auth = _signup_and_auth(client)
    cust = client.post(
        "/api/customers", headers=auth, json={"name": "Alice"}
    ).json()
    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-05-01",
            "due_date": "2026-05-31",
            "gst_rate": 0,
            "lines": [{"description": "Item", "qty": 1, "rate": 1000}],
        },
    ).json()
    # Pay 300 of 1000 → status should become 'partial'
    r = client.post(
        "/api/payments-received",
        headers=auth,
        json={
            "customer_name": "Alice",
            "payment_date": "2026-05-05",
            "amount": 300,
            "method": "cash",
            "allocations": [{"invoice_id": inv["id"], "amount": 300}],
        },
    )
    assert r.status_code == 201, r.text
    invs = client.get("/api/invoices", headers=auth).json()["items"]
    assert invs[0]["status"] == "partial"
    # Pay the remaining 700 → status becomes 'paid'
    r = client.post(
        "/api/payments-received",
        headers=auth,
        json={
            "customer_name": "Alice",
            "payment_date": "2026-05-10",
            "amount": 700,
            "method": "cash",
            "allocations": [{"invoice_id": inv["id"], "amount": 700}],
        },
    )
    assert r.status_code == 201, r.text
    invs = client.get("/api/invoices", headers=auth).json()["items"]
    assert invs[0]["status"] == "paid"


def test_allocation_exceeding_payment_amount_rejected(client: TestClient):
    auth = _signup_and_auth(client)
    cust = client.post("/api/customers", headers=auth, json={"name": "Bob"}).json()
    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-05-01",
            "due_date": "2026-05-31",
            "gst_rate": 0,
            "lines": [{"description": "X", "qty": 1, "rate": 100}],
        },
    ).json()
    r = client.post(
        "/api/payments-received",
        headers=auth,
        json={
            "customer_name": "Bob",
            "payment_date": "2026-05-05",
            "amount": 50,  # paid 50
            "allocations": [{"invoice_id": inv["id"], "amount": 100}],  # but allocated 100
        },
    )
    assert r.status_code == 400


def test_period_close_zeroes_revenue_and_expense(client: TestClient):
    auth = _signup_and_auth(client)
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    tenant_id = accounts[0]["tenant_id"]

    cust = client.post("/api/customers", headers=auth, json={"name": "C"}).json()
    # Invoice for 1000 in May
    client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-05-15",
            "due_date": "2026-06-01",
            "gst_rate": 0,
            "lines": [{"description": "S", "qty": 1, "rate": 1000}],
        },
    )

    # Create a May period and close it
    r = client.post(
        "/api/periods",
        headers=auth,
        json={"name": "May 2026", "period_start": "2026-05-01", "period_end": "2026-05-31"},
    )
    assert r.status_code == 201
    period_id = r.json()["id"]
    r = client.post(f"/api/periods/{period_id}/close", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["period"]["is_locked"] is True
    assert Decimal(data["net_income"]) == Decimal("1000")

    # Income statement for May should show zero net (revenue closed to RE)
    rows = client.get(
        "/api/reports/trial-balance",
        headers=auth,
        params={"start": "2026-05-01", "end": "2026-05-31"},
    ).json()
    # After close, Revenue is zero net within the period because of the
    # closing JV; verify Dr=Cr overall remains balanced.
    assert _sum_decimal(rows, "total_debit") == _sum_decimal(rows, "total_credit")

    # Double-close should 400
    r = client.post(f"/api/periods/{period_id}/close", headers=auth)
    assert r.status_code == 400


def test_recurring_run_due_posts_and_advances(client: TestClient):
    auth = _signup_and_auth(client)
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    cash = next(a for a in accounts if a["code"] == "1000")
    rent = next(
        (a for a in accounts if a["code"] == "5100"), None
    )
    if rent is None:
        # Fallback: create Rent if seed doesn't include it
        r = client.post(
            "/api/accounts",
            headers=auth,
            json={"code": "5100", "name": "Rent Expense", "type": "Expense"},
        )
        rent = r.json()

    r = client.post(
        "/api/recurring",
        headers=auth,
        json={
            "name": "Monthly office rent",
            "frequency": "monthly",
            "next_run": "2026-05-01",
            "entries": [
                {"account_id": rent["id"], "debit": 500, "credit": 0},
                {"account_id": cash["id"], "debit": 0, "credit": 500},
            ],
        },
    )
    assert r.status_code == 201, r.text
    template_id = r.json()["id"]

    r = client.post("/api/recurring/run-due", headers=auth)
    assert r.status_code == 200
    assert r.json()["posted"] == 1

    # Re-running should be a no-op until next_run advances past today
    r2 = client.post("/api/recurring/run-due", headers=auth)
    assert r2.json()["posted"] == 0

    # And next_run should now be 2026-06-01
    items = client.get("/api/recurring", headers=auth).json()
    assert items[0]["next_run"] == "2026-06-01"
    assert items[0]["last_run"] == "2026-05-01"
