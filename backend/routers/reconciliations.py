"""Bank reconciliation: create period, toggle line matches, close."""
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    BankAccount, JournalEntry, Reconciliation, ReconciliationLine, Transaction,
)
from services.money import D, ZERO
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/reconciliations", tags=["reconciliations"], dependencies=[perm_dep("reconciliations")])


class ReconciliationCreate(BaseModel):
    bank_account_id: int
    period_start: str
    period_end: str
    statement_balance: Decimal


@router.get("")
def list_reconciliations(session: SessionDep, user: CurrentUserDep):
    recs = session.exec(
        select(Reconciliation)
        .where(Reconciliation.tenant_id == user.tenant_id)
        .order_by(Reconciliation.period_end.desc())
    ).all()
    out = []
    for r in recs:
        ba = session.get(BankAccount, r.bank_account_id)
        out.append({**r.model_dump(), "bank_account_name": ba.name if ba else "—"})
    return out


@router.post("", status_code=201)
def create_reconciliation(
    session: SessionDep, user: WriteUserDep, body: ReconciliationCreate
):
    ba = session.get(BankAccount, body.bank_account_id)
    if not ba or ba.tenant_id != user.tenant_id:
        raise HTTPException(404, "Bank account not found")
    rec = Reconciliation(
        tenant_id=user.tenant_id,
        bank_account_id=body.bank_account_id,
        period_start=body.period_start,
        period_end=body.period_end,
        statement_balance=body.statement_balance,
    )
    session.add(rec)
    session.flush()

    if ba.coa_account_id:
        entries = session.exec(
            select(JournalEntry)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                JournalEntry.account_id == ba.coa_account_id,
                JournalEntry.tenant_id == user.tenant_id,
                Transaction.date >= body.period_start,
                Transaction.date <= body.period_end,
            )
        ).all()
        for e in entries:
            session.add(
                ReconciliationLine(
                    reconciliation_id=rec.id, journal_entry_id=e.id, is_matched=False
                )
            )

    session.commit()
    session.refresh(rec)
    return rec


@router.get("/{rec_id}")
def get_reconciliation(session: SessionDep, user: CurrentUserDep, rec_id: int):
    rec = session.exec(
        select(Reconciliation).where(
            Reconciliation.id == rec_id, Reconciliation.tenant_id == user.tenant_id
        )
    ).first()
    if not rec:
        raise HTTPException(404, "Not found")
    lines = session.exec(
        select(ReconciliationLine).where(ReconciliationLine.reconciliation_id == rec_id)
    ).all()
    line_details = []
    for ln in lines:
        je = session.get(JournalEntry, ln.journal_entry_id)
        txn = session.get(Transaction, je.transaction_id) if je else None
        line_details.append({
            "id": ln.id,
            "journal_entry_id": ln.journal_entry_id,
            "is_matched": ln.is_matched,
            "debit": je.debit if je else 0,
            "credit": je.credit if je else 0,
            "date": txn.date if txn else "",
            "description": txn.description if txn else "",
        })
    return {**rec.model_dump(), "lines": line_details}


@router.patch("/{rec_id}/lines/{line_id}")
def toggle_reconciliation_line(
    session: SessionDep, user: WriteUserDep,
    rec_id: int, line_id: int, is_matched: bool,
):
    rec = session.exec(
        select(Reconciliation).where(
            Reconciliation.id == rec_id, Reconciliation.tenant_id == user.tenant_id
        )
    ).first()
    if not rec:
        raise HTTPException(404, "Not found")
    ln = session.exec(
        select(ReconciliationLine).where(
            ReconciliationLine.id == line_id,
            ReconciliationLine.reconciliation_id == rec_id,
        )
    ).first()
    if not ln:
        raise HTTPException(404, "Line not found")
    ln.is_matched = is_matched
    session.add(ln)
    session.commit()
    return {"success": True}


@router.post("/{rec_id}/close")
def close_reconciliation(session: SessionDep, user: WriteUserDep, rec_id: int):
    rec = session.exec(
        select(Reconciliation).where(
            Reconciliation.id == rec_id, Reconciliation.tenant_id == user.tenant_id
        )
    ).first()
    if not rec:
        raise HTTPException(404, "Not found")

    # IAS 7.48 — reconciliation must balance before close.
    # Sum matched JE amounts (debit − credit for each bank entry).
    matched_lines = session.exec(
        select(ReconciliationLine).where(
            ReconciliationLine.reconciliation_id == rec_id,
            ReconciliationLine.is_matched == True,  # noqa: E712
        )
    ).all()
    matched_total = ZERO
    for rl in matched_lines:
        je = session.get(JournalEntry, rl.journal_entry_id)
        if je:
            matched_total += D(je.debit) - D(je.credit)

    difference = D(str(rec.statement_balance)) - matched_total
    if abs(difference) >= D("0.01"):
        raise HTTPException(
            422,
            f"Cannot close: unreconciled difference of {difference:.2f}. "
            "Post an adjustment entry (bank fee, interest) and match it first.",
        )

    rec.status = "closed"
    session.add(rec)
    session.commit()
    return {"success": True}


class AdjustmentCreate(BaseModel):
    description: str
    account_id: int   # the non-bank side (charges / interest account)
    date: str         # YYYY-MM-DD


def _compute_matched_total(session, rec_id: int) -> Decimal:
    matched_lines = session.exec(
        select(ReconciliationLine).where(
            ReconciliationLine.reconciliation_id == rec_id,
            ReconciliationLine.is_matched == True,  # noqa: E712
        )
    ).all()
    total = ZERO
    for rl in matched_lines:
        je = session.get(JournalEntry, rl.journal_entry_id)
        if je:
            total += D(je.debit) - D(je.credit)
    return total


@router.post("/{rec_id}/adjustment", status_code=201)
def post_adjustment(
    session: SessionDep, user: WriteUserDep, rec_id: int, body: AdjustmentCreate
):
    """Post a bank fee / interest adjustment JV and auto-append it as an unmatched line."""
    rec = session.exec(
        select(Reconciliation).where(
            Reconciliation.id == rec_id, Reconciliation.tenant_id == user.tenant_id
        )
    ).first()
    if not rec:
        raise HTTPException(404, "Not found")
    if rec.status == "closed":
        raise HTTPException(400, "Reconciliation is already closed")

    matched_total = _compute_matched_total(session, rec_id)
    difference = D(str(rec.statement_balance)) - matched_total
    if abs(difference) < D("0.01"):
        raise HTTPException(400, "No adjustment needed — difference is already zero")

    ba = session.get(BankAccount, rec.bank_account_id)
    if not ba or not ba.coa_account_id:
        raise HTTPException(400, "Bank account has no linked GL account")

    abs_diff = abs(difference)
    # difference > 0: statement > GL → unrecorded credit (interest): Dr Bank, Cr other
    # difference < 0: GL > statement → unrecorded expense (charges):  Dr other, Cr Bank
    if difference > ZERO:
        entries = [
            EntryInput(account_id=ba.coa_account_id, debit=abs_diff),
            EntryInput(account_id=body.account_id, credit=abs_diff),
        ]
    else:
        entries = [
            EntryInput(account_id=body.account_id, debit=abs_diff),
            EntryInput(account_id=ba.coa_account_id, credit=abs_diff),
        ]

    txn = post_transaction(
        session, user,
        date=body.date,
        description=body.description,
        entries=entries,
        voucher_type="JV",
    )
    session.flush()

    # Attach the bank-side JE as a new (unmatched) reconciliation line
    bank_je = session.exec(
        select(JournalEntry).where(
            JournalEntry.transaction_id == txn.id,
            JournalEntry.account_id == ba.coa_account_id,
        )
    ).first()
    if bank_je:
        session.add(ReconciliationLine(
            reconciliation_id=rec.id,
            journal_entry_id=bank_je.id,
            is_matched=False,
        ))

    session.commit()
    return {"jv_number": txn.jv_number, "amount": float(abs_diff)}
