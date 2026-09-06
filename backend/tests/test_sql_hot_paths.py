"""SQL hot-path fixes: journal pagination, dashboard aggregates, batched
invoice/bill lines, open-for-allocation, store-issue list pagination."""
from decimal import Decimal

from fastapi.testclient import TestClient


def _accounts(client, headers):
    items = client.get("/api/accounts", headers=headers).json()["items"]
    cash = next(a for a in items if a["code"] == "1000")
    revenue = next(a for a in items if a["code"] == "4000")
    expense = next(a for a in items if a["code"] == "5000")
    return cash, revenue, expense


def _post_jv(client, headers, date, debit_id, credit_id, amount, description="hot-path JV"):
    r = client.post("/api/transactions", headers=headers, json={
        "date": date,
        "description": description,
        "entries": [
            {"account_id": debit_id, "debit": amount, "credit": 0},
            {"account_id": credit_id, "debit": 0, "credit": amount},
        ],
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _signup_mfg(client: TestClient, email: str) -> dict:
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co",
        "business_model": "manufacturing",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_journal_paginates_in_sql(client, admin_headers):
    cash, revenue, _ = _accounts(client, admin_headers)
    for i in range(30):
        _post_jv(
            client, admin_headers, "2026-04-01",
            cash["id"], revenue["id"], 10 + i,
            description=f"JV {i:02d}",
        )

    page1 = client.get(
        "/api/reports/journal?skip=0&limit=20", headers=admin_headers,
    )
    assert page1.status_code == 200, page1.text
    data1 = page1.json()
    assert data1["total"] >= 60
    assert len(data1["items"]) == 20

    page2 = client.get(
        "/api/reports/journal?skip=20&limit=20", headers=admin_headers,
    ).json()
    assert page2["total"] == data1["total"]
    assert len(page2["items"]) == 20

    def _key(row):
        return (row["jv_number"], row["account_name"], str(row["debit"]), str(row["credit"]))

    assert {_key(r) for r in data1["items"]}.isdisjoint({_key(r) for r in page2["items"]})


def test_dashboard_revenue_expense_match_posted_jes(client, admin_headers):
    cash, revenue, expense = _accounts(client, admin_headers)
    _post_jv(client, admin_headers, "2026-06-01", cash["id"], revenue["id"], 50, "sale")
    _post_jv(client, admin_headers, "2026-06-02", expense["id"], cash["id"], 100, "cost")

    dash = client.get(
        "/api/reports/dashboard?start=2026-06-01&end=2026-06-30",
        headers=admin_headers,
    )
    assert dash.status_code == 200, dash.text
    summary = dash.json()["summary"]
    assert Decimal(str(summary["total_revenue"])) == Decimal("50")
    assert Decimal(str(summary["total_expense"])) == Decimal("100")


def test_invoice_list_batches_lines(client, admin_headers):
    cust = client.post("/api/customers", headers=admin_headers, json={"name": "Lines Co"}).json()
    a = client.post("/api/invoices", headers=admin_headers, json={
        "customer_id": cust["id"], "issue_date": "2026-05-01", "due_date": "2026-05-31",
        "gst_rate": 0,
        "lines": [{"description": "One", "qty": 1, "rate": 10}],
    })
    assert a.status_code == 201, a.text
    b = client.post("/api/invoices", headers=admin_headers, json={
        "customer_id": cust["id"], "issue_date": "2026-05-02", "due_date": "2026-05-31",
        "gst_rate": 0,
        "lines": [
            {"description": "Two-a", "qty": 1, "rate": 20},
            {"description": "Two-b", "qty": 2, "rate": 5},
        ],
    })
    assert b.status_code == 201, b.text

    listing = client.get("/api/invoices", headers=admin_headers)
    assert listing.status_code == 200, listing.text
    by_id = {inv["id"]: inv for inv in listing.json()["items"]}
    assert len(by_id[a.json()["id"]]["lines"]) == 1
    assert {ln["description"] for ln in by_id[a.json()["id"]]["lines"]} == {"One"}
    assert len(by_id[b.json()["id"]]["lines"]) == 2
    assert {ln["description"] for ln in by_id[b.json()["id"]]["lines"]} == {"Two-a", "Two-b"}


def test_open_invoices_for_allocation_excludes_paid(client, admin_headers):
    h = admin_headers
    cust = client.post("/api/customers", headers=h, json={"name": "Alloc Co"}).json()

    def _inv(rate, date):
        inv = client.post("/api/invoices", headers=h, json={
            "customer_id": cust["id"], "issue_date": date, "due_date": "2026-06-30",
            "gst_rate": 0,
            "lines": [{"description": "S", "qty": 1, "rate": rate}],
        }).json()
        client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
        return inv

    paid = _inv(100, "2026-05-01")
    partial = _inv(200, "2026-05-02")
    open_inv = _inv(300, "2026-05-03")

    r = client.post("/api/payments-received", headers=h, json={
        "customer_id": cust["id"], "payment_date": "2026-05-10", "amount": 100, "method": "cash",
        "allocations": [{"invoice_id": paid["id"], "amount": 100}],
    })
    assert r.status_code == 201, r.text
    r = client.post("/api/payments-received", headers=h, json={
        "customer_id": cust["id"], "payment_date": "2026-05-11", "amount": 50, "method": "cash",
        "allocations": [{"invoice_id": partial["id"], "amount": 50}],
    })
    assert r.status_code == 201, r.text

    rows = client.get(
        f"/api/invoices/open-for-allocation?customer_id={cust['id']}",
        headers=h,
    )
    assert rows.status_code == 200, rows.text
    by_id = {row["id"]: row for row in rows.json()}
    assert paid["id"] not in by_id
    assert Decimal(str(by_id[partial["id"]]["balance_due"])) == Decimal("150")
    assert Decimal(str(by_id[open_inv["id"]]["balance_due"])) == Decimal("300")


def test_open_bills_for_allocation_excludes_paid(client, admin_headers):
    h = admin_headers
    vendor = client.post("/api/vendors", headers=h, json={"name": "Alloc Vendor"}).json()

    def _bill(rate, date):
        bill = client.post("/api/bills", headers=h, json={
            "vendor_id": vendor["id"], "bill_date": date, "due_date": "2026-06-30",
            "gst_rate": 0,
            "lines": [{"description": "B", "qty": 1, "rate": rate}],
        }).json()
        client.patch(f"/api/bills/{bill['id']}/status?status=received", headers=h)
        return bill

    paid = _bill(100, "2026-05-01")
    partial = _bill(200, "2026-05-02")
    open_bill = _bill(300, "2026-05-03")

    r = client.post("/api/bill-payments", headers=h, json={
        "vendor_id": vendor["id"], "payment_date": "2026-05-10", "amount": 100, "method": "cash",
        "allocations": [{"bill_id": paid["id"], "amount": 100}],
    })
    assert r.status_code == 201, r.text
    r = client.post("/api/bill-payments", headers=h, json={
        "vendor_id": vendor["id"], "payment_date": "2026-05-11", "amount": 50, "method": "cash",
        "allocations": [{"bill_id": partial["id"], "amount": 50}],
    })
    assert r.status_code == 201, r.text

    rows = client.get(
        f"/api/bills/open-for-allocation?vendor_id={vendor['id']}",
        headers=h,
    )
    assert rows.status_code == 200, rows.text
    by_id = {row["id"]: row for row in rows.json()}
    assert paid["id"] not in by_id
    assert Decimal(str(by_id[partial["id"]]["balance_due"])) == Decimal("150")
    assert Decimal(str(by_id[open_bill["id"]]["balance_due"])) == Decimal("300")


def test_bill_list_batches_lines(client, admin_headers):
    vendor = client.post("/api/vendors", headers=admin_headers, json={"name": "Line Vendor"}).json()
    a = client.post("/api/bills", headers=admin_headers, json={
        "vendor_id": vendor["id"], "bill_date": "2026-05-01", "due_date": "2026-05-31",
        "gst_rate": 0,
        "lines": [{"description": "One", "qty": 1, "rate": 10}],
    })
    assert a.status_code == 201, a.text
    b = client.post("/api/bills", headers=admin_headers, json={
        "vendor_id": vendor["id"], "bill_date": "2026-05-02", "due_date": "2026-05-31",
        "gst_rate": 0,
        "lines": [
            {"description": "Two-a", "qty": 1, "rate": 20},
            {"description": "Two-b", "qty": 2, "rate": 5},
        ],
    })
    assert b.status_code == 201, b.text

    listing = client.get("/api/bills", headers=admin_headers).json()
    by_id = {bill["id"]: bill for bill in listing["items"]}
    assert len(by_id[a.json()["id"]]["lines"]) == 1
    assert len(by_id[b.json()["id"]]["lines"]) == 2


def test_store_issues_list_paginates(client: TestClient):
    auth = _signup_mfg(client, "si-hot@t.com")
    p = client.post("/api/products", headers=auth, json={
        "name": "Grease", "product_type": "stock", "opening_qty": 200,
    }).json()
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    exp = next(a for a in accounts if a["type"] == "Expense" and not a.get("is_group"))
    loc_id = client.get("/api/stock-locations", headers=auth).json()["items"][0]["id"]
    for i in range(55):
        r = client.post("/api/store-issues", headers=auth, json={
            "issue_date": "2026-07-07", "from_location_id": loc_id,
            "debit_account_id": exp["id"], "notes": f"draw {i}",
            "lines": [{"product_id": p["id"], "qty": 1}],
        })
        assert r.status_code == 201, r.text

    page1 = client.get("/api/store-issues?limit=50", headers=auth)
    assert page1.status_code == 200, page1.text
    data = page1.json()
    assert data["total"] == 55
    assert len(data["items"]) == 50
    assert data["items"][0]["location_name"]
    assert data["items"][0]["lines"]

    page2 = client.get("/api/store-issues?skip=50&limit=50", headers=auth).json()
    assert page2["total"] == 55
    assert len(page2["items"]) == 5
    assert {i["id"] for i in data["items"]}.isdisjoint({i["id"] for i in page2["items"]})
