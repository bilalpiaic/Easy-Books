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
    Customer, Vendor, Invoice, Bill, PaymentReceived, BillPayment,
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

class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
    fiscal_year_start: Optional[str] = None
    currency: Optional[str] = None
    email_notifications: Optional[str] = None
    invoice_prefix: Optional[str] = None
    bill_prefix: Optional[str] = None
    financial_statement_date: Optional[str] = None

@app.patch("/api/settings")
def update_settings(session: SessionDep, user: CurrentUserDep, body: SettingsUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    for key, value in updates.items():
        row = session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id, Settings.key == key)).first()
        if row:
            row.value = value
        else:
            row = Settings(key=key, value=value, tenant_id=user.tenant_id)
        session.add(row)
    session.commit()
    return {"success": True}

# --- Customers API ---
class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: float = 0.0

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Optional[float] = None
    is_active: Optional[bool] = None

@app.get("/api/customers")
def list_customers(session: SessionDep, user: CurrentUserDep,
                   search: str = "", skip: int = 0, limit: int = 50):
    q = select(Customer).where(Customer.tenant_id == user.tenant_id)
    if search:
        q = q.where(Customer.name.ilike(f"%{search}%"))
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset(skip).limit(limit)).all()
    return {"total": total, "items": items}

@app.post("/api/customers", status_code=201)
def create_customer(session: SessionDep, user: CurrentUserDep, body: CustomerCreate):
    c = Customer(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c

@app.put("/api/customers/{customer_id}")
def update_customer(session: SessionDep, user: CurrentUserDep, customer_id: int, body: CustomerUpdate):
    c = session.exec(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c

@app.delete("/api/customers/{customer_id}", status_code=204)
def delete_customer(session: SessionDep, user: CurrentUserDep, customer_id: int):
    c = session.exec(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    session.delete(c)
    session.commit()

# --- Vendors API ---
class VendorCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: float = 0.0

class VendorUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Optional[float] = None
    is_active: Optional[bool] = None

@app.get("/api/vendors")
def list_vendors(session: SessionDep, user: CurrentUserDep,
                 search: str = "", skip: int = 0, limit: int = 50):
    q = select(Vendor).where(Vendor.tenant_id == user.tenant_id)
    if search:
        q = q.where(Vendor.name.ilike(f"%{search}%"))
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset(skip).limit(limit)).all()
    return {"total": total, "items": items}

@app.post("/api/vendors", status_code=201)
def create_vendor(session: SessionDep, user: CurrentUserDep, body: VendorCreate):
    v = Vendor(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(v)
    session.commit()
    session.refresh(v)
    return v

@app.put("/api/vendors/{vendor_id}")
def update_vendor(session: SessionDep, user: CurrentUserDep, vendor_id: int, body: VendorUpdate):
    v = session.exec(select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id)).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    for k, val in body.model_dump(exclude_none=True).items():
        setattr(v, k, val)
    session.add(v)
    session.commit()
    session.refresh(v)
    return v

@app.delete("/api/vendors/{vendor_id}", status_code=204)
def delete_vendor(session: SessionDep, user: CurrentUserDep, vendor_id: int):
    v = session.exec(select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id)).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    session.delete(v)
    session.commit()

# --- Invoices API ---
def _get_or_create_account(session: Session, tenant_id: int, code: str, name: str, acct_type: str) -> Account:
    acc = session.exec(select(Account).where(Account.tenant_id == tenant_id, Account.code == code)).first()
    if not acc:
        acc = Account(code=code, name=name, type=acct_type, tenant_id=tenant_id)
        session.add(acc)
        session.flush()
    return acc

def _next_invoice_number(session: Session, tenant_id: int, prefix: str) -> str:
    count = session.exec(select(func.count(Invoice.id)).where(Invoice.tenant_id == tenant_id)).one()
    return f"{prefix}-{count + 1:04d}"

class InvoiceCreate(BaseModel):
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    issue_date: str
    due_date: str
    description: Optional[str] = None
    subtotal: float
    gst_rate: float = 17.0
    ar_account_id: Optional[int] = None
    revenue_account_id: Optional[int] = None

@app.get("/api/invoices")
def list_invoices(session: SessionDep, user: CurrentUserDep,
                  search: str = "", skip: int = 0, limit: int = 50,
                  status: str = ""):
    q = select(Invoice).where(Invoice.tenant_id == user.tenant_id)
    if search:
        q = q.where((Invoice.number.ilike(f"%{search}%")) | (Invoice.customer_name.ilike(f"%{search}%")))
    if status:
        q = q.where(Invoice.status == status)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(Invoice.issue_date.desc()).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}

@app.post("/api/invoices", status_code=201)
def create_invoice(session: SessionDep, user: CurrentUserDep, body: InvoiceCreate):
    prefix_row = session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id, Settings.key == "invoice_prefix")).first()
    prefix = prefix_row.value if prefix_row else "INV"
    gst_amount = round(body.subtotal * body.gst_rate / 100, 2)
    total = round(body.subtotal + gst_amount, 2)

    # Resolve customer name
    cname = body.customer_name
    if body.customer_id:
        c = session.get(Customer, body.customer_id)
        if c:
            cname = c.name

    invoice = Invoice(
        tenant_id=user.tenant_id,
        number=_next_invoice_number(session, user.tenant_id, prefix),
        customer_id=body.customer_id,
        customer_name=cname,
        issue_date=body.issue_date,
        due_date=body.due_date,
        description=body.description,
        subtotal=body.subtotal,
        gst_rate=body.gst_rate,
        gst_amount=gst_amount,
        total=total,
        status="draft",
        ar_account_id=body.ar_account_id,
        revenue_account_id=body.revenue_account_id,
    )
    session.add(invoice)
    session.flush()

    # Auto-post GL: Dr AR / Cr Revenue [/ Cr GST Payable]
    ar_acc = session.get(Account, body.ar_account_id) if body.ar_account_id else \
        _get_or_create_account(session, user.tenant_id, "1100", "Accounts Receivable", "Asset")
    rev_acc = session.get(Account, body.revenue_account_id) if body.revenue_account_id else \
        _get_or_create_account(session, user.tenant_id, "4000", "Sales Revenue", "Revenue")

    jv_count = session.exec(select(func.count(Transaction.id)).where(Transaction.tenant_id == user.tenant_id)).one()
    txn = Transaction(
        tenant_id=user.tenant_id,
        jv_number=f"JV-{jv_count + 1:05d}",
        date=invoice.issue_date,
        description=f"Invoice {invoice.number} — {cname or ''}",
    )
    session.add(txn)
    session.flush()

    entries = [JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=ar_acc.id, debit=total, credit=0)]
    if gst_amount > 0:
        gst_acc = _get_or_create_account(session, user.tenant_id, "2200", "GST Payable", "Liability")
        entries.append(JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=rev_acc.id, debit=0, credit=body.subtotal))
        entries.append(JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=gst_acc.id, debit=0, credit=gst_amount))
    else:
        entries.append(JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=rev_acc.id, debit=0, credit=total))

    for e in entries:
        session.add(e)

    invoice.transaction_id = txn.id
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice

@app.patch("/api/invoices/{invoice_id}/status")
def update_invoice_status(session: SessionDep, user: CurrentUserDep, invoice_id: int, status: str):
    inv = session.exec(select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.status = status
    session.add(inv)
    session.commit()
    session.refresh(inv)
    return inv

# --- Bills API ---
def _next_bill_number(session: Session, tenant_id: int, prefix: str) -> str:
    count = session.exec(select(func.count(Bill.id)).where(Bill.tenant_id == tenant_id)).one()
    return f"{prefix}-{count + 1:04d}"

class BillCreate(BaseModel):
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    bill_date: str
    due_date: str
    description: Optional[str] = None
    subtotal: float
    gst_rate: float = 17.0
    ap_account_id: Optional[int] = None
    expense_account_id: Optional[int] = None

@app.get("/api/bills")
def list_bills(session: SessionDep, user: CurrentUserDep,
               search: str = "", skip: int = 0, limit: int = 50, status: str = ""):
    q = select(Bill).where(Bill.tenant_id == user.tenant_id)
    if search:
        q = q.where((Bill.number.ilike(f"%{search}%")) | (Bill.vendor_name.ilike(f"%{search}%")))
    if status:
        q = q.where(Bill.status == status)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(Bill.bill_date.desc()).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}

@app.post("/api/bills", status_code=201)
def create_bill(session: SessionDep, user: CurrentUserDep, body: BillCreate):
    prefix_row = session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id, Settings.key == "bill_prefix")).first()
    prefix = prefix_row.value if prefix_row else "BILL"
    gst_amount = round(body.subtotal * body.gst_rate / 100, 2)
    total = round(body.subtotal + gst_amount, 2)

    vname = body.vendor_name
    if body.vendor_id:
        v = session.get(Vendor, body.vendor_id)
        if v:
            vname = v.name

    bill = Bill(
        tenant_id=user.tenant_id,
        number=_next_bill_number(session, user.tenant_id, prefix),
        vendor_id=body.vendor_id,
        vendor_name=vname,
        bill_date=body.bill_date,
        due_date=body.due_date,
        description=body.description,
        subtotal=body.subtotal,
        gst_rate=body.gst_rate,
        gst_amount=gst_amount,
        total=total,
        status="draft",
        ap_account_id=body.ap_account_id,
        expense_account_id=body.expense_account_id,
    )
    session.add(bill)
    session.flush()

    # Auto-post GL: Dr Expense [+ Dr GST Receivable] / Cr Accounts Payable
    ap_acc = session.get(Account, body.ap_account_id) if body.ap_account_id else \
        _get_or_create_account(session, user.tenant_id, "2000", "Accounts Payable", "Liability")
    exp_acc = session.get(Account, body.expense_account_id) if body.expense_account_id else \
        _get_or_create_account(session, user.tenant_id, "5000", "General Expenses", "Expense")

    jv_count = session.exec(select(func.count(Transaction.id)).where(Transaction.tenant_id == user.tenant_id)).one()
    txn = Transaction(
        tenant_id=user.tenant_id,
        jv_number=f"JV-{jv_count + 1:05d}",
        date=bill.bill_date,
        description=f"Bill {bill.number} — {vname or ''}",
    )
    session.add(txn)
    session.flush()

    entries = [JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=ap_acc.id, debit=0, credit=total)]
    if gst_amount > 0:
        gst_input_acc = _get_or_create_account(session, user.tenant_id, "1200", "GST Receivable (Input)", "Asset")
        entries.append(JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=exp_acc.id, debit=body.subtotal, credit=0))
        entries.append(JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=gst_input_acc.id, debit=gst_amount, credit=0))
    else:
        entries.append(JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=exp_acc.id, debit=total, credit=0))

    for e in entries:
        session.add(e)

    bill.transaction_id = txn.id
    session.add(bill)
    session.commit()
    session.refresh(bill)
    return bill

@app.patch("/api/bills/{bill_id}/status")
def update_bill_status(session: SessionDep, user: CurrentUserDep, bill_id: int, status: str):
    b = session.exec(select(Bill).where(Bill.id == bill_id, Bill.tenant_id == user.tenant_id)).first()
    if not b:
        raise HTTPException(404, "Bill not found")
    b.status = status
    session.add(b)
    session.commit()
    session.refresh(b)
    return b

# --- Payments Received API ---
class PaymentReceivedCreate(BaseModel):
    invoice_id: Optional[int] = None
    customer_name: Optional[str] = None
    payment_date: str
    amount: float
    method: str = "cash"
    reference: Optional[str] = None
    cash_account_id: Optional[int] = None

@app.get("/api/payments-received")
def list_payments_received(session: SessionDep, user: CurrentUserDep, skip: int = 0, limit: int = 50):
    q = select(PaymentReceived).where(PaymentReceived.tenant_id == user.tenant_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(PaymentReceived.payment_date.desc()).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}

@app.post("/api/payments-received", status_code=201)
def create_payment_received(session: SessionDep, user: CurrentUserDep, body: PaymentReceivedCreate):
    cname = body.customer_name
    if body.invoice_id:
        inv = session.get(Invoice, body.invoice_id)
        if inv and inv.tenant_id == user.tenant_id:
            if not cname:
                cname = inv.customer_name
            inv.status = "paid"
            session.add(inv)

    # GL: Dr Cash/Bank / Cr AR
    cash_acc = session.get(Account, body.cash_account_id) if body.cash_account_id else \
        _get_or_create_account(session, user.tenant_id, "1000", "Cash in Hand", "Asset")
    ar_acc = _get_or_create_account(session, user.tenant_id, "1100", "Accounts Receivable", "Asset")

    jv_count = session.exec(select(func.count(Transaction.id)).where(Transaction.tenant_id == user.tenant_id)).one()
    txn = Transaction(
        tenant_id=user.tenant_id,
        jv_number=f"JV-{jv_count + 1:05d}",
        date=body.payment_date,
        description=f"Payment received — {cname or ''} {body.reference or ''}".strip(),
    )
    session.add(txn)
    session.flush()

    for e in [
        JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=cash_acc.id, debit=body.amount, credit=0),
        JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=ar_acc.id, debit=0, credit=body.amount),
    ]:
        session.add(e)

    pmt = PaymentReceived(
        tenant_id=user.tenant_id,
        invoice_id=body.invoice_id,
        customer_name=cname,
        payment_date=body.payment_date,
        amount=body.amount,
        method=body.method,
        reference=body.reference,
        cash_account_id=cash_acc.id,
        transaction_id=txn.id,
    )
    session.add(pmt)
    session.commit()
    session.refresh(pmt)
    return pmt

# --- Bill Payments API ---
class BillPaymentCreate(BaseModel):
    bill_id: Optional[int] = None
    vendor_name: Optional[str] = None
    payment_date: str
    amount: float
    method: str = "cash"
    reference: Optional[str] = None
    cash_account_id: Optional[int] = None

@app.get("/api/bill-payments")
def list_bill_payments(session: SessionDep, user: CurrentUserDep, skip: int = 0, limit: int = 50):
    q = select(BillPayment).where(BillPayment.tenant_id == user.tenant_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(BillPayment.payment_date.desc()).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}

@app.post("/api/bill-payments", status_code=201)
def create_bill_payment(session: SessionDep, user: CurrentUserDep, body: BillPaymentCreate):
    vname = body.vendor_name
    if body.bill_id:
        b = session.get(Bill, body.bill_id)
        if b and b.tenant_id == user.tenant_id:
            if not vname:
                vname = b.vendor_name
            b.status = "paid"
            session.add(b)

    # GL: Dr AP / Cr Cash/Bank
    cash_acc = session.get(Account, body.cash_account_id) if body.cash_account_id else \
        _get_or_create_account(session, user.tenant_id, "1000", "Cash in Hand", "Asset")
    ap_acc = _get_or_create_account(session, user.tenant_id, "2000", "Accounts Payable", "Liability")

    jv_count = session.exec(select(func.count(Transaction.id)).where(Transaction.tenant_id == user.tenant_id)).one()
    txn = Transaction(
        tenant_id=user.tenant_id,
        jv_number=f"JV-{jv_count + 1:05d}",
        date=body.payment_date,
        description=f"Bill payment — {vname or ''} {body.reference or ''}".strip(),
    )
    session.add(txn)
    session.flush()

    for e in [
        JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=ap_acc.id, debit=body.amount, credit=0),
        JournalEntry(tenant_id=user.tenant_id, transaction_id=txn.id, account_id=cash_acc.id, debit=0, credit=body.amount),
    ]:
        session.add(e)

    bp = BillPayment(
        tenant_id=user.tenant_id,
        bill_id=body.bill_id,
        vendor_name=vname,
        payment_date=body.payment_date,
        amount=body.amount,
        method=body.method,
        reference=body.reference,
        cash_account_id=cash_acc.id,
        transaction_id=txn.id,
    )
    session.add(bp)
    session.commit()
    session.refresh(bp)
    return bp

# --- Accounts API ---
class AccountCreate(BaseModel):
    code: str
    name: str
    type: str

class AccountUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None

@app.post("/api/accounts")
def create_account(session: SessionDep, user: CurrentUserDep, data: AccountCreate):
    existing = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id, Account.code == data.code)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account code {data.code} already exists")
    account = Account(code=data.code, name=data.name, type=data.type, tenant_id=user.tenant_id)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account

@app.put("/api/accounts/{account_id}")
def update_account(account_id: int, session: SessionDep, user: CurrentUserDep, data: AccountUpdate):
    account = session.exec(
        select(Account).where(Account.id == account_id, Account.tenant_id == user.tenant_id)
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if data.code is not None:
        account.code = data.code
    if data.name is not None:
        account.name = data.name
    if data.type is not None:
        account.type = data.type
    session.add(account)
    session.commit()
    session.refresh(account)
    return account

@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int, session: SessionDep, user: CurrentUserDep):
    account = session.exec(
        select(Account).where(Account.id == account_id, Account.tenant_id == user.tenant_id)
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    # Block deletion if the account has journal entries
    entries = session.exec(select(JournalEntry).where(JournalEntry.account_id == account_id)).first()
    if entries:
        raise HTTPException(status_code=400, detail="Cannot delete account with existing journal entries")
    session.delete(account)
    session.commit()
    return {"success": True}

@app.get("/api/accounts")
    session: SessionDep,
    user: CurrentUserDep,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
):
    q = select(Account).where(Account.tenant_id == user.tenant_id)
    if search:
        q = q.where((Account.name.ilike(f"%{search}%")) | (Account.code.ilike(f"%{search}%")))
    total = len(session.exec(q).all())
    results = session.exec(q.order_by(Account.code).offset(skip).limit(limit)).all()
    return {"total": total, "items": [r.model_dump() for r in results]}

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
    end: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    query = select(Transaction, JournalEntry, Account).join(JournalEntry).join(Account)
    query = query.where(Transaction.tenant_id == user.tenant_id)

    if start:
        query = query.where(Transaction.date >= start)
    if end:
        query = query.where(Transaction.date <= end)

    query = query.order_by(Transaction.date.desc(), Transaction.id.desc())
    total_q = session.exec(query).all()
    total = len(total_q)
    results = total_q[skip: skip + limit]

    return {
        "total": total,
        "items": [
            {
                "id": tx.id,
                "jv_number": tx.jv_number,
                "date": tx.date,
                "description": tx.description,
                "account_name": acc.name,
                "debit": je.debit,
                "credit": je.credit,
            }
            for tx, je, acc in results
        ],
    }

@app.get("/api/reports/trial-balance")
def get_trial_balance(
    session: SessionDep,
    user: CurrentUserDep,
    start: Optional[str] = None,
    end: Optional[str] = None,
    date: Optional[str] = None,
):
    query = session.query(
        Account.code,
        Account.name,
        Account.type,
        func.sum(JournalEntry.debit).label("total_debit"),
        func.sum(JournalEntry.credit).label("total_credit")
    ).join(JournalEntry).join(Transaction)

    query = query.filter(Transaction.tenant_id == user.tenant_id)

    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)
    elif date:
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
            "total_credit": r.total_credit,
        }
        for r in results
    ]

@app.get("/api/reports/dashboard")
def get_dashboard_data(
    session: SessionDep,
    user: CurrentUserDep,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    tx_base = select(Transaction).where(Transaction.tenant_id == user.tenant_id)
    if start:
        tx_base = tx_base.where(Transaction.date >= start)
    if end:
        tx_base = tx_base.where(Transaction.date <= end)

    recent_txs = session.exec(
        tx_base.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(10)
    ).all()

    transaction_count = session.exec(
        select(func.count()).select_from(tx_base.subquery())
    ).one()

    je_q = select(JournalEntry, Account).join(Account).join(Transaction).where(
        Transaction.tenant_id == user.tenant_id
    )
    if start:
        je_q = je_q.where(Transaction.date >= start)
    if end:
        je_q = je_q.where(Transaction.date <= end)

    total_revenue = 0.0
    total_expense = 0.0
    for entry, account in session.exec(je_q).all():
        if account.type == "Revenue":
            total_revenue += entry.credit - entry.debit
        elif account.type == "Expense":
            total_expense += entry.debit - entry.credit
    
    return {
        "summary": {
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "transaction_count": transaction_count,
        },
        "recent": [
            {
                "id": tx.id,
                "jv_number": tx.jv_number,
                "date": tx.date,
                "description": tx.description or "",
            }
            for tx in recent_txs
        ],
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

@app.get("/api/reports/ledger")
def get_ledger(
    session: SessionDep,
    user: CurrentUserDep,
    start: Optional[str] = None,
    end: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    query = (
        session.query(Account, Transaction, JournalEntry)
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(Transaction.tenant_id == user.tenant_id)
    )
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)
    if search:
        query = query.filter(Account.name.ilike(f"%{search}%"))

    rows = query.order_by(Account.code, Transaction.date, Transaction.id).all()

    # Group by account, compute running balance
    accounts: dict = {}
    for account, tx, je in rows:
        if account.id not in accounts:
            accounts[account.id] = {
                "code": account.code,
                "name": account.name,
                "type": account.type,
                "entries": [],
                "running_balance": 0.0,
            }
        running = accounts[account.id]["running_balance"]
        if account.type in ("Asset", "Expense"):
            running += je.debit - je.credit
        else:
            running += je.credit - je.debit
        accounts[account.id]["running_balance"] = running
        accounts[account.id]["entries"].append({
            "date": tx.date,
            "jv_number": tx.jv_number,
            "description": tx.description or "",
            "debit": je.debit,
            "credit": je.credit,
            "balance": running,
        })

    all_accounts = list(accounts.values())
    total = len(all_accounts)
    return {"total": total, "items": all_accounts[skip: skip + limit]}

@app.get("/api/reports/balance-sheet")
def get_balance_sheet(
    session: SessionDep,
    user: CurrentUserDep,
    start: Optional[str] = None,
    end: Optional[str] = None,
    date: Optional[str] = None,
):
    query = session.query(
        Account.code,
        Account.name,
        Account.type,
        func.sum(JournalEntry.debit).label("total_debit"),
        func.sum(JournalEntry.credit).label("total_credit")
    ).join(JournalEntry).join(Transaction)

    query = query.filter(Transaction.tenant_id == user.tenant_id)

    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)
    elif date:
        query = query.filter(Transaction.date <= date)

    results = query.group_by(Account.id).order_by(Account.code).all()

    items = []
    net_income = 0.0
    for r in results:
        debit = r.total_debit or 0
        credit = r.total_credit or 0
        if r.type in ("Asset",):
            balance = debit - credit
        elif r.type in ("Liability", "Equity"):
            balance = credit - debit
        elif r.type == "Revenue":
            net_income += credit - debit
            continue
        elif r.type == "Expense":
            net_income -= debit - credit
            continue
        else:
            balance = debit - credit
        items.append({"code": r.code, "name": r.name, "type": r.type, "balance": balance})

    # Inject current-period retained earnings into Equity
    if net_income != 0:
        items.append({
            "code": "RE-CUR",
            "name": "Retained Earnings (Current Period)",
            "type": "Equity",
            "balance": net_income,
        })

    return items

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

