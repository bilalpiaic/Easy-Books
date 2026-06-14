"""Exchange rates CRUD."""
from decimal import Decimal
from typing import Optional

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
