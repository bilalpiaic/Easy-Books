"""Dual-home Operations summary API — module gating + empty bag for base tenants."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import Tenant, User
from auth import get_password_hash


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    app.state.engine = engine
    app.dependency_overrides[get_session] = _override
    c = TestClient(app)
    yield c, engine
    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _signup(c, email, business_model="simple"):
    r = c.post("/api/auth/signup", json={
        "email": email, "password": "password123", "full_name": "U",
        "company_name": "Co", "business_model": business_model,
    })
    assert r.status_code in (200, 201), r.text
    tok = c.post("/api/auth/login", data={
        "username": email, "password": "password123",
    }).json()["access_token"]
    c.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def test_operations_available_false_for_simple(client):
    c, _engine = client
    auth = _signup(c, "simple@ops.test", "simple")
    r = c.get("/api/dashboard/operations-available", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is False
    assert body["modules"] == []


def test_operations_summary_empty_modules_for_simple(client):
    c, _engine = client
    auth = _signup(c, "simple2@ops.test", "simple")
    r = c.get("/api/dashboard/operations-summary", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["modules"] == []
    assert "spinning" not in body
    assert "production" not in body


def test_operations_available_for_manufacturing(client):
    c, engine = client
    auth = _signup(c, "mfg@ops.test", "manufacturing")
    # Force modules in case signup ignores model (API may only allow certain models)
    with Session(engine) as s:
        u = s.exec(select(User).where(User.email == "mfg@ops.test")).first()
        t = s.get(Tenant, u.tenant_id)
        t.enabled_modules = json.dumps(["base", "inventory", "production", "purchase_store", "weaving"])
        t.business_model = "manufacturing"
        s.add(t)
        s.commit()

    r = c.get("/api/dashboard/operations-available", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True
    assert "production" in body["modules"]
    assert "purchase_store" in body["modules"]

    summary = c.get("/api/dashboard/operations-summary", headers=auth)
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert "production" in data
    assert "purchase_store" in data
    assert "pipeline" in data["production"]
    assert "open_demands" in data["purchase_store"]


def test_operations_summary_requires_auth(client):
    c, _engine = client
    r = c.get("/api/dashboard/operations-summary")
    assert r.status_code in (401, 403)
