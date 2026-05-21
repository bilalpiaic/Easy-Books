"""RatePlan catalogue + customer assignment.

A RatePlan captures a value-addition pricing model:
  per_unit_rate                — flat charge per processed unit
  includes_materials_at_cost   — whether to also bill consumed materials
  overhead_pct / margin_pct    — uplifts on top

Customers are assigned one or more plans; the active assignment is what
production-order billing reaches for. Plans are versioned so historical
invoices reproduce exactly.
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Customer, CustomerRatePlan, Product, RatePlan
from services.money import D

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/rate-plans", tags=["rate-plans"])


class RatePlanCreate(BaseModel):
    code: str
    name: str
    output_product_id: Optional[int] = None
    per_unit_rate: Decimal
    includes_materials_at_cost: bool = True
    overhead_pct: Decimal = Decimal("0")
    margin_pct: Decimal = Decimal("0")
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    notes: Optional[str] = None


class RatePlanUpdate(BaseModel):
    name: Optional[str] = None
    per_unit_rate: Optional[Decimal] = None
    includes_materials_at_cost: Optional[bool] = None
    overhead_pct: Optional[Decimal] = None
    margin_pct: Optional[Decimal] = None
    is_active: Optional[bool] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_rate_plans(
    session: SessionDep, user: CurrentUserDep,
    active_only: bool = False,
    skip: int = 0, limit: int = 100,
):
    q = select(RatePlan).where(RatePlan.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(RatePlan.is_active == True)  # noqa: E712
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(RatePlan.code, RatePlan.version.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


@router.post("", status_code=201)
def create_rate_plan(
    session: SessionDep, user: WriteUserDep, body: RatePlanCreate
):
    if D(body.per_unit_rate) < 0 or D(body.overhead_pct) < 0 or D(body.margin_pct) < 0:
        raise HTTPException(400, "rates must be >= 0")
    if body.output_product_id is not None:
        p = session.get(Product, body.output_product_id)
        if not p or p.tenant_id != user.tenant_id:
            raise HTTPException(400, "output_product_id not found for tenant")

    # Resolve next version for this code: max + 1
    existing_max = session.exec(
        select(func.max(RatePlan.version)).where(
            RatePlan.tenant_id == user.tenant_id,
            RatePlan.code == body.code,
        )
    ).one()
    new_version = (existing_max or 0) + 1

    # Deactivate prior versions of the same code
    prior = session.exec(
        select(RatePlan).where(
            RatePlan.tenant_id == user.tenant_id,
            RatePlan.code == body.code,
            RatePlan.is_active == True,  # noqa: E712
        )
    ).all()
    for p in prior:
        p.is_active = False
        session.add(p)

    plan = RatePlan(
        tenant_id=user.tenant_id,
        code=body.code,
        name=body.name,
        output_product_id=body.output_product_id,
        per_unit_rate=D(body.per_unit_rate),
        includes_materials_at_cost=body.includes_materials_at_cost,
        overhead_pct=D(body.overhead_pct),
        margin_pct=D(body.margin_pct),
        version=new_version,
        is_active=True,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        notes=body.notes,
    )
    session.add(plan)
    session.flush()
    log_audit(
        session, user, "CREATE", "rate_plan", plan.id,
        {"code": plan.code, "version": new_version},
    )
    session.commit()
    session.refresh(plan)
    return plan


@router.put("/{plan_id}")
def update_rate_plan(
    session: SessionDep, user: WriteUserDep, plan_id: int, body: RatePlanUpdate
):
    plan = session.exec(
        select(RatePlan).where(
            RatePlan.id == plan_id, RatePlan.tenant_id == user.tenant_id
        )
    ).first()
    if not plan:
        raise HTTPException(404, "Rate plan not found")
    # Bulk-set the simple fields. Caller is responsible for the semantic of
    # editing an in-use plan (we don't lock plans once they're referenced —
    # versioning is the right answer for that).
    for k, v in body.model_dump(exclude_none=True).items():
        if k in {"per_unit_rate", "overhead_pct", "margin_pct"}:
            if D(v) < 0:
                raise HTTPException(400, f"{k} must be >= 0")
            setattr(plan, k, D(v))
        else:
            setattr(plan, k, v)
    session.add(plan)
    log_audit(session, user, "UPDATE", "rate_plan", plan.id, {"code": plan.code})
    session.commit()
    session.refresh(plan)
    return plan


# ── Customer ↔ plan assignment ──────────────────────────────────────────────


class AssignPlan(BaseModel):
    customer_id: int
    rate_plan_id: int


@router.post("/assign", status_code=201)
def assign_to_customer(
    session: SessionDep, user: WriteUserDep, body: AssignPlan
):
    cust = session.get(Customer, body.customer_id)
    if not cust or cust.tenant_id != user.tenant_id:
        raise HTTPException(404, "Customer not found")
    plan = session.get(RatePlan, body.rate_plan_id)
    if not plan or plan.tenant_id != user.tenant_id:
        raise HTTPException(404, "Rate plan not found")

    # Deactivate prior assignments for this customer
    prior = session.exec(
        select(CustomerRatePlan).where(
            CustomerRatePlan.tenant_id == user.tenant_id,
            CustomerRatePlan.customer_id == body.customer_id,
            CustomerRatePlan.is_active == True,  # noqa: E712
        )
    ).all()
    for p in prior:
        p.is_active = False
        session.add(p)

    # Upsert: if (customer, plan) already exists, reactivate it
    existing = session.exec(
        select(CustomerRatePlan).where(
            CustomerRatePlan.tenant_id == user.tenant_id,
            CustomerRatePlan.customer_id == body.customer_id,
            CustomerRatePlan.rate_plan_id == body.rate_plan_id,
        )
    ).first()
    if existing:
        existing.is_active = True
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    assignment = CustomerRatePlan(
        tenant_id=user.tenant_id,
        customer_id=body.customer_id,
        rate_plan_id=body.rate_plan_id,
        is_active=True,
    )
    session.add(assignment)
    session.flush()
    log_audit(
        session, user, "ASSIGN", "rate_plan", plan.id,
        {"customer_id": body.customer_id, "rate_plan_code": plan.code},
    )
    session.commit()
    session.refresh(assignment)
    return assignment


@router.get("/customer/{customer_id}")
def list_customer_plans(
    session: SessionDep, user: CurrentUserDep, customer_id: int
):
    """All rate plans ever assigned to this customer, active flag included."""
    cust = session.get(Customer, customer_id)
    if not cust or cust.tenant_id != user.tenant_id:
        raise HTTPException(404, "Customer not found")
    rows = session.exec(
        select(CustomerRatePlan, RatePlan)
        .join(RatePlan, RatePlan.id == CustomerRatePlan.rate_plan_id)
        .where(
            CustomerRatePlan.tenant_id == user.tenant_id,
            CustomerRatePlan.customer_id == customer_id,
        )
        .order_by(CustomerRatePlan.assigned_at.desc())
    ).all()
    return [
        {
            "assignment_id": a.id,
            "is_active": a.is_active,
            "assigned_at": a.assigned_at.isoformat(),
            "plan": p.model_dump(),
        }
        for a, p in rows
    ]
