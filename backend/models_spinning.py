"""
SQLModel tables for the Yarn Spinning module.

Full GL integration via services.spinning_posting — weights stored in Kg;
Lbs/Bags derived via services.spinning_calc.
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


# ── Masters ──────────────────────────────────────────────────────────────────


class SpYarnSpec(SQLModel, table=True):
    __tablename__ = "sp_yarn_spec"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_sp_yarn_spec_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    count_ne: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    count_nm: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    twist_direction: Optional[str] = None
    blend_cotton_pct: Decimal = _qty()
    blend_poly_pct: Decimal = _qty()
    output_product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpFiberGrade(SQLModel, table=True):
    __tablename__ = "sp_fiber_grade"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_sp_fiber_grade_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    staple_mm: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    micronaire: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    grade: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpMachine(SQLModel, table=True):
    __tablename__ = "sp_machine"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_sp_machine_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    machine_type: Optional[str] = None
    spindle_count: Optional[int] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpShift(SQLModel, table=True):
    __tablename__ = "sp_shift"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_sp_shift_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpOperator(SQLModel, table=True):
    __tablename__ = "sp_operator"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_sp_operator_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    phone: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpWasteType(SQLModel, table=True):
    __tablename__ = "sp_waste_type"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_sp_waste_type_code"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)
    name: str
    gl_account_code: str = Field(default="5901")
    default_stage: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpRecipe(SQLModel, table=True):
    __tablename__ = "sp_recipe"
    __table_args__ = (
        UniqueConstraint("tenant_id", "yarn_spec_id", "version", name="uq_sp_recipe_version"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    yarn_spec_id: int = Field(foreign_key="sp_yarn_spec.id", index=True)
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpRecipeLine(SQLModel, table=True):
    __tablename__ = "sp_recipe_line"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    recipe_id: int = Field(foreign_key="sp_recipe.id", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    qty_per_100kg_output: Decimal = _qty()
    stage: Optional[str] = None


class SpProductionPlan(SQLModel, table=True):
    __tablename__ = "sp_production_plan"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sp_production_plan_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    plan_date: str = Field(index=True)
    yarn_spec_id: int = Field(foreign_key="sp_yarn_spec.id", index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    target_kg: Decimal = _qty()
    status: str = Field(default="draft", index=True)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class SpSpinLot(SQLModel, table=True):
    __tablename__ = "sp_spin_lot"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sp_spin_lot_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    yarn_spec_id: int = Field(foreign_key="sp_yarn_spec.id", index=True)
    recipe_id: Optional[int] = Field(default=None, foreign_key="sp_recipe.id")
    plan_id: Optional[int] = Field(default=None, foreign_key="sp_production_plan.id")
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    start_date: str = Field(index=True)
    target_output_kg: Decimal = _qty()
    status: str = Field(default="draft", index=True)
    material_cost: Decimal = _money()
    labour_cost: Decimal = _money()
    overhead_cost: Decimal = _money()
    waste_cost: Decimal = _money()
    total_cost: Decimal = _money()
    cost_per_kg: Decimal = _money()
    output_kg: Decimal = _qty()
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class SpBaleReceipt(SQLModel, table=True):
    __tablename__ = "sp_bale_receipt"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sp_bale_receipt_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")
    bill_id: Optional[int] = Field(default=None, foreign_key="bill.id")
    gate_inward_id: Optional[int] = Field(default=None, foreign_key="gateinward.id")
    product_id: int = Field(foreign_key="product.id", index=True)
    spin_lot_id: Optional[int] = Field(default=None, foreign_key="sp_spin_lot.id", index=True)
    fiber_grade_id: Optional[int] = Field(default=None, foreign_key="sp_fiber_grade.id")
    lot_no: Optional[str] = None
    date: str = Field(index=True)
    gross_kg: Decimal = _qty()
    tare_kg: Decimal = _qty()
    net_kg: Decimal = _qty()
    moisture_pct: Decimal = _qty()
    rate_per_kg: Decimal = _money()
    total_value: Decimal = _money()
    status: str = Field(default="draft", index=True)
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class SpStageEntry(SQLModel, table=True):
    __tablename__ = "sp_stage_entry"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sp_stage_entry_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    spin_lot_id: int = Field(foreign_key="sp_spin_lot.id", index=True)
    stage: str = Field(index=True)
    machine_id: Optional[int] = Field(default=None, foreign_key="sp_machine.id")
    shift_id: Optional[int] = Field(default=None, foreign_key="sp_shift.id")
    operator_id: Optional[int] = Field(default=None, foreign_key="sp_operator.id")
    date: str = Field(index=True)
    input_kg: Decimal = _qty()
    output_kg: Decimal = _qty()
    waste_kg: Decimal = _qty()
    yield_pct: Decimal = _qty()
    labour_cost: Decimal = _money()
    overhead_cost: Decimal = _money()
    status: str = Field(default="draft", index=True)
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class SpConeOutput(SQLModel, table=True):
    __tablename__ = "sp_cone_output"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sp_cone_output_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    spin_lot_id: int = Field(foreign_key="sp_spin_lot.id", index=True)
    date: str = Field(index=True)
    cones_count: int = Field(default=0)
    net_kg: Decimal = _qty()
    quality_grade: Optional[str] = None
    lot_no: Optional[str] = None
    machine_id: Optional[int] = Field(default=None, foreign_key="sp_machine.id")
    shift_id: Optional[int] = Field(default=None, foreign_key="sp_shift.id")
    operator_id: Optional[int] = Field(default=None, foreign_key="sp_operator.id")
    unit_cost: Decimal = _money()
    total_cost: Decimal = _money()
    status: str = Field(default="draft", index=True)
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class SpWasteLog(SQLModel, table=True):
    __tablename__ = "sp_waste_log"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sp_waste_log_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    spin_lot_id: int = Field(foreign_key="sp_spin_lot.id", index=True)
    stage: str = Field(index=True)
    waste_type_id: int = Field(foreign_key="sp_waste_type.id", index=True)
    date: str = Field(index=True)
    qty_kg: Decimal = _qty()
    cost_value: Decimal = _money()
    status: str = Field(default="draft", index=True)
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class SpYarnDispatch(SQLModel, table=True):
    __tablename__ = "sp_yarn_dispatch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sp_yarn_dispatch_number"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    yarn_spec_id: int = Field(foreign_key="sp_yarn_spec.id", index=True)
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    date: str = Field(index=True)
    cones_count: int = Field(default=0)
    net_kg: Decimal = _qty()
    rate_per_kg: Decimal = _money()
    dispatch_value: Decimal = _money()
    status: str = Field(default="draft", index=True)
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class SpCalcRun(SQLModel, table=True):
    __tablename__ = "sp_calc_run"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    spin_lot_id: Optional[int] = Field(default=None, foreign_key="sp_spin_lot.id", index=True)
    calc_type: str = Field(index=True)
    inputs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    outputs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    override_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


STAGE_WIP_ACCOUNTS: dict[str, str] = {
    "opening": "1201",
    "carding": "1201",
    "drawing": "1202",
    "roving": "1202",
    "spinning": "1203",
    "winding": "1203",
}

STAGE_ORDER: tuple[str, ...] = ("opening", "carding", "drawing", "roving", "spinning", "winding")
