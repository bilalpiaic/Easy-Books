"""P6 tests: CSV upload de-dupe, auto-match by amount+date, manual match."""
import io
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
            "email": "bk@bk.test",
            "password": "password123",
            "full_name": "U",
            "company_name": "Bank Co",
        },
    )
    r = client.post(
        "/api/auth/login", data={"username": "bk@bk.test", "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _bank_account(client: TestClient, auth: dict) -> int:
    r = client.post(
        "/api/bank-accounts",
        headers=auth,
        json={"name": "Main Checking", "account_number": "12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


SAMPLE_CSV = """date,description,debit,credit,balance
2026-05-02,Customer payment Alice,0,500,1500
2026-05-03,Stripe payout,0,1000,2500
2026-05-04,Office rent,200,0,2300
"""


def test_upload_creates_statement_lines(client: TestClient):
    auth = _auth(client)
    acct_id = _bank_account(client, auth)

    files = {"file": ("statement.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")}
    r = client.post(
        "/api/bank-imports",
        headers=auth,
        data={"bank_account_id": str(acct_id)},
        files=files,
    )
    assert r.status_code == 201, r.text
    imp = r.json()
    assert imp["line_count"] == 3

    lines = client.get(f"/api/bank-imports/{imp['id']}/lines", headers=auth).json()
    assert len(lines) == 3
    assert lines[0]["description"] == "Customer payment Alice"
    assert Decimal(str(lines[0]["credit"])) == Decimal("500")


def test_duplicate_upload_409s(client: TestClient):
    auth = _auth(client)
    acct_id = _bank_account(client, auth)
    files = {"file": ("statement.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")}
    r1 = client.post(
        "/api/bank-imports",
        headers=auth,
        data={"bank_account_id": str(acct_id)},
        files=files,
    )
    assert r1.status_code == 201

    files2 = {"file": ("statement.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")}
    r2 = client.post(
        "/api/bank-imports",
        headers=auth,
        data={"bank_account_id": str(acct_id)},
        files=files2,
    )
    assert r2.status_code == 409


def test_auto_match_links_lines_to_existing_jvs_by_amount(client: TestClient):
    auth = _auth(client)
    acct_id = _bank_account(client, auth)

    # Post a JV that should be matchable: Dr Cash 500 / Cr Sales 500 on 2026-05-02
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    cash = next(a for a in accounts if a["code"] == "1000")
    sales = next(a for a in accounts if a["code"] == "4000")
    tenant_id = cash["tenant_id"]
    r = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "tenant_id": tenant_id,
            "date": "2026-05-02",
            "description": "Test sale",
            "entries": [
                {"tenant_id": tenant_id, "account_id": cash["id"], "debit": 500, "credit": 0},
                {"tenant_id": tenant_id, "account_id": sales["id"], "debit": 0, "credit": 500},
            ],
        },
    )
    assert r.status_code == 200

    # Upload the CSV
    files = {"file": ("statement.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")}
    imp = client.post(
        "/api/bank-imports",
        headers=auth,
        data={"bank_account_id": str(acct_id)},
        files=files,
    ).json()

    # Auto-match
    r = client.post(f"/api/bank-imports/{imp['id']}/auto-match", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["newly_matched"] == 1  # the 500 credit line matches the JV

    lines = client.get(f"/api/bank-imports/{imp['id']}/lines", headers=auth).json()
    matched = [l for l in lines if l["is_matched"]]
    assert len(matched) == 1
    assert Decimal(str(matched[0]["credit"])) == Decimal("500")