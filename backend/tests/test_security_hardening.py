"""Commit C tests: CSRF protection on cookie-auth mutations, DB-backed throttle."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import LoginAttempt


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


def _signup_and_login_via_cookie(c: TestClient) -> str:
    """Returns the CSRF token; cookies are persisted on the client session."""
    c.post(
        "/api/auth/signup",
        json={
            "email": "csrf@x.test", "password": "password123",
            "full_name": "U", "company_name": "Co",
        },
    )
    r = c.post(
        "/api/auth/login",
        data={"username": "csrf@x.test", "password": "password123"},
    )
    return r.json()["csrf_token"]


# ── B7: CSRF ─────────────────────────────────────────────────────────────────


def test_cookie_auth_post_without_csrf_header_is_rejected(client):
    c, _ = client
    _signup_and_login_via_cookie(c)
    # No X-CSRF-Token header → 403
    r = c.post("/api/customers", json={"name": "X"})
    assert r.status_code == 403
    assert "csrf" in r.json()["detail"].lower()


def test_cookie_auth_post_with_matching_csrf_header_succeeds(client):
    c, _ = client
    csrf = _signup_and_login_via_cookie(c)
    r = c.post(
        "/api/customers",
        json={"name": "Y"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 201


def test_cookie_auth_post_with_wrong_csrf_header_is_rejected(client):
    c, _ = client
    _signup_and_login_via_cookie(c)
    r = c.post(
        "/api/customers",
        json={"name": "Z"},
        headers={"X-CSRF-Token": "bogus"},
    )
    assert r.status_code == 403


def test_bearer_auth_post_does_not_require_csrf(client):
    c, _ = client
    # Sign up and login, take the bearer token, drop the cookies so CSRF
    # middleware's "is cookie auth?" check sees no cookie.
    c.post(
        "/api/auth/signup",
        json={
            "email": "bear@x.test", "password": "password123",
            "full_name": "U", "company_name": "Co",
        },
    )
    r = c.post(
        "/api/auth/login",
        data={"username": "bear@x.test", "password": "password123"},
    )
    token = r.json()["access_token"]
    c.cookies.clear()
    # Bearer-only POST: no CSRF expected.
    r = c.post(
        "/api/customers",
        json={"name": "OnlyBearer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201


# ── B9: DB-backed throttle ──────────────────────────────────────────────────


def test_login_attempts_are_persisted_in_db(client):
    c, engine = client
    # 3 failed logins
    for _ in range(3):
        c.post(
            "/api/auth/login",
            data={"username": "ghost@x.test", "password": "wrong"},
        )
    with Session(engine) as s:
        rows = s.exec(select(LoginAttempt)).all()
        assert len(rows) == 3


def test_db_throttle_blocks_after_limit(client):
    c, _ = client
    for _ in range(10):
        c.post(
            "/api/auth/login",
            data={"username": "x@x.test", "password": "wrong"},
        )
    r = c.post(
        "/api/auth/login",
        data={"username": "x@x.test", "password": "wrong"},
    )
    assert r.status_code == 429
