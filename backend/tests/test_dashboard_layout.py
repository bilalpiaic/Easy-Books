"""#52 §3 — per-user dashboard layout store: round-trip + per-user/tenant isolation."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from auth import get_password_hash
from db import get_session
from main import app
from models import User


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


def _signup(c, email):
    """Signup creates a NEW tenant; first user is its owner. Returns Bearer headers."""
    c.post("/api/auth/signup", json={
        "email": email, "password": "password123", "full_name": "U", "company_name": "Co",
    })
    tok = c.post("/api/auth/login", data={
        "username": email, "password": "password123",
    }).json()["access_token"]
    c.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def _tenant_id(engine, email):
    with Session(engine) as s:
        return s.exec(select(User).where(User.email == email)).first().tenant_id


def _add_user_to_tenant(engine, email, tenant_id, role="accountant"):
    with Session(engine) as s:
        s.add(User(
            email=email, hashed_password=get_password_hash("password123"),
            full_name="Second", role=role, tenant_id=tenant_id, is_active=True,
        ))
        s.commit()


def _login(c, email):
    tok = c.post("/api/auth/login", data={
        "username": email, "password": "password123",
    }).json()["access_token"]
    c.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def test_layout_defaults_to_null_when_unset(client):
    c, engine = client
    auth = _signup(c, "a@t.test")
    r = c.get("/api/dashboard/layout", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"layout": None}


def test_layout_round_trips(client):
    c, engine = client
    auth = _signup(c, "a@t.test")
    payload = {"layout": {"version": 1, "widgets": [
        {"id": "primary_kpis", "visible": True},
        {"id": "ar_aging", "visible": False},
    ]}}
    put = c.put("/api/dashboard/layout", headers=auth, json=payload)
    assert put.status_code == 200, put.text
    got = c.get("/api/dashboard/layout", headers=auth).json()
    assert got["layout"] == payload["layout"]


def test_layout_per_user_isolation_same_tenant(client):
    """Two users in the SAME tenant must have independent layouts — guards
    against keying the store by tenant_id only (like the Settings table)."""
    c, engine = client
    auth_a = _signup(c, "owner@t.test")
    tid = _tenant_id(engine, "owner@t.test")
    _add_user_to_tenant(engine, "clerk@t.test", tid)
    auth_b = _login(c, "clerk@t.test")

    c.put("/api/dashboard/layout", headers=auth_a, json={"layout": {"version": 1, "widgets": [{"id": "primary_kpis", "visible": False}]}})

    # B in the same tenant is unaffected — still default.
    assert c.get("/api/dashboard/layout", headers=auth_b).json() == {"layout": None}
    # A keeps its own.
    assert c.get("/api/dashboard/layout", headers=auth_a).json()["layout"]["widgets"][0]["visible"] is False


def test_layout_tenant_isolation(client):
    c, engine = client
    auth_a = _signup(c, "a@t.test")
    auth_b = _signup(c, "b@t.test")
    c.put("/api/dashboard/layout", headers=auth_a, json={"layout": {"version": 1, "widgets": [{"id": "ar_aging", "visible": False}]}})
    assert c.get("/api/dashboard/layout", headers=auth_b).json() == {"layout": None}


def test_layout_rejects_non_object(client):
    c, engine = client
    auth = _signup(c, "a@t.test")
    r = c.put("/api/dashboard/layout", headers=auth, json={"layout": [1, 2, 3]})
    assert r.status_code == 422
