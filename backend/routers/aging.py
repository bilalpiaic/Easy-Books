"""AR / AP aging buckets.

Aging is computed against the *outstanding* balance (total minus any
PaymentAllocation rows), not the gross document total. A partially-paid
invoice ages on the remaining amount only — without this, a $1000 invoice
partly paid down to $200 would still show $1000 outstanding in the 30-day
bucket, which is wrong.
"""
from datetime import date as DateType
from decimal import Decimal
from typing import Iterable

from fastapi import APIRouter
from sqlmodel import func, select

from models import Bill, Invoice, PaymentAllocation
from services.money import D, ZERO

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
    }


@router.get("/api/invoices/aging")
def invoice_aging(session: SessionDep, user: CurrentUserDep):
    today = DateType.today()
    # Single query: gross total minus sum(allocations) per invoice.
    rows = session.exec(
        select(
            Invoice.id, Invoice.number, Invoice.customer_name,
            Invoice.customer_id,
            Invoice.due_date, Invoice.total, Invoice.status,
            func.coalesce(
                select(func.sum(PaymentAllocation.amount))
                .where(PaymentAllocation.invoice_id == Invoice.id)
                .correlate(Invoice).scalar_subquery(),
                0,
            ).label("allocated"),
        ).where(Invoice.tenant_id == user.tenant_id)
    ).all()
    buckets = _empty_buckets()
    for r in rows:
        outstanding = D(r.total) - D(r.allocated)
        if outstanding <= 0:
            continue  # fully paid (or over-paid)
        due = DateType.fromisoformat(r.due_date)
        days_past = (today - due).days
        key, label = _bucket_for(days_past)
        buckets[key] += outstanding
        buckets["items"].append({
            "id": r.id,
            "name": r.customer_name or "—",
            "number": r.number,
            "due_date": r.due_date,
            "amount": outstanding,
            "days_past": max(0, days_past),
            "bucket": label,
            "customer_id": r.customer_id,
        })
    return buckets


@router.get("/api/bills/aging")
def bill_aging(session: SessionDep, user: CurrentUserDep):
    today = DateType.today()
    rows = session.exec(
        select(
            Bill.id, Bill.number, Bill.vendor_name,
            Bill.vendor_id,
            Bill.due_date, Bill.total, Bill.status,
            func.coalesce(
                select(func.sum(PaymentAllocation.amount))
                .where(PaymentAllocation.bill_id == Bill.id)
                .correlate(Bill).scalar_subquery(),
                0,
            ).label("allocated"),
        ).where(Bill.tenant_id == user.tenant_id)
    ).all()
    buckets = _empty_buckets()
    for r in rows:
        outstanding = D(r.total) - D(r.allocated)
        if outstanding <= 0:
            continue
        due = DateType.fromisoformat(r.due_date)
        days_past = (today - due).days
        key, label = _bucket_for(days_past)
        buckets[key] += outstanding
        buckets["items"].append({
            "id": r.id,
            "name": r.vendor_name or "—",
            "number": r.number,
            "due_date": r.due_date,
            "amount": outstanding,
            "days_past": max(0, days_past),
            "bucket": label,
            "vendor_id": r.vendor_id,
        })
    return buckets
