"""Weaving unit-control module (#140) — masters + operational documents (memo/ops)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from models import Customer, Vendor
from models_weaving import (
    WvContract, WvDispatch, WvFabricQuality, WvLoom, WvOperator,
    WvProduction, WvShift, WvSizing, WvYarnInward, WvYarnType,
)
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit, next_number
from routers.modules import _get_enabled
from services.money import D, ZERO, money
from services.permissions import perm_dep
from services import weaving_calc as calc
from models import Tenant

router = APIRouter(prefix="/api/weaving", tags=["weaving"])

_STATUSES = {"draft", "in_process", "completed", "delayed", "cancelled"}


def _require_weaving(session: Session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "weaving" not in _get_enabled(tenant):
        raise HTTPException(
            403,
            "The Weaving module is not installed. Install it from System → Apps.",
        )


def _contract_or_404(session: Session, tenant_id: int, cid: int) -> WvContract:
    row = session.exec(
        select(WvContract).where(WvContract.id == cid, WvContract.tenant_id == tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Contract not found")
    return row


def _ser_weight(kg: Decimal | float | None) -> dict[str, float]:
    return calc.weight_triple(kg)


def _ser_contract(c: WvContract) -> dict[str, Any]:
    return {
        "id": c.id,
        "number": c.number,
        "customer_id": c.customer_id,
        "fabric_quality_id": c.fabric_quality_id,
        "yarn_type_id": c.yarn_type_id,
        "start_date": c.start_date,
        "end_date": c.end_date,
        "contract_meters": float(c.contract_meters),
        "pick_per_inch": float(c.pick_per_inch),
        "assumed_yarn_rate_per_kg": float(c.assumed_yarn_rate_per_kg),
        "assumed_yarn_rate_per_lb": calc.rate_per_lb(c.assumed_yarn_rate_per_kg),
        "fabric_return_price_per_meter": float(c.fabric_return_price_per_meter),
        "weaving_rate": float(c.weaving_rate),
        "expected_shrinkage_pct": float(c.expected_shrinkage_pct),
        "expected_weaving_revenue": float(
            calc.expected_weaving_revenue(c.contract_meters, c.weaving_rate)
        ),
        "payment_terms": c.payment_terms,
        "status": c.status,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _ser_yarn_inward(r: WvYarnInward) -> dict[str, Any]:
    net = _ser_weight(r.net_kg)
    return {
        "id": r.id,
        "number": r.number,
        "contract_id": r.contract_id,
        "yarn_type_id": r.yarn_type_id,
        "date": r.date,
        "gross_kg": float(r.gross_kg),
        "tare_kg": float(r.tare_kg),
        "net_kg": float(r.net_kg),
        "net_lbs": net["lbs"],
        "net_bags": net["bags"],
        "rate_per_kg": float(r.rate_per_kg),
        "rate_per_lb": calc.rate_per_lb(r.rate_per_kg),
        "yarn_value": float(r.yarn_value),
        "notes": r.notes,
    }


def _ser_sizing(r: WvSizing) -> dict[str, Any]:
    inp = _ser_weight(r.input_kg)
    out = _ser_weight(r.output_kg)
    return {
        "id": r.id,
        "number": r.number,
        "contract_id": r.contract_id,
        "vendor_id": r.vendor_id,
        "date": r.date,
        "input_kg": float(r.input_kg),
        "input_lbs": inp["lbs"],
        "input_bags": inp["bags"],
        "output_kg": float(r.output_kg),
        "output_lbs": out["lbs"],
        "output_bags": out["bags"],
        "gain_shrink_pct": float(r.gain_shrink_pct),
        "sizing_cost": float(r.sizing_cost),
        "notes": r.notes,
    }


def _ser_production(r: WvProduction) -> dict[str, Any]:
    total = _ser_weight(r.total_yarn_kg)
    return {
        "id": r.id,
        "number": r.number,
        "contract_id": r.contract_id,
        "loom_id": r.loom_id,
        "shift_id": r.shift_id,
        "operator_id": r.operator_id,
        "date": r.date,
        "warp_yarn_kg": float(r.warp_yarn_kg),
        "weft_yarn_kg": float(r.weft_yarn_kg),
        "total_yarn_kg": float(r.total_yarn_kg),
        "total_yarn_lbs": total["lbs"],
        "total_yarn_bags": total["bags"],
        "grey_meters": float(r.grey_meters),
        "efficiency_pct": float(r.efficiency_pct),
        "weaving_charges": float(r.weaving_charges),
        "notes": r.notes,
    }


def _ser_dispatch(r: WvDispatch) -> dict[str, Any]:
    return {
        "id": r.id,
        "number": r.number,
        "contract_id": r.contract_id,
        "date": r.date,
        "meters": float(r.meters),
        "dispatch_value": float(r.dispatch_value),
        "weaving_charges_billed": float(r.weaving_charges_billed),
        "net_receivable": float(r.net_receivable),
        "notes": r.notes,
    }


# ── Master CRUD helper factory ───────────────────────────────────────────────

def _master_list(session, model, tenant_id, active_only: bool = False):
    q = select(model).where(model.tenant_id == tenant_id)
    if active_only and hasattr(model, "is_active"):
        q = q.where(model.is_active == True)  # noqa: E712
    return session.exec(q.order_by(model.code)).all()


class MasterCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    loom_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True


class MasterUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    loom_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


def _ser_master(row) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "is_active": row.is_active,
    }
    for attr in ("description", "loom_type", "start_time", "end_time", "phone"):
        if hasattr(row, attr):
            d[attr] = getattr(row, attr)
    return d


# Fabric qualities
@router.get("/fabric-qualities", dependencies=[perm_dep("weaving.setup", "view")])
def list_fabric_qualities(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_weaving(session, user)
    return [_ser_master(r) for r in _master_list(session, WvFabricQuality, user.tenant_id, active_only)]


@router.post("/fabric-qualities", status_code=201, dependencies=[perm_dep("weaving.setup", "edit")])
def create_fabric_quality(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_weaving(session, user)
    row = WvFabricQuality(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        description=body.description, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log_audit(session, user, "create", "wv_fabric_quality", row.id, body.code)
    return _ser_master(row)


@router.put("/fabric-qualities/{id}", dependencies=[perm_dep("weaving.setup", "edit")])
def update_fabric_quality(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_weaving(session, user)
    row = session.exec(
        select(WvFabricQuality).where(WvFabricQuality.id == id, WvFabricQuality.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


# Looms
@router.get("/looms", dependencies=[perm_dep("weaving.setup", "view")])
def list_looms(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_weaving(session, user)
    return [_ser_master(r) for r in _master_list(session, WvLoom, user.tenant_id, active_only)]


@router.post("/looms", status_code=201, dependencies=[perm_dep("weaving.setup", "edit")])
def create_loom(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_weaving(session, user)
    row = WvLoom(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        loom_type=body.loom_type, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log_audit(session, user, "create", "wv_loom", row.id, body.code)
    return _ser_master(row)


@router.put("/looms/{id}", dependencies=[perm_dep("weaving.setup", "edit")])
def update_loom(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_weaving(session, user)
    row = session.exec(select(WvLoom).where(WvLoom.id == id, WvLoom.tenant_id == user.tenant_id)).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


# Yarn types
@router.get("/yarn-types", dependencies=[perm_dep("weaving.setup", "view")])
def list_yarn_types(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_weaving(session, user)
    return [_ser_master(r) for r in _master_list(session, WvYarnType, user.tenant_id, active_only)]


@router.post("/yarn-types", status_code=201, dependencies=[perm_dep("weaving.setup", "edit")])
def create_yarn_type(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_weaving(session, user)
    row = WvYarnType(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        description=body.description, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.put("/yarn-types/{id}", dependencies=[perm_dep("weaving.setup", "edit")])
def update_yarn_type(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_weaving(session, user)
    row = session.exec(
        select(WvYarnType).where(WvYarnType.id == id, WvYarnType.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


# Shifts
@router.get("/shifts", dependencies=[perm_dep("weaving.setup", "view")])
def list_shifts(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_weaving(session, user)
    return [_ser_master(r) for r in _master_list(session, WvShift, user.tenant_id, active_only)]


@router.post("/shifts", status_code=201, dependencies=[perm_dep("weaving.setup", "edit")])
def create_shift(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_weaving(session, user)
    row = WvShift(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        start_time=body.start_time, end_time=body.end_time, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.put("/shifts/{id}", dependencies=[perm_dep("weaving.setup", "edit")])
def update_shift(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_weaving(session, user)
    row = session.exec(select(WvShift).where(WvShift.id == id, WvShift.tenant_id == user.tenant_id)).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


# Operators
@router.get("/operators", dependencies=[perm_dep("weaving.setup", "view")])
def list_operators(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_weaving(session, user)
    return [_ser_master(r) for r in _master_list(session, WvOperator, user.tenant_id, active_only)]


@router.post("/operators", status_code=201, dependencies=[perm_dep("weaving.setup", "edit")])
def create_operator(user: WriteUserDep, session: SessionDep, body: MasterCreate):
    _require_weaving(session, user)
    row = WvOperator(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        phone=body.phone, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


@router.put("/operators/{id}", dependencies=[perm_dep("weaving.setup", "edit")])
def update_operator(id: int, user: WriteUserDep, session: SessionDep, body: MasterUpdate):
    _require_weaving(session, user)
    row = session.exec(
        select(WvOperator).where(WvOperator.id == id, WvOperator.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_master(row)


# ── Contracts ────────────────────────────────────────────────────────────────

class ContractCreate(BaseModel):
    customer_id: int
    fabric_quality_id: Optional[int] = None
    yarn_type_id: Optional[int] = None
    start_date: str
    end_date: Optional[str] = None
    contract_meters: Decimal = ZERO
    pick_per_inch: Decimal = ZERO
    assumed_yarn_rate_per_kg: Decimal = ZERO
    fabric_return_price_per_meter: Decimal = ZERO
    weaving_rate: Decimal = ZERO
    expected_shrinkage_pct: Decimal = ZERO
    payment_terms: Optional[str] = None
    status: str = "draft"
    notes: Optional[str] = None


class ContractUpdate(BaseModel):
    customer_id: Optional[int] = None
    fabric_quality_id: Optional[int] = None
    yarn_type_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    contract_meters: Optional[Decimal] = None
    pick_per_inch: Optional[Decimal] = None
    assumed_yarn_rate_per_kg: Optional[Decimal] = None
    fabric_return_price_per_meter: Optional[Decimal] = None
    weaving_rate: Optional[Decimal] = None
    expected_shrinkage_pct: Optional[Decimal] = None
    payment_terms: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("/contracts", dependencies=[perm_dep("weaving.contracts", "view")])
def list_contracts(user: CurrentUserDep, session: SessionDep, status: Optional[str] = None):
    _require_weaving(session, user)
    q = select(WvContract).where(WvContract.tenant_id == user.tenant_id)
    if status:
        q = q.where(WvContract.status == status)
    rows = session.exec(q.order_by(WvContract.id.desc())).all()
    return [_ser_contract(r) for r in rows]


@router.get("/contracts/{id}", dependencies=[perm_dep("weaving.contracts", "view")])
def get_contract(id: int, user: CurrentUserDep, session: SessionDep):
    _require_weaving(session, user)
    return _ser_contract(_contract_or_404(session, user.tenant_id, id))


@router.post("/contracts", status_code=201, dependencies=[perm_dep("weaving.contracts", "edit")])
def create_contract(user: WriteUserDep, session: SessionDep, body: ContractCreate):
    _require_weaving(session, user)
    cust = session.exec(
        select(Customer).where(Customer.id == body.customer_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not cust:
        raise HTTPException(400, "Customer not found")
    if body.status not in _STATUSES:
        raise HTTPException(400, f"Invalid status; expected one of {sorted(_STATUSES)}")
    num = next_number(session, user.tenant_id, "wv_contract", "WC", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = WvContract(
        tenant_id=user.tenant_id,
        number=num,
        customer_id=body.customer_id,
        fabric_quality_id=body.fabric_quality_id,
        yarn_type_id=body.yarn_type_id,
        start_date=body.start_date,
        end_date=body.end_date,
        contract_meters=money(body.contract_meters),
        pick_per_inch=money(body.pick_per_inch),
        assumed_yarn_rate_per_kg=money(body.assumed_yarn_rate_per_kg),
        fabric_return_price_per_meter=money(body.fabric_return_price_per_meter),
        weaving_rate=money(body.weaving_rate),
        expected_shrinkage_pct=money(body.expected_shrinkage_pct),
        payment_terms=body.payment_terms,
        status=body.status,
        notes=body.notes,
        created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log_audit(session, user, "create", "wv_contract", row.id, num)
    return _ser_contract(row)


@router.put("/contracts/{id}", dependencies=[perm_dep("weaving.contracts", "edit")])
def update_contract(id: int, user: WriteUserDep, session: SessionDep, body: ContractUpdate):
    _require_weaving(session, user)
    row = _contract_or_404(session, user.tenant_id, id)
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in _STATUSES:
        raise HTTPException(400, f"Invalid status; expected one of {sorted(_STATUSES)}")
    money_fields = {
        "contract_meters", "pick_per_inch", "assumed_yarn_rate_per_kg",
        "fabric_return_price_per_meter", "weaving_rate", "expected_shrinkage_pct",
    }
    for k, v in data.items():
        if k in money_fields and v is not None:
            setattr(row, k, money(v))
        else:
            setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_contract(row)


# ── Yarn Inward ──────────────────────────────────────────────────────────────

class YarnInwardCreate(BaseModel):
    contract_id: int
    yarn_type_id: Optional[int] = None
    date: str
    gross_kg: Decimal = ZERO
    tare_kg: Decimal = ZERO
    rate_per_kg: Optional[Decimal] = None
    yarn_value: Optional[Decimal] = None
    notes: Optional[str] = None


@router.get("/yarn-inwards", dependencies=[perm_dep("weaving.yarn_inward", "view")])
def list_yarn_inwards(user: CurrentUserDep, session: SessionDep, contract_id: Optional[int] = None):
    _require_weaving(session, user)
    q = select(WvYarnInward).where(WvYarnInward.tenant_id == user.tenant_id)
    if contract_id:
        q = q.where(WvYarnInward.contract_id == contract_id)
    return [_ser_yarn_inward(r) for r in session.exec(q.order_by(WvYarnInward.id.desc())).all()]


@router.post("/yarn-inwards", status_code=201, dependencies=[perm_dep("weaving.yarn_inward", "edit")])
def create_yarn_inward(user: WriteUserDep, session: SessionDep, body: YarnInwardCreate):
    _require_weaving(session, user)
    c = _contract_or_404(session, user.tenant_id, body.contract_id)
    net = calc.net_kg(body.gross_kg, body.tare_kg)
    rate = money(body.rate_per_kg) if body.rate_per_kg is not None else money(c.assumed_yarn_rate_per_kg)
    value = money(body.yarn_value) if body.yarn_value is not None else money(net * rate)
    num = next_number(session, user.tenant_id, "wv_yarn_inward", "YI", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = WvYarnInward(
        tenant_id=user.tenant_id, number=num, contract_id=c.id,
        yarn_type_id=body.yarn_type_id or c.yarn_type_id, date=body.date,
        gross_kg=money(body.gross_kg), tare_kg=money(body.tare_kg), net_kg=net,
        rate_per_kg=rate, yarn_value=value, notes=body.notes, created_by_id=user.id,
    )
    if c.status == "draft":
        c.status = "in_process"
        session.add(c)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_yarn_inward(row)


# ── Sizing ───────────────────────────────────────────────────────────────────

class SizingCreate(BaseModel):
    contract_id: int
    vendor_id: Optional[int] = None
    date: str
    input_kg: Decimal = ZERO
    output_kg: Decimal = ZERO
    sizing_cost: Decimal = ZERO
    notes: Optional[str] = None


@router.get("/sizings", dependencies=[perm_dep("weaving.sizing", "view")])
def list_sizings(user: CurrentUserDep, session: SessionDep, contract_id: Optional[int] = None):
    _require_weaving(session, user)
    q = select(WvSizing).where(WvSizing.tenant_id == user.tenant_id)
    if contract_id:
        q = q.where(WvSizing.contract_id == contract_id)
    return [_ser_sizing(r) for r in session.exec(q.order_by(WvSizing.id.desc())).all()]


@router.post("/sizings", status_code=201, dependencies=[perm_dep("weaving.sizing", "edit")])
def create_sizing(user: WriteUserDep, session: SessionDep, body: SizingCreate):
    _require_weaving(session, user)
    _contract_or_404(session, user.tenant_id, body.contract_id)
    if body.vendor_id is not None:
        v = session.exec(
            select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)
        ).first()
        if not v:
            raise HTTPException(400, "Vendor not found")
    pct = calc.sizing_gain_shrink_pct(body.input_kg, body.output_kg)
    num = next_number(session, user.tenant_id, "wv_sizing", "SZ", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = WvSizing(
        tenant_id=user.tenant_id, number=num, contract_id=body.contract_id,
        vendor_id=body.vendor_id, date=body.date,
        input_kg=money(body.input_kg), output_kg=money(body.output_kg),
        gain_shrink_pct=money(pct), sizing_cost=money(body.sizing_cost),
        notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_sizing(row)


# ── Production ───────────────────────────────────────────────────────────────

class ProductionCreate(BaseModel):
    contract_id: int
    loom_id: Optional[int] = None
    shift_id: Optional[int] = None
    operator_id: Optional[int] = None
    date: str
    warp_yarn_kg: Decimal = ZERO
    weft_yarn_kg: Decimal = ZERO
    grey_meters: Decimal = ZERO
    efficiency_pct: Optional[Decimal] = None
    weaving_charges: Optional[Decimal] = None
    notes: Optional[str] = None


@router.get("/productions", dependencies=[perm_dep("weaving.production", "view")])
def list_productions(user: CurrentUserDep, session: SessionDep, contract_id: Optional[int] = None):
    _require_weaving(session, user)
    q = select(WvProduction).where(WvProduction.tenant_id == user.tenant_id)
    if contract_id:
        q = q.where(WvProduction.contract_id == contract_id)
    return [_ser_production(r) for r in session.exec(q.order_by(WvProduction.id.desc())).all()]


@router.post("/productions", status_code=201, dependencies=[perm_dep("weaving.production", "edit")])
def create_production(user: WriteUserDep, session: SessionDep, body: ProductionCreate):
    _require_weaving(session, user)
    c = _contract_or_404(session, user.tenant_id, body.contract_id)
    total = money(D(body.warp_yarn_kg) + D(body.weft_yarn_kg))
    eff = (
        money(body.efficiency_pct)
        if body.efficiency_pct is not None
        else money(calc.production_efficiency_pct(body.grey_meters, c.contract_meters))
    )
    charges = (
        money(body.weaving_charges)
        if body.weaving_charges is not None
        else calc.weaving_charges(body.grey_meters, c.weaving_rate)
    )
    num = next_number(session, user.tenant_id, "wv_production", "WP", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = WvProduction(
        tenant_id=user.tenant_id, number=num, contract_id=c.id,
        loom_id=body.loom_id, shift_id=body.shift_id, operator_id=body.operator_id,
        date=body.date, warp_yarn_kg=money(body.warp_yarn_kg), weft_yarn_kg=money(body.weft_yarn_kg),
        total_yarn_kg=total, grey_meters=money(body.grey_meters),
        efficiency_pct=eff, weaving_charges=charges, notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_production(row)


# ── Dispatch ─────────────────────────────────────────────────────────────────

class DispatchCreate(BaseModel):
    contract_id: int
    date: str
    meters: Decimal = ZERO
    dispatch_value: Optional[Decimal] = None
    weaving_charges_billed: Optional[Decimal] = None
    net_receivable: Optional[Decimal] = None
    notes: Optional[str] = None


@router.get("/dispatches", dependencies=[perm_dep("weaving.dispatch", "view")])
def list_dispatches(user: CurrentUserDep, session: SessionDep, contract_id: Optional[int] = None):
    _require_weaving(session, user)
    q = select(WvDispatch).where(WvDispatch.tenant_id == user.tenant_id)
    if contract_id:
        q = q.where(WvDispatch.contract_id == contract_id)
    return [_ser_dispatch(r) for r in session.exec(q.order_by(WvDispatch.id.desc())).all()]


@router.post("/dispatches", status_code=201, dependencies=[perm_dep("weaving.dispatch", "edit")])
def create_dispatch(user: WriteUserDep, session: SessionDep, body: DispatchCreate):
    _require_weaving(session, user)
    c = _contract_or_404(session, user.tenant_id, body.contract_id)
    dval = (
        money(body.dispatch_value)
        if body.dispatch_value is not None
        else calc.dispatch_value(body.meters, c.fabric_return_price_per_meter)
    )
    billed = (
        money(body.weaving_charges_billed)
        if body.weaving_charges_billed is not None
        else calc.weaving_charges(body.meters, c.weaving_rate)
    )
    net = (
        money(body.net_receivable)
        if body.net_receivable is not None
        else calc.net_receivable(dval, billed)
    )
    num = next_number(session, user.tenant_id, "wv_dispatch", "WD", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = WvDispatch(
        tenant_id=user.tenant_id, number=num, contract_id=c.id, date=body.date,
        meters=money(body.meters), dispatch_value=dval,
        weaving_charges_billed=billed, net_receivable=net,
        notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_dispatch(row)
