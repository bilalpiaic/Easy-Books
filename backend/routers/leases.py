"""IFRS 16 leases API — contract master, activate, period post, maturity (#256)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import LeaseContract, LeaseScheduleLine, Settings
from routers.common import SessionDep, WriteUserDep, CurrentUserDep, log_audit
from services.leases import (
    LeaseError,
    activate_lease,
    allocate_number,
    maturity_analysis,
    post_period,
    preview_lease,
    terminate_lease,
)
from services.money import D, money
from services.permissions import perm_dep

router = APIRouter(prefix="/api/leases", tags=["leases"])


def _enabled(session, tenant_id: int) -> bool:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == "leases_enabled")
    ).first()
    val = (row.value if row else "true") or "true"
    return val.lower() not in ("0", "false", "no", "off")


def _require_enabled(session, tenant_id: int):
    if not _enabled(session, tenant_id):
        raise HTTPException(400, "Leases are disabled in Settings (leases_enabled)")


def _http(exc: LeaseError) -> HTTPException:
    return HTTPException(exc.status_code, exc.message)


def _lease_out(lease: LeaseContract) -> dict:
    return {
        "id": lease.id,
        "number": lease.number,
        "name": lease.name,
        "lessor": lease.lessor,
        "commencement_date": lease.commencement_date,
        "term_months": lease.term_months,
        "payment_amount": float(lease.payment_amount or 0),
        "annual_discount_rate": float(lease.annual_discount_rate or 0),
        "payment_timing": lease.payment_timing,
        "initial_direct_costs": float(lease.initial_direct_costs or 0),
        "present_value": float(lease.present_value or 0),
        "rou_cost": float(lease.rou_cost or 0),
        "liability_opening": float(lease.liability_opening or 0),
        "accumulated_depreciation": float(lease.accumulated_depreciation or 0),
        "liability_carrying": float(lease.liability_carrying or 0),
        "rou_nbv": float(D(lease.rou_cost or 0) - D(lease.accumulated_depreciation or 0)),
        "status": lease.status,
        "rou_account_id": lease.rou_account_id,
        "accum_depr_account_id": lease.accum_depr_account_id,
        "depr_expense_account_id": lease.depr_expense_account_id,
        "liability_account_id": lease.liability_account_id,
        "interest_expense_account_id": lease.interest_expense_account_id,
        "payment_account_id": lease.payment_account_id,
        "initial_transaction_id": lease.initial_transaction_id,
        "terminated_at": lease.terminated_at,
        "notes": lease.notes,
        "created_at": lease.created_at,
    }


def _line_out(line: LeaseScheduleLine) -> dict:
    return {
        "id": line.id,
        "lease_id": line.lease_id,
        "period_index": line.period_index,
        "period_date": line.period_date,
        "opening_liability": float(line.opening_liability or 0),
        "interest": float(line.interest or 0),
        "payment": float(line.payment or 0),
        "principal": float(line.principal or 0),
        "closing_liability": float(line.closing_liability or 0),
        "depreciation": float(line.depreciation or 0),
        "status": line.status,
        "interest_transaction_id": line.interest_transaction_id,
        "payment_transaction_id": line.payment_transaction_id,
        "depr_transaction_id": line.depr_transaction_id,
        "posted_at": line.posted_at,
    }


def _get_lease(session, user, lease_id: int) -> LeaseContract:
    lease = session.exec(
        select(LeaseContract).where(
            LeaseContract.id == lease_id,
            LeaseContract.tenant_id == user.tenant_id,
        )
    ).first()
    if not lease:
        raise HTTPException(404, "Lease not found")
    return lease


class LeaseCreate(BaseModel):
    name: str
    lessor: Optional[str] = None
    commencement_date: str
    term_months: int
    payment_amount: float
    annual_discount_rate: float
    payment_timing: str = "arrears"
    initial_direct_costs: float = 0
    payment_account_id: Optional[int] = None
    notes: Optional[str] = None
    activate: bool = False


class LeasePreviewIn(BaseModel):
    commencement_date: str = "2026-01-01"
    term_months: int
    payment_amount: float
    annual_discount_rate: float
    payment_timing: str = "arrears"
    initial_direct_costs: float = 0


class TerminateIn(BaseModel):
    termination_date: str


@router.get("", dependencies=[perm_dep("leases", "view")])
def list_leases(
    session: SessionDep, user: CurrentUserDep,
    status: Optional[str] = None, skip: int = 0, limit: int = 50,
):
    _require_enabled(session, user.tenant_id)
    q = select(LeaseContract).where(LeaseContract.tenant_id == user.tenant_id)
    if status:
        q = q.where(LeaseContract.status == status)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(LeaseContract.id.desc()).offset(skip).limit(limit)  # type: ignore
    ).all()
    return {"total": total, "items": [_lease_out(x) for x in items]}


@router.post("/preview", dependencies=[perm_dep("leases", "view")])
def preview(body: LeasePreviewIn, session: SessionDep, user: CurrentUserDep):
    _require_enabled(session, user.tenant_id)
    return preview_lease(
        payment=money(body.payment_amount),
        term_months=body.term_months,
        annual_pct=money(body.annual_discount_rate),
        timing=body.payment_timing or "arrears",
        initial_direct_costs=money(body.initial_direct_costs),
        commencement=body.commencement_date,
    )


@router.get("/maturity", dependencies=[perm_dep("leases", "view")])
def maturity(session: SessionDep, user: CurrentUserDep, as_of: Optional[str] = None):
    _require_enabled(session, user.tenant_id)
    return maturity_analysis(session, user.tenant_id, as_of)


@router.post("", status_code=201, dependencies=[perm_dep("leases", "edit")])
def create_lease(body: LeaseCreate, session: SessionDep, user: WriteUserDep):
    _require_enabled(session, user.tenant_id)
    timing = (body.payment_timing or "arrears").lower()
    if timing not in ("arrears", "advance"):
        raise HTTPException(400, "payment_timing must be arrears or advance")
    if body.term_months <= 0:
        raise HTTPException(400, "term_months must be > 0")
    lease = LeaseContract(
        tenant_id=user.tenant_id,
        number=allocate_number(session, user.tenant_id),
        name=body.name,
        lessor=body.lessor,
        commencement_date=body.commencement_date,
        term_months=body.term_months,
        payment_amount=money(body.payment_amount),
        annual_discount_rate=money(body.annual_discount_rate),
        payment_timing=timing,
        initial_direct_costs=money(body.initial_direct_costs),
        payment_account_id=body.payment_account_id,
        notes=body.notes,
        status="draft",
        created_by_id=user.id,
    )
    session.add(lease)
    session.commit()
    session.refresh(lease)
    log_audit(session, user, "CREATE", "lease", lease.id, {"number": lease.number})

    if body.activate:
        try:
            lease = activate_lease(
                session, user, lease, payment_account_id=body.payment_account_id,
            )
        except LeaseError as e:
            raise _http(e)
        log_audit(session, user, "ACTIVATE", "lease", lease.id, {"number": lease.number})

    return _lease_out(lease)


@router.get("/{lease_id}", dependencies=[perm_dep("leases", "view")])
def get_lease(lease_id: int, session: SessionDep, user: CurrentUserDep):
    _require_enabled(session, user.tenant_id)
    lease = _get_lease(session, user, lease_id)
    lines = session.exec(
        select(LeaseScheduleLine)
        .where(LeaseScheduleLine.lease_id == lease_id)
        .order_by(LeaseScheduleLine.period_index)
    ).all()
    return {**_lease_out(lease), "schedule": [_line_out(x) for x in lines]}


@router.post("/{lease_id}/activate", dependencies=[perm_dep("leases", "edit")])
def activate(lease_id: int, session: SessionDep, user: WriteUserDep):
    _require_enabled(session, user.tenant_id)
    lease = _get_lease(session, user, lease_id)
    try:
        lease = activate_lease(session, user, lease)
    except LeaseError as e:
        raise _http(e)
    log_audit(session, user, "ACTIVATE", "lease", lease.id, {"number": lease.number})
    return _lease_out(lease)


@router.post("/{lease_id}/periods/{period_index}/post", dependencies=[perm_dep("leases", "edit")])
def post_schedule_period(
    lease_id: int, period_index: int, session: SessionDep, user: WriteUserDep,
):
    _require_enabled(session, user.tenant_id)
    lease = _get_lease(session, user, lease_id)
    line = session.exec(
        select(LeaseScheduleLine).where(
            LeaseScheduleLine.lease_id == lease_id,
            LeaseScheduleLine.period_index == period_index,
            LeaseScheduleLine.tenant_id == user.tenant_id,
        )
    ).first()
    if not line:
        raise HTTPException(404, "Schedule period not found")
    try:
        line = post_period(session, user, lease, line)
    except LeaseError as e:
        raise _http(e)
    log_audit(session, user, "POST_PERIOD", "lease", lease.id, {
        "period": period_index, "date": line.period_date,
    })
    return _line_out(line)


@router.post("/{lease_id}/terminate", dependencies=[perm_dep("leases", "edit")])
def terminate(lease_id: int, body: TerminateIn, session: SessionDep, user: WriteUserDep):
    _require_enabled(session, user.tenant_id)
    lease = _get_lease(session, user, lease_id)
    try:
        lease = terminate_lease(session, user, lease, termination_date=body.termination_date)
    except LeaseError as e:
        raise _http(e)
    log_audit(session, user, "TERMINATE", "lease", lease.id, {
        "date": body.termination_date,
    })
    return _lease_out(lease)
