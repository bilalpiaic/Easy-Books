"""P2 tests: RBAC, HttpOnly cookie auth, login throttle."""
from collections import deque

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from db import get_session
from main import app
from models import User
from routers.auth import _login_attempts


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
    # Reset throttle bookkeeping per test
    _login_attempts.clear()
    yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def _signup(client: TestClient, email: str) -> None:
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "U",
            "company_name": "Co",
        },
    )
    assert r.status_code == 200, r.text


def test_signup_assigns_owner_role(client):
    c, engine = client
    _signup(c, "owner@x.test")
    with Session(engine) as s:
        u = s.exec(SQLModel.metadata.tables["user"].select()).first()
        # Use raw row by index — Pydantic User model is also fine, but this
        # avoids reimporting User into the assert.
        assert u.role == "owner"


def test_login_sets_httponly_cookie(client):
    c, _ = client
    _signup(c, "a@a.test")
    r = c.post(
        "/api/auth/login", data={"username": "a@a.test", "password": "password123"}
    )
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert "eb_access=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie.lower() or "samesite=lax" in set_cookie.lower()


def test_cookie_alone_authenticates_subsequent_requests(client):
    c, _ = client
    _signup(c, "b@b.test")
    # TestClient persists cookies on the session
    c.post(
        "/api/auth/login", data={"username": "b@b.test", "password": "password123"}
    )
    # No Authorization header supplied — must still authenticate via cookie
    r = c.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "b@b.test"


def test_logout_clears_cookie(client):
    c, _ = client
    _signup(c, "lo@lo.test")
    c.post(
        "/api/auth/login", data={"username": "lo@lo.test", "password": "password123"}
    )
    r = c.post("/api/auth/logout")
    assert r.status_code == 200
    # After logout, /me without a cookie must 401. We pop the cookie jar.
    c.cookies.clear()
    r = c.get("/api/auth/me")
    assert r.status_code == 401


def test_viewer_cannot_write_owner_can(client):
    c, engine = client
    _signup(c, "vw@vw.test")
    # Demote the owner to viewer in DB
    with Session(engine) as s:
        from models import User as UserModel
        u = s.query(UserModel).filter(UserModel.email == "vw@vw.test").first()
        u.role = "viewer"
        s.add(u)
        s.commit()
    r = c.post(
        "/api/auth/login", data={"username": "vw@vw.test", "password": "password123"}
    )
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # Viewer trying to create a customer → 403
    r = c.post("/api/customers", headers=headers, json={"name": "Nope"})
    assert r.status_code == 403, r.text

    # Promote to accountant: should succeed
    with Session(engine) as s:
        from models import User as UserModel
        u = s.query(UserModel).filter(UserModel.email == "vw@vw.test").first()
        u.role = "accountant"
        s.add(u)
        s.commit()
    r = c.post("/api/customers", headers=headers, json={"name": "Yes"})
    assert r.status_code == 201, r.text


def test_login_throttle_kicks_in_after_too_many_attempts(client):
    c, _ = client
    _signup(c, "th@th.test")
    # Burn through the limit with wrong password
    for _ in range(10):
        r = c.post(
            "/api/auth/login",
            data={"username": "th@th.test", "password": "wrong"},
        )
        assert r.status_code == 401
    # 11th attempt should be throttled regardless of credentials
    r = c.post(
        "/api/auth/login",
        data={"username": "th@th.test", "password": "password123"},
    )
    assert r.status_code == 429


def test_password_min_length_enforced(client):
    c, _ = client
    r = c.post(
        "/api/auth/signup",
        json={
            "email": "short@x.test",
            "password": "abc",  # < 8
            "full_name": "U",
            "company_name": "Co",
        },
    )
    assert r.status_code == 422
