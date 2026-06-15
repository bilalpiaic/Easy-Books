"""
Central GL posting service.

Every journal-affecting endpoint (invoice, bill, payment, manual JV, reversal,
period close) MUST route through `post_transaction` in this module. The service
owns the four book-keeping invariants in one place:

  1.  Σdebit == Σcredit (exact Decimal equality — no float tolerance)
  2.  No entry has both debit AND credit non-zero (single-sided rule)
  3.  No entry has both debit AND credit zero (no empty rows)
  4.  txn.date does NOT fall inside any locked AccountingPeriod

Before this service existed, those checks were either missing entirely from
the auto-posting endpoints (invoices/bills/payments bypassed period-lock) or
applied with float-tolerance (≤0.01) that masked accumulated drift.

The service does not commit — the caller's outer business transaction does.
That keeps the JE write atomic with whatever document (Invoice/Bill/etc) is
being created in the same request.
"""
from __future__ import annotations

import json as _json
from dataclasses import dataclass
from datetime import date as DateType
from decimal import Decimal
from typing import Iterable, Optional, Sequence

from fastapi import HTTPException
from sqlmodel import Session, select

from models import AccountingPeriod, Account, AuditLog, JournalEntry, Transaction, User
from services.accounts import assert_account_postable
from services.money import D, ZERO
from services.vouchers import voucher_number


@dataclass(frozen=True)
class EntryInput:
    """One side of a journal entry. Exactly one of debit / credit must be > 0."""
    account_id: int
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    analytic_account_id: Optional[int] = None
    customer_id: Optional[int] = None
    vendor_id: Optional[int] = None

    def normalised(self) -> "EntryInput":
        return EntryInput(
            account_id=self.account_id,
            debit=D(self.debit),
            credit=D(self.credit),
            analytic_account_id=self.analytic_account_id,
            customer_id=self.customer_id,
            vendor_id=self.vendor_id,
        )


class PostingError(HTTPException):
    """HTTP 400 surfaced from book-keeping invariant failures."""

    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)


def _validate_entries(entries: Sequence[EntryInput]) -> tuple[Decimal, Decimal]:
    if len(entries) < 2:
        raise PostingError("A journal voucher requires at least 2 entries (one debit, one credit).")

    total_dr = ZERO
    total_cr = ZERO
    for e in entries:
        if e.debit < 0 or e.credit < 0:
            raise PostingError(f"Negative amounts are not allowed (account {e.account_id}).")
        if e.debit > 0 and e.credit > 0:
            raise PostingError(f"Entry on account {e.account_id} has both debit and credit; use two rows instead.")
        if e.debit == 0 and e.credit == 0:
            raise PostingError(f"Entry on account {e.account_id} has zero amounts.")
        total_dr += e.debit
        total_cr += e.credit

    if total_dr != total_cr:
        raise PostingError(
            f"Journal not balanced: debit total {total_dr} ≠ credit total {total_cr}."
        )

    return total_dr, total_cr


def _check_period_locked(session: Session, tenant_id: int, when: str | DateType) -> None:
    when_str = when.isoformat() if isinstance(when, DateType) else str(when)
    locked = session.exec(
        select(AccountingPeriod).where(
            AccountingPeriod.tenant_id == tenant_id,
            AccountingPeriod.is_locked == True,  # noqa: E712
            AccountingPeriod.period_start <= when_str,
            AccountingPeriod.period_end >= when_str,
        )
    ).all()
    if locked:
        p = locked[0]
        raise PostingError(
            f"Date {when_str} falls in a locked accounting period: {p.name or p.period_start}."
        )


def _check_accounts_belong_to_tenant(
    session: Session, tenant_id: int, account_ids: Iterable[int]
) -> None:
    ids = list({int(i) for i in account_ids})
    accounts = session.exec(
        select(Account).where(Account.id.in_(ids), Account.tenant_id == tenant_id)
    ).all()
    if len(accounts) != len(ids):
        raise PostingError("One or more entries reference an account not in your tenant.")
    # Enforce posting control: only active, non-group, leaf accounts may be posted to.
    for account in accounts:
        assert_account_postable(session, tenant_id, account)


def post_transaction(
    session: Session,
    user: User,
    *,
    date: str,
    description: str,
    entries: Sequence[EntryInput],
    reference: Optional[str] = None,
    party: Optional[str] = None,
    payment_method: Optional[str] = None,
    notes: Optional[str] = None,
    audit_detail: Optional[dict] = None,
    audit_entity_type: str = "transaction",
    voucher_type: str = "JV",
) -> Transaction:
    """
    Create a Transaction header plus its journal entries, atomically with the caller's session.

    Returns the persisted Transaction. The caller is responsible for the final commit.
    """
    norm = [e.normalised() for e in entries]
    _validate_entries(norm)
    _check_period_locked(session, user.tenant_id, date)
    _check_accounts_belong_to_tenant(session, user.tenant_id, (e.account_id for e in norm))

    txn = Transaction(
        tenant_id=user.tenant_id,
        jv_number="__TMP__",
        voucher_type=voucher_type,
        date=date,
        description=description,
        reference=reference,
        party=party,
        payment_method=payment_method,
        notes=notes,
        created_by_id=user.id,
    )
    session.add(txn)
    session.flush()
    txn.jv_number = voucher_number(session, user.tenant_id, voucher_type)
    session.add(txn)

    for e in norm:
        session.add(
            JournalEntry(
                tenant_id=user.tenant_id,
                transaction_id=txn.id,
                account_id=e.account_id,
                debit=e.debit,
                credit=e.credit,
                analytic_account_id=e.analytic_account_id,
                customer_id=e.customer_id,
                vendor_id=e.vendor_id,
            )
        )

    detail = {"jv_number": txn.jv_number, "date": date}
    if audit_detail:
        detail.update(audit_detail)
    session.add(
        AuditLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="CREATE",
            entity_type=audit_entity_type,
            entity_id=txn.id,
            detail=_json.dumps(detail),
        )
    )

    return txn
