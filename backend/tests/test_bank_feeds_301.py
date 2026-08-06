"""Open Banking / bank feed sync depth (#301)."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from main import app
from models import PlaidConnection, StatementLine
from services.bank_sync import sync_all_active_connections


def _auth(client: TestClient, email: str = "feeds301@co.test"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Feeds",
            "company_name": "Feeds Co",
        },
    )
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _bank(client, auth) -> int:
    r = client.post(
        "/api/bank-accounts",
        headers=auth,
        json={"name": "Checking", "account_number": "301"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_mock_connect_sync_and_status(client: TestClient):
    auth = _auth(client)
    ba = _bank(client, auth)

    r = client.post(
        "/api/banking/feeds/mock/connect",
        headers=auth,
        json={"bank_account_id": ba, "institution_name": "Mock OBIE Sandbox"},
    )
    assert r.status_code == 201, r.text
    conn = r.json()
    assert conn["provider"] == "mock"
    assert conn["sync_status"] == "never"
    assert conn["consent_expires_at"]

    listed = client.get("/api/banking/feeds/connections", headers=auth).json()
    assert any(c["id"] == conn["id"] for c in listed)

    sync = client.post(f"/api/banking/feeds/{conn['id']}/sync", headers=auth)
    assert sync.status_code == 200, sync.text
    body = sync.json()
    assert body["ok"] is True
    assert body["imported"] == 3
    assert body["sync_status"] == "ok"

    sync2 = client.post(f"/api/banking/feeds/{conn['id']}/sync", headers=auth)
    assert sync2.status_code == 200
    assert sync2.json()["imported"] == 0
    assert sync2.json()["skipped"] == 3

    status = client.get("/api/banking/feeds/connections", headers=auth).json()
    row = next(c for c in status if c["id"] == conn["id"])
    assert row["sync_status"] == "ok"
    assert row["last_sync"]
    assert row["last_error"] is None


def test_consent_expired_blocks_sync(client: TestClient):
    auth = _auth(client, "consent301@co.test")
    ba = _bank(client, auth)
    r = client.post(
        "/api/banking/feeds/mock/connect",
        headers=auth,
        json={"bank_account_id": ba, "consent_days": 90},
    )
    assert r.status_code == 201
    conn_id = r.json()["id"]

    with Session(app.state.engine) as session:
        conn = session.get(PlaidConnection, conn_id)
        assert conn is not None
        conn.consent_expires_at = datetime.utcnow() - timedelta(days=1)
        session.add(conn)
        session.commit()

    listed = client.get("/api/banking/feeds/connections", headers=auth).json()
    row = next(c for c in listed if c["id"] == conn_id)
    assert row["sync_status"] == "consent_expired"

    sync = client.post(f"/api/banking/feeds/{conn_id}/sync", headers=auth)
    assert sync.status_code == 400
    assert "consent" in sync.json()["detail"].lower()


def test_scheduler_syncs_mock_connections(client: TestClient):
    auth = _auth(client, "sched301@co.test")
    ba = _bank(client, auth)
    r = client.post(
        "/api/banking/feeds/mock/connect",
        headers=auth,
        json={"bank_account_id": ba},
    )
    assert r.status_code == 201

    with Session(app.state.engine) as session:
        counts = sync_all_active_connections(session)
        assert counts["ok"] >= 1
        lines = session.exec(select(StatementLine)).all()
        descs = {ln.description for ln in lines}
        assert any("RENT ACME" in d for d in descs)


def test_plaid_list_includes_sync_status_fields(client: TestClient):
    auth = _auth(client, "plaidstatus301@co.test")
    ba = _bank(client, auth)
    client.post(
        "/api/banking/feeds/mock/connect",
        headers=auth,
        json={"bank_account_id": ba},
    )
    rows = client.get("/api/banking/plaid/connections", headers=auth).json()
    assert rows
    assert "sync_status" in rows[0]
    assert "provider" in rows[0]
    assert "last_error" in rows[0]
