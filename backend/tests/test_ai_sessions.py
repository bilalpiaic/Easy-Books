"""#117 completion — chat sessions: CRUD, per-user privacy, cascade."""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> dict:
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co", "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_ai(client: TestClient, auth: dict) -> None:
    r = client.post("/api/modules/ai_assistant/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def test_session_crud_lifecycle(client: TestClient):
    auth = _signup(client, "ai1@t.com")
    _install_ai(client, auth)

    r = client.post("/api/ai/sessions", headers=auth, json={})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["title"] == "New chat"

    rows = client.get("/api/ai/sessions", headers=auth).json()
    assert [s["id"] for s in rows] == [sid]

    r = client.patch(f"/api/ai/sessions/{sid}", headers=auth, json={"title": "Renamed"})
    assert r.status_code == 200
    assert client.get("/api/ai/sessions", headers=auth).json()[0]["title"] == "Renamed"

    assert client.get(f"/api/ai/sessions/{sid}/messages", headers=auth).json() == []

    r = client.delete(f"/api/ai/sessions/{sid}", headers=auth)
    assert r.status_code == 200
    assert client.get("/api/ai/sessions", headers=auth).json() == []


def test_sessions_are_private_per_user_even_same_tenant(client: TestClient):
    auth_owner = _signup(client, "ai2@t.com")
    _install_ai(client, auth_owner)
    sid = client.post("/api/ai/sessions", headers=auth_owner, json={}).json()["id"]

    # second user in the SAME tenant
    client.post("/api/users", headers=auth_owner, json={
        "email": "ai2b@t.com", "password": "password123",
        "full_name": "Colleague", "role": "admin",
    })
    r = client.post("/api/auth/login", data={"username": "ai2b@t.com", "password": "password123"})
    auth_colleague = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get("/api/ai/sessions", headers=auth_colleague).json() == []
    assert client.get(f"/api/ai/sessions/{sid}/messages", headers=auth_colleague).status_code == 404
    assert client.patch(f"/api/ai/sessions/{sid}", headers=auth_colleague, json={"title": "x"}).status_code == 404
    assert client.delete(f"/api/ai/sessions/{sid}", headers=auth_colleague).status_code == 404


def test_sessions_gated_by_module(client: TestClient):
    auth = _signup(client, "ai3@t.com")  # ai_assistant NOT installed
    assert client.get("/api/ai/sessions", headers=auth).status_code == 403
    assert client.post("/api/ai/sessions", headers=auth, json={}).status_code == 403
