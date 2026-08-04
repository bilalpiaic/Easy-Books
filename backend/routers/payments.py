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
    Account, Bill, BillPayment, Customer, Invoice, PaymentAllocation, PaymentReceived, TaxCode, Vendor,
)
from services.events import emit
from services.money import D, ONE, ZERO, money
from services.posting import EntryInput, post_transaction
from services.vouchers import classify_cash_account

from services.permissions import perm_dep, apply_own_filter
from .common import CurrentUserDep, SessionDep, WriteUserDep, get_or_create_account

router = APIRouter(tags=["payments"])


def resolve_wht_amount(
    session,
    *,
    tenant_id: int,
    vendor_id: Optional[int],
    payment_amount: Decimal,
    explicit_wht: Optional[Decimal] = None,
    explicit_rate: Optional[Decimal] = None,
) -> Decimal:
    """Compute WHT to withhold from a bill payment (gross AP amount)."""
    if explicit_wht is not None:
        wht = money(explicit_wht)
        if wht < ZERO:
            raise HTTPException(400, "wht_amount cannot be negative")
        if wht > money(payment_amount):
            raise HTTPException(400, "wht_amount cannot exceed payment amount")
        return wht

    rate: Optional[Decimal] = None
    if explicit_rate is not None:
        rate = D(explicit_rate)
    elif vendor_id is not None:
        vend = session.exec(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id)
        ).first()
        if vend:
            if vend.wht_rate is not None:
                rate = D(vend.wht_rate)
            elif vend.wht_tax_code_id:
                tc = session.exec(
                    select(TaxCode).where(
                        TaxCode.id == vend.wht_tax_code_id,
                        TaxCode.tenant_id == tenant_id,
                    )
                ).first()
                if tc:
                    rate = D(tc.rate)

    if rate is None or rate <= ZERO:
        return ZERO
    wht = money(D(payment_amount) * rate / D("100"))
    if wht > money(payment_amount):
        raise HTTPException(400, "Computed WHT exceeds payment amount")
    return wht


def apply_wht_split(
    session,
    *,
    tenant_id: int,
    entries: list,
    wht_amount: Decimal,
    cash_account_id: int,
    vendor_id: Optional[int] = None,
) -> list:
    """Rewrite settlement entries: Cr Bank net, Cr 2265 WHT payable."""
    wht = money(wht_amount)
    if wht <= ZERO:
        return list(entries)

    wht_acc = get_or_create_account(
        session, tenant_id, "2265", "Withholding Tax Payable", "Liability"
    )
    new_entries: list = []
    cash_reduced = False
    for e in entries:
        if (
            not cash_reduced
            and e.account_id == cash_account_id
            and D(e.credit) > ZERO
        ):
            new_credit = money(D(e.credit) - wht)
            if new_credit < ZERO:
                raise HTTPException(400, "WHT exceeds cash credit leg")
            if new_credit > ZERO:
                new_entries.append(
                    EntryInput(
                        account_id=e.account_id,
                        debit=e.debit,
                        credit=new_credit,
                        analytic_account_id=e.analytic_account_id,
                        analytic_2_id=e.analytic_2_id,
                        analytic_3_id=e.analytic_3_id,
                        customer_id=e.customer_id,
                        vendor_id=e.vendor_id,
                    )
                )
            cash_reduced = True
        else:
            new_entries.append(e)
    if not cash_reduced:
        raise HTTPException(400, "Could not apply WHT: cash credit leg missing")
    new_entries.append(
        EntryInput(
            account_id=wht_acc.id,
            credit=wht,
            vendor_id=vendor_id,
        )
    )
    return new_entries


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
    analytic_2_id: Optional[int] = None
    analytic_3_id: Optional[int] = None
    analytic_ids: Optional[List[int]] = None


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
            "currency": inv.currency if inv else None,
            "carrying_rate": (
                float(inv.carrying_rate if inv and inv.carrying_rate is not None else inv.exchange_rate)
                if inv else None
            ),
        }
        for a, inv in rows
    ]
    settle_rate = D(pay.exchange_rate) if pay.exchange_rate is not None else ONE
    cash_base = money(D(pay.amount) * settle_rate)
    cleared_base = money(sum(
        (
            D(a["amount"]) * D(str(a["carrying_rate"] or 1))
            for a in allocations
            if a.get("carrying_rate") is not None
        ),
        start=ZERO,
    )) if allocations else cash_base
    realised = money(cash_base - cleared_base) if allocations else ZERO
    return {
        **pay.model_dump(),
        "allocations": allocations,
        "cash_base": cash_base,
        "cleared_base": cleared_base,
        "realised_fx": realised,
        "is_fx": bool(pay.currency and pay.exchange_rate is not None and D(pay.exchange_rate) != ONE),
    }


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
        analytic_account_id=body.analytic_account_id, analytic_2_id=body.analytic_2_id, analytic_3_id=body.analytic_3_id, analytic_ids=body.analytic_ids,
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
        analytic_account_id=body.analytic_account_id, analytic_2_id=body.analytic_2_id, analytic_3_id=body.analytic_3_id,
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
    return {
        **pmt.model_dump(),
        "realised_fx": plan.realised,
        "cash_base": plan.cash_base,
        "cleared_base": plan.cleared_base,
        "is_fx": plan.is_fx,
    }


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
    analytic_2_id: Optional[int] = None
    analytic_3_id: Optional[int] = None
    analytic_ids: Optional[List[int]] = None
    wht_amount: Optional[Decimal] = None  # explicit override; else from vendor rate
    wht_rate: Optional[Decimal] = None    # explicit rate % override


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
            "currency": bill.currency if bill else None,
            "carrying_rate": (
                float(bill.carrying_rate if bill and bill.carrying_rate is not None else bill.exchange_rate)
                if bill else None
            ),
        }
        for a, bill in rows
    ]
    settle_rate = D(pay.exchange_rate) if pay.exchange_rate is not None else ONE
    cash_base = money(D(pay.amount) * settle_rate)
    cleared_base = money(sum(
        (
            D(a["amount"]) * D(str(a["carrying_rate"] or 1))
            for a in allocations
            if a.get("carrying_rate") is not None
        ),
        start=ZERO,
    )) if allocations else cash_base
    realised = money(cash_base - cleared_base) if allocations else ZERO
    return {
        **pay.model_dump(),
        "allocations": allocations,
        "cash_base": cash_base,
        "cleared_base": cleared_base,
        "realised_fx": realised,
        "is_fx": bool(pay.currency and pay.exchange_rate is not None and D(pay.exchange_rate) != ONE),
    }


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
    vendor_id = body.vendor_id

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
            if vendor_id is None and b0.vendor_id:
                vendor_id = b0.vendor_id

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
        analytic_account_id=body.analytic_account_id, analytic_2_id=body.analytic_2_id, analytic_3_id=body.analytic_3_id, analytic_ids=body.analytic_ids,
        party_vendor_id=vendor_id,
    )

    wht = resolve_wht_amount(
        session,
        tenant_id=user.tenant_id,
        vendor_id=vendor_id,
        payment_amount=amount,
        explicit_wht=body.wht_amount,
        explicit_rate=body.wht_rate,
    )
    entries = list(plan.entries)
    if wht > ZERO:
        if plan.is_fx:
            raise HTTPException(
                400,
                "Withholding tax is not supported on foreign-currency payments yet",
            )
        entries = apply_wht_split(
            session,
            tenant_id=user.tenant_id,
            entries=entries,
            wht_amount=wht,
            cash_account_id=cash_acc.id,
            vendor_id=vendor_id,
        )

    payment_type = (
        "BP" if classify_cash_account(session, user.tenant_id, cash_acc.id) == "bank"
        else "CP"
    )
    txn = post_transaction(
        session, user,
        date=body.payment_date,
        description=f"Bill payment — {vname or ''} {body.reference or ''}".strip(),
        entries=entries,
        reference=body.reference,
        payment_method=body.method,
        audit_entity_type="bill_payment",
        audit_detail={
            "amount": str(amount),
            "wht_amount": str(wht),
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
        vendor_id=vendor_id,
        vendor_name=vname,
        payment_date=body.payment_date,
        amount=amount,
        wht_amount=wht,
        currency=plan.currency,
        exchange_rate=plan.settlement_rate,
        method=body.method,
        reference=body.reference,
        cash_account_id=cash_acc.id,
        transaction_id=txn.id,
        created_by_id=user.id,
        analytic_account_id=body.analytic_account_id, analytic_2_id=body.analytic_2_id, analytic_3_id=body.analytic_3_id,
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
        "amount": str(amount), "wht_amount": str(wht),
        "payment_date": body.payment_date,
        "method": body.method,
    })
    session.commit()
    session.refresh(bp)
    return {
        **bp.model_dump(),
        "realised_fx": plan.realised,
        "cash_base": plan.cash_base,
        "cleared_base": plan.cleared_base,
        "is_fx": plan.is_fx,
    }
