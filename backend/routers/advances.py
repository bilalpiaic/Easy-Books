"""Customer & Vendor Advances (prepayments).

Record:
    Customer advance →  Dr Bank / Cr 2310 Customer Advances
    Vendor advance   →  Dr 1260 Advances to Vendors / Cr Bank
Apply (reuses the payments + PaymentAllocation machinery so invoice/bill
status derives automatically):
    Customer →  Dr 2310 / Cr 1100 AR     (via a PaymentReceived on account 2310)
    Vendor   →  Dr 2000 AP / Cr 1260      (via a BillPayment on account 1260)
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import (
    Account, Bill, BillPayment, CustomerAdvance, Customer, Invoice,
    PaymentAllocation, PaymentReceived, Vendor, VendorAdvance,
)
from routers.common import (
    SessionDep, WriteUserDep, get_or_create_account, log_audit, next_number,
)
from routers.payments import _refresh_bill_status, _refresh_invoice_status
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction

router = APIRouter(prefix="/api/advances", tags=["advances"])


# ── DTOs ──────────────────────────────────────────────────────────────────────

class AdvanceCreate(BaseModel):
    party_id: int                       # customer_id or vendor_id
    date: str
    amount: Decimal
    cash_account_id: Optional[int] = None
    notes: Optional[str] = None


class AdvanceApply(BaseModel):
    target_id: int                      # invoice_id or bill_id
    amount: Decimal


def _remaining(adv) -> Decimal:
    return D(adv.amount) - D(adv.applied_amount)


# ── Customer advances ─────────────────────────────────────────────────────────

@router.get("/customer")
def list_customer_advances(session: SessionDep, user: WriteUserDep):
    rows = session.exec(
        select(CustomerAdvance).where(CustomerAdvance.tenant_id == user.tenant_id)
        .order_by(CustomerAdvance.date.desc())
    ).all()
    return [{**a.model_dump(), "remaining": _remaining(a)} for a in rows]


@router.post("/customer", status_code=201)
def create_customer_advance(session: SessionDep, user: WriteUserDep, body: AdvanceCreate):
    amount = money(body.amount)
    if amount <= ZERO:
        raise HTTPException(400, "Amount must be > 0")
    cust = session.exec(
        select(Customer).where(Customer.id == body.party_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not cust:
        raise HTTPException(400, "Customer not found for this tenant")

    cash_acc = (
        session.exec(select(Account).where(
            Account.id == body.cash_account_id, Account.tenant_id == user.tenant_id)).first()
        if body.cash_account_id
        else get_or_create_account(session, user.tenant_id, "1010", "Bank", "Asset")
    )
    if not cash_acc:
        raise HTTPException(400, "Cash/bank account not found for this tenant")
    adv_acc = get_or_create_account(session, user.tenant_id, "2310", "Customer Advances", "Liability")

    number = next_number(session, user.tenant_id, "customer_advance", "CADV")
    txn = post_transaction(
        session, user, date=body.date,
        description=f"Customer advance {number} — {cust.name}",
        entries=[
            EntryInput(account_id=cash_acc.id, debit=amount),    # cash in
            EntryInput(account_id=adv_acc.id, credit=amount),    # liability up
        ],
        audit_entity_type="customer_advance",
        audit_detail={"number": number, "amount": str(amount)},
    )
    adv = CustomerAdvance(
        tenant_id=user.tenant_id, number=number, customer_id=cust.id, date=body.date,
        amount=amount, applied_amount=ZERO, cash_account_id=cash_acc.id,
        advance_account_id=adv_acc.id, transaction_id=txn.id, status="open",
        notes=body.notes,
    )
    session.add(adv)
    log_audit(session, user, "CREATE", "customer_advance", None, {"number": number})
    session.commit()
    session.refresh(adv)
    return adv


@router.post("/customer/{advance_id}/apply")
def apply_customer_advance(
    session: SessionDep, user: WriteUserDep, advance_id: int, body: AdvanceApply
):
    adv = session.exec(
        select(CustomerAdvance).where(
            CustomerAdvance.id == advance_id, CustomerAdvance.tenant_id == user.tenant_id)
    ).first()
    if not adv:
        raise HTTPException(404, "Advance not found")
    amount = money(body.amount)
    if amount <= ZERO:
        raise HTTPException(400, "Amount must be > 0")
    if amount > _remaining(adv):
        raise HTTPException(400, f"Amount exceeds remaining advance ({_remaining(adv)})")

    inv = session.exec(
        select(Invoice).where(Invoice.id == body.target_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not inv:
        raise HTTPException(400, "Invoice not found for this tenant")

    ar_acc = get_or_create_account(session, user.tenant_id, "1100", "Accounts Receivable", "Asset")
    # Apply: Dr 2310 Customer Advances / Cr 1100 AR (advance account is the "cash")
    txn = post_transaction(
        session, user, date=inv.issue_date,
        description=f"Apply advance {adv.number} to {inv.number}",
        entries=[
            EntryInput(account_id=adv.advance_account_id, debit=amount),
            EntryInput(account_id=ar_acc.id, credit=amount),
        ],
        audit_entity_type="payment_received",
        audit_detail={"advance": adv.number, "invoice": inv.number},
    )
    pmt = PaymentReceived(
        tenant_id=user.tenant_id, invoice_id=inv.id, customer_name=inv.customer_name,
        payment_date=inv.issue_date, amount=amount, method="advance",
        reference=adv.number, cash_account_id=adv.advance_account_id, transaction_id=txn.id,
    )
    session.add(pmt)
    session.flush()
    session.add(PaymentAllocation(
        tenant_id=user.tenant_id, payment_received_id=pmt.id, invoice_id=inv.id, amount=amount,
    ))
    session.flush()
    _refresh_invoice_status(session, inv)

    adv.applied_amount = money(D(adv.applied_amount) + amount)
    adv.status = "applied" if _remaining(adv) <= ZERO else "partial"
    session.add(adv)
    log_audit(session, user, "UPDATE", "customer_advance", adv.id,
              {"applied": str(amount), "invoice": inv.number})
    session.commit()
    session.refresh(adv)
    return {"advance": adv.model_dump(), "remaining": _remaining(adv), "invoice_status": inv.status}


# ── Vendor advances ───────────────────────────────────────────────────────────

@router.get("/vendor")
def list_vendor_advances(session: SessionDep, user: WriteUserDep):
    rows = session.exec(
        select(VendorAdvance).where(VendorAdvance.tenant_id == user.tenant_id)
        .order_by(VendorAdvance.date.desc())
    ).all()
    return [{**a.model_dump(), "remaining": _remaining(a)} for a in rows]


@router.post("/vendor", status_code=201)
def create_vendor_advance(session: SessionDep, user: WriteUserDep, body: AdvanceCreate):
    amount = money(body.amount)
    if amount <= ZERO:
        raise HTTPException(400, "Amount must be > 0")
    vendor = session.exec(
        select(Vendor).where(Vendor.id == body.party_id, Vendor.tenant_id == user.tenant_id)
    ).first()
    if not vendor:
        raise HTTPException(400, "Vendor not found for this tenant")

    cash_acc = (
        session.exec(select(Account).where(
            Account.id == body.cash_account_id, Account.tenant_id == user.tenant_id)).first()
        if body.cash_account_id
        else get_or_create_account(session, user.tenant_id, "1010", "Bank", "Asset")
    )
    if not cash_acc:
        raise HTTPException(400, "Cash/bank account not found for this tenant")
    adv_acc = get_or_create_account(session, user.tenant_id, "1260", "Advances to Vendors", "Asset")

    number = next_number(session, user.tenant_id, "vendor_advance", "VADV")
    txn = post_transaction(
        session, user, date=body.date,
        description=f"Vendor advance {number} — {vendor.name}",
        entries=[
            EntryInput(account_id=adv_acc.id, debit=amount),     # asset up (prepayment)
            EntryInput(account_id=cash_acc.id, credit=amount),   # cash out
        ],
        audit_entity_type="vendor_advance",
        audit_detail={"number": number, "amount": str(amount)},
    )
    adv = VendorAdvance(
        tenant_id=user.tenant_id, number=number, vendor_id=vendor.id, date=body.date,
        amount=amount, applied_amount=ZERO, cash_account_id=cash_acc.id,
        advance_account_id=adv_acc.id, transaction_id=txn.id, status="open",
        notes=body.notes,
    )
    session.add(adv)
    log_audit(session, user, "CREATE", "vendor_advance", None, {"number": number})
    session.commit()
    session.refresh(adv)
    return adv


@router.post("/vendor/{advance_id}/apply")
def apply_vendor_advance(
    session: SessionDep, user: WriteUserDep, advance_id: int, body: AdvanceApply
):
    adv = session.exec(
        select(VendorAdvance).where(
            VendorAdvance.id == advance_id, VendorAdvance.tenant_id == user.tenant_id)
    ).first()
    if not adv:
        raise HTTPException(404, "Advance not found")
    amount = money(body.amount)
    if amount <= ZERO:
        raise HTTPException(400, "Amount must be > 0")
    if amount > _remaining(adv):
        raise HTTPException(400, f"Amount exceeds remaining advance ({_remaining(adv)})")

    bill = session.exec(
        select(Bill).where(Bill.id == body.target_id, Bill.tenant_id == user.tenant_id)
    ).first()
    if not bill:
        raise HTTPException(400, "Bill not found for this tenant")

    ap_acc = get_or_create_account(session, user.tenant_id, "2000", "Accounts Payable", "Liability")
    # Apply: Dr 2000 AP / Cr 1260 Advances to Vendors (advance account is the "cash")
    txn = post_transaction(
        session, user, date=bill.bill_date,
        description=f"Apply advance {adv.number} to {bill.number}",
        entries=[
            EntryInput(account_id=ap_acc.id, debit=amount),
            EntryInput(account_id=adv.advance_account_id, credit=amount),
        ],
        audit_entity_type="bill_payment",
        audit_detail={"advance": adv.number, "bill": bill.number},
    )
    pmt = BillPayment(
        tenant_id=user.tenant_id, bill_id=bill.id, vendor_name=bill.vendor_name,
        payment_date=bill.bill_date, amount=amount, method="advance",
        reference=adv.number, cash_account_id=adv.advance_account_id, transaction_id=txn.id,
    )
    session.add(pmt)
    session.flush()
    session.add(PaymentAllocation(
        tenant_id=user.tenant_id, bill_payment_id=pmt.id, bill_id=bill.id, amount=amount,
    ))
    session.flush()
    _refresh_bill_status(session, bill)

    adv.applied_amount = money(D(adv.applied_amount) + amount)
    adv.status = "applied" if _remaining(adv) <= ZERO else "partial"
    session.add(adv)
    log_audit(session, user, "UPDATE", "vendor_advance", adv.id,
              {"applied": str(amount), "bill": bill.number})
    session.commit()
    session.refresh(adv)
    return {"advance": adv.model_dump(), "remaining": _remaining(adv), "bill_status": bill.status}
