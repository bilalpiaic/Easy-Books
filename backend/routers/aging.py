"""AR / AP aging buckets.

Shared between Invoices and Bills since both follow the same 0-30/31-60/61-90/90+
classification. The bucketing logic lives here rather than in either router.
"""
from datetime import date as DateType
from decimal import Decimal

from fastapi import APIRouter
from sqlmodel import select

from models import Bill, Invoice
from services.money import D, ZERO

from .common import CurrentUserDep, SessionDep

router = APIRouter(tags=["aging"])


def _aging_buckets(items: list, date_field: str, amount_field: str, name_field: str) -> dict:
    today = DateType.today()
    buckets = {
        "current": ZERO, "1_30": ZERO, "31_60": ZERO, "61_90": ZERO, "over_90": ZERO,
        "items": [],
    }
    for item in items:
        if getattr(item, "status", None) == "paid":
            continue
        due = DateType.fromisoformat(getattr(item, date_field))
        days_past = (today - due).days
        amount = D(getattr(item, amount_field))
        if days_past <= 0:
            buckets["current"] += amount; bucket = "current"
        elif days_past <= 30:
            buckets["1_30"] += amount; bucket = "1-30"
        elif days_past <= 60:
            buckets["31_60"] += amount; bucket = "31-60"
        elif days_past <= 90:
            buckets["61_90"] += amount; bucket = "61-90"
        else:
            buckets["over_90"] += amount; bucket = "90+"
        buckets["items"].append({
            "id": item.id,
            "name": getattr(item, name_field) or "—",
            "number": getattr(item, "number", ""),
            "due_date": getattr(item, date_field),
            "amount": amount,
            "days_past": max(0, days_past),
            "bucket": bucket,
        })
    return buckets


@router.get("/api/invoices/aging")
def invoice_aging(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(Invoice).where(Invoice.tenant_id == user.tenant_id)
    ).all()
    return _aging_buckets(items, "due_date", "total", "customer_name")


@router.get("/api/bills/aging")
def bill_aging(session: SessionDep, user: CurrentUserDep):
    items = session.exec(select(Bill).where(Bill.tenant_id == user.tenant_id)).all()
    return _aging_buckets(items, "due_date", "total", "vendor_name")
