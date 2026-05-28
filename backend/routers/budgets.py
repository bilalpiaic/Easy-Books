"""Monthly account budgets + budget-vs-actual variance. IAS 1 management commentary."""
import calendar
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, Budget, JournalEntry, Transaction
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.money import D, ZERO

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


class BudgetCreate(BaseModel):
    account_id: int
    fiscal_year: int
    period_month: int
    amount: Decimal
    label: Optional[str] = None


@router.get("")
def list_budgets(
    session: SessionDep, user: WriteUserDep, year: Optional[int] = None
):
    q = select(Budget).where(Budget.tenant_id == user.tenant_id)
    if year:
        q = q.where(Budget.fiscal_year == year)
    return session.exec(q.order_by(Budget.fiscal_year, Budget.period_month)).all()


@router.post("", status_code=201)
def create_or_update_budget(session: SessionDep, user: WriteUserDep, body: BudgetCreate):
    if not (1 <= body.period_month <= 12):
        raise HTTPException(400, "period_month must be 1-12")
    if not (2000 <= body.fiscal_year <= 2100):
        raise HTTPException(400, "fiscal_year out of range")

    # Validate account belongs to tenant
    acc = session.exec(
        select(Account).where(
            Account.id == body.account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not acc:
        raise HTTPException(400, "Account not found for this tenant")

    # Upsert: update if already exists
    existing = session.exec(
        select(Budget).where(
            Budget.tenant_id == user.tenant_id,
            Budget.account_id == body.account_id,
            Budget.fiscal_year == body.fiscal_year,
            Budget.period_month == body.period_month,
        )
    ).first()
    if existing:
        existing.amount = D(str(body.amount))
        if body.label:
            existing.label = body.label
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    b = Budget(tenant_id=user.tenant_id, **body.model_dump())
    session.add(b)
    log_audit(session, user, "CREATE", "budget", None,
              {"account": acc.code, "year": body.fiscal_year, "month": body.period_month})
    session.commit()
    session.refresh(b)
    return b


@router.delete("/{budget_id}", status_code=204)
def delete_budget(session: SessionDep, user: WriteUserDep, budget_id: int):
    b = session.exec(
        select(Budget).where(Budget.id == budget_id, Budget.tenant_id == user.tenant_id)
    ).first()
    if not b:
        raise HTTPException(404)
    session.delete(b)
    session.commit()
