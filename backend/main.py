from typing import Annotated, List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlmodel import Session, select, func
from db import engine, get_session, create_db_and_tables, seed_data
from models import (
    Account, Transaction, JournalEntry, Settings, User, Tenant,
    TransactionCreate, TransactionRead, JournalEntryRead
)
from auth import SECRET_KEY, ALGORITHM, get_password_hash, verify_password, create_access_token

app = FastAPI(title="Easy-Books API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def get_current_user(session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        tenant_id: int = payload.get("tenant_id")
        if email is None or tenant_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise credentials_exception
    return user

SessionDep = Annotated[Session, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]

class UserSignup(BaseModel):
    email: str
    password: str
    full_name: str
    company_name: str

@app.post("/api/auth/signup")
def signup(data: UserSignup, session: SessionDep):
    # Check if user exists
    existing_user = session.exec(select(User).where(User.email == data.email)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create Tenant
    tenant = Tenant(name=data.company_name)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    
    # Create User
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        tenant_id=tenant.id
    )
    session.add(user)
    session.commit()
    
    # Auto-seed COA
    seed_data(tenant.id, session=session)
    
    return {"success": True, "tenant_id": tenant.id}

@app.post("/api/auth/login")
def login(session: SessionDep, form_data: OAuth2PasswordRequestForm = Depends()):
    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.email, "tenant_id": user.tenant_id, "full_name": user.full_name}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
def get_me(user: CurrentUserDep):
    return {"email": user.email, "full_name": user.full_name}

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --- Settings API ---
@app.get("/api/settings")
def get_settings(session: SessionDep, user: CurrentUserDep):
    settings = session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id)).all()
    return {s.key: s.value for s in settings}

@app.patch("/api/settings")
def update_settings(session: SessionDep, user: CurrentUserDep, org_name: str):
    settings = session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id, Settings.key == "org_name")).first()
    if settings:
        settings.value = org_name
    else:
        settings = Settings(key="org_name", value=org_name, tenant_id=user.tenant_id)
    session.add(settings)
    session.commit()
    return {"success": True}

# --- Accounts API ---
@app.get("/api/accounts", response_model=List[Account])
def get_accounts(session: SessionDep, user: CurrentUserDep):
    return session.exec(
        select(Account)
        .where(Account.tenant_id == user.tenant_id)
        .order_by(Account.code)
    ).all()

# --- Transactions API ---
@app.post("/api/transactions")
def create_transaction(session: SessionDep, user: CurrentUserDep, tx_data: TransactionCreate):
    # Validation: Dr must equal Cr
    total_dr = sum(e.debit for e in tx_data.entries)
    total_cr = sum(e.credit for e in tx_data.entries)
    
    if abs(total_dr - total_cr) > 0.01:
        raise HTTPException(status_code=400, detail="Transaction not balanced")

    # Validate account IDs and ensure they belong to the tenant
    account_ids = {e.account_id for e in tx_data.entries}
    accounts = session.exec(
        select(Account)
        .where(Account.id.in_(account_ids), Account.tenant_id == user.tenant_id)
    ).all()
    if len(accounts) != len(account_ids):
        raise HTTPException(status_code=400, detail="One or more invalid or unauthorized account IDs")

    # Generate JV number per tenant
    last_tx = session.exec(
        select(Transaction)
        .where(Transaction.tenant_id == user.tenant_id)
        .order_by(Transaction.id.desc())
    ).first()
    next_num = 110
    if last_tx and last_tx.jv_number.startswith("JV-"):
        try:
            next_num = int(last_tx.jv_number.split("-")[1]) + 1
        except (ValueError, IndexError):
            pass
    jv_number = f"JV-{next_num}"

    # Create Transaction
    db_tx = Transaction(
        tenant_id=user.tenant_id,
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
            tenant_id=user.tenant_id,
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
    user: CurrentUserDep,
    start: Optional[str] = None,
    end: Optional[str] = None
):
    query = select(Transaction, JournalEntry, Account).join(JournalEntry).join(Account)
    query = query.where(Transaction.tenant_id == user.tenant_id)
    
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
def get_trial_balance(session: SessionDep, user: CurrentUserDep, date: Optional[str] = None):
    # Subquery for grouped entries
    query = session.query(
        Account.code,
        Account.name,
        Account.type,
        func.sum(JournalEntry.debit).label("total_debit"),
        func.sum(JournalEntry.credit).label("total_credit")
    ).join(JournalEntry).join(Transaction)
    
    query = query.filter(Transaction.tenant_id == user.tenant_id)
    
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
        for r in results
    ]

@app.get("/api/reports/dashboard")
def get_dashboard_data(session: SessionDep, user: CurrentUserDep):
    # Get recent transactions
    recent_txs = session.exec(
        select(Transaction)
        .where(Transaction.tenant_id == user.tenant_id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(10)
    ).all()
    
    # Calculate summary by iterating over journal entries
    total_revenue = 0.0
    total_expense = 0.0
    
    je_query = session.exec(
        select(JournalEntry, Account)
        .join(Account)
        .join(Transaction)
        .where(Transaction.tenant_id == user.tenant_id)
    ).all()
    
    for entry, account in je_query:
        if account.type == 'Revenue':
            total_revenue += (entry.credit - entry.debit)
        elif account.type == 'Expense':
            total_expense += (entry.debit - entry.credit)
    
    return {
        "summary": {
            "total_revenue": total_revenue,
            "total_expense": total_expense
        },
        "recent": [
            {
                "id": tx.id,
                "jv_number": tx.jv_number,
                "date": tx.date,
                "description": tx.description or "",
                "total_amount": 0
            }
            for tx in recent_txs
        ]
    }

@app.get("/api/reports/income-statement")
def get_income_statement(
    session: SessionDep,
    user: CurrentUserDep,
    start: Optional[str] = None,
    end: Optional[str] = None
):
    query = session.query(
        Account.name,
        Account.type,
        func.sum(JournalEntry.debit).label("total_debit"),
        func.sum(JournalEntry.credit).label("total_credit")
    ).join(JournalEntry).join(Transaction).filter(Account.type.in_(['Revenue', 'Expense']))
    
    query = query.filter(Transaction.tenant_id == user.tenant_id)
    
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
def get_transaction(transaction_id: int, session: SessionDep, user: CurrentUserDep):
    tx = session.exec(
        select(Transaction)
        .where(Transaction.id == transaction_id, Transaction.tenant_id == user.tenant_id)
    ).first()
    
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

