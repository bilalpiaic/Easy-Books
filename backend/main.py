from typing import Annotated, List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, func
from db import engine, get_session, create_db_and_tables
from models import (
    Account, Transaction, JournalEntry, Settings,
    TransactionCreate, TransactionRead, JournalEntryRead
)

app = FastAPI(title="Easy-Books API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SessionDep = Annotated[Session, Depends(get_session)]

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --- Settings API ---
@app.get("/api/settings")
def get_settings(session: SessionDep):
    settings = session.exec(select(Settings)).all()
    return {s.key: s.value for s in settings}

@app.patch("/api/settings")
def update_settings(session: SessionDep, org_name: str):
    settings = session.get(Settings, "org_name")
    if settings:
        settings.value = org_name
    else:
        settings = Settings(key="org_name", value=org_name)
    session.add(settings)
    session.commit()
    return {"success": True}

# --- Accounts API ---
@app.get("/api/accounts", response_model=List[Account])
def get_accounts(session: SessionDep):
    return session.exec(select(Account).order_by(Account.code)).all()

# --- Transactions API ---
@app.post("/api/transactions")
def create_transaction(session: SessionDep, tx_data: TransactionCreate):
    # Validation: Dr must equal Cr
    total_dr = sum(e.debit for e in tx_data.entries)
    total_cr = sum(e.credit for e in tx_data.entries)
    
    if abs(total_dr - total_cr) > 0.01:
        raise HTTPException(status_code=400, detail="Transaction not balanced")

    # Validate account IDs
    account_ids = {e.account_id for e in tx_data.entries}
    accounts = session.exec(select(Account).where(Account.id.in_(account_ids))).all()
    if len(accounts) != len(account_ids):
        raise HTTPException(status_code=400, detail="One or more invalid account IDs")

    # Generate JV number
    last_tx = session.exec(select(Transaction).order_by(Transaction.id.desc())).first()
    next_num = 110
    if last_tx and last_tx.jv_number.startswith("JV-"):
        try:
            next_num = int(last_tx.jv_number.split("-")[1]) + 1
        except (ValueError, IndexError):
            pass
    jv_number = f"JV-{next_num}"

    # Create Transaction
    db_tx = Transaction(
        jv_number=jv_number,
        date=tx_data.date,
        description=tx_data.description,
        reference=tx_data.reference,
        party=tx_data.party,
        payment_method=tx_data.payment_method,
        notes=tx_data.notes
    )
    session.add(db_tx)
    session.commit()
    session.refresh(db_tx)

    # Create Journal Entries
    for e in tx_data.entries:
        db_entry = JournalEntry(
            transaction_id=db_tx.id,
            account_id=e.account_id,
            debit=e.debit,
            credit=e.credit
        )
        session.add(db_entry)
    
    session.commit()
    return {"id": db_tx.id, "jv_number": db_tx.jv_number}

# --- Reports API ---
@app.get("/api/reports/journal")
def get_journal_report(
    session: SessionDep,
    start: Optional[str] = None,
    end: Optional[str] = None
):
    query = select(Transaction, JournalEntry, Account).join(JournalEntry).join(Account)
    if start and end:
        query = query.where(Transaction.date >= start, Transaction.date <= end)
    
    results = session.exec(query.order_by(Transaction.date.desc(), Transaction.id.desc())).all()
    
    return [
        {
            "id": tx.id,
            "jv_number": tx.jv_number,
            "date": tx.date,
            "description": tx.description,
            "account_name": acc.name,
            "debit": je.debit,
            "credit": je.credit
        }
        for tx, je, acc in results
    ]

@app.get("/api/reports/trial-balance")
def get_trial_balance(session: SessionDep, date: Optional[str] = None):
    # Subquery for grouped entries
    query = session.query(
        Account.code,
        Account.name,
        Account.type,
        func.sum(JournalEntry.debit).label("total_debit"),
        func.sum(JournalEntry.credit).label("total_credit")
    ).join(JournalEntry).join(Transaction)
    
    if date:
        query = query.filter(Transaction.date <= date)
    
    results = query.group_by(Account.id).having(
        (func.sum(JournalEntry.debit) > 0) | (func.sum(JournalEntry.credit) > 0)
    ).order_by(Account.code).all()
    
    return [
        {
            "code": r.code,
            "name": r.name,
            "type": r.type,
            "total_debit": r.total_debit,
            "total_credit": r.total_credit
        }
        from sqlmodel import Session, select, func, case
        ...
        @app.get("/api/reports/dashboard")
        def get_dashboard_data(session: SessionDep):
            # Summary
            summary_query = session.query(
                func.sum(case([(Account.type == 'Revenue', JournalEntry.credit - JournalEntry.debit)], else_=0)).label("total_revenue"),
                func.sum(case([(Account.type == 'Expense', JournalEntry.debit - JournalEntry.credit)], else_=0)).label("total_expense")
            ).join(JournalEntry, JournalEntry.account_id == Account.id)
        ...
    
    summary = summary_query.one()
    
    # Recent Transactions
    recent_txs = session.exec(
        select(Transaction, func.sum(JournalEntry.debit))
        .join(JournalEntry)
        .group_by(Transaction.id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(10)
    ).all()
    
    return {
        "summary": {
            "total_revenue": summary.total_revenue or 0,
            "total_expense": summary.total_expense or 0
        },
        "recent": [
            {
                "id": tx.id,
                "jv_number": tx.jv_number,
                "date": tx.date,
                "description": tx.description,
                "total_amount": amt
            }
            for tx, amt in recent_txs
        ]
    }

@app.get("/api/reports/income-statement")
def get_income_statement(
    session: SessionDep,
    start: Optional[str] = None,
    end: Optional[str] = None
):
    query = session.query(
        Account.name,
        Account.type,
        func.sum(JournalEntry.debit).label("total_debit"),
        func.sum(JournalEntry.credit).label("total_credit")
    ).join(JournalEntry).join(Transaction).filter(Account.type.in_(['Revenue', 'Expense']))
    
    if start and end:
        query = query.filter(Transaction.date >= start, Transaction.date <= end)
    
    results = query.group_by(Account.id).order_by(Account.type.desc(), Account.code).all()
    
    return [
        {
            "name": r.name,
            "type": r.type,
            "total_debit": r.total_debit,
            "total_credit": r.total_credit
        }
        for r in results
    ]

@app.get("/api/transactions/{transaction_id}", response_model=TransactionRead)
def get_transaction(transaction_id: int, session: SessionDep):
    tx = session.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    entries = []
    for je in tx.journal_entries:
        entries.append({
            "account_id": je.account_id,
            "account_name": je.account.name,
            "account_type": je.account.type,
            "debit": je.debit,
            "credit": je.credit
        })
    
    # We need a custom return because TransactionRead has account details
    return {
        "id": tx.id,
        "jv_number": tx.jv_number,
        "date": tx.date,
        "description": tx.description,
        "reference": tx.reference,
        "party": tx.party,
        "payment_method": tx.payment_method,
        "notes": tx.notes,
        "entries": entries
    }

