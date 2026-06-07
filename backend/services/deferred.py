"""Deferred-revenue origination (#47): classify deferred invoice lines, split
the revenue credit between Sales Revenue and Deferred Revenue (2300), and
manage the per-line DeferredRevenueSchedule lifecycle. Shared by create_invoice
and update_invoice so the two paths cannot diverge.

GST is never deferred — only net line revenue is parked in 2300. Recognition
itself is unchanged: the existing /api/deferred-revenue/run-recognition engine
posts Dr 2300 / Cr Revenue over each schedule's window.
"""
import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from models import Account, DeferredRevenueSchedule, Product
from services.money import D, ZERO, money


def _add_months(date_str: str, months: int) -> str:
    """Advance a YYYY-MM-DD date by `months` months, clamping to month end."""
    d = date.fromisoformat(date_str)
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()
