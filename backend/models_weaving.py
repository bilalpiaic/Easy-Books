"""
SQLModel tables for the Weaving unit-control module (#140).

Operational / memo documents only in v1 — no GL posting.
Yarn weights are stored in Kg; Lbs and 100-lb Bags are derived via
services.weaving_calc.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from services.money import ZERO


def _money(default: Decimal = ZERO, **kw):
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


def _qty(default: Decimal = ZERO, **kw):
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


# ── Masters ──────────────────────────────────────────────────────────────────


class WvFabricQuality(SQLModel, table=True):
    __tablename__ = "wv_fabric_quality"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_wv_fabric_quality_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WvLoom(SQLModel, table=True):
    __tablename__ = "wv_loom"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_wv_loom_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    loom_type: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WvYarnType(SQLModel, table=True):
    __tablename__ = "wv_yarn_type"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_wv_yarn_type_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WvShift(SQLModel, table=True):
    __tablename__ = "wv_shift"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_wv_shift_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    start_time: Optional[str] = None  # HH:MM
    end_time: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WvOperator(SQLModel, table=True):
    __tablename__ = "wv_operator"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_wv_operator_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    phone: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Contract (+ rate / costing assumptions) ──────────────────────────────────


class WvContract(SQLModel, table=True):
    __tablename__ = "wv_contract"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_wv_contract_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)  # WC-YYYY-seq
    customer_id: int = Field(foreign_key="customer.id", index=True)
    fabric_quality_id: Optional[int] = Field(default=None, foreign_key="wv_fabric_quality.id")
    yarn_type_id: Optional[int] = Field(default=None, foreign_key="wv_yarn_type.id")
    start_date: str  # YYYY-MM-DD
    end_date: Optional[str] = None
    contract_meters: Decimal = _qty()
    pick_per_inch: Decimal = _qty()
    assumed_yarn_rate_per_kg: Decimal = _money()
    fabric_return_price_per_meter: Decimal = _money()
    weaving_rate: Decimal = _money()  # per meter
    expected_shrinkage_pct: Decimal = _qty()
    payment_terms: Optional[str] = None
    # draft | in_process | completed | delayed | cancelled
    status: str = Field(default="draft", index=True)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


# ── Operational documents ────────────────────────────────────────────────────


class WvYarnInward(SQLModel, table=True):
    __tablename__ = "wv_yarn_inward"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_wv_yarn_inward_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    contract_id: int = Field(foreign_key="wv_contract.id", index=True)
    yarn_type_id: Optional[int] = Field(default=None, foreign_key="wv_yarn_type.id")
    date: str = Field(index=True)
    gross_kg: Decimal = _qty()
    tare_kg: Decimal = _qty()
    net_kg: Decimal = _qty()
    rate_per_kg: Decimal = _money()
    yarn_value: Decimal = _money()
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class WvSizing(SQLModel, table=True):
    __tablename__ = "wv_sizing"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_wv_sizing_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    contract_id: int = Field(foreign_key="wv_contract.id", index=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")
    date: str = Field(index=True)
    input_kg: Decimal = _qty()
    output_kg: Decimal = _qty()
    gain_shrink_pct: Decimal = _qty()
    sizing_cost: Decimal = _money()
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class WvProduction(SQLModel, table=True):
    __tablename__ = "wv_production"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_wv_production_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    contract_id: int = Field(foreign_key="wv_contract.id", index=True)
    loom_id: Optional[int] = Field(default=None, foreign_key="wv_loom.id")
    shift_id: Optional[int] = Field(default=None, foreign_key="wv_shift.id")
    operator_id: Optional[int] = Field(default=None, foreign_key="wv_operator.id")
    date: str = Field(index=True)
    warp_yarn_kg: Decimal = _qty()
    weft_yarn_kg: Decimal = _qty()
    total_yarn_kg: Decimal = _qty()
    grey_meters: Decimal = _qty()
    efficiency_pct: Decimal = _qty()
    weaving_charges: Decimal = _money()
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class WvDispatch(SQLModel, table=True):
    __tablename__ = "wv_dispatch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_wv_dispatch_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    contract_id: int = Field(foreign_key="wv_contract.id", index=True)
    date: str = Field(index=True)
    meters: Decimal = _qty()
    dispatch_value: Decimal = _money()
    weaving_charges_billed: Decimal = _money()
    net_receivable: Decimal = _money()
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
