"""Commit B tests: FX inverse fallback, scoped auto-match, atomic numbering."""
import io
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import Invoice


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


def _auth(client: TestClient, email: str = "b@b.test") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Op Co",
        },
    )
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── B5: FX inverse fallback ─────────────────────────────────────────────────


def test_fx_inverse_lookup_resolves_when_only_reverse_pair_exists(client):
    c, _ = client
    auth = _auth(c)
    # Catalog only has USD→EUR (the inverse of what an EUR invoice needs)
    c.post(
        "/api/exchange-rates",
        headers=auth,
        json={"date": "2026-05-01", "from_currency": "USD", "to_currency": "EUR", "rate": 0.9090909},
    )
    cust = c.post("/api/customers", headers=auth, json={"name": "EU"}).json()
    # EUR invoice → needs EUR→USD; should fall back to 1/0.9090909 ≈ 1.10
    r = c.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-05-02",
            "due_date": "2026-05-31",
            "gst_rate": 0,
            "currency": "EUR",
            "lines": [{"description": "S", "qty": 1, "rate": 1000}],
        },
    )
    assert r.status_code == 201, r.text
    rate = Decimal(str(r.json()["exchange_rate"]))
    # Within rounding tolerance of 1.10
    assert abs(rate - Decimal("1.10")) < Decimal("0.01")


# ── B6: auto-match scoped to current import ─────────────────────────────────


def test_auto_match_across_two_imports_does_not_block(client):
    c, _ = client
    auth = _auth(c)
    # Bank account
    acct = c.post(
        "/api/bank-accounts",
        headers=auth,
        json={"name": "Main", "account_number": "1"},
    ).json()
    # Single JV that's a candidate for the same-amount line in both imports
    accounts = c.get("/api/accounts", headers=auth).json()["items"]
    cash = next(a for a in accounts if a["code"] == "1000")
    sales = next(a for a in accounts if a["code"] == "4000")
    tenant_id = cash["tenant_id"]
    c.post(
        "/api/transactions",
        headers=auth,
        json={
            "tenant_id": tenant_id, "date": "2026-05-02", "description": "sale",
            "entries": [
                {"tenant_id": tenant_id, "account_id": cash["id"], "debit": 250, "credit": 0},
                {"tenant_id": tenant_id, "account_id": sales["id"], "debit": 0, "credit": 250},
            ],
        },
    )
    # First import — line for 250 should match the JV
    csv_a = "date,description,debit,credit,balance\n2026-05-02,P1,0,250,250\n"
    imp_a = c.post(
        "/api/bank-imports", headers=auth,
        data={"bank_account_id": str(acct["id"])},
        files={"file": ("a.csv", io.BytesIO(csv_a.encode()), "text/csv")},
    ).json()
    r = c.post(f"/api/bank-imports/{imp_a['id']}/auto-match", headers=auth)
    assert r.json()["newly_matched"] == 1

    # Second import (different file, same amount) — pre-fix this would
    # see the JV "already used" by import_a and skip. Post-fix it matches.
    csv_b = "date,description,debit,credit,balance\n2026-05-02,P2,0,250,250\n"
    imp_b = c.post(
        "/api/bank-imports", headers=auth,
        data={"bank_account_id": str(acct["id"])},
        files={"file": ("b.csv", io.BytesIO(csv_b.encode()), "text/csv")},
    ).json()
    r = c.post(f"/api/bank-imports/{imp_b['id']}/auto-match", headers=auth)
    assert r.json()["newly_matched"] == 1


# ── B8: atomic invoice numbering via SequenceCounter ───────────────────────


def test_invoice_numbering_uses_counter_not_count(client):
    """Numbering must come from SequenceCounter, not COUNT(*) + 1.

    Pre-fix: deleting an invoice via reversal could let the next POST mint
    the same number again (count went back down). Post-fix: the counter
    advances monotonically regardless of how many rows actually exist.
    """
    c, _ = client
    auth = _auth(c)
    cust = c.post("/api/customers", headers=auth, json={"name": "C"}).json()

    def _make():
        return c.post(
            "/api/invoices",
            headers=auth,
            json={
                "customer_id": cust["id"],
                "issue_date": "2026-05-02",
                "due_date": "2026-05-31",
                "gst_rate": 0,
                "lines": [{"description": "S", "qty": 1, "rate": 1}],
            },
        ).json()

    inv1 = _make()
    inv2 = _make()
    inv3 = _make()
    assert inv1["number"] == "INV-0001"
    assert inv2["number"] == "INV-0002"
    assert inv3["number"] == "INV-0003"

    # Reverse inv2 (so its row stays but the document is void). The next
    # invoice must be INV-0004, NOT a re-used INV-0003 or INV-0002.
    c.post(
        f"/api/transactions/{inv2['transaction_id']}/reverse", headers=auth
    )
    inv4 = _make()
    assert inv4["number"] == "INV-0004"


def test_sequence_counter_is_per_tenant(client):
    """Two tenants on the same DB get independent sequences."""
    c, _ = client
    # Tenant A
    c.post("/api/auth/signup", json={
        "email": "a@x.test", "password": "password123",
        "full_name": "A", "company_name": "A Co",
    })
    auth_a = {"Authorization": "Bearer " + c.post(
        "/api/auth/login", data={"username": "a@x.test", "password": "password123"}
    ).json()["access_token"]}
    # Tenant B
    c.post("/api/auth/signup", json={
        "email": "b@x.test", "password": "password123",
        "full_name": "B", "company_name": "B Co",
    })
    auth_b = {"Authorization": "Bearer " + c.post(
        "/api/auth/login", data={"username": "b@x.test", "password": "password123"}
    ).json()["access_token"]}

    cust_a = c.post("/api/customers", headers=auth_a, json={"name": "A Cust"}).json()
    cust_b = c.post("/api/customers", headers=auth_b, json={"name": "B Cust"}).json()
    body = {
        "issue_date": "2026-05-02", "due_date": "2026-05-31", "gst_rate": 0,
        "lines": [{"description": "S", "qty": 1, "rate": 1}],
    }
    a1 = c.post("/api/invoices", headers=auth_a, json={**body, "customer_id": cust_a["id"]}).json()
    b1 = c.post("/api/invoices", headers=auth_b, json={**body, "customer_id": cust_b["id"]}).json()
    # Each tenant starts at INV-0001 — counters don't bleed across tenants
    assert a1["number"] == "INV-0001"
    assert b1["number"] == "INV-0001"
