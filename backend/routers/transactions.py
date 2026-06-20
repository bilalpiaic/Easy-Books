"""Manual JV creation, read, reverse.

Reversal is more than negating the journal entries — derived state (invoice
status, payment allocations, inventory layers, COGS sub-transactions) has to
unwind too. The `_unwind_*` helpers below do that based on which source
document points at the transaction being reversed.
"""
from datetime import date as DateType
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from models import (
    AllocationInput, Bill, BillLine, BillPayment, Invoice, InvoiceLine,
    PaymentAllocation, PaymentReceived, Product, Transaction,
    TransactionCreate, TransactionRead,
)
from services.inventory import reverse_consumption, reverse_purchase
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/transactions", tags=["transactions"], dependencies=[perm_dep("journal_entry")])

# Document-backed types must only originate from their dedicated routers (invoice, bill, credit_note, debit_note).
# CP/CR/BP/BR/JV/CO are all valid as manual GL postings via New Entry.
_DOCUMENT_BACKED_TYPES = {"SL", "PR", "CN", "DN", "SR", "PV"}


def _unwind_payment_received(session, user, pmt: PaymentReceived) -> None:
    """Drop allocations tied to this payment and recompute each invoice's
    derived status."""
    allocs = session.exec(
        select(PaymentAllocation).where(
            PaymentAllocation.payment_received_id == pmt.id
        )
    ).all()
    touched: list[int] = []
    for a in allocs:
        if a.invoice_id:
            touched.append(a.invoice_id)
        session.delete(a)
    session.flush()
    for inv_id in set(touched):
        inv = session.get(Invoice, inv_id)
        if not inv or inv.tenant_id != user.tenant_id:
            continue
        from sqlmodel import func as _func
        total_allocated = session.exec(
            select(_func.coalesce(_func.sum(PaymentAllocation.amount), 0))
            .where(PaymentAllocation.invoice_id == inv.id)
        ).one()
        allocated = D(total_allocated)
        if allocated >= D(inv.total):
            inv.status = "paid"
        elif allocated > 0:
            inv.status = "partial"
        else:
            inv.status = "sent"
        session.add(inv)


def _unwind_bill_payment(session, user, bp: BillPayment) -> None:
    allocs = session.exec(
        select(PaymentAllocation).where(
            PaymentAllocation.bill_payment_id == bp.id
        )
    ).all()
    touched: list[int] = []
    for a in allocs:
        if a.bill_id:
            touched.append(a.bill_id)
        session.delete(a)
    session.flush()
    for bid in set(touched):
        bill = session.get(Bill, bid)
        if not bill or bill.tenant_id != user.tenant_id:
            continue
        from sqlmodel import func as _func
        total_allocated = session.exec(
            select(_func.coalesce(_func.sum(PaymentAllocation.amount), 0))
            .where(PaymentAllocation.bill_id == bill.id)
        ).one()
        allocated = D(total_allocated)
        if allocated >= D(bill.total):
            bill.status = "paid"
        elif allocated > 0:
            bill.status = "partial"
        else:
            bill.status = "received"
        session.add(bill)


def _unwind_invoice(session, user, inv: Invoice) -> Optional[Transaction]:
    """Reverse stock side-effects of a sale and locate the matching COGS JV
    so the caller can reverse it too. Returns the COGS Transaction (or None
    if the invoice had no stock lines)."""
    lines = session.exec(
        select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)
    ).all()
    total_cogs = ZERO
    for line in lines:
        if not line.product_id:
            continue
        prod = session.get(Product, line.product_id)
        if not prod or prod.product_type != "stock":
            continue
        # Stock returns at the rate it was sold at (current avg_cost when
        # the line posted — we approximate using line qty × avg_cost now,
        # which matches what consume_stock charged).
        cogs_for_line = money(D(line.qty) * D(prod.avg_cost))
        reverse_consumption(
            session,
            tenant_id=user.tenant_id,
            product_id=prod.id,
            qty=D(line.qty),
            cogs_total=cogs_for_line,
        )
        total_cogs += cogs_for_line
    inv.status = "void"
    session.add(inv)
    # Locate the separate COGS JV by description prefix used at posting time.
    if total_cogs > 0:
        return session.exec(
            select(Transaction).where(
                Transaction.tenant_id == user.tenant_id,
                Transaction.description == f"COGS for {inv.number}",
                Transaction.is_reversed == False,  # noqa: E712
            )
        ).first()
    return None


def _unwind_bill(session, user, bill: Bill) -> None:
    """Reverse stock receipts created by this bill."""
    reverse_purchase(session, tenant_id=user.tenant_id, source_doc=bill.number)
    bill.status = "void"
    session.add(bill)


from sqlmodel import func as _func


def _apply_allocations(
    session,
    user,
    txn: Transaction,
    allocs: list[AllocationInput],
    date: str,
) -> None:
    """After posting a CR/BR/CP/BP JV, create PaymentReceived/BillPayment +
    PaymentAllocation records and refresh each document's derived status."""
    from routers.payments import _refresh_invoice_status, _refresh_bill_status

    invoice_allocs = [a for a in allocs if a.invoice_id and (a.amount or 0) > 0]
    bill_allocs    = [a for a in allocs if a.bill_id    and (a.amount or 0) > 0]

    if invoice_allocs:
        total = sum(a.amount for a in invoice_allocs)
        pmt = PaymentReceived(
            tenant_id=user.tenant_id,
            transaction_id=txn.id,
            payment_date=date,
            amount=total,
            created_by_id=user.id,
        )
        session.add(pmt)
        session.flush()
        for a in invoice_allocs:
            inv = session.get(Invoice, a.invoice_id)
            if not inv or inv.tenant_id != user.tenant_id:
                continue
            session.add(PaymentAllocation(
                tenant_id=user.tenant_id,
                payment_received_id=pmt.id,
                invoice_id=inv.id,
                amount=a.amount,
            ))
            session.flush()
            _refresh_invoice_status(session, inv)

    if bill_allocs:
        total = sum(a.amount for a in bill_allocs)
        bp = BillPayment(
            tenant_id=user.tenant_id,
            transaction_id=txn.id,
            payment_date=date,
            amount=total,
            created_by_id=user.id,
        )
        session.add(bp)
        session.flush()
        for a in bill_allocs:
            bill = session.get(Bill, a.bill_id)
            if not bill or bill.tenant_id != user.tenant_id:
                continue
            session.add(PaymentAllocation(
                tenant_id=user.tenant_id,
                bill_payment_id=bp.id,
                bill_id=bill.id,
                amount=a.amount,
            ))
            session.flush()
            _refresh_bill_status(session, bill)


@router.post("")
def create_transaction(
    session: SessionDep, user: WriteUserDep, tx_data: TransactionCreate
):
    vt = (tx_data.voucher_type or "JV").upper()
    if vt in _DOCUMENT_BACKED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Voucher type '{vt}' cannot be created via the journal entry form. "
                f"Use the dedicated invoice / bill / credit note / debit note module instead."
            ),
        )
    txn = post_transaction(
        session, user,
        date=tx_data.date,
        description=tx_data.description or "",
        entries=[
            EntryInput(
                account_id=e.account_id,
                debit=D(e.debit),
                credit=D(e.credit),
                analytic_account_id=tx_data.analytic_account_id,
                customer_id=tx_data.customer_id,
                vendor_id=tx_data.vendor_id,
            )
            for e in tx_data.entries
        ],
        reference=tx_data.reference,
        party=tx_data.party,
        payment_method=tx_data.payment_method,
        notes=tx_data.notes,
        voucher_type=vt,
        audit_entity_type="transaction",
    )
    if tx_data.allocations:
        _apply_allocations(session, user, txn, tx_data.allocations, tx_data.date)
    session.commit()
    return {"id": txn.id, "jv_number": txn.jv_number}


def _reverse_one(session, user, txn: Transaction) -> Transaction:
    """Post the mirror JV for a single transaction and mark it reversed.
    Does NOT unwind derived state — the caller does that.
    The reversal inherits the original transaction's voucher_type."""
    rev = post_transaction(
        session, user,
        date=str(DateType.today()),
        description=f"Reversal of {txn.jv_number}",
        entries=[
            EntryInput(account_id=je.account_id, debit=D(je.credit), credit=D(je.debit))
            for je in txn.journal_entries
        ],
        audit_entity_type="transaction",
        audit_detail={"original_jv": txn.jv_number},
        voucher_type=txn.voucher_type,
    )
    txn.is_reversed = True
    txn.reversed_by_id = rev.id
    session.add(txn)
    return rev


@router.post("/{transaction_id}/reverse")
def reverse_transaction(
    session: SessionDep, user: WriteUserDep, transaction_id: int
):
    """Reverse a transaction AND unwind any derived state pointing at it.

    Looks up Invoice / Bill / PaymentReceived / BillPayment by their
    `transaction_id` foreign key. For each source found, an unwind helper
    rolls back the side effects: allocations, status flags, inventory.

    For an invoice with stock lines, the separate COGS sub-JV is also
    reversed automatically so cost-of-goods and revenue come off together.
    """
    txn = session.exec(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.tenant_id == user.tenant_id
        )
    ).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.is_reversed:
        raise HTTPException(400, "Transaction already reversed")

    # Find the source document(s). At most one of these should match per JV;
    # we check all because manual JVs match none.
    inv = session.exec(
        select(Invoice).where(Invoice.transaction_id == txn.id)
    ).first()
    bill = session.exec(
        select(Bill).where(Bill.transaction_id == txn.id)
    ).first()
    pmt = session.exec(
        select(PaymentReceived).where(PaymentReceived.transaction_id == txn.id)
    ).first()
    bp = session.exec(
        select(BillPayment).where(BillPayment.transaction_id == txn.id)
    ).first()

    rev_txn = _reverse_one(session, user, txn)
    cogs_rev_txn = None

    if pmt:
        _unwind_payment_received(session, user, pmt)
    elif bp:
        _unwind_bill_payment(session, user, bp)
    elif inv:
        cogs_txn = _unwind_invoice(session, user, inv)
        if cogs_txn is not None:
            cogs_rev_txn = _reverse_one(session, user, cogs_txn)
    elif bill:
        _unwind_bill(session, user, bill)

    log_audit(
        session, user, "REVERSE", "transaction", txn.id,
        {"original_jv": txn.jv_number, "reversal_jv": rev_txn.jv_number},
    )
    session.commit()
    session.refresh(rev_txn)
    out = {"reversal_jv_number": rev_txn.jv_number, "reversal_id": rev_txn.id}
    if cogs_rev_txn:
        out["cogs_reversal_jv_number"] = cogs_rev_txn.jv_number
    return out


@router.get("/{transaction_id}")
def get_transaction(transaction_id: int, session: SessionDep, user: CurrentUserDep):
    """Returns the transaction header + entries + back-references to any
    source documents (invoice/bill/payment/etc.) that posted this txn."""
    tx = session.exec(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.tenant_id == user.tenant_id
        )
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    entries = [
        {
            "account_id": je.account_id,
            "account_name": je.account.name,
            "account_type": je.account.type,
            "debit": je.debit,
            "credit": je.credit,
            "customer_id": je.customer_id,
            "vendor_id": je.vendor_id,
        }
        for je in tx.journal_entries
    ]

    # Resolve back-references: a transaction can be the booking of an
    # invoice, bill, payment-received, bill-payment, GRN, or a manual JV.
    # Multiple may point at the same txn (e.g. an invoice + its COGS sub-JV
    # share none, but reversal txns link back via reversed_by_id).
    source_docs: list[dict] = []

    inv = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == user.tenant_id, Invoice.transaction_id == tx.id
        )
    ).first()
    if inv:
        source_docs.append({"type": "invoice", "id": inv.id, "number": inv.number})

    bill = session.exec(
        select(Bill).where(
            Bill.tenant_id == user.tenant_id, Bill.transaction_id == tx.id
        )
    ).first()
    if bill:
        source_docs.append({"type": "bill", "id": bill.id, "number": bill.number})

    pmt = session.exec(
        select(PaymentReceived).where(
            PaymentReceived.tenant_id == user.tenant_id, PaymentReceived.transaction_id == tx.id
        )
    ).first()
    if pmt:
        source_docs.append({"type": "payment_received", "id": pmt.id, "number": f"REC-{pmt.id:05d}"})

    bp = session.exec(
        select(BillPayment).where(
            BillPayment.tenant_id == user.tenant_id, BillPayment.transaction_id == tx.id
        )
    ).first()
    if bp:
        source_docs.append({"type": "bill_payment", "id": bp.id, "number": f"PAY-{bp.id:05d}"})

    # GRN reverse-lookup (custodial memo JE)
    from models import GoodsReceiptNote
    grn = session.exec(
        select(GoodsReceiptNote).where(
            GoodsReceiptNote.tenant_id == user.tenant_id,
            GoodsReceiptNote.transaction_id == tx.id,
        )
    ).first()
    if grn:
        source_docs.append({"type": "grn", "id": grn.id, "number": grn.number})

    return {
        "id": tx.id,
        "jv_number": tx.jv_number,
        "voucher_type": tx.voucher_type,
        "date": tx.date,
        "description": tx.description,
        "reference": tx.reference,
        "party": tx.party,
        "payment_method": tx.payment_method,
        "notes": tx.notes,
        "is_reversed": tx.is_reversed,
        "reversed_by_id": tx.reversed_by_id,
        "entries": entries,
        "source_docs": source_docs,
    }
