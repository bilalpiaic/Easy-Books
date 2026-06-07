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


@dataclass
class LineDeferral:
    net_base: Decimal
    recognition_months: int
    revenue_account_id: int | None


@dataclass
class DeferralPlan:
    deferred_lines: list[LineDeferral] = field(default_factory=list)
    deferred_net_base: Decimal = ZERO


def plan_deferral(session: Session, tenant_id: int, lines, fx_rate: Decimal) -> DeferralPlan:
    """Classify lines by product.is_deferred. Returns the deferred per-line specs
    and their summed net (base currency). Lines with no product, or a
    non-deferred product, are ignored here (they stay as normal revenue)."""
    plan = DeferralPlan()
    for ln in lines:
        if not getattr(ln, "product_id", None):
            continue
        prod = session.exec(
            select(Product).where(
                Product.id == ln.product_id, Product.tenant_id == tenant_id
            )
        ).first()
        if not prod or not prod.is_deferred:
            continue
        net_base = money(D(ln.qty) * D(ln.rate) * D(fx_rate))
        # Deferral requires a positive amount. Zero/negative lines deliberately
        # fall through to immediate revenue: a negative-total schedule would
        # break the recognition engine (it divides total/months), and negative
        # invoice lines are not a supported flow here (credit memos use the
        # separate CreditNote entity, not negative invoice lines).
        if net_base <= ZERO:
            continue
        plan.deferred_lines.append(LineDeferral(
            net_base=net_base,
            recognition_months=max(1, int(prod.recognition_months or 0)),
            revenue_account_id=prod.revenue_account_id,
        ))
        plan.deferred_net_base = money(plan.deferred_net_base + net_base)
    return plan


def resolve_deferred_account(session: Session, tenant_id: int) -> Account:
    """Tenant's Deferred Revenue account: settings override → 2300 → auto-create."""
    from routers.common import get_default_account
    return get_default_account(
        session, tenant_id, "default_deferred_revenue_account",
        "2300", "Deferred Revenue", "Liability",
    )
