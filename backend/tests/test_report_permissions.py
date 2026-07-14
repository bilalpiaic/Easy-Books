"""#141 leftover: 12 report.* + customer_ledger/vendor_ledger PERMISSION_RESOURCES
entries were registered (shown in the admin matrix, toggleable) but never
actually checked by any endpoint — reports.py imported perm_dep and never
called it. Any authenticated user could view every financial report
regardless of role/permission settings. Fixed by wiring dependencies=[perm_dep(...)]
onto each mapped endpoint; verified here with the module ON + an explicit
'none' override, following the pattern in test_user_rights.py."""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> dict:
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Owner", "company_name": "Co",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _accountant(client: TestClient, owner_auth: dict, email: str) -> dict:
    """Create an accountant sub-user under owner_auth's tenant; return their headers."""
    r = client.post("/api/users", headers=owner_auth, json={
        "email": email, "password": "password123",
        "full_name": "Accountant", "role": "accountant",
    })
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _deny(client: TestClient, owner_auth: dict, user_id: int, resource_key: str) -> None:
    client.patch("/api/settings", headers=owner_auth, json={"user_rights_enabled": "true"})
    r = client.put(f"/api/permissions/users/{user_id}", headers=owner_auth,
                   json=[{"resource_key": resource_key, "access_level": "none"}])
    assert r.status_code == 200, r.text


def _user_id(client: TestClient, owner_auth: dict, email: str) -> int:
    users = client.get("/api/users", headers=owner_auth).json()["items"]
    return next(u["id"] for u in users if u["email"] == email)


# (resource_key, method, url) — every endpoint mapped to a previously-dead
# PERMISSION_RESOURCES entry. Query params kept minimal; these reports all
# tolerate an empty/undated request with a 200, which is all this needs.
REPORT_ENDPOINTS = [
    ("report.trial_balance", "GET", "/api/reports/trial-balance"),
    ("report.income_statement", "GET", "/api/reports/income-statement"),
    ("report.balance_sheet", "GET", "/api/reports/balance-sheet"),
    ("report.cash_flow", "GET", "/api/reports/cash-flow"),
    ("report.general_ledger", "GET", "/api/reports/journal"),
    ("report.customer_performance", "GET", "/api/reports/customer-performance"),
    ("report.inventory_performance", "GET", "/api/reports/inventory-performance"),
    ("report.tax", "GET", "/api/reports/tax-summary"),
    ("report.budget_vs_actual", "GET", "/api/reports/budget-vs-actual?year=2026"),
    ("report.product_ledger", "GET", "/api/reports/product-ledger?product_id={product_id}"),
    ("report.ar_aging", "GET", "/api/invoices/aging"),
    ("report.ap_aging", "GET", "/api/bills/aging"),
]


def test_all_report_resources_now_enforce_none(client: TestClient):
    owner = _signup(client, "repperm1@t.com")
    email = "repacct1@t.com"
    client.post("/api/users", headers=owner, json={
        "email": email, "password": "password123",
        "full_name": "Accountant", "role": "accountant",
    })
    acct_auth = {"Authorization": f"Bearer {client.post('/api/auth/login', data={'username': email, 'password': 'password123'}).json()['access_token']}"}
    uid = _user_id(client, owner, email)

    product = client.post("/api/products", headers=owner,
                          json={"name": "P1", "product_type": "stock"}).json()

    for resource_key, method, raw_url in REPORT_ENDPOINTS:
        url = raw_url.format(product_id=product["id"])
        # Baseline: accountant's role default is 'edit' — endpoint must be reachable.
        r = client.request(method, url, headers=acct_auth)
        assert r.status_code == 200, f"{resource_key} ({url}) unexpectedly blocked before any override: {r.text}"

        _deny(client, owner, uid, resource_key)
        r = client.request(method, url, headers=acct_auth)
        assert r.status_code == 403, f"{resource_key} ({url}) still reachable after access_level=none"

        # Clean up: revert to default so the next resource in the loop starts fresh.
        client.put(f"/api/permissions/users/{uid}", headers=owner,
                   json=[{"resource_key": resource_key, "access_level": "default"}])


def test_report_ledger_subledger_gated_by_general_ledger(client: TestClient):
    owner = _signup(client, "repperm2@t.com")
    email = "repacct2@t.com"
    client.post("/api/users", headers=owner, json={
        "email": email, "password": "password123",
        "full_name": "Accountant", "role": "accountant",
    })
    acct_auth = {"Authorization": f"Bearer {client.post('/api/auth/login', data={'username': email, 'password': 'password123'}).json()['access_token']}"}
    uid = _user_id(client, owner, email)

    r = client.get("/api/reports/ledger/subledger?control=ar", headers=acct_auth)
    assert r.status_code == 200

    _deny(client, owner, uid, "report.general_ledger")
    r = client.get("/api/reports/ledger", headers=acct_auth)
    assert r.status_code == 403
    r = client.get("/api/reports/ledger/subledger?control=ar", headers=acct_auth)
    assert r.status_code == 403


def test_module_off_leaves_reports_unrestricted(client: TestClient):
    """user_rights_enabled defaults to false — no behavior change for tenants
    that haven't opted into the granular permission system."""
    owner = _signup(client, "repperm3@t.com")
    r = client.get("/api/reports/trial-balance", headers=owner)
    assert r.status_code == 200
    r = client.get("/api/invoices/aging", headers=owner)
    assert r.status_code == 200


def test_customer_and_vendor_ledger_resources_enforce_none(client: TestClient):
    owner = _signup(client, "repperm4@t.com")
    email = "repacct4@t.com"
    client.post("/api/users", headers=owner, json={
        "email": email, "password": "password123",
        "full_name": "Accountant", "role": "accountant",
    })
    acct_auth = {"Authorization": f"Bearer {client.post('/api/auth/login', data={'username': email, 'password': 'password123'}).json()['access_token']}"}
    uid = _user_id(client, owner, email)

    cust = client.post("/api/customers", headers=owner, json={"name": "C1"}).json()
    vend = client.post("/api/vendors", headers=owner, json={"name": "V1"}).json()

    cust_stmt = f"/api/customers/{cust['id']}/statement?from_date=2026-01-01&to_date=2026-12-31"
    vend_stmt = f"/api/vendors/{vend['id']}/statement?from_date=2026-01-01&to_date=2026-12-31"

    # Baseline: still gated by the coarse customers/vendors permission,
    # so both are reachable while that's at its role default.
    assert client.get(cust_stmt, headers=acct_auth).status_code == 200
    assert client.get(vend_stmt, headers=acct_auth).status_code == 200

    _deny(client, owner, uid, "customer_ledger")
    assert client.get(cust_stmt, headers=acct_auth).status_code == 403
    # The customer LIST endpoint (still gated by the coarser 'customers'
    # resource) must remain unaffected by the ledger-specific denial.
    assert client.get("/api/customers", headers=acct_auth).status_code == 200

    _deny(client, owner, uid, "vendor_ledger")
    assert client.get(vend_stmt, headers=acct_auth).status_code == 403
    assert client.get("/api/vendors", headers=acct_auth).status_code == 200
