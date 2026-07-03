"""Purchase Demands — quantity-only requisitions (#137 Phase 1). Memo documents, no GL."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import PurchaseDemand, PurchaseDemandLine
from routers.common import AdminUserDep, SessionDep, WriteUserDep, log_audit, next_number
from services.money import D
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(
    prefix="/api/purchase-demands", tags=["purchase-demands"],
    dependencies=[perm_dep("purchase.demand")],
)


class DemandLineIn(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None


class DemandIn(BaseModel):
    demand_date: str
    required_by: Optional[str] = None
    analytic_account_id: Optional[int] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None
    lines: List[DemandLineIn] = []


def _serialize(session, d: PurchaseDemand) -> dict:
    lines = session.exec(
        select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == d.id)
    ).all()
    out = d.model_dump()
    out["lines"] = [l.model_dump() for l in lines]
    return out


def _get_demand(session, user, demand_id: int) -> PurchaseDemand:
    d = session.exec(
        select(PurchaseDemand).where(
            PurchaseDemand.id == demand_id, PurchaseDemand.tenant_id == user.tenant_id
        )
    ).first()
    if not d:
        raise HTTPException(404, "Demand not found")
    return d


@router.get("")
def list_demands(session: SessionDep, user: WriteUserDep, status: Optional[str] = None):
    q = select(PurchaseDemand).where(PurchaseDemand.tenant_id == user.tenant_id)
    if status:
        q = q.where(PurchaseDemand.status == status)
    q = apply_own_filter(q, PurchaseDemand, user, session)
    rows = session.exec(q.order_by(PurchaseDemand.id.desc())).all()
    return [_serialize(session, d) for d in rows]


@router.get("/{demand_id}")
def get_demand(session: SessionDep, user: WriteUserDep, demand_id: int):
    return _serialize(session, _get_demand(session, user, demand_id))


@router.post("", status_code=201)
def create_demand(session: SessionDep, user: WriteUserDep, body: DemandIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    number = next_number(
        session, user.tenant_id, "purchase_demand", "PD", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    d = PurchaseDemand(
        tenant_id=user.tenant_id, number=number, demand_date=body.demand_date,
        required_by=body.required_by, analytic_account_id=body.analytic_account_id,
        purpose=body.purpose, notes=body.notes, status="draft", created_by_id=user.id,
    )
    session.add(d)
    session.flush()
    for l in body.lines:
        session.add(PurchaseDemandLine(
            demand_id=d.id, product_id=l.product_id,
            description=l.description, qty=D(l.qty), unit=l.unit,
        ))
    log_audit(session, user, "CREATE", "purchase_demand", d.id, {"number": number})
    session.commit()
    return _serialize(session, d)


@router.put("/{demand_id}")
def update_demand(session: SessionDep, user: WriteUserDep, demand_id: int, body: DemandIn):
    d = _get_demand(session, user, demand_id)
    if d.status != "draft":
        raise HTTPException(400, f"Cannot edit a demand with status '{d.status}'")
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    d.demand_date = body.demand_date
    d.required_by = body.required_by
    d.analytic_account_id = body.analytic_account_id
    d.purpose = body.purpose
    d.notes = body.notes
    for old in session.exec(
        select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == d.id)
    ).all():
        session.delete(old)
    for l in body.lines:
        session.add(PurchaseDemandLine(
            demand_id=d.id, product_id=l.product_id,
            description=l.description, qty=D(l.qty), unit=l.unit,
        ))
    session.add(d)
    log_audit(session, user, "UPDATE", "purchase_demand", d.id, {"number": d.number})
    session.commit()
    return _serialize(session, d)


@router.patch("/{demand_id}/approve")
def approve_demand(session: SessionDep, user: AdminUserDep, demand_id: int):
    d = _get_demand(session, user, demand_id)
    if d.status != "draft":
        raise HTTPException(400, f"Cannot approve a demand with status '{d.status}'")
    if d.created_by_id == user.id:
        raise HTTPException(400, "A demand cannot be approved by its creator")
    d.status = "approved"
    d.approved_by_id = user.id
    d.approved_at = datetime.utcnow()
    session.add(d)
    log_audit(session, user, "UPDATE", "purchase_demand", d.id, {"action": "approved"})
    session.commit()
    return {"success": True, "status": "approved"}


@router.patch("/{demand_id}/cancel")
def cancel_demand(session: SessionDep, user: AdminUserDep, demand_id: int):
    d = _get_demand(session, user, demand_id)
    if d.status not in ("draft", "approved"):
        raise HTTPException(400, f"Cannot cancel a demand with status '{d.status}'")
    d.status = "cancelled"
    session.add(d)
    log_audit(session, user, "UPDATE", "purchase_demand", d.id, {"action": "cancelled"})
    session.commit()
    return {"success": True, "status": "cancelled"}


@router.patch("/{demand_id}/close")
def close_demand(session: SessionDep, user: AdminUserDep, demand_id: int):
    d = _get_demand(session, user, demand_id)
    if d.status != "approved":
        raise HTTPException(400, "Only approved demands can be closed")
    d.status = "closed"
    session.add(d)
    log_audit(session, user, "UPDATE", "purchase_demand", d.id, {"action": "closed"})
    session.commit()
    return {"success": True, "status": "closed"}
