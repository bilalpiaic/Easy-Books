"""End-to-end API integration tests via TestClient.

Exercises the live FastAPI app over a fresh SQLite DB:
- signup → invoice → payment → trial balance balances (∑Dr == ∑Cr)
- tenant isolation (two tenants can't see each other's data)
- transaction reversal nets to zero across endpoints
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from db import get_session
from main import app


@pytest.fixture(name="client")
def client_fixture():
    # Per-test in-memory SQLite — StaticPool keeps a single connection alive
    # so all sessions share the same database without file I/O.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    engine.dispose()


def _signup_and_login(client: TestClient, email: str, company: str) -> dict:
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Test User",
            "company_name": company,
        },
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "password123"}
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _sum_decimal(rows, key: str) -> Decimal:
    total = Decimal("0")
    for r in rows:
        v = r.get(key)
        if v is None:
            continue
        total += Decimal(str(v))
    return total


# ── Test 1: signup → invoice → payment → trial balance balances ──────────────


def test_full_invoice_to_payment_flow_keeps_trial_balance_balanced(client: TestClient):
    auth = _signup_and_login(client, "owner@acme.test", "Acme Co")

    # Create a customer
    r = client.post(
        "/api/customers",
        headers=auth,
        json={"name": "Bob Buyer", "email": "bob@buyer.test"},
    )
    assert r.status_code == 201, r.text
    customer_id = r.json()["id"]

    # Create an invoice (no GST for simpler arithmetic)
    r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": customer_id,
            "issue_date": "2026-05-01",
            "due_date": "2026-05-31",
            "description": "Consulting services",
            "gst_rate": 0,
            "lines": [
                {"description": "Design hours", "qty": 10, "rate": 100},
            ],
        },
    )
    assert r.status_code == 201, r.text
    invoice = r.json()
    assert Decimal(str(invoice["total"])) == Decimal("1000")

    # Receive a partial payment
    r = client.post(
        "/api/payments-received",
        headers=auth,
        json={
            "invoice_id": invoice["id"],
            "customer_name": "Bob Buyer",
            "payment_date": "2026-05-02",
            "amount": 400,
            "method": "cash",
        },
    )
    assert r.status_code == 201, r.text

    # Trial balance should balance: ∑Dr == ∑Cr
    r = client.get("/api/reports/trial-balance", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    total_debit = Decimal(str(body["totals"]["debit"]))
    total_credit = Decimal(str(body["totals"]["credit"]))
    assert total_debit == total_credit, f"Dr={total_debit} Cr={total_credit}"
    assert total_debit > 0  # something actually posted


# ── Test 2: tenant isolation ─────────────────────────────────────────────────


def test_two_tenants_cannot_see_each_others_data(client: TestClient):
    auth_a = _signup_and_login(client, "a@a.test", "Tenant A")
    auth_b = _signup_and_login(client, "b@b.test", "Tenant B")

    # Tenant A creates a customer
    r = client.post(
        "/api/customers", headers=auth_a, json={"name": "Alice (A only)"}
    )
    assert r.status_code == 201
    a_customer_id = r.json()["id"]

    # Tenant B creates a customer
    r = client.post(
        "/api/customers", headers=auth_b, json={"name": "Bruce (B only)"}
    )
    assert r.status_code == 201

    # Tenant B should not see Tenant A's customer in the list
    r = client.get("/api/customers", headers=auth_b)
    assert r.status_code == 200
    b_names = {c["name"] for c in r.json()["items"]}
    assert "Alice (A only)" not in b_names
    assert "Bruce (B only)" in b_names

    # Tenant B trying to UPDATE Tenant A's customer should 404
    r = client.put(
        f"/api/customers/{a_customer_id}",
        headers=auth_b,
        json={"name": "Hijacked"},
    )
    assert r.status_code == 404

    # Tenant A creates an invoice; Tenant B's trial balance must not include it
    r = client.post(
        "/api/invoices",
        headers=auth_a,
        json={
            "customer_id": a_customer_id,
            "issue_date": "2026-05-01",
            "due_date": "2026-05-31",
            "description": "A-only invoice",
            "gst_rate": 0,
            "lines": [{"description": "Item", "qty": 1, "rate": 500}],
        },
    )
    assert r.status_code == 201

    r = client.get("/api/reports/trial-balance", headers=auth_b)
    assert r.status_code == 200
    # Tenant B has no transactions → empty trial balance tree
    body_b = r.json()
    assert body_b["tree"] == []
    assert Decimal(str(body_b["totals"]["debit"])) == Decimal("0")


# ── Test 3: reversal nets to zero across the GL ──────────────────────────────


def test_transaction_reversal_nets_to_zero(client: TestClient):
    auth = _signup_and_login(client, "rev@rev.test", "Reversal Co")

    # Seed gives us a Chart of Accounts. Fetch two accounts to post against.
    r = client.get("/api/accounts", headers=auth)
    assert r.status_code == 200
    accounts = r.json()["items"]
    cash = next(a for a in accounts if a["code"] == "1000")
    sales = next(a for a in accounts if a["code"] == "4000")
    tenant_id = cash["tenant_id"]

    # Post a manual JV: Dr Cash 250 / Cr Sales 250
    r = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "tenant_id": tenant_id,
            "date": "2026-05-10",
            "description": "Manual sale",
            "entries": [
                {
                    "tenant_id": tenant_id,
                    "account_id": cash["id"],
                    "debit": 250,
                    "credit": 0,
                },
                {
                    "tenant_id": tenant_id,
                    "account_id": sales["id"],
                    "debit": 0,
                    "credit": 250,
                },
            ],
        },
    )
    assert r.status_code == 200, r.text
    tx_id = r.json()["id"]

    # Trial balance after first JV
    r = client.get("/api/reports/trial-balance", headers=auth)
    tb_after_post = r.json()
    assert Decimal(str(tb_after_post["totals"]["debit"])) == Decimal("250")
    assert Decimal(str(tb_after_post["totals"]["credit"])) == Decimal("250")

    # Reverse it
    r = client.post(f"/api/transactions/{tx_id}/reverse", headers=auth)
    assert r.status_code == 200, r.text

    # After reversal: each account has equal debit AND credit totals,
    # so net (Dr - Cr) per account == 0 and the books are balanced.
    r = client.get("/api/reports/trial-balance", headers=auth)
    tb_after_rev = r.json()
    total_debit = Decimal(str(tb_after_rev["totals"]["debit"]))
    total_credit = Decimal(str(tb_after_rev["totals"]["credit"]))
    assert total_debit == total_credit
    # The cumulative debits include both the post (250) and the reversal's
    # credit-leg-turned-debit (250), so 500 on each side is the expected sum.
    assert total_debit == Decimal("500")

    # Double-reverse should be rejected
    r = client.post(f"/api/transactions/{tx_id}/reverse", headers=auth)
    assert r.status_code == 400
