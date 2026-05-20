"""Bank reconciliation: create period, toggle line matches, close."""
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    BankAccount, JournalEntry, Reconciliation, ReconciliationLine, Transaction,
)

from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/reconciliations", tags=["reconciliations"])


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
    rec.status = "closed"
    session.add(rec)
    session.commit()
    return {"success": True}
