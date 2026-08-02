"""Apply Stripe Checkout (or simulated) portal payments to the GL (#270).

Idempotent on PaymentReceived.reference = `stripe:<checkout_session_id>`.
Creates PaymentReceived + PaymentAllocation and posts Dr Bank / Cr AR.
"""
from __future__ import annotations

from datetime import date as DateType
from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session, func, select

from models import (
    Account, Customer, Invoice, PaymentAllocation, PaymentReceived, User,
)
from services.events import emit
from services.money import D, ZERO, money
from services.payment_fx import build_settlement, resolve_invoice_allocs
from services.posting import post_transaction
from services.vouchers import classify_cash_account


def stripe_payment_ref(checkout_session_id: str) -> str:
    return f"stripe:{checkout_session_id}"


def _tenant_actor(session: Session, tenant_id: int) -> User:
    user = session.exec(
        select(User).where(
            User.tenant_id == tenant_id,
            User.is_active == True,  # noqa: E712
            User.role.in_(("owner", "admin")),  # type: ignore
        ).order_by(User.id)  # type: ignore
    ).first()
    if not user:
        user = session.exec(
            select(User).where(
                User.tenant_id == tenant_id,
                User.is_active == True,  # noqa: E712
            ).order_by(User.id)  # type: ignore
        ).first()
    if not user:
        raise ValueError(f"No active user for tenant {tenant_id}")
    return user


def _invoice_balance(session: Session, inv: Invoice) -> Decimal:
    allocated = session.exec(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
            PaymentAllocation.invoice_id == inv.id
        )
    ).one()
    return max(D(inv.total) - D(allocated), ZERO)


def _refresh_invoice_status(session: Session, inv: Invoice) -> None:
    old = inv.status
    bal = _invoice_balance(session, inv)
    if bal <= ZERO and D(inv.total) > ZERO:
        inv.status = "paid"
    elif bal < D(inv.total):
        inv.status = "partial"
    session.add(inv)
    if inv.status == "paid" and old != "paid":
        emit(session, inv.tenant_id, "invoice.paid", {
            "invoice_id": inv.id, "number": inv.number,
            "customer_name": inv.customer_name, "total": str(inv.total),
        })


def _default_bank_account(session: Session, tenant_id: int) -> Account:
    for code, name in (("1010", "Bank"), ("1000", "Cash in Hand")):
        acc = session.exec(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.code == code,
            )
        ).first()
        if acc:
            return acc
    acc = session.exec(
        select(Account).where(
            Account.tenant_id == tenant_id,
            Account.type == "Asset",
            Account.is_group == False,  # noqa: E712
        ).order_by(Account.id)  # type: ignore
    ).first()
    if not acc:
        raise ValueError("No cash/bank account available for portal payment")
    return acc


def apply_checkout_payment(
    session: Session,
    *,
    tenant_id: int,
    invoice_id: int,
    checkout_session_id: str,
    amount: Optional[Decimal] = None,
    payment_date: Optional[str] = None,
    currency: Optional[str] = None,
) -> dict[str, Any]:
    """Post portal Stripe payment. Safe to call twice with the same session id.

    Returns {applied, payment_id, invoice_id, invoice_status, payment_link_status}.
    """
    ref = stripe_payment_ref(checkout_session_id)
    existing = session.exec(
        select(PaymentReceived).where(
            PaymentReceived.tenant_id == tenant_id,
            PaymentReceived.reference == ref,
        )
    ).first()
    if existing:
        inv = session.get(Invoice, invoice_id)
        return {
            "applied": False,
            "payment_id": existing.id,
            "invoice_id": invoice_id,
            "invoice_status": inv.status if inv else None,
            "payment_link_status": inv.payment_link_status if inv else None,
            "reason": "duplicate",
        }

    inv = session.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != tenant_id:
        raise ValueError("Invoice not found for tenant")

    balance = _invoice_balance(session, inv)
    if balance <= ZERO:
        inv.payment_link_status = "paid"
        session.add(inv)
        return {
            "applied": False,
            "payment_id": None,
            "invoice_id": inv.id,
            "invoice_status": inv.status,
            "payment_link_status": inv.payment_link_status,
            "reason": "already_paid",
        }

    pay_amt = money(amount) if amount is not None else balance
    if pay_amt <= ZERO:
        raise ValueError("Payment amount must be positive")
    if pay_amt > balance:
        pay_amt = balance

    actor = _tenant_actor(session, tenant_id)
    cash = _default_bank_account(session, tenant_id)
    pay_date = payment_date or DateType.today().isoformat()

    resolved = resolve_invoice_allocs(session, tenant_id, [(inv.id, pay_amt)])
    plan = build_settlement(
        session,
        tenant_id=tenant_id,
        side="receipt",
        payment_amount=pay_amt,
        payment_date=pay_date,
        cash_account_id=cash.id,
        currency=currency or inv.currency,
        exchange_rate=None,
        allocs=resolved,
        analytic_account_id=None,
        party_customer_id=inv.customer_id,
    )
    receipt_type = (
        "BR" if classify_cash_account(session, tenant_id, cash.id) == "bank" else "CR"
    )
    txn = post_transaction(
        session, actor,
        date=pay_date,
        description=f"Portal payment — {inv.number} ({checkout_session_id[:12]})",
        entries=plan.entries,
        reference=ref,
        payment_method="stripe",
        audit_entity_type="payment_received",
        audit_detail={
            "amount": str(pay_amt),
            "invoice_id": inv.id,
            "stripe_session": checkout_session_id,
            "source": "portal",
        },
        voucher_type=receipt_type,
    )

    cust_name = inv.customer_name
    if inv.customer_id:
        cust = session.get(Customer, inv.customer_id)
        if cust:
            cust_name = cust.name

    pmt = PaymentReceived(
        tenant_id=tenant_id,
        invoice_id=inv.id,
        customer_name=cust_name,
        payment_date=pay_date,
        amount=pay_amt,
        currency=plan.currency,
        exchange_rate=plan.settlement_rate,
        method="stripe",
        reference=ref,
        cash_account_id=cash.id,
        transaction_id=txn.id,
        created_by_id=actor.id,
    )
    session.add(pmt)
    session.flush()
    session.add(PaymentAllocation(
        tenant_id=tenant_id,
        payment_received_id=pmt.id,
        invoice_id=inv.id,
        amount=pay_amt,
    ))
    session.flush()
    _refresh_invoice_status(session, inv)
    inv.payment_link_status = "paid" if inv.status == "paid" else inv.payment_link_status or "paid"
    if inv.status == "paid":
        inv.payment_link_status = "paid"
    session.add(inv)
    emit(session, tenant_id, "payment.received", {
        "payment_id": pmt.id, "customer_name": cust_name,
        "amount": str(pay_amt), "payment_date": pay_date, "method": "stripe",
        "source": "portal",
    })
    return {
        "applied": True,
        "payment_id": pmt.id,
        "invoice_id": inv.id,
        "invoice_status": inv.status,
        "payment_link_status": inv.payment_link_status,
        "reason": "created",
    }
