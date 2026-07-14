"""User Rights Module — tests covering permission resolution and enforcement."""
import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def accountant_user(client, admin_headers):
    """Create an accountant-role user under the same tenant as admin."""
    r = client.post(
        "/api/users",
        headers=admin_headers,
        json={"email": "acct@acme.test", "password": "pw12345678", "role": "accountant", "full_name": "Acct User"},
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def accountant_headers(client, accountant_user):
    """JWT headers for the accountant user."""
    tok = client.post(
        "/api/auth/login",
        data={"username": "acct@acme.test", "password": "pw12345678"},
    ).json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


# ── Module toggle ──────────────────────────────────────────────────────────────

def test_module_off_by_default_no_restriction(client, accountant_headers):
    """Default state: user_rights_enabled=false → no 403 on any endpoint."""
    r = client.get("/api/invoices", headers=accountant_headers)
    assert r.status_code == 200


def test_module_toggle_persists(client, admin_headers):
    """user_rights_enabled round-trips through the settings endpoint."""
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    r = client.get("/api/settings", headers=admin_headers)
    assert r.json()["user_rights_enabled"] == "true"

    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "false"})
    r = client.get("/api/settings", headers=admin_headers)
    assert r.json()["user_rights_enabled"] == "false"


def test_module_on_owner_always_has_edit(client, admin_headers):
    """Even with module on, the owner role always has edit (no override needed)."""
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    r = client.get("/api/invoices", headers=admin_headers)
    assert r.status_code == 200


# ── Permissions endpoint ───────────────────────────────────────────────────────

def test_my_permissions_returns_full_map(client, admin_headers):
    """GET /api/permissions/me returns module_enabled flag + full resource map."""
    r = client.get("/api/permissions/me", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "permissions" in data
    assert "module_enabled" in data
    assert "my_data_only" in data
    # Owner default: edit on all resources
    assert data["permissions"].get("invoices") == "edit"
    assert data["permissions"].get("bills") == "edit"
    assert data["permissions"].get("telecom.tracker") == "edit"


def test_my_permissions_accountant_default(client, accountant_headers):
    """Accountant role default is 'edit' when no override exists."""
    r = client.get("/api/permissions/me", headers=accountant_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["permissions"].get("invoices") == "edit"


def test_resources_endpoint_returns_registry(client, admin_headers):
    """GET /api/permissions/resources returns all registered resource keys."""
    r = client.get("/api/permissions/resources", headers=admin_headers)
    assert r.status_code == 200
    keys = {item["key"] for item in r.json()}
    assert "invoices" in keys
    assert "telecom.tracker" in keys
    assert "report.trial_balance" in keys


# ── Permission overrides ───────────────────────────────────────────────────────

def test_explicit_none_blocks_view(client, admin_headers, accountant_headers, accountant_user):
    """Explicit 'none' override on invoices blocks GET /api/invoices for that user."""
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    client.put(
        f"/api/permissions/users/{accountant_user['id']}",
        headers=admin_headers,
        json=[{"resource_key": "invoices", "access_level": "none"}],
    )
    r = client.get("/api/invoices", headers=accountant_headers)
    assert r.status_code == 403


def test_explicit_view_allows_get_blocks_post(client, admin_headers, accountant_headers, accountant_user):
    """Explicit 'view' override allows GET but blocks POST (edit operation)."""
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    client.put(
        f"/api/permissions/users/{accountant_user['id']}",
        headers=admin_headers,
        json=[{"resource_key": "invoices", "access_level": "view"}],
    )
    # GET should pass (view access)
    r = client.get("/api/invoices", headers=accountant_headers)
    assert r.status_code == 200
    # POST should be blocked (needs edit)
    r = client.post("/api/invoices", headers=accountant_headers, json={})
    assert r.status_code == 403


def test_default_access_level_removes_override(client, admin_headers, accountant_user):
    """access_level='default' deletes the override and reverts to role default."""
    # Set override
    client.put(
        f"/api/permissions/users/{accountant_user['id']}",
        headers=admin_headers,
        json=[{"resource_key": "invoices", "access_level": "none"}],
    )
    # Remove it
    client.put(
        f"/api/permissions/users/{accountant_user['id']}",
        headers=admin_headers,
        json=[{"resource_key": "invoices", "access_level": "default"}],
    )
    # Check reverted to role default (edit for accountant)
    r = client.get(f"/api/permissions/users/{accountant_user['id']}", headers=admin_headers)
    assert r.json()["permissions"]["invoices"] == "edit"


def test_invalid_access_level_rejected(client, admin_headers, accountant_user):
    """Invalid access_level values are rejected with 400."""
    r = client.put(
        f"/api/permissions/users/{accountant_user['id']}",
        headers=admin_headers,
        json=[{"resource_key": "invoices", "access_level": "superuser"}],
    )
    assert r.status_code == 400


def test_unknown_resource_key_rejected(client, admin_headers, accountant_user):
    """Unknown resource keys are rejected with 400."""
    r = client.put(
        f"/api/permissions/users/{accountant_user['id']}",
        headers=admin_headers,
        json=[{"resource_key": "nonexistent_module", "access_level": "edit"}],
    )
    assert r.status_code == 400


# ── My Data Only ──────────────────────────────────────────────────────────────

def test_my_data_only_toggle(client, admin_headers, accountant_user):
    """PATCH /api/permissions/users/:id/my-data-only persists the flag."""
    client.patch(
        f"/api/permissions/users/{accountant_user['id']}/my-data-only",
        headers=admin_headers,
        params={"enabled": "true"},
    )
    r = client.get(f"/api/permissions/users/{accountant_user['id']}", headers=admin_headers)
    assert r.json()["my_data_only"] is True


def test_team_resource_removed_from_registry(client, admin_headers, accountant_user):
    """'team' was registered in PERMISSION_RESOURCES (shown as a togglable row
    in the admin matrix) but users.py is hardcoded AdminUserDep on every
    endpoint — the resource had zero effect and was actively misleading.
    Removed; it must now behave exactly like any other unknown key."""
    r = client.get("/api/permissions/resources", headers=admin_headers)
    keys = {item["key"] for item in r.json()}
    assert "team" not in keys

    r = client.put(
        f"/api/permissions/users/{accountant_user['id']}",
        headers=admin_headers,
        json=[{"resource_key": "team", "access_level": "edit"}],
    )
    assert r.status_code == 400

    # Team management stays admin-only regardless of any permission grant —
    # unaffected by the removal, since AdminUserDep was always the real gate.
    client.patch("/api/settings", headers=admin_headers, json={"user_rights_enabled": "true"})
    accountant_headers = {
        "Authorization": f"Bearer {client.post('/api/auth/login', data={'username': accountant_user['email'], 'password': 'pw12345678'}).json()['access_token']}"
    }
    assert client.get("/api/users", headers=accountant_headers).status_code == 403
