import os
import csv
import io
from decimal import Decimal
from typing import Annotated, List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlmodel import Session, select, func
from db import engine, get_session, create_db_and_tables, seed_data
from models import (
    Account, Transaction, JournalEntry, Settings, User, Tenant,
    Customer, Vendor, Invoice, Bill, PaymentReceived, BillPayment, BankAccount,
    Reconciliation, ReconciliationLine, AccountingPeriod, AuditLog,
    Product, InvoiceLine, BillLine, InventoryLayer,
    TransactionCreate, TransactionRead, JournalEntryRead
)
import json as _json
from auth import SECRET_KEY, ALGORITHM, get_password_hash, verify_password, create_access_token
from services.money import D, ZERO, money, sum_money
from services.posting import EntryInput, post_transaction
from services.inventory import record_purchase, consume_stock

app = FastAPI(title="Easy-Books API")

_allowed_origins = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
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
    opening_balance: Decimal = Decimal("0")

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Optional[Decimal] = None
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
    opening_balance: Decimal = Decimal("0")

class VendorUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Optional[Decimal] = None
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

# --- Products API ---
class ProductCreate(BaseModel):
    code: Optional[str] = None
    name: str
    unit: str = "pcs"
    product_type: str = "service"
    default_rate: Decimal = Decimal("0")
    reorder_level: Decimal = Decimal("0")
    stock_account_id: Optional[int] = None
    revenue_account_id: Optional[int] = None
    cogs_account_id: Optional[int] = None

@app.get("/api/products")
def list_products(
    session: SessionDep,
    user: CurrentUserDep,
    search: str = "",
    product_type: str = "",
    skip: int = 0,
    limit: int = 100,
):
    q = select(Product).where(Product.tenant_id == user.tenant_id)
    if search:
        q = q.where((Product.name.ilike(f"%{search}%")) | (Product.code.ilike(f"%{search}%")))
    if product_type:
        q = q.where(Product.product_type == product_type)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(Product.name).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}

@app.get("/api/products/stock-summary")
def products_stock_summary(session: SessionDep, user: CurrentUserDep):
    items = session.exec(select(Product).where(Product.tenant_id == user.tenant_id, Product.product_type == "stock")).all()
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "unit": p.unit,
            "stock_qty": p.stock_qty,
            "reorder_level": p.reorder_level,
            "default_rate": p.default_rate,
            "value": round(p.stock_qty * p.default_rate, 2),
            "low_stock": p.stock_qty <= p.reorder_level,
        }
        for p in items
    ]

@app.post("/api/products", status_code=201)
def create_product(session: SessionDep, user: CurrentUserDep, body: ProductCreate):
    p = Product(tenant_id=user.tenant_id, **body.model_dump())
    session.add(p)
    log_audit(session, user, "CREATE", "product", None, {"name": body.name})
    session.commit()
    session.refresh(p)
    return p

@app.put("/api/products/{product_id}")
def update_product(session: SessionDep, user: CurrentUserDep, product_id: int, body: ProductCreate):
    p = session.exec(select(Product).where(Product.id == product_id, Product.tenant_id == user.tenant_id)).first()
    if not p:
        raise HTTPException(404, "Product not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    session.add(p)
    log_audit(session, user, "UPDATE", "product", p.id, {"name": p.name})
    session.commit()
    session.refresh(p)
    return p

@app.delete("/api/products/{product_id}", status_code=204)
def delete_product(session: SessionDep, user: CurrentUserDep, product_id: int):
    p = session.exec(select(Product).where(Product.id == product_id, Product.tenant_id == user.tenant_id)).first()
    if not p:
        raise HTTPException(404, "Product not found")
    used_in_invoice = session.exec(select(InvoiceLine).where(InvoiceLine.product_id == product_id)).first()
    used_in_bill = session.exec(select(BillLine).where(BillLine.product_id == product_id)).first()
    if used_in_invoice or used_in_bill:
        raise HTTPException(400, "Cannot delete product used in invoice or bill lines")
    log_audit(session, user, "DELETE", "product", p.id, {"name": p.name})
    session.delete(p)
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

class InvoiceLineCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")

class InvoiceCreate(BaseModel):
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    issue_date: str
    due_date: str
    description: Optional[str] = None
    lines: List[InvoiceLineCreate] = []
    gst_rate: Decimal = Decimal("17")
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
    result_items = []
    for inv in items:
        d = inv.model_dump()
        d["lines"] = [l.model_dump() for l in session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)).all()]
        result_items.append(d)
    return {"total": total, "items": result_items}

@app.post("/api/invoices", status_code=201)
def create_invoice(session: SessionDep, user: CurrentUserDep, body: InvoiceCreate):
    prefix_row = session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id, Settings.key == "invoice_prefix")).first()
    prefix = prefix_row.value if prefix_row else "INV"

    subtotal = money(sum_money(D(l.qty) * D(l.rate) for l in body.lines))
    gst_amount = money(subtotal * D(body.gst_rate) / D("100"))
    total = money(subtotal + gst_amount)

    cname = body.customer_name
    if body.customer_id:
        c = session.exec(select(Customer).where(Customer.id == body.customer_id, Customer.tenant_id == user.tenant_id)).first()
        if not c:
            raise HTTPException(404, "Customer not found")
        cname = c.name

    invoice = Invoice(
        tenant_id=user.tenant_id,
        number=_next_invoice_number(session, user.tenant_id, prefix),
        customer_id=body.customer_id,
        customer_name=cname,
        issue_date=body.issue_date,
        due_date=body.due_date,
        description=body.description,
        subtotal=subtotal,
        gst_rate=D(body.gst_rate),
        gst_amount=gst_amount,
        total=total,
        status="draft",
        ar_account_id=body.ar_account_id,
        revenue_account_id=body.revenue_account_id,
    )
    session.add(invoice)
    session.flush()

    # Persist line items; for stock-type lines, relieve inventory at WAvg cost
    # and accumulate total COGS so we can post Dr COGS / Cr Inventory once.
    total_cogs = ZERO
    for line_data in body.lines:
        amount = money(D(line_data.qty) * D(line_data.rate))
        il = InvoiceLine(
            invoice_id=invoice.id,
            product_id=line_data.product_id,
            description=line_data.description,
            qty=D(line_data.qty),
            unit=line_data.unit,
            rate=D(line_data.rate),
            amount=amount,
        )
        session.add(il)
        if line_data.product_id:
            prod = session.exec(select(Product).where(Product.id == line_data.product_id, Product.tenant_id == user.tenant_id)).first()
            if prod and prod.product_type == "stock":
                total_cogs += consume_stock(
                    session,
                    tenant_id=user.tenant_id,
                    product_id=prod.id,
                    qty=D(line_data.qty),
                )

    # Resolve GL accounts (tenant-scoped).
    ar_acc = session.get(Account, body.ar_account_id) if body.ar_account_id else \
        _get_or_create_account(session, user.tenant_id, "1100", "Accounts Receivable", "Asset")
    rev_acc = session.get(Account, body.revenue_account_id) if body.revenue_account_id else \
        _get_or_create_account(session, user.tenant_id, "4000", "Sales Revenue", "Revenue")

    # Build revenue-side entries.
    entries = [EntryInput(account_id=ar_acc.id, debit=total)]
    if gst_amount > 0:
        gst_acc = _get_or_create_account(session, user.tenant_id, "2200", "GST Payable (Output)", "Liability")
        entries.append(EntryInput(account_id=rev_acc.id, credit=subtotal))
        entries.append(EntryInput(account_id=gst_acc.id, credit=gst_amount))
    else:
        entries.append(EntryInput(account_id=rev_acc.id, credit=total))

    txn = post_transaction(
        session, user,
        date=invoice.issue_date,
        description=f"Invoice {invoice.number} — {cname or ''}",
        entries=entries,
        audit_entity_type="invoice",
        audit_detail={"invoice_number": invoice.number, "total": str(total)},
    )
    invoice.transaction_id = txn.id
    session.add(invoice)

    # COGS posting (a separate JV so the sale and the cost-relief stay
    # individually inspectable, and so reversing one doesn't auto-reverse
    # the other inappropriately).
    if total_cogs > 0:
        cogs_acc = _get_or_create_account(session, user.tenant_id, "5010", "Cost of Goods Sold", "Expense")
        inv_acc = _get_or_create_account(session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset")
        post_transaction(
            session, user,
            date=invoice.issue_date,
            description=f"COGS for {invoice.number}",
            entries=[
                EntryInput(account_id=cogs_acc.id, debit=total_cogs),
                EntryInput(account_id=inv_acc.id, credit=total_cogs),
            ],
            audit_entity_type="invoice",
            audit_detail={"invoice_number": invoice.number, "cogs": str(total_cogs)},
        )

    log_audit(session, user, "CREATE", "invoice", invoice.id, {"number": invoice.number, "total": str(total)})
    session.commit()
    session.refresh(invoice)

    lines_out = session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)).all()
    result = invoice.model_dump()
    result["lines"] = [l.model_dump() for l in lines_out]
    return result

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

class BillLineCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")

class BillCreate(BaseModel):
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    bill_date: str
    due_date: str
    description: Optional[str] = None
    lines: List[BillLineCreate] = []
    gst_rate: Decimal = Decimal("17")
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

    subtotal = money(sum_money(D(l.qty) * D(l.rate) for l in body.lines))
    gst_amount = money(subtotal * D(body.gst_rate) / D("100"))
    total = money(subtotal + gst_amount)

    vname = body.vendor_name
    if body.vendor_id:
        v = session.exec(select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)).first()
        if not v:
            raise HTTPException(404, "Vendor not found")
        vname = v.name

    bill = Bill(
        tenant_id=user.tenant_id,
        number=_next_bill_number(session, user.tenant_id, prefix),
        vendor_id=body.vendor_id,
        vendor_name=vname,
        bill_date=body.bill_date,
        due_date=body.due_date,
        description=body.description,
        subtotal=subtotal,
        gst_rate=D(body.gst_rate),
        gst_amount=gst_amount,
        total=total,
        status="draft",
        ap_account_id=body.ap_account_id,
        expense_account_id=body.expense_account_id,
    )
    session.add(bill)
    session.flush()

    # Persist line items; for stock-type products, append to the WAvg cost layer.
    total_stock_value = ZERO
    for line_data in body.lines:
        line_qty = D(line_data.qty)
        line_rate = D(line_data.rate)
        amount = money(line_qty * line_rate)
        bl = BillLine(
            bill_id=bill.id,
            product_id=line_data.product_id,
            description=line_data.description,
            qty=line_qty,
            unit=line_data.unit,
            rate=line_rate,
            amount=amount,
        )
        session.add(bl)
        if line_data.product_id:
            prod = session.exec(select(Product).where(Product.id == line_data.product_id, Product.tenant_id == user.tenant_id)).first()
            if prod and prod.product_type == "stock":
                record_purchase(
                    session,
                    tenant_id=user.tenant_id,
                    product_id=prod.id,
                    qty=line_qty,
                    unit_cost=line_rate,
                    source_doc=bill.number,
                )
                total_stock_value += amount

    # Resolve GL accounts.
    ap_acc = session.get(Account, body.ap_account_id) if body.ap_account_id else \
        _get_or_create_account(session, user.tenant_id, "2000", "Accounts Payable", "Liability")
    # When the bill has stock lines, debit Inventory for the stock portion and
    # only the non-stock remainder hits the expense account.
    non_stock_subtotal = subtotal - total_stock_value
    entries: list[EntryInput] = [EntryInput(account_id=ap_acc.id, credit=total)]
    if total_stock_value > 0:
        inv_acc = _get_or_create_account(session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset")
        entries.append(EntryInput(account_id=inv_acc.id, debit=total_stock_value))
    if non_stock_subtotal > 0:
        exp_acc = session.get(Account, body.expense_account_id) if body.expense_account_id else \
            _get_or_create_account(session, user.tenant_id, "5000", "General Expenses", "Expense")
        entries.append(EntryInput(account_id=exp_acc.id, debit=non_stock_subtotal))
    if gst_amount > 0:
        gst_input_acc = _get_or_create_account(session, user.tenant_id, "1250", "GST Receivable (Input)", "Asset")
        entries.append(EntryInput(account_id=gst_input_acc.id, debit=gst_amount))

    txn = post_transaction(
        session, user,
        date=bill.bill_date,
        description=f"Bill {bill.number} — {vname or ''}",
        entries=entries,
        audit_entity_type="bill",
        audit_detail={"bill_number": bill.number, "total": str(total)},
    )
    bill.transaction_id = txn.id
    session.add(bill)

    log_audit(session, user, "CREATE", "bill", bill.id, {"number": bill.number, "total": str(total)})
    session.commit()
    session.refresh(bill)

    lines_out = session.exec(select(BillLine).where(BillLine.bill_id == bill.id)).all()
    result = bill.model_dump()
    result["lines"] = [l.model_dump() for l in lines_out]
    return result

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
    amount: Decimal
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
    amount = money(body.amount)
    cname = body.customer_name
    if body.invoice_id:
        inv = session.get(Invoice, body.invoice_id)
        if inv and inv.tenant_id == user.tenant_id:
            if not cname:
                cname = inv.customer_name
            inv.status = "paid"
            session.add(inv)

    cash_acc = session.get(Account, body.cash_account_id) if body.cash_account_id else \
        _get_or_create_account(session, user.tenant_id, "1000", "Cash in Hand", "Asset")
    ar_acc = _get_or_create_account(session, user.tenant_id, "1100", "Accounts Receivable", "Asset")

    txn = post_transaction(
        session, user,
        date=body.payment_date,
        description=f"Payment received — {cname or ''} {body.reference or ''}".strip(),
        entries=[
            EntryInput(account_id=cash_acc.id, debit=amount),
            EntryInput(account_id=ar_acc.id, credit=amount),
        ],
        reference=body.reference,
        payment_method=body.method,
        audit_entity_type="payment_received",
        audit_detail={"amount": str(amount), "invoice_id": body.invoice_id},
    )

    pmt = PaymentReceived(
        tenant_id=user.tenant_id,
        invoice_id=body.invoice_id,
        customer_name=cname,
        payment_date=body.payment_date,
        amount=amount,
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
    amount: Decimal
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
    amount = money(body.amount)
    vname = body.vendor_name
    if body.bill_id:
        b = session.get(Bill, body.bill_id)
        if b and b.tenant_id == user.tenant_id:
            if not vname:
                vname = b.vendor_name
            b.status = "paid"
            session.add(b)

    cash_acc = session.get(Account, body.cash_account_id) if body.cash_account_id else \
        _get_or_create_account(session, user.tenant_id, "1000", "Cash in Hand", "Asset")
    ap_acc = _get_or_create_account(session, user.tenant_id, "2000", "Accounts Payable", "Liability")

    txn = post_transaction(
        session, user,
        date=body.payment_date,
        description=f"Bill payment — {vname or ''} {body.reference or ''}".strip(),
        entries=[
            EntryInput(account_id=ap_acc.id, debit=amount),
            EntryInput(account_id=cash_acc.id, credit=amount),
        ],
        reference=body.reference,
        payment_method=body.method,
        audit_entity_type="bill_payment",
        audit_detail={"amount": str(amount), "bill_id": body.bill_id},
    )

    bp = BillPayment(
        tenant_id=user.tenant_id,
        bill_id=body.bill_id,
        vendor_name=vname,
        payment_date=body.payment_date,
        amount=amount,
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
    statement_balance: Decimal

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
def list_accounts(
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

# --- Transactions API ---
@app.post("/api/transactions")
def create_transaction(session: SessionDep, user: CurrentUserDep, tx_data: TransactionCreate):
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
    query = (
        select(Transaction, JournalEntry, Account)
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .join(Account, JournalEntry.account_id == Account.id)
        .where(Transaction.tenant_id == user.tenant_id)
    )

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
    
    ar_outstanding = session.exec(
        select(func.sum(Invoice.total)).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status.in_(["draft", "sent", "overdue"])
        )
    ).one() or 0.0

    ap_outstanding = session.exec(
        select(func.sum(Bill.total)).where(
            Bill.tenant_id == user.tenant_id,
            Bill.status.in_(["draft", "received", "overdue"])
        )
    ).one() or 0.0

    overdue_invoices = session.exec(
        select(func.count(Invoice.id)).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status == "overdue"
        )
    ).one() or 0

    unpaid_bills = session.exec(
        select(func.count(Bill.id)).where(
            Bill.tenant_id == user.tenant_id,
            Bill.status.in_(["draft", "received", "overdue"])
        )
    ).one() or 0

    low_stock = session.exec(
        select(func.count(Product.id)).where(
            Product.tenant_id == user.tenant_id,
            Product.product_type == "stock",
            Product.stock_qty <= Product.reorder_level,
        )
    ).one() or 0

    return {
        "summary": {
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "transaction_count": transaction_count,
            "ar_outstanding": ar_outstanding,
            "ap_outstanding": ap_outstanding,
            "overdue_invoices": overdue_invoices,
            "unpaid_bills": unpaid_bills,
            "low_stock_items": low_stock,
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

@app.get("/api/reports/dashboard/charts")
def get_dashboard_charts(
    session: SessionDep,
    user: CurrentUserDep,
    months: int = 12,
):
    from datetime import date, timedelta
    today = date.today()
    # Build last N months list
    result_months = []
    for i in range(months - 1, -1, -1):
        d = date(today.year, today.month, 1)
        # go back i months
        m = d.month - i
        y = d.year
        while m <= 0:
            m += 12; y -= 1
        result_months.append((y, m))

    monthly = []
    for y, m in result_months:
        start = f"{y:04d}-{m:02d}-01"
        if m == 12:
            end = f"{y+1:04d}-01-01"
        else:
            end = f"{y:04d}-{m+1:02d}-01"
        label = f"{y}-{m:02d}"

        je_q = session.exec(
            select(JournalEntry, Account).join(Account).join(Transaction).where(
                Transaction.tenant_id == user.tenant_id,
                Transaction.date >= start,
                Transaction.date < end,
            )
        ).all()
        rev = sum(e.credit - e.debit for e, a in je_q if a.type == "Revenue")
        exp = sum(e.debit - e.credit for e, a in je_q if a.type == "Expense")
        monthly.append({"month": label, "revenue": round(rev, 2), "expenses": round(exp, 2), "profit": round(rev - exp, 2)})

    # Expense breakdown by account (top 8)
    exp_q = session.exec(
        select(Account.name, func.sum(JournalEntry.debit - JournalEntry.credit).label("total"))
        .join(JournalEntry, Account.id == JournalEntry.account_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Account.type == "Expense",
            Transaction.date >= f"{today.year:04d}-01-01",
        )
        .group_by(Account.id)
        .order_by(func.sum(JournalEntry.debit - JournalEntry.credit).desc())
        .limit(8)
    ).all()
    expense_breakdown = [
        {"account": name, "amount": round(float(total or 0), 2)}
        for name, total in exp_q if (total or 0) > 0
    ]

    # Top 5 customers by invoice total
    top_customers = session.exec(
        select(Customer.name, func.sum(Invoice.total).label("total"))
        .join(Invoice, Invoice.customer_id == Customer.id)
        .where(Customer.tenant_id == user.tenant_id)
        .group_by(Customer.id)
        .order_by(func.sum(Invoice.total).desc())
        .limit(5)
    ).all()
    top_cust = [{"name": n, "total": round(float(t or 0), 2)} for n, t in top_customers]

    return {
        "monthly": monthly,
        "expense_breakdown": expense_breakdown,
        "top_customers": top_cust,
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
    txn = session.exec(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.tenant_id == user.tenant_id
        )
    ).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.is_reversed:
        raise HTTPException(400, "Transaction already reversed")

    today = str(DateType.today())
    rev_txn = post_transaction(
        session, user,
        date=today,
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

# ── CSV Import helpers ────────────────────────────────────────────────────────

SAMPLE_CSVS: dict[str, list[list[str]]] = {
    "transactions": [
        ["date", "description", "account_code", "debit", "credit"],
        ["2025-01-01", "Cash sale", "1000", "5000", "0"],
        ["2025-01-01", "Cash sale", "4000", "0", "5000"],
        ["2025-01-02", "Office supplies", "5100", "1500", "0"],
        ["2025-01-02", "Office supplies", "1000", "0", "1500"],
    ],
    "accounts": [
        ["code", "name", "type"],
        ["1050", "Petty Cash", "Asset"],
        ["2200", "Accrued Liabilities", "Liability"],
        ["5200", "Depreciation Expense", "Expense"],
    ],
    "customers": [
        ["name", "email", "phone", "address", "opening_balance"],
        ["Ahmed Traders", "ahmed@example.com", "0300-1234567", "Karachi", "0"],
        ["Bilal Enterprises", "bilal@example.com", "0321-9876543", "Lahore", "50000"],
    ],
    "vendors": [
        ["name", "email", "phone", "address", "opening_balance"],
        ["Ali Suppliers", "ali@supplier.com", "0311-1111111", "Islamabad", "0"],
        ["Khan & Sons", "khan@supplier.com", "0333-2222222", "Faisalabad", "25000"],
    ],
    "products": [
        ["code", "name", "unit", "product_type", "default_rate", "reorder_level"],
        ["PRD-001", "Widget A", "pcs", "stock", "1500", "50"],
        ["PRD-002", "Consulting Hour", "hrs", "service", "5000", "0"],
        ["PRD-003", "Raw Cotton", "kg", "stock", "350", "200"],
    ],
}


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig").strip()
    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]


def _csv_response(entity: str) -> StreamingResponse:
    rows = SAMPLE_CSVS.get(entity)
    if not rows:
        raise HTTPException(404, "No sample for this entity")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sample_{entity}.csv"'},
    )


@app.get("/api/import/{entity}/sample")
def download_sample(entity: str, _user: CurrentUserDep):
    return _csv_response(entity)


# ── Import: Chart of Accounts ─────────────────────────────────────────────────

@app.post("/api/import/accounts")
async def import_accounts(
    file: UploadFile,
    session: SessionDep,
    user: CurrentUserDep,
):
    VALID_TYPES = {"Asset", "Liability", "Equity", "Revenue", "Expense"}
    rows = _parse_csv(await file.read())
    imported, errors = 0, []
    for i, row in enumerate(rows, start=2):
        code = (row.get("code") or "").strip()
        name = (row.get("name") or "").strip()
        atype = (row.get("type") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        if atype not in VALID_TYPES:
            errors.append({"row": i, "message": f"type must be one of {sorted(VALID_TYPES)}"}); continue
        if code:
            existing = session.exec(select(Account).where(Account.code == code, Account.tenant_id == user.tenant_id)).first()
            if existing:
                errors.append({"row": i, "message": f"account code '{code}' already exists"}); continue
        session.add(Account(tenant_id=user.tenant_id, code=code or None, name=name, type=atype))
        imported += 1
    session.commit()
    log_audit(session, user, "import", "Account", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


# ── Import: Customers ─────────────────────────────────────────────────────────

@app.post("/api/import/customers")
async def import_customers(
    file: UploadFile,
    session: SessionDep,
    user: CurrentUserDep,
):
    rows = _parse_csv(await file.read())
    imported, errors = 0, []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        try:
            ob = float(row.get("opening_balance") or "0")
        except ValueError:
            errors.append({"row": i, "message": "opening_balance must be a number"}); continue
        session.add(Customer(
            tenant_id=user.tenant_id,
            name=name,
            email=(row.get("email") or "").strip() or None,
            phone=(row.get("phone") or "").strip() or None,
            address=(row.get("address") or "").strip() or None,
            opening_balance=ob,
            is_active=True,
        ))
        imported += 1
    session.commit()
    log_audit(session, user, "import", "Customer", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


# ── Import: Vendors ───────────────────────────────────────────────────────────

@app.post("/api/import/vendors")
async def import_vendors(
    file: UploadFile,
    session: SessionDep,
    user: CurrentUserDep,
):
    rows = _parse_csv(await file.read())
    imported, errors = 0, []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        try:
            ob = float(row.get("opening_balance") or "0")
        except ValueError:
            errors.append({"row": i, "message": "opening_balance must be a number"}); continue
        session.add(Vendor(
            tenant_id=user.tenant_id,
            name=name,
            email=(row.get("email") or "").strip() or None,
            phone=(row.get("phone") or "").strip() or None,
            address=(row.get("address") or "").strip() or None,
            opening_balance=ob,
            is_active=True,
        ))
        imported += 1
    session.commit()
    log_audit(session, user, "import", "Vendor", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


# ── Import: Products ──────────────────────────────────────────────────────────

@app.post("/api/import/products")
async def import_products(
    file: UploadFile,
    session: SessionDep,
    user: CurrentUserDep,
):
    VALID_TYPES = {"stock", "service"}
    VALID_UNITS = {"pcs", "kg", "mtr", "hrs", "ltr", "box", "doz"}
    rows = _parse_csv(await file.read())
    imported, errors = 0, []
    for i, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": i, "message": "name is required"}); continue
        ptype = (row.get("product_type") or "service").strip().lower()
        if ptype not in VALID_TYPES:
            errors.append({"row": i, "message": f"product_type must be 'stock' or 'service'"}); continue
        unit = (row.get("unit") or "pcs").strip().lower()
        if unit not in VALID_UNITS:
            unit = "pcs"
        try:
            rate = float(row.get("default_rate") or "0")
            reorder = float(row.get("reorder_level") or "0")
        except ValueError:
            errors.append({"row": i, "message": "default_rate and reorder_level must be numbers"}); continue
        session.add(Product(
            tenant_id=user.tenant_id,
            code=(row.get("code") or "").strip() or None,
            name=name,
            unit=unit,
            product_type=ptype,
            default_rate=rate,
            reorder_level=reorder,
            stock_qty=0.0,
            is_active=True,
        ))
        imported += 1
    session.commit()
    log_audit(session, user, "import", "Product", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


# ── Import: Journal Transactions ──────────────────────────────────────────────
# CSV rows are grouped by date+description into one Transaction.
# Each row = one JournalEntry line. Dr = Cr must balance per group.

@app.post("/api/import/transactions")
async def import_transactions(
    file: UploadFile,
    session: SessionDep,
    user: CurrentUserDep,
):
    rows = _parse_csv(await file.read())
    errors: list[dict] = []
    imported = 0

    # Group rows into transactions by (date, description)
    groups: dict[tuple, list[dict]] = {}
    for i, row in enumerate(rows, start=2):
        date = (row.get("date") or "").strip()
        desc = (row.get("description") or "").strip()
        if not date or not desc:
            errors.append({"row": i, "message": "date and description are required"}); continue
        key = (date, desc, i // 1000)  # crude grouping: same date+desc adjacent rows
        # Use date+description as group key; collect sequential rows with same key
        gkey = (date, desc)
        groups.setdefault(gkey, []).append((i, row))

    for (date, desc), group_rows in groups.items():
        entries: list[EntryInput] = []
        group_errors = []
        for i, row in group_rows:
            acct_code = (row.get("account_code") or "").strip()
            if not acct_code:
                group_errors.append({"row": i, "message": "account_code is required"}); continue
            acct = session.exec(select(Account).where(
                Account.tenant_id == user.tenant_id,
                Account.code == acct_code,
            )).first()
            if not acct:
                group_errors.append({"row": i, "message": f"account code '{acct_code}' not found"}); continue
            try:
                dr = D(row.get("debit") or "0")
                cr = D(row.get("credit") or "0")
            except Exception:
                group_errors.append({"row": i, "message": "debit and credit must be numbers"}); continue
            if dr == 0 and cr == 0:
                continue  # blank rows are skipped, not errors
            entries.append(EntryInput(account_id=acct.id, debit=dr, credit=cr))

        if group_errors:
            errors.extend(group_errors); continue
        if not entries:
            continue

        try:
            post_transaction(
                session, user,
                date=date,
                description=desc,
                entries=entries,
                audit_entity_type="transaction_import",
            )
            imported += 1
        except HTTPException as ex:
            errors.append({"row": group_rows[0][0], "message": ex.detail})

    session.commit()
    log_audit(session, user, "import", "Transaction", detail={"imported": imported, "errors": len(errors)})
    session.commit()
    return {"imported": imported, "errors": errors}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)

