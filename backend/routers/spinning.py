"""Yarn Spinning module — masters, lots, bale receipts, stages, cones, waste, dispatch."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from models import Customer, Product, Tenant
from models_spinning import (
    STAGE_ORDER,
    SpBaleReceipt,
    SpConeOutput,
    SpFiberGrade,
    SpMachine,
    SpOperator,
    SpProductionPlan,
    SpRecipe,
    SpRecipeLine,
    SpShift,
    SpSpinLot,
    SpStageEntry,
    SpWasteLog,
    SpWasteType,
    SpYarnDispatch,
    SpYarnSpec,
)
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit, next_number
from routers.modules import _get_enabled
from services import spinning_calc as calc
from services.money import D, ZERO, money
from services.permissions import perm_dep
from services import spinning_posting as posting

router = APIRouter(prefix="/api/spinning", tags=["spinning"])


def _require_spinning(session: Session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "spinning" not in _get_enabled(tenant):
        raise HTTPException(403, "The Yarn Spinning module is not installed. Install it from System → Apps.")


def _wt(kg) -> dict[str, float]:
    return calc.weight_triple(kg)


def _master_list(session, model, tenant_id, active_only: bool = False):
    q = select(model).where(model.tenant_id == tenant_id)
    if active_only and hasattr(model, "is_active"):
        q = q.where(model.is_active == True)  # noqa: E712
    return session.exec(q.order_by(model.code)).all()


class MasterCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    machine_type: Optional[str] = None
    spindle_count: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    phone: Optional[str] = None
    count_ne: Optional[Decimal] = None
    count_nm: Optional[Decimal] = None
    twist_direction: Optional[str] = None
    blend_cotton_pct: Optional[Decimal] = None
    blend_poly_pct: Optional[Decimal] = None
    output_product_id: Optional[int] = None
    staple_mm: Optional[Decimal] = None
    micronaire: Optional[Decimal] = None
    grade: Optional[str] = None
    gl_account_code: Optional[str] = None
    default_stage: Optional[str] = None
    is_active: bool = True


class MasterUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    machine_type: Optional[str] = None
    spindle_count: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    phone: Optional[str] = None
    count_ne: Optional[Decimal] = None
    count_nm: Optional[Decimal] = None
    twist_direction: Optional[str] = None
    blend_cotton_pct: Optional[Decimal] = None
    blend_poly_pct: Optional[Decimal] = None
    output_product_id: Optional[int] = None
    staple_mm: Optional[Decimal] = None
    micronaire: Optional[Decimal] = None
    grade: Optional[str] = None
    gl_account_code: Optional[str] = None
    default_stage: Optional[str] = None
    is_active: Optional[bool] = None


def _ser_master(row) -> dict[str, Any]:
    d: dict[str, Any] = {"id": row.id, "code": row.code, "name": row.name, "is_active": row.is_active}
    for attr in (
        "description", "machine_type", "spindle_count", "start_time", "end_time", "phone",
        "twist_direction", "grade", "gl_account_code", "default_stage", "output_product_id",
    ):
        if hasattr(row, attr):
            d[attr] = getattr(row, attr)
    for attr in ("count_ne", "count_nm", "blend_cotton_pct", "blend_poly_pct", "staple_mm", "micronaire"):
        if hasattr(row, attr):
            v = getattr(row, attr)
            d[attr] = float(v) if v is not None else None
    return d


def _crud_master(model, create_fn, path: str):
    @router.get(f"/{path}", dependencies=[perm_dep("spinning.setup", "view")])
    def list_(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
        _require_spinning(session, user)
        return [_ser_master(r) for r in _master_list(session, model, user.tenant_id, active_only)]

    @router.post(f"/{path}", status_code=201, dependencies=[perm_dep("spinning.setup", "edit")])
    def create(user: WriteUserDep, session: SessionDep, body: MasterCreate):
        _require_spinning(session, user)
        row = create_fn(user.tenant_id, body)
        session.add(row)
        session.commit()
        session.refresh(row)
        return _ser_master(row)

    @router.put(f"/{path}/{{id}}", dependencies=[perm_dep("spinning.setup", "edit")])
    def update(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
        _require_spinning(session, user)
        row = session.exec(select(model).where(model.id == id, model.tenant_id == user.tenant_id)).first()
        if not row:
            raise HTTPException(404, "Not found")
        for k, v in body.model_dump(exclude_unset=True).items():
            if hasattr(row, k) and v is not None:
                setattr(row, k, v.strip() if isinstance(v, str) else v)
        session.add(row)
        session.commit()
        session.refresh(row)
        return _ser_master(row)


# Register masters
@router.get("/yarn-specs", dependencies=[perm_dep("spinning.setup", "view")])
def list_yarn_specs(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_spinning(session, user)
    return [_ser_master(r) for r in _master_list(session, SpYarnSpec, user.tenant_id, active_only)]


@router.post("/yarn-specs", status_code=201, dependencies=[perm_dep("spinning.setup", "edit")])
def create_yarn_spec(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_spinning(session, user)
    row = SpYarnSpec(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        count_ne=body.count_ne, count_nm=body.count_nm, twist_direction=body.twist_direction,
        blend_cotton_pct=body.blend_cotton_pct or ZERO, blend_poly_pct=body.blend_poly_pct or ZERO,
        output_product_id=body.output_product_id, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.put("/yarn-specs/{id}", dependencies=[perm_dep("spinning.setup", "edit")])
def update_yarn_spec(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_spinning(session, user)
    row = session.exec(select(SpYarnSpec).where(SpYarnSpec.id == id, SpYarnSpec.tenant_id == user.tenant_id)).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.get("/fiber-grades", dependencies=[perm_dep("spinning.setup", "view")])
def list_fiber_grades(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_spinning(session, user)
    return [_ser_master(r) for r in _master_list(session, SpFiberGrade, user.tenant_id, active_only)]


@router.post("/fiber-grades", status_code=201, dependencies=[perm_dep("spinning.setup", "edit")])
def create_fiber_grade(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_spinning(session, user)
    row = SpFiberGrade(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        staple_mm=body.staple_mm, micronaire=body.micronaire, grade=body.grade, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.put("/fiber-grades/{id}", dependencies=[perm_dep("spinning.setup", "edit")])
def update_fiber_grade(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_spinning(session, user)
    row = session.exec(select(SpFiberGrade).where(SpFiberGrade.id == id, SpFiberGrade.tenant_id == user.tenant_id)).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.get("/machines", dependencies=[perm_dep("spinning.setup", "view")])
def list_machines(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_spinning(session, user)
    return [_ser_master(r) for r in _master_list(session, SpMachine, user.tenant_id, active_only)]


@router.post("/machines", status_code=201, dependencies=[perm_dep("spinning.setup", "edit")])
def create_machine(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_spinning(session, user)
    row = SpMachine(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        machine_type=body.machine_type, spindle_count=body.spindle_count, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.put("/machines/{id}", dependencies=[perm_dep("spinning.setup", "edit")])
def update_machine(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_spinning(session, user)
    row = session.exec(select(SpMachine).where(SpMachine.id == id, SpMachine.tenant_id == user.tenant_id)).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.get("/shifts", dependencies=[perm_dep("spinning.setup", "view")])
def list_shifts(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_spinning(session, user)
    return [_ser_master(r) for r in _master_list(session, SpShift, user.tenant_id, active_only)]


@router.post("/shifts", status_code=201, dependencies=[perm_dep("spinning.setup", "edit")])
def create_shift(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_spinning(session, user)
    row = SpShift(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        start_time=body.start_time, end_time=body.end_time, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.put("/shifts/{id}", dependencies=[perm_dep("spinning.setup", "edit")])
def update_shift(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_spinning(session, user)
    row = session.exec(select(SpShift).where(SpShift.id == id, SpShift.tenant_id == user.tenant_id)).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.get("/operators", dependencies=[perm_dep("spinning.setup", "view")])
def list_operators(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_spinning(session, user)
    return [_ser_master(r) for r in _master_list(session, SpOperator, user.tenant_id, active_only)]


@router.post("/operators", status_code=201, dependencies=[perm_dep("spinning.setup", "edit")])
def create_operator(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_spinning(session, user)
    row = SpOperator(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        phone=body.phone, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.put("/operators/{id}", dependencies=[perm_dep("spinning.setup", "edit")])
def update_operator(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_spinning(session, user)
    row = session.exec(select(SpOperator).where(SpOperator.id == id, SpOperator.tenant_id == user.tenant_id)).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.get("/waste-types", dependencies=[perm_dep("spinning.setup", "view")])
def list_waste_types(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_spinning(session, user)
    return [_ser_master(r) for r in _master_list(session, SpWasteType, user.tenant_id, active_only)]


@router.post("/waste-types", status_code=201, dependencies=[perm_dep("spinning.setup", "edit")])
def create_waste_type(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_spinning(session, user)
    row = SpWasteType(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        gl_account_code=body.gl_account_code or "5901", default_stage=body.default_stage,
        is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.put("/waste-types/{id}", dependencies=[perm_dep("spinning.setup", "edit")])
def update_waste_type(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_spinning(session, user)
    row = session.exec(select(SpWasteType).where(SpWasteType.id == id, SpWasteType.tenant_id == user.tenant_id)).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


# ── Recipes ──────────────────────────────────────────────────────────────────

class RecipeLineIn(BaseModel):
    product_id: int
    qty_per_100kg_output: Decimal
    stage: Optional[str] = None


class RecipeCreate(BaseModel):
    yarn_spec_id: int
    version: int = 1
    notes: Optional[str] = None
    lines: list[RecipeLineIn] = []


def _ser_recipe(session: Session, r: SpRecipe) -> dict:
    lines = session.exec(select(SpRecipeLine).where(SpRecipeLine.recipe_id == r.id)).all()
    return {
        "id": r.id, "yarn_spec_id": r.yarn_spec_id, "version": r.version,
        "is_active": r.is_active, "notes": r.notes,
        "lines": [{"id": ln.id, "product_id": ln.product_id,
                   "qty_per_100kg_output": float(ln.qty_per_100kg_output), "stage": ln.stage}
                  for ln in lines],
    }


@router.get("/recipes", dependencies=[perm_dep("spinning.setup", "view")])
def list_recipes(user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    rows = session.exec(select(SpRecipe).where(SpRecipe.tenant_id == user.tenant_id)).all()
    return [_ser_recipe(session, r) for r in rows]


@router.post("/recipes", status_code=201, dependencies=[perm_dep("spinning.setup", "edit")])
def create_recipe(user: WriteUserDep, session: SessionDep, body: RecipeCreate):
    _require_spinning(session, user)
    r = SpRecipe(tenant_id=user.tenant_id, yarn_spec_id=body.yarn_spec_id, version=body.version, notes=body.notes)
    session.add(r)
    session.flush()
    for ln in body.lines:
        session.add(SpRecipeLine(
            tenant_id=user.tenant_id, recipe_id=r.id, product_id=ln.product_id,
            qty_per_100kg_output=ln.qty_per_100kg_output, stage=ln.stage,
        ))
    session.commit()
    session.refresh(r)
    return _ser_recipe(session, r)


# ── Spin lots ────────────────────────────────────────────────────────────────

class SpinLotCreate(BaseModel):
    yarn_spec_id: int
    recipe_id: Optional[int] = None
    plan_id: Optional[int] = None
    customer_id: Optional[int] = None
    start_date: str
    target_output_kg: Decimal
    notes: Optional[str] = None


def _ser_lot(lot: SpSpinLot) -> dict:
    return {
        "id": lot.id, "number": lot.number, "yarn_spec_id": lot.yarn_spec_id,
        "recipe_id": lot.recipe_id, "plan_id": lot.plan_id, "customer_id": lot.customer_id,
        "start_date": lot.start_date, "target_output_kg": float(lot.target_output_kg),
        "status": lot.status, "material_cost": float(lot.material_cost),
        "labour_cost": float(lot.labour_cost), "overhead_cost": float(lot.overhead_cost),
        "waste_cost": float(lot.waste_cost), "total_cost": float(lot.total_cost),
        "cost_per_kg": float(lot.cost_per_kg), "output_kg": float(lot.output_kg),
        "target_weight": _wt(lot.target_output_kg), "output_weight": _wt(lot.output_kg),
        "notes": lot.notes,
        "started_at": lot.started_at.isoformat() if lot.started_at else None,
        "completed_at": lot.completed_at.isoformat() if lot.completed_at else None,
    }


@router.get("/lots", dependencies=[perm_dep("spinning.lots", "view")])
def list_lots(user: CurrentUserDep, session: SessionDep, status: Optional[str] = None):
    _require_spinning(session, user)
    q = select(SpSpinLot).where(SpSpinLot.tenant_id == user.tenant_id)
    if status:
        q = q.where(SpSpinLot.status == status)
    rows = session.exec(q.order_by(SpSpinLot.start_date.desc())).all()
    return [_ser_lot(r) for r in rows]


@router.get("/lots/{lot_id}", dependencies=[perm_dep("spinning.lots", "view")])
def get_lot(lot_id: int, user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    lot = session.exec(
        select(SpSpinLot).where(SpSpinLot.id == lot_id, SpSpinLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(404, "Spin lot not found")
    out = _ser_lot(lot)
    stages = session.exec(
        select(SpStageEntry).where(SpStageEntry.spin_lot_id == lot_id).order_by(SpStageEntry.date)
    ).all()
    out["stages"] = [_ser_stage(s) for s in stages]
    bales = session.exec(select(SpBaleReceipt).where(SpBaleReceipt.spin_lot_id == lot_id)).all()
    out["bale_receipts"] = [_ser_bale(b) for b in bales]
    cones = session.exec(select(SpConeOutput).where(SpConeOutput.spin_lot_id == lot_id)).all()
    out["cone_outputs"] = [_ser_cone(c) for c in cones]
    return out


@router.post("/lots", status_code=201, dependencies=[perm_dep("spinning.lots", "edit")])
def create_lot(user: WriteUserDep, session: SessionDep, body: SpinLotCreate):
    _require_spinning(session, user)
    posting.ensure_spinning_locations(session, user.tenant_id)
    num = next_number(session, user.tenant_id, "sp_spin_lot", "SL", fmt="{prefix}-{YYYY}-{seq:04d}")
    lot = SpSpinLot(
        tenant_id=user.tenant_id, number=num, yarn_spec_id=body.yarn_spec_id,
        recipe_id=body.recipe_id, plan_id=body.plan_id, customer_id=body.customer_id,
        start_date=body.start_date, target_output_kg=body.target_output_kg,
        notes=body.notes, created_by_id=user.id,
    )
    session.add(lot)
    session.commit()
    session.refresh(lot)
    log_audit(session, user, "create", "sp_spin_lot", lot.id, num)
    return _ser_lot(lot)


@router.patch("/lots/{lot_id}/start", dependencies=[perm_dep("spinning.lots", "edit")])
def start_lot(lot_id: int, user: WriteUserDep, session: SessionDep):
    _require_spinning(session, user)
    lot = session.exec(
        select(SpSpinLot).where(SpSpinLot.id == lot_id, SpSpinLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(404, "Not found")
    posting.start_spin_lot(session, lot)
    session.commit()
    session.refresh(lot)
    return _ser_lot(lot)


@router.patch("/lots/{lot_id}/complete", dependencies=[perm_dep("spinning.lots", "edit")])
def complete_lot(lot_id: int, user: WriteUserDep, session: SessionDep):
    _require_spinning(session, user)
    lot = session.exec(
        select(SpSpinLot).where(SpSpinLot.id == lot_id, SpSpinLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(404, "Not found")
    posting.complete_spin_lot(session, lot)
    session.commit()
    session.refresh(lot)
    return _ser_lot(lot)


@router.patch("/lots/{lot_id}/close", dependencies=[perm_dep("spinning.lots", "edit")])
def close_lot(lot_id: int, user: WriteUserDep, session: SessionDep):
    _require_spinning(session, user)
    lot = session.exec(
        select(SpSpinLot).where(SpSpinLot.id == lot_id, SpSpinLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(404, "Not found")
    posting.close_spin_lot(session, lot)
    session.commit()
    session.refresh(lot)
    return _ser_lot(lot)


# ── Bale receipts ────────────────────────────────────────────────────────────

class BaleReceiptCreate(BaseModel):
    product_id: int
    date: str
    gross_kg: Decimal
    tare_kg: Decimal = ZERO
    moisture_pct: Decimal = ZERO
    rate_per_kg: Decimal
    vendor_id: Optional[int] = None
    bill_id: Optional[int] = None
    gate_inward_id: Optional[int] = None
    spin_lot_id: Optional[int] = None
    fiber_grade_id: Optional[int] = None
    lot_no: Optional[str] = None
    notes: Optional[str] = None


def _ser_bale(r: SpBaleReceipt) -> dict:
    net = calc.net_kg(r.gross_kg, r.tare_kg)
    w = _wt(net)
    return {
        "id": r.id, "number": r.number, "product_id": r.product_id, "date": r.date,
        "gross_kg": float(r.gross_kg), "tare_kg": float(r.tare_kg), "net_kg": float(r.net_kg),
        "net_lbs": w["lbs"], "net_bags": w["bags"], "moisture_pct": float(r.moisture_pct),
        "rate_per_kg": float(r.rate_per_kg), "total_value": float(r.total_value),
        "status": r.status, "spin_lot_id": r.spin_lot_id, "vendor_id": r.vendor_id,
        "bill_id": r.bill_id, "gate_inward_id": r.gate_inward_id,
        "fiber_grade_id": r.fiber_grade_id, "lot_no": r.lot_no, "notes": r.notes,
    }


@router.get("/bale-receipts", dependencies=[perm_dep("spinning.bale_receipt", "view")])
def list_bale_receipts(user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    rows = session.exec(
        select(SpBaleReceipt).where(SpBaleReceipt.tenant_id == user.tenant_id).order_by(SpBaleReceipt.date.desc())
    ).all()
    return [_ser_bale(r) for r in rows]


@router.post("/bale-receipts", status_code=201, dependencies=[perm_dep("spinning.bale_receipt", "edit")])
def create_bale_receipt(user: WriteUserDep, session: SessionDep, body: BaleReceiptCreate):
    _require_spinning(session, user)
    net = calc.net_kg(body.gross_kg, body.tare_kg)
    num = next_number(session, user.tenant_id, "sp_bale_receipt", "BR", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = SpBaleReceipt(
        tenant_id=user.tenant_id, number=num, product_id=body.product_id, date=body.date,
        gross_kg=body.gross_kg, tare_kg=body.tare_kg, net_kg=net,
        moisture_pct=body.moisture_pct, rate_per_kg=body.rate_per_kg,
        total_value=money(net * body.rate_per_kg), vendor_id=body.vendor_id,
        bill_id=body.bill_id, gate_inward_id=body.gate_inward_id,
        spin_lot_id=body.spin_lot_id, fiber_grade_id=body.fiber_grade_id,
        lot_no=body.lot_no, notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_bale(row)


@router.patch("/bale-receipts/{id}/approve", dependencies=[perm_dep("spinning.bale_receipt", "edit")])
def approve_bale_receipt(id: int, user: WriteUserDep, session: SessionDep):
    _require_spinning(session, user)
    row = session.exec(
        select(SpBaleReceipt).where(SpBaleReceipt.id == id, SpBaleReceipt.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Not found")
    posting.approve_bale_receipt(session, user, row)
    session.commit()
    session.refresh(row)
    return _ser_bale(row)


# ── Stage entries ────────────────────────────────────────────────────────────

class StageEntryCreate(BaseModel):
    spin_lot_id: int
    stage: str
    date: str
    input_kg: Decimal
    output_kg: Decimal
    waste_kg: Decimal = ZERO
    machine_id: Optional[int] = None
    shift_id: Optional[int] = None
    operator_id: Optional[int] = None
    labour_cost: Decimal = ZERO
    overhead_cost: Decimal = ZERO
    notes: Optional[str] = None


def _ser_stage(r: SpStageEntry) -> dict:
    return {
        "id": r.id, "number": r.number, "spin_lot_id": r.spin_lot_id, "stage": r.stage,
        "date": r.date, "input_kg": float(r.input_kg), "output_kg": float(r.output_kg),
        "input_weight": _wt(r.input_kg), "output_weight": _wt(r.output_kg),
        "waste_kg": float(r.waste_kg), "yield_pct": float(r.yield_pct),
        "labour_cost": float(r.labour_cost), "overhead_cost": float(r.overhead_cost),
        "status": r.status, "machine_id": r.machine_id, "shift_id": r.shift_id,
        "operator_id": r.operator_id, "notes": r.notes,
    }


@router.get("/stages", dependencies=[perm_dep("spinning.stages", "view")])
def list_stages(user: CurrentUserDep, session: SessionDep, spin_lot_id: Optional[int] = None):
    _require_spinning(session, user)
    q = select(SpStageEntry).where(SpStageEntry.tenant_id == user.tenant_id)
    if spin_lot_id:
        q = q.where(SpStageEntry.spin_lot_id == spin_lot_id)
    rows = session.exec(q.order_by(SpStageEntry.date.desc())).all()
    return [_ser_stage(r) for r in rows]


@router.post("/stages", status_code=201, dependencies=[perm_dep("spinning.stages", "edit")])
def create_stage(user: WriteUserDep, session: SessionDep, body: StageEntryCreate):
    _require_spinning(session, user)
    if body.stage not in STAGE_ORDER:
        raise HTTPException(400, f"stage must be one of {STAGE_ORDER}")
    num = next_number(session, user.tenant_id, "sp_stage_entry", "SE", fmt="{prefix}-{YYYY}-{seq:04d}")
    yld = calc.stage_yield_pct(body.input_kg, body.output_kg)
    row = SpStageEntry(
        tenant_id=user.tenant_id, number=num, spin_lot_id=body.spin_lot_id,
        stage=body.stage, date=body.date, input_kg=body.input_kg, output_kg=body.output_kg,
        waste_kg=body.waste_kg, yield_pct=yld, machine_id=body.machine_id,
        shift_id=body.shift_id, operator_id=body.operator_id,
        labour_cost=body.labour_cost, overhead_cost=body.overhead_cost,
        notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.flush()
    posting.post_stage_entry(session, user, row)
    session.commit()
    session.refresh(row)
    return _ser_stage(row)


# ── Cone output ──────────────────────────────────────────────────────────────

class ConeOutputCreate(BaseModel):
    spin_lot_id: int
    date: str
    cones_count: int
    net_kg: Decimal
    quality_grade: Optional[str] = None
    lot_no: Optional[str] = None
    machine_id: Optional[int] = None
    shift_id: Optional[int] = None
    operator_id: Optional[int] = None
    notes: Optional[str] = None


def _ser_cone(r: SpConeOutput) -> dict:
    w = _wt(r.net_kg)
    return {
        "id": r.id, "number": r.number, "spin_lot_id": r.spin_lot_id, "date": r.date,
        "cones_count": r.cones_count, "net_kg": float(r.net_kg), "net_lbs": w["lbs"],
        "quality_grade": r.quality_grade, "lot_no": r.lot_no, "status": r.status,
        "unit_cost": float(r.unit_cost), "total_cost": float(r.total_cost),
        "machine_id": r.machine_id, "shift_id": r.shift_id, "operator_id": r.operator_id,
        "notes": r.notes,
    }


@router.get("/cone-outputs", dependencies=[perm_dep("spinning.cone_output", "view")])
def list_cone_outputs(user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    rows = session.exec(
        select(SpConeOutput).where(SpConeOutput.tenant_id == user.tenant_id).order_by(SpConeOutput.date.desc())
    ).all()
    return [_ser_cone(r) for r in rows]


@router.post("/cone-outputs", status_code=201, dependencies=[perm_dep("spinning.cone_output", "edit")])
def create_cone_output(user: WriteUserDep, session: SessionDep, body: ConeOutputCreate):
    _require_spinning(session, user)
    num = next_number(session, user.tenant_id, "sp_cone_output", "CO", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = SpConeOutput(
        tenant_id=user.tenant_id, number=num, spin_lot_id=body.spin_lot_id,
        date=body.date, cones_count=body.cones_count, net_kg=body.net_kg,
        quality_grade=body.quality_grade, lot_no=body.lot_no,
        machine_id=body.machine_id, shift_id=body.shift_id, operator_id=body.operator_id,
        notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_cone(row)


@router.patch("/cone-outputs/{id}/approve", dependencies=[perm_dep("spinning.cone_output", "edit")])
def approve_cone_output(id: int, user: WriteUserDep, session: SessionDep):
    _require_spinning(session, user)
    row = session.exec(
        select(SpConeOutput).where(SpConeOutput.id == id, SpConeOutput.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Not found")
    posting.approve_cone_output(session, user, row)
    session.commit()
    session.refresh(row)
    return _ser_cone(row)


# ── Waste logs ─────────────────────────────────────────────────────────────────

class WasteLogCreate(BaseModel):
    spin_lot_id: int
    stage: str
    waste_type_id: int
    date: str
    qty_kg: Decimal
    cost_value: Decimal = ZERO
    notes: Optional[str] = None


def _ser_waste(r: SpWasteLog) -> dict:
    return {
        "id": r.id, "number": r.number, "spin_lot_id": r.spin_lot_id,
        "stage": r.stage, "waste_type_id": r.waste_type_id, "date": r.date,
        "qty_kg": float(r.qty_kg), "weight": _wt(r.qty_kg),
        "cost_value": float(r.cost_value), "status": r.status, "notes": r.notes,
    }


@router.get("/waste-logs", dependencies=[perm_dep("spinning.waste", "view")])
def list_waste_logs(user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    rows = session.exec(
        select(SpWasteLog).where(SpWasteLog.tenant_id == user.tenant_id).order_by(SpWasteLog.date.desc())
    ).all()
    return [_ser_waste(r) for r in rows]


@router.post("/waste-logs", status_code=201, dependencies=[perm_dep("spinning.waste", "edit")])
def create_waste_log(user: WriteUserDep, session: SessionDep, body: WasteLogCreate):
    _require_spinning(session, user)
    num = next_number(session, user.tenant_id, "sp_waste_log", "WL", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = SpWasteLog(
        tenant_id=user.tenant_id, number=num, spin_lot_id=body.spin_lot_id,
        stage=body.stage, waste_type_id=body.waste_type_id, date=body.date,
        qty_kg=body.qty_kg, cost_value=body.cost_value, notes=body.notes,
        created_by_id=user.id,
    )
    session.add(row)
    session.flush()
    posting.post_waste_log(session, user, row)
    session.commit()
    session.refresh(row)
    return _ser_waste(row)


# ── Yarn dispatch ────────────────────────────────────────────────────────────

class YarnDispatchCreate(BaseModel):
    customer_id: int
    yarn_spec_id: int
    product_id: Optional[int] = None
    date: str
    cones_count: int
    net_kg: Decimal
    rate_per_kg: Decimal
    invoice_id: Optional[int] = None
    notes: Optional[str] = None


def _ser_dispatch(r: SpYarnDispatch) -> dict:
    w = _wt(r.net_kg)
    return {
        "id": r.id, "number": r.number, "customer_id": r.customer_id,
        "yarn_spec_id": r.yarn_spec_id, "product_id": r.product_id,
        "date": r.date, "cones_count": r.cones_count, "net_kg": float(r.net_kg),
        "net_lbs": w["lbs"], "rate_per_kg": float(r.rate_per_kg),
        "dispatch_value": float(r.dispatch_value), "status": r.status,
        "invoice_id": r.invoice_id, "notes": r.notes,
    }


@router.get("/dispatches", dependencies=[perm_dep("spinning.dispatch", "view")])
def list_dispatches(user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    rows = session.exec(
        select(SpYarnDispatch).where(SpYarnDispatch.tenant_id == user.tenant_id).order_by(SpYarnDispatch.date.desc())
    ).all()
    return [_ser_dispatch(r) for r in rows]


@router.post("/dispatches", status_code=201, dependencies=[perm_dep("spinning.dispatch", "edit")])
def create_dispatch(user: WriteUserDep, session: SessionDep, body: YarnDispatchCreate):
    _require_spinning(session, user)
    num = next_number(session, user.tenant_id, "sp_yarn_dispatch", "YD", fmt="{prefix}-{YYYY}-{seq:04d}")
    val = calc.dispatch_value(body.net_kg, body.rate_per_kg)
    row = SpYarnDispatch(
        tenant_id=user.tenant_id, number=num, customer_id=body.customer_id,
        yarn_spec_id=body.yarn_spec_id, product_id=body.product_id,
        date=body.date, cones_count=body.cones_count, net_kg=body.net_kg,
        rate_per_kg=body.rate_per_kg, dispatch_value=val, invoice_id=body.invoice_id,
        notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_dispatch(row)


@router.patch("/dispatches/{id}/approve", dependencies=[perm_dep("spinning.dispatch", "edit")])
def approve_dispatch(id: int, user: WriteUserDep, session: SessionDep):
    _require_spinning(session, user)
    row = session.exec(
        select(SpYarnDispatch).where(SpYarnDispatch.id == id, SpYarnDispatch.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Not found")
    posting.approve_yarn_dispatch(session, user, row)
    session.commit()
    session.refresh(row)
    return _ser_dispatch(row)


# ── Production plans ─────────────────────────────────────────────────────────

class PlanCreate(BaseModel):
    plan_date: str
    yarn_spec_id: int
    target_kg: Decimal
    customer_id: Optional[int] = None
    notes: Optional[str] = None


def _ser_plan(p: SpProductionPlan) -> dict:
    return {
        "id": p.id, "number": p.number, "plan_date": p.plan_date,
        "yarn_spec_id": p.yarn_spec_id, "target_kg": float(p.target_kg),
        "target_weight": _wt(p.target_kg), "status": p.status,
        "customer_id": p.customer_id, "notes": p.notes,
    }


@router.get("/plans", dependencies=[perm_dep("spinning.plans", "view")])
def list_plans(user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    rows = session.exec(
        select(SpProductionPlan).where(SpProductionPlan.tenant_id == user.tenant_id)
    ).all()
    return [_ser_plan(r) for r in rows]


@router.post("/plans", status_code=201, dependencies=[perm_dep("spinning.plans", "edit")])
def create_plan(user: WriteUserDep, session: SessionDep, body: PlanCreate):
    _require_spinning(session, user)
    num = next_number(session, user.tenant_id, "sp_production_plan", "PP", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = SpProductionPlan(
        tenant_id=user.tenant_id, number=num, plan_date=body.plan_date,
        yarn_spec_id=body.yarn_spec_id, target_kg=body.target_kg,
        customer_id=body.customer_id, notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_plan(row)


@router.patch("/plans/{id}/approve", dependencies=[perm_dep("spinning.plans", "edit")])
def approve_plan(id: int, user: WriteUserDep, session: SessionDep):
    _require_spinning(session, user)
    row = session.exec(
        select(SpProductionPlan).where(SpProductionPlan.id == id, SpProductionPlan.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Not found")
    row.status = "approved"
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_plan(row)
