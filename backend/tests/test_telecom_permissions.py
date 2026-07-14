"""telecom.py permissions split: all 54 endpoints shared a single router-level
perm_dep("telecom.tracker") check at the default "view" level. That meant (a)
POST/mutating endpoints only required view access, not edit, and (b) the other
8 registered telecom.* resources (rso/sim/fca/mobile_money/postpaid/
commissions/franchise/devices) were dead -- denying any of them had zero
effect since the router-level "telecom.tracker" check was the only one that
ever ran. Fixed by replacing the router-level dependency with per-route
dependencies=[perm_dep(resource, level)] on all 54 endpoints. Verified here
with one representative GET (view-level denial) per category, plus one
GET+POST pair on telecom.tracker proving the level split now actually holds."""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> dict:
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Owner", "company_name": "Co", "business_model": "telecom_franchise",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _accountant(client: TestClient, owner_auth: dict, email: str) -> dict:
    r = client.post("/api/users", headers=owner_auth, json={
        "email": email, "password": "password123",
        "full_name": "Accountant", "role": "accountant",
    })
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user_id(client: TestClient, owner_auth: dict, email: str) -> int:
    users = client.get("/api/users", headers=owner_auth).json()["items"]
    return next(u["id"] for u in users if u["email"] == email)


def _set_level(client: TestClient, owner_auth: dict, user_id: int, resource_key: str, level: str) -> None:
    client.patch("/api/settings", headers=owner_auth, json={"user_rights_enabled": "true"})
    r = client.put(f"/api/permissions/users/{user_id}", headers=owner_auth,
                   json=[{"resource_key": resource_key, "access_level": level}])
    assert r.status_code == 200, r.text


# (resource_key, GET url) — one representative read endpoint per telecom
# sub-resource category.
CATEGORY_ENDPOINTS = [
    ("telecom.tracker", "/api/telecom/operators"),
    ("telecom.rso", "/api/telecom/rso/agents"),
    ("telecom.sim", "/api/telecom/sim/batches"),
    ("telecom.fca", "/api/telecom/fca/events"),
    ("telecom.mobile_money", "/api/telecom/mm/accounts"),
    ("telecom.postpaid", "/api/telecom/postpaid/connections"),
    ("telecom.commissions", "/api/telecom/commissions/statements"),
    ("telecom.franchise", "/api/telecom/franchise/agreements"),
    ("telecom.devices", "/api/telecom/imei"),
]


def test_each_telecom_category_independently_gated(client: TestClient):
    owner = _signup(client, "telperm1@t.com")
    email = "telacct1@t.com"
    acct_auth = _accountant(client, owner, email)
    uid = _user_id(client, owner, email)

    for resource_key, url in CATEGORY_ENDPOINTS:
        # Baseline: accountant role default is 'edit' -- reachable.
        r = client.get(url, headers=acct_auth)
        assert r.status_code == 200, f"{resource_key} ({url}) unexpectedly blocked: {r.text}"

        _set_level(client, owner, uid, resource_key, "none")
        r = client.get(url, headers=acct_auth)
        assert r.status_code == 403, f"{resource_key} ({url}) still reachable after access_level=none"

        # Denying this one resource must not affect the others -- proves the
        # split isn't still funneling through the old single tracker gate.
        for other_key, other_url in CATEGORY_ENDPOINTS:
            if other_key == resource_key:
                continue
            r = client.get(other_url, headers=acct_auth)
            assert r.status_code == 200, (
                f"denying {resource_key} unexpectedly blocked unrelated {other_key} ({other_url})"
            )

        _set_level(client, owner, uid, resource_key, "default")


def test_telecom_tracker_view_level_blocks_post_not_get(client: TestClient):
    """Previously the router-level gate ran at 'view' for every method, so a
    view-only user could still POST. Now POST requires 'edit' explicitly."""
    owner = _signup(client, "telperm2@t.com")
    email = "telacct2@t.com"
    acct_auth = _accountant(client, owner, email)
    uid = _user_id(client, owner, email)

    _set_level(client, owner, uid, "telecom.tracker", "view")

    r = client.get("/api/telecom/operators", headers=acct_auth)
    assert r.status_code == 200

    r = client.post("/api/telecom/operators", headers=acct_auth,
                     json={"name": "Op1", "operator_code": "OP1"})
    assert r.status_code == 403


def test_module_off_leaves_telecom_unrestricted(client: TestClient):
    owner = _signup(client, "telperm3@t.com")
    for _, url in CATEGORY_ENDPOINTS:
        r = client.get(url, headers=owner)
        assert r.status_code == 200, f"{url} blocked with user_rights_enabled off"
