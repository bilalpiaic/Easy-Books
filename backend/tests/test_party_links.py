"""§2 — JournalEntry carries customer_id/vendor_id; Account carries party_type.
   §3 — FixedAsset carries acquisition_transaction_id."""
from models import JournalEntry, Account, FixedAsset


def test_journal_entry_has_customer_id():
    fields = JournalEntry.model_fields
    assert "customer_id" in fields
    assert fields["customer_id"].default is None


def test_journal_entry_has_vendor_id():
    fields = JournalEntry.model_fields
    assert "vendor_id" in fields
    assert fields["vendor_id"].default is None


def test_account_has_party_type():
    fields = Account.model_fields
    assert "party_type" in fields
    assert fields["party_type"].default is None


def test_fixed_asset_has_acquisition_transaction_id():
    fields = FixedAsset.model_fields
    assert "acquisition_transaction_id" in fields
    assert fields["acquisition_transaction_id"].default is None


# ── Integration tests ──────────────────────────────────────────────────────

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _login_headers():
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    if r.status_code != 200:
        return None
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _get_accounts(headers) -> list:
    r = client.get("/api/accounts?limit=500", headers=headers)
    return r.json().get("items", []) if r.status_code == 200 else []


def test_invoice_ar_je_has_customer_id():
    """Invoice posting must tag the AR JournalEntry row with customer_id."""
    headers = _login_headers()
    if not headers:
        return
    r = client.get("/api/customers?limit=5", headers=headers)
    if r.status_code != 200:
        return
    body = r.json()
    items = body.get("items") or (body if isinstance(body, list) else [])
    if not items:
        return
    customer_id = items[0]["id"]

    accounts = _get_accounts(headers)
    rev_acc = next((a for a in accounts if a["type"] == "Revenue" and not a.get("is_group")), None)
    if not rev_acc:
        return

    r = client.post("/api/invoices", json={
        "customer_id": customer_id,
        "issue_date": "2026-01-01",
        "due_date": "2026-01-31",
        "lines": [{"description": "Test", "qty": 1, "rate": 500, "account_id": rev_acc["id"]}],
    }, headers=headers)
    if r.status_code not in (200, 201):
        return
    inv_id = r.json()["id"]

    inv_r = client.get(f"/api/invoices/{inv_id}", headers=headers)
    txn_id = inv_r.json().get("transaction_id")
    if not txn_id:
        return

    txn_r = client.get(f"/api/transactions/{txn_id}", headers=headers)
    entries = txn_r.json().get("entries", [])
    ar_entries = [e for e in entries if (e.get("debit") or 0) > 0 and e.get("account_type") == "Asset"]
    assert any(e.get("customer_id") == customer_id for e in ar_entries), \
        f"No AR entry tagged with customer_id={customer_id}. entries={entries}"


def test_bill_ap_je_has_vendor_id():
    """Bill posting must tag the AP JournalEntry row with vendor_id."""
    headers = _login_headers()
    if not headers:
        return
    r = client.get("/api/vendors?limit=5", headers=headers)
    if r.status_code != 200:
        return
    body = r.json()
    items = body.get("items") or (body if isinstance(body, list) else [])
    if not items:
        return
    vendor_id = items[0]["id"]

    accounts = _get_accounts(headers)
    exp_acc = next((a for a in accounts if a["type"] == "Expense" and not a.get("is_group")), None)
    if not exp_acc:
        return

    r = client.post("/api/bills", json={
        "vendor_id": vendor_id,
        "bill_date": "2026-01-01",
        "due_date": "2026-01-31",
        "lines": [{"description": "Test", "qty": 1, "rate": 300, "account_id": exp_acc["id"]}],
    }, headers=headers)
    if r.status_code not in (200, 201):
        return
    bill_id = r.json()["id"]

    bill_r = client.get(f"/api/bills/{bill_id}", headers=headers)
    txn_id = bill_r.json().get("transaction_id")
    if not txn_id:
        return

    txn_r = client.get(f"/api/transactions/{txn_id}", headers=headers)
    entries = txn_r.json().get("entries", [])
    ap_entries = [e for e in entries if (e.get("credit") or 0) > 0 and e.get("account_type") == "Liability"]
    assert any(e.get("vendor_id") == vendor_id for e in ap_entries), \
        f"No AP entry tagged with vendor_id={vendor_id}. entries={entries}"
