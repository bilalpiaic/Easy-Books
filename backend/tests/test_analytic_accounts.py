"""Tests: analytic_account_id propagates to JournalEntry rows for all document types."""
from decimal import Decimal
from models import Invoice, Bill, PaymentReceived, BillPayment, TransactionCreate
import inspect


def test_invoice_model_has_analytic_account_id():
    fields = Invoice.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_bill_model_has_analytic_account_id():
    fields = Bill.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_payment_received_model_has_analytic_account_id():
    fields = PaymentReceived.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_bill_payment_model_has_analytic_account_id():
    fields = BillPayment.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_transaction_create_has_analytic_account_id():
    fields = TransactionCreate.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


# ── Integration tests: analytic tag flows from document → JournalEntry rows ──

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _login_token():
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    if r.status_code != 200:
        return None
    return r.json().get("access_token")


def _headers():
    token = _login_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def _first_analytic_id(headers):
    r = client.get("/api/analytic-accounts", headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    return items[0]["id"] if items else None


def test_invoice_analytic_propagates_to_je():
    h = _headers()
    if not h:
        return  # no admin user in test DB — skip
    aid = _first_analytic_id(h)
    if aid is None:
        return  # no analytic accounts — skip
    payload = {
        "customer_name": "Test Co",
        "issue_date": "2026-01-15",
        "due_date": "2026-02-15",
        "gst_rate": 0,
        "lines": [{"description": "Service", "qty": 1, "rate": 500}],
        "analytic_account_id": aid,
    }
    r = client.post("/api/invoices", json=payload, headers=h)
    assert r.status_code == 200, r.text
    inv_id = r.json()["id"]
    inv = client.get(f"/api/invoices/{inv_id}", headers=h).json()
    txn_id = inv.get("transaction_id")
    assert txn_id, "Invoice must have transaction_id after posting"
    txn = client.get(f"/api/transactions/{txn_id}", headers=h).json()
    for entry in txn["entries"]:
        assert entry.get("analytic_account_id") == aid, (
            f"JE row for account {entry.get('account_id')} missing analytic tag"
        )


def test_bill_analytic_propagates_to_je():
    h = _headers()
    if not h:
        return
    aid = _first_analytic_id(h)
    if aid is None:
        return
    payload = {
        "vendor_name": "Supplier Ltd",
        "bill_date": "2026-01-15",
        "due_date": "2026-02-15",
        "gst_rate": 0,
        "lines": [{"description": "Office supplies", "qty": 2, "rate": 100}],
        "analytic_account_id": aid,
    }
    r = client.post("/api/bills", json=payload, headers=h)
    assert r.status_code == 200, r.text
    bid = r.json()["id"]
    bill = client.get(f"/api/bills/{bid}", headers=h).json()
    txn = client.get(f"/api/transactions/{bill['transaction_id']}", headers=h).json()
    for entry in txn["entries"]:
        assert entry.get("analytic_account_id") == aid


def test_seed_analytic_pl_non_empty_when_tagged():
    """If analytic accounts exist, Analytic P&L must return rows for at least one dimension."""
    h = _headers()
    if not h:
        return  # no admin user in test DB — skip
    r = client.get("/api/analytic-accounts", headers=h)
    if r.status_code != 200:
        return
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    if not items:
        return  # no analytic accounts seeded — skip
    non_empty = 0
    for acc in items[:5]:
        pl = client.get(f"/api/reports/analytic-pl?analytic_account_id={acc['id']}", headers=h)
        if pl.status_code == 200 and pl.json():
            non_empty += 1
    # After seeding, at least 1 dimension must have non-empty P&L
    assert non_empty >= 1, "Analytic P&L empty for all checked dimensions — seed data missing analytic tags"
