"""
Account-level helpers used by posting control and hierarchy validation.

JournalEntry.tenant_id exists directly on the table (inherited from
JournalEntryBase), so tenant-scoped postings counts query it directly without
needing a join to Transaction.
"""
from __future__ import annotations

from sqlmodel import Session, func, select

from models import Account, JournalEntry


def account_has_children(session: Session, tenant_id: int, account_id: int) -> bool:
    """Return True if any account in the tenant has parent_id == account_id."""
    count = session.exec(
        select(func.count()).select_from(Account).where(
            Account.tenant_id == tenant_id,
            Account.parent_id == account_id,
        )
    ).one()
    return count > 0


def account_has_postings(session: Session, tenant_id: int, account_id: int) -> bool:
    """Return True if any JournalEntry exists for this account in the tenant."""
    count = session.exec(
        select(func.count()).select_from(JournalEntry).where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.account_id == account_id,
        )
    ).one()
    return count > 0


def assert_account_postable(session: Session, tenant_id: int, account: Account) -> None:
    """Raise HTTP 400 if the account is not a valid posting target.

    An account is postable iff it is ALL of:
      - not a group/header account  (is_group == False)
      - active                       (is_active == True)
      - a leaf                       (no child accounts)
    """
    from fastapi import HTTPException

    if account.is_group:
        raise HTTPException(
            400,
            f"Cannot post to '{account.code} {account.name}' — it is a group/header account.",
        )
    if not account.is_active:
        raise HTTPException(
            400,
            f"Cannot post to '{account.code} {account.name}' — it is inactive.",
        )
    if account_has_children(session, tenant_id, account.id):
        raise HTTPException(
            400,
            f"Cannot post to '{account.code} {account.name}' — it has sub-accounts; "
            "post to a detail account.",
        )
