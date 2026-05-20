"""Manual JV creation, read, reverse."""
from datetime import date as DateType

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from models import Transaction, TransactionCreate, TransactionRead
from services.money import D
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("")
def create_transaction(
    session: SessionDep, user: WriteUserDep, tx_data: TransactionCreate
):
    txn = post_transaction(
        session, user,
        date=tx_data.date,
        description=tx_data.description or "",
        entries=[
            EntryInput(account_id=e.account_id, debit=D(e.debit), credit=D(e.credit))
            for e in tx_data.entries
        ],
        reference=tx_data.reference,
        party=tx_data.party,
        payment_method=tx_data.payment_method,
        notes=tx_data.notes,
        audit_entity_type="transaction",
    )
    session.commit()
    return {"id": txn.id, "jv_number": txn.jv_number}


@router.post("/{transaction_id}/reverse")
def reverse_transaction(
    session: SessionDep, user: WriteUserDep, transaction_id: int
):
    txn = session.exec(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.tenant_id == user.tenant_id
        )
    ).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.is_reversed:
        raise HTTPException(400, "Transaction already reversed")

    rev_txn = post_transaction(
        session, user,
        date=str(DateType.today()),
        description=f"Reversal of {txn.jv_number}",
        entries=[
            EntryInput(account_id=je.account_id, debit=D(je.credit), credit=D(je.debit))
            for je in txn.journal_entries
        ],
        audit_entity_type="transaction",
        audit_detail={"original_jv": txn.jv_number},
    )
    txn.is_reversed = True
    txn.reversed_by_id = rev_txn.id
    session.add(txn)
    log_audit(
        session, user, "REVERSE", "transaction", txn.id,
        {"original_jv": txn.jv_number, "reversal_jv": rev_txn.jv_number},
    )
    session.commit()
    session.refresh(rev_txn)
    return {"reversal_jv_number": rev_txn.jv_number, "reversal_id": rev_txn.id}


@router.get("/{transaction_id}", response_model=TransactionRead)
def get_transaction(transaction_id: int, session: SessionDep, user: CurrentUserDep):
    tx = session.exec(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.tenant_id == user.tenant_id
        )
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    entries = [
        {
            "account_id": je.account_id,
            "account_name": je.account.name,
            "account_type": je.account.type,
            "debit": je.debit,
            "credit": je.credit,
        }
        for je in tx.journal_entries
    ]
    return {
        "id": tx.id,
        "jv_number": tx.jv_number,
        "date": tx.date,
        "description": tx.description,
        "reference": tx.reference,
        "party": tx.party,
        "payment_method": tx.payment_method,
        "notes": tx.notes,
        "entries": entries,
    }
