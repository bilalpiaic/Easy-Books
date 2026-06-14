"""Bank account CRUD with derived balance."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from models import Account, BankAccount, JournalEntry
from services.money import D, ZERO

from .common import CurrentUserDep, SessionDep, WriteUserDep
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/bank-accounts", tags=["bank-accounts"], dependencies=[perm_dep("bank_accounts")])


class BankAccountCreate(BaseModel):
    name: str
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    coa_account_id: Optional[int] = None


class BankAccountUpdate(BaseModel):
    name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    coa_account_id: Optional[int] = None
    is_active: Optional[bool] = None


def _bank_balance(session: Session, tenant_id: int, coa_id: int) -> Decimal:
    acc = session.get(Account, coa_id)
    if not acc:
        return ZERO
    entries = session.exec(
        select(JournalEntry).where(
            JournalEntry.account_id == coa_id, JournalEntry.tenant_id == tenant_id
        )
    ).all()
    if acc.type in ("Asset", "Expense"):
        return sum((D(e.debit) - D(e.credit) for e in entries), ZERO)
    return sum((D(e.credit) - D(e.debit) for e in entries), ZERO)


@router.get("")
def list_bank_accounts(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(BankAccount).where(BankAccount.tenant_id == user.tenant_id)
    ).all()
    return [
        {
            **ba.model_dump(),
            "balance": _bank_balance(session, user.tenant_id, ba.coa_account_id)
            if ba.coa_account_id
            else ZERO,
        }
        for ba in rows
    ]


@router.post("", status_code=201)
def create_bank_account(
    session: SessionDep, user: WriteUserDep, body: BankAccountCreate
):
    ba = BankAccount(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(ba)
    session.commit()
    session.refresh(ba)
    return ba


@router.put("/{ba_id}")
def update_bank_account(
    session: SessionDep, user: WriteUserDep, ba_id: int, body: BankAccountUpdate
):
    ba = session.exec(
        select(BankAccount).where(
            BankAccount.id == ba_id, BankAccount.tenant_id == user.tenant_id
        )
    ).first()
    if not ba:
        raise HTTPException(404, "Bank account not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ba, k, v)
    session.add(ba)
    session.commit()
    session.refresh(ba)
    return ba


@router.delete("/{ba_id}", status_code=204)
def delete_bank_account(session: SessionDep, user: WriteUserDep, ba_id: int):
    ba = session.exec(
        select(BankAccount).where(
            BankAccount.id == ba_id, BankAccount.tenant_id == user.tenant_id
        )
    ).first()
    if not ba:
        raise HTTPException(404, "Bank account not found")
    session.delete(ba)
    session.commit()
