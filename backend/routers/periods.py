"""Accounting periods: create, list, lock/unlock, delete."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import AccountingPeriod

from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/periods", tags=["periods"])


class PeriodCreate(BaseModel):
    name: Optional[str] = None
    period_start: str
    period_end: str


@router.get("")
def list_periods(session: SessionDep, user: CurrentUserDep):
    return session.exec(
        select(AccountingPeriod)
        .where(AccountingPeriod.tenant_id == user.tenant_id)
        .order_by(AccountingPeriod.period_start.desc())
    ).all()


@router.post("", status_code=201)
def create_period(session: SessionDep, user: WriteUserDep, body: PeriodCreate):
    p = AccountingPeriod(tenant_id=user.tenant_id, **body.model_dump())
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@router.patch("/{period_id}/lock")
def toggle_period_lock(
    session: SessionDep, user: WriteUserDep, period_id: int, is_locked: bool
):
    p = session.exec(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.tenant_id == user.tenant_id,
        )
    ).first()
    if not p:
        raise HTTPException(404, "Period not found")
    p.is_locked = is_locked
    session.add(p)
    session.commit()
    return p


@router.delete("/{period_id}", status_code=204)
def delete_period(session: SessionDep, user: WriteUserDep, period_id: int):
    p = session.exec(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.tenant_id == user.tenant_id,
        )
    ).first()
    if not p:
        raise HTTPException(404, "Period not found")
    session.delete(p)
    session.commit()
