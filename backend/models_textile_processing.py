"""
SQLModel tables for the Textile Processing / Printing Unit (ballor) module.

Customer owns grey; unit processes/prints only. Custodial grey is memo;
process billing, labor AP, grey credit, and wastage revenue post via posting.py.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, JSON, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from services.money import ZERO


def _money(default: Decimal = ZERO, **kw):
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


def _qty(default: Decimal = ZERO, **kw):
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


# Default PPC pipeline after mending (mending is pre-PO, not a stage entry).
# "Production" renamed to "prep" in seed code to avoid clash with TpProductionOrder.
# Dyeing (65) sits beside Printing (70) — SO/process_rates pick which path applies.
DEFAULT_PROCESSES: tuple[tuple[int, str, str, bool], ...] = (
    (10, "prep", "Production Prep", True),
    (20, "salai", "Salai", True),
    (30, "singing", "Singing", True),
    (40, "desizing", "Desizing", True),
    (50, "washing", "Washing / Jet", True),
    (60, "batching", "Batching", True),
    (65, "dyeing", "Dyeing", True),
    (70, "printing", "Printing", True),
    (80, "ageing", "Ageing", True),
    (90, "stentoring", "Stentoring", True),
    (100, "calender", "Calender", True),
    (110, "sanforising", "Sanforising", True),
    (120, "comforting", "Comforting", True),
    (130, "folding", "Folding", True),
    (140, "packing", "Packing", False),
    (150, "baling", "Baling", False),
    (160, "dispatch", "Dispatch", False),
)

# Fresh packing assortment codes (SO planned lines + packing docs).
PACKING_ITEM_TYPES: tuple[str, ...] = ("KMZ", "SHL", "DPT", "2PC", "3PC", "OTHER")


# ── Masters ──────────────────────────────────────────────────────────────────


class TpQuality(SQLModel, table=True):
    """Grey quality master.

    Structured CODE form: ``{fiber} {warp}X{weft} {epi}X{ppi} {width}"``
    e.g. ``CTN 60X60 40X52 45"``. Free-text ``code`` remains the unique key;
    structured columns feed the formatter when present.
    """
    __tablename__ = "tp_quality"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tp_quality_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    blend: Optional[str] = None
    width: Optional[str] = None
    unit: str = Field(default="MTR")  # MTR | YRD
    # Structured segments for CODE STRUCTURE (optional; code may still be free-text)
    fiber: Optional[str] = None          # CTN | PC | CVC | …
    warp_count: Optional[str] = None     # e.g. 60
    weft_count: Optional[str] = None     # e.g. 60
    epi: Optional[str] = None            # ends per inch
    ppi: Optional[str] = None            # picks per inch
    width_inch: Optional[str] = None     # e.g. 45
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TpProcess(SQLModel, table=True):
    __tablename__ = "tp_process"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tp_process_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    seq: int = Field(default=0, index=True)
    code: str = Field(index=True)
    name: str
    is_billing: bool = Field(default=True)
    default_sale_rate: Decimal = _money()
    contractor_expense_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TpContractor(SQLModel, table=True):
    __tablename__ = "tp_contractor"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tp_contractor_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    vendor_id: int = Field(foreign_key="vendor.id", index=True)
    default_process_id: Optional[int] = Field(default=None, foreign_key="tp_process.id")
    phone: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Commercial / grey intake ─────────────────────────────────────────────────


class TpSalesOrder(SQLModel, table=True):
    __tablename__ = "tp_sales_order"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_sales_order_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    # Primary / first grey quality (compat); full list lives in TpSalesOrderQualityLine
    quality_id: int = Field(foreign_key="tp_quality.id", index=True)
    date: str = Field(index=True)
    expected_mtr: Decimal = _qty()
    grey_rate: Decimal = _money()  # customer grey valuation for return credit
    # JSON list of {process_id, rate, enabled}
    process_rates: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="open", index=True)  # open|in_process|closed|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpSalesOrderQualityLine(SQLModel, table=True):
    """Grey quality input line on a sales order (many qualities per SO)."""
    __tablename__ = "tp_sales_order_quality_line"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    sales_order_id: int = Field(foreign_key="tp_sales_order.id", index=True)
    quality_id: int = Field(foreign_key="tp_quality.id", index=True)
    expected_mtr: Decimal = _qty()
    grey_rate: Decimal = _money()
    notes: Optional[str] = None


class TpSalesOrderPackingLine(SQLModel, table=True):
    """Planned fresh packing assortment on a sales order.

    item_type: KMZ | SHL | DPT | 2PC | 3PC | OTHER — each line may target a
    different grey quality and process path (printing / dyeing).
    """
    __tablename__ = "tp_sales_order_packing_line"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    sales_order_id: int = Field(foreign_key="tp_sales_order.id", index=True)
    item_type: str = Field(default="KMZ", index=True)
    quality_id: int = Field(foreign_key="tp_quality.id", index=True)
    process_id: Optional[int] = Field(default=None, foreign_key="tp_process.id")
    qty: Decimal = _qty()          # pieces or packs
    meters: Decimal = _qty()
    rate: Decimal = _money()
    notes: Optional[str] = None


class TpGreyLot(SQLModel, table=True):
    __tablename__ = "tp_grey_lot"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_grey_lot_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    sales_order_id: int = Field(foreign_key="tp_sales_order.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    quality_id: int = Field(foreign_key="tp_quality.id", index=True)
    godown_location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id")
    date: str = Field(index=True)
    received_mtr: Decimal = _qty()
    than_count: int = Field(default=0)
    # rolled after mending / stages
    ready_mtr: Decimal = _qty()
    rejection_mtr: Decimal = _qty()
    visible_wastage_mtr: Decimal = _qty()
    invisible_wastage_mtr: Decimal = _qty()
    dispatched_mtr: Decimal = _qty()
    status: str = Field(default="received", index=True)
    # received|mending|ready|in_process|packed|dispatched|closed|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpGreyThan(SQLModel, table=True):
    """Than line on a grey lot — Than#, Mtrs, Rej, Safi."""
    __tablename__ = "tp_grey_than"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    than_no: str
    meters: Decimal = _qty()
    rejection_mtr: Decimal = _qty()  # Rej at intake (optional; full mending still later)
    safi_mtr: Decimal = _qty()       # Safi = meters − rejection_mtr (stored for printouts)
    width: Optional[str] = None
    notes: Optional[str] = None


class TpKachiParchi(SQLModel, table=True):
    """Provisional customer slip issued on grey receipt."""
    __tablename__ = "tp_kachi_parchi"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_kachi_parchi_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    quality_id: int = Field(foreign_key="tp_quality.id", index=True)
    date: str = Field(index=True)
    meters: Decimal = _qty()
    than_count: int = Field(default=0)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpMending(SQLModel, table=True):
    __tablename__ = "tp_mending"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_mending_number"),
        UniqueConstraint("tenant_id", "lot_id", name="uq_tp_mending_lot"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    date: str = Field(index=True)
    grey_mtr: Decimal = _qty()
    l_kami_mtr: Decimal = _qty()
    rejection_mtr: Decimal = _qty()
    safai_mtr: Decimal = _qty()  # mending loss (NOT Safi grey)
    ready_mtr: Decimal = _qty()  # Safi grey = grey − L-Kami − Rejection − Safai
    status: str = Field(default="draft", index=True)  # draft|posted|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpPakkiParchi(SQLModel, table=True):
    """Final slip: Safi grey under unit responsibility after mending."""
    __tablename__ = "tp_pakki_parchi"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_pakki_parchi_number"),
        UniqueConstraint("tenant_id", "lot_id", name="uq_tp_pakki_parchi_lot"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    mending_id: int = Field(foreign_key="tp_mending.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    quality_id: int = Field(foreign_key="tp_quality.id", index=True)
    date: str = Field(index=True)
    meters: Decimal = _qty()  # = mending.ready_mtr (Safi)
    than_count: int = Field(default=0)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpRejectionIssueNote(SQLModel, table=True):
    """Advises customer of rejected grey available to lift from godown."""
    __tablename__ = "tp_rejection_issue_note"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_rej_note_number"),
        UniqueConstraint("tenant_id", "lot_id", name="uq_tp_rej_note_lot"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    mending_id: int = Field(foreign_key="tp_mending.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    quality_id: int = Field(foreign_key="tp_quality.id", index=True)
    date: str = Field(index=True)
    issued_mtr: Decimal = _qty()
    lifted_mtr: Decimal = _qty()
    status: str = Field(default="issued", index=True)
    # issued|partially_lifted|lifted|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpRejectionOgp(SQLModel, table=True):
    """Outward Gate Pass when customer lifts rejection from godown."""
    __tablename__ = "tp_rejection_ogp"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_rej_ogp_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    rejection_issue_note_id: int = Field(foreign_key="tp_rejection_issue_note.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    date: str = Field(index=True)
    qty_mtr: Decimal = _qty()
    vehicle: Optional[str] = None
    challan: Optional[str] = None
    status: str = Field(default="posted", index=True)  # posted|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


# ── Production PPC ───────────────────────────────────────────────────────────


class TpProductionOrder(SQLModel, table=True):
    __tablename__ = "tp_production_order"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_prod_order_number"),
        UniqueConstraint("tenant_id", "lot_id", name="uq_tp_prod_order_lot"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    sales_order_id: int = Field(foreign_key="tp_sales_order.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    quality_id: int = Field(foreign_key="tp_quality.id", index=True)
    date: str = Field(index=True)
    issued_mtr: Decimal = _qty()  # Safi issued into PPC
    status: str = Field(default="draft", index=True)
    # draft|released|in_process|completed|dispatched|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpStageEntry(SQLModel, table=True):
    __tablename__ = "tp_stage_entry"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_stage_entry_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    production_order_id: int = Field(foreign_key="tp_production_order.id", index=True)
    process_id: int = Field(foreign_key="tp_process.id", index=True)
    # denormalized for reporting without N+1
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    quality_id: int = Field(foreign_key="tp_quality.id", index=True)
    date: str = Field(index=True)
    input_mtr: Decimal = _qty()
    output_mtr: Decimal = _qty()
    visible_wastage_mtr: Decimal = _qty()
    invisible_wastage_mtr: Decimal = _qty()
    rejection_mtr: Decimal = _qty()  # optional distinct from visible
    contractor_id: Optional[int] = Field(default=None, foreign_key="tp_contractor.id")
    labor_qty: Decimal = _qty()
    labor_rate: Decimal = _money()
    labor_amount: Decimal = _money()
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    status: str = Field(default="draft", index=True)  # draft|completed|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpPacking(SQLModel, table=True):
    __tablename__ = "tp_packing"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_packing_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    production_order_id: int = Field(foreign_key="tp_production_order.id", index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    date: str = Field(index=True)
    meters: Decimal = _qty()
    pieces: int = Field(default=0)
    item_type: Optional[str] = Field(default=None, index=True)  # KMZ|SHL|DPT|2PC|3PC|OTHER
    quality_id: Optional[int] = Field(default=None, foreign_key="tp_quality.id")
    process_id: Optional[int] = Field(default=None, foreign_key="tp_process.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpBaling(SQLModel, table=True):
    __tablename__ = "tp_baling"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_baling_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    production_order_id: int = Field(foreign_key="tp_production_order.id", index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    date: str = Field(index=True)
    meters: Decimal = _qty()
    bale_count: int = Field(default=0)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpDispatch(SQLModel, table=True):
    """Fresh Dispatch of finished goods — drives process-charge Invoice."""
    __tablename__ = "tp_dispatch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_dispatch_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    production_order_id: int = Field(foreign_key="tp_production_order.id", index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    sales_order_id: int = Field(foreign_key="tp_sales_order.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    date: str = Field(index=True)
    meters: Decimal = _qty()
    vehicle: Optional[str] = None
    challan: Optional[str] = None
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    status: str = Field(default="draft", index=True)  # draft|posted|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpGreySettlement(SQLModel, table=True):
    """Lot/SO close — credit remaining grey to customer at grey_rate."""
    __tablename__ = "tp_grey_settlement"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_grey_settlement_number"),
        UniqueConstraint("tenant_id", "lot_id", name="uq_tp_grey_settlement_lot"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    lot_id: int = Field(foreign_key="tp_grey_lot.id", index=True)
    sales_order_id: int = Field(foreign_key="tp_sales_order.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    date: str = Field(index=True)
    total_grey_received: Decimal = _qty()
    fresh_dispatch_mtr: Decimal = _qty()
    visible_wastage_mtr: Decimal = _qty()
    invisible_wastage_mtr: Decimal = _qty()
    credit_qty_mtr: Decimal = _qty()
    grey_rate: Decimal = _money()
    credit_value: Decimal = _money()
    credit_note_id: Optional[int] = Field(default=None, foreign_key="creditnote.id")
    wastage_invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    status: str = Field(default="draft", index=True)  # draft|posted|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpLaborBill(SQLModel, table=True):
    """Contractor labor bill → Vendor Bill."""
    __tablename__ = "tp_labor_bill"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_labor_bill_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    contractor_id: int = Field(foreign_key="tp_contractor.id", index=True)
    vendor_id: int = Field(foreign_key="vendor.id", index=True)
    date: str = Field(index=True)
    # JSON list of stage_entry ids included
    stage_entry_ids: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    labor_amount: Decimal = _money()
    bill_id: Optional[int] = Field(default=None, foreign_key="bill.id")
    status: str = Field(default="draft", index=True)  # draft|posted|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class TpInspection(SQLModel, table=True):
    """RM inspection between Gate Inward and GRN."""
    __tablename__ = "tp_inspection"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_tp_inspection_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    gate_inward_id: int = Field(foreign_key="gateinward.id", index=True)
    production_order_id: Optional[int] = Field(default=None, foreign_key="tp_production_order.id")
    date: str = Field(index=True)
    accepted_qty: Decimal = _qty()
    rejected_qty: Decimal = _qty()
    hold_qty: Decimal = _qty()
    status: str = Field(default="draft", index=True)  # draft|accepted|rejected|partial|cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
