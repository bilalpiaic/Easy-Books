"""Point of Sale API (#304)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

import json

from models import Tenant
from models_pos import PosRegister, PosSale, PosShift
from services.permissions import perm_dep
from services.pos import (
    complete_pos_sale,
    expected_cash_for_shift,
    resolve_default_cash_account,
)
from services.money import money
from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/pos", tags=["pos"])


def _dump(row) -> dict:
    """model_dump + cast Numeric→float (SQLAlchemy returns Decimal for Numeric cols)."""
    d = row.model_dump()
    for k, v in list(d.items()):
        if isinstance(v, Decimal):
            d[k] = float(v)
    return d


def _require_pos(session, user):
    tenant = session.get(Tenant, user.tenant_id)
    try:
        enabled = set(json.loads(tenant.enabled_modules or "[]")) if tenant else set()
    except Exception:
        enabled = set()
    if "pos" not in enabled:
        raise HTTPException(403, "Point of Sale module is not installed")


# ── Registers ────────────────────────────────────────────────────────────────

class RegisterIn(BaseModel):
    name: str
    code: str = "REG1"
    cash_account_id: Optional[int] = None
    bank_account_id: Optional[int] = None
    default_customer_id: Optional[int] = None
    is_active: bool = True


@router.get("/registers", dependencies=[perm_dep("pos.register")])
def list_registers(session: SessionDep, user: CurrentUserDep):
    _require_pos(session, user)
    rows = session.exec(
        select(PosRegister).where(PosRegister.tenant_id == user.tenant_id)
        .order_by(PosRegister.id)  # type: ignore
    ).all()
    return [_dump(r) for r in rows]


@router.post("/registers", status_code=201, dependencies=[perm_dep("pos.register", "edit")])
def create_register(body: RegisterIn, session: SessionDep, user: WriteUserDep):
    _require_pos(session, user)
    cash_id = body.cash_account_id or resolve_default_cash_account(session, user.tenant_id)
    row = PosRegister(
        tenant_id=user.tenant_id,
        name=body.name.strip(),
        code=(body.code or "REG1").strip(),
        cash_account_id=cash_id,
        bank_account_id=body.bank_account_id,
        default_customer_id=body.default_customer_id,
        is_active=body.is_active,
    )
    session.add(row)
    session.flush()
    log_audit(session, user, "CREATE", "pos_register", row.id, {"name": row.name})
    session.commit()
    session.refresh(row)
    return _dump(row)


# ── Shifts ────────────────────────────────────────────────────────────────────

class OpenShiftIn(BaseModel):
    register_id: int
    opening_float: Decimal = Decimal("0")


class CloseShiftIn(BaseModel):
    closing_count: Decimal
    notes: Optional[str] = None


@router.get("/shifts", dependencies=[perm_dep("pos.shift")])
def list_shifts(
    session: SessionDep,
    user: CurrentUserDep,
    status: Optional[str] = None,
    limit: int = 50,
):
    _require_pos(session, user)
    q = select(PosShift).where(PosShift.tenant_id == user.tenant_id)
    if status:
        q = q.where(PosShift.status == status)
    rows = session.exec(q.order_by(PosShift.id.desc()).limit(limit)).all()  # type: ignore
    return [_dump(r) for r in rows]


@router.post("/shifts/open", status_code=201, dependencies=[perm_dep("pos.shift", "edit")])
def open_shift(body: OpenShiftIn, session: SessionDep, user: WriteUserDep):
    _require_pos(session, user)
    reg = session.get(PosRegister, body.register_id)
    if not reg or reg.tenant_id != user.tenant_id or not reg.is_active:
        raise HTTPException(400, "Invalid register")
    existing = session.exec(
        select(PosShift).where(
            PosShift.tenant_id == user.tenant_id,
            PosShift.register_id == reg.id,
            PosShift.status == "open",
        )
    ).first()
    if existing:
        raise HTTPException(400, f"Register already has open shift #{existing.id}")
    shift = PosShift(
        tenant_id=user.tenant_id,
        register_id=reg.id,
        opened_by_id=user.id,
        opening_float=float(money(body.opening_float)),
        status="open",
    )
    session.add(shift)
    session.commit()
    session.refresh(shift)
    return _dump(shift)


@router.get("/shifts/{shift_id}", dependencies=[perm_dep("pos.shift")])
def get_shift(shift_id: int, session: SessionDep, user: CurrentUserDep):
    _require_pos(session, user)
    shift = session.get(PosShift, shift_id)
    if not shift or shift.tenant_id != user.tenant_id:
        raise HTTPException(404, "Shift not found")
    sales = session.exec(
        select(PosSale).where(
            PosSale.shift_id == shift.id,
            PosSale.tenant_id == user.tenant_id,
        )
    ).all()
    expected = expected_cash_for_shift(session, shift)
    return {
        **_dump(shift),
        "sale_count": len(sales),
        "expected_cash_live": float(expected),
        "sales": [_dump(s) for s in sales],
    }


@router.post("/shifts/{shift_id}/close", dependencies=[perm_dep("pos.shift", "edit")])
def close_shift(
    shift_id: int, body: CloseShiftIn, session: SessionDep, user: WriteUserDep
):
    _require_pos(session, user)
    shift = session.get(PosShift, shift_id)
    if not shift or shift.tenant_id != user.tenant_id:
        raise HTTPException(404, "Shift not found")
    if shift.status != "open":
        raise HTTPException(400, "Shift already closed")
    expected = expected_cash_for_shift(session, shift)
    counted = money(body.closing_count)
    variance = money(counted - expected)
    shift.closing_count = float(counted)
    shift.expected_cash = float(expected)
    shift.variance = float(variance)
    shift.closed_by_id = user.id
    shift.closed_at = datetime.utcnow()
    shift.status = "closed"
    shift.notes = body.notes
    session.add(shift)
    session.commit()
    session.refresh(shift)
    return _dump(shift)


# ── Sales ─────────────────────────────────────────────────────────────────────

class SaleLineIn(BaseModel):
    product_id: Optional[int] = None
    description: Optional[str] = None
    qty: Decimal = Decimal("1")
    rate: Optional[Decimal] = None
    unit: Optional[str] = None
    discount_pct: Decimal = Decimal("0")
    tax_code_id: Optional[int] = None
    tax_inclusive: bool = False


class SaleIn(BaseModel):
    shift_id: int
    lines: List[SaleLineIn]
    tender: str = "cash"
    cash_tendered: Optional[Decimal] = None
    payment_mode: Optional[int] = None
    customer_id: Optional[int] = None
    buyer_ntn: Optional[str] = None
    buyer_cnic: Optional[str] = None
    gst_rate: Optional[Decimal] = None


@router.post("/sales", status_code=201, dependencies=[perm_dep("pos.sale", "edit")])
def post_sale(
    body: SaleIn,
    session: SessionDep,
    user: WriteUserDep,
    background_tasks: BackgroundTasks,
):
    _require_pos(session, user)
    lines = [ln.model_dump() for ln in body.lines]
    # Normalize optional rate → omit zeros so service fills from product
    for ln in lines:
        if ln.get("rate") is None:
            ln["rate"] = 0
    result = complete_pos_sale(
        session,
        user,
        shift_id=body.shift_id,
        lines=lines,
        tender=body.tender,
        cash_tendered=body.cash_tendered,
        payment_mode=body.payment_mode,
        customer_id=body.customer_id,
        buyer_ntn=body.buyer_ntn,
        buyer_cnic=body.buyer_cnic,
        gst_rate=body.gst_rate,
        background_tasks=background_tasks,
    )
    log_audit(session, user, "CREATE", "pos_sale", result["id"], {
        "invoice_id": result["invoice_id"], "total": str(result["total"]),
    })
    session.commit()
    return result
