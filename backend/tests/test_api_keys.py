"""Part 2/4 of #113 — ApiKey model, CRUD endpoints, and the eb_live_
branch in get_current_user()."""
from fastapi.testclient import TestClient


def _signup(client, email, company="Co"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": company, "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    client.cookies.clear()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _invite_member(client, owner_auth, email, role):
    """Materialise a second user on the owner's tenant via the invite flow."""
    r = client.post("/api/users/invites", headers=owner_auth, json={"email": email, "role": role})
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    r = client.post("/api/auth/accept-invite", json={
        "token": token, "password": "password123", "full_name": "Member",
    })
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {access}"}


def test_create_returns_raw_key_exactly_once(client: TestClient):
    auth = _signup(client, "keys1@t.com")

    r = client.post("/api/auth/keys", headers=auth, json={"name": "Zapier integration"})
    assert r.status_code == 201, r.text
    created = r.json()
    raw = created["key"]
    assert raw.startswith("eb_live_")
    assert created["key_hint"] == raw[-4:]
    assert created["name"] == "Zapier integration"

    # The list never re-exposes the raw key (or any hash).
    r = client.get("/api/auth/keys", headers=auth)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert "key" not in rows[0]
    assert "key_hash" not in rows[0]
    assert rows[0]["key_hint"] == raw[-4:]


def test_raw_key_authenticates_identically_to_a_jwt(client: TestClient):
    auth = _signup(client, "keys2@t.com")
    raw = client.post("/api/auth/keys", headers=auth, json={"name": "bot"}).json()["key"]

    key_auth = {"Authorization": f"Bearer {raw}"}
    r = client.get("/api/customers", headers=key_auth)
    assert r.status_code == 200
    # Inherits the owning user's identity, not some separate principal.
    r = client.get("/api/auth/me", headers=key_auth)
    assert r.status_code == 200
    assert r.json()["email"] == "keys2@t.com"
    # last_used gets stamped
    row = client.get("/api/auth/keys", headers=auth).json()[0]
    assert row["last_used"] is not None


def test_revoked_key_is_rejected_immediately(client: TestClient):
    auth = _signup(client, "keys3@t.com")
    created = client.post("/api/auth/keys", headers=auth, json={"name": "bot"}).json()
    key_auth = {"Authorization": f"Bearer {created['key']}"}
    assert client.get("/api/customers", headers=key_auth).status_code == 200

    r = client.delete(f"/api/auth/keys/{created['id']}", headers=auth)
    assert r.status_code == 200
    assert client.get("/api/customers", headers=key_auth).status_code == 401
    # Soft revoke: still listed, flagged inactive.
    row = client.get("/api/auth/keys", headers=auth).json()[0]
    assert row["is_active"] is False


def test_garbage_key_with_prefix_is_401_not_500(client: TestClient):
    _signup(client, "keys4@t.com")
    r = client.get("/api/customers", headers={"Authorization": "Bearer eb_live_not-a-real-key"})
    assert r.status_code == 401


def test_non_admin_roles_cannot_manage_keys(client: TestClient):
    owner_auth = _signup(client, "keys5@t.com")
    acct_auth = _invite_member(client, owner_auth, "keys5b@t.com", "accountant")

    assert client.post("/api/auth/keys", headers=acct_auth, json={"name": "x"}).status_code == 403
    assert client.get("/api/auth/keys", headers=acct_auth).status_code == 403
    created = client.post("/api/auth/keys", headers=owner_auth, json={"name": "x"}).json()
    assert client.delete(f"/api/auth/keys/{created['id']}", headers=acct_auth).status_code == 403


def test_keys_are_tenant_scoped(client: TestClient):
    auth_a = _signup(client, "keys6a@t.com", company="A Co")
    auth_b = _signup(client, "keys6b@t.com", company="B Co")
    created = client.post("/api/auth/keys", headers=auth_a, json={"name": "a-key"}).json()

    # Tenant B sees nothing and cannot revoke A's key.
    assert client.get("/api/auth/keys", headers=auth_b).json() == []
    assert client.delete(f"/api/auth/keys/{created['id']}", headers=auth_b).status_code == 404
    # A's key still works.
    assert client.get(
        "/api/customers", headers={"Authorization": f"Bearer {created['key']}"}
    ).status_code == 200
