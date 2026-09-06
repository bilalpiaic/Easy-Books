"""GET /api/auth/bootstrap — one payload for the SPA shell."""


def test_bootstrap_requires_auth(client):
    r = client.get("/api/auth/bootstrap")
    assert r.status_code == 401


def test_bootstrap_matches_existing_endpoints(client, admin_headers):
    r = client.get("/api/auth/bootstrap", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data) >= {"me", "settings", "modules", "permissions"}

    me = client.get("/api/auth/me", headers=admin_headers).json()
    assert data["me"]["id"] == me["id"]
    assert data["me"]["email"] == me["email"]
    assert data["me"]["tenant"]["business_model"] == me["tenant"]["business_model"]

    settings = client.get("/api/settings", headers=admin_headers).json()
    assert data["settings"]["business_model"] == settings["business_model"]
    assert "company_name" in data["settings"]

    modules = client.get("/api/modules", headers=admin_headers).json()
    assert isinstance(data["modules"], list) and len(data["modules"]) == len(modules)
    assert any(m["id"] == "base" and m["installed"] for m in data["modules"])

    perms = client.get("/api/permissions/me", headers=admin_headers).json()
    assert data["permissions"]["module_enabled"] == perms["module_enabled"]
    assert data["permissions"]["my_data_only"] == perms["my_data_only"]
    assert data["permissions"]["permissions"] == perms["permissions"]
