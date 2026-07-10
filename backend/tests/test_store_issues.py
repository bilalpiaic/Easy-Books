"""#137 Phase 3 — Store Issue: departmental/cost-center consumption with
immediate GL posting + stock relief (no draft/approve gate)."""
from decimal import Decimal

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str, model: str = "manufacturing") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": model,
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_store_issue_models_and_permission_registered(client: TestClient):
    from models import StoreIssue, StoreIssueLine  # importable = tables exist
    from services.permissions import PERMISSION_RESOURCES
    assert "store.issue" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["store.issue"]["category"] == "Store"
