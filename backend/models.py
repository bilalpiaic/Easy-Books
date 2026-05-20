"""
SQLModel tables for Easy-Books.

P0 migration notes:
  - Money columns: float → Decimal stored as NUMERIC(18,4). The `Money` type
    alias preserves the JSON-number API contract for the frontend.
  - JournalEntry has a DB-level CHECK constraint making accidental "both
    debit and credit" or "negative amount" rows impossible.
  - InventoryLayer + Product.avg_cost added so COGS can be posted at
    Weighted-Average cost when stock is sold.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import CheckConstraint, Column, Numeric
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from services.money import Money, ZERO


def money_col(default: Decimal = ZERO, **kw):
    """Numeric(18,4) column with a Decimal default. Centralised so future
    precision tweaks happen in one place."""
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


class Tenant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    base_currency: str = Field(default="USD")  # ISO 4217; reporting currency
    created_at: datetime = Field(default_factory=datetime.utcnow)

    users: List["User"] = Relationship(back_populates="tenant")
    accounts: List["Account"] = Relationship(back_populates="tenant")
    transactions: List["Transaction"] = Relationship(back_populates="tenant")
    settings: List["Settings"] = Relationship(back_populates="tenant")


class User(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner','admin','accountant','viewer')",
            name="ck_user_role",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    role: str = Field(default="viewer", index=True)
    tenant_id: int = Field(foreign_key="tenant.id")

    tenant: Tenant = Relationship(back_populates="users")


class Settings(SQLModel, table=True):
    tenant_id: int = Field(foreign_key="tenant.id", primary_key=True)
    key: str = Field(primary_key=True)
    value: str

    tenant: Tenant = Relationship(back_populates="settings")


class Account(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="unique_account_code_per_tenant"),
        CheckConstraint(
            "type IN ('Asset','Liability','Equity','Revenue','Expense')",
            name="ck_account_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    type: str  # Asset | Liability | Equity | Revenue | Expense (CHECK enforced)
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
    debit: Money = money_col()
    credit: Money = money_col()


class JournalEntry(JournalEntryBase, table=True):
    __table_args__ = (
        # Single-sided rule + non-negative — the DB refuses malformed entries
        # even if a future endpoint forgets to call post_transaction().
        CheckConstraint(
            "debit >= 0 AND credit >= 0 AND NOT (debit > 0 AND credit > 0) AND (debit > 0 OR credit > 0)",
            name="ck_journal_entry_single_sided",
        ),
    )
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
    opening_balance: Money = money_col()
    is_active: bool = Field(default=True)


class Vendor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Money = money_col()
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
    subtotal: Money = money_col()              # in document currency
    gst_rate: Money = money_col(default=Decimal("17"))
    gst_amount: Money = money_col()            # in document currency
    total: Money = money_col()                 # in document currency
    currency: str = Field(default="USD")       # document currency; defaults to tenant base
    exchange_rate: Money = money_col(default=Decimal("1"))  # doc → base; snapshot at issue
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
    subtotal: Money = money_col()              # in document currency
    gst_rate: Money = money_col(default=Decimal("17"))
    gst_amount: Money = money_col()            # in document currency
    total: Money = money_col()                 # in document currency
    currency: str = Field(default="USD")
    exchange_rate: Money = money_col(default=Decimal("1"))
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
    amount: Money = money_col()
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
    amount: Money = money_col()
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
    statement_balance: Money = money_col()
    status: str = Field(default="open")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReconciliationLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    reconciliation_id: int = Field(foreign_key="reconciliation.id")
    journal_entry_id: int = Field(foreign_key="journalentry.id")
    is_matched: bool = Field(default=False)


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    action: str  # CREATE | UPDATE | DELETE | REVERSE
    entity_type: str  # account | customer | vendor | invoice | bill | transaction | ...
    entity_id: Optional[int] = None
    detail: Optional[str] = None  # JSON blob with context
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: Optional[str] = None
    name: str
    unit: str = Field(default="pcs")
    product_type: str = Field(default="service")  # "stock" | "service"
    default_rate: Money = money_col()  # default sale price
    stock_qty: Money = money_col()  # current on-hand quantity (allows fractional units)
    avg_cost: Money = money_col()  # running Weighted-Average cost; updated on each receipt
    reorder_level: Money = money_col()
    stock_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    revenue_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    cogs_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    is_active: bool = Field(default=True)


class InventoryLayer(SQLModel, table=True):
    """One row per stock receipt. Used for audit trail of cost layers."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    qty_received: Money = money_col()
    qty_remaining: Money = money_col()
    unit_cost: Money = money_col()
    source_doc: Optional[str] = None  # e.g. "BILL-0042"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InvoiceLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None
    rate: Money = money_col()
    amount: Money = money_col()  # stored = qty × rate


class BillLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bill_id: int = Field(foreign_key="bill.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None
    rate: Money = money_col()
    amount: Money = money_col()  # stored = qty × rate


class TaxCode(SQLModel, table=True):
    """Per-tenant tax catalog. Output = sales tax (liability), Input = purchase
    tax (receivable). gl_account_id is the GL account the tax leg posts to.
    """
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="unique_tax_code_per_tenant"),
        CheckConstraint("type IN ('output','input')", name="ck_tax_code_type"),
        CheckConstraint("rate >= 0", name="ck_tax_code_rate_nonneg"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)        # e.g. "GST17", "ZERO"
    name: str                            # e.g. "Standard GST 17%"
    rate: Money = money_col()            # percent, e.g. 17
    type: str                            # output | input
    gl_account_id: int = Field(foreign_key="account.id")
    is_active: bool = Field(default=True)


class PaymentAllocation(SQLModel, table=True):
    """Allocates a payment (received or paid) against an invoice/bill.

    Lets a single payment settle multiple invoices and supports partial
    allocations. invoice_id XOR bill_id must be set.
    """
    __table_args__ = (
        CheckConstraint(
            "(invoice_id IS NOT NULL) <> (bill_id IS NOT NULL)",
            name="ck_alloc_one_target",
        ),
        CheckConstraint("amount > 0", name="ck_alloc_amount_pos"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    payment_received_id: Optional[int] = Field(default=None, foreign_key="paymentreceived.id")
    bill_payment_id: Optional[int] = Field(default=None, foreign_key="billpayment.id")
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    bill_id: Optional[int] = Field(default=None, foreign_key="bill.id")
    amount: Money = money_col()
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExchangeRate(SQLModel, table=True):
    """Per-tenant FX rates. rate = how many `to_currency` units one
    `from_currency` unit buys at `date`. Lookups fall back to nearest prior
    date if the exact date is absent.
    """
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "date", "from_currency", "to_currency",
            name="unique_rate_per_pair_per_day",
        ),
        CheckConstraint("rate > 0", name="ck_rate_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    date: str = Field(index=True)
    from_currency: str
    to_currency: str
    rate: Money = money_col(default=Decimal("1"))


class IdempotencyKey(SQLModel, table=True):
    """Caches the response of a POST so clients can safely retry.

    The (tenant_id, key) pair is unique. On a replay, the stored response is
    returned verbatim with the original status code so the caller sees the
    same result without re-running the side effect.
    """
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="unique_idemp_key_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    key: str = Field(index=True)
    method: str
    path: str
    status_code: int
    response_body: str          # JSON-serialised response
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RecurringTemplate(SQLModel, table=True):
    """Recurring journal-entry template. The /scheduler endpoint reads due
    rows and posts a Transaction copy per schedule firing."""
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('daily','weekly','monthly','quarterly','yearly')",
            name="ck_recurring_frequency",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    description: Optional[str] = None
    frequency: str                       # daily | weekly | monthly | quarterly | yearly
    next_run: str                        # ISO date
    last_run: Optional[str] = None
    is_active: bool = Field(default=True)
    # JSON-serialised list[{account_id, debit, credit}]
    entries_json: str


# --- API DTOs (used by routers for request bodies & responses) ---

class JournalEntryCreate(JournalEntryBase):
    tenant_id: Optional[int] = None  # set by server from JWT


class TransactionCreate(TransactionBase):
    tenant_id: Optional[int] = None  # set by server from JWT
    entries: List[JournalEntryCreate]


class TransactionRead(TransactionBase):
    id: int
    jv_number: str
    entries: List["JournalEntryRead"]


class JournalEntryRead(JournalEntryBase):
    account_name: str
    account_type: str
