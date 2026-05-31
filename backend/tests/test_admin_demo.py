"""Tests for WS-2: admin endpoints to load/remove demo sample data.

POST  /api/admin/demo/seed  — idempotent seeder, admin+ only
DELETE /api/admin/demo/seed  — purge the 5 demo tenants, admin+ only
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db as _db_module
from db import get_session
from main import app


@pytest.fixture(name="client")
def client_fixture(monkeypatch):
    """In-memory SQLite engine, overrides both the FastAPI session dep and the
    module-level `db.engine` that the seeder (scripts.seed_demo) uses directly."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    # Patch db.engine AND the seeder's own module-level `engine` binding so the
    # seeder deterministically targets the in-memory test DB regardless of import
    # order (scripts.seed_demo does `from db import engine` at import time, so
    # patching db.engine alone is not enough if it was imported earlier).
    monkeypatch.setattr(_db_module, "engine", engine)
    import scripts.seed_demo as _seed_mod
    monkeypatch.setattr(_seed_mod, "engine", engine)
    app.state.engine = engine
    app.dependency_overrides[get_session] = _override

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _admin_headers(client: TestClient) -> dict:
    """Sign up a new tenant; the first user is automatically 'owner'.
    'owner' has a higher role rank than 'admin', so AdminUserDep passes.
    """
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "owner@acme.test",
            "password": "pw12345678",
            "full_name": "Owner",
            "company_name": "Acme",
        },
    )
    assert r.status_code == 200, r.text
    tok = client.post(
        "/api/auth/login",
        data={"username": "owner@acme.test", "password": "pw12345678"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_demo_seed_is_idempotent_and_admin_gated(client):
    # 1. No token → 401
    assert client.post("/api/admin/demo/seed").status_code == 401

    headers = _admin_headers(client)

    # 2. First seed — creates all 5 demo tenants with rich data
    r1 = client.post("/api/admin/demo/seed", headers=headers)
    assert r1.status_code == 200, r1.text
    assert len(r1.json()["tenants"]) == 5

    # 3. Second seed — idempotent; same 5 entries, no error, no duplicates
    r2 = client.post("/api/admin/demo/seed", headers=headers)
    assert r2.status_code == 200
    emails = {t["email"] for t in r2.json()["tenants"]}
    assert "demo.simple@easy-books.app" in emails

    # 4. Purge — removes at least the 5 demo tenants
    rd = client.delete("/api/admin/demo/seed", headers=headers)
    assert rd.status_code == 200, rd.text
    assert rd.json()["removed_tenants"] >= 5

    # 5. The caller's OWN tenant must survive the purge (the critical safety
    #    invariant: purge deletes only the demo tenants, never the caller's data).
    relogin = client.post(
        "/api/auth/login",
        data={"username": "owner@acme.test", "password": "pw12345678"},
    )
    assert relogin.status_code == 200, "purge must not delete the caller's own account"
    # And a second purge is a harmless no-op once the demo tenants are gone.
    rd2 = client.delete("/api/admin/demo/seed", headers=headers)
    assert rd2.status_code == 200
    assert rd2.json()["removed_tenants"] == 0
