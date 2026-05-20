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

    Identity (1) when from == base. Falls back to the most recent rate at or
    before `on_date`. Raises LookupError if no rate is available.
    """
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise LookupError(f"Tenant {tenant_id} not found")
    base = tenant.base_currency
    if from_currency == base:
        return ONE
    row = session.exec(
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
    if row is None:
        raise LookupError(
            f"No exchange rate for {from_currency}→{base} on or before {on_date}"
        )
    return D(row.rate)
