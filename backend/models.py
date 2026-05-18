from datetime import datetime
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

class Tenant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    users: List["User"] = Relationship(back_populates="tenant")
    accounts: List["Account"] = Relationship(back_populates="tenant")
    transactions: List["Transaction"] = Relationship(back_populates="tenant")
    settings: List["Settings"] = Relationship(back_populates="tenant")

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    tenant_id: int = Field(foreign_key="tenant.id")

    tenant: Tenant = Relationship(back_populates="users")

class Settings(SQLModel, table=True):
    tenant_id: int = Field(foreign_key="tenant.id", primary_key=True)
    key: str = Field(primary_key=True)
    value: str
    
    tenant: Tenant = Relationship(back_populates="settings")

class Account(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="unique_account_code_per_tenant"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    type: str # Asset, Liability, Equity, Revenue, Expense
    parent_id: Optional[int] = Field(default=None, foreign_key="account.id")

    tenant: Tenant = Relationship(back_populates="accounts")
    journal_entries: List["JournalEntry"] = Relationship(back_populates="account")

class AccountingPeriod(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    period_start: str
    period_end: str
    is_locked: bool = Field(default=False)
    name: Optional[str] = None

class TransactionBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    date: str
    description: Optional[str] = None
    reference: Optional[str] = None
    party: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None

class Transaction(TransactionBase, table=True):
    __table_args__ = (UniqueConstraint("tenant_id", "jv_number", name="unique_jv_number_per_tenant"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    jv_number: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_reversed: bool = Field(default=False)
    reversed_by_id: Optional[int] = Field(default=None)

    tenant: Tenant = Relationship(back_populates="transactions")
    journal_entries: List["JournalEntry"] = Relationship(back_populates="transaction", cascade_delete=True)

class JournalEntryBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    account_id: int = Field(foreign_key="account.id")
    debit: float = Field(default=0.0)
    credit: float = Field(default=0.0)

class JournalEntry(JournalEntryBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transaction.id", ondelete="CASCADE")

    transaction: Transaction = Relationship(back_populates="journal_entries")
    account: Account = Relationship(back_populates="journal_entries")

class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: float = Field(default=0.0)
    is_active: bool = Field(default=True)

class Vendor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: float = Field(default=0.0)
    is_active: bool = Field(default=True)

class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    customer_name: Optional[str] = None
    issue_date: str
    due_date: str
    description: Optional[str] = None
    subtotal: float = Field(default=0.0)
    gst_rate: float = Field(default=17.0)
    gst_amount: float = Field(default=0.0)
    total: float = Field(default=0.0)
    status: str = Field(default="draft")
    ar_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    revenue_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")

class Bill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")
    vendor_name: Optional[str] = None
    bill_date: str
    due_date: str
    description: Optional[str] = None
    subtotal: float = Field(default=0.0)
    gst_rate: float = Field(default=17.0)
    gst_amount: float = Field(default=0.0)
    total: float = Field(default=0.0)
    status: str = Field(default="draft")
    ap_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    expense_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")

class PaymentReceived(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    customer_name: Optional[str] = None
    payment_date: str
    amount: float
    method: str = Field(default="cash")
    reference: Optional[str] = None
    cash_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")

class BillPayment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    bill_id: Optional[int] = Field(default=None, foreign_key="bill.id")
    vendor_name: Optional[str] = None
    payment_date: str
    amount: float
    method: str = Field(default="cash")
    reference: Optional[str] = None
    cash_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")

class BankAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    coa_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    is_active: bool = Field(default=True)

class Reconciliation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    bank_account_id: int = Field(foreign_key="bankaccount.id")
    period_start: str
    period_end: str
    statement_balance: float = Field(default=0.0)
    status: str = Field(default="open")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ReconciliationLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    reconciliation_id: int = Field(foreign_key="reconciliation.id")
    journal_entry_id: int = Field(foreign_key="journalentry.id")
    is_matched: bool = Field(default=False)

# API Models
class JournalEntryCreate(JournalEntryBase):
    pass

class TransactionCreate(TransactionBase):
    entries: List[JournalEntryCreate]

class TransactionRead(TransactionBase):
    id: int
    jv_number: str
    entries: List["JournalEntryRead"]

class JournalEntryRead(JournalEntryBase):
    account_name: str
    account_type: str
