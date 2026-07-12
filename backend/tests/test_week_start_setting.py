"""#141 — week_start_day setting round-trips through the settings KV."""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> dict:
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co", "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_week_start_day_roundtrip(client: TestClient):
    auth = _signup(client, "ws1@t.com")
    r = client.patch("/api/settings", headers=auth, json={"week_start_day": "Sunday"})
    assert r.status_code == 200
    assert client.get("/api/settings", headers=auth).json().get("week_start_day") == "Sunday"
