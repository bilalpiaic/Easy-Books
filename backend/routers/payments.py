"""Customer payments received + vendor bill payments.

Payments support multi-invoice allocation: a single PaymentReceived can settle
several invoices via PaymentAllocation rows. The invoice's status flips to
'paid' only when the cumulative allocated amount meets or exceeds its total
(otherwise → 'partial'). Same logic applies to BillPayment ↔ Bill.
"""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import (
    Account, Bill, BillPayment, Invoice, PaymentAllocation, PaymentReceived,
)
from services.money import D, money
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, get_or_create_account

router = APIRouter(tags=["payments"])


# ── Customer payments ────────────────────────────────────────────────────────


class AllocationLine(BaseModel):
    invoice_id: Optional[int] = None
    bill_id: Optional[int] = None
    amount: Decimal


class PaymentReceivedCreate(BaseModel):
    invoice_id: Optional[int] = None  # legacy single-invoice shortcut
    customer_name: Optional[str] = None
    payment_date: str
    amount: Decimal
    method: str = "cash"
    reference: Optional[str] = None
    cash_account_id: Optional[int] = None
    allocations: List[AllocationLine] = []


def _refresh_invoice_status(session, inv: Invoice) -> None:
    """Re-derive invoice.status from sum(allocations) against invoice.total."""
    total_allocated = session.exec(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
            PaymentAllocation.invoice_id == inv.id
        )
    ).one()
    allocated = D(total_allocated)
    if allocated >= D(inv.total):
        inv.status = "paid"
    elif allocated > 0:
        inv.status = "partial"
    session.add(inv)


def _refresh_bill_status(session, bill: Bill) -> None:
    total_allocated = session.exec(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
            PaymentAllocation.bill_id == bill.id
        )
    ).one()
    allocated = D(total_allocated)
    if allocated >= D(bill.total):
        bill.status = "paid"
    elif allocated > 0:
        bill.status = "partial"
    session.add(bill)


@router.get("/api/payments-received")
def list_payments_received(
    session: SessionDep, user: CurrentUserDep, skip: int = 0, limit: int = 50
):
    q = select(PaymentReceived).where(PaymentReceived.tenant_id == user.tenant_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(PaymentReceived.payment_date.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


@router.post("/api/payments-received", status_code=201)
def create_payment_received(
    session: SessionDep, user: WriteUserDep, body: PaymentReceivedCreate
):
    amount = money(body.amount)
    cname = body.customer_name

    # Resolve allocations: either explicit body.allocations or the legacy
    # single-invoice shortcut (invoice_id + amount).
    allocations: List[AllocationLine] = list(body.allocations)
    if body.invoice_id and not allocations:
        allocations = [AllocationLine(invoice_id=body.invoice_id, amount=body.amount)]
    if allocations:
        total_alloc = sum((D(a.amount) for a in allocations), start=D(0))
        if total_alloc > D(body.amount):
            raise HTTPException(
                400, "Allocations exceed payment amount"
            )
    # Customer name fallback from first allocated invoice
    if allocations and not cname:
        inv = session.get(Invoice, allocations[0].invoice_id) if allocations[0].invoice_id else None
        if inv and inv.tenant_id == user.tenant_id:
            cname = inv.customer_name

    cash_acc = (
        session.get(Account, body.cash_account_id)
        if body.cash_account_id
        else get_or_create_account(session, user.tenant_id, "1000", "Cash in Hand", "Asset")
    )
    ar_acc = get_or_create_account(
        session, user.tenant_id, "1100", "Accounts Receivable", "Asset"
    )

    txn = post_transaction(
        session, user,
        date=body.payment_date,
        description=f"Payment received — {cname or ''} {body.reference or ''}".strip(),
        entries=[
            EntryInput(account_id=cash_acc.id, debit=amount),
            EntryInput(account_id=ar_acc.id, credit=amount),
        ],
        reference=body.reference,
        payment_method=body.method,
        audit_entity_type="payment_received",
        audit_detail={"amount": str(amount), "invoice_id": body.invoice_id},
    )

    pmt = PaymentReceived(
        tenant_id=user.tenant_id,
        invoice_id=body.invoice_id,
        customer_name=cname,
        payment_date=body.payment_date,
        amount=amount,
        method=body.method,
        reference=body.reference,
        cash_account_id=cash_acc.id,
        transaction_id=txn.id,
    )
    session.add(pmt)
    session.flush()

    # Persist allocations and refresh each invoice's derived status
    for a in allocations:
        if not a.invoice_id:
            continue
        inv = session.get(Invoice, a.invoice_id)
        if not inv or inv.tenant_id != user.tenant_id:
            raise HTTPException(400, f"Invoice {a.invoice_id} not found for tenant")
        session.add(
            PaymentAllocation(
                tenant_id=user.tenant_id,
                payment_received_id=pmt.id,
                invoice_id=inv.id,
                amount=money(a.amount),
            )
        )
        session.flush()
        _refresh_invoice_status(session, inv)

    session.commit()
    session.refresh(pmt)
    return pmt


# ── Vendor bill payments ─────────────────────────────────────────────────────


class BillPaymentCreate(BaseModel):
    bill_id: Optional[int] = None  # legacy single-bill shortcut
    vendor_name: Optional[str] = None
    payment_date: str
    amount: Decimal
    method: str = "cash"
    reference: Optional[str] = None
    cash_account_id: Optional[int] = None
    allocations: List[AllocationLine] = []


@router.get("/api/bill-payments")
def list_bill_payments(
    session: SessionDep, user: CurrentUserDep, skip: int = 0, limit: int = 50
):
    q = select(BillPayment).where(BillPayment.tenant_id == user.tenant_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(BillPayment.payment_date.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


@router.post("/api/bill-payments", status_code=201)
def create_bill_payment(
    session: SessionDep, user: WriteUserDep, body: BillPaymentCreate
):
    amount = money(body.amount)
    vname = body.vendor_name

    allocations: List[AllocationLine] = list(body.allocations)
    if body.bill_id and not allocations:
        allocations = [AllocationLine(bill_id=body.bill_id, amount=body.amount)]
    if allocations:
        total_alloc = sum((D(a.amount) for a in allocations), start=D(0))
        if total_alloc > D(body.amount):
            raise HTTPException(400, "Allocations exceed payment amount")
    if allocations and not vname:
        b0 = session.get(Bill, allocations[0].bill_id) if allocations[0].bill_id else None
        if b0 and b0.tenant_id == user.tenant_id:
            vname = b0.vendor_name

    cash_acc = (
        session.get(Account, body.cash_account_id)
        if body.cash_account_id
        else get_or_create_account(session, user.tenant_id, "1000", "Cash in Hand", "Asset")
    )
    ap_acc = get_or_create_account(
        session, user.tenant_id, "2000", "Accounts Payable", "Liability"
    )

    txn = post_transaction(
        session, user,
        date=body.payment_date,
        description=f"Bill payment — {vname or ''} {body.reference or ''}".strip(),
        entries=[
            EntryInput(account_id=ap_acc.id, debit=amount),
            EntryInput(account_id=cash_acc.id, credit=amount),
        ],
        reference=body.reference,
        payment_method=body.method,
        audit_entity_type="bill_payment",
        audit_detail={"amount": str(amount), "bill_id": body.bill_id},
    )

    bp = BillPayment(
        tenant_id=user.tenant_id,
        bill_id=body.bill_id,
        vendor_name=vname,
        payment_date=body.payment_date,
        amount=amount,
        method=body.method,
        reference=body.reference,
        cash_account_id=cash_acc.id,
        transaction_id=txn.id,
    )
    session.add(bp)
    session.flush()

    for a in allocations:
        if not a.bill_id:
            continue
        bill = session.get(Bill, a.bill_id)
        if not bill or bill.tenant_id != user.tenant_id:
            raise HTTPException(400, f"Bill {a.bill_id} not found for tenant")
        session.add(
            PaymentAllocation(
                tenant_id=user.tenant_id,
                bill_payment_id=bp.id,
                bill_id=bill.id,
                amount=money(a.amount),
            )
        )
        session.flush()
        _refresh_bill_status(session, bill)

    session.commit()
    session.refresh(bp)
    return bp
