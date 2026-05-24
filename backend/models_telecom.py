"""
SQLModel tables for the telecom-franchise business model.

Covers the operational entities described in
TELECOM_FRANCHISE_BLUEPRINT.md §4 and the corrected operational reference §7:

  Operator + Tracker (deposit wallet, transactions, load orders, stock auto-debit)
  SIM lifecycle (batches, activations, IMSI inventory)
  Airtime / scratch-card inventory + retail sales
  Load distribution chain (MSR -> RSO -> Retail) + FCA events
  Mobile-money agency (wallet accounts + customer txns)
  Device sales with IMEI tracking
  Postpaid billing (connections, monthly cycles, remittance)
  Commission tracking (statements + lines + accruals)
  RSO channel (agents, retail outlets, stock issues, daily collections, targets)
  Franchise administration (agreement, KPI targets, royalty)

All tables include tenant_id (required for multi-tenancy), money columns are
NUMERIC(18,4) via money_col(), and most carry FK transaction_id to wire each
domain event to its posted GL JV.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from services.money import ZERO


def _money(default: Decimal = ZERO, **kw):
    from sqlalchemy import Column
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


# ── Operator ────────────────────────────────────────────────────────────────


class Operator(SQLModel, table=True):
    __tablename__ = "tc_operator"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operator_code", name="uq_operator_code_per_tenant"),
        CheckConstraint(
            "commission_settlement_cycle IN ('daily','weekly','monthly')",
            name="ck_operator_cycle",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    operator_code: str = Field(index=True)
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    commission_settlement_cycle: str = Field(default="monthly")
    # GL account FKs let the posting service post without hard-coding codes.
    deposit_account_id: Optional[int] = Field(default=None, foreign_key="account.id")  # 1210
    load_account_id: Optional[int] = Field(default=None, foreign_key="account.id")     # 1211
    payable_account_id: Optional[int] = Field(default=None, foreign_key="account.id")  # 2010
    advance_account_id: Optional[int] = Field(default=None, foreign_key="account.id")  # 1210/2300
    commission_account_id: Optional[int] = Field(default=None, foreign_key="account.id")  # 4020
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Tracker (operator-side wallet that mirrors the franchise's deposits) ───


class TrackerAccount(SQLModel, table=True):
    __tablename__ = "tc_tracker_account"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operator_id", "account_number",
                         name="uq_tracker_per_operator"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_id: int = Field(foreign_key="tc_operator.id", index=True)
    account_number: str
    # Denormalised running balances; invariant: must match GL at all times.
    deposit_balance: Decimal = _money()
    load_balance: Decimal = _money()
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TrackerTransaction(SQLModel, table=True):
    __tablename__ = "tc_tracker_transaction"
    __table_args__ = (
        CheckConstraint(
            "txn_type IN ('deposit','load_order','stock_debit',"
            "'commission_credit','penalty_debit','adjustment')",
            name="ck_tracker_txn_type",
        ),
        CheckConstraint("amount >= 0", name="ck_tracker_amount_nonneg"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    tracker_account_id: int = Field(foreign_key="tc_tracker_account.id", index=True)
    txn_date: str  # ISO date
    txn_type: str
    amount: Decimal = _money()                # always positive; sign implied by type
    load_disbursed: Decimal = _money()        # for load_order: 103% of amount
    commission_earned: Decimal = _money()     # for load_order: 3% uplift
    tracker_reference: Optional[str] = None
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    is_reconciled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── SIM lifecycle ──────────────────────────────────────────────────────────


class SimBatch(SQLModel, table=True):
    __tablename__ = "tc_sim_batch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_number", name="uq_sim_batch_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_id: int = Field(foreign_key="tc_operator.id", index=True)
    batch_number: str
    series_from: Optional[str] = None
    series_to: Optional[str] = None
    qty_received: int
    qty_activated: int = Field(default=0)
    unit_cost: Decimal = _money()
    received_date: str
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SimActivation(SQLModel, table=True):
    __tablename__ = "tc_sim_activation"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sim_number", name="uq_sim_msisdn_per_tenant"),
        CheckConstraint(
            "activation_type IN ('prepaid','postpaid','biometric')",
            name="ck_sim_activation_type",
        ),
        CheckConstraint(
            "status IN ('pending','active','rejected','ported')",
            name="ck_sim_activation_status",
        ),
        CheckConstraint(
            "commission_status IN ('pending','accrued','settled')",
            name="ck_sim_commission_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_id: int = Field(foreign_key="tc_operator.id", index=True)
    sim_number: str                              # MSISDN
    batch_id: Optional[int] = Field(default=None, foreign_key="tc_sim_batch.id")
    activation_date: str
    customer_name: Optional[str] = None
    customer_cnic: Optional[str] = None
    activation_type: str = Field(default="prepaid")
    status: str = Field(default="pending")
    commission_rate: Decimal = _money()          # snapshot
    commission_status: str = Field(default="pending")
    commission_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    invoice_line_id: Optional[int] = Field(default=None, foreign_key="invoiceline.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Airtime / scratch-card inventory ───────────────────────────────────────


class AirtimeStock(SQLModel, table=True):
    __tablename__ = "tc_airtime_stock"
    __table_args__ = (
        CheckConstraint(
            "stock_type IN ('scratch_card','pin_code','digital_bundle')",
            name="ck_airtime_stock_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_id: int = Field(foreign_key="tc_operator.id", index=True)
    stock_type: str
    denomination: Decimal = _money()
    qty_received: int
    qty_sold: int = Field(default=0)
    unit_cost: Decimal = _money()
    purchase_date: str
    expiry_date: Optional[str] = None
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AirtimeSale(SQLModel, table=True):
    __tablename__ = "tc_airtime_sale"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('walk_in','rso','pos_terminal','retail')",
            name="ck_airtime_sale_channel",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    stock_id: int = Field(foreign_key="tc_airtime_stock.id", index=True)
    sale_date: str
    qty: int
    face_value: Decimal = _money()
    sale_price: Decimal = _money()
    margin: Decimal = _money()
    channel: str = Field(default="walk_in")
    rso_id: Optional[int] = Field(default=None, foreign_key="tc_rso_agent.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Load distribution (MSR → RSO → Retail) ─────────────────────────────────


class LoadTransfer(SQLModel, table=True):
    """Each hop of the load-distribution chain. MSR→RSO and RSO→Retail are
    two rows; each creates a GL JV (Dr next-level receivable / Cr current
    receivable or load float)."""
    __tablename__ = "tc_load_transfer"
    __table_args__ = (
        CheckConstraint("from_type IN ('msr','rso')", name="ck_loadxfer_from"),
        CheckConstraint("to_type IN ('rso','retail')", name="ck_loadxfer_to"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    transfer_date: str
    from_type: str
    from_ref_id: Optional[int] = None  # msr=tracker_account.id, rso=rso_agent.id
    to_type: str
    to_ref_id: int                     # rso_agent.id or retail_outlet.id
    amount: Decimal = _money()
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    is_settled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RetailOutlet(SQLModel, table=True):
    __tablename__ = "tc_retail_outlet"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    rso_id: int = Field(foreign_key="tc_rso_agent.id", index=True)
    shop_name: str
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FcaEvent(SQLModel, table=True):
    """First-Call-Attempt event. No GL posting per event — counted toward the
    monthly target and rolled up to commission via kpi_target."""
    __tablename__ = "tc_fca_event"
    __table_args__ = (
        CheckConstraint(
            "source_channel IN ('counter','rso_retail','direct')",
            name="ck_fca_source",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    sim_id: Optional[int] = Field(default=None, foreign_key="tc_sim_activation.id")
    event_date: str
    msisdn: str
    source_channel: str = Field(default="rso_retail")
    kpi_target_id: Optional[int] = Field(default=None, foreign_key="tc_kpi_target.id")
    synced_from_tracker: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Mobile money agency (JazzCash / EasyPaisa) ─────────────────────────────


class MobileMoneyAccount(SQLModel, table=True):
    __tablename__ = "tc_mm_account"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_number", name="uq_mm_account_per_tenant"),
        CheckConstraint(
            "account_type IN ('jazzcash','easypaisa','nayapay','other')",
            name="ck_mm_account_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_id: int = Field(foreign_key="tc_operator.id", index=True)
    account_number: str
    account_type: str = Field(default="jazzcash")
    float_asset_account_id: Optional[int] = Field(default=None, foreign_key="account.id")    # 1214
    float_liability_account_id: Optional[int] = Field(default=None, foreign_key="account.id")  # 2100
    commission_account_id: Optional[int] = Field(default=None, foreign_key="account.id")     # 4022
    current_float_balance: Decimal = _money()
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MobileMoneyTransaction(SQLModel, table=True):
    __tablename__ = "tc_mm_transaction"
    __table_args__ = (
        CheckConstraint(
            "txn_type IN ('deposit','withdrawal','transfer_in','transfer_out',"
            "'bill_payment','commission_credit','float_top_up','float_withdrawal','adjustment')",
            name="ck_mm_txn_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    mm_account_id: int = Field(foreign_key="tc_mm_account.id", index=True)
    txn_date: str
    txn_type: str
    amount: Decimal = _money()
    fee_charged: Decimal = _money()
    commission_earned: Decimal = _money()
    customer_reference: Optional[str] = None
    operator_txn_id: Optional[str] = None
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    is_reconciled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Device IMEI tracking ───────────────────────────────────────────────────


class DeviceImei(SQLModel, table=True):
    __tablename__ = "tc_device_imei"
    __table_args__ = (
        UniqueConstraint("tenant_id", "imei_number", name="uq_device_imei_per_tenant"),
        CheckConstraint(
            "status IN ('in_stock','sold','returned','demo')",
            name="ck_device_imei_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    imei_number: str
    serial_number: Optional[str] = None
    status: str = Field(default="in_stock")
    purchase_invoice_line_id: Optional[int] = Field(default=None, foreign_key="billline.id")
    sale_invoice_line_id: Optional[int] = Field(default=None, foreign_key="invoiceline.id")
    sale_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Postpaid franchise billing ─────────────────────────────────────────────


class PostpaidConnection(SQLModel, table=True):
    __tablename__ = "tc_postpaid_connection"
    __table_args__ = (
        UniqueConstraint("tenant_id", "msisdn", name="uq_postpaid_msisdn_per_tenant"),
        CheckConstraint(
            "status IN ('active','suspended','terminated')",
            name="ck_postpaid_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_id: int = Field(foreign_key="tc_operator.id", index=True)
    msisdn: str
    customer_name: str
    customer_cnic: Optional[str] = None
    plan_name: str
    monthly_rental: Decimal = _money()
    activation_date: str
    status: str = Field(default="active")
    franchise_commission_rate: Decimal = _money()  # %
    last_billed_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PostpaidBillCycle(SQLModel, table=True):
    __tablename__ = "tc_postpaid_bill_cycle"
    __table_args__ = (
        UniqueConstraint("tenant_id", "connection_id", "billing_month",
                         name="uq_postpaid_cycle_per_month"),
        CheckConstraint(
            "collection_status IN ('pending','partial','collected')",
            name="ck_postpaid_collection_status",
        ),
        CheckConstraint(
            "remittance_status IN ('pending','remitted')",
            name="ck_postpaid_remittance_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    connection_id: int = Field(foreign_key="tc_postpaid_connection.id", index=True)
    billing_month: str   # ISO date — first day of month
    gross_amount: Decimal = _money()
    franchise_commission: Decimal = _money()
    net_remittance: Decimal = _money()
    collection_status: str = Field(default="pending")
    remittance_status: str = Field(default="pending")
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    remittance_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Commission tracking ────────────────────────────────────────────────────


class CommissionStatement(SQLModel, table=True):
    __tablename__ = "tc_commission_statement"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received','reconciled','disputed')",
            name="ck_commission_statement_status",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_id: int = Field(foreign_key="tc_operator.id", index=True)
    statement_date: str
    period_from: str
    period_to: str
    statement_reference: Optional[str] = None
    total_commission: Decimal = _money()
    status: str = Field(default="received")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommissionLine(SQLModel, table=True):
    __tablename__ = "tc_commission_line"
    __table_args__ = (
        CheckConstraint(
            "commission_type IN ('activation','recharge','digital','bundle',"
            "'postpaid','incentive','load_uplift','fca_target')",
            name="ck_commission_line_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    statement_id: int = Field(foreign_key="tc_commission_statement.id", index=True)
    commission_type: str
    event_reference: Optional[str] = None
    event_date: Optional[str] = None
    accrued_amount: Decimal = _money()
    settled_amount: Decimal = _money()
    variance: Decimal = _money()
    is_disputed: bool = Field(default=False)


# ── RSO channel ────────────────────────────────────────────────────────────


class RsoAgent(SQLModel, table=True):
    __tablename__ = "tc_rso_agent"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    phone: Optional[str] = None
    cnic: Optional[str] = None
    territory: Optional[str] = None
    receivable_account_id: Optional[int] = Field(default=None, foreign_key="account.id")  # 1120
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RsoStockIssue(SQLModel, table=True):
    __tablename__ = "tc_rso_stock_issue"
    __table_args__ = (
        CheckConstraint(
            "stock_type IN ('scratch_card','sim_batch','bundle','imsi')",
            name="ck_rso_stock_type",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    rso_id: int = Field(foreign_key="tc_rso_agent.id", index=True)
    issue_date: str
    stock_type: str
    stock_ref_id: int                       # airtime_stock.id, sim_batch.id, etc.
    qty_issued: int
    face_value: Decimal = _money()
    cost_value: Decimal = _money()
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RsoDailyCollection(SQLModel, table=True):
    """Daily cash deposit from RSO. Splits between load settlement and stock
    settlement. Variance posts to 5070 Tracker / Float Variance."""
    __tablename__ = "tc_rso_daily_collection"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    rso_id: int = Field(foreign_key="tc_rso_agent.id", index=True)
    collection_date: str
    load_portion: Decimal = _money()
    stock_portion: Decimal = _money()
    total_deposited: Decimal = _money()
    load_outstanding_before: Decimal = _money()
    stock_outstanding_before: Decimal = _money()
    variance: Decimal = _money()
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    is_reconciled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RsoTarget(SQLModel, table=True):
    __tablename__ = "tc_rso_target"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rso_id", "target_month",
                         name="uq_rso_target_per_month"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    rso_id: int = Field(foreign_key="tc_rso_agent.id", index=True)
    target_month: str
    target_activations: int = Field(default=0)
    target_recharge_value: Decimal = _money()
    actual_activations: int = Field(default=0)
    actual_recharge_value: Decimal = _money()
    incentive_earned: Decimal = _money()
    penalty_applied: Decimal = _money()
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Franchise administration ───────────────────────────────────────────────


class FranchiseAgreement(SQLModel, table=True):
    __tablename__ = "tc_franchise_agreement"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_id: int = Field(foreign_key="tc_operator.id", index=True)
    agreement_number: str
    start_date: str
    end_date: Optional[str] = None
    franchise_fee_paid: Decimal = _money()
    royalty_rate_pct: Decimal = _money()
    min_monthly_target: Decimal = _money()
    penalty_rate_pct: Decimal = _money()
    intangible_account_id: Optional[int] = Field(default=None, foreign_key="account.id")  # 1300
    amortisation_account_id: Optional[int] = Field(default=None, foreign_key="account.id")  # 5030
    amortisation_months: int = Field(default=60)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KpiTarget(SQLModel, table=True):
    __tablename__ = "tc_kpi_target"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operator_id", "target_month", "metric",
                         name="uq_kpi_target_per_month"),
        CheckConstraint(
            "metric IN ('activations','recharges','mm_transactions',"
            "'postpaid_additions','device_sales','fca')",
            name="ck_kpi_metric",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    operator_id: int = Field(foreign_key="tc_operator.id", index=True)
    target_month: str
    metric: str
    target_value: Decimal = _money()
    actual_value: Decimal = _money()
    achievement_pct: Decimal = _money()
    incentive_earned: Decimal = _money()
    penalty_applied: Decimal = _money()
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
