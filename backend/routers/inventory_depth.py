"""Inventory depth APIs — landed cost, NRV, lot/serial (#257)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    InventoryLayer, LandedCost, LandedCostAllocation, NrVLine, NrVRun,
    Product, Settings, StockSerial,
)
from services.landed_cost import (
    LandedCostError, create_draft, layers_for_source_doc, plan_allocation, post_landed_cost,
)
from services.nrv import NrVError, create_and_post, preview_lines, reverse_run
from services.permissions import perm_dep
from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/inventory", tags=["inventory-depth"])


def _flag(session, tenant_id: int, key: str, default: str = "true") -> bool:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    val = (row.value if row else default) or default
    return val.lower() not in ("0", "false", "no", "off")


# ── Landed cost ──────────────────────────────────────────────────────────────

class LandedCostIn(BaseModel):
    cost_date: str
    amount: float
    goods_source_doc: Optional[str] = None
    goods_bill_id: Optional[int] = None
    charge_bill_id: Optional[int] = None
    allocation_method: str = "value"
    description: Optional[str] = None
    post: bool = True


def _lc_out(lc: LandedCost) -> dict:
    return {
        "id": lc.id,
        "number": lc.number,
        "cost_date": lc.cost_date,
        "amount": float(lc.amount or 0),
        "allocation_method": lc.allocation_method,
        "status": lc.status,
        "goods_source_doc": lc.goods_source_doc,
        "goods_bill_id": lc.goods_bill_id,
        "charge_bill_id": lc.charge_bill_id,
        "description": lc.description,
        "transaction_id": lc.transaction_id,
        "created_at": lc.created_at,
    }


@router.get("/landed-costs", dependencies=[perm_dep("products", "view")])
def list_landed_costs(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(LandedCost).where(LandedCost.tenant_id == user.tenant_id)
        .order_by(LandedCost.id.desc())  # type: ignore
    ).all()
    return [_lc_out(r) for r in rows]


@router.post("/landed-costs", status_code=201, dependencies=[perm_dep("products", "edit")])
def create_landed_cost(body: LandedCostIn, session: SessionDep, user: WriteUserDep):
    if not _flag(session, user.tenant_id, "inventory_landed_cost_enabled", "true"):
        raise HTTPException(400, "Landed cost is disabled in Settings")
    try:
        lc = create_draft(
            session, user,
            cost_date=body.cost_date or date.today().isoformat(),
            amount=Decimal(str(body.amount)),
            goods_source_doc=body.goods_source_doc,
            goods_bill_id=body.goods_bill_id,
            charge_bill_id=body.charge_bill_id,
            allocation_method=body.allocation_method,
            description=body.description,
        )
        if body.post:
            post_landed_cost(session, user, lc)
        session.commit()
        session.refresh(lc)
        log_audit(session, user, "CREATE", "landed_cost", lc.id, {"number": lc.number})
        session.commit()
        return _lc_out(lc)
    except LandedCostError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/landed-costs/preview", dependencies=[perm_dep("products", "view")])
def preview_landed(session: SessionDep, user: CurrentUserDep, source_doc: str, amount: float, method: str = "value"):
    layers = layers_for_source_doc(session, user.tenant_id, source_doc)
    plan = plan_allocation(layers, Decimal(str(amount)), method)
    return [
        {
            "layer_id": p["layer"].id,
            "product_id": p["layer"].product_id,
            "lot_no": p["layer"].lot_no,
            "qty_remaining": float(p["qty_basis"]),
            "unit_cost": float(p["layer"].unit_cost),
            "amount": float(p["amount"]),
        }
        for p in plan
    ]


@router.get("/landed-costs/{lc_id}", dependencies=[perm_dep("products", "view")])
def get_landed_cost(lc_id: int, session: SessionDep, user: CurrentUserDep):
    lc = session.get(LandedCost, lc_id)
    if not lc or lc.tenant_id != user.tenant_id:
        raise HTTPException(404, "Not found")
    allocs = session.exec(
        select(LandedCostAllocation).where(LandedCostAllocation.landed_cost_id == lc.id)
    ).all()
    return {**lc.model_dump(), "allocations": [a.model_dump() for a in allocs]}


# ── NRV ──────────────────────────────────────────────────────────────────────

class NrVIn(BaseModel):
    run_date: Optional[str] = None
    use_allowance: bool = True
    notes: Optional[str] = None
    # product_id → nrv_unit overrides
    overrides: Optional[dict[int, float]] = None


@router.get("/nrv/preview", dependencies=[perm_dep("products", "view")])
def nrv_preview(session: SessionDep, user: CurrentUserDep):
    if not _flag(session, user.tenant_id, "inventory_nrv_enabled", "true"):
        raise HTTPException(400, "NRV is disabled in Settings")
    rows = preview_lines(session, user.tenant_id)
    return [
        {**r, "qty": float(r["qty"]), "unit_cost": float(r["unit_cost"]),
         "nrv_unit": float(r["nrv_unit"]), "write_down": float(r["write_down"])}
        for r in rows
    ]


@router.post("/nrv/runs", status_code=201, dependencies=[perm_dep("products", "edit")])
def nrv_run(body: NrVIn, session: SessionDep, user: WriteUserDep):
    if not _flag(session, user.tenant_id, "inventory_nrv_enabled", "true"):
        raise HTTPException(400, "NRV is disabled in Settings")
    overrides = None
    if body.overrides:
        overrides = {int(k): Decimal(str(v)) for k, v in body.overrides.items()}
    try:
        run = create_and_post(
            session, user,
            run_date=body.run_date or date.today().isoformat(),
            use_allowance=body.use_allowance,
            notes=body.notes,
            overrides=overrides,
        )
        session.commit()
        session.refresh(run)
        return run.model_dump()
    except NrVError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/nrv/runs", dependencies=[perm_dep("products", "view")])
def list_nrv(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(NrVRun).where(NrVRun.tenant_id == user.tenant_id)
        .order_by(NrVRun.id.desc())  # type: ignore
    ).all()
    return [r.model_dump() for r in rows]


@router.get("/nrv/runs/{run_id}", dependencies=[perm_dep("products", "view")])
def get_nrv(run_id: int, session: SessionDep, user: CurrentUserDep):
    run = session.get(NrVRun, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Not found")
    lines = session.exec(select(NrVLine).where(NrVLine.run_id == run.id)).all()
    return {**run.model_dump(), "lines": [l.model_dump() for l in lines]}


@router.post("/nrv/runs/{run_id}/reverse", dependencies=[perm_dep("products", "edit")])
def nrv_reverse(run_id: int, session: SessionDep, user: WriteUserDep):
    run = session.get(NrVRun, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Not found")
    try:
        reverse_run(session, user, run)
        session.commit()
        session.refresh(run)
        return run.model_dump()
    except NrVError as exc:
        raise HTTPException(400, str(exc)) from exc


# ── Layers / serials (stock card helpers) ────────────────────────────────────

@router.get("/layers", dependencies=[perm_dep("products", "view")])
def list_layers(
    session: SessionDep, user: CurrentUserDep,
    product_id: Optional[int] = None, lot_no: Optional[str] = None,
):
    q = select(InventoryLayer).where(
        InventoryLayer.tenant_id == user.tenant_id,
        InventoryLayer.qty_remaining > 0,
    )
    if product_id:
        q = q.where(InventoryLayer.product_id == product_id)
    if lot_no:
        q = q.where(InventoryLayer.lot_no == lot_no)
    rows = session.exec(q.order_by(InventoryLayer.id.desc())).all()  # type: ignore
    return [r.model_dump() for r in rows]


@router.get("/serials", dependencies=[perm_dep("products", "view")])
def list_serials(
    session: SessionDep, user: CurrentUserDep,
    product_id: Optional[int] = None, status: str = "available",
):
    q = select(StockSerial).where(StockSerial.tenant_id == user.tenant_id)
    if product_id:
        q = q.where(StockSerial.product_id == product_id)
    if status and status != "all":
        q = q.where(StockSerial.status == status)
    rows = session.exec(q.order_by(StockSerial.id.desc())).all()  # type: ignore
    return [r.model_dump() for r in rows]
