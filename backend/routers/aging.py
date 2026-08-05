"""AR / AP aging buckets.

Aging is computed against the *outstanding* balance (total minus any
PaymentAllocation rows), not the gross document total. A partially-paid
invoice ages on the remaining amount only — without this, a $1000 invoice
partly paid down to $200 would still show $1000 outstanding in the 30-day
bucket, which is wrong.

Multi-currency (#300): each item carries document currency + base-equivalent
outstanding (using carrying_rate ?? exchange_rate). Bucket totals sum base
amounts so mixed-currency tenants are not silently added in doc units.
"""
from datetime import date as DateType
from decimal import Decimal

from fastapi import APIRouter
from sqlmodel import func, select

from models import Bill, Invoice, PaymentAllocation, Tenant
from services.money import D, ONE, ZERO
from services.permissions import perm_dep

from .common import CurrentUserDep, SessionDep

router = APIRouter(tags=["aging"])


def _bucket_for(days_past: int) -> tuple[str, str]:
    if days_past <= 0:
        return "current", "current"
    if days_past <= 30:
        return "1_30", "1-30"
    if days_past <= 60:
        return "31_60", "31-60"
    if days_past <= 90:
        return "61_90", "61-90"
    return "over_90", "90+"


def _empty_buckets() -> dict:
    return {
        "current": ZERO, "1_30": ZERO, "31_60": ZERO,
        "61_90": ZERO, "over_90": ZERO, "items": [],
        "base_currency": None,
    }


def _doc_rate(exchange_rate, carrying_rate) -> Decimal:
    if carrying_rate is not None:
        r = D(carrying_rate)
        if r > ZERO:
            return r
    if exchange_rate is not None:
        r = D(exchange_rate)
        if r > ZERO:
            return r
    return ONE


@router.get("/api/invoices/aging", dependencies=[perm_dep("report.ar_aging")])
def invoice_aging(session: SessionDep, user: CurrentUserDep):
    today = DateType.today()
    tenant = session.get(Tenant, user.tenant_id)
    base_currency = tenant.base_currency if tenant else "USD"
    # Single query: gross total minus sum(allocations) per invoice.
    rows = session.exec(
        select(
            Invoice.id, Invoice.number, Invoice.customer_name,
            Invoice.customer_id,
            Invoice.due_date, Invoice.total, Invoice.status,
            Invoice.currency, Invoice.exchange_rate, Invoice.carrying_rate,
            func.coalesce(
                select(func.sum(PaymentAllocation.amount))
                .where(PaymentAllocation.invoice_id == Invoice.id)
                .correlate(Invoice).scalar_subquery(),
                0,
            ).label("allocated"),
        ).where(Invoice.tenant_id == user.tenant_id)
    ).all()
    buckets = _empty_buckets()
    buckets["base_currency"] = base_currency
    for r in rows:
        outstanding = D(r.total) - D(r.allocated)
        if outstanding <= 0:
            continue  # fully paid (or over-paid)
        rate = _doc_rate(r.exchange_rate, r.carrying_rate)
        amount_base = outstanding * rate
        due = DateType.fromisoformat(r.due_date)
        days_past = (today - due).days
        key, label = _bucket_for(days_past)
        buckets[key] += amount_base
        buckets["items"].append({
            "id": r.id,
            "name": r.customer_name or "—",
            "number": r.number,
            "due_date": r.due_date,
            "amount": outstanding,
            "amount_base": amount_base,
            "currency": r.currency or base_currency,
            "exchange_rate": rate,
            "days_past": max(0, days_past),
            "bucket": label,
            "customer_id": r.customer_id,
        })
    return buckets


@router.get("/api/bills/aging", dependencies=[perm_dep("report.ap_aging")])
def bill_aging(session: SessionDep, user: CurrentUserDep):
    today = DateType.today()
    tenant = session.get(Tenant, user.tenant_id)
    base_currency = tenant.base_currency if tenant else "USD"
    rows = session.exec(
        select(
            Bill.id, Bill.number, Bill.vendor_name,
            Bill.vendor_id,
            Bill.due_date, Bill.total, Bill.status,
            Bill.currency, Bill.exchange_rate, Bill.carrying_rate,
            func.coalesce(
                select(func.sum(PaymentAllocation.amount))
                .where(PaymentAllocation.bill_id == Bill.id)
                .correlate(Bill).scalar_subquery(),
                0,
            ).label("allocated"),
        ).where(Bill.tenant_id == user.tenant_id)
    ).all()
    buckets = _empty_buckets()
    buckets["base_currency"] = base_currency
    for r in rows:
        outstanding = D(r.total) - D(r.allocated)
        if outstanding <= 0:
            continue
        rate = _doc_rate(r.exchange_rate, r.carrying_rate)
        amount_base = outstanding * rate
        due = DateType.fromisoformat(r.due_date)
        days_past = (today - due).days
        key, label = _bucket_for(days_past)
        buckets[key] += amount_base
        buckets["items"].append({
            "id": r.id,
            "name": r.vendor_name or "—",
            "number": r.number,
            "due_date": r.due_date,
            "amount": outstanding,
            "amount_base": amount_base,
            "currency": r.currency or base_currency,
            "exchange_rate": rate,
            "days_past": max(0, days_past),
            "bucket": label,
            "vendor_id": r.vendor_id,
        })
    return buckets
