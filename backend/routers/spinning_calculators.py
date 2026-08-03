"""Yarn Spinning calculators — yield, blend, spindle efficiency."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from models import Tenant
from models_spinning import SpCalcRun
from routers.common import CurrentUserDep, SessionDep, WriteUserDep
from routers.modules import _get_enabled
from services import spinning_calc as calc
from services.permissions import perm_dep

router = APIRouter(prefix="/api/spinning/calculators", tags=["spinning-calculators"])


def _require_spinning(session: Session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "spinning" not in _get_enabled(tenant):
        raise HTTPException(403, "The Yarn Spinning module is not installed.")


class YieldCalcIn(BaseModel):
    input_kg: Decimal
    output_kg: Optional[Decimal] = None
    expected_yield_pct: Optional[Decimal] = None
    spin_lot_id: Optional[int] = None


class BlendCalcIn(BaseModel):
    cotton_pct: Decimal
    poly_pct: Decimal
    input_kg: Decimal


class SpindleCalcIn(BaseModel):
    actual_kg: Decimal
    spindle_count: int
    shift_hours: Decimal
    std_kg_per_spindle_hour: Decimal


@router.post("/yield", dependencies=[perm_dep("spinning.calculators", "view")])
def calc_yield(user: CurrentUserDep, session: SessionDep, body: YieldCalcIn):
    _require_spinning(session, user)
    outputs: dict = {
        "input_kg": float(body.input_kg),
        "input_weight": calc.weight_triple(body.input_kg),
    }
    if body.output_kg is not None:
        outputs["output_kg"] = float(body.output_kg)
        outputs["output_weight"] = calc.weight_triple(body.output_kg)
        outputs["yield_pct"] = calc.stage_yield_pct(body.input_kg, body.output_kg)
    if body.expected_yield_pct is not None:
        exp = calc.expected_output_kg(body.input_kg, body.expected_yield_pct)
        outputs["expected_output_kg"] = float(exp)
        outputs["expected_weight"] = calc.weight_triple(exp)

    run = SpCalcRun(
        tenant_id=user.tenant_id, spin_lot_id=body.spin_lot_id,
        calc_type="yield", inputs=body.model_dump(mode="json"),
        outputs=outputs, created_by_id=user.id,
    )
    session.add(run)
    session.commit()
    return outputs


@router.post("/blend", dependencies=[perm_dep("spinning.calculators", "view")])
def calc_blend(user: CurrentUserDep, session: SessionDep, body: BlendCalcIn):
    _require_spinning(session, user)
    total_pct = body.cotton_pct + body.poly_pct
    if total_pct != 100 and total_pct != 0:
        raise HTTPException(400, "Blend percentages should sum to 100")
    cotton_kg = body.input_kg * body.cotton_pct / 100 if total_pct else body.input_kg
    poly_kg = body.input_kg * body.poly_pct / 100 if total_pct else Decimal("0")
    outputs = {
        "cotton_kg": float(cotton_kg),
        "poly_kg": float(poly_kg),
        "cotton_weight": calc.weight_triple(cotton_kg),
        "poly_weight": calc.weight_triple(poly_kg),
    }
    run = SpCalcRun(
        tenant_id=user.tenant_id, calc_type="blend",
        inputs=body.model_dump(mode="json"), outputs=outputs, created_by_id=user.id,
    )
    session.add(run)
    session.commit()
    return outputs


@router.post("/spindle", dependencies=[perm_dep("spinning.calculators", "view")])
def calc_spindle(user: CurrentUserDep, session: SessionDep, body: SpindleCalcIn):
    _require_spinning(session, user)
    eff = calc.spindle_efficiency(
        body.actual_kg, body.spindle_count, body.shift_hours, body.std_kg_per_spindle_hour,
    )
    outputs = {
        "efficiency_pct": eff,
        "actual_kg": float(body.actual_kg),
        "actual_weight": calc.weight_triple(body.actual_kg),
    }
    run = SpCalcRun(
        tenant_id=user.tenant_id, calc_type="spindle",
        inputs=body.model_dump(mode="json"), outputs=outputs, created_by_id=user.id,
    )
    session.add(run)
    session.commit()
    return outputs
