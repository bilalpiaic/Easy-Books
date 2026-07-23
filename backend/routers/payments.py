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
    Account, Bill, BillPayment, Customer, Invoice, PaymentAllocation, PaymentReceived, Vendor,
)
from services.events import emit
from services.money import D, money
from services.posting import post_transaction
from services.vouchers import classify_cash_account

from services.permissions import perm_dep, apply_own_filter
from .common import CurrentUserDep, SessionDep, WriteUserDep, get_or_create_account

router = APIRouter(tags=["payments"])


# ── Customer payments ────────────────────────────────────────────────────────


class AllocationLine(BaseModel):
    invoice_id: Optional[int] = None
    bill_id: Optional[int] = None
    amount: Decimal


class PaymentReceivedCreate(BaseModel):
    invoice_id: Optional[int] = None  # legacy single-invoice shortcut
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    payment_date: str
    amount: Decimal
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    method: str = "cash"
    reference: Optional[str] = None
    cash_account_id: Optional[int] = None
    allocations: List[AllocationLine] = []
    analytic_account_id: Optional[int] = None


def _refresh_invoice_status(session, inv: Invoice) -> None:
    """Re-derive invoice.status from sum(allocations) against invoice.total."""
    old_status = inv.status
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
    if inv.status == "paid" and old_status != "paid":
        emit(session, inv.tenant_id, "invoice.paid", {
            "invoice_id": inv.id, "number": inv.number,
            "customer_name": inv.customer_name, "total": str(inv.total),
        })


def _refresh_bill_status(session, bill: Bill) -> None:
    old_status = bill.status
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
    if bill.status == "paid" and old_status != "paid":
        emit(session, bill.tenant_id, "bill.paid", {
            "bill_id": bill.id, "number": bill.number,
            "vendor_name": bill.vendor_name, "total": str(bill.total),
        })


@router.get("/api/payments-received", dependencies=[perm_dep("payments_received")])
def list_payments_received(
    session: SessionDep, user: CurrentUserDep, skip: int = 0, limit: int = 50
):
    q = select(PaymentReceived).where(PaymentReceived.tenant_id == user.tenant_id)
    q = apply_own_filter(q, PaymentReceived, user, session)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(PaymentReceived.payment_date.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


@router.get("/api/payments-received/{payment_id}", dependencies=[perm_dep("payments_received")])
def get_payment_received(
    session: SessionDep, user: CurrentUserDep, payment_id: int
):
    """Single payment with its allocations (joined to invoice numbers)."""
    pay = session.exec(
        select(PaymentReceived).where(
            PaymentReceived.id == payment_id,
            PaymentReceived.tenant_id == user.tenant_id,
        )
    ).first()
    if not pay:
        from fastapi import HTTPException
        raise HTTPException(404, "Payment not found")
    rows = session.exec(
        select(PaymentAllocation, Invoice)
        .join(Invoice, Invoice.id == PaymentAllocation.invoice_id, isouter=True)
        .where(
            PaymentAllocation.tenant_id == user.tenant_id,
            PaymentAllocation.payment_received_id == pay.id,
        )
    ).all()
    allocations = [
        {
            "id": a.id,
            "invoice_id": a.invoice_id,
            "invoice_number": inv.number if inv else None,
            "amount": a.amount,
        }
        for a, inv in rows
    ]
    return {**pay.model_dump(), "allocations": allocations}


@router.post("/api/payments-received", status_code=201, dependencies=[perm_dep("payments_received", "edit")])
def create_payment_received(
    session: SessionDep, user: WriteUserDep, body: PaymentReceivedCreate
):
    from services.payment_fx import build_settlement, resolve_invoice_allocs

    amount = money(body.amount)
    cname = body.customer_name

    if body.customer_id is not None:
        cust = session.exec(
            select(Customer).where(
                Customer.id == body.customer_id,
                Customer.tenant_id == user.tenant_id,
            )
        ).first()
        if not cust:
            raise HTTPException(404, "Customer not found")
        cname = cust.name

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

    alloc_pairs = [
        (a.invoice_id, a.amount)
        for a in allocations
        if a.invoice_id
    ]
    # Validate invoices exist before building settlement (also used for FX currency)
    resolved = resolve_invoice_allocs(session, user.tenant_id, alloc_pairs) if alloc_pairs else []

    plan = build_settlement(
        session,
        tenant_id=user.tenant_id,
        side="receipt",
        payment_amount=amount,
        payment_date=body.payment_date,
        cash_account_id=cash_acc.id,
        currency=body.currency,
        exchange_rate=body.exchange_rate,
        allocs=resolved,
        analytic_account_id=body.analytic_account_id,
        party_customer_id=body.customer_id,
    )

    receipt_type = (
        "BR" if classify_cash_account(session, user.tenant_id, cash_acc.id) == "bank"
        else "CR"
    )
    txn = post_transaction(
        session, user,
        date=body.payment_date,
        description=f"Payment received — {cname or ''} {body.reference or ''}".strip(),
        entries=plan.entries,
        reference=body.reference,
        payment_method=body.method,
        audit_entity_type="payment_received",
        audit_detail={
            "amount": str(amount),
            "invoice_id": body.invoice_id,
            "currency": plan.currency,
            "exchange_rate": str(plan.settlement_rate),
            "realised_fx": str(plan.realised),
        },
        voucher_type=receipt_type,
    )

    pmt = PaymentReceived(
        tenant_id=user.tenant_id,
        invoice_id=body.invoice_id,
        customer_name=cname,
        payment_date=body.payment_date,
        amount=amount,
        currency=plan.currency,
        exchange_rate=plan.settlement_rate,
        method=body.method,
        reference=body.reference,
        cash_account_id=cash_acc.id,
        transaction_id=txn.id,
        created_by_id=user.id,
        analytic_account_id=body.analytic_account_id,
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

    emit(session, user.tenant_id, "payment.received", {
        "payment_id": pmt.id, "customer_name": cname,
        "amount": str(amount), "payment_date": body.payment_date,
        "method": body.method,
    })
    session.commit()
    session.refresh(pmt)
    return pmt


# ── Vendor bill payments ─────────────────────────────────────────────────────


class BillPaymentCreate(BaseModel):
    bill_id: Optional[int] = None  # legacy single-bill shortcut
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    payment_date: str
    amount: Decimal
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    method: str = "cash"
    reference: Optional[str] = None
    cash_account_id: Optional[int] = None
    allocations: List[AllocationLine] = []
    analytic_account_id: Optional[int] = None


@router.get("/api/bill-payments/{payment_id}", dependencies=[perm_dep("bill_payments")])
def get_bill_payment(
    session: SessionDep, user: CurrentUserDep, payment_id: int
):
    """Single bill-payment with its allocations (joined to bill numbers)."""
    pay = session.exec(
        select(BillPayment).where(
            BillPayment.id == payment_id,
            BillPayment.tenant_id == user.tenant_id,
        )
    ).first()
    if not pay:
        from fastapi import HTTPException
        raise HTTPException(404, "Bill payment not found")
    rows = session.exec(
        select(PaymentAllocation, Bill)
        .join(Bill, Bill.id == PaymentAllocation.bill_id, isouter=True)
        .where(
            PaymentAllocation.tenant_id == user.tenant_id,
            PaymentAllocation.bill_payment_id == pay.id,
        )
    ).all()
    allocations = [
        {
            "id": a.id,
            "bill_id": a.bill_id,
            "bill_number": bill.number if bill else None,
            "amount": a.amount,
        }
        for a, bill in rows
    ]
    return {**pay.model_dump(), "allocations": allocations}


@router.get("/api/bill-payments", dependencies=[perm_dep("bill_payments")])
def list_bill_payments(
    session: SessionDep, user: CurrentUserDep, skip: int = 0, limit: int = 50
):
    q = select(BillPayment).where(BillPayment.tenant_id == user.tenant_id)
    q = apply_own_filter(q, BillPayment, user, session)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(BillPayment.payment_date.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


@router.post("/api/bill-payments", status_code=201, dependencies=[perm_dep("bill_payments", "edit")])
def create_bill_payment(
    session: SessionDep, user: WriteUserDep, body: BillPaymentCreate
):
    from services.payment_fx import build_settlement, resolve_bill_allocs

    amount = money(body.amount)
    vname = body.vendor_name

    if body.vendor_id is not None:
        vend = session.exec(
            select(Vendor).where(
                Vendor.id == body.vendor_id,
                Vendor.tenant_id == user.tenant_id,
            )
        ).first()
        if not vend:
            raise HTTPException(404, "Vendor not found")
        vname = vend.name

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

    alloc_pairs = [(a.bill_id, a.amount) for a in allocations if a.bill_id]
    resolved = resolve_bill_allocs(session, user.tenant_id, alloc_pairs) if alloc_pairs else []

    plan = build_settlement(
        session,
        tenant_id=user.tenant_id,
        side="bill_payment",
        payment_amount=amount,
        payment_date=body.payment_date,
        cash_account_id=cash_acc.id,
        currency=body.currency,
        exchange_rate=body.exchange_rate,
        allocs=resolved,
        analytic_account_id=body.analytic_account_id,
        party_vendor_id=body.vendor_id,
    )

    payment_type = (
        "BP" if classify_cash_account(session, user.tenant_id, cash_acc.id) == "bank"
        else "CP"
    )
    txn = post_transaction(
        session, user,
        date=body.payment_date,
        description=f"Bill payment — {vname or ''} {body.reference or ''}".strip(),
        entries=plan.entries,
        reference=body.reference,
        payment_method=body.method,
        audit_entity_type="bill_payment",
        audit_detail={
            "amount": str(amount),
            "bill_id": body.bill_id,
            "currency": plan.currency,
            "exchange_rate": str(plan.settlement_rate),
            "realised_fx": str(plan.realised),
        },
        voucher_type=payment_type,
    )

    bp = BillPayment(
        tenant_id=user.tenant_id,
        bill_id=body.bill_id,
        vendor_name=vname,
        payment_date=body.payment_date,
        amount=amount,
        currency=plan.currency,
        exchange_rate=plan.settlement_rate,
        method=body.method,
        reference=body.reference,
        cash_account_id=cash_acc.id,
        transaction_id=txn.id,
        created_by_id=user.id,
        analytic_account_id=body.analytic_account_id,
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

    emit(session, user.tenant_id, "payment.made", {
        "payment_id": bp.id, "vendor_name": vname,
        "amount": str(amount), "payment_date": body.payment_date,
        "method": body.method,
    })
    session.commit()
    session.refresh(bp)
    return bp
