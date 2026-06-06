"""One-time, idempotent backfill that infers voucher types from source documents
and renumbers existing transactions per type.

Algorithm
---------
1. Check for a per-tenant done-marker (``Settings(key="voucher_backfill_done",
   value="true")``).  If present → return immediately (no-op).

2. Build ``{txn_id: vtype}`` from every source-document back-reference within
   the tenant.  The inference table (spec §Backfill):

   Source                          Inferred type
   -------                         -------------
   Invoice.transaction_id          SL
   Invoice.cogs_transaction_id     JV
   Bill.transaction_id             PR
   PaymentReceived.transaction_id  BR if cash_account_id is bank-linked else CR
   BillPayment.transaction_id      BP if cash_account_id is bank-linked else CP
   CreditNote.transaction_id       CN
   DebitNote.transaction_id        DN
   Reversal txn (appears as some   inherits the *original* (reversed) txn's type
     txn's reversed_by_id)
   Anything unmatched              JV

3. Select rows where ``legacy_jv_number IS NULL`` for the actual first-run
   processing (correct for the first run; the outer done-marker prevents
   re-processing post-migration live transactions on any subsequent call).

4. Two-pass renumber to stay within the UNIQUE(tenant_id, jv_number) constraint:
   - Pass A: set ``jv_number = f"__MIG__{txn.id}"``,
             ``legacy_jv_number = old jv_number``,
             ``voucher_type = inferred``.  flush().
   - Pass B: order the processed rows by (date, id), assign
             ``jv_number = f"{vtype}-{seq:06d}"`` with a LOCAL counter per type
             (NOT ``next_number``, so numbering is deterministic and restartable).
             flush().

5. Seed ``SequenceCounter`` for every type touched: set
   ``next_value = max_assigned_seq + 1`` (create if missing; raise if already
   lower) so post-migration ``voucher_number()`` continues the series.

6. Write the per-tenant done-marker so subsequent calls are no-ops.

Caller is responsible for committing the session.

Idempotency guarantee
---------------------
``backfill_vouchers`` is intrinsically idempotent via the per-tenant
``Settings(key="voucher_backfill_done", value="true")`` row written at the
end of the first successful run.  Any call after the first — whether triggered
by a re-run migration, a scheduled job, or direct invocation — returns
immediately without reading or touching any Transaction rows.  This prevents
live post-migration transactions (which also have ``legacy_jv_number IS NULL``)
from being wrongly renumbered on a second call.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from models import (
    Bill,
    BillPayment,
    CreditNote,
    DebitNote,
    Invoice,
    PaymentReceived,
    SequenceCounter,
    Settings,
    Transaction,
)
from services.vouchers import classify_cash_account

_DONE_MARKER_KEY = "voucher_backfill_done"


def backfill_vouchers(session: Session, tenant_id: int) -> None:
    """Infer, backfill, and renumber voucher types for a single tenant.

    Idempotent via a per-tenant done-marker stored in
    ``Settings(key="voucher_backfill_done", value="true")``.  Once the marker
    exists the function returns immediately, leaving all data untouched.  This
    ensures that live transactions posted after the initial migration (which
    also have ``legacy_jv_number IS NULL``) are never wrongly re-processed on
    a second call.
    """
    # ── 0. Done-marker guard ─────────────────────────────────────────────────
    done_row: Optional[Settings] = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id,
            Settings.key == _DONE_MARKER_KEY,
        )
    ).first()
    if done_row is not None and done_row.value == "true":
        return  # already completed; no-op regardless of new NULL rows
    # ── 1. Build {txn_id → vtype} from source back-refs ──────────────────────

    type_map: dict[int, str] = {}

    # Invoice sales transactions → SL
    for row in session.exec(
        select(Invoice.transaction_id).where(
            Invoice.tenant_id == tenant_id,
            Invoice.transaction_id != None,  # noqa: E711
        )
    ).all():
        type_map[row] = "SL"

    # Invoice COGS sub-JVs → JV
    for row in session.exec(
        select(Invoice.cogs_transaction_id).where(
            Invoice.tenant_id == tenant_id,
            Invoice.cogs_transaction_id != None,  # noqa: E711
        )
    ).all():
        type_map[row] = "JV"

    # Bills (purchase invoices) → PR
    for row in session.exec(
        select(Bill.transaction_id).where(
            Bill.tenant_id == tenant_id,
            Bill.transaction_id != None,  # noqa: E711
        )
    ).all():
        type_map[row] = "PR"

    # Payments received → CR or BR (depending on cash_account_id)
    for txn_id, cash_account_id in session.exec(
        select(PaymentReceived.transaction_id, PaymentReceived.cash_account_id).where(
            PaymentReceived.tenant_id == tenant_id,
            PaymentReceived.transaction_id != None,  # noqa: E711
        )
    ).all():
        kind = classify_cash_account(session, tenant_id, cash_account_id)
        type_map[txn_id] = "BR" if kind == "bank" else "CR"

    # Bill payments → BP or CP
    for txn_id, cash_account_id in session.exec(
        select(BillPayment.transaction_id, BillPayment.cash_account_id).where(
            BillPayment.tenant_id == tenant_id,
            BillPayment.transaction_id != None,  # noqa: E711
        )
    ).all():
        kind = classify_cash_account(session, tenant_id, cash_account_id)
        type_map[txn_id] = "BP" if kind == "bank" else "CP"

    # Credit notes → CN
    for row in session.exec(
        select(CreditNote.transaction_id).where(
            CreditNote.tenant_id == tenant_id,
            CreditNote.transaction_id != None,  # noqa: E711
        )
    ).all():
        type_map[row] = "CN"

    # Debit notes → DN
    for row in session.exec(
        select(DebitNote.transaction_id).where(
            DebitNote.tenant_id == tenant_id,
            DebitNote.transaction_id != None,  # noqa: E711
        )
    ).all():
        type_map[row] = "DN"

    # ── 2. Resolve reversals ─────────────────────────────────────────────────
    # A reversal txn's id appears as ``original.reversed_by_id``.
    # Collect all (original_id, reversal_id) pairs for the tenant.
    reversal_pairs = session.exec(
        select(Transaction.id, Transaction.reversed_by_id).where(
            Transaction.tenant_id == tenant_id,
            Transaction.reversed_by_id != None,  # noqa: E711
        )
    ).all()

    # Reversal inherits the ORIGINAL txn's inferred type.
    # We do two passes in case a reversal's original is itself a reversal (rare
    # but theoretically possible; one extra pass handles chains of length 2).
    for _pass in range(2):
        for original_id, reversal_id in reversal_pairs:
            if reversal_id not in type_map and original_id in type_map:
                type_map[reversal_id] = type_map[original_id]

    # ── 3. Identify rows to process (legacy_jv_number IS NULL) ───────────────
    to_process = session.exec(
        select(Transaction).where(
            Transaction.tenant_id == tenant_id,
            Transaction.legacy_jv_number == None,  # noqa: E711
        )
    ).all()

    if not to_process:
        # Nothing to backfill — write the done-marker anyway so future calls
        # are guarded by the outer check (not by the volatile NULL-row scan).
        if done_row is None:
            session.add(Settings(
                tenant_id=tenant_id,
                key=_DONE_MARKER_KEY,
                value="true",
            ))
        session.flush()
        return

    # ── 4. Pass A: temp-rename → store legacy; set voucher_type ──────────────
    for txn in to_process:
        vtype = type_map.get(txn.id, "JV")
        txn.legacy_jv_number = txn.jv_number
        txn.jv_number = f"__MIG__{txn.id}"
        txn.voucher_type = vtype
        session.add(txn)

    session.flush()  # writes all temp names; no UNIQUE collision possible

    # ── 5. Pass B: assign deterministic TYPE-NNNNNN numbers ──────────────────
    # Sort by (date, id) — canonical chronological order.
    sorted_txns = sorted(to_process, key=lambda t: (t.date, t.id))

    # Local per-type counter (starts from 1; NOT next_number so it's deterministic).
    counters: dict[str, int] = {}
    for txn in sorted_txns:
        vtype = txn.voucher_type
        counters[vtype] = counters.get(vtype, 0) + 1
        seq = counters[vtype]
        txn.jv_number = f"{vtype}-{seq:06d}"
        session.add(txn)

    session.flush()  # writes all final typed numbers

    # ── 6. Seed SequenceCounters ──────────────────────────────────────────────
    # For each type touched, set next_value = max_assigned_seq + 1.
    # Create the row if it doesn't exist; raise it if it already exists but is lower.
    for vtype, max_seq in counters.items():
        counter_name = f"voucher:{vtype}"
        row: Optional[SequenceCounter] = session.exec(
            select(SequenceCounter).where(
                SequenceCounter.tenant_id == tenant_id,
                SequenceCounter.name == counter_name,
            )
        ).first()
        desired_next = max_seq + 1
        if row is None:
            row = SequenceCounter(
                tenant_id=tenant_id,
                name=counter_name,
                next_value=desired_next,
            )
            session.add(row)
        else:
            if row.next_value < desired_next:
                row.next_value = desired_next
                session.add(row)

    session.flush()

    # ── 7. Write per-tenant done-marker ──────────────────────────────────────
    # Any subsequent call to backfill_vouchers() will see this row and return
    # immediately, preventing live post-migration transactions from being
    # wrongly re-processed.
    if done_row is None:
        session.add(Settings(
            tenant_id=tenant_id,
            key=_DONE_MARKER_KEY,
            value="true",
        ))
    else:
        done_row.value = "true"
        session.add(done_row)

    session.flush()
