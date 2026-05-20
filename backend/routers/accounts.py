"""Chart of accounts CRUD."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import Account, JournalEntry

from .common import CurrentUserDep, SessionDep, log_audit

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    code: str
    name: str
    type: str
    parent_id: Optional[int] = None


class AccountUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    parent_id: Optional[int] = None


@router.post("")
def create_account(session: SessionDep, user: CurrentUserDep, data: AccountCreate):
    existing = session.exec(
        select(Account).where(
            Account.tenant_id == user.tenant_id, Account.code == data.code
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account code {data.code} already exists")
    account = Account(
        code=data.code, name=data.name, type=data.type,
        parent_id=data.parent_id, tenant_id=user.tenant_id,
    )
    session.add(account)
    session.flush()
    log_audit(
        session, user, "CREATE", "account", account.id,
        {"code": account.code, "name": account.name},
    )
    session.commit()
    session.refresh(account)
    return account


@router.put("/{account_id}")
def update_account(
    account_id: int, session: SessionDep, user: CurrentUserDep, data: AccountUpdate
):
    account = session.exec(
        select(Account).where(
            Account.id == account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    for field in ("code", "name", "type", "parent_id"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(account, field, val)
    session.add(account)
    log_audit(
        session, user, "UPDATE", "account", account.id,
        {"code": account.code, "name": account.name},
    )
    session.commit()
    session.refresh(account)
    return account


@router.delete("/{account_id}")
def delete_account(account_id: int, session: SessionDep, user: CurrentUserDep):
    account = session.exec(
        select(Account).where(
            Account.id == account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if session.exec(select(JournalEntry).where(JournalEntry.account_id == account_id)).first():
        raise HTTPException(
            status_code=400, detail="Cannot delete account with existing journal entries"
        )
    log_audit(
        session, user, "DELETE", "account", account.id,
        {"code": account.code, "name": account.name},
    )
    session.delete(account)
    session.commit()
    return {"success": True}


@router.get("")
def list_accounts(
    session: SessionDep, user: CurrentUserDep,
    search: Optional[str] = None, skip: int = 0, limit: int = 200,
):
    q = select(Account).where(Account.tenant_id == user.tenant_id)
    if search:
        q = q.where(
            (Account.name.ilike(f"%{search}%")) | (Account.code.ilike(f"%{search}%"))
        )
    total = len(session.exec(q).all())
    results = session.exec(q.order_by(Account.code).offset(skip).limit(limit)).all()
    return {"total": total, "items": [r.model_dump() for r in results]}
