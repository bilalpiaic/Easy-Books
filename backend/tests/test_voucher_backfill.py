"""Tests for the voucher backfill migration logic (Task 3).

The backfill is a one-time, idempotent operation that:
  1. Infers each transaction's voucher type from its source document.
  2. Preserves the original jv_number in legacy_jv_number.
  3. Renumbers per type in (date, id) chronological order.
  4. Seeds SequenceCounters so post-backfill voucher_number() continues the series.

These tests seed a tenant via the HTTP API so every transaction is created through
the real posting path, then call backfill_vouchers() directly and assert all
invariants.
"""
import re

import db as _db_module
from models import BankAccount, Bill, CreditNote, DebitNote, Invoice, PaymentReceived, BillPayment, SequenceCounter, Settings, Transaction
from services.voucher_backfill import backfill_vouchers
from services.vouchers import voucher_number
from sqlmodel import Session, select


# ── helpers ───────────────────────────────────────────────────────────────────


def _setup(client, h):
    """Create a customer, vendor, stock product (with inventory), and a service product."""
    cust = client.post("/api/customers", headers=h, json={"name": "BF Customer"}).json()
    vend = client.post("/api/vendors", headers=h, json={"name": "BF Vendor"}).json()
    svc_prod = client.post(
        "/api/products", headers=h,
        json={"name": "BF Service", "product_type": "service", "sale_price": 100},
    ).json()
    stock_prod = client.post(
        "/api/products", headers=h,
        json={"name": "BF Widget", "product_type": "stock", "sale_price": 50},
    ).json()
    return cust, vend, svc_prod, stock_prod


def _bank_coa_id(client, h) -> int:
    """Register account 1010 (Bank) as a BankAccount and return its GL account id."""
    accounts = client.get("/api/accounts", headers=h).json()["items"]
    bank_acc = next(a for a in accounts if a["code"] == "1010")
    coa_id = bank_acc["id"]
    r = client.post("/api/bank-accounts", headers=h, json={
        "name": "BF Bank",
        "bank_name": "First National",
        "coa_account_id": coa_id,
    })
    assert r.status_code in (200, 201), r.text
    return coa_id


def _get_txn(session: Session, txn_id: int) -> Transaction:
    t = session.get(Transaction, txn_id)
    assert t is not None, f"Transaction {txn_id} not found"
    return t


def _get_tenant_id(client, h) -> int:
    r = client.get("/api/accounts", headers=h)
    assert r.status_code == 200
    # Grab tenant_id from any account row in the DB
    with Session(_db_module.engine) as s:
        from models import Tenant
        tenant = s.exec(select(Tenant)).first()
        assert tenant is not None
        return tenant.id


# ── main backfill test ────────────────────────────────────────────────────────


def test_backfill_types_numbers_legacy_and_counters(client, admin_headers):
    """Full integration: seed mixed sources, backfill, assert all invariants."""
    h = admin_headers
    cust, vend, svc_prod, stock_prod = _setup(client, h)

    # --- Step 0: purchase stock so we can sell it (non-zero avg_cost for COGS JV)
    buy_r = client.post("/api/bills", headers=h, json={
        "vendor_id": vend["id"],
        "bill_date": "2026-01-01",
        "gst_rate": 0,
        "lines": [{"product_id": stock_prod["id"], "description": "stock purchase", "qty": 10, "rate": 40}],
    })
    assert buy_r.status_code == 201, buy_r.text
    buy_bill = buy_r.json()
    buy_txn_id = buy_bill["transaction_id"]

    # --- Step 1: invoice with a STOCK product (generates sale txn + COGS JV)
    inv_r = client.post("/api/invoices", headers=h, json={
        "customer_id": cust["id"],
        "issue_date": "2026-01-10",
        "gst_rate": 0,
        "lines": [{"product_id": stock_prod["id"], "description": "sale", "qty": 1, "rate": 50}],
    })
    assert inv_r.status_code == 201, inv_r.text
    inv = inv_r.json()
    inv_txn_id = inv["transaction_id"]
    cogs_txn_id = inv.get("cogs_transaction_id")
    assert cogs_txn_id, "Stock product invoice must have cogs_transaction_id"

    # --- Step 2: bill (purchase invoice)
    bill_r = client.post("/api/bills", headers=h, json={
        "vendor_id": vend["id"],
        "bill_date": "2026-01-11",
        "gst_rate": 0,
        "lines": [{"description": "Office supplies", "qty": 1, "rate": 200}],
    })
    assert bill_r.status_code == 201, bill_r.text
    bill_txn_id = bill_r.json()["transaction_id"]

    # --- Step 3: payment received into a CASH account (→ CR)
    cr_r = client.post("/api/payments-received", headers=h, json={
        "customer_id": cust["id"],
        "amount": 100,
        "method": "cash",
        "payment_date": "2026-01-12",
    })
    assert cr_r.status_code == 201, cr_r.text
    cr_txn_id = cr_r.json()["transaction_id"]

    # --- Step 4: bill payment from a BANK account (→ BP)
    bank_coa_id = _bank_coa_id(client, h)
    bp_r = client.post("/api/bill-payments", headers=h, json={
        "vendor_id": vend["id"],
        "amount": 200,
        "method": "bank_transfer",
        "payment_date": "2026-01-13",
        "cash_account_id": bank_coa_id,
    })
    assert bp_r.status_code == 201, bp_r.text
    bp_txn_id = bp_r.json()["transaction_id"]

    # --- Step 5: credit note (→ CN)
    cn_r = client.post("/api/credit-notes", headers=h, json={
        "customer_name": "BF Customer",
        "issue_date": "2026-01-14",
        "gst_amount": 0,
        "restock": False,
        "lines": [{"description": "Credit return", "qty": 1, "rate": 80}],
    })
    assert cn_r.status_code == 201, cn_r.text
    cn_txn_id = cn_r.json()["transaction_id"]

    # Collect all source txn ids (excluding the stock-purchase bill — that's also PR)
    source_txn_ids = {
        "inv": inv_txn_id,
        "cogs": cogs_txn_id,
        "bill": bill_txn_id,
        "cr": cr_txn_id,
        "bp": bp_txn_id,
        "cn": cn_txn_id,
        "buy": buy_txn_id,   # the stock purchase bill → PR
    }

    # --- Capture original jv_numbers BEFORE backfill
    with Session(_db_module.engine) as session:
        original_nums = {
            name: _get_txn(session, tid).jv_number
            for name, tid in source_txn_ids.items()
        }
        tenant_id = _get_txn(session, inv_txn_id).tenant_id

    # --- Run backfill
    with Session(_db_module.engine) as session:
        backfill_vouchers(session, tenant_id)
        session.commit()

    # --- Assert type assignments and legacy preservation
    EXPECTED_TYPES = {
        "inv": "SL",
        "cogs": "JV",
        "bill": "PR",
        "buy": "PR",
        "cr": "CR",
        "bp": "BP",
        "cn": "CN",
    }
    NUMBER_RE = re.compile(r"^([A-Z]{2})-(\d{6})$")

    with Session(_db_module.engine) as session:
        for name, tid in source_txn_ids.items():
            txn = _get_txn(session, tid)
            expected_type = EXPECTED_TYPES[name]
            assert txn.voucher_type == expected_type, (
                f"txn '{name}' (id={tid}): expected voucher_type={expected_type!r}, got {txn.voucher_type!r}"
            )
            # legacy_jv_number must equal the original number
            assert txn.legacy_jv_number == original_nums[name], (
                f"txn '{name}': legacy_jv_number {txn.legacy_jv_number!r} != original {original_nums[name]!r}"
            )
            # new jv_number must match TYPE-NNNNNN
            m = NUMBER_RE.match(txn.jv_number)
            assert m is not None, f"txn '{name}': jv_number {txn.jv_number!r} doesn't match pattern"
            assert m.group(1) == expected_type, (
                f"txn '{name}': jv_number prefix {m.group(1)!r} != expected type {expected_type!r}"
            )

    # --- Assert chronological ordering within each type
    with Session(_db_module.engine) as session:
        all_txns = session.exec(
            select(Transaction).where(Transaction.tenant_id == tenant_id)
        ).all()

        # Group by voucher_type
        by_type: dict[str, list[Transaction]] = {}
        for t in all_txns:
            by_type.setdefault(t.voucher_type, []).append(t)

        for vtype, txns in by_type.items():
            # Only check txns that were backfilled (have legacy_jv_number)
            backfilled = [t for t in txns if t.legacy_jv_number is not None]
            if not backfilled:
                continue
            # Sort by (date, id) — the canonical backfill order
            sorted_bf = sorted(backfilled, key=lambda t: (t.date, t.id))
            for i, t in enumerate(sorted_bf, 1):
                m = NUMBER_RE.match(t.jv_number)
                assert m is not None, f"Backfilled txn {t.id} has bad jv_number {t.jv_number!r}"
                seq = int(m.group(2))
                assert seq == i, (
                    f"Type {vtype!r}: expected seq {i} at pos {i}, got {seq} "
                    f"(txn.id={t.id}, date={t.date})"
                )

    # --- Assert uniqueness of jv_number within tenant
    with Session(_db_module.engine) as session:
        all_txns = session.exec(
            select(Transaction).where(Transaction.tenant_id == tenant_id)
        ).all()
        jv_numbers = [t.jv_number for t in all_txns]
        assert len(jv_numbers) == len(set(jv_numbers)), (
            f"Duplicate jv_numbers found: {[n for n in jv_numbers if jv_numbers.count(n) > 1]}"
        )

    # --- Assert SequenceCounter seeded so voucher_number() continues after highest backfilled
    with Session(_db_module.engine) as session:
        # Find the highest backfilled SL number
        sl_txns = session.exec(
            select(Transaction).where(
                Transaction.tenant_id == tenant_id,
                Transaction.voucher_type == "SL",
                Transaction.legacy_jv_number != None,  # noqa: E711
            )
        ).all()
        assert sl_txns, "Expected at least one SL txn after backfill"

        max_sl_seq = max(
            int(NUMBER_RE.match(t.jv_number).group(2))
            for t in sl_txns
            if NUMBER_RE.match(t.jv_number)
        )

        # voucher_number() should return max_sl_seq + 1
        next_sl = voucher_number(session, tenant_id, "SL")
        session.flush()
        next_seq = int(next_sl.split("-")[1])
        assert next_seq == max_sl_seq + 1, (
            f"Expected next SL seq {max_sl_seq + 1}, got {next_seq} (number: {next_sl!r})"
        )


def test_backfill_idempotent(client, admin_headers):
    """Running backfill_vouchers twice must be a no-op on the second call."""
    h = admin_headers
    cust, vend, svc_prod, _ = _setup(client, h)

    # Post a simple invoice and a bill
    inv_r = client.post("/api/invoices", headers=h, json={
        "customer_id": cust["id"],
        "issue_date": "2026-02-01",
        "gst_rate": 0,
        "lines": [{"product_id": svc_prod["id"], "description": "service", "qty": 1, "rate": 100}],
    })
    assert inv_r.status_code == 201, inv_r.text
    inv_txn_id = inv_r.json()["transaction_id"]

    bill_r = client.post("/api/bills", headers=h, json={
        "vendor_id": vend["id"],
        "bill_date": "2026-02-02",
        "gst_rate": 0,
        "lines": [{"description": "Expense", "qty": 1, "rate": 150}],
    })
    assert bill_r.status_code == 201, bill_r.text
    bill_txn_id = bill_r.json()["transaction_id"]

    with Session(_db_module.engine) as session:
        tenant_id = _get_txn(session, inv_txn_id).tenant_id

    # First backfill
    with Session(_db_module.engine) as session:
        backfill_vouchers(session, tenant_id)
        session.commit()

    # Capture state after first backfill
    with Session(_db_module.engine) as session:
        snap_inv = _get_txn(session, inv_txn_id)
        snap_bill = _get_txn(session, bill_txn_id)
        snap_inv_jv = snap_inv.jv_number
        snap_inv_legacy = snap_inv.legacy_jv_number
        snap_inv_type = snap_inv.voucher_type
        snap_bill_jv = snap_bill.jv_number
        snap_bill_legacy = snap_bill.legacy_jv_number
        snap_bill_type = snap_bill.voucher_type

        counter_sl = session.exec(
            select(SequenceCounter).where(
                SequenceCounter.tenant_id == tenant_id,
                SequenceCounter.name == "voucher:SL",
            )
        ).first()
        counter_sl_val = counter_sl.next_value if counter_sl else None

    # Second backfill — must be idempotent
    with Session(_db_module.engine) as session:
        backfill_vouchers(session, tenant_id)
        session.commit()

    # Assert nothing changed
    with Session(_db_module.engine) as session:
        inv_after = _get_txn(session, inv_txn_id)
        bill_after = _get_txn(session, bill_txn_id)

        assert inv_after.jv_number == snap_inv_jv, "Invoice jv_number changed on re-run"
        assert inv_after.legacy_jv_number == snap_inv_legacy, "Invoice legacy changed on re-run"
        assert inv_after.voucher_type == snap_inv_type, "Invoice voucher_type changed on re-run"

        assert bill_after.jv_number == snap_bill_jv, "Bill jv_number changed on re-run"
        assert bill_after.legacy_jv_number == snap_bill_legacy, "Bill legacy changed on re-run"
        assert bill_after.voucher_type == snap_bill_type, "Bill voucher_type changed on re-run"

        counter_sl_after = session.exec(
            select(SequenceCounter).where(
                SequenceCounter.tenant_id == tenant_id,
                SequenceCounter.name == "voucher:SL",
            )
        ).first()
        assert counter_sl_after is not None
        assert counter_sl_after.next_value == counter_sl_val, (
            f"SL counter changed on re-run: was {counter_sl_val}, now {counter_sl_after.next_value}"
        )


def test_new_post_after_backfill_continues_series(client, admin_headers):
    """A new invoice posted AFTER backfill must get the next SL number (no collision)."""
    h = admin_headers
    cust, _, svc_prod, _ = _setup(client, h)

    # Post an invoice BEFORE backfill
    inv1_r = client.post("/api/invoices", headers=h, json={
        "customer_id": cust["id"],
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"product_id": svc_prod["id"], "description": "pre-backfill", "qty": 1, "rate": 100}],
    })
    assert inv1_r.status_code == 201, inv1_r.text
    inv1 = inv1_r.json()
    inv1_txn_id = inv1["transaction_id"]

    with Session(_db_module.engine) as session:
        tenant_id = _get_txn(session, inv1_txn_id).tenant_id

    # Run backfill
    with Session(_db_module.engine) as session:
        backfill_vouchers(session, tenant_id)
        session.commit()

    # Get the SL number assigned by backfill
    with Session(_db_module.engine) as session:
        inv1_backfilled = _get_txn(session, inv1_txn_id)
        assert inv1_backfilled.voucher_type == "SL"
        assert inv1_backfilled.jv_number.startswith("SL-")
        bf_seq = int(inv1_backfilled.jv_number.split("-")[1])

    # Post a NEW invoice AFTER backfill
    inv2_r = client.post("/api/invoices", headers=h, json={
        "customer_id": cust["id"],
        "issue_date": "2026-03-05",
        "gst_rate": 0,
        "lines": [{"product_id": svc_prod["id"], "description": "post-backfill", "qty": 1, "rate": 120}],
    })
    assert inv2_r.status_code == 201, inv2_r.text
    inv2_txn_id = inv2_r.json()["transaction_id"]

    with Session(_db_module.engine) as session:
        inv2 = _get_txn(session, inv2_txn_id)
        assert inv2.jv_number.startswith("SL-"), (
            f"Post-backfill invoice should get SL- number, got {inv2.jv_number!r}"
        )
        new_seq = int(inv2.jv_number.split("-")[1])
        assert new_seq == bf_seq + 1, (
            f"Post-backfill SL should be {bf_seq + 1}, got {new_seq}"
        )

    # Check no collisions across all tenant transactions
    with Session(_db_module.engine) as session:
        all_jv = [
            t.jv_number for t in
            session.exec(select(Transaction).where(Transaction.tenant_id == tenant_id)).all()
        ]
        assert len(all_jv) == len(set(all_jv)), "Duplicate jv_number after new post"


def test_backfill_reversal_inherits_parent_type(client, admin_headers):
    """A reversal transaction (reversed_by_id) should inherit the original's voucher type."""
    h = admin_headers
    cust, _, svc_prod, _ = _setup(client, h)

    # Post an invoice (SL)
    inv_r = client.post("/api/invoices", headers=h, json={
        "customer_id": cust["id"],
        "issue_date": "2026-04-01",
        "gst_rate": 0,
        "lines": [{"product_id": svc_prod["id"], "description": "rev test", "qty": 1, "rate": 100}],
    })
    assert inv_r.status_code == 201, inv_r.text
    inv = inv_r.json()
    inv_txn_id = inv["transaction_id"]

    # Reverse the invoice transaction
    rev_r = client.post(f"/api/transactions/{inv_txn_id}/reverse", headers=h)
    assert rev_r.status_code == 200, rev_r.text
    reversal_id = rev_r.json()["reversal_id"]

    with Session(_db_module.engine) as session:
        tenant_id = _get_txn(session, inv_txn_id).tenant_id

    # At this point, the reversal already has voucher_type="SL" from Task 2.
    # The backfill should ALSO handle it correctly (the reversal is mapped via
    # the reversed_by_id back-ref, inheriting the original's type).
    # To test the backfill path, we temporarily reset the reversal's type.
    with Session(_db_module.engine) as session:
        rev_txn = _get_txn(session, reversal_id)
        original_rev_jv = rev_txn.jv_number
        rev_txn.voucher_type = "JV"              # reset to simulate pre-backfill state
        rev_txn.legacy_jv_number = None          # mark as un-backfilled
        session.add(rev_txn)
        # Also reset the original invoice txn
        inv_txn = _get_txn(session, inv_txn_id)
        inv_txn.voucher_type = "JV"
        inv_txn.legacy_jv_number = None
        session.add(inv_txn)
        session.commit()

    # Now run backfill
    with Session(_db_module.engine) as session:
        backfill_vouchers(session, tenant_id)
        session.commit()

    with Session(_db_module.engine) as session:
        inv_txn = _get_txn(session, inv_txn_id)
        rev_txn = _get_txn(session, reversal_id)

        assert inv_txn.voucher_type == "SL", (
            f"Invoice txn should be SL, got {inv_txn.voucher_type!r}"
        )
        assert rev_txn.voucher_type == "SL", (
            f"Reversal should inherit SL from original, got {rev_txn.voucher_type!r}"
        )
        assert rev_txn.jv_number.startswith("SL-"), (
            f"Reversal jv_number should start SL-, got {rev_txn.jv_number!r}"
        )


def test_backfill_safe_after_live_post(client, admin_headers):
    """Calling backfill_vouchers AFTER go-live must not corrupt live data.

    Scenario (the exact bug the done-marker guards against):
      1. Seed pre-migration invoices.
      2. Run backfill_vouchers (first run) → renumbers + writes done-marker.
      3. Post a NEW invoice AFTER backfill (live, legacy_jv_number = NULL).
      4. Call backfill_vouchers AGAIN.

    Expected: no exception; live invoice is UNCHANGED (same jv_number,
    legacy_jv_number still NULL, voucher_type still "SL"); backfilled rows
    are also unchanged.
    """
    h = admin_headers
    cust, _, svc_prod, _ = _setup(client, h)

    # ── Step 1: pre-migration invoice ────────────────────────────────────────
    pre_r = client.post("/api/invoices", headers=h, json={
        "customer_id": cust["id"],
        "issue_date": "2026-05-01",
        "gst_rate": 0,
        "lines": [{"product_id": svc_prod["id"], "description": "pre-backfill", "qty": 1, "rate": 100}],
    })
    assert pre_r.status_code == 201, pre_r.text
    pre_txn_id = pre_r.json()["transaction_id"]

    with Session(_db_module.engine) as session:
        tenant_id = _get_txn(session, pre_txn_id).tenant_id

    # ── Step 2: first backfill ────────────────────────────────────────────────
    with Session(_db_module.engine) as session:
        backfill_vouchers(session, tenant_id)
        session.commit()

    # Capture state of the backfilled transaction
    with Session(_db_module.engine) as session:
        pre_snap = _get_txn(session, pre_txn_id)
        pre_snap_jv = pre_snap.jv_number
        pre_snap_legacy = pre_snap.legacy_jv_number
        pre_snap_type = pre_snap.voucher_type
        # Done-marker must exist now
        marker = session.exec(
            select(Settings).where(
                Settings.tenant_id == tenant_id,
                Settings.key == "voucher_backfill_done",
            )
        ).first()
        assert marker is not None, "Done-marker missing after first backfill"
        assert marker.value == "true"

    # ── Step 3: post a NEW live invoice (legacy_jv_number = NULL after post) ──
    live_r = client.post("/api/invoices", headers=h, json={
        "customer_id": cust["id"],
        "issue_date": "2026-05-10",
        "gst_rate": 0,
        "lines": [{"product_id": svc_prod["id"], "description": "live post-backfill", "qty": 1, "rate": 120}],
    })
    assert live_r.status_code == 201, live_r.text
    live_txn_id = live_r.json()["transaction_id"]

    # Capture live transaction state immediately after posting
    with Session(_db_module.engine) as session:
        live_snap = _get_txn(session, live_txn_id)
        live_snap_jv = live_snap.jv_number
        live_snap_legacy = live_snap.legacy_jv_number  # should be NULL
        live_snap_type = live_snap.voucher_type          # should be "SL"

    # ── Step 4: second backfill — must be a no-op ─────────────────────────────
    with Session(_db_module.engine) as session:
        # Must not raise (no IntegrityError from duplicate jv_number)
        backfill_vouchers(session, tenant_id)
        session.commit()

    # ── Step 5: assert live invoice UNCHANGED ────────────────────────────────
    with Session(_db_module.engine) as session:
        live_after = _get_txn(session, live_txn_id)
        assert live_after.jv_number == live_snap_jv, (
            f"Live invoice jv_number was corrupted: was {live_snap_jv!r}, now {live_after.jv_number!r}"
        )
        assert live_after.legacy_jv_number is None, (
            f"Live invoice should have legacy_jv_number=NULL, got {live_after.legacy_jv_number!r}"
        )
        assert live_after.voucher_type == live_snap_type, (
            f"Live invoice voucher_type changed: was {live_snap_type!r}, now {live_after.voucher_type!r}"
        )

        # Assert backfilled rows are also unchanged
        pre_after = _get_txn(session, pre_txn_id)
        assert pre_after.jv_number == pre_snap_jv, (
            f"Backfilled invoice jv_number changed on second run: was {pre_snap_jv!r}, now {pre_after.jv_number!r}"
        )
        assert pre_after.legacy_jv_number == pre_snap_legacy, (
            f"Backfilled invoice legacy changed on second run"
        )
        assert pre_after.voucher_type == pre_snap_type, (
            f"Backfilled invoice voucher_type changed on second run"
        )
