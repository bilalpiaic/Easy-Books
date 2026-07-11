"""#137 Phase 3 — Store Issue: departmental/cost-center consumption with
immediate GL posting + stock relief (no draft/approve gate)."""
from decimal import Decimal

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


def test_store_issue_models_and_permission_registered(client: TestClient):
    from models import StoreIssue, StoreIssueLine  # importable = tables exist
    from services.permissions import PERMISSION_RESOURCES
    assert "store.issue" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["store.issue"]["category"] == "Store"


def _get_tenant_id(client, auth) -> int:
    return client.get("/api/auth/me", headers=auth).json()["tenant"]["id"]


def _stock_product(client, auth, qty=100, avg_cost=10):
    """Direct insert — the product-creation API has no field for pre-setting
    stock_qty/avg_cost; those only move via consume_stock/record_purchase."""
    from sqlmodel import Session
    from models import Product
    import db as _db
    tenant_id = _get_tenant_id(client, auth)
    with Session(_db.engine) as s:
        p = Product(tenant_id=tenant_id, name="Consumable Widget", product_type="stock",
                    stock_qty=Decimal(str(qty)), avg_cost=Decimal(str(avg_cost)))
        s.add(p); s.commit(); s.refresh(p)
        return p.id


def _own_location(client, auth) -> int:
    """The seeded default 'own' StockLocation ("MAIN"/"Main Store"), created
    by db.py's seed_data for every tenant regardless of business model.
    GET /api/stock-locations returns {"total":.., "items":[...]}, not a
    bare list — routers/stock_locations.py:36-45."""
    rows = client.get("/api/stock-locations", headers=auth).json()["items"]
    own = next(l for l in rows if l["type"] == "own")
    return own["id"]


def _expense_account(client, auth, code="5100", name="Office Supplies Expense") -> int:
    """GET /api/accounts returns {"total":.., "items":[...]}, not a bare
    list — routers/accounts.py:289-349."""
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    existing = next((a for a in accounts if a["code"] == code), None)
    if existing:
        return existing["id"]
    r = client.post("/api/accounts", headers=auth, json={
        "code": code, "name": name, "type": "Expense",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_store_issue_create_posts_gl_and_relieves_stock(client: TestClient):
    auth = _signup(client, "si1@t.com")
    pid = _stock_product(client, auth, qty=100, avg_cost=10)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": pid, "qty": 5}],
    })
    assert r.status_code == 201, r.text
    si = r.json()
    assert si["number"].startswith("SI-")

    prod = client.get(f"/api/products/{pid}", headers=auth).json()
    assert Decimal(str(prod["stock_qty"])) == Decimal("95")

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    def _find(node, code):
        if node.get("code") == code:
            return node
        for child in node.get("children") or []:
            found = _find(child, code)
            if found is not None:
                return found
        return None
    def bal(code):
        for node in tb["tree"]:
            found = _find(node, code)
            if found is not None:
                return found
        return None
    expense = bal("5100")
    assert expense is not None and Decimal(str(expense["debit"])) == Decimal("50")  # 5 * avg_cost(10)


def test_store_issue_with_analytic_account(client: TestClient):
    auth = _signup(client, "si2@t.com")
    pid = _stock_product(client, auth)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    aa = client.post("/api/analytic-accounts", headers=auth, json={
        "code": "CC-100", "name": "Maintenance Dept", "type": "cost_center",
    })
    assert aa.status_code in (200, 201), aa.text
    aa_id = aa.json()["id"]

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "analytic_account_id": aa_id,
        "lines": [{"product_id": pid, "qty": 2}],
    })
    assert r.status_code == 201, r.text
    detail = client.get(f"/api/store-issues/{r.json()['id']}", headers=auth).json()
    assert detail["analytic_account_id"] == aa_id


def test_store_issue_requires_expense_type_debit_account(client: TestClient):
    auth = _signup(client, "si3@t.com")
    pid = _stock_product(client, auth)
    loc_id = _own_location(client, auth)
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    asset_acct = next(a for a in accounts if a["type"] == "Asset" and not a.get("is_group"))

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": asset_acct["id"],
        "lines": [{"product_id": pid, "qty": 1}],
    })
    assert r.status_code == 400
    assert "expense" in r.json()["detail"].lower()


def test_store_issue_rejects_non_stock_product(client: TestClient):
    """consume_stock silently no-ops (returns ZERO cost) for non-stock
    products, which would otherwise produce a misleading zero-cost Store
    Issue line — reject up front instead."""
    auth = _signup(client, "si-nonstock@t.com")
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    service = client.post("/api/products", headers=auth, json={
        "name": "Consulting Hour", "product_type": "service", "unit": "hr",
    }).json()

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": service["id"], "qty": 1}],
    })
    assert r.status_code == 400
    assert "not a stock item" in r.json()["detail"]


def test_store_issue_blocks_negative_stock_when_setting_enabled(client: TestClient):
    auth = _signup(client, "si4@t.com")
    pid = _stock_product(client, auth, qty=3, avg_cost=10)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    client.patch("/api/settings", headers=auth, json={"block_negative_stock": "true"})

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": pid, "qty": 10}],
    })
    assert r.status_code == 400
    prod = client.get(f"/api/products/{pid}", headers=auth).json()
    assert Decimal(str(prod["stock_qty"])) == Decimal("3")  # unchanged, no partial mutation


def test_store_issue_multi_line_sums_cost(client: TestClient):
    auth = _signup(client, "si5@t.com")
    pid1 = _stock_product(client, auth, qty=50, avg_cost=4)
    pid2 = _stock_product(client, auth, qty=50, avg_cost=6)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": pid1, "qty": 5}, {"product_id": pid2, "qty": 5}],
    })
    assert r.status_code == 201, r.text
    detail = client.get(f"/api/store-issues/{r.json()['id']}", headers=auth).json()
    line1 = next(l for l in detail["lines"] if l["product_id"] == pid1)
    line2 = next(l for l in detail["lines"] if l["product_id"] == pid2)
    assert Decimal(str(line1["unit_cost"])) == Decimal("4")
    assert Decimal(str(line2["unit_cost"])) == Decimal("6")


def test_store_issue_rejects_empty_lines_and_foreign_tenant_refs(client: TestClient):
    auth = _signup(client, "si6@t.com")
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "lines": [],
    })
    assert r.status_code == 400

    auth_b = _signup(client, "si6b@t.com")
    pid_b = _stock_product(client, auth_b)
    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "lines": [{"product_id": pid_b, "qty": 1}],
    })
    assert r.status_code == 404


def test_store_issue_permission_view_only_blocked_from_create(client: TestClient):
    auth = _signup(client, "si7@t.com")
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    client.patch("/api/settings", headers=auth, json={"user_rights_enabled": "true"})
    client.post("/api/users", headers=auth, json={
        "email": "siviewer@t.com", "password": "password123",
        "full_name": "Viewer", "role": "accountant",
    })
    users = client.get("/api/users", headers=auth).json()["items"]
    uid = next(u["id"] for u in users if u["email"] == "siviewer@t.com")
    client.put(f"/api/permissions/users/{uid}", headers=auth,
              json=[{"resource_key": "store.issue", "access_level": "view"}])
    r = client.post("/api/auth/login",
                    data={"username": "siviewer@t.com", "password": "password123"})
    viewer = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get("/api/store-issues", headers=viewer).status_code == 200
    r = client.post("/api/store-issues", headers=viewer, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "lines": [],
    })
    assert r.status_code == 403


def test_store_issue_multi_line_failure_rolls_back_first_line(client: TestClient):
    """Line 1 consumes stock in-session, line 2 fails block_negative —
    the whole request must 400 and line 1's stock must be untouched."""
    auth = _signup(client, "si8@t.com")
    pid_ok = _stock_product(client, auth, qty=50, avg_cost=4)
    pid_short = _stock_product(client, auth, qty=2, avg_cost=6)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    client.patch("/api/settings", headers=auth, json={"block_negative_stock": "true"})

    r = client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [
            {"product_id": pid_ok, "qty": 5},       # would succeed
            {"product_id": pid_short, "qty": 10},   # fails: only 2 on hand
        ],
    })
    assert r.status_code == 400

    # Line 1's product must be fully untouched — no partial consumption
    prod_ok = client.get(f"/api/products/{pid_ok}", headers=auth).json()
    assert Decimal(str(prod_ok["stock_qty"])) == Decimal("50")
    prod_short = client.get(f"/api/products/{pid_short}", headers=auth).json()
    assert Decimal(str(prod_short["stock_qty"])) == Decimal("2")

    # And no Store Issue row was persisted
    rows = client.get("/api/store-issues", headers=auth).json()
    assert rows == []


def test_issue_register_filters(client: TestClient):
    auth = _signup(client, "rep1@t.com")
    pid = _stock_product(client, auth, qty=50, avg_cost=5)
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id, "notes": "monthly maintenance draw",
        "lines": [{"product_id": pid, "qty": 3}],
    })
    rows = client.get("/api/store-reports/issue-register", headers=auth).json()
    assert len(rows) == 1
    assert Decimal(str(rows[0]["total_cost"])) == Decimal("15")  # 3 * 5

    rows = client.get("/api/store-reports/issue-register?q=maintenance", headers=auth).json()
    assert len(rows) == 1
    rows = client.get("/api/store-reports/issue-register?q=NOPE", headers=auth).json()
    assert rows == []


def test_stock_tie_out_zero_variance_on_clean_data(client: TestClient):
    """A product whose only movements in-window are one bill receipt and
    one store issue should tie out exactly."""
    auth = _signup(client, "rep2@t.com")
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    vendors = client.post("/api/vendors", headers=auth, json={"name": "Tie-Out Vendor"}).json()
    products = client.post("/api/products", headers=auth, json={
        "name": "Tie-Out Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    bill = client.post("/api/bills", headers=auth, json={
        "vendor_id": vendors["id"], "bill_date": "2026-07-01", "due_date": "2026-07-31",
        "lines": [{"description": "Tie-Out Widget", "product_id": products["id"], "qty": 20, "rate": 5}],
    })
    assert bill.status_code == 201, bill.text

    client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": products["id"], "qty": 6}],
    })

    rows = client.get(
        f"/api/store-reports/stock-tie-out?product_id={products['id']}", headers=auth
    ).json()
    assert len(rows) == 1
    row = rows[0]
    assert Decimal(str(row["received_qty"])) == Decimal("20")
    assert Decimal(str(row["issued_qty"])) == Decimal("6")
    assert Decimal(str(row["variance"])) == Decimal("0")


def test_stock_tie_out_zero_variance_with_sale(client: TestClient):
    """A product that also has a normal sale (INVOICE, not just a Store
    Issue) must still tie out to zero — expected_closing now accounts for
    ALL movement types that touch Product.stock_qty, not just bill
    receipts and store issues."""
    auth = _signup(client, "rep4@t.com")
    loc_id = _own_location(client, auth)
    acct_id = _expense_account(client, auth)
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Sale Tie-Out Vendor"}).json()
    customer = client.post("/api/customers", headers=auth, json={"name": "Sale Tie-Out Customer"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "Sale Tie-Out Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    bill = client.post("/api/bills", headers=auth, json={
        "vendor_id": vendor["id"], "bill_date": "2026-07-01", "due_date": "2026-07-31",
        "lines": [{"description": "Sale Tie-Out Widget", "product_id": product["id"], "qty": 20, "rate": 5}],
    })
    assert bill.status_code == 201, bill.text

    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": customer["id"], "issue_date": "2026-07-05", "gst_rate": 0,
        "lines": [{"product_id": product["id"], "description": "Sale Tie-Out Widget", "qty": 4, "rate": 20}],
    })
    assert inv.status_code == 201, inv.text

    client.post("/api/store-issues", headers=auth, json={
        "issue_date": "2026-07-10", "from_location_id": loc_id,
        "debit_account_id": acct_id,
        "lines": [{"product_id": product["id"], "qty": 6}],
    })

    rows = client.get(
        f"/api/store-reports/stock-tie-out?product_id={product['id']}", headers=auth
    ).json()
    assert len(rows) == 1
    row = rows[0]
    assert Decimal(str(row["received_qty"])) == Decimal("20")
    assert Decimal(str(row["issued_qty"])) == Decimal("6")
    assert Decimal(str(row["variance"])) == Decimal("0")


def test_stock_tie_out_windowed_end_returns_null_variance(client: TestClient):
    """A past `end` cannot be honestly reconciled against live stock —
    variance columns must be None while window quantities still return."""
    auth = _signup(client, "rep3@t.com")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Window Vendor"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "Window Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    bill = client.post("/api/bills", headers=auth, json={
        "vendor_id": vendor["id"], "bill_date": "2026-07-01", "due_date": "2026-07-31",
        "lines": [{"description": "Window Widget", "product_id": product["id"], "qty": 20, "rate": 5}],
    })
    assert bill.status_code == 201, bill.text

    rows = client.get(
        f"/api/store-reports/stock-tie-out?end=2026-01-01&product_id={product['id']}",
        headers=auth,
    ).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["variance"] is None
    assert row["expected_closing"] is None
    assert row["actual_closing"] is None
    # Window quantities still computed (the receipt occurred today, after
    # end=2026-01-01, so it falls outside the window and start is unset)
    assert Decimal(str(row["received_qty"])) == Decimal("0")
