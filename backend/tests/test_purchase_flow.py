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


def _make_demand(client, auth, lines=None):
    r = client.post(
        "/api/purchase-demands",
        headers=auth,
        json={
            "demand_date": "2026-07-04",
            "purpose": "Line restock",
            "lines": lines or [{"description": "Steel rods 12mm", "qty": 100, "unit": "kg"}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _second_admin(client, auth, email="approver@t.com"):
    """Invite a second admin in the same tenant and return their auth header."""
    client.post(
        "/api/users",
        headers=auth,
        json={"email": email, "password": "password123", "full_name": "Approver", "role": "admin"},
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_demand_lifecycle_and_self_approval_block(client: TestClient):
    auth = _signup(client, "pd1@t.com")
    d = _make_demand(client, auth)
    assert d["number"].startswith("PD-") and d["status"] == "draft"
    assert d["lines"][0]["description"] == "Steel rods 12mm"

    # Self-approval must be rejected
    r = client.patch(f"/api/purchase-demands/{d['id']}/approve", headers=auth)
    assert r.status_code == 400
    assert "creator" in r.json()["detail"].lower()

    # A different admin approves
    auth2 = _second_admin(client, auth)
    r = client.patch(f"/api/purchase-demands/{d['id']}/approve", headers=auth2)
    assert r.status_code == 200
    got = client.get(f"/api/purchase-demands/{d['id']}", headers=auth).json()
    assert got["status"] == "approved" and got["approved_by_id"] is not None

    # Editing an approved demand is blocked
    r = client.put(
        f"/api/purchase-demands/{d['id']}", headers=auth,
        json={"demand_date": "2026-07-05", "lines": [{"description": "x", "qty": 1}]},
    )
    assert r.status_code == 400


def test_demand_tenant_isolation(client: TestClient):
    auth_a = _signup(client, "pd2a@t.com")
    auth_b = _signup(client, "pd2b@t.com")
    d = _make_demand(client, auth_a)
    assert client.get(f"/api/purchase-demands/{d['id']}", headers=auth_b).status_code == 404
