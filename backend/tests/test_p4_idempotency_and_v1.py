"""P4 tests: Idempotency-Key replay + /api/v1 versioned aliases."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from db import get_session
from main import app
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

    # Tell the IdempotencyMiddleware about our test engine
    app.state.engine = engine
    app.dependency_overrides[get_session] = _override
    _login_attempts.clear()
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
            "email": "p4@p4.test",
            "password": "password123",
            "full_name": "U",
            "company_name": "P4 Co",
        },
    )
    r = client.post(
        "/api/auth/login", data={"username": "p4@p4.test", "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_idempotent_post_returns_cached_response(client: TestClient):
    auth = _auth(client)
    headers = {**auth, "Idempotency-Key": "create-customer-once"}

    r1 = client.post(
        "/api/customers", headers=headers, json={"name": "Alice"}
    )
    assert r1.status_code == 201
    body1 = r1.json()
    assert "id" in body1

    # Same key → same body, no second row created
    r2 = client.post(
        "/api/customers", headers=headers, json={"name": "Alice"}
    )
    assert r2.status_code == 201
    body2 = r2.json()
    assert body1["id"] == body2["id"]
    assert r2.headers.get("idempotency-replay") == "true"

    # Verify only one customer exists
    listing = client.get("/api/customers", headers=auth).json()
    assert listing["total"] == 1


def test_idempotency_without_key_does_not_dedupe(client: TestClient):
    auth = _auth(client)
    r1 = client.post(
        "/api/customers", headers=auth, json={"name": "C1"}
    )
    r2 = client.post(
        "/api/customers", headers=auth, json={"name": "C2"}
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


def test_v1_alias_works_alongside_legacy_path(client: TestClient):
    auth = _auth(client)
    # Legacy
    r1 = client.get("/api/customers", headers=auth)
    assert r1.status_code == 200
    # Versioned alias
    r2 = client.get("/api/v1/customers", headers=auth)
    assert r2.status_code == 200
    assert r1.json() == r2.json()


def test_v1_alias_works_for_auth_endpoints(client: TestClient):
    # Signup via /api/v1
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "v1@v1.test",
            "password": "password123",
            "full_name": "V1 User",
            "company_name": "V1 Co",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
