"""Tests for the sub-ledger GL view endpoint.

GET /api/reports/ledger/subledger?control=ar|ap|bank&start=&end=
Returns {control, items, control_balance, sub_total, reconciles}.
"""
from decimal import Decimal


# ── Helpers ──────────────────────────────────────────────────────────────────


def _post_inv(client, h, cid, pid, rate, qty, date):
    """Create and mark-sent an invoice."""
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": cid, "issue_date": date, "gst_rate": 0,
        "lines": [{"product_id": pid, "description": "x", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    return inv


def _post_bill(client, h, vid, pid, rate, qty, date):
    """Create a bill and mark it received."""
    bill = client.post("/api/bills", headers=h, json={
        "vendor_id": vid, "bill_date": date, "gst_rate": 0,
        "lines": [{"product_id": pid, "description": "x", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/bills/{bill['id']}/status?status=received", headers=h)
    return bill


# ── Task 1: AR sub-ledger ────────────────────────────────────────────────────


def test_ar_subledger_reconciles(client, admin_headers):
    h = admin_headers
    a = client.post("/api/customers", headers=h, json={"name": "Alpha"}).json()
    b = client.post("/api/customers", headers=h, json={"name": "Beta"}).json()
    p = client.post("/api/products", headers=h, json={
        "name": "W", "product_type": "service",
    }).json()
    _post_inv(client, h, a["id"], p["id"], 100, 2, "2026-02-01")   # Alpha AR 200
    _post_inv(client, h, b["id"], p["id"], 50, 3, "2026-02-05")    # Beta AR 150

    data = client.get(
        "/api/reports/ledger/subledger?control=ar&start=2026-01-01&end=2026-02-28",
        headers=h,
    ).json()

    by = {r["name"]: r for r in data["items"]}
    assert by["Alpha"]["closing"] == 200 and by["Alpha"]["debit"] == 200
    assert by["Beta"]["closing"] == 150
    assert data["sub_total"] == 350
    assert data["reconciles"] is True          # Σ sub == control 1100 GL balance
    assert by["Alpha"]["link"] == "/customers/%d/ledger" % a["id"]


# ── Task 2: AP sub-ledger ────────────────────────────────────────────────────


def test_ap_subledger_reconciles(client, admin_headers):
    h = admin_headers
    v1 = client.post("/api/vendors", headers=h, json={"name": "VendorOne"}).json()
    v2 = client.post("/api/vendors", headers=h, json={"name": "VendorTwo"}).json()
    p = client.post("/api/products", headers=h, json={
        "name": "Svc", "product_type": "service",
    }).json()
    _post_bill(client, h, v1["id"], p["id"], 200, 1, "2026-02-01")   # V1 AP 200
    _post_bill(client, h, v2["id"], p["id"], 100, 3, "2026-02-05")   # V2 AP 300

    data = client.get(
        "/api/reports/ledger/subledger?control=ap&start=2026-01-01&end=2026-02-28",
        headers=h,
    ).json()

    by = {r["name"]: r for r in data["items"]}
    assert by["VendorOne"]["closing"] == 200 and by["VendorOne"]["credit"] == 200
    assert by["VendorTwo"]["closing"] == 300
    assert data["sub_total"] == 500
    assert data["reconciles"] is True          # Σ sub == control 2000 GL balance
    assert by["VendorOne"]["link"] == "/vendors/%d/ledger" % v1["id"]


# ── Task 3: Bank sub-ledger ──────────────────────────────────────────────────


def test_bank_subledger(client, admin_headers):
    """Two payments into two different cash/bank GL accounts (1000 Cash, 1010 Bank).
    Each account should appear as a sub-entity with matching GL balance.

    Both accounts are pre-seeded by the tenant bootstrap — we look them up
    rather than creating them.
    """
    h = admin_headers

    # Both 1000 and 1010 are pre-seeded by db.py; retrieve their ids.
    accs = client.get("/api/accounts", headers=h).json()["items"]
    cash_acc = next(a for a in accs if a["code"] == "1000")
    bank_acc = next(a for a in accs if a["code"] == "1010")
    cash_acc_id = cash_acc["id"]
    bank_acc_id = bank_acc["id"]

    cust = client.post("/api/customers", headers=h, json={"name": "Cust"}).json()
    svc = client.post("/api/products", headers=h, json={
        "name": "Svc", "product_type": "service",
    }).json()

    inv1 = _post_inv(client, h, cust["id"], svc["id"], 500, 1, "2026-02-01")
    inv2 = _post_inv(client, h, cust["id"], svc["id"], 300, 1, "2026-02-05")

    # Pay inv1 into cash (1000), inv2 into bank (1010)
    pay1_r = client.post("/api/payments-received", headers=h, json={
        "invoice_id": inv1["id"], "payment_date": "2026-02-10",
        "amount": 500, "method": "cash",
        "cash_account_id": cash_acc_id,
    })
    assert pay1_r.status_code == 201, pay1_r.text

    pay2_r = client.post("/api/payments-received", headers=h, json={
        "invoice_id": inv2["id"], "payment_date": "2026-02-10",
        "amount": 300, "method": "bank",
        "cash_account_id": bank_acc_id,
    })
    assert pay2_r.status_code == 201, pay2_r.text

    data = client.get(
        "/api/reports/ledger/subledger?control=bank&start=2026-01-01&end=2026-02-28",
        headers=h,
    ).json()

    # Find accounts by id since names may vary across seeds
    cash_item = next((r for r in data["items"] if r["id"] == cash_acc_id), None)
    bank_item = next((r for r in data["items"] if r["id"] == bank_acc_id), None)
    assert cash_item is not None, f"Cash account {cash_acc_id} not in items: {data['items']}"
    assert bank_item is not None, f"Bank account {bank_acc_id} not in items: {data['items']}"
    assert cash_item["closing"] == 500
    assert bank_item["closing"] == 300
    assert data["sub_total"] == 800
    assert data["reconciles"] is True
    # Each item links to the per-account ledger
    assert cash_item["link"] == f"/ledger?account_id={cash_acc_id}"
    assert bank_item["link"] == f"/ledger?account_id={bank_acc_id}"


# ── Task 5: Edge cases ───────────────────────────────────────────────────────


def test_subledger_tenant_isolation(client, admin_headers):
    """A foreign-tenant customer/AR never leaks into the response."""
    h_a = admin_headers  # tenant A

    # Sign up a second tenant
    r = client.post("/api/auth/signup", json={
        "email": "ownerB@test.test", "password": "pw12345678",
        "full_name": "OwnerB", "company_name": "CompanyB",
    })
    assert r.status_code == 200, r.text
    tok_b = client.post("/api/auth/login", data={
        "username": "ownerB@test.test", "password": "pw12345678",
    }).json()["access_token"]
    client.cookies.clear()
    h_b = {"Authorization": f"Bearer {tok_b}"}

    # Tenant B creates a customer with an invoice
    cust_b = client.post("/api/customers", headers=h_b, json={"name": "ForeignCust"}).json()
    svc_b = client.post("/api/products", headers=h_b, json={
        "name": "Svc", "product_type": "service",
    }).json()
    _post_inv(client, h_b, cust_b["id"], svc_b["id"], 999, 1, "2026-02-01")

    # Tenant A's subledger should NOT include ForeignCust
    data_a = client.get(
        "/api/reports/ledger/subledger?control=ar&start=2026-01-01&end=2026-12-31",
        headers=h_a,
    ).json()
    names_a = [r["name"] for r in data_a["items"]]
    assert "ForeignCust" not in names_a


def test_subledger_empty_control(client, admin_headers):
    """Control account with no sub-entity activity returns items: [], reconciles True."""
    h = admin_headers
    data = client.get(
        "/api/reports/ledger/subledger?control=ar&start=2026-01-01&end=2026-12-31",
        headers=h,
    ).json()
    assert data["items"] == []
    # sub_total == control_balance == 0, so reconciles == True
    assert data["reconciles"] is True


def test_ar_opening_balance_caveat(client, admin_headers):
    """A customer with a non-zero opening_balance that was NOT journalised to the AR
    control account causes reconciles == False by the opening-balance delta.

    POLICY (documented here and in the endpoint code):
    Customer.opening_balance is a setup-time snapshot used to seed the
    customer's AR sub-ledger. It is NOT automatically journalised to the AR
    control account (1100). Therefore, sub_total (which includes the opening
    balance) will differ from control_balance (which is derived purely from
    JournalEntry rows) by the sum of non-journalised opening balances.

    The correct reconciliation path is to manually post an opening-balance JE
    at setup: Dr 1100 Accounts Receivable / Cr Opening Balance Equity, and set
    Customer.opening_balance = that amount.
    """
    h = admin_headers
    # Create a customer with an opening_balance NOT backed by a JE
    cust = client.post("/api/customers", headers=h, json={
        "name": "OBCust", "opening_balance": "500",
    }).json()
    # No invoices, no journalised transactions for this customer

    data = client.get(
        "/api/reports/ledger/subledger?control=ar&start=2026-01-01&end=2026-12-31",
        headers=h,
    ).json()
    by = {r["name"]: r for r in data["items"]}
    # The customer appears because opening_balance > 0
    assert "OBCust" in by
    # The sub_total includes the opening balance (500), but the control GL
    # balance is 0 (no JE was posted). So they differ → reconciles == False.
    assert data["reconciles"] is False
    # sub_total should include the opening balance
    assert data["sub_total"] >= 500
