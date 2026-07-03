"""#137 Phase 1 — Demand → Quotation → Comparative → PO chain."""
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


def test_purchase_store_module_registered(client: TestClient):
    auth = _signup(client, "mod@t.com")
    mods = client.get("/api/modules", headers=auth).json()
    ids = {m["id"] for m in mods}
    assert "purchase_store" in ids
    entry = next(m for m in mods if m["id"] == "purchase_store")
    assert entry["installed"] is True  # manufacturing pre-installs it


def test_permission_resources_registered(client: TestClient):
    from services.permissions import PERMISSION_RESOURCES
    assert "purchase.demand" in PERMISSION_RESOURCES
    assert "purchase.comparative" in PERMISSION_RESOURCES
