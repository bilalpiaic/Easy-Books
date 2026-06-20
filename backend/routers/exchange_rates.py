"""Exchange rates CRUD + live rate proxy."""
from datetime import date as DateType
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import ExchangeRate
from services.money import D

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/exchange-rates", tags=["exchange-rates"], dependencies=[perm_dep("exchange_rates")])


class RateCreate(BaseModel):
    date: str
    from_currency: str
    to_currency: str
    rate: Decimal


@router.get("")
def list_rates(
    session: SessionDep, user: CurrentUserDep,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
    skip: int = 0, limit: int = 200,
):
    q = select(ExchangeRate).where(ExchangeRate.tenant_id == user.tenant_id)
    if from_currency:
        q = q.where(ExchangeRate.from_currency == from_currency)
    if to_currency:
        q = q.where(ExchangeRate.to_currency == to_currency)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(ExchangeRate.date.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


@router.post("", status_code=201)
def create_rate(
    session: SessionDep, user: WriteUserDep, body: RateCreate
):
    if D(body.rate) <= 0:
        raise HTTPException(400, "rate must be positive")
    # Upsert: if a row for (tenant, date, from, to) exists, replace its rate
    existing = session.exec(
        select(ExchangeRate).where(
            ExchangeRate.tenant_id == user.tenant_id,
            ExchangeRate.date == body.date,
            ExchangeRate.from_currency == body.from_currency,
            ExchangeRate.to_currency == body.to_currency,
        )
    ).first()
    if existing:
        existing.rate = D(body.rate)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    row = ExchangeRate(
        tenant_id=user.tenant_id,
        date=body.date,
        from_currency=body.from_currency,
        to_currency=body.to_currency,
        rate=D(body.rate),
    )
    session.add(row)
    session.flush()
    log_audit(
        session, user, "CREATE", "exchange_rate", row.id,
        {"pair": f"{body.from_currency}->{body.to_currency}", "date": body.date},
    )
    session.commit()
    session.refresh(row)
    return row


# Currencies covered by the ECB / Frankfurter reference set.
# Everything outside this set is fetched from ExchangeRate-API v4 instead.
_FRANKFURTER_CURRENCIES = {
    "AUD","BGN","BRL","CAD","CHF","CNY","CZK","DKK","EUR","GBP",
    "HKD","HUF","IDR","ILS","INR","ISK","JPY","KRW","MXN","MYR",
    "NOK","NZD","PHP","PLN","RON","SEK","SGD","THB","TRY","USD","ZAR",
}


def _fetch_frankfurter(from_currency: str, to_currency: str) -> dict:
    """ECB reference rates via Frankfurter. Raises ValueError if unavailable."""
    resp = httpx.get(
        "https://api.frankfurter.app/latest",
        params={"from": from_currency, "to": to_currency},
        timeout=8.0,
        follow_redirects=True,
    )
    if resp.status_code == 404:
        raise ValueError("not_in_frankfurter")
    resp.raise_for_status()
    data = resp.json()
    rate = data.get("rates", {}).get(to_currency)
    if rate is None:
        raise ValueError("not_in_frankfurter")
    return {"rate": float(rate), "date": data.get("date"), "source": "frankfurter.app (ECB)"}


def _fetch_exchangerate_api(from_currency: str, to_currency: str) -> dict:
    """ExchangeRate-API v4 — free, no key, 160+ currencies incl. PKR/AED/SAR/KWD."""
    resp = httpx.get(
        f"https://api.exchangerate-api.com/v4/latest/{from_currency}",
        timeout=8.0,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    rate = data.get("rates", {}).get(to_currency)
    if rate is None:
        raise ValueError(f"ExchangeRate-API does not publish a rate for {to_currency}")
    return {
        "rate": float(rate),
        "date": data.get("date", DateType.today().isoformat()),
        "source": "exchangerate-api.com",
    }


@router.get("/live")
def get_live_rate(
    from_currency: str,
    to_currency: str,
    user: CurrentUserDep,
):
    """Proxy a live FX rate.

    Primary source: Frankfurter (ECB reference rates, ~32 currencies).
    Fallback: ExchangeRate-API v4 (free, no key, 160+ currencies incl. PKR/AED/SAR/KWD/QAR).
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency == to_currency:
        return {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": 1.0,
            "date": DateType.today().isoformat(),
            "source": "identity",
        }

    # Choose source: use Frankfurter when both currencies are in its set,
    # otherwise go straight to ExchangeRate-API.
    use_frankfurter = (
        from_currency in _FRANKFURTER_CURRENCIES
        and to_currency in _FRANKFURTER_CURRENCIES
    )

    try:
        if use_frankfurter:
            try:
                result = _fetch_frankfurter(from_currency, to_currency)
            except ValueError:
                result = _fetch_exchangerate_api(from_currency, to_currency)
        else:
            result = _fetch_exchangerate_api(from_currency, to_currency)
    except httpx.RequestError:
        raise HTTPException(502, "Could not reach the FX rate service. Check internet connectivity.")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"FX rate service returned HTTP {exc.response.status_code}.")
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    return {
        "from_currency": from_currency,
        "to_currency": to_currency,
        **result,
    }


@router.delete("/{rate_id}", status_code=204)
def delete_rate(session: SessionDep, user: WriteUserDep, rate_id: int):
    row = session.exec(
        select(ExchangeRate).where(
            ExchangeRate.id == rate_id, ExchangeRate.tenant_id == user.tenant_id
        )
    ).first()
    if not row:
        raise HTTPException(404, "Rate not found")
    session.delete(row)
    session.commit()
