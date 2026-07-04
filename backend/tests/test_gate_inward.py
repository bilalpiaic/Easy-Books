"""#137 Phase 2 — Gate Inward chain: GI → billing gate → reports."""
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


def test_gate_models_and_permission_registered(client: TestClient):
    from models import GateInward, GateInwardLine  # importable = tables exist
    from services.permissions import PERMISSION_RESOURCES
    assert "purchase.gate" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["purchase.gate"]["category"] == "Purchasing"
