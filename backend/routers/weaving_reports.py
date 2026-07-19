"""Weaving yellow-tab reports (#140) — read-only aggregates."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, func, select

from models import Customer, Tenant
from models_weaving import (
    WvContract, WvDispatch, WvLoom, WvOperator, WvProduction,
    WvShift, WvSizing, WvYarnInward,
)
from routers.common import CurrentUserDep, SessionDep
from routers.modules import _get_enabled
from routers.weaving import _ser_contract, _ser_dispatch, _ser_production, _ser_sizing, _ser_yarn_inward
from services import weaving_calc as calc
from services.money import D, ZERO, money
from services.permissions import perm_dep

router = APIRouter(prefix="/api/weaving/reports", tags=["weaving-reports"])


def _require_weaving(session: Session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "weaving" not in _get_enabled(tenant):
        raise HTTPException(
            403,
            "The Weaving module is not installed. Install it from System → Apps.",
        )


def _sum_field(rows, attr) -> Decimal:
    total = ZERO
    for r in rows:
        total = money(total + D(getattr(r, attr) or 0))
    return total


@router.get("/dashboard", dependencies=[perm_dep("weaving.reports", "view")])
def weaving_dashboard(user: CurrentUserDep, session: SessionDep):
    """Top-level KPIs + monthly trend (reference pattern for Kg+Lbs+Bags)."""
    _require_weaving(session, user)
    tid = user.tenant_id
    inwards = session.exec(select(WvYarnInward).where(WvYarnInward.tenant_id == tid)).all()
    sizings = session.exec(select(WvSizing).where(WvSizing.tenant_id == tid)).all()
    prods = session.exec(select(WvProduction).where(WvProduction.tenant_id == tid)).all()
    disps = session.exec(select(WvDispatch).where(WvDispatch.tenant_id == tid)).all()
    contracts = session.exec(select(WvContract).where(WvContract.tenant_id == tid)).all()

    yarn_recv = _sum_field(inwards, "net_kg")
    yarn_used = _sum_field(prods, "total_yarn_kg")
    yarn_bal = money(yarn_recv - yarn_used)
    sizing_out = _sum_field(sizings, "output_kg")
    grey = _sum_field(prods, "grey_meters")
    dispatched = _sum_field(disps, "meters")
    revenue = _sum_field(disps, "weaving_charges_billed")
    avg_eff = ZERO
    if prods:
        avg_eff = money(_sum_field(prods, "efficiency_pct") / len(prods))

    # Monthly trend: group by YYYY-MM of date
    monthly: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"yarn_received_kg": ZERO, "yarn_used_kg": ZERO, "grey_meters": ZERO, "dispatch_meters": ZERO, "weaving_revenue": ZERO}
    )
    for r in inwards:
        monthly[r.date[:7]]["yarn_received_kg"] = money(monthly[r.date[:7]]["yarn_received_kg"] + r.net_kg)
    for r in prods:
        monthly[r.date[:7]]["yarn_used_kg"] = money(monthly[r.date[:7]]["yarn_used_kg"] + r.total_yarn_kg)
        monthly[r.date[:7]]["grey_meters"] = money(monthly[r.date[:7]]["grey_meters"] + r.grey_meters)
    for r in disps:
        monthly[r.date[:7]]["dispatch_meters"] = money(monthly[r.date[:7]]["dispatch_meters"] + r.meters)
        monthly[r.date[:7]]["weaving_revenue"] = money(monthly[r.date[:7]]["weaving_revenue"] + r.weaving_charges_billed)

    trend = []
    for month in sorted(monthly.keys()):
        m = monthly[month]
        trend.append({
            "month": month,
            "yarn_received": calc.weight_triple(m["yarn_received_kg"]),
            "yarn_used": calc.weight_triple(m["yarn_used_kg"]),
            "grey_meters": float(m["grey_meters"]),
            "dispatch_meters": float(m["dispatch_meters"]),
            "weaving_revenue": float(m["weaving_revenue"]),
        })

    status_counts: dict[str, int] = defaultdict(int)
    for c in contracts:
        status_counts[c.status] += 1

    return {
        "kpis": {
            "yarn_received": calc.weight_triple(yarn_recv),
            "yarn_used": calc.weight_triple(yarn_used),
            "yarn_balance": calc.weight_triple(yarn_bal),
            "sizing_output": calc.weight_triple(sizing_out),
            "grey_meters": float(grey),
            "dispatch_meters": float(dispatched),
            "weaving_revenue": float(revenue),
            "avg_efficiency_pct": float(avg_eff),
            "contract_count": len(contracts),
            "status_summary": dict(status_counts),
        },
        "monthly_trend": trend,
    }


@router.get("/daily", dependencies=[perm_dep("weaving.reports", "view")])
def daily_operations(
    user: CurrentUserDep,
    session: SessionDep,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    _require_weaving(session, user)
    tid = user.tenant_id

    def _date_filter(q, model):
        if start:
            q = q.where(model.date >= start)
        if end:
            q = q.where(model.date <= end)
        return q

    inwards = session.exec(_date_filter(select(WvYarnInward).where(WvYarnInward.tenant_id == tid), WvYarnInward)).all()
    sizings = session.exec(_date_filter(select(WvSizing).where(WvSizing.tenant_id == tid), WvSizing)).all()
    prods = session.exec(_date_filter(select(WvProduction).where(WvProduction.tenant_id == tid), WvProduction)).all()
    disps = session.exec(_date_filter(select(WvDispatch).where(WvDispatch.tenant_id == tid), WvDispatch)).all()

    yarn_recv = _sum_field(inwards, "net_kg")
    yarn_sized = _sum_field(sizings, "output_kg")
    grey = _sum_field(prods, "grey_meters")
    delivered = _sum_field(disps, "meters")
    charges = _sum_field(prods, "weaving_charges")
    receivable = _sum_field(disps, "net_receivable")
    avg_eff = money(_sum_field(prods, "efficiency_pct") / len(prods)) if prods else ZERO

    # Activity feed
    activity: list[dict[str, Any]] = []
    for r in inwards:
        w = calc.weight_triple(r.net_kg)
        activity.append({"date": r.date, "type": "yarn_inward", "number": r.number, "contract_id": r.contract_id,
                         "kg": w["kg"], "lbs": w["lbs"], "bags": w["bags"], "amount": float(r.yarn_value)})
    for r in sizings:
        w = calc.weight_triple(r.output_kg)
        activity.append({"date": r.date, "type": "sizing", "number": r.number, "contract_id": r.contract_id,
                         "kg": w["kg"], "lbs": w["lbs"], "bags": w["bags"], "amount": float(r.sizing_cost)})
    for r in prods:
        w = calc.weight_triple(r.total_yarn_kg)
        activity.append({"date": r.date, "type": "production", "number": r.number, "contract_id": r.contract_id,
                         "kg": w["kg"], "lbs": w["lbs"], "bags": w["bags"], "meters": float(r.grey_meters),
                         "efficiency_pct": float(r.efficiency_pct), "amount": float(r.weaving_charges),
                         "loom_id": r.loom_id, "shift_id": r.shift_id, "operator_id": r.operator_id})
    for r in disps:
        activity.append({"date": r.date, "type": "dispatch", "number": r.number, "contract_id": r.contract_id,
                         "meters": float(r.meters), "amount": float(r.net_receivable)})
    activity.sort(key=lambda x: (x["date"], x["number"]), reverse=True)

    # Efficiency breakdowns
    by_shift: dict[int, list] = defaultdict(list)
    by_operator: dict[int, list] = defaultdict(list)
    by_loom: dict[int, list] = defaultdict(list)
    for r in prods:
        if r.shift_id:
            by_shift[r.shift_id].append(r)
        if r.operator_id:
            by_operator[r.operator_id].append(r)
        if r.loom_id:
            by_loom[r.loom_id].append(r)

    def _avg_eff(rows):
        if not rows:
            return 0.0
        return float(money(_sum_field(rows, "efficiency_pct") / len(rows)))

    shift_names = {s.id: s.name for s in session.exec(select(WvShift).where(WvShift.tenant_id == tid)).all()}
    op_names = {o.id: o.name for o in session.exec(select(WvOperator).where(WvOperator.tenant_id == tid)).all()}
    loom_names = {l.id: l.name for l in session.exec(select(WvLoom).where(WvLoom.tenant_id == tid)).all()}

    return {
        "kpis": {
            "yarn_received": calc.weight_triple(yarn_recv),
            "yarn_sized": calc.weight_triple(yarn_sized),
            "fabric_produced_m": float(grey),
            "fabric_delivered_m": float(delivered),
            "avg_efficiency_pct": float(avg_eff),
            "weaving_charges": float(charges),
            "net_receivable": float(receivable),
        },
        "activity": activity,
        "efficiency_by_shift": [
            {"id": sid, "name": shift_names.get(sid, str(sid)), "avg_efficiency_pct": _avg_eff(rows)}
            for sid, rows in by_shift.items()
        ],
        "efficiency_by_operator": [
            {"id": oid, "name": op_names.get(oid, str(oid)), "avg_efficiency_pct": _avg_eff(rows)}
            for oid, rows in by_operator.items()
        ],
        "efficiency_by_loom": [
            {"id": lid, "name": loom_names.get(lid, str(lid)), "avg_efficiency_pct": _avg_eff(rows)}
            for lid, rows in by_loom.items()
        ],
    }


@router.get("/contract-control", dependencies=[perm_dep("weaving.reports", "view")])
def contract_control(user: CurrentUserDep, session: SessionDep, contract_id: int):
    _require_weaving(session, user)
    tid = user.tenant_id
    c = session.exec(
        select(WvContract).where(WvContract.id == contract_id, WvContract.tenant_id == tid)
    ).first()
    if not c:
        raise HTTPException(404, "Contract not found")

    inwards = session.exec(
        select(WvYarnInward).where(WvYarnInward.tenant_id == tid, WvYarnInward.contract_id == contract_id)
    ).all()
    sizings = session.exec(
        select(WvSizing).where(WvSizing.tenant_id == tid, WvSizing.contract_id == contract_id)
    ).all()
    prods = session.exec(
        select(WvProduction).where(WvProduction.tenant_id == tid, WvProduction.contract_id == contract_id)
    ).all()
    disps = session.exec(
        select(WvDispatch).where(WvDispatch.tenant_id == tid, WvDispatch.contract_id == contract_id)
    ).all()

    yarn_recv = _sum_field(inwards, "net_kg")
    yarn_sized = _sum_field(sizings, "output_kg")
    yarn_used = _sum_field(prods, "total_yarn_kg")
    grey = _sum_field(prods, "grey_meters")
    dispatched = _sum_field(disps, "meters")

    activity = []
    for r in inwards:
        w = calc.weight_triple(r.net_kg)
        activity.append({"date": r.date, "type": "yarn_inward", "number": r.number,
                         "kg": w["kg"], "lbs": w["lbs"], "bags": w["bags"]})
    for r in sizings:
        w = calc.weight_triple(r.output_kg)
        activity.append({"date": r.date, "type": "sizing", "number": r.number,
                         "kg": w["kg"], "lbs": w["lbs"], "bags": w["bags"]})
    for r in prods:
        activity.append({"date": r.date, "type": "production", "number": r.number,
                         "meters": float(r.grey_meters), **calc.weight_triple(r.total_yarn_kg)})
    for r in disps:
        activity.append({"date": r.date, "type": "dispatch", "number": r.number, "meters": float(r.meters)})
    activity.sort(key=lambda x: x["date"])

    progress_pct = float(money(dispatched / c.contract_meters * 100)) if c.contract_meters else 0.0

    return {
        "contract": _ser_contract(c),
        "progress_pct": progress_pct,
        "yarn_received": calc.weight_triple(yarn_recv),
        "yarn_sized": calc.weight_triple(yarn_sized),
        "yarn_used": calc.weight_triple(yarn_used),
        "yarn_balance": calc.weight_triple(money(yarn_recv - yarn_used)),
        "grey_meters": float(grey),
        "dispatch_meters": float(dispatched),
        "finished_stock_m": float(money(grey - dispatched)),
        "activity": activity,
        "yarn_inwards": [_ser_yarn_inward(r) for r in inwards],
        "sizings": [_ser_sizing(r) for r in sizings],
        "productions": [_ser_production(r) for r in prods],
        "dispatches": [_ser_dispatch(r) for r in disps],
    }


@router.get("/customer-kpi", dependencies=[perm_dep("weaving.reports", "view")])
def customer_contract_kpi(user: CurrentUserDep, session: SessionDep):
    _require_weaving(session, user)
    tid = user.tenant_id
    contracts = session.exec(select(WvContract).where(WvContract.tenant_id == tid)).all()
    customers = {
        c.id: c.name
        for c in session.exec(select(Customer).where(Customer.tenant_id == tid)).all()
    }

    status_counts = defaultdict(int)
    total_value = ZERO
    for c in contracts:
        status_counts[c.status] += 1
        total_value = money(total_value + calc.expected_weaving_revenue(c.contract_meters, c.weaving_rate))

    grid = []
    for c in contracts:
        inwards = session.exec(
            select(WvYarnInward).where(WvYarnInward.tenant_id == tid, WvYarnInward.contract_id == c.id)
        ).all()
        prods = session.exec(
            select(WvProduction).where(WvProduction.tenant_id == tid, WvProduction.contract_id == c.id)
        ).all()
        recv = _sum_field(inwards, "net_kg")
        used = _sum_field(prods, "total_yarn_kg")
        bal = money(recv - used)
        grid.append({
            "contract_id": c.id,
            "number": c.number,
            "customer_id": c.customer_id,
            "customer_name": customers.get(c.customer_id, ""),
            "status": c.status,
            "contract_meters": float(c.contract_meters),
            "expected_value": float(calc.expected_weaving_revenue(c.contract_meters, c.weaving_rate)),
            "yarn_received": calc.weight_triple(recv),
            "yarn_used": calc.weight_triple(used),
            "yarn_balance": calc.weight_triple(bal),
        })

    # Portfolio yarn totals
    all_in = session.exec(select(WvYarnInward).where(WvYarnInward.tenant_id == tid)).all()
    all_prod = session.exec(select(WvProduction).where(WvProduction.tenant_id == tid)).all()
    recv_t = _sum_field(all_in, "net_kg")
    used_t = _sum_field(all_prod, "total_yarn_kg")

    return {
        "portfolio": {
            "total_contracts": len(contracts),
            "in_process": status_counts.get("in_process", 0),
            "completed": status_counts.get("completed", 0),
            "delayed": status_counts.get("delayed", 0),
            "draft": status_counts.get("draft", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "total_value": float(total_value),
            "yarn_received": calc.weight_triple(recv_t),
            "yarn_used": calc.weight_triple(used_t),
            "yarn_balance": calc.weight_triple(money(recv_t - used_t)),
        },
        "contracts": grid,
    }
