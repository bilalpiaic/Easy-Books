"""Shared pytest fixtures."""
import pytest

import db as _db_module
from db import get_session
from main import app
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture(autouse=True)
def _clear_login_throttle():
    """Login throttle is process-global; reset before every test so tests
    don't poison each other's IP counters."""
    from routers.auth import _login_attempts
    _login_attempts.clear()
    yield
    _login_attempts.clear()


@pytest.fixture(name="client")
def client_fixture(monkeypatch):
    """In-memory SQLite engine; overrides the FastAPI session dep AND the
    module-level `db.engine` + `scripts.seed_demo.engine` so the demo seeder
    deterministically targets the test DB regardless of import order."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(_db_module, "engine", engine)
    import scripts.seed_demo as _seed_mod
    monkeypatch.setattr(_seed_mod, "engine", engine)
    app.state.engine = engine
    app.dependency_overrides[get_session] = _override

    test_client = TestClient(app)
    yield test_client

    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


@pytest.fixture
def admin_headers(client):
    """Sign up a new tenant (first user is 'owner', which outranks 'admin')
    and return Authorization headers for it.

    Cookies are cleared after obtaining the token so that tests which
    subsequently call endpoints *without* the returned headers still hit
    the JWT/auth dependency (returning 401) rather than the CSRF check
    (which would see the lingering eb_access cookie and return 403)."""
    r = client.post("/api/auth/signup", json={
        "email": "owner@acme.test", "password": "pw12345678",
        "full_name": "Owner", "company_name": "Acme",
    })
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login", data={
        "username": "owner@acme.test", "password": "pw12345678",
    }).json()["access_token"]
    # Clear the cookies the login set so they don't bleed into the test body.
    # Tests that want cookie-auth can set them explicitly; Bearer-header tests
    # use the returned dict.
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}
