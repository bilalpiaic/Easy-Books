"""Shared pytest fixtures."""
import pytest

import db as _db_module
from db import get_session
from main import app
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture(autouse=True)
def _disable_module_plan_enforcement(monkeypatch):
    """Existing tests POST /api/modules/*/install on free signup tenants.
    Production default is ENFORCE_MODULE_PLANS=true; entitlement tests turn
    it back on themselves."""
    monkeypatch.setenv("ENFORCE_MODULE_PLANS", "false")


@pytest.fixture(autouse=True)
def _clear_login_throttle():
    """Login throttle is process-global; reset before every test so tests
    don't poison each other's IP counters."""
    from routers.auth import _login_attempts
    _login_attempts.clear()
    yield
    _login_attempts.clear()


@pytest.fixture(autouse=True)
def _clear_ai_rate_limit():
    """AI chat rate limiter is process-global, keyed by (tenant_id, user_id).
    Each test gets a fresh in-memory DB where those ids restart at 1, so
    without clearing, buckets from earlier tests leak into later ones."""
    from routers.ai_chat import _RATE
    _RATE.clear()
    yield
    _RATE.clear()


@pytest.fixture(autouse=True)
def _clear_global_rate_limit():
    """RateLimitMiddleware's buckets are process-global too. The anon bucket
    is keyed by client IP, which TestClient keeps constant across tests
    (unlike tenant/user ids, which restart at 1 in each test's fresh
    in-memory DB but don't help here) — without clearing, unauthenticated
    request counts leak across every test in the whole suite."""
    from services.rate_limit import _AUTH_BUCKETS, _ANON_BUCKETS
    _AUTH_BUCKETS.clear()
    _ANON_BUCKETS.clear()
    yield
    _AUTH_BUCKETS.clear()
    _ANON_BUCKETS.clear()


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
