"""Accounting periods: create, list, lock/unlock, delete, period-end close."""
from datetime import date as DateType
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, AccountingPeriod, JournalEntry, Transaction
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, get_or_create_account, log_audit

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


@router.post("/{period_id}/close")
def close_period(session: SessionDep, user: WriteUserDep, period_id: int):
    """Period-end close: zero out Revenue/Expense into Retained Earnings,
    then lock the period.

    Posts one closing JV:
      Dr Revenue (sum of net credits on Revenue accts)
      Cr Expense (sum of net debits on Expense accts)
      Cr/Dr Retained Earnings for the difference (net income/loss)

    Idempotent in spirit: a second call on an already-locked period 400s.
    """
    p = session.exec(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.tenant_id == user.tenant_id,
        )
    ).first()
    if not p:
        raise HTTPException(404, "Period not found")
    if p.is_locked:
        raise HTTPException(400, "Period already closed/locked")

    # Aggregate net balance per income-statement account in [start, end]
    rows = session.exec(
        select(
            Account.id,
            Account.type,
            func.coalesce(func.sum(JournalEntry.debit), 0).label("dr"),
            func.coalesce(func.sum(JournalEntry.credit), 0).label("cr"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Transaction.date >= p.period_start,
            Transaction.date <= p.period_end,
            Account.type.in_(("Revenue", "Expense")),
        )
        .group_by(Account.id, Account.type)
    ).all()

    entries: list[EntryInput] = []
    net = ZERO  # positive = net income (credit to RE), negative = net loss
    for r in rows:
        dr = D(r.dr)
        cr = D(r.cr)
        if r.type == "Revenue":
            # Revenue normal balance is credit; close by Dr Revenue.
            amount = cr - dr
            if amount > 0:
                entries.append(EntryInput(account_id=r.id, debit=money(amount)))
                net += amount
        else:  # Expense
            # Expense normal balance is debit; close by Cr Expense.
            amount = dr - cr
            if amount > 0:
                entries.append(EntryInput(account_id=r.id, credit=money(amount)))
                net -= amount

    if entries:
        re_acc = get_or_create_account(
            session, user.tenant_id, "3100", "Retained Earnings", "Equity"
        )
        if net > 0:
            entries.append(EntryInput(account_id=re_acc.id, credit=money(net)))
        elif net < 0:
            entries.append(EntryInput(account_id=re_acc.id, debit=money(-net)))
        # else: zero — skip, no JV needed
        if net != 0:
            post_transaction(
                session, user,
                date=p.period_end,
                description=f"Period-end close: {p.period_start} → {p.period_end}",
                entries=entries,
                audit_entity_type="period",
                audit_detail={"period_id": p.id, "net_income": str(net)},
            )

    p.is_locked = True
    session.add(p)
    log_audit(session, user, "CLOSE", "period", p.id, {"net_income": str(net)})
    session.commit()
    session.refresh(p)
    return {"period": p, "net_income": str(net), "entries_posted": len(entries)}
