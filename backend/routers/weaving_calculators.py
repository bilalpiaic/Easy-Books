"""Weaving / sizing planning calculators (#196)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from models import Tenant
from models_weaving import WvCalcRun, WvContract
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from routers.modules import _get_enabled
from routers.weaving import _contract_or_404, _ser_contract
from services.money import D
from services.permissions import perm_dep
from services import weaving_yarn_calc as ycalc

router = APIRouter(prefix="/api/weaving/calculators", tags=["weaving-calculators"])


def _require_weaving(session: Session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "weaving" not in _get_enabled(tenant):
        raise HTTPException(
            403,
            "The Weaving module is not installed. Install it from System → Apps.",
        )


class WeavingCalcIn(BaseModel):
    epi: Decimal
    ppi: Decimal
    width_in: Decimal
    length_yd: Decimal
    warp_ne: Decimal
    weft_ne: Decimal
    warp_crimp_pct: Decimal = Decimal("0")
    weft_crimp_pct: Decimal = Decimal("0")
    visible_waste_pct: Decimal = Decimal("3")
    invisible_waste_pct: Decimal = Decimal("1")


class SizingCalcIn(BaseModel):
    unsized_kg: Decimal
    pickup_pct: Decimal = Decimal("12")
    stretch_pct: Decimal = Decimal("1.5")
    visible_waste_pct: Decimal = Decimal("0.7")
    invisible_waste_pct: Decimal = Decimal("1")


class AssignWeavingIn(WeavingCalcIn):
    contract_id: int
    override_reason: Optional[str] = None


class AssignSizingIn(SizingCalcIn):
    contract_id: int
    override_reason: Optional[str] = None


def _contract_snapshot(c: WvContract) -> dict[str, Any]:
    return {
        "planned_total_yarn_kg": c.planned_total_yarn_kg,
        "warp_count_ne": c.warp_count_ne,
        "weft_count_ne": c.weft_count_ne,
    }


def _ser_run(r: WvCalcRun) -> dict[str, Any]:
    return {
        "id": r.id,
        "contract_id": r.contract_id,
        "calc_type": r.calc_type,
        "inputs": r.inputs,
        "outputs": r.outputs,
        "override_reason": r.override_reason,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "created_by_id": r.created_by_id,
    }


def _json_safe(d: dict) -> dict:
    """Ensure Decimal values become JSON-serializable floats for JSON column."""
    out = {}
    for k, v in d.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


@router.post("/weaving", dependencies=[perm_dep("weaving.calculators", "view")])
def preview_weaving(user: CurrentUserDep, session: SessionDep, body: WeavingCalcIn):
    _require_weaving(session, user)
    return ycalc.calculate_weaving(**body.model_dump())


@router.post("/sizing", dependencies=[perm_dep("weaving.calculators", "view")])
def preview_sizing(user: CurrentUserDep, session: SessionDep, body: SizingCalcIn):
    _require_weaving(session, user)
    return ycalc.calculate_sizing(**body.model_dump())


@router.post("/weaving/assign", dependencies=[perm_dep("weaving.calculators", "edit")])
def assign_weaving(user: WriteUserDep, session: SessionDep, body: AssignWeavingIn):
    _require_weaving(session, user)
    c = _contract_or_404(session, user.tenant_id, body.contract_id)
    inputs = _json_safe(body.model_dump(exclude={"contract_id", "override_reason"}))
    result = ycalc.calculate_weaving(**inputs)
    cmp = ycalc.compare_to_contract(result, _contract_snapshot(c), threshold=0.10)
    if not cmp["ok"]:
        reason = (body.override_reason or "").strip()
        if not reason:
            raise HTTPException(
                400,
                detail={
                    "message": "Calculation mismatches contract; provide override_reason",
                    "warnings": cmp["warnings"],
                },
            )
    else:
        reason = (body.override_reason or "").strip() or None

    now = datetime.utcnow()
    c.planned_warp_kg = D(result["warp_kg"])
    c.planned_weft_kg = D(result["weft_kg"])
    c.planned_total_yarn_kg = D(result["total_kg"])
    c.warp_count_ne = D(result["warp_ne"])
    c.weft_count_ne = D(result["weft_ne"])
    c.last_calc_at = now
    session.add(c)

    run = WvCalcRun(
        tenant_id=user.tenant_id,
        contract_id=c.id,
        calc_type="weaving",
        inputs=inputs,
        outputs=result,
        override_reason=reason,
        created_by_id=user.id,
        created_at=now,
    )
    session.add(run)
    session.commit()
    session.refresh(c)
    session.refresh(run)
    log_audit(session, user, "assign", "wv_calc_run", run.id, {"contract": c.number, "type": "weaving"})
    return {"contract": _ser_contract(c), "run": _ser_run(run), "warnings": cmp["warnings"]}


@router.post("/sizing/assign", dependencies=[perm_dep("weaving.calculators", "edit")])
def assign_sizing(user: WriteUserDep, session: SessionDep, body: AssignSizingIn):
    _require_weaving(session, user)
    c = _contract_or_404(session, user.tenant_id, body.contract_id)
    inputs = _json_safe(body.model_dump(exclude={"contract_id", "override_reason"}))
    result = ycalc.calculate_sizing(**inputs)
    cmp = ycalc.compare_to_contract(result, _contract_snapshot(c), threshold=0.10)
    if not cmp["ok"]:
        reason = (body.override_reason or "").strip()
        if not reason:
            raise HTTPException(
                400,
                detail={
                    "message": "Calculation mismatches contract; provide override_reason",
                    "warnings": cmp["warnings"],
                },
            )
    else:
        reason = (body.override_reason or "").strip() or None

    now = datetime.utcnow()
    c.planned_total_yarn_kg = D(result["total_kg"])
    c.last_calc_at = now
    session.add(c)

    run = WvCalcRun(
        tenant_id=user.tenant_id,
        contract_id=c.id,
        calc_type="sizing",
        inputs=inputs,
        outputs=result,
        override_reason=reason,
        created_by_id=user.id,
        created_at=now,
    )
    session.add(run)
    session.commit()
    session.refresh(c)
    session.refresh(run)
    log_audit(session, user, "assign", "wv_calc_run", run.id, {"contract": c.number, "type": "sizing"})
    return {"contract": _ser_contract(c), "run": _ser_run(run), "warnings": cmp["warnings"]}


@router.get("/history", dependencies=[perm_dep("weaving.calculators", "view")])
def calc_history(user: CurrentUserDep, session: SessionDep, contract_id: int):
    _require_weaving(session, user)
    _contract_or_404(session, user.tenant_id, contract_id)
    rows = session.exec(
        select(WvCalcRun)
        .where(
            WvCalcRun.tenant_id == user.tenant_id,
            WvCalcRun.contract_id == contract_id,
        )
        .order_by(WvCalcRun.id.desc())
    ).all()
    return [_ser_run(r) for r in rows]
