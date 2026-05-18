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
    Customer, Vendor, Invoice, Bill, PaymentReceived, BillPayment, BankAccount,
    Reconciliation, ReconciliationLine, AccountingPeriod, AuditLog,
    TransactionCreate, TransactionRead, JournalEntryRead
)
import json as _json
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

def log_audit(session: Session, user: User, action: str, entity_type: str, entity_id: Optional[int] = None, detail: dict = {}):
    entry = AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=_json.dumps(detail) if detail else None,
    )
    session.add(entry)

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
    session.flush()
    log_audit(session, user, "CREATE", "customer", c.id, {"name": c.name})
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
    log_audit(session, user, "UPDATE", "customer", c.id, {"name": c.name})
    session.commit()
    session.refresh(c)
    return c

@app.delete("/api/customers/{customer_id}", status_code=204)
def delete_customer(session: SessionDep, user: CurrentUserDep, customer_id: int):
    c = session.exec(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    log_audit(session, user, "DELETE", "customer", c.id, {"name": c.name})
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
    session.flush()
    log_audit(session, user, "CREATE", "vendor", v.id, {"name": v.name})
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
    log_audit(session, user, "UPDATE", "vendor", v.id, {"name": v.name})
    session.commit()
    session.refresh(v)
    return v

@app.delete("/api/vendors/{vendor_id}", status_code=204)
def delete_vendor(session: SessionDep, user: CurrentUserDep, vendor_id: int):
    v = session.exec(select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id)).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    log_audit(session, user, "DELETE", "vendor", v.id, {"name": v.name})
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
    log_audit(session, user, "CREATE", "invoice", invoice.id, {"number": invoice.number, "total": invoice.total})
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
    log_audit(session, user, "UPDATE", "invoice", inv.id, {"number": inv.number, "status": status})
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
    log_audit(session, user, "CREATE", "bill", bill.id, {"number": bill.number, "total": bill.total})
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
    log_audit(session, user, "UPDATE", "bill", b.id, {"number": b.number, "status": status})
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

# --- AR / AP Aging ---
from datetime import date as DateType

def _aging_buckets(items: list, date_field: str, amount_field: str, name_field: str) -> dict:
    today = DateType.today()
    buckets = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "over_90": 0, "items": []}
    for item in items:
        if getattr(item, "status", None) == "paid":
            continue
        due = DateType.fromisoformat(getattr(item, date_field))
        days_past = (today - due).days
        amount = getattr(item, amount_field)
        if days_past <= 0:
            buckets["current"] += amount
            bucket = "current"
        elif days_past <= 30:
            buckets["1_30"] += amount
            bucket = "1-30"
        elif days_past <= 60:
            buckets["31_60"] += amount
            bucket = "31-60"
        elif days_past <= 90:
            buckets["61_90"] += amount
            bucket = "61-90"
        else:
            buckets["over_90"] += amount
            bucket = "90+"
        buckets["items"].append({
            "id": item.id,
            "name": getattr(item, name_field) or "—",
            "number": getattr(item, "number", ""),
            "due_date": getattr(item, date_field),
            "amount": amount,
            "days_past": max(0, days_past),
            "bucket": bucket,
        })
    return buckets

@app.get("/api/invoices/aging")
def invoice_aging(session: SessionDep, user: CurrentUserDep):
    items = session.exec(select(Invoice).where(Invoice.tenant_id == user.tenant_id)).all()
    return _aging_buckets(items, "due_date", "total", "customer_name")

@app.get("/api/bills/aging")
def bill_aging(session: SessionDep, user: CurrentUserDep):
    items = session.exec(select(Bill).where(Bill.tenant_id == user.tenant_id)).all()
    return _aging_buckets(items, "due_date", "total", "vendor_name")

# --- Bank Accounts API ---
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

def _bank_balance(session: Session, tenant_id: int, coa_id: int) -> float:
    entries = session.exec(select(JournalEntry).join(Account).where(
        Account.id == coa_id,
        JournalEntry.tenant_id == tenant_id
    )).all()
    acc = session.get(Account, coa_id)
    if not acc:
        return 0.0
    if acc.type in ("Asset", "Expense"):
        return sum(e.debit - e.credit for e in entries)
    return sum(e.credit - e.debit for e in entries)

@app.get("/api/bank-accounts")
def list_bank_accounts(session: SessionDep, user: CurrentUserDep):
    accounts = session.exec(select(BankAccount).where(BankAccount.tenant_id == user.tenant_id)).all()
    result = []
    for ba in accounts:
        balance = _bank_balance(session, user.tenant_id, ba.coa_account_id) if ba.coa_account_id else 0.0
        result.append({**ba.model_dump(), "balance": balance})
    return result

@app.post("/api/bank-accounts", status_code=201)
def create_bank_account(session: SessionDep, user: CurrentUserDep, body: BankAccountCreate):
    ba = BankAccount(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(ba)
    session.commit()
    session.refresh(ba)
    return ba

@app.put("/api/bank-accounts/{ba_id}")
def update_bank_account(session: SessionDep, user: CurrentUserDep, ba_id: int, body: BankAccountUpdate):
    ba = session.exec(select(BankAccount).where(BankAccount.id == ba_id, BankAccount.tenant_id == user.tenant_id)).first()
    if not ba:
        raise HTTPException(404, "Bank account not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ba, k, v)
    session.add(ba)
    session.commit()
    session.refresh(ba)
    return ba

@app.delete("/api/bank-accounts/{ba_id}", status_code=204)
def delete_bank_account(session: SessionDep, user: CurrentUserDep, ba_id: int):
    ba = session.exec(select(BankAccount).where(BankAccount.id == ba_id, BankAccount.tenant_id == user.tenant_id)).first()
    if not ba:
        raise HTTPException(404, "Bank account not found")
    session.delete(ba)
    session.commit()

# --- Reconciliations API ---
class ReconciliationCreate(BaseModel):
    bank_account_id: int
    period_start: str
    period_end: str
    statement_balance: float

@app.get("/api/reconciliations")
def list_reconciliations(session: SessionDep, user: CurrentUserDep):
    recs = session.exec(select(Reconciliation).where(Reconciliation.tenant_id == user.tenant_id).order_by(Reconciliation.period_end.desc())).all()
    result = []
    for r in recs:
        ba = session.get(BankAccount, r.bank_account_id)
        result.append({**r.model_dump(), "bank_account_name": ba.name if ba else "—"})
    return result

@app.post("/api/reconciliations", status_code=201)
def create_reconciliation(session: SessionDep, user: CurrentUserDep, body: ReconciliationCreate):
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

    # Create reconciliation lines for all unmatched GL entries in this period for the linked CoA account
    if ba.coa_account_id:
        entries = session.exec(
            select(JournalEntry).join(Transaction).where(
                JournalEntry.account_id == ba.coa_account_id,
                JournalEntry.tenant_id == user.tenant_id,
                Transaction.date >= body.period_start,
                Transaction.date <= body.period_end,
            )
        ).all()
        for e in entries:
            line = ReconciliationLine(reconciliation_id=rec.id, journal_entry_id=e.id, is_matched=False)
            session.add(line)

    session.commit()
    session.refresh(rec)
    return rec

@app.get("/api/reconciliations/{rec_id}")
def get_reconciliation(session: SessionDep, user: CurrentUserDep, rec_id: int):
    rec = session.exec(select(Reconciliation).where(Reconciliation.id == rec_id, Reconciliation.tenant_id == user.tenant_id)).first()
    if not rec:
        raise HTTPException(404, "Not found")
    lines = session.exec(select(ReconciliationLine).where(ReconciliationLine.reconciliation_id == rec_id)).all()
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

@app.patch("/api/reconciliations/{rec_id}/lines/{line_id}")
def toggle_reconciliation_line(session: SessionDep, user: CurrentUserDep, rec_id: int, line_id: int, is_matched: bool):
    rec = session.exec(select(Reconciliation).where(Reconciliation.id == rec_id, Reconciliation.tenant_id == user.tenant_id)).first()
    if not rec:
        raise HTTPException(404, "Not found")
    ln = session.exec(select(ReconciliationLine).where(ReconciliationLine.id == line_id, ReconciliationLine.reconciliation_id == rec_id)).first()
    if not ln:
        raise HTTPException(404, "Line not found")
    ln.is_matched = is_matched
    session.add(ln)
    session.commit()
    return {"success": True}

@app.post("/api/reconciliations/{rec_id}/close")
def close_reconciliation(session: SessionDep, user: CurrentUserDep, rec_id: int):
    rec = session.exec(select(Reconciliation).where(Reconciliation.id == rec_id, Reconciliation.tenant_id == user.tenant_id)).first()
    if not rec:
        raise HTTPException(404, "Not found")
    rec.status = "closed"
    session.add(rec)
    session.commit()
    return {"success": True}

# --- Accounts API ---
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

@app.post("/api/accounts")
def create_account(session: SessionDep, user: CurrentUserDep, data: AccountCreate):
    existing = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id, Account.code == data.code)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account code {data.code} already exists")
    account = Account(code=data.code, name=data.name, type=data.type, parent_id=data.parent_id, tenant_id=user.tenant_id)
    session.add(account)
    session.flush()
    log_audit(session, user, "CREATE", "account", account.id, {"code": account.code, "name": account.name})
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
    for field in ("code", "name", "type", "parent_id"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(account, field, val)
    session.add(account)
    log_audit(session, user, "UPDATE", "account", account.id, {"code": account.code, "name": account.name})
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
    log_audit(session, user, "DELETE", "account", account.id, {"code": account.code, "name": account.name})
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

# --- Accounting Periods API ---
class PeriodCreate(BaseModel):
    name: Optional[str] = None
    period_start: str
    period_end: str

@app.get("/api/periods")
def list_periods(session: SessionDep, user: CurrentUserDep):
    return session.exec(select(AccountingPeriod).where(AccountingPeriod.tenant_id == user.tenant_id).order_by(AccountingPeriod.period_start.desc())).all()

@app.post("/api/periods", status_code=201)
def create_period(session: SessionDep, user: CurrentUserDep, body: PeriodCreate):
    p = AccountingPeriod(tenant_id=user.tenant_id, **body.model_dump())
    session.add(p)
    session.commit()
    session.refresh(p)
    return p

@app.patch("/api/periods/{period_id}/lock")
def toggle_period_lock(session: SessionDep, user: CurrentUserDep, period_id: int, is_locked: bool):
    p = session.exec(select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.tenant_id == user.tenant_id)).first()
    if not p:
        raise HTTPException(404, "Period not found")
    p.is_locked = is_locked
    session.add(p)
    session.commit()
    return p

@app.delete("/api/periods/{period_id}", status_code=204)
def delete_period(session: SessionDep, user: CurrentUserDep, period_id: int):
    p = session.exec(select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.tenant_id == user.tenant_id)).first()
    if not p:
        raise HTTPException(404, "Period not found")
    session.delete(p)
    session.commit()

# --- Audit Log API ---
@app.get("/api/audit-log")
def get_audit_log(
    session: SessionDep,
    user: CurrentUserDep,
    entity_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    q = select(AuditLog, User).join(User, AuditLog.user_id == User.id).where(AuditLog.tenant_id == user.tenant_id)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    q = q.order_by(AuditLog.timestamp.desc())
    total = len(session.exec(q).all())
    results = session.exec(q.offset(skip).limit(limit)).all()
    return {
        "total": total,
        "items": [
            {
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "detail": log.detail,
                "timestamp": log.timestamp.isoformat(),
                "user_name": usr.full_name or usr.email,
            }
            for log, usr in results
        ],
    }

def _check_period_locked(session: Session, tenant_id: int, date_str: str):
    periods = session.exec(select(AccountingPeriod).where(
        AccountingPeriod.tenant_id == tenant_id,
        AccountingPeriod.is_locked == True,
        AccountingPeriod.period_start <= date_str,
        AccountingPeriod.period_end >= date_str,
    )).all()
    if periods:
        raise HTTPException(400, f"Date {date_str} falls in a locked accounting period: {periods[0].name or periods[0].period_start}")

# --- Transactions API ---
@app.post("/api/transactions")
def create_transaction(session: SessionDep, user: CurrentUserDep, tx_data: TransactionCreate):
    # Validate period not locked
    _check_period_locked(session, user.tenant_id, tx_data.date)

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

    log_audit(session, user, "CREATE", "transaction", db_tx.id, {"jv_number": db_tx.jv_number, "date": db_tx.date})
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
                "transaction_id": tx.id,
                "jv_number": tx.jv_number,
                "date": tx.date,
                "description": tx.description,
                "account_name": acc.name,
                "debit": je.debit,
                "credit": je.credit,
                "is_reversed": tx.is_reversed,
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

@app.get("/api/reports/cash-flow")
def cash_flow_statement(session: SessionDep, user: CurrentUserDep,
                         start: str = Query(default=""), end: str = Query(default="")):
    if not start:
        start = f"{DateType.today().year}-01-01"
    if not end:
        end = str(DateType.today())

    accounts = session.exec(select(Account).where(Account.tenant_id == user.tenant_id)).all()

    def acct_net(acct: Account) -> float:
        q = select(JournalEntry).join(Transaction).where(
            JournalEntry.account_id == acct.id,
            JournalEntry.tenant_id == user.tenant_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
        entries = session.exec(q).all()
        if acct.type in ("Asset", "Expense"):
            return sum(e.debit - e.credit for e in entries)
        return sum(e.credit - e.debit for e in entries)

    # Net Income
    net_income = sum(acct_net(a) for a in accounts if a.type == "Revenue") - \
                 sum(acct_net(a) for a in accounts if a.type == "Expense")

    # Working capital changes (AR, AP, Inventory)
    ar_change = sum(acct_net(a) for a in accounts if "receivable" in a.name.lower() or a.code == "1100")
    ap_change = sum(acct_net(a) for a in accounts if "payable" in a.name.lower() or a.code == "2000")
    operating_cash = net_income - ar_change + ap_change

    # Investing: fixed asset movements (Asset accounts not cash/receivable/gst)
    def is_fixed_asset(a: Account) -> bool:
        n = a.name.lower()
        return a.type == "Asset" and not any(x in n for x in ["cash", "bank", "receivable", "advance", "gst", "inventory"])
    investing_items = []
    investing_cash = 0.0
    for a in accounts:
        if is_fixed_asset(a):
            mv = acct_net(a)
            if mv != 0:
                investing_items.append({"name": a.name, "amount": -mv})
                investing_cash -= mv

    # Financing: equity + long-term liabilities (not AP/GST payable)
    def is_financing(a: Account) -> bool:
        if a.type == "Equity":
            return True
        if a.type == "Liability":
            n = a.name.lower()
            return not any(x in n for x in ["payable", "gst", "advance"])
        return False
    financing_items = []
    financing_cash = 0.0
    for a in accounts:
        if is_financing(a):
            mv = acct_net(a)
            if mv != 0:
                financing_items.append({"name": a.name, "amount": mv})
                financing_cash += mv

    # Cash accounts balance at period boundaries
    cash_accounts = [a for a in accounts if "cash" in a.name.lower() or "bank" in a.name.lower()]

    def balance_at(a: Account, as_of: str) -> float:
        q = select(JournalEntry).join(Transaction).where(
            JournalEntry.account_id == a.id,
            JournalEntry.tenant_id == user.tenant_id,
            Transaction.date <= as_of,
        )
        entries = session.exec(q).all()
        if a.type in ("Asset", "Expense"):
            return sum(e.debit - e.credit for e in entries)
        return sum(e.credit - e.debit for e in entries)

    # Find day before start for beginning balance
    try:
        start_dt = DateType.fromisoformat(start)
        day_before = str(start_dt - __import__("datetime").timedelta(days=1))
    except Exception:
        day_before = start

    beginning_balance = sum(balance_at(a, day_before) for a in cash_accounts)
    ending_balance = sum(balance_at(a, end) for a in cash_accounts)
    net_cash_change = operating_cash + investing_cash + financing_cash

    return {
        "period": {"start": start, "end": end},
        "net_income": net_income,
        "operating_adjustments": {"ar_change": ar_change, "ap_change": ap_change},
        "operating_cash": operating_cash,
        "investing_items": investing_items,
        "investing_cash": investing_cash,
        "financing_items": financing_items,
        "financing_cash": financing_cash,
        "net_cash_change": net_cash_change,
        "beginning_balance": beginning_balance,
        "ending_balance": ending_balance,
    }

@app.get("/api/reports/tax-summary")
def tax_summary(session: SessionDep, user: CurrentUserDep,
                start: str = Query(default=""), end: str = Query(default="")):
    if not start:
        start = f"{DateType.today().year}-07-01"
    if not end:
        end = str(DateType.today())

    accounts = session.exec(select(Account).where(Account.tenant_id == user.tenant_id)).all()

    def period_total(acct: Account, side: str) -> float:
        q = select(JournalEntry).join(Transaction).where(
            JournalEntry.account_id == acct.id,
            JournalEntry.tenant_id == user.tenant_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
        entries = session.exec(q).all()
        return sum(getattr(e, side) for e in entries)

    # GST Output = credits to GST Payable (code 2200)
    gst_payable_accts = [a for a in accounts if a.code == "2200" or "gst payable" in a.name.lower()]
    output_gst = sum(period_total(a, "credit") for a in gst_payable_accts)

    # GST Input = debits to GST Receivable (code 1200)
    gst_input_accts = [a for a in accounts if a.code == "1200" or "gst receivable" in a.name.lower()]
    input_gst = sum(period_total(a, "debit") for a in gst_input_accts)

    net_gst = output_gst - input_gst

    # Taxable income = Revenue - Expenses
    revenue = sum(
        sum(period_total(a, "credit") - period_total(a, "debit") for a in [a] if True)
        for a in accounts if a.type == "Revenue"
    )
    expenses = sum(
        sum(period_total(a, "debit") - period_total(a, "credit") for a in [a] if True)
        for a in accounts if a.type == "Expense"
    )
    taxable_income = revenue - expenses

    # Pakistan ITO 2001 slabs (FY 2024-25, non-salaried individual / company)
    def income_tax_ito(income: float) -> float:
        if income <= 600000: return 0
        if income <= 1200000: return (income - 600000) * 0.05
        if income <= 2400000: return 30000 + (income - 1200000) * 0.15
        if income <= 3600000: return 210000 + (income - 2400000) * 0.25
        if income <= 6000000: return 510000 + (income - 3600000) * 0.30
        return 1230000 + (income - 6000000) * 0.35

    estimated_income_tax = income_tax_ito(max(0, taxable_income))

    return {
        "period": {"start": start, "end": end},
        "gst": {
            "output_gst": output_gst,
            "input_gst": input_gst,
            "net_gst_payable": net_gst,
        },
        "income_tax": {
            "revenue": revenue,
            "expenses": expenses,
            "taxable_income": taxable_income,
            "estimated_tax": estimated_income_tax,
            "tax_basis": "ITO 2001 — Non-salaried individual slabs (FY 2024-25)",
        },
    }

@app.post("/api/transactions/{transaction_id}/reverse")
def reverse_transaction(session: SessionDep, user: CurrentUserDep, transaction_id: int):
    txn = session.exec(select(Transaction).where(Transaction.id == transaction_id, Transaction.tenant_id == user.tenant_id)).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.is_reversed:
        raise HTTPException(400, "Transaction already reversed")

    today = str(DateType.today())
    _check_period_locked(session, user.tenant_id, today)

    jv_count = session.exec(select(func.count(Transaction.id)).where(Transaction.tenant_id == user.tenant_id)).one()
    rev_txn = Transaction(
        tenant_id=user.tenant_id,
        jv_number=f"JV-{jv_count + 1:05d}",
        date=today,
        description=f"Reversal of {txn.jv_number}",
    )
    session.add(rev_txn)
    session.flush()

    for je in txn.journal_entries:
        rev_je = JournalEntry(
            tenant_id=user.tenant_id,
            transaction_id=rev_txn.id,
            account_id=je.account_id,
            debit=je.credit,
            credit=je.debit,
        )
        session.add(rev_je)

    txn.is_reversed = True
    txn.reversed_by_id = rev_txn.id
    session.add(txn)
    log_audit(session, user, "REVERSE", "transaction", txn.id, {"original_jv": txn.jv_number, "reversal_jv": rev_txn.jv_number})
    session.commit()
    session.refresh(rev_txn)
    return {"reversal_jv_number": rev_txn.jv_number, "reversal_id": rev_txn.id}

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

