"""FX rate lookup.

Single source of truth: any code that needs to translate a document currency
to the tenant's base currency calls `rate_to_base()`. The lookup walks
backwards in time from the document date to the most recent ExchangeRate
row for the pair, so rates only need to be entered when they change rather
than every business day.
"""
from datetime import date as DateType
from decimal import Decimal

from sqlmodel import Session, select

from models import ExchangeRate, Tenant
from services.money import D, ONE


def rate_to_base(
    session: Session, tenant_id: int, from_currency: str, on_date: str
) -> Decimal:
    """Return the rate that converts `from_currency` → tenant base currency.

    Resolution order:
      1. Identity (1) when from == base.
      2. Direct row `from_currency → base` at or before `on_date`.
      3. Inverse row `base → from_currency` at or before `on_date`; the
         direct rate is 1 / inverse_rate. Saves having to enter both
         directions in the catalog.
    Raises LookupError if neither direction is available.
    """
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise LookupError(f"Tenant {tenant_id} not found")
    base = tenant.base_currency
    if from_currency == base:
        return ONE

    direct = session.exec(
        select(ExchangeRate)
        .where(
            ExchangeRate.tenant_id == tenant_id,
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == base,
            ExchangeRate.date <= on_date,
        )
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    ).first()
    if direct is not None:
        return D(direct.rate)

    inverse = session.exec(
        select(ExchangeRate)
        .where(
            ExchangeRate.tenant_id == tenant_id,
            ExchangeRate.from_currency == base,
            ExchangeRate.to_currency == from_currency,
            ExchangeRate.date <= on_date,
        )
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    ).first()
    if inverse is not None and D(inverse.rate) > 0:
        return ONE / D(inverse.rate)

    raise LookupError(
        f"No exchange rate for {from_currency}↔{base} on or before {on_date}"
    )
