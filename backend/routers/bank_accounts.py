"""Bank account CRUD with derived balance.

Each BankAccount links 1:1 to a postable Asset CoA leaf. When create omits
``coa_account_id``, a sibling leaf under Current Assets (parent of 1010) is
auto-created so Trial Balance, Bank Book, and balances stay consistent.
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from models import Account, BankAccount, JournalEntry
from services.accounts import account_has_children, suggest_next_code
from services.money import D, ZERO
from services.permissions import perm_dep

from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(
    prefix="/api/bank-accounts",
    tags=["bank-accounts"],
    dependencies=[perm_dep("bank_accounts")],
)


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


def _bank_coa_parent_id(session: Session, tenant_id: int) -> Optional[int]:
    """Parent for new bank leaves: parent of 1010, else Current Assets group 11."""
    bank = session.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == "1010")
    ).first()
    if bank and bank.parent_id is not None:
        return bank.parent_id
    ca = session.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == "11")
    ).first()
    return ca.id if ca else None


def _validate_coa_link(
    session: Session,
    tenant_id: int,
    coa_account_id: int,
    *,
    exclude_ba_id: Optional[int] = None,
) -> Account:
    """Ensure CoA link is a tenant Asset leaf and not already used by another bank."""
    acc = session.get(Account, coa_account_id)
    if not acc or acc.tenant_id != tenant_id:
        raise HTTPException(400, "Linked GL account not found")
    if acc.type != "Asset":
        raise HTTPException(400, "Linked GL account must be an Asset account")
    if not acc.is_active:
        raise HTTPException(400, "Linked GL account is inactive")
    if acc.is_group:
        raise HTTPException(400, "Linked GL account must be a postable leaf, not a group")
    if account_has_children(session, tenant_id, acc.id):
        raise HTTPException(400, "Linked GL account has sub-accounts; pick a detail leaf")

    q = select(BankAccount).where(
        BankAccount.tenant_id == tenant_id,
        BankAccount.coa_account_id == coa_account_id,
    )
    if exclude_ba_id is not None:
        q = q.where(BankAccount.id != exclude_ba_id)
    other = session.exec(q).first()
    if other:
        raise HTTPException(
            400,
            f"GL account '{acc.code} {acc.name}' is already linked to bank account "
            f"'{other.name}'. Each bank needs its own CoA leaf.",
        )
    return acc


def _auto_create_bank_leaf(session: Session, tenant_id: int, name: str) -> Account:
    """Create a dedicated Asset leaf under Current Assets for this bank."""
    parent_id = _bank_coa_parent_id(session, tenant_id)
    code = suggest_next_code(session, tenant_id, parent_id)
    leaf_name = name.strip() or "Bank Account"
    # Avoid duplicate name under the same parent
    dup_q = select(Account).where(
        Account.tenant_id == tenant_id,
        Account.name == leaf_name,
    )
    if parent_id is None:
        dup_q = dup_q.where(Account.parent_id.is_(None))
    else:
        dup_q = dup_q.where(Account.parent_id == parent_id)
    if session.exec(dup_q).first():
        leaf_name = f"{leaf_name} (Bank)"

    acc = Account(
        tenant_id=tenant_id,
        code=code,
        name=leaf_name,
        type="Asset",
        parent_id=parent_id,
        is_group=False,
        is_active=True,
    )
    session.add(acc)
    session.flush()
    return acc


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
    tid = user.tenant_id
    coa_id = body.coa_account_id
    if coa_id is not None:
        _validate_coa_link(session, tid, coa_id)
    else:
        leaf = _auto_create_bank_leaf(session, tid, body.name)
        coa_id = leaf.id

    ba = BankAccount(
        tenant_id=tid,
        name=body.name,
        bank_name=body.bank_name,
        account_number=body.account_number,
        coa_account_id=coa_id,
    )
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

    data = body.model_dump(exclude_none=True)
    if "coa_account_id" in data:
        _validate_coa_link(
            session, user.tenant_id, data["coa_account_id"], exclude_ba_id=ba.id
        )

    for k, v in data.items():
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
