"""Yarn Spinning reports — dashboard, daily register, lot control, waste, dispatch."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, func, select

from models import Tenant
from models_spinning import (
    STAGE_ORDER,
    SpBaleReceipt,
    SpConeOutput,
    SpSpinLot,
    SpStageEntry,
    SpWasteLog,
    SpYarnDispatch,
    SpYarnSpec,
)
from routers.common import CurrentUserDep, SessionDep
from routers.modules import _get_enabled
from services import spinning_calc as calc
from services.money import D, ZERO, money
from services.permissions import perm_dep

router = APIRouter(prefix="/api/spinning/reports", tags=["spinning-reports"])


def _require_spinning(session: Session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "spinning" not in _get_enabled(tenant):
        raise HTTPException(403, "The Yarn Spinning module is not installed.")


def _sum(rows, attr) -> Decimal:
    return money(sum((D(getattr(r, attr) or 0) for r in rows), start=ZERO))


@router.get("/dashboard", dependencies=[perm_dep("spinning.reports", "view")])
def spinning_dashboard(user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    tid = user.tenant_id
    lots = session.exec(select(SpSpinLot).where(SpSpinLot.tenant_id == tid)).all()
    bales = session.exec(
        select(SpBaleReceipt).where(SpBaleReceipt.tenant_id == tid, SpBaleReceipt.status == "approved")
    ).all()
    stages = session.exec(
        select(SpStageEntry).where(SpStageEntry.tenant_id == tid, SpStageEntry.status == "posted")
    ).all()
    cones = session.exec(
        select(SpConeOutput).where(SpConeOutput.tenant_id == tid, SpConeOutput.status == "approved")
    ).all()
    disps = session.exec(
        select(SpYarnDispatch).where(SpYarnDispatch.tenant_id == tid, SpYarnDispatch.status == "approved")
    ).all()

    open_lots = sum(1 for l in lots if l.status in ("draft", "in_process"))
    bale_in = _sum(bales, "net_kg")
    cone_out = _sum(cones, "net_kg")
    disp_kg = _sum(disps, "net_kg")
    disp_val = _sum(disps, "dispatch_value")

    wip_by_stage: dict[str, float] = {}
    for st in STAGE_ORDER:
        ins = _sum([s for s in stages if s.stage == st], "input_kg")
        outs = _sum([s for s in stages if s.stage == st], "output_kg")
        wip_by_stage[st] = float(money(ins - outs))

    status_counts: dict[str, int] = defaultdict(int)
    for l in lots:
        status_counts[l.status] += 1

    yield_pct = calc.lot_yield_pct(bale_in, cone_out) if bale_in else 0.0

    return {
        "kpis": {
            "open_lots": open_lots,
            "bale_received": calc.weight_triple(bale_in),
            "cone_output": calc.weight_triple(cone_out),
            "dispatched": calc.weight_triple(disp_kg),
            "dispatch_value": float(disp_val),
            "overall_yield_pct": yield_pct,
            "lot_count": len(lots),
            "status_summary": dict(status_counts),
        },
        "wip_by_stage": wip_by_stage,
    }


@router.get("/daily", dependencies=[perm_dep("spinning.reports", "view")])
def daily_register(
    user: CurrentUserDep, session: SessionDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    _require_spinning(session, user)
    tid = user.tenant_id
    q = select(SpStageEntry).where(SpStageEntry.tenant_id == tid, SpStageEntry.status == "posted")
    if start:
        q = q.where(SpStageEntry.date >= start)
    if end:
        q = q.where(SpStageEntry.date <= end)
    rows = session.exec(q.order_by(SpStageEntry.date)).all()

    by_date: dict[str, list] = defaultdict(list)
    for r in rows:
        by_date[r.date].append({
            "number": r.number, "stage": r.stage, "spin_lot_id": r.spin_lot_id,
            "input_kg": float(r.input_kg), "output_kg": float(r.output_kg),
            "waste_kg": float(r.waste_kg), "yield_pct": float(r.yield_pct),
            "machine_id": r.machine_id, "shift_id": r.shift_id,
        })

    items = []
    for d in sorted(by_date.keys()):
        entries = by_date[d]
        items.append({
            "date": d,
            "input_kg": sum(e["input_kg"] for e in entries),
            "output_kg": sum(e["output_kg"] for e in entries),
            "waste_kg": sum(e["waste_kg"] for e in entries),
            "entries": entries,
        })
    return {"items": items}


@router.get("/lot-control/{lot_id}", dependencies=[perm_dep("spinning.reports", "view")])
def lot_control(lot_id: int, user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    lot = session.exec(
        select(SpSpinLot).where(SpSpinLot.id == lot_id, SpSpinLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(404, "Lot not found")

    bales = session.exec(select(SpBaleReceipt).where(SpBaleReceipt.spin_lot_id == lot_id)).all()
    stages = session.exec(
        select(SpStageEntry).where(SpStageEntry.spin_lot_id == lot_id).order_by(SpStageEntry.date)
    ).all()
    cones = session.exec(select(SpConeOutput).where(SpConeOutput.spin_lot_id == lot_id)).all()
    waste = session.exec(select(SpWasteLog).where(SpWasteLog.spin_lot_id == lot_id)).all()

    bale_kg = _sum([b for b in bales if b.status == "approved"], "net_kg")
    cone_kg = _sum([c for c in cones if c.status == "approved"], "net_kg")
    waste_kg = _sum([w for w in waste if w.status == "posted"], "qty_kg")

    stage_progress = []
    for st in STAGE_ORDER:
        st_rows = [s for s in stages if s.stage == st]
        if st_rows:
            stage_progress.append({
                "stage": st,
                "input_kg": float(_sum(st_rows, "input_kg")),
                "output_kg": float(_sum(st_rows, "output_kg")),
                "yield_pct": calc.stage_yield_pct(_sum(st_rows, "input_kg"), _sum(st_rows, "output_kg")),
                "entries": len(st_rows),
            })

    return {
        "lot": {
            "id": lot.id, "number": lot.number, "status": lot.status,
            "target_output_kg": float(lot.target_output_kg),
            "output_kg": float(lot.output_kg),
            "total_cost": float(lot.total_cost), "cost_per_kg": float(lot.cost_per_kg),
        },
        "bale_in_kg": float(bale_kg),
        "cone_out_kg": float(cone_kg),
        "waste_kg": float(waste_kg),
        "yield_pct": calc.lot_yield_pct(bale_kg, cone_kg),
        "stage_progress": stage_progress,
        "plan_variance_kg": float(money(lot.target_output_kg - lot.output_kg)),
    }


@router.get("/waste", dependencies=[perm_dep("spinning.reports", "view")])
def waste_analysis(user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    rows = session.exec(
        select(SpWasteLog).where(SpWasteLog.tenant_id == user.tenant_id, SpWasteLog.status == "posted")
    ).all()
    by_type: dict[int, dict] = defaultdict(lambda: {"qty_kg": ZERO, "cost": ZERO, "count": 0})
    by_stage: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for r in rows:
        by_type[r.waste_type_id]["qty_kg"] = money(by_type[r.waste_type_id]["qty_kg"] + r.qty_kg)
        by_type[r.waste_type_id]["cost"] = money(by_type[r.waste_type_id]["cost"] + r.cost_value)
        by_type[r.waste_type_id]["count"] += 1
        by_stage[r.stage] = money(by_stage[r.stage] + r.qty_kg)

    return {
        "by_type": {str(k): {"qty_kg": float(v["qty_kg"]), "cost": float(v["cost"]), "count": v["count"]}
                    for k, v in by_type.items()},
        "by_stage": {k: float(v) for k, v in by_stage.items()},
        "total_waste_kg": float(_sum(rows, "qty_kg")),
    }


@router.get("/cost-per-kg", dependencies=[perm_dep("spinning.reports", "view")])
def cost_per_kg_report(user: CurrentUserDep, session: SessionDep):
    _require_spinning(session, user)
    lots = session.exec(
        select(SpSpinLot).where(
            SpSpinLot.tenant_id == user.tenant_id,
            SpSpinLot.status.in_(["completed", "closed"]),
        )
    ).all()
    specs = {s.id: s for s in session.exec(select(SpYarnSpec).where(SpYarnSpec.tenant_id == user.tenant_id)).all()}
    items = []
    for lot in lots:
        spec = specs.get(lot.yarn_spec_id)
        items.append({
            "lot_number": lot.number,
            "yarn_spec": spec.name if spec else "",
            "count_ne": float(spec.count_ne) if spec and spec.count_ne else None,
            "output_kg": float(lot.output_kg),
            "material_cost": float(lot.material_cost),
            "labour_cost": float(lot.labour_cost),
            "overhead_cost": float(lot.overhead_cost),
            "waste_cost": float(lot.waste_cost),
            "total_cost": float(lot.total_cost),
            "cost_per_kg": float(lot.cost_per_kg),
        })
    return {"items": items}


@router.get("/dispatch", dependencies=[perm_dep("spinning.reports", "view")])
def dispatch_register(
    user: CurrentUserDep, session: SessionDep,
    q: Optional[str] = None, skip: int = 0, limit: int = 50,
):
    _require_spinning(session, user)
    stmt = select(SpYarnDispatch).where(SpYarnDispatch.tenant_id == user.tenant_id)
    if q:
        stmt = stmt.where(SpYarnDispatch.number.ilike(f"%{q}%"))
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(stmt.order_by(SpYarnDispatch.date.desc()).offset(skip).limit(limit)).all()
    items = [{
        "id": r.id, "number": r.number, "date": r.date, "customer_id": r.customer_id,
        "net_kg": float(r.net_kg), "dispatch_value": float(r.dispatch_value),
        "status": r.status, "cones_count": r.cones_count,
    } for r in rows]
    return {"total": total, "items": items}
