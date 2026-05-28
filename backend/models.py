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

from sqlalchemy import CheckConstraint, Column, Index, Numeric
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from services.money import Money, ZERO


def money_col(default: Decimal = ZERO, **kw):
    """Numeric(18,4) column with a Decimal default. Centralised so future
    precision tweaks happen in one place."""
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


class Tenant(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "business_model IN ('simple','services','trader','manufacturing','telecom_franchise')",
            name="ck_tenant_business_model",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    base_currency: str = Field(default="USD")  # ISO 4217; reporting currency
    business_model: str = Field(default="simple", index=True)
    # JSON-serialised list of enabled module names. Derived from business_model
    # at signup but persisted so it can be edited later (e.g. a 'simple' tenant
    # can enable the 'inventory' module without becoming a 'trader').
    enabled_modules: str = Field(default="[]")
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
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = Field(default=True)
    # When true, the user must set a new password before doing anything else
    # (admin-created accounts with a temporary password).
    must_change_password: bool = Field(default=False)
    role: str = Field(default="viewer", index=True)
    tenant_id: int = Field(foreign_key="tenant.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    tenant: Tenant = Relationship(back_populates="users")


class UserInvite(SQLModel, table=True):
    """Pending invitation for a new user to join a tenant. The recipient
    accepts by POSTing the token + a chosen password to
    /api/auth/accept-invite, which materialises an active User row."""
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner','admin','accountant','viewer')",
            name="ck_invite_role",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    email: str = Field(index=True)
    role: str = Field(default="viewer")
    token: str = Field(unique=True, index=True)
    invited_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    # Memorandum accounts (e.g. 1210 Customer Goods on Hand, 2150 Customer
    # Goods Liability) are excluded from formal A=L+E totals on the balance
    # sheet and shown in a separate "Memorandum / Custodial" section.
    is_memo: bool = Field(default=False)

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


class PaymentTerm(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str                  # "NET30"
    name: str                  # "Net 30 Days"
    days: int                  # 30


class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Money = money_col()
    is_active: bool = Field(default=True)
    payment_term_id: Optional[int] = Field(default=None, foreign_key="paymentterm.id")


class Vendor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Money = money_col()
    is_active: bool = Field(default=True)
    payment_term_id: Optional[int] = Field(default=None, foreign_key="paymentterm.id")


class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    customer_name: Optional[str] = None
    issue_date: str
    due_date: str
    description: Optional[str] = None
    notes: Optional[str] = None              # customer-facing; printed on invoice
    internal_memo: Optional[str] = None     # staff-only; not printed
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
    payment_term_id: Optional[int] = Field(default=None, foreign_key="paymentterm.id")


class Bill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")
    vendor_name: Optional[str] = None
    bill_date: str
    due_date: str
    description: Optional[str] = None
    notes: Optional[str] = None              # vendor-facing; printed on bill
    internal_memo: Optional[str] = None     # staff-only; not printed
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
    payment_term_id: Optional[int] = Field(default=None, foreign_key="paymentterm.id")


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


class BomHeader(SQLModel, table=True):
    """Bill of Materials — the recipe for producing one batch of an output.

    A BoM is versioned: every time the recipe changes you bump `version` and
    flag the new row `is_active=True` (and the old one False). Production
    orders pin a specific version so cost reconstruction stays accurate even
    after the BoM evolves.
    """
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "output_product_id", "version",
            name="unique_bom_per_product_version",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    output_product_id: int = Field(foreign_key="product.id", index=True)
    output_qty: Money = money_col(default=Decimal("1"))  # produces N output units per recipe run
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    description: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BomLine(SQLModel, table=True):
    """One component line of a BoM.

    `source` distinguishes manufacturer-owned consumables from customer-
    supplied inputs:
      own_stock        — pulled from a raw-material store; costs flow into
                         WIP and ultimately COGS
      customer_supplied — pulled from the customer-goods godown; cost is
                         zero to us (custodial), GL impact via memo accounts
                         only
    """
    __table_args__ = (
        CheckConstraint(
            "source IN ('own_stock','customer_supplied')",
            name="ck_bom_line_source",
        ),
        CheckConstraint("qty_per_output > 0", name="ck_bom_line_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    bom_id: int = Field(foreign_key="bomheader.id", ondelete="CASCADE", index=True)
    component_product_id: int = Field(foreign_key="product.id")
    qty_per_output: Money = money_col()
    source: str = Field(default="own_stock")
    default_location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id")
    is_optional: bool = Field(default=False)
    notes: Optional[str] = None


class RatePlan(SQLModel, table=True):
    """Pricing template for value-addition services.

    Per-unit flat rate is the headline number. The plan also captures whether
    consumed materials get billed at cost (passthrough) and the overhead/
    margin uplifts. Plans are versioned — historical invoices reference the
    specific version they were billed under so they stay reproducible after
    the catalogue changes.
    """
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "code", "version",
            name="unique_rate_plan_code_version",
        ),
        CheckConstraint("per_unit_rate >= 0", name="ck_rate_plan_rate_nonneg"),
        CheckConstraint("overhead_pct >= 0", name="ck_rate_plan_oh_nonneg"),
        CheckConstraint("margin_pct >= 0", name="ck_rate_plan_margin_nonneg"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    output_product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    per_unit_rate: Money = money_col()              # e.g. ₨50 per processed unit
    includes_materials_at_cost: bool = Field(default=True)
    overhead_pct: Money = money_col(default=Decimal("0"))   # % on direct cost
    margin_pct: Money = money_col(default=Decimal("0"))     # % final markup
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    notes: Optional[str] = None


class CustomerRatePlan(SQLModel, table=True):
    """Many-to-many assignment: a customer can have one or more rate plans
    assigned. The active plan (is_active=true, most-recently-assigned) is
    what production billing uses by default. History preserved.
    """
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "customer_id", "rate_plan_id",
            name="unique_customer_rate_plan_assignment",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    rate_plan_id: int = Field(foreign_key="rateplan.id", index=True)
    is_active: bool = Field(default=True)
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class StockLocation(SQLModel, table=True):
    """A physical or logical place where inventory lives.

    Types:
      own                — manufacturer-owned stock (raw mat, FG, WIP staging)
      customer_custodial — godown holding goods we received from a customer
                           for processing; goods are NOT our asset
      wip                — work-in-progress holding bucket during production
    """
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="unique_stock_location_code"),
        CheckConstraint(
            "type IN ('own','customer_custodial','wip')",
            name="ck_stock_location_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)              # e.g. RM-1, GODOWN-A
    name: str                                  # human label
    type: str                                  # own | customer_custodial | wip
    is_active: bool = Field(default=True)


class InventoryLayer(SQLModel, table=True):
    """One row per stock receipt (or movement that creates a fresh lot).

    Layers are now scoped to (product, location) — the same product can have
    separate layers in different stores, and goods in the customer godown
    are owned by the customer (owner_customer_id set).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id", index=True)
    owner_customer_id: Optional[int] = Field(
        default=None, foreign_key="customer.id", index=True
    )  # set for customer-custodial layers; null for own-stock
    lot_no: Optional[str] = Field(default=None, index=True)
    qty_received: Money = money_col()
    qty_remaining: Money = money_col()
    unit_cost: Money = money_col()
    source_doc: Optional[str] = None  # e.g. "BILL-0042", "GRN-0007"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StockMovement(SQLModel, table=True):
    """Event log: every qty change writes one row.

    InventoryLayer state can be reconstructed from these. Movements flagged
    `posted_to_gl=false` are pure-custodial (customer goods in/out of godown
    during processing) — no JE is written for those.
    """
    __table_args__ = (
        CheckConstraint(
            "direction IN ('RECEIPT','CUSTODIAL_RECEIPT','ISSUE','CUSTODIAL_ISSUE',"
            "'COMPLETION','CUSTODIAL_COMPLETION','DELIVERY','SHIPMENT','ADJUSTMENT')",
            name="ck_stock_movement_direction",
        ),
        CheckConstraint("qty > 0", name="ck_stock_movement_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    occurred_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    direction: str                              # see CHECK
    qty: Money = money_col()
    from_location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id")
    to_location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id")
    lot_no: Optional[str] = Field(default=None, index=True)
    owner_customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    unit_cost: Money = money_col(default=Decimal("0"))
    total_cost: Money = money_col(default=Decimal("0"))
    source_doc_type: Optional[str] = None       # 'bill', 'invoice', 'grn', 'production_order', 'manual', 'adjustment'
    source_doc_id: Optional[int] = None
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    posted_to_gl: bool = Field(default=False)
    notes: Optional[str] = None


class GoodsReceiptNote(SQLModel, table=True):
    """Receipt of customer-supplied material into the godown.

    Custodial — the goods belong to the customer, not us. We hold them and
    later issue them to a production order. Optionally a `declared_value`
    can be supplied so that a memorandum JE (Dr 1210 / Cr 2150) is posted
    to keep an off-balance-sheet record of our custodian liability.
    """
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_grn_number_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)            # e.g. GRN-0001
    customer_id: int = Field(foreign_key="customer.id", index=True)
    received_date: str
    location_id: int = Field(foreign_key="stocklocation.id")  # must be customer_custodial type
    declared_value: Money = money_col(default=Decimal("0"))   # optional memo value (sum across lines)
    notes: Optional[str] = None
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GRNLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_grn_line_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    grn_id: int = Field(foreign_key="goodsreceiptnote.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id")
    qty: Money = money_col()
    lot_no: Optional[str] = None
    declared_value: Money = money_col(default=Decimal("0"))   # per-line memo value
    notes: Optional[str] = None


class ProductionOrder(SQLModel, table=True):
    """One run of producing N units of a recipe for a specific customer.

    State machine:
      draft → started → completed → delivered → billed
                                              ↓
                                          cancelled (from any non-billed state)
    Each transition posts the relevant journal entries + stock movements.
    Cost capitalisation: own_stock consumption hits WIP at start; FG capit-
    alises from WIP at complete; delivery relieves FG at cost. Customer-
    supplied components never touch the GL — only the custodial memo JE
    posted at GRN time (released at delivery) tracks them.
    """
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_po_number_per_tenant"),
        CheckConstraint(
            "state IN ('draft','started','completed','delivered','billed','cancelled')",
            name="ck_production_order_state",
        ),
        CheckConstraint("output_qty > 0", name="ck_production_order_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)            # PO-0001
    bom_id: int = Field(foreign_key="bomheader.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    rate_plan_id: Optional[int] = Field(default=None, foreign_key="rateplan.id")
    output_qty: Money = money_col()
    state: str = Field(default="draft", index=True)
    # Cost basis snapshots (filled as transitions fire)
    own_material_cost: Money = money_col(default=Decimal("0"))   # set on start
    output_unit_cost: Money = money_col(default=Decimal("0"))    # set on complete
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    # Stage timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    billed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    notes: Optional[str] = None


class InvoiceLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None
    rate: Money = money_col()
    amount: Money = money_col()  # stored = qty × rate
    tax_code_id: Optional[int] = Field(default=None, foreign_key="taxcode.id")


class BillLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bill_id: int = Field(foreign_key="bill.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None
    rate: Money = money_col()
    amount: Money = money_col()  # stored = qty × rate
    tax_code_id: Optional[int] = Field(default=None, foreign_key="taxcode.id")


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


class CreditNote(SQLModel, table=True):
    """Document reducing a customer's AR balance. Posted as Dr Revenue / Cr AR.
    ISA 240 — issued instead of editing a posted invoice.
    """
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_cn_number_per_tenant"),
        CheckConstraint(
            "status IN ('draft','posted','applied')",
            name="ck_cn_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    customer_name: Optional[str] = None
    issue_date: str
    description: Optional[str] = None
    notes: Optional[str] = None
    subtotal: Money = money_col()
    gst_amount: Money = money_col()
    total: Money = money_col()
    currency: str = Field(default="PKR")
    exchange_rate: Money = money_col(default=Decimal("1"))
    status: str = Field(default="draft")
    ar_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    revenue_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CreditNoteLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    credit_note_id: int = Field(foreign_key="creditnote.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None
    rate: Money = money_col()
    amount: Money = money_col()


class LoginAttempt(SQLModel, table=True):
    """One row per /login attempt. Used by the per-IP throttle so the count
    is shared across uvicorn workers and survives restarts (vs. an in-process
    dict which only sees its own worker's traffic).

    Old rows past the rolling window are pruned in the same call that reads
    them — no cron job needed.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    ip: str = Field(index=True)
    attempted_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class SequenceCounter(SQLModel, table=True):
    """Per-tenant atomic counter for document numbers.

    Used in place of `SELECT COUNT(*) + 1` for invoice/bill/jv numbering,
    which had a race window: two simultaneous POSTs could read the same
    count and mint the same number, then collide on the UNIQUE constraint.

    Reading the row with FOR UPDATE serialises increments on Postgres.
    SQLite is single-writer anyway so the lock is a no-op there.
    """
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="unique_seq_per_tenant_name"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str = Field(index=True)
    next_value: int = Field(default=1)


class AccountBalance(SQLModel, table=True):
    """Materialised per-account balance for a closed accounting period.

    Written once when /api/periods/{id}/close runs. Trial balance and
    similar reports read from here for any date range that falls inside a
    closed period and fall back to live aggregation across JournalEntry
    for the open period (which still moves).
    """
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "period_id", "account_id",
            name="unique_balance_per_period_account",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    period_id: int = Field(foreign_key="accountingperiod.id", index=True)
    account_id: int = Field(foreign_key="account.id")
    debit_total: Money = money_col()
    credit_total: Money = money_col()


class BankStatementImport(SQLModel, table=True):
    """One row per CSV upload. file_hash de-dupes uploads of the same file
    across re-tries / accidental re-uploads.
    """
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "bank_account_id", "file_hash",
            name="unique_bank_import_file_per_account",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    bank_account_id: int = Field(foreign_key="bankaccount.id")
    file_name: str
    file_hash: str = Field(index=True)
    line_count: int = Field(default=0)
    matched_count: int = Field(default=0)
    status: str = Field(default="parsed")   # parsed | matched | reconciled
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StatementLine(SQLModel, table=True):
    """One row per line in an uploaded bank statement. debit/credit are the
    bank's perspective: a customer payment received hits the credit column
    (money INTO the account). When matched to a Transaction, is_matched
    flips and matched_transaction_id points at the JV.
    """
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_stmt_line_nonneg"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    import_id: int = Field(foreign_key="bankstatementimport.id", ondelete="CASCADE", index=True)
    date: str
    description: str
    debit: Money = money_col()
    credit: Money = money_col()
    balance: Money = money_col()
    matched_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    is_matched: bool = Field(default=False)


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


class Attachment(SQLModel, table=True):
    """Polymorphic document attachment for vouchers and source documents.

    A single row binds an uploaded file to its parent business record
    (invoice / bill / transaction / payment_received / bill_payment). The
    physical file lives under UPLOAD_ROOT / tenant_id / parent_type /
    parent_id / file_name.uuid.ext; this row records the metadata.

    Storage layout (local fs):
        backend/uploads/<tenant_id>/<parent_type>/<parent_id>/<uuid>.<ext>

    The composite index on (tenant_id, parent_type, parent_id) lets the
    list endpoint enumerate attachments for one record in one seek.
    """
    __table_args__ = (
        CheckConstraint(
            "parent_type IN ('invoice','bill','transaction','payment_received','bill_payment','grn','production_order')",
            name="ck_attachment_parent_type",
        ),
        Index("ix_attachment_parent", "tenant_id", "parent_type", "parent_id"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    parent_type: str = Field(index=True)
    parent_id: int = Field(index=True)
    file_name: str                       # uuid-prefixed name on disk
    original_name: str                   # filename the user uploaded
    mime_type: str
    size_bytes: int
    file_path: str                       # relative path under UPLOAD_ROOT
    uploaded_by_id: int = Field(foreign_key="user.id")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


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


# ---------------------------------------------------------------------------
# Telecom Franchise models
# ---------------------------------------------------------------------------

class TrackerAccount(SQLModel, table=True):
    """Franchisee's Tracker wallet per operator (cash deposited with the
    telecom company that is consumed by load orders and stock debits)."""
    __tablename__ = "tracker_account"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_reference", name="uq_tracker_account_ref"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_name: str                        # e.g. "Jazz (PMCL)"
    operator_code: str                        # JAZZ | TELENOR | ZONG | UFONE
    account_reference: str                    # franchisee's Tracker ID
    deposit_balance: Money = money_col()      # denormalised; mirrors Account(1210)
    load_balance: Money = money_col()         # denormalised; mirrors Account(1211)
    deposit_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    load_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TrackerTransaction(SQLModel, table=True):
    """Every movement in the Tracker wallet: deposits, load orders, SIM/IMSI
    stock debits, FCA commission credits, and penalty debits."""
    __tablename__ = "tracker_transaction"
    __table_args__ = (
        CheckConstraint(
            "txn_type IN ('deposit','load_order','stock_debit',"
            "'commission_credit','penalty_debit','adjustment')",
            name="ck_tracker_txn_type",
        ),
        CheckConstraint("amount > 0", name="ck_tracker_txn_amount_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    tracker_account_id: int = Field(foreign_key="tracker_account.id", index=True)
    txn_date: str                             # ISO date string
    txn_type: str                             # see CHECK
    amount: Money = money_col()               # amount paid / debited (always positive)
    load_disbursed: Money = money_col()       # for load_order: 103% of amount
    commission_earned: Money = money_col()    # for load_order: 3% of amount
    tracker_reference: Optional[str] = None  # operator's transaction ID
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    is_reconciled: bool = Field(default=False)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RSOAgent(SQLModel, table=True):
    """Retail Sales Officer — field team member who handles load distribution
    and SIM stock allocation to tagged retail outlets."""
    __tablename__ = "rso_agent"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cnic", name="uq_rso_agent_cnic"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    phone: str
    cnic: Optional[str] = None
    territory: Optional[str] = None
    receivable_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RetailOutlet(SQLModel, table=True):
    """A retail shop tagged to a specific RSO. Receives load and SIM stock
    from that RSO; cash collected by RSO daily."""
    __tablename__ = "retail_outlet"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    rso_id: int = Field(foreign_key="rso_agent.id", index=True)
    shop_name: str
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LoadTransfer(SQLModel, table=True):
    """One hop in the load distribution chain: MSR SIM → RSO SIM, or RSO SIM
    → Retail outlet SIM.  Each hop has a GL entry and is settled by the
    downstream daily collection."""
    __tablename__ = "load_transfer"
    __table_args__ = (
        CheckConstraint(
            "from_type IN ('msr','rso')",
            name="ck_load_transfer_from_type",
        ),
        CheckConstraint(
            "to_type IN ('rso','retail')",
            name="ck_load_transfer_to_type",
        ),
        CheckConstraint("amount > 0", name="ck_load_transfer_amount_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    transfer_date: str                        # ISO date
    from_type: str                            # msr | rso
    from_ref_id: Optional[int] = None        # rso_agent.id when from_type=rso
    to_type: str                              # rso | retail
    to_ref_id: int                            # rso_agent.id or retail_outlet.id
    amount: Money = money_col()               # face value of load transferred
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    is_settled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SimBatch(SQLModel, table=True):
    """A batch of SIM cards received from the telecom company.  Cost is
    auto-debited from the Tracker balance (stock_debit transaction)."""
    __tablename__ = "sim_batch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_reference", name="uq_sim_batch_ref"),
        CheckConstraint("qty_received > 0", name="ck_sim_batch_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_name: str
    batch_reference: str                      # company-assigned batch number
    series_from: Optional[str] = None
    series_to: Optional[str] = None
    qty_received: int
    qty_activated: int = Field(default=0)     # counter sales
    qty_issued_rso: int = Field(default=0)    # issued to RSO channel
    unit_cost: Money = money_col()            # Tracker deduction / qty
    received_date: str                        # ISO date
    tracker_txn_id: Optional[int] = Field(default=None, foreign_key="tracker_transaction.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SimActivation(SQLModel, table=True):
    """A SIM card sold at the service counter or issued to the RSO channel."""
    __tablename__ = "sim_activation"
    __table_args__ = (
        CheckConstraint(
            "activation_type IN ('counter_sale','rso_issue')",
            name="ck_sim_activation_type",
        ),
        CheckConstraint(
            "status IN ('pending','active','rejected')",
            name="ck_sim_activation_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    sim_batch_id: int = Field(foreign_key="sim_batch.id", index=True)
    sim_number: Optional[str] = None         # MSISDN if known
    activation_date: str                      # ISO date
    customer_name: Optional[str] = None
    customer_cnic: Optional[str] = None
    activation_type: str                      # counter_sale | rso_issue
    rso_id: Optional[int] = Field(default=None, foreign_key="rso_agent.id", index=True)
    status: str = Field(default="pending")
    sale_price: Money = money_col()           # for counter sales
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RSODailyCollection(SQLModel, table=True):
    """RSO's daily bank deposit that settles both load transferred and SIM
    stock issued to that RSO.  Variance (if any) posts to account 5070."""
    __tablename__ = "rso_daily_collection"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    rso_id: int = Field(foreign_key="rso_agent.id", index=True)
    collection_date: str                      # ISO date
    load_portion: Money = money_col()         # load settlement cash
    stock_portion: Money = money_col()        # SIM stock settlement cash
    total_deposited: Money = money_col()      # actual bank deposit
    variance: Money = money_col()             # total - load - stock (±); posts to 5070
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    is_reconciled: bool = Field(default=False)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FCAEvent(SQLModel, table=True):
    """First Call Activation — logged when an end customer makes their first
    call on a newly activated SIM.  No GL posting; only increments the
    KPITarget counter.  Commission is posted at month-end close."""
    __tablename__ = "fca_event"
    __table_args__ = (
        CheckConstraint(
            "source_channel IN ('counter','rso_retail','direct')",
            name="ck_fca_event_channel",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    kpi_target_id: int = Field(foreign_key="kpi_target.id", index=True)
    sim_number: Optional[str] = None
    event_date: str                           # ISO date
    source_channel: str                       # counter | rso_retail | direct
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KPITarget(SQLModel, table=True):
    """Monthly FCA target set by the telecom company.  Tracks actual FCA
    count; at month-end close, posts the commission or penalty JV."""
    __tablename__ = "kpi_target"
    __table_args__ = (
        UniqueConstraint("tenant_id", "tracker_account_id", "target_month",
                         name="uq_kpi_target_month"),
        CheckConstraint(
            "status IN ('open','closed')",
            name="ck_kpi_target_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    tracker_account_id: int = Field(foreign_key="tracker_account.id", index=True)
    target_month: str                         # YYYY-MM-01
    target_fca_count: int
    actual_fca_count: int = Field(default=0)
    incentive_earned: Money = money_col()
    penalty_applied: Money = money_col()
    commission_txn_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    status: str = Field(default="open")       # open | closed
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


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


# Re-export telecom-franchise tables so SQLModel.metadata.create_all() picks
# them up at boot and existing `from models import X` imports keep working.
from models_telecom import (  # noqa: E402,F401
    AirtimeSale, AirtimeStock, CommissionLine, CommissionStatement,
    DeviceImei, FcaEvent, FranchiseAgreement, KpiTarget, LoadTransfer,
    MobileMoneyAccount, MobileMoneyTransaction, Operator,
    PostpaidBillCycle, PostpaidConnection, RetailOutlet, RsoAgent,
    RsoDailyCollection, RsoStockIssue, RsoTarget, SimActivation, SimBatch,
    TrackerAccount, TrackerTransaction,
)
