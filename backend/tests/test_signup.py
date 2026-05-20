"""Signup + login smoke tests."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import Account, Tenant, User


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


def test_signup_flow(client):
    c, engine = client
    signup_data = {
        "email": "test@example.com",
        "password": "password123",
        "full_name": "Test User",
        "company_name": "Test Company",
    }
    r = c.post("/api/auth/signup", json=signup_data)
    assert r.status_code == 200
    assert r.json()["success"] is True

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "test@example.com")).first()
        assert user is not None
        assert user.full_name == "Test User"

        tenant = session.exec(select(Tenant).where(Tenant.id == user.tenant_id)).first()
        assert tenant.name == "Test Company"

        accounts = session.exec(select(Account).where(Account.tenant_id == tenant.id)).all()
        assert len(accounts) > 0
        assert any(a.name == "Cash in Hand" for a in accounts)


def test_login_flow(client):
    c, _ = client
    c.post(
        "/api/auth/signup",
        json={
            "email": "test@example.com",
            "password": "password123",
            "full_name": "Test User",
            "company_name": "Test Company",
        },
    )
    r = c.post(
        "/api/auth/login",
        data={"username": "test@example.com", "password": "password123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert r.json()["token_type"] == "bearer"
