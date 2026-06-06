"""Tests for voucher-type assignment at posting sites (Task 2 of voucher-series feature).

Verifies that each posting site assigns the correct voucher_type to the
Transaction row, and that jv_number starts with the expected prefix.

Coverage:
- Invoice create  → SL
- Invoice COGS sub-JV → JV
- Bill create     → PR
- Credit note     → CN
- Debit note      → DN
- Payment received into a cash account → CR
- Payment received into a bank-linked account → BR
- Bill payment from a cash account → CP
- Bill payment from a bank-linked account → BP
- Reversal of an invoice transaction (via /reverse endpoint) → inherits SL
- Invoice edit: the reversal inherits the old txn's voucher_type (SL),
  the new re-post gets SL again; edit-reversal of a COGS JV stays JV.
"""
import db as _db_module
from models import BankAccount, Invoice, Bill, CreditNote, DebitNote, Transaction
from sqlmodel import Session, select


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_txn(txn_id: int) -> Transaction:
    """Fetch a Transaction directly from the test DB (bypasses the API)."""
    with Session(_db_module.engine) as s:
        txn = s.get(Transaction, txn_id)
        assert txn is not None, f"Transaction {txn_id} not found"
        return txn


def _setup(client, h):
    """Create a customer, vendor, service product, and a stock product.
    Returns (customer, vendor, svc_product, stock_product)."""
    cust = client.post("/api/customers", headers=h, json={"name": "Test Customer"}).json()
    vend = client.post("/api/vendors", headers=h, json={"name": "Test Vendor"}).json()
    svc_prod = client.post(
        "/api/products", headers=h,
        json={"name": "Service", "product_type": "service", "sale_price": 100},
    ).json()
    stock_prod = client.post(
        "/api/products", headers=h,
        json={"name": "Widget", "product_type": "stock", "sale_price": 50},
    ).json()
    return cust, vend, svc_prod, stock_prod


def _post_invoice(client, h, customer_id, product_id, rate=100, gst_rate=0, date="2026-01-10"):
    """Create and return an invoice (service product by default → no COGS JV)."""
    r = client.post("/api/invoices", headers=h, json={
        "customer_id": customer_id,
        "issue_date": date,
        "gst_rate": gst_rate,
        "lines": [{"product_id": product_id, "description": "x", "qty": 1, "rate": rate}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _post_bill(client, h, vendor_id, rate=200, gst_rate=0, date="2026-01-11"):
    """Create a non-stock bill (pure expense line → minimal GL entries)."""
    r = client.post("/api/bills", headers=h, json={
        "vendor_id": vendor_id,
        "bill_date": date,
        "gst_rate": gst_rate,
        "lines": [{"description": "Office supplies", "qty": 1, "rate": rate}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _create_bank_account_linked(client, h) -> int:
    """Find the seeded "Bank" GL account (code 1010) and register it as a
    BankAccount so that classify_cash_account() returns 'bank' for it.
    Returns the GL account_id."""
    # The default CoA seeds account 1010 "Bank" — reuse it to avoid a
    # unique-constraint collision on account code.
    accounts = client.get("/api/accounts", headers=h).json()["items"]
    bank_acc = next(
        (a for a in accounts if a["code"] == "1010"),
        None,
    )
    assert bank_acc is not None, "Seeded 'Bank' account (1010) not found"
    coa_id = bank_acc["id"]

    # Register it as a BankAccount (links coa_account_id → classify as 'bank')
    ba_r = client.post("/api/bank-accounts", headers=h, json={
        "name": "Test Bank",
        "bank_name": "First National",
        "coa_account_id": coa_id,
    })
    assert ba_r.status_code in (200, 201), ba_r.text

    return coa_id


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_invoice_gets_sl_voucher_type(client, admin_headers):
    """An invoice transaction must be assigned voucher_type='SL'."""
    h = admin_headers
    cust, _, svc_prod, _ = _setup(client, h)
    inv = _post_invoice(client, h, cust["id"], svc_prod["id"])

    assert inv.get("transaction_id"), "Invoice should have a transaction_id"
    txn = _get_txn(inv["transaction_id"])
    assert txn.voucher_type == "SL", f"Expected SL, got {txn.voucher_type!r}"
    assert txn.jv_number.startswith("SL-"), f"Expected SL- prefix, got {txn.jv_number!r}"


def test_invoice_cogs_sub_entry_gets_jv(client, admin_headers):
    """The COGS sub-JV for a stock-product invoice must stay as JV."""
    h = admin_headers
    # First stock product needs a purchase to build inventory (non-zero avg_cost).
    cust, vend, _, stock_prod = _setup(client, h)

    # Purchase some stock so we have inventory to sell.
    client.post("/api/bills", headers=h, json={
        "vendor_id": vend["id"],
        "bill_date": "2026-01-05",
        "gst_rate": 0,
        "lines": [{"product_id": stock_prod["id"], "description": "buy", "qty": 10, "rate": 40}],
    })

    inv = _post_invoice(client, h, cust["id"], stock_prod["id"], rate=50, date="2026-01-10")
    cogs_txn_id = inv.get("cogs_transaction_id")
    assert cogs_txn_id, "Stock product invoice should have a cogs_transaction_id"

    cogs_txn = _get_txn(cogs_txn_id)
    assert cogs_txn.voucher_type == "JV", f"COGS JV should be JV, got {cogs_txn.voucher_type!r}"
    assert cogs_txn.jv_number.startswith("JV-"), f"COGS JV should have JV- prefix"


def test_bill_gets_pr_voucher_type(client, admin_headers):
    """A bill transaction must be assigned voucher_type='PR'."""
    h = admin_headers
    _, vend, _, _ = _setup(client, h)
    bill = _post_bill(client, h, vend["id"])

    assert bill.get("transaction_id"), "Bill should have a transaction_id"
    txn = _get_txn(bill["transaction_id"])
    assert txn.voucher_type == "PR", f"Expected PR, got {txn.voucher_type!r}"
    assert txn.jv_number.startswith("PR-"), f"Expected PR- prefix, got {txn.jv_number!r}"


def test_credit_note_gets_cn_voucher_type(client, admin_headers):
    """A credit note transaction must be assigned voucher_type='CN'."""
    h = admin_headers
    cust, _, svc_prod, _ = _setup(client, h)

    cn_r = client.post("/api/credit-notes", headers=h, json={
        "customer_name": "Test Customer",
        "issue_date": "2026-01-15",
        "gst_amount": 0,
        "restock": False,
        "lines": [{"description": "Return of service", "qty": 1, "rate": 80}],
    })
    assert cn_r.status_code == 201, cn_r.text
    cn = cn_r.json()

    assert cn.get("transaction_id"), "Credit note should have a transaction_id"
    txn = _get_txn(cn["transaction_id"])
    assert txn.voucher_type == "CN", f"Expected CN, got {txn.voucher_type!r}"
    assert txn.jv_number.startswith("CN-"), f"Expected CN- prefix, got {txn.jv_number!r}"


def test_debit_note_gets_dn_voucher_type(client, admin_headers):
    """A debit note transaction must be assigned voucher_type='DN'."""
    h = admin_headers
    _, vend, _, _ = _setup(client, h)

    # Debit note requires an existing bill.
    bill = _post_bill(client, h, vend["id"], rate=200)

    dn_r = client.post("/api/debit-notes", headers=h, json={
        "bill_id": bill["id"],
        "vendor_id": vend["id"],
        "issue_date": "2026-01-20",
        "gst_amount": 0,
        "lines": [{"description": "Return", "qty": 1, "rate": 50}],
    })
    assert dn_r.status_code == 201, dn_r.text
    dn = dn_r.json()

    assert dn.get("transaction_id"), "Debit note should have a transaction_id"
    txn = _get_txn(dn["transaction_id"])
    assert txn.voucher_type == "DN", f"Expected DN, got {txn.voucher_type!r}"
    assert txn.jv_number.startswith("DN-"), f"Expected DN- prefix, got {txn.jv_number!r}"


def test_payment_received_cash_gets_cr(client, admin_headers):
    """Payment received into a cash account (default 1000) → voucher_type='CR'."""
    h = admin_headers
    cust, _, _, _ = _setup(client, h)

    # No cash_account_id → falls back to "Cash in Hand" (code 1000), which has
    # no BankAccount row → classify_cash_account returns 'cash' → CR.
    pmt_r = client.post("/api/payments-received", headers=h, json={
        "customer_id": cust["id"],
        "amount": 100,
        "method": "cash",
        "payment_date": "2026-01-12",
    })
    assert pmt_r.status_code == 201, pmt_r.text
    pmt = pmt_r.json()

    assert pmt.get("transaction_id"), "Payment should have a transaction_id"
    txn = _get_txn(pmt["transaction_id"])
    assert txn.voucher_type == "CR", f"Expected CR, got {txn.voucher_type!r}"
    assert txn.jv_number.startswith("CR-"), f"Expected CR- prefix, got {txn.jv_number!r}"


def test_payment_received_bank_gets_br(client, admin_headers):
    """Payment received into a bank-linked account → voucher_type='BR'."""
    h = admin_headers
    cust, _, _, _ = _setup(client, h)

    # Create a bank-linked GL account.
    bank_coa_id = _create_bank_account_linked(client, h)

    pmt_r = client.post("/api/payments-received", headers=h, json={
        "customer_id": cust["id"],
        "amount": 150,
        "method": "bank_transfer",
        "payment_date": "2026-01-13",
        "cash_account_id": bank_coa_id,
    })
    assert pmt_r.status_code == 201, pmt_r.text
    pmt = pmt_r.json()

    assert pmt.get("transaction_id"), "Payment should have a transaction_id"
    txn = _get_txn(pmt["transaction_id"])
    assert txn.voucher_type == "BR", f"Expected BR, got {txn.voucher_type!r}"
    assert txn.jv_number.startswith("BR-"), f"Expected BR- prefix, got {txn.jv_number!r}"


def test_bill_payment_cash_gets_cp(client, admin_headers):
    """Bill payment from a cash account (default 1000) → voucher_type='CP'."""
    h = admin_headers
    _, vend, _, _ = _setup(client, h)

    bp_r = client.post("/api/bill-payments", headers=h, json={
        "vendor_id": vend["id"],
        "amount": 200,
        "method": "cash",
        "payment_date": "2026-01-14",
    })
    assert bp_r.status_code == 201, bp_r.text
    bp = bp_r.json()

    assert bp.get("transaction_id"), "Bill payment should have a transaction_id"
    txn = _get_txn(bp["transaction_id"])
    assert txn.voucher_type == "CP", f"Expected CP, got {txn.voucher_type!r}"
    assert txn.jv_number.startswith("CP-"), f"Expected CP- prefix, got {txn.jv_number!r}"


def test_bill_payment_bank_gets_bp(client, admin_headers):
    """Bill payment from a bank-linked account → voucher_type='BP'."""
    h = admin_headers
    _, vend, _, _ = _setup(client, h)

    bank_coa_id = _create_bank_account_linked(client, h)

    bp_r = client.post("/api/bill-payments", headers=h, json={
        "vendor_id": vend["id"],
        "amount": 250,
        "method": "bank_transfer",
        "payment_date": "2026-01-15",
        "cash_account_id": bank_coa_id,
    })
    assert bp_r.status_code == 201, bp_r.text
    bp = bp_r.json()

    assert bp.get("transaction_id"), "Bill payment should have a transaction_id"
    txn = _get_txn(bp["transaction_id"])
    assert txn.voucher_type == "BP", f"Expected BP, got {txn.voucher_type!r}"
    assert txn.jv_number.startswith("BP-"), f"Expected BP- prefix, got {txn.jv_number!r}"


def test_reverse_invoice_txn_inherits_sl(client, admin_headers):
    """Reversing an invoice transaction via the /reverse endpoint gives a
    reversal transaction that inherits the original's voucher_type ('SL')."""
    h = admin_headers
    cust, _, svc_prod, _ = _setup(client, h)
    inv = _post_invoice(client, h, cust["id"], svc_prod["id"])

    original_txn_id = inv["transaction_id"]
    original_txn = _get_txn(original_txn_id)
    assert original_txn.voucher_type == "SL"

    rev_r = client.post(f"/api/transactions/{original_txn_id}/reverse", headers=h)
    assert rev_r.status_code == 200, rev_r.text
    rev_data = rev_r.json()

    reversal_id = rev_data["reversal_id"]
    rev_txn = _get_txn(reversal_id)
    assert rev_txn.voucher_type == "SL", (
        f"Reversal should inherit SL from the original, got {rev_txn.voucher_type!r}"
    )
    assert rev_txn.jv_number.startswith("SL-"), (
        f"Reversal JV number should have SL- prefix, got {rev_txn.jv_number!r}"
    )


def test_invoice_edit_reversal_inherits_sl(client, admin_headers):
    """When an invoice is edited, the internal reversal of the old txn should
    inherit the old txn's voucher_type (SL), and the new re-post should also
    be SL."""
    h = admin_headers
    cust, _, svc_prod, _ = _setup(client, h)
    inv = _post_invoice(client, h, cust["id"], svc_prod["id"], rate=100)

    original_txn_id = inv["transaction_id"]
    original_txn = _get_txn(original_txn_id)
    assert original_txn.voucher_type == "SL"

    # Edit the invoice
    edit_r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_id": cust["id"],
        "issue_date": "2026-01-10",
        "gst_rate": 0,
        "lines": [{"product_id": svc_prod["id"], "description": "x edited", "qty": 1, "rate": 120}],
    })
    assert edit_r.status_code == 200, edit_r.text
    edited_inv = edit_r.json()

    # The original txn should now be reversed
    orig_txn_refreshed = _get_txn(original_txn_id)
    assert orig_txn_refreshed.is_reversed, "Original txn should be marked reversed"

    # The reversal txn (reversed_by_id on the old txn) should inherit SL.
    assert orig_txn_refreshed.reversed_by_id is not None
    rev_txn = _get_txn(orig_txn_refreshed.reversed_by_id)
    assert rev_txn.voucher_type == "SL", (
        f"Edit-reversal should inherit SL, got {rev_txn.voucher_type!r}"
    )
    assert rev_txn.jv_number.startswith("SL-"), (
        f"Edit-reversal JV should start SL-, got {rev_txn.jv_number!r}"
    )

    # The new re-post on the edited invoice should also be SL.
    new_txn_id = edited_inv["transaction_id"]
    new_txn = _get_txn(new_txn_id)
    assert new_txn.voucher_type == "SL", (
        f"Re-posted invoice txn should be SL, got {new_txn.voucher_type!r}"
    )
    assert new_txn.jv_number.startswith("SL-")


def test_bill_edit_reversal_inherits_pr(client, admin_headers):
    """When a bill is edited, the reversal of the old txn inherits PR, and the
    re-post is also PR."""
    h = admin_headers
    _, vend, _, _ = _setup(client, h)
    bill = _post_bill(client, h, vend["id"], rate=200)

    orig_txn_id = bill["transaction_id"]
    orig_txn = _get_txn(orig_txn_id)
    assert orig_txn.voucher_type == "PR"

    edit_r = client.put(f"/api/bills/{bill['id']}", headers=h, json={
        "vendor_id": vend["id"],
        "bill_date": "2026-01-11",
        "gst_rate": 0,
        "lines": [{"description": "Office supplies edited", "qty": 1, "rate": 250}],
    })
    assert edit_r.status_code == 200, edit_r.text
    edited_bill = edit_r.json()

    orig_refreshed = _get_txn(orig_txn_id)
    assert orig_refreshed.is_reversed

    rev_txn = _get_txn(orig_refreshed.reversed_by_id)
    assert rev_txn.voucher_type == "PR", (
        f"Bill edit-reversal should inherit PR, got {rev_txn.voucher_type!r}"
    )
    assert rev_txn.jv_number.startswith("PR-")

    new_txn_id = edited_bill["transaction_id"]
    new_txn = _get_txn(new_txn_id)
    assert new_txn.voucher_type == "PR", (
        f"Re-posted bill txn should be PR, got {new_txn.voucher_type!r}"
    )
    assert new_txn.jv_number.startswith("PR-")
