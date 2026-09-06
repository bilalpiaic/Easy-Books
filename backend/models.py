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

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, JSON, Numeric, Text
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from services.money import Money, ZERO


def money_col(default: Decimal = ZERO, **kw):
    """Numeric(18,4) column with a Decimal default. Centralised so future
    precision tweaks happen in one place."""
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


class Tenant(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "business_model IN ('simple','services','trader','manufacturing','telecom_franchise','pra_einvoice','hospital','yarn_spinning','textile_processing')",
            name="ck_tenant_business_model",
        ),
        CheckConstraint(
            "cost_method IN ('wavg','fifo')",
            name="ck_tenant_cost_method",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    base_currency: str = Field(default="USD")  # ISO 4217; reporting currency
    business_model: str = Field(default="simple", index=True)
    # JSON list of enabled module IDs. Set from MODULES_BY_MODEL at signup;
    # managed independently via POST /api/modules/{id}/install|uninstall after that.
    enabled_modules: str = Field(default='["base"]')
    # JSON dict: {module_id: {tier, installed_at, expires_at}} — billing metadata.
    # tier is "free" | "pro" | "enterprise". expires_at null = perpetual.
    # Shape is intentionally flexible so billing logic can be added without schema changes.
    module_meta: str = Field(default="{}")
    # IAS 2.25: FIFO or weighted-average; applied consistently to all products.
    cost_method: str = Field(default="wavg")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # SaaS plan metering (#119)
    plan: str = Field(default="free", index=True)  # free|starter|pro|enterprise
    max_users: int = Field(default=2)
    max_documents: int = Field(default=50)
    storage_quota_mb: int = Field(default=100)
    is_suspended: bool = Field(default=False)
    trial_ends_at: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    subscription_status: Optional[str] = None  # active|past_due|canceled

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

    my_data_only: bool = Field(default=False)

    # 2FA / SSO (#118)
    totp_enabled: bool = Field(default=False)
    totp_secret: Optional[str] = None  # Fernet-encrypted at rest
    totp_verified_at: Optional[datetime] = None
    oauth_provider: Optional[str] = None  # google|microsoft
    oauth_sub: Optional[str] = None

    tenant: Tenant = Relationship(back_populates="users")


class TenantMembership(SQLModel, table=True):
    """User ↔ tenant membership for practice multi-client switcher (#220).

    `User.tenant_id` / `User.role` remain the *active* membership (updated on
    switch) so existing routers keep filtering by user.tenant_id unchanged.
    """
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_tenant_membership_user_tenant"),
        CheckConstraint(
            "role IN ('owner','admin','accountant','viewer')",
            name="ck_membership_role",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    role: str = Field(default="viewer", index=True)
    invited_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


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


class ApiKey(SQLModel, table=True):
    """Machine-to-machine API key (#113). The raw key ("eb_live_" +
    token_urlsafe) is returned exactly once at creation and never stored —
    only its SHA-256 hex lands in key_hash (unique, the lookup column), plus
    the last 4 raw characters in key_hint for display in the Settings list.

    A key authenticates AS its owning user: get_current_user() resolves
    key_hash → ApiKey → User, so role checks, permission gates, and audit
    attribution all behave exactly as if that user had presented a JWT.
    Revocation is a soft is_active=False (keeps the audit trail), enforced
    on every request.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key_hash: str = Field(unique=True, index=True)
    key_hint: str  # last 4 chars of the raw key — non-secret, for display
    name: str
    scopes: str = Field(default="[]")  # json.dumps(list[str]); unused in v1, reserved
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WebhookEndpoint(SQLModel, table=True):
    """Outgoing webhook registration (#114). `events` holds a JSON array of
    event-type strings from services/events.EVENT_TYPES; an empty array means
    the endpoint receives no events (it must opt in explicitly)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    url: str
    secret: str                      # HMAC-SHA256 signing key; server-generated
    events: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WebhookDelivery(SQLModel, table=True):
    """Durable outbox row for one webhook send (#114). Written in the same
    transaction as the business document (emit never sends inline), then
    drained by the lifespan delivery loop. Retry ladder lives in
    services/events.RETRY_DELAYS; after MAX_ATTEMPTS the row is `failed`."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    endpoint_id: int = Field(foreign_key="webhookendpoint.id", ondelete="CASCADE", index=True)
    event_type: str = Field(index=True)
    payload_json: str
    status: str = Field(default="pending", index=True)   # pending | delivered | failed
    attempts: int = Field(default=0)
    next_retry: Optional[datetime] = Field(default=None, index=True)
    response_code: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None


class TaskDeadLetter(SQLModel, table=True):
    """Failed background job (PDF/email/import/…) for admin retry (#271)."""
    __tablename__ = "taskdeadletter"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="tenant.id", index=True)
    task_name: str = Field(index=True)
    args_json: str = Field(default="[]")
    kwargs_json: str = Field(default="{}")
    error: str
    status: str = Field(default="open", index=True)  # open | retried | discarded
    created_at: datetime = Field(default_factory=datetime.utcnow)
    retried_at: Optional[datetime] = None


class UserPermission(SQLModel, table=True):
    """Sparse per-user permission overrides, scoped per tenant (#299).

    When no row exists for a (tenant_id, user_id, resource_key) triple, the
    role default applies: owner/admin/accountant → edit, viewer → view.
    """
    __tablename__ = "user_permission"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id", "resource_key",
            name="uq_user_permission_tenant",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    resource_key: str = Field(index=True)
    access_level: str = Field(default="edit")  # "none" | "view" | "edit"


class Settings(SQLModel, table=True):
    tenant_id: int = Field(foreign_key="tenant.id", primary_key=True)
    key: str = Field(primary_key=True)
    value: str
    tenant: "Tenant" = Relationship(back_populates="settings")


class CommissionPlan(SQLModel, table=True):
    """Per-user commission configuration. A single active plan per user at a time."""
    __tablename__ = "commission_plan"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    rate: Decimal = Field(sa_column=Column(Numeric(10, 4), nullable=False))  # % of recovery
    sales_target: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    recovery_target: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    target_bonus: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    effective_from: str = Field(index=True)  # YYYY-MM-DD
    effective_to: Optional[str] = None       # null = open-ended
    active: bool = Field(default=True)


class CommissionLedger(SQLModel, table=True):
    """Computed monthly commission record for a sales person. One row per user per period."""
    __tablename__ = "commission_ledger"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "period", name="uq_commission_period"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    period: str = Field(index=True)               # YYYY-MM
    total_invoiced: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False, server_default="0"))
    total_recovered: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False, server_default="0"))
    rate: Decimal = Field(sa_column=Column(Numeric(10, 4), nullable=False))
    commission_amount: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False, server_default="0"))
    bonus_amount: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False, server_default="0"))
    total_payable: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False, server_default="0"))
    status: str = Field(default="draft")          # draft | approved | posted
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")


class UserDashboardLayout(SQLModel, table=True):
    """Per-user dual-home dashboard layout (#52 §3 / v4). Opaque JSON blob —
    the widget registry and merge logic live in the frontend; the backend only
    stores and returns the string keyed by (tenant_id, user_id).

    Schema v4: `{version:4, activeView?, dashboards:{financial, operations}}`
    where each slice holds `{layouts:{lg, sm?, xs?}, dismissed?, quickActions?}`.
    Older v1–v3 blobs are migrated under `dashboards.financial` on the client.
    """
    tenant_id: int = Field(foreign_key="tenant.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    layout_json: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserAlert(SQLModel, table=True):
    """Per-user in-app ops alert (overdue, low stock, pending approval)."""
    __tablename__ = "user_alert"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_user_alert_dedupe"),
        CheckConstraint(
            "kind IN ('overdue_invoice','low_stock','approval_needed','system','invoice_dispute')",
            name="ck_user_alert_kind",
        ),
        CheckConstraint(
            "severity IN ('info','warning','critical')",
            name="ck_user_alert_severity",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str = Field(index=True)
    severity: str = Field(default="warning")
    title: str
    body: Optional[str] = None
    href: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    dedupe_key: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = None


class AppUpdateNotice(SQLModel, table=True):
    """Global what's-new notice for a shipped commit — fans out to UserAlert (#update-notices)."""
    __tablename__ = "app_update_notice"
    __table_args__ = (
        UniqueConstraint("sha", name="uq_app_update_notice_sha"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    sha: str = Field(index=True)  # short or full commit hash
    title: str  # easy-language headline
    body: Optional[str] = None  # short plain-language description
    commit_date: Optional[str] = None  # YYYY-MM-DD
    # False for first-run seed so we don't spam historical commits.
    notify_users: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    # Group/header accounts are control nodes — never postable.
    # Existing rows default to is_group=False (postable) via the Alembic migration.
    is_group: bool = Field(default=False, index=True)
    # Inactive accounts are excluded from new postings.
    is_active: bool = Field(default=True)
    # AR/AP party classification (§2): "customer" | "vendor" | None
    party_type: Optional[str] = None

    tenant: Tenant = Relationship(back_populates="accounts")
    journal_entries: List["JournalEntry"] = Relationship(back_populates="account")


class AccountingPeriod(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    period_start: str
    period_end: str
    is_locked: bool = Field(default=False)
    name: Optional[str] = None


class CloseChecklistItem(SQLModel, table=True):
    """Per-period month-end close task (#262)."""
    __tablename__ = "closechecklistitem"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "period_id", "task_key",
            name="uq_close_checklist_period_task",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    period_id: int = Field(foreign_key="accountingperiod.id", index=True)
    task_key: str = Field(index=True)
    label: str
    required: bool = Field(default=True)
    sort_order: int = Field(default=0)
    is_done: bool = Field(default=False)
    completed_at: Optional[datetime] = None
    completed_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    notes: Optional[str] = None


class ConsolidationMember(SQLModel, table=True):
    """Entity graph edge for group consolidation (IFRS 10) — #255.

    Stored on the *holding* tenant. `member_tenant_id` is another tenant the
    holding user can access (via TenantMembership). Parent is typically the
    holding itself; subsidiaries are line-by-line consolidated; associates
    are equity-method one-liners (ownership % of equity only).
    """
    __tablename__ = "consolidationmember"
    __table_args__ = (
        UniqueConstraint(
            "holding_tenant_id", "member_tenant_id",
            name="uq_consol_member",
        ),
        CheckConstraint(
            "relationship IN ('parent','subsidiary','associate')",
            name="ck_consol_member_relationship",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    holding_tenant_id: int = Field(foreign_key="tenant.id", index=True)
    member_tenant_id: int = Field(foreign_key="tenant.id", index=True)
    relationship: str = Field(default="subsidiary", index=True)
    ownership_pct: Money = money_col(default=Decimal("100"))  # 0–100
    label: Optional[str] = None
    is_active: bool = Field(default=True)
    # Optional IC control-account codes on this member (for propose)
    ic_ar_code: Optional[str] = None
    ic_ap_code: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConsolidationRun(SQLModel, table=True):
    """One consolidation worksheet for a period — draft → posted (immutable) / void."""
    __tablename__ = "consolidationrun"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','posted','void')",
            name="ck_consol_run_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    holding_tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: Optional[str] = None
    period_start: str
    period_end: str
    status: str = Field(default="draft", index=True)
    notes: Optional[str] = None
    # Snapshot of consolidated statements JSON once posted (immutable package)
    package_json: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    posted_at: Optional[datetime] = None
    posted_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    voided_at: Optional[datetime] = None
    voided_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class ConsolidationElimination(SQLModel, table=True):
    """Worksheet elimination journal line (not posted to member GLs)."""
    __tablename__ = "consolidationelimination"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('ic_balance','ic_sales','unrealised_stock','nci','manual')",
            name="ck_consol_elim_kind",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    holding_tenant_id: int = Field(foreign_key="tenant.id", index=True)
    run_id: int = Field(foreign_key="consolidationrun.id", index=True)
    kind: str = Field(default="manual", index=True)
    description: str = Field(default="")
    account_code: str
    account_name: str = Field(default="")
    account_type: str = Field(default="Equity")  # Asset|Liability|Equity|Revenue|Expense
    debit: Money = money_col()
    credit: Money = money_col()
    member_tenant_id: Optional[int] = Field(default=None, foreign_key="tenant.id")
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    voucher_type: str = Field(default="JV", index=True)
    legacy_jv_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_reversed: bool = Field(default=False)
    reversed_by_id: Optional[int] = Field(default=None)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)

    tenant: Tenant = Relationship(back_populates="transactions")
    journal_entries: List["JournalEntry"] = Relationship(back_populates="transaction", cascade_delete=True)


class JournalEntryBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    account_id: int = Field(foreign_key="account.id")
    debit: Money = money_col()
    credit: Money = money_col()
    # Optional cost-center / project tag for segment P&L (IAS 1 management commentary).
    # Slot 0 of up to 3 analytic dimensions (#260); analytic_2_id / analytic_3_id are slots 1–2.
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_2_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_3_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    # AR/AP party tracking (§2): links the JE line to the debtor/creditor
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")


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
    # PRA e-Invoice buyer identification
    ntn: Optional[str] = None   # 7-digit NTN e.g. "1234567-8" (maps to BuyerPNTN)
    cnic: Optional[str] = None  # 13-digit CNIC (maps to BuyerCNIC)
    dunning_opt_out: bool = Field(default=False)  # #120 — skip automated reminders
    # India GST (#265)
    gstin: Optional[str] = None       # 15-char GSTIN
    state_code: Optional[str] = None  # 2-digit place-of-supply state code
    # Studio-lite custom fields (#372) — JSON map of x.* keys; never posted to GL
    custom_fields: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


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
    # India GST (#265)
    gstin: Optional[str] = None
    state_code: Optional[str] = None
    # Withholding tax (#267)
    wht_tax_code_id: Optional[int] = Field(default=None, foreign_key="taxcode.id")
    wht_rate: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    custom_fields: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


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
    # After FX revaluation: carrying rate used for settlement / subsequent revals (IAS 21).
    # None → fall back to exchange_rate.
    carrying_rate: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    status: str = Field(default="draft")
    ar_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    revenue_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    # Separate FK to the COGS JV (Dr 5010 / Cr 1200) posted for stock lines, so
    # an edit can reverse + re-post it independently of the AR/Revenue JV.
    cogs_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    payment_term_id: Optional[int] = Field(default=None, foreign_key="paymentterm.id")
    # Stripe payment link fields (G-12)
    payment_link_url: Optional[str] = None
    payment_link_status: Optional[str] = None  # "unpaid" | "paid"
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    assigned_to_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_2_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_3_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    # PRA e-Invoice fields
    payment_mode: Optional[int] = None  # 1=Cash 2=Card 3=GiftVoucher 4=Loyalty 5=Mixed 6=Cheque
    pra_usin: Optional[str] = None          # User Serial Invoice Number sent to PRA (= invoice.number)
    pra_fiscal_number: Optional[str] = None # Fiscal Invoice Number returned by PRA on success
    pra_status: str = Field(default="not_required")  # not_required|pending|submitted|failed
    pra_submitted_at: Optional[datetime] = None
    pra_response_raw: Optional[str] = None  # raw JSON response for audit trail
    buyer_ntn: Optional[str] = None   # walk-in NTN override (takes priority over customer.ntn)
    buyer_cnic: Optional[str] = None  # walk-in CNIC override (takes priority over customer.cnic)
    # Saudi ZATCA e-Invoice (#264)
    zatca_status: Optional[str] = Field(default=None, index=True)  # pending|submitted|cleared|reported|rejected|error
    zatca_uuid: Optional[str] = None
    zatca_hash: Optional[str] = None
    zatca_qr: Optional[str] = None
    zatca_submitted_at: Optional[datetime] = None
    # Peppol / EU VAT e-Invoice (#266)
    peppol_status: Optional[str] = Field(default=None, index=True)  # pending|submitted|accepted|rejected|error
    peppol_document_id: Optional[str] = None
    peppol_submitted_at: Optional[datetime] = None
    # Approval workflow (#123) — null means no workflow engaged / legacy docs
    approval_status: Optional[str] = Field(default=None, index=True)
    # Intercompany (#261) — flag + sister-entity link; mirror bill id on counterparty
    # Mirror ids are plain ints (no DB FK) to avoid Invoice↔Bill circular FKs.
    is_intercompany: bool = Field(default=False, index=True)
    ic_counterparty_tenant_id: Optional[int] = Field(default=None, index=True)
    ic_mirror_bill_id: Optional[int] = Field(default=None)
    custom_fields: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


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
    carrying_rate: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    status: str = Field(default="draft")
    ap_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    expense_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    payment_term_id: Optional[int] = Field(default=None, foreign_key="paymentterm.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_2_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_3_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    approval_status: Optional[str] = Field(default=None, index=True)  # #123
    # Intercompany (#261) — mirror invoice id is a plain int (no circular FK)
    is_intercompany: bool = Field(default=False, index=True)
    ic_counterparty_tenant_id: Optional[int] = Field(default=None, index=True)
    ic_mirror_invoice_id: Optional[int] = Field(default=None)
    custom_fields: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class PaymentReceived(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    customer_name: Optional[str] = None
    payment_date: str
    amount: Money = money_col()
    currency: Optional[str] = None  # doc currency; None/base → legacy base-only path
    exchange_rate: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    method: str = Field(default="cash")
    reference: Optional[str] = None
    cash_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_2_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_3_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")


class BillPayment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    bill_id: Optional[int] = Field(default=None, foreign_key="bill.id")
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id", index=True)
    vendor_name: Optional[str] = None
    payment_date: str
    amount: Money = money_col()
    wht_amount: Money = money_col()  # withholding deducted; Cr 2265 (#267)
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    method: str = Field(default="cash")
    reference: Optional[str] = None
    cash_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_2_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_3_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")


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


class ProductCategory(SQLModel, table=True):
    """A 2-level product taxonomy. parent_id NULL → a top-level category;
    parent_id set → a sub-category. Depth is capped at 2 by the router."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "parent_id", "name", name="unique_category_name_per_parent"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    parent_id: Optional[int] = Field(default=None, foreign_key="productcategory.id", index=True)
    is_active: bool = Field(default=True)


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    category_id: Optional[int] = Field(default=None, foreign_key="productcategory.id", index=True)
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
    # IFRS 15: if True, invoice lines for this product post to Deferred Revenue (2300)
    is_deferred: bool = Field(default=False)
    recognition_months: int = Field(default=12)
    hs_code: Optional[str] = Field(default=None)  # Harmonized System code for FBR / customs
    pct_code: Optional[str] = Field(default=None)  # 8-digit PRA product classification (PCTCode)
    hsn_sac: Optional[str] = Field(default=None)  # India GST HSN/SAC (#265)
    # IAS 2.25: per-product cost-flow override. None → inherit from Tenant.cost_method.
    cost_method: Optional[str] = Field(default=None)  # 'wavg' | 'fifo' | None
    # IAS 2 tracking (#257)
    track_lot: bool = Field(default=False)
    track_serial: bool = Field(default=False)
    # Latest estimated net realisable value per unit (optional; NRV runs can override).
    nrv_unit: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    # IFRS 15 standalone selling price (unit catalog SSP) for relative allocation (#259).
    standalone_selling_price: Optional[Decimal] = Field(
        default=None, sa_column=Column(Numeric(18, 4), nullable=True)
    )
    custom_fields: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class CustomFieldDef(SQLModel, table=True):
    """Tenant-defined extra document fields (`x.*`). Values live on the
    document JSON column; this row is the definition. Soft-delete via
    ``archived_at`` so historical values stay readable (#372)."""
    __tablename__ = "custom_field_def"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity", "key", name="uq_custom_field_def_tenant_entity_key"),
        Index("ix_custom_field_def_tenant_entity", "tenant_id", "entity"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    entity: str  # invoice | bill | customer | product | vendor
    key: str  # x.gate_pass_no
    label: str
    type: str = Field(default="text")  # text | number | date | enum | bool
    enum_values: Optional[list] = Field(default=None, sa_column=Column(JSON, nullable=True))
    required: bool = Field(default=False)
    show_on_form: bool = Field(default=True)
    show_on_print: bool = Field(default=False)
    show_on_list: bool = Field(default=False)
    sort_order: int = Field(default=0)
    archived_at: Optional[datetime] = Field(default=None, index=True)
    source_extension_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FormSchema(SQLModel, table=True):
    """Tenant (or role) overlay for hide/show/required on a document form (#373).

    ``role='*'`` is the tenant default. A matching role row replaces ``*``
    for that user. Missing field keys keep the shipped default (visible).
    """
    __tablename__ = "form_schema"
    tenant_id: int = Field(foreign_key="tenant.id", primary_key=True)
    entity: str = Field(primary_key=True)
    role: str = Field(default="*", primary_key=True)
    payload_json: dict = Field(default_factory=dict, sa_column=Column("schema_json", JSON, nullable=False))
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class PrintTemplate(SQLModel, table=True):
    """Tenant print-template clone or default picker (#374). Built-in
    ``standard`` keeps using ``backend/templates/{entity}.html`` unless a
    clone is marked default and stores HTML here."""
    __tablename__ = "print_template"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity", "key", name="uq_print_template_tenant_entity_key"),
        Index("ix_print_template_tenant_entity", "tenant_id", "entity"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    entity: str  # invoice | bill
    key: str  # standard | x.mill_packing
    label: str
    html: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    is_builtin_override: bool = Field(default=False)
    is_default: bool = Field(default=False)
    source_extension_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StockSerial(SQLModel, table=True):
    """Per-unit serial number for track_serial products (#257)."""
    __tablename__ = "stockserial"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "serial", name="uq_stock_serial"),
        CheckConstraint(
            "status IN ('available','sold','scrapped')",
            name="ck_stock_serial_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    serial: str = Field(index=True)
    status: str = Field(default="available", index=True)
    layer_id: Optional[int] = Field(default=None, foreign_key="inventorylayer.id")
    source_doc: Optional[str] = None
    sold_doc_type: Optional[str] = None
    sold_doc_id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LandedCost(SQLModel, table=True):
    """Allocate freight/duty/insurance onto inventory receipt layers (#257)."""
    __tablename__ = "landedcost"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_landed_cost_number"),
        CheckConstraint(
            "status IN ('draft','posted','void')",
            name="ck_landed_cost_status",
        ),
        CheckConstraint(
            "allocation_method IN ('value','qty')",
            name="ck_landed_cost_alloc",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    cost_date: str
    # Bill that carries the landed charges (freight/duty) — optional.
    charge_bill_id: Optional[int] = Field(default=None, foreign_key="bill.id")
    # Goods bill whose open layers receive the allocation.
    goods_bill_id: Optional[int] = Field(default=None, foreign_key="bill.id", index=True)
    goods_source_doc: Optional[str] = Field(default=None, index=True)  # bill.number fallback
    description: Optional[str] = None
    amount: Money = money_col()
    allocation_method: str = Field(default="value")
    status: str = Field(default="draft", index=True)
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LandedCostAllocation(SQLModel, table=True):
    __tablename__ = "landedcostallocation"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    landed_cost_id: int = Field(foreign_key="landedcost.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    layer_id: int = Field(foreign_key="inventorylayer.id", index=True)
    amount: Money = money_col()
    qty_basis: Money = money_col()
    value_basis: Money = money_col()


class NrVRun(SQLModel, table=True):
    """IAS 2 NRV valuation run — write inventory down to NRV (#257)."""
    __tablename__ = "nrvrun"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_nrv_run_number"),
        CheckConstraint(
            "status IN ('draft','posted','reversed')",
            name="ck_nrv_run_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    run_date: str
    status: str = Field(default="draft", index=True)
    use_allowance: bool = Field(default=True)  # Cr allowance vs direct Cr inventory
    notes: Optional[str] = None
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    reverse_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NrVLine(SQLModel, table=True):
    __tablename__ = "nrvline"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    run_id: int = Field(foreign_key="nrvrun.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    qty: Money = money_col()
    unit_cost: Money = money_col()
    nrv_unit: Money = money_col()
    write_down: Money = money_col()  # max(0, (cost - nrv) * qty)


class BomHeader(SQLModel, table=True):
    """Bill of Materials — the recipe for producing one batch of an output.

    A BoM is versioned: every time the recipe changes you bump `version` and
    flag the new row `is_active=True` (and the old one False). Production
    orders pin a specific version so cost reconstruction stays accurate even
    after the BoM evolves.

    `output_product_id` / `output_qty` remain the denormalized PRIMARY output
    (version key, invoice explode, PO batch scale). Extra outputs live in
    BomOutput (#223).
    """
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "output_product_id", "version",
            name="unique_bom_per_product_version",
        ),
        CheckConstraint(
            "cost_alloc_method IN ('primary_only','fixed_pct','relative_sales_value')",
            name="ck_bom_cost_alloc_method",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    output_product_id: int = Field(foreign_key="product.id", index=True)
    output_qty: Money = money_col(default=Decimal("1"))  # produces N output units per recipe run
    # Joint-product cost split at PO complete (#223)
    cost_alloc_method: str = Field(default="primary_only")
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    explode_on_invoice: bool = Field(default=False)  # auto-consume components when output product is sold
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


class BomOutput(SQLModel, table=True):
    """One output product of a BoM (primary / co-product / by-product) — #223.

    Primary is also mirrored on BomHeader.output_product_id for back-compat.
    """
    __table_args__ = (
        CheckConstraint(
            "role IN ('primary','co_product','by_product')",
            name="ck_bom_output_role",
        ),
        CheckConstraint("qty_per_batch > 0", name="ck_bom_output_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    bom_id: int = Field(foreign_key="bomheader.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    qty_per_batch: Money = money_col()
    role: str = Field(default="primary")
    alloc_pct: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    sales_price_hint: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))


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
    overhead_pct: Money = money_col(default=Decimal("0"))   # % on direct cost (billing uplift)
    margin_pct: Money = money_col(default=Decimal("0"))     # % final markup
    # Absorption costing (#222) — applied into WIP at PO start (not billing)
    labour_per_unit: Money = money_col(default=Decimal("0"))
    overhead_per_unit: Money = money_col(default=Decimal("0"))
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
      in_transit         — system bucket between ship and receive (#302)
    """
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="unique_stock_location_code"),
        CheckConstraint(
            "type IN ('own','customer_custodial','wip','in_transit')",
            name="ck_stock_location_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)              # e.g. RM-1, GODOWN-A
    name: str                                  # human label
    type: str                                  # own | customer_custodial | wip | in_transit
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
            "'COMPLETION','CUSTODIAL_COMPLETION','DELIVERY','SHIPMENT','ADJUSTMENT',"
            "'TRANSFER_OUT','TRANSFER_IN')",
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


class StockTransfer(SQLModel, table=True):
    """Inter-warehouse transfer with in-transit state (#302). Memo location move —
    Product.stock_qty unchanged; no GL for own↔own transfers."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_stock_transfer_number"),
        CheckConstraint(
            "status IN ('draft','in_transit','received','cancelled')",
            name="ck_stock_transfer_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)  # ST-YYYY-seq
    transfer_date: str
    from_location_id: int = Field(foreign_key="stocklocation.id", index=True)
    to_location_id: int = Field(foreign_key="stocklocation.id", index=True)
    status: str = Field(default="draft", index=True)
    notes: Optional[str] = None
    created_by_id: int = Field(foreign_key="user.id")
    shipped_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    shipped_at: Optional[datetime] = None
    received_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    received_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StockTransferLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_st_line_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    transfer_id: int = Field(foreign_key="stocktransfer.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id")
    qty: Money = money_col()
    lot_no: Optional[str] = None
    unit_cost: Money = money_col(default=Decimal("0"))  # filled on ship


class StockReservation(SQLModel, table=True):
    """Location-level stock hold (#302). Blocks oversell when settings.stock_reservation_enabled."""
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_stock_reservation_qty"),
        CheckConstraint(
            "status IN ('open','released','consumed')",
            name="ck_stock_reservation_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id", index=True)
    qty: Money = money_col()
    source_doc_type: str = Field(default="manual", index=True)  # invoice|pick_list|manual
    source_doc_id: Optional[int] = Field(default=None, index=True)
    status: str = Field(default="open", index=True)
    notes: Optional[str] = None
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    released_at: Optional[datetime] = None


class PickList(SQLModel, table=True):
    """Pick/pack worksheet against an invoice (#302)."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_pick_list_number"),
        CheckConstraint(
            "status IN ('draft','picking','picked','packed','cancelled')",
            name="ck_pick_list_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id")
    status: str = Field(default="draft", index=True)
    notes: Optional[str] = None
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    packed_at: Optional[datetime] = None


class PickListLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pick_list_id: int = Field(foreign_key="picklist.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id")
    qty_ordered: Money = money_col()
    qty_picked: Money = money_col(default=Decimal("0"))
    location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id")
    reservation_id: Optional[int] = Field(default=None, foreign_key="stockreservation.id")


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
        # Must not reuse PurchaseOrder's constraint name — Postgres requires
        # unique constraint names across the whole schema.
        UniqueConstraint("tenant_id", "number", name="unique_prod_order_number_per_tenant"),
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
    labour_cost: Money = money_col(default=Decimal("0"))         # absorbed at start (#222)
    overhead_cost: Money = money_col(default=Decimal("0"))       # absorbed at start (#222)
    output_unit_cost: Money = money_col(default=Decimal("0"))    # set on complete
    delivered_qty: Money = money_col(default=Decimal("0"))       # cumulative (#222)
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    # Stage timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    billed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    notes: Optional[str] = None


class ProductionOrderOutput(SQLModel, table=True):
    """Per-output qty/cost snapshot written at PO complete (#223)."""
    __table_args__ = (
        CheckConstraint(
            "role IN ('primary','co_product','by_product')",
            name="ck_po_output_role",
        ),
        CheckConstraint("qty > 0", name="ck_po_output_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    po_id: int = Field(foreign_key="productionorder.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    role: str = Field(default="primary")
    qty: Money = money_col()
    unit_cost: Money = money_col(default=Decimal("0"))
    delivered_qty: Money = money_col(default=Decimal("0"))


class ScrapReason(SQLModel, table=True):
    """Tenant catalog of scrap/damage reason codes for production (#224)."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="unique_scrap_reason_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str
    name: str
    is_active: bool = Field(default=True)


class ProductionScrap(SQLModel, table=True):
    """Scrap/damage recorded against a production order (#224)."""
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_production_scrap_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    po_id: int = Field(foreign_key="productionorder.id", index=True)
    reason_id: int = Field(foreign_key="scrapreason.id", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    qty: Money = money_col()
    unit_cost: Money = money_col(default=Decimal("0"))
    total_cost: Money = money_col(default=Decimal("0"))
    gl_posted: bool = Field(default=False)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class PromoRule(SQLModel, table=True):
    """Promotional pricing rule. Matches on product/category + date range +
    optional qty/value threshold. Applies a % discount or adds giveaway lines."""
    __tablename__ = "promo_rule"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    start_date: Optional[str] = None    # YYYY-MM-DD; null = no lower bound
    end_date: Optional[str] = None      # YYYY-MM-DD; null = no upper bound
    # Scope: which products this promo covers
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    category_id: Optional[int] = Field(default=None, foreign_key="productcategory.id")
    # Trigger thresholds (both optional; each is ANDed when set)
    min_qty: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    min_invoice_value: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    # Discount action
    discount_type: str = Field(default="percent")   # "percent" | "fixed" | "giveaway"
    discount_value: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    giveaway_product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    giveaway_qty: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4)))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InvoiceLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None
    rate: Money = money_col()
    discount_pct: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(5, 2), nullable=False, server_default="0"))
    amount: Money = money_col()  # stored = qty × rate × (1 − discount_pct/100); net when exclusive
    tax_code_id: Optional[int] = Field(default=None, foreign_key="taxcode.id")
    # Snapshots at post time — never re-derived from the live catalog (#263).
    tax_rate: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4), nullable=True))
    tax_amount: Money = money_col()
    tax_inclusive: bool = Field(default=False)
    promo_rule_id: Optional[int] = Field(default=None, foreign_key="promo_rule.id")
    # IFRS 15 (#259): SSP snapshot at invoice time; amount before relative-SSP reallocation.
    ssp: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    pre_allocation_amount: Optional[Decimal] = Field(
        default=None, sa_column=Column(Numeric(18, 4), nullable=True)
    )


class BillLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bill_id: int = Field(foreign_key="bill.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None
    rate: Money = money_col()
    amount: Money = money_col()  # stored = qty × rate; net when exclusive
    tax_code_id: Optional[int] = Field(default=None, foreign_key="taxcode.id")
    tax_rate: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4), nullable=True))
    tax_amount: Money = money_col()
    tax_inclusive: bool = Field(default=False)


class TaxCode(SQLModel, table=True):
    """Per-tenant tax catalog. Output = sales tax (liability), Input = purchase
    tax (receivable). gl_account_id is the GL account the tax leg posts to.

    Live `rate` mirrors the open TaxRateHistory row; historical documents use
    line snapshots + history as-of the document date (#263).
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
    rate: Money = money_col()            # percent, e.g. 17 — current/open rate
    type: str                            # output | input
    gl_account_id: int = Field(foreign_key="account.id")
    is_active: bool = Field(default=True)
    is_reverse_charge: bool = Field(default=False)
    is_exempt: bool = Field(default=False)
    is_zero_rated: bool = Field(default=False)
    is_withholding: bool = Field(default=False)  # WHT on vendor payments (#267)


class CitAdjustment(SQLModel, table=True):
    """Manual corporate-tax worksheet addback/deduction lines (#267)."""
    __table_args__ = (
        CheckConstraint(
            "kind IN ('addback','deduction')",
            name="ck_cit_adj_kind",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    fiscal_year: str = Field(index=True)  # e.g. "2026" or "2025-26"
    kind: str  # addback | deduction
    description: str
    amount: Money = money_col()


class TaxRateHistory(SQLModel, table=True):
    """Effective-dated rate versions for a TaxCode. Open-ended rows have
    effective_to IS NULL. resolve_rate(on_date) picks the matching row.
    """
    __table_args__ = (
        Index("ix_taxratehistory_code_from", "tax_code_id", "effective_from"),
        CheckConstraint("rate >= 0", name="ck_tax_rate_history_rate_nonneg"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tax_code_id: int = Field(foreign_key="taxcode.id", index=True)
    rate: Money = money_col()
    effective_from: str = Field(index=True)  # YYYY-MM-DD
    effective_to: Optional[str] = Field(default=None)  # inclusive end; None = open


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


class DeferredRevenueSchedule(SQLModel, table=True):
    """Tracks revenue recognition over time for deferred invoices. IFRS 15.31."""
    __table_args__ = (
        CheckConstraint("frequency IN ('monthly','quarterly','yearly')", name="ck_deferred_freq"),
        CheckConstraint("status IN ('active','completed','cancelled')", name="ck_deferred_status"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    invoice_id: int = Field(foreign_key="invoice.id")
    total_amount: Money = money_col()
    recognised_amount: Money = money_col()
    start_date: str
    end_date: str
    frequency: str = Field(default="monthly")
    next_recognition_date: str
    status: str = Field(default="active")
    deferred_revenue_account_id: int = Field(foreign_key="account.id")
    revenue_account_id: int = Field(foreign_key="account.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RevenueAllocationAudit(SQLModel, table=True):
    """Audit trail for IFRS 15 relative-SSP allocation on an invoice (#259)."""
    __tablename__ = "revenueallocationaudit"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    transaction_price: Money = money_col()
    method: str = Field(default="relative_ssp")  # relative_ssp | none
    detail_json: Optional[list] = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractAsset(SQLModel, table=True):
    """Unbilled receivable after performance obligation satisfied (IFRS 15 #259).

    Certify: Dr Contract Asset (1140) / Cr Revenue.
    Settle on invoice: Cr 1140 instead of Revenue for the remaining amount.
    """
    __tablename__ = "contractasset"
    __table_args__ = (
        CheckConstraint("status IN ('open','closed')", name="ck_contract_asset_status"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    description: str
    certify_date: str
    amount: Money = money_col()
    recognised_amount: Money = money_col()  # settled / billed portion
    revenue_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    asset_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    status: str = Field(default="open", index=True)
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id", index=True)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AnalyticDimension(SQLModel, table=True):
    """Up to 3 tenant-defined analytic dimension types (#260), e.g. Cost Center / Project / Location."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="unique_dimension_code_per_tenant"),
        UniqueConstraint("tenant_id", "sort_order", name="unique_dimension_sort_per_tenant"),
        CheckConstraint(
            "sort_order >= 0 AND sort_order <= 2",
            name="ck_dimension_sort_order",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str                          # e.g. CC / PROJ / LOC
    name: str
    required: bool = Field(default=False)
    sort_order: int = Field(default=0)  # 0–2 → JE analytic_account_id / analytic_2_id / analytic_3_id
    is_active: bool = Field(default=True)


class AnalyticAccount(SQLModel, table=True):
    """Analytic value (cost center / project / …) belonging to a dimension. IAS 1."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="unique_analytic_code_per_tenant"),
        CheckConstraint(
            "type IN ('cost_center','project','department')",
            name="ck_analytic_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str
    name: str
    type: str = Field(default="cost_center")  # legacy label; prefer dimension_id
    dimension_id: Optional[int] = Field(default=None, foreign_key="analyticdimension.id", index=True)
    is_active: bool = Field(default=True)


class PurchaseOrder(SQLModel, table=True):
    """Pre-approval document for purchases. Maps to a Bill on conversion. IAS 2."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_po_number_per_tenant"),
        CheckConstraint(
            "status IN ('draft','approved','received','billed','cancelled')",
            name="ck_po_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")
    vendor_name: Optional[str] = None
    order_date: str
    expected_date: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    subtotal: Money = money_col()
    total: Money = money_col()
    status: str = Field(default="draft")
    bill_id: Optional[int] = Field(default=None, foreign_key="bill.id")
    demand_id: Optional[int] = Field(default=None, foreign_key="purchasedemand.id")
    comparative_id: Optional[int] = Field(default=None, foreign_key="comparativestatement.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PurchaseOrderLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    po_id: int = Field(foreign_key="purchaseorder.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None
    rate: Money = money_col()
    amount: Money = money_col()


class GateInward(SQLModel, table=True):
    """Gate entry at goods receipt (#137 Phase 2). Memo document — no GL,
    no stock movement; stock still arrives at bill posting. The control is
    append-only recording + per-line qty caps + the billing gate."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_gi_number_per_tenant"),
        CheckConstraint("status IN ('open','billed','cancelled')", name="ck_gi_status"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)                       # GI-YYYY-seq
    po_id: int = Field(foreign_key="purchaseorder.id", index=True)
    gate_date: str
    time_in: Optional[str] = None                         # "HH:MM"
    vehicle_no: Optional[str] = None
    challan_no: Optional[str] = None                      # challan / bilty
    remarks: Optional[str] = None
    status: str = Field(default="open")                   # open | billed | cancelled
    cancel_reason: Optional[str] = None
    created_by_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GateInwardLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("qty_received > 0", name="ck_gi_line_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    gate_inward_id: int = Field(foreign_key="gateinward.id", ondelete="CASCADE", index=True)
    po_line_id: int = Field(foreign_key="purchaseorderline.id")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    qty_received: Money = money_col()


class PurchaseDemand(SQLModel, table=True):
    """Purchase requisition — quantity-only memo document (#137 Phase 1).
    Requester never sets prices; that segregation is the control."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_pd_number_per_tenant"),
        CheckConstraint(
            "status IN ('draft','approved','converted','closed','cancelled')",
            name="ck_pd_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    demand_date: str
    required_by: Optional[str] = None
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    purpose: Optional[str] = None
    notes: Optional[str] = None
    status: str = Field(default="draft")
    created_by_id: int = Field(foreign_key="user.id")
    approved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PurchaseDemandLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    demand_id: int = Field(foreign_key="purchasedemand.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None


class VendorQuotation(SQLModel, table=True):
    """One vendor's offer against an approved demand. Memo document."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_vq_number_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    demand_id: int = Field(foreign_key="purchasedemand.id", index=True)
    vendor_id: int = Field(foreign_key="vendor.id")
    quote_date: str
    valid_until: Optional[str] = None
    delivery_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VendorQuotationLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quotation_id: int = Field(foreign_key="vendorquotation.id", ondelete="CASCADE")
    demand_line_id: int = Field(foreign_key="purchasedemandline.id")
    rate: Money = money_col()
    qty: Money = money_col(default=Decimal("1"))
    amount: Money = money_col()


class ComparativeStatement(SQLModel, table=True):
    """Quotation comparison + vendor selection. One per demand. Memo document."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_cs_number_per_tenant"),
        UniqueConstraint("tenant_id", "demand_id", name="unique_cs_per_demand"),
        CheckConstraint(
            "status IN ('draft','approved','converted','cancelled')",
            name="ck_cs_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    demand_id: int = Field(foreign_key="purchasedemand.id", index=True)
    cs_date: str
    selected_quotation_id: Optional[int] = Field(default=None, foreign_key="vendorquotation.id")
    justification: Optional[str] = None
    status: str = Field(default="draft")
    created_by_id: int = Field(foreign_key="user.id")
    approved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    approved_at: Optional[datetime] = None
    # use_alter breaks the CS<->PO FK cycle in metadata.sorted_tables; the
    # demo purge nulls this column before bulk deletes (routers/admin.py).
    po_id: Optional[int] = Field(
        default=None,
        sa_column=Column("po_id", Integer, ForeignKey("purchaseorder.id", use_alter=True)),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Budget(SQLModel, table=True):
    """Monthly account-level budget for variance analysis. IAS 1 management commentary."""
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "account_id", "fiscal_year", "period_month",
            name="unique_budget_per_account_period",
        ),
        CheckConstraint("period_month >= 1 AND period_month <= 12", name="ck_budget_month"),
        CheckConstraint("fiscal_year >= 2000 AND fiscal_year <= 2100", name="ck_budget_year"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    account_id: int = Field(foreign_key="account.id")
    fiscal_year: int
    period_month: int  # 1–12
    amount: Money = money_col()
    label: Optional[str] = None


class FixedAsset(SQLModel, table=True):
    """Long-lived asset with systematic depreciation. IAS 16 / IAS 36 (#258).

    Components: `parent_id` links leaf components under a parent shell.
    Parents are roll-up only (no direct dep/impair/dispose). NBV =
    cost − accum_depr − accum_impairment.
    """
    __tablename__ = "fixedasset"
    __table_args__ = (
        CheckConstraint(
            "method IN ('straight_line','reducing_balance')",
            name="ck_fixed_asset_method",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="fixedasset.id", index=True)
    name: str
    code: Optional[str] = None
    asset_account_id: int = Field(foreign_key="account.id")
    accum_depr_account_id: int = Field(foreign_key="account.id")
    depr_expense_account_id: int = Field(foreign_key="account.id")
    acquisition_date: str
    acquisition_cost: Money = money_col()
    salvage_value: Money = money_col()
    useful_life_months: int
    method: str = Field(default="straight_line")
    accumulated_depreciation: Money = money_col()
    accum_impairment: Money = money_col()
    book_value: Money = money_col()
    is_disposed: bool = Field(default=False)
    last_depreciation_date: Optional[str] = None
    # §3: links asset to the JV that recorded its acquisition (Dr Asset / Cr AP or Bank)
    acquisition_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    disposal_date: Optional[str] = None
    disposal_proceeds: Money = money_col()
    disposal_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DepreciationEntry(SQLModel, table=True):
    """One row per depreciation run on a fixed asset."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    asset_id: int = Field(foreign_key="fixedasset.id")
    depreciation_date: str
    depreciation_amount: Money = money_col()
    transaction_id: int = Field(foreign_key="transaction.id")


class AssetImpairment(SQLModel, table=True):
    """IAS 36 impairment (or reversal) posted against a leaf fixed asset (#258).

    amount > 0 = loss; amount < 0 = reversal. Posted as Dr/Cr Impairment P&L
    vs Accum. Depreciation (gross cost unchanged).
    """
    __tablename__ = "assetimpairment"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    asset_id: int = Field(foreign_key="fixedasset.id", index=True)
    impairment_date: str
    recoverable_amount: Money = money_col()
    carrying_before: Money = money_col()
    amount: Money = money_col()  # >0 loss, <0 reversal
    notes: Optional[str] = None
    transaction_id: int = Field(foreign_key="transaction.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LeaseContract(SQLModel, table=True):
    """IFRS 16 lease — right-of-use asset + lease liability (#256)."""
    __tablename__ = "leasecontract"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_lease_number_per_tenant"),
        CheckConstraint(
            "status IN ('draft','active','terminated')",
            name="ck_lease_status",
        ),
        CheckConstraint(
            "payment_timing IN ('arrears','advance')",
            name="ck_lease_payment_timing",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    name: str
    lessor: Optional[str] = None
    commencement_date: str
    term_months: int
    payment_amount: Money = money_col()
    annual_discount_rate: Money = money_col()  # percent, e.g. 8.00 = 8%
    payment_timing: str = Field(default="arrears")
    initial_direct_costs: Money = money_col()
    # Computed at activation
    present_value: Money = money_col()
    rou_cost: Money = money_col()
    liability_opening: Money = money_col()
    accumulated_depreciation: Money = money_col()
    liability_carrying: Money = money_col()
    status: str = Field(default="draft", index=True)
    # GL accounts (resolved/created on activate)
    rou_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    accum_depr_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    depr_expense_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    liability_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    interest_expense_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    payment_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    initial_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    terminated_at: Optional[str] = None
    termination_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class LeaseScheduleLine(SQLModel, table=True):
    """One period of the IFRS 16 amortisation / depreciation schedule."""
    __tablename__ = "leasescheduleline"
    __table_args__ = (
        UniqueConstraint("lease_id", "period_index", name="uq_lease_schedule_period"),
        CheckConstraint(
            "status IN ('pending','posted')",
            name="ck_lease_schedule_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    lease_id: int = Field(foreign_key="leasecontract.id", index=True)
    period_index: int
    period_date: str
    opening_liability: Money = money_col()
    interest: Money = money_col()
    payment: Money = money_col()
    principal: Money = money_col()
    closing_liability: Money = money_col()
    depreciation: Money = money_col()
    status: str = Field(default="pending", index=True)
    interest_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    payment_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    depr_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    posted_at: Optional[datetime] = None


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


class DebitNote(SQLModel, table=True):
    """Purchase Return — reduces a vendor payable for goods returned. Linked to
    the original bill so stock is reversed at its original cost. Posts
    Dr AP / Cr Inventory (+ Cr GST Input)."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_dn_number_per_tenant"),
        CheckConstraint("status IN ('draft','posted','applied')", name="ck_dn_status"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    bill_id: int = Field(foreign_key="bill.id")            # required — original bill
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")
    vendor_name: Optional[str] = None
    issue_date: str
    description: Optional[str] = None
    notes: Optional[str] = None
    subtotal: Money = money_col()
    gst_amount: Money = money_col()
    total: Money = money_col()
    currency: str = Field(default="PKR")
    exchange_rate: Money = money_col(default=Decimal("1"))
    status: str = Field(default="draft")
    ap_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DebitNoteLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debit_note_id: int = Field(foreign_key="debitnote.id", ondelete="CASCADE")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    description: str
    qty: Money = money_col(default=Decimal("1"))
    unit: Optional[str] = None
    rate: Money = money_col()
    amount: Money = money_col()


class GateOutward(SQLModel, table=True):
    """Dispatch exit at the gate (#137 Phase 2b). Mirrors GateInward but for
    goods leaving: invoice/debit_note sources are pure memo (stock already
    left the books when the source document was created/posted); scrap has
    no source document — its own approval IS the transaction that consumes
    stock and posts GL."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_go_number_per_tenant"),
        CheckConstraint("status IN ('draft','approved','cancelled')", name="ck_go_status"),
        CheckConstraint(
            "source_doc_type IN ('invoice','debit_note','scrap')",
            name="ck_go_source_doc_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)                        # GO-YYYY-seq
    source_doc_type: str                                   # invoice | debit_note | scrap
    source_doc_id: Optional[int] = None                    # null only for scrap
    gate_date: str
    time_out: Optional[str] = None                         # "HH:MM"
    vehicle_no: Optional[str] = None
    challan_no: Optional[str] = None
    remarks: Optional[str] = None
    status: str = Field(default="draft")                   # draft | approved | cancelled
    created_by_id: int = Field(foreign_key="user.id")
    approved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    approved_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GateOutwardLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_go_line_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    gate_outward_id: int = Field(foreign_key="gateoutward.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id")
    qty: Money = money_col()
    unit_cost: Money = money_col(default=Decimal("0"))     # scrap only
    unit_value: Money = money_col(default=Decimal("0"))    # scrap only


class StoreIssue(SQLModel, table=True):
    """Store consumption to a department/cost-center/project (#137 Phase 3).
    Deliberately separate from ProductionOrder's own raw-material
    consumption path — this is the "everything else" leg. Posts GL and
    relieves stock immediately on create; block_negative_stock is the
    control, not a second approver (unlike scrap Gate-Outward)."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_si_number_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)                            # SI-YYYY-seq
    issue_date: str
    from_location_id: int = Field(foreign_key="stocklocation.id")
    analytic_account_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_2_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    analytic_3_id: Optional[int] = Field(default=None, foreign_key="analyticaccount.id")
    debit_account_id: int = Field(foreign_key="account.id")
    notes: Optional[str] = None
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_by_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StoreIssueLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_si_line_qty_positive"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    store_issue_id: int = Field(foreign_key="storeissue.id", ondelete="CASCADE", index=True)
    product_id: int = Field(foreign_key="product.id")
    qty: Money = money_col()
    unit_cost: Money = money_col(default=Decimal("0"))         # written after posting


class AiChatSession(SQLModel, table=True):
    """One AI-assistant conversation (#117). Per-user private: every query
    filters tenant_id AND user_id — same-tenant colleagues never see each
    other's chats."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(default="New chat")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AiChatMessage(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_ai_msg_role"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="aichatsession.id", ondelete="CASCADE", index=True)
    role: str
    content: str
    model: Optional[str] = None          # litellm model string, assistant rows
    agent: Optional[str] = None          # routed specialist-agent key, assistant rows
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CustomerAdvance(SQLModel, table=True):
    """Advance received from a customer (prepayment). Posts Dr Bank / Cr 2310.
    Applied later against an invoice via the payments machinery."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_cadv_number_per_tenant"),
        CheckConstraint("status IN ('open','partial','applied')", name="ck_cadv_status"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    customer_id: int = Field(foreign_key="customer.id")
    date: str
    amount: Money = money_col()
    applied_amount: Money = money_col()
    cash_account_id: int = Field(foreign_key="account.id")        # bank/cash received into
    advance_account_id: int = Field(foreign_key="account.id")     # 2310 Customer Advances
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    status: str = Field(default="open")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VendorAdvance(SQLModel, table=True):
    """Advance paid to a vendor (prepayment). Posts Dr 1260 / Cr Bank.
    Applied later against a bill via the payments machinery."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="unique_vadv_number_per_tenant"),
        CheckConstraint("status IN ('open','partial','applied')", name="ck_vadv_status"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    vendor_id: int = Field(foreign_key="vendor.id")
    date: str
    amount: Money = money_col()
    applied_amount: Money = money_col()
    cash_account_id: int = Field(foreign_key="account.id")        # bank/cash paid out of
    advance_account_id: int = Field(foreign_key="account.id")     # 1260 Advances to Vendors
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    status: str = Field(default="open")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


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


class RevokedToken(SQLModel, table=True):
    """JWT denylist (#113). Logout inserts the token's jti here; every
    authenticated request checks it, so a logged-out token dies immediately
    instead of surviving until its natural 24h expiry. DB-backed (not
    in-memory) for the same reason as LoginAttempt: revocation must hold
    across every uvicorn worker, and this app can't take a Redis dependency
    (offline Electron/script-installer distribution).

    expires_at is copied from the token's own exp claim, so the background
    prune (main.py lifespan) never keeps a row alive past the point the
    token would have expired anyway.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    jti: str = Field(unique=True, index=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    expires_at: datetime = Field(index=True)


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
    # Plaid (or other feed) transaction id for de-dupe on sync (#214)
    external_id: Optional[str] = Field(default=None, index=True)
    # Bank-feed harden (#268)
    suggested_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    match_confidence: Optional[float] = None  # 0–100
    categorized_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    # null | suggested | accepted | rejected
    match_status: Optional[str] = Field(default=None, index=True)
    match_decided_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    match_decided_at: Optional[datetime] = None
    expense_draft_suggested: bool = Field(default=False)


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


class PRASubmissionLog(SQLModel, table=True):
    """Audit trail of every outbound call to the PRA e-IMS API."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True)
    invoice_id: int = Field(index=True)
    attempt_at: datetime = Field(default_factory=datetime.utcnow)
    endpoint: str
    request_json: str
    response_code: Optional[str] = None   # PRA code "100" = success
    response_json: Optional[str] = None
    http_status: Optional[int] = None
    success: bool = Field(default=False)
    error_message: Optional[str] = None


class UaeEinvoiceLog(SQLModel, table=True):
    """Audit trail for UAE FTA e-invoice adapter attempts (sandbox stub or live)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True)
    invoice_id: int = Field(index=True)
    attempt_at: datetime = Field(default_factory=datetime.utcnow)
    endpoint: str
    request_json: str
    response_uuid: Optional[str] = None
    response_json: Optional[str] = None
    http_status: Optional[int] = None
    success: bool = Field(default=False)
    error_message: Optional[str] = None
    sandbox: bool = Field(default=True)


class ZatcaSubmissionLog(SQLModel, table=True):
    """Audit trail of every outbound call to the ZATCA Fatoora API (#264)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True)
    invoice_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    request_payload: str
    response_payload: Optional[str] = None
    status: str = Field(default="error")  # cleared|reported|rejected|error|submitted
    http_status: Optional[int] = None
    endpoint: Optional[str] = None
    error_message: Optional[str] = None
    sandbox: bool = Field(default=True)


class PeppolSubmissionLog(SQLModel, table=True):
    """Audit trail of every outbound call to a Peppol Access Point (#266)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True)
    invoice_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    request_payload: str
    response_payload: Optional[str] = None
    status: str = Field(default="error")  # accepted|rejected|error|submitted
    http_status: Optional[int] = None
    endpoint: Optional[str] = None
    error_message: Optional[str] = None
    sandbox: bool = Field(default=True)
    document_id: Optional[str] = None


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


class AllocationInput(SQLModel):
    """Inline allocation when posting a CR/BR/CP/BP voucher from the entry form."""
    invoice_id: Optional[int] = None
    bill_id: Optional[int] = None
    amount: Decimal


class TransactionCreate(TransactionBase):
    tenant_id: Optional[int] = None  # set by server from JWT
    voucher_type: str = "JV"         # classification → per-type number series (#52 §4)
    entries: List[JournalEntryCreate]
    allocations: Optional[List["AllocationInput"]] = None
    analytic_account_id: Optional[int] = None
    analytic_2_id: Optional[int] = None
    analytic_3_id: Optional[int] = None
    analytic_ids: Optional[List[int]] = None  # maps to slots 0–2 (#260)
    customer_id: Optional[int] = None
    vendor_id: Optional[int] = None


class TransactionRead(TransactionBase):
    id: int
    jv_number: str
    entries: List["JournalEntryRead"]


class JournalEntryRead(JournalEntryBase):
    account_name: str
    account_type: str


class ReportDefinition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    source_key: str
    config: str = Field(sa_column=Column(JSON))   # ReportConfig JSON
    visibility: str = Field(default="private")    # "private" | "shared"
    owner_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Payroll models ────────────────────────────────────────────────────────────

class Employee(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    employee_code: str
    name: str
    department: Optional[str] = None
    designation: Optional[str] = None
    join_date: Optional[str] = None          # ISO date string
    cnic: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class SalaryComponent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    code: str                                # e.g. BASIC, HRA, TAX, EOBI
    component_type: str                      # "earnings" | "deductions" | "statutory"
    is_taxable: bool = False
    is_fixed: bool = True                    # fixed amount vs % of basic
    gl_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    is_active: bool = True


class EmployeeSalaryStructure(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: int = Field(index=True, foreign_key="employee.id")
    component_id: int = Field(foreign_key="salarycomponent.id")
    amount: float = 0.0
    pct_of_basic: Optional[float] = None    # if not is_fixed, compute as pct
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


class PayrollRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    period_start: str
    period_end: str
    pay_date: str
    status: str = "draft"                   # draft | approved | posted | void
    notes: Optional[str] = None
    jv_number: Optional[str] = None
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class PayrollLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    payroll_run_id: int = Field(index=True, foreign_key="payrollrun.id")
    employee_id: int = Field(foreign_key="employee.id")
    gross_earnings: float = 0.0
    total_deductions: float = 0.0
    net_pay: float = 0.0


class PayrollLineDetail(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    payroll_line_id: int = Field(index=True, foreign_key="payrollline.id")
    component_id: int = Field(foreign_key="salarycomponent.id")
    amount: float = 0.0
    is_override: bool = False


class AttendanceRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    employee_id: int = Field(index=True, foreign_key="employee.id")
    date: str                               # ISO date "YYYY-MM-DD"
    time_in: Optional[str] = None          # "HH:MM" 24h
    time_out: Optional[str] = None         # "HH:MM" 24h
    hours_worked: Optional[float] = None   # computed on save
    status: str = "present"                # present|absent|half_day|leave|holiday|off
    notes: Optional[str] = None
    source: str = "manual"                 # manual|biometric
    raw_data: Optional[str] = None         # JSON string — future biometric payload
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class LeaveType(SQLModel, table=True):
    """Leave catalogue (#303) — annual entitlement + paid/unpaid flag."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="unique_leave_type_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)  # AL, SL, UL…
    name: str
    is_paid: bool = Field(default=True)
    annual_entitlement: float = Field(default=0)  # days per year
    is_active: bool = Field(default=True)


class LeaveBalance(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "employee_id", "leave_type_id", "year",
            name="unique_leave_balance",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    employee_id: int = Field(foreign_key="employee.id", index=True)
    leave_type_id: int = Field(foreign_key="leavetype.id", index=True)
    year: int
    entitled: float = Field(default=0)
    used: float = Field(default=0)
    pending: float = Field(default=0)


class LeaveRequest(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name="ck_leave_request_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    employee_id: int = Field(foreign_key="employee.id", index=True)
    leave_type_id: int = Field(foreign_key="leavetype.id", index=True)
    from_date: str
    to_date: str
    days: float = Field(default=1)
    status: str = Field(default="pending", index=True)
    reason: Optional[str] = None
    created_by_id: int = Field(foreign_key="user.id")
    approved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    approved_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExpenseClaim(SQLModel, table=True):
    """Employee expense claim → AP reimbursement bill on approve (#303)."""
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_expense_claim_number"),
        CheckConstraint(
            "status IN ('draft','submitted','approved','rejected','cancelled')",
            name="ck_expense_claim_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)  # EC-YYYY-seq
    employee_id: int = Field(foreign_key="employee.id", index=True)
    claim_date: str
    description: Optional[str] = None
    status: str = Field(default="draft", index=True)
    total: Money = money_col(default=Decimal("0"))
    bill_id: Optional[int] = Field(default=None, foreign_key="bill.id")
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    approved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    approved_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExpenseClaimLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expense_claim_line_amount"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    claim_id: int = Field(foreign_key="expenseclaim.id", ondelete="CASCADE", index=True)
    description: str
    amount: Money = money_col()
    expense_account_id: Optional[int] = Field(default=None, foreign_key="account.id")


# ── Wave B–D cloud / parity / AI models (#118–#125) ──────────────────────────

class PortalToken(SQLModel, table=True):
    """Magic-link access for customer/vendor/patient portal (#120 + lab publish)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    entity_type: str  # customer | vendor | patient
    entity_id: int = Field(index=True)
    token_hash: str = Field(index=True)
    expires_at: datetime
    permissions: list = Field(default_factory=lambda: ["view_invoices", "pay"], sa_column=Column(JSON))
    last_accessed: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PortalDispute(SQLModel, table=True):
    """Customer dispute / note thread on an invoice via portal (#270)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    body: str
    status: str = Field(default="open", index=True)  # open | resolved
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class DunningRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    days_overdue: int = Field(default=3)
    subject_template: str = "Payment reminder: invoice {{ number }}"
    body_template: str = "Dear {{ customer_name }}, invoice {{ number }} for {{ amount }} is overdue."
    is_active: bool = Field(default=True)


class ApprovalWorkflow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    document_type: str  # see services.approval_document_types (full product LOV)
    name: str
    is_active: bool = Field(default=True)


class ApprovalStep(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="approvalworkflow.id", index=True)
    step_order: int = Field(default=0)
    approver_role: Optional[str] = None
    approver_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    min_amount: Optional[float] = None
    timeout_hours: Optional[int] = None


class ApprovalRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    workflow_id: int = Field(foreign_key="approvalworkflow.id")
    document_type: str
    document_id: int = Field(index=True)
    current_step: int = Field(default=0)
    status: str = Field(default="pending", index=True)  # pending|approved|rejected|timed_out
    requested_by_id: int = Field(foreign_key="user.id")
    # Snapshotted at submit so later doc edits can't retarget the threshold chain (#269)
    amount: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    notes: Optional[str] = None


class ApprovalSubstitute(SQLModel, table=True):
    """Out-of-office / delegate approver for a date range (#269)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)  # principal being covered
    substitute_user_id: int = Field(foreign_key="user.id", index=True)
    starts_on: str  # YYYY-MM-DD
    ends_on: str    # YYYY-MM-DD
    is_active: bool = Field(default=True)


class ApprovalDecision(SQLModel, table=True):
    """Append-only audit trail for approve/reject actions (#269)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    request_id: int = Field(foreign_key="approvalrequest.id", index=True)
    actor_id: int = Field(foreign_key="user.id")
    action: str  # approve | reject
    step_index: int = Field(default=0)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PlaidConnection(SQLModel, table=True):
    """Bank feed connection (#121 / #301).

    Historically Plaid-only; ``provider`` now selects the adapter
    (``plaid`` | ``mock`` | future EU/UK Open Banking). Sync health lives on
    ``sync_status`` / ``last_error`` / ``consent_expires_at`` so the UI can
    distinguish expired AIS consent from a broken pull.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    bank_account_id: Optional[int] = Field(default=None, foreign_key="bankaccount.id")
    access_token: str  # encrypted (or opaque mock token)
    item_id: str = Field(index=True)
    institution_name: str = ""
    last_sync: Optional[datetime] = None
    is_active: bool = Field(default=True)
    # #301 — multi-provider sync status
    provider: str = Field(default="plaid", index=True)  # plaid | mock | …
    last_error: Optional[str] = None
    sync_status: str = Field(default="never")  # never | ok | error | consent_expired
    consent_expires_at: Optional[datetime] = None



class CategorizationRule(SQLModel, table=True):
    """Bank-feed categorization rule (#121 / #268).

    First matching rule by ascending `priority` wins. `pattern` is a
    case-insensitive substring of the statement description; optional
    `match_amount` further requires an exact debit-or-credit amount.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    pattern: str  # substring match on statement description
    account_id: int = Field(foreign_key="account.id")
    is_active: bool = Field(default=True)
    priority: int = Field(default=100, index=True)  # lower = higher priority
    match_amount: Optional[float] = None  # exact |debit| or |credit| when set
    create_expense_draft: bool = Field(default=False)


class AgentSuggestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    kind: str = Field(index=True)
    title: str
    body: str = ""
    action_href: Optional[str] = None
    action_label: Optional[str] = None
    dismissed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class AgentAutomation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    trigger: str  # monthly_1st | on_bank_sync | on_month_end | daily
    agent_prompt: str = ""
    is_active: bool = Field(default=True)
    last_run: Optional[datetime] = None
    dry_run_only: bool = Field(default=True)


# Re-exports follow (telecom / healthcare / weaving).
from models_telecom import (  # noqa: E402,F401
    AirtimeSale, AirtimeStock, CommissionLine, CommissionStatement,
    DeviceImei, FcaEvent, FranchiseAgreement, KpiTarget, LoadTransfer,
    MobileMoneyAccount, MobileMoneyTransaction, Operator,
    PostpaidBillCycle, PostpaidConnection, RetailOutlet, RsoAgent,
    RsoDailyCollection, RsoStockIssue, RsoTarget, SimActivation, SimBatch,
    TrackerAccount, TrackerTransaction,
)
from models_healthcare import (  # noqa: E402,F401
    HcPatient, HcDoctor, HcWard, HcBed, HcProcedureCatalog, HcProcedureConsumable,
    HcOpdToken, HcOpdVisit, HcPrescription, HcPrescriptionItem,
    HcAdmission, HcAdmissionCharge,
    HcLabTest, HcLabOrder, HcLabOrderItem, HcSampleCollection,
    HcProcedureOrder, HcStoreIssue, HcStoreIssueItem,
    HcDialysisUnit, HcDialysisMachine, HcDialysisShift, HcDialysisSession,
)
from models_weaving import (  # noqa: E402,F401
    WvFabricQuality, WvLoom, WvYarnType, WvShift, WvOperator,
    WvContract, WvYarnInward, WvSizing, WvProduction, WvDispatch, WvCalcRun,
)
from models_spinning import (  # noqa: E402,F401
    SpYarnSpec, SpFiberGrade, SpMachine, SpShift, SpOperator, SpWasteType,
    SpRecipe, SpRecipeLine, SpProductionPlan, SpSpinLot,
    SpBaleReceipt, SpStageEntry, SpConeOutput, SpWasteLog, SpYarnDispatch, SpCalcRun,
)
from models_textile_processing import (  # noqa: E402,F401
    TpQuality, TpProcess, TpContractor, TpSalesOrder,
    TpSalesOrderQualityLine, TpSalesOrderPackingLine,
    TpGreyLot, TpGreyThan,
    TpKachiParchi, TpMending, TpPakkiParchi, TpRejectionIssueNote, TpRejectionOgp,
    TpProductionOrder, TpStageEntry as TpStageEntry, TpPacking, TpBaling,
    TpDispatch, TpGreySettlement, TpLaborBill, TpInspection,
)
from models_pos import PosRegister, PosShift, PosSale  # noqa: E402,F401
from models_ecommerce import (  # noqa: E402,F401
    EcommerceConnection, EcommerceProductMap, EcommerceOrderImport,
)
