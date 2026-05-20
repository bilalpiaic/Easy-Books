"""Customer payments received + vendor bill payments."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, Bill, BillPayment, Invoice, PaymentReceived
from services.money import money
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, get_or_create_account

router = APIRouter(tags=["payments"])


# ── Customer payments ────────────────────────────────────────────────────────


class PaymentReceivedCreate(BaseModel):
    invoice_id: Optional[int] = None
    customer_name: Optional[str] = None
    payment_date: str
    amount: Decimal
    method: str = "cash"
    reference: Optional[str] = None
    cash_account_id: Optional[int] = None


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
    if body.invoice_id:
        inv = session.get(Invoice, body.invoice_id)
        if inv and inv.tenant_id == user.tenant_id:
            if not cname:
                cname = inv.customer_name
            inv.status = "paid"
            session.add(inv)

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
    session.commit()
    session.refresh(pmt)
    return pmt


# ── Vendor bill payments ─────────────────────────────────────────────────────


class BillPaymentCreate(BaseModel):
    bill_id: Optional[int] = None
    vendor_name: Optional[str] = None
    payment_date: str
    amount: Decimal
    method: str = "cash"
    reference: Optional[str] = None
    cash_account_id: Optional[int] = None


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
    if body.bill_id:
        b = session.get(Bill, body.bill_id)
        if b and b.tenant_id == user.tenant_id:
            if not vname:
                vname = b.vendor_name
            b.status = "paid"
            session.add(b)

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
    session.commit()
    session.refresh(bp)
    return bp
