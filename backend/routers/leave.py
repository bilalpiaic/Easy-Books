"""Leave types, balances, and requests (#303)."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import Employee, LeaveBalance, LeaveRequest, LeaveType
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import apply_own_filter, perm_dep

router = APIRouter(prefix="/api/leave", tags=["leave"])


def _days_inclusive(from_date: str, to_date: str) -> float:
    a = date.fromisoformat(from_date)
    b = date.fromisoformat(to_date)
    if b < a:
        raise HTTPException(400, "to_date must be on or after from_date")
    return float((b - a).days + 1)


def _get_or_create_balance(
    session, tenant_id: int, employee_id: int, leave_type: LeaveType, year: int
) -> LeaveBalance:
    row = session.exec(
        select(LeaveBalance).where(
            LeaveBalance.tenant_id == tenant_id,
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type.id,
            LeaveBalance.year == year,
        )
    ).first()
    if row:
        return row
    row = LeaveBalance(
        tenant_id=tenant_id,
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        year=year,
        entitled=float(leave_type.annual_entitlement or 0),
        used=0,
        pending=0,
    )
    session.add(row)
    session.flush()
    return row


# ── Types ─────────────────────────────────────────────────────────────────────

class LeaveTypeIn(BaseModel):
    code: str
    name: str
    is_paid: bool = True
    annual_entitlement: float = 0
    is_active: bool = True


@router.get("/types", dependencies=[perm_dep("leave")])
def list_types(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(LeaveType).where(LeaveType.tenant_id == user.tenant_id).order_by(LeaveType.code)
    ).all()
    return [r.model_dump() for r in rows]


@router.post("/types", status_code=201, dependencies=[perm_dep("leave", "edit")])
def create_type(body: LeaveTypeIn, session: SessionDep, user: WriteUserDep):
    code = body.code.strip().upper()
    existing = session.exec(
        select(LeaveType).where(
            LeaveType.tenant_id == user.tenant_id, LeaveType.code == code
        )
    ).first()
    if existing:
        raise HTTPException(400, f"Leave type {code} already exists")
    row = LeaveType(
        tenant_id=user.tenant_id,
        code=code,
        name=body.name.strip(),
        is_paid=body.is_paid,
        annual_entitlement=body.annual_entitlement,
        is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.model_dump()


@router.post("/types/seed-defaults", dependencies=[perm_dep("leave", "edit")])
def seed_default_types(session: SessionDep, user: WriteUserDep):
    """Idempotent AL / SL / UL pack for new HRM tenants."""
    defaults = [
        ("AL", "Annual Leave", True, 14),
        ("SL", "Sick Leave", True, 10),
        ("UL", "Unpaid Leave", False, 0),
    ]
    created = []
    for code, name, paid, ent in defaults:
        exists = session.exec(
            select(LeaveType).where(
                LeaveType.tenant_id == user.tenant_id, LeaveType.code == code
            )
        ).first()
        if exists:
            continue
        row = LeaveType(
            tenant_id=user.tenant_id,
            code=code,
            name=name,
            is_paid=paid,
            annual_entitlement=ent,
        )
        session.add(row)
        created.append(code)
    session.commit()
    return {"created": created}


# ── Balances ──────────────────────────────────────────────────────────────────

@router.get("/balances", dependencies=[perm_dep("leave")])
def list_balances(
    session: SessionDep,
    user: CurrentUserDep,
    employee_id: Optional[int] = None,
    year: Optional[int] = None,
):
    y = year or date.today().year
    q = select(LeaveBalance).where(
        LeaveBalance.tenant_id == user.tenant_id,
        LeaveBalance.year == y,
    )
    if employee_id:
        q = q.where(LeaveBalance.employee_id == employee_id)
    rows = session.exec(q).all()
    out = []
    for r in rows:
        d = r.model_dump()
        lt = session.get(LeaveType, r.leave_type_id)
        emp = session.get(Employee, r.employee_id)
        d["leave_type_code"] = lt.code if lt else None
        d["leave_type_name"] = lt.name if lt else None
        d["is_paid"] = lt.is_paid if lt else None
        d["employee_name"] = emp.name if emp else None
        d["available"] = float(r.entitled) - float(r.used) - float(r.pending)
        out.append(d)
    return out


# ── Requests ──────────────────────────────────────────────────────────────────

class LeaveRequestIn(BaseModel):
    employee_id: int
    leave_type_id: int
    from_date: str
    to_date: str
    reason: Optional[str] = None


class RejectIn(BaseModel):
    reason: Optional[str] = None


def _serialize_request(session, req: LeaveRequest) -> dict:
    d = req.model_dump()
    emp = session.get(Employee, req.employee_id)
    lt = session.get(LeaveType, req.leave_type_id)
    d["employee_name"] = emp.name if emp else None
    d["employee_code"] = emp.employee_code if emp else None
    d["leave_type_code"] = lt.code if lt else None
    d["leave_type_name"] = lt.name if lt else None
    d["is_paid"] = lt.is_paid if lt else None
    return d


@router.get("/requests", dependencies=[perm_dep("leave")])
def list_requests(
    session: SessionDep,
    user: CurrentUserDep,
    status: Optional[str] = None,
    employee_id: Optional[int] = None,
):
    q = select(LeaveRequest).where(LeaveRequest.tenant_id == user.tenant_id)
    q = apply_own_filter(q, LeaveRequest, user, session)
    if status:
        q = q.where(LeaveRequest.status == status)
    if employee_id:
        q = q.where(LeaveRequest.employee_id == employee_id)
    rows = session.exec(q.order_by(LeaveRequest.id.desc())).all()  # type: ignore
    return [_serialize_request(session, r) for r in rows]


@router.post("/requests", status_code=201, dependencies=[perm_dep("leave", "edit")])
def create_request(body: LeaveRequestIn, session: SessionDep, user: WriteUserDep):
    emp = session.get(Employee, body.employee_id)
    if not emp or emp.tenant_id != user.tenant_id:
        raise HTTPException(400, "Invalid employee")
    lt = session.get(LeaveType, body.leave_type_id)
    if not lt or lt.tenant_id != user.tenant_id or not lt.is_active:
        raise HTTPException(400, "Invalid leave type")
    days = _days_inclusive(body.from_date, body.to_date)
    year = int(body.from_date[:4])
    bal = _get_or_create_balance(session, user.tenant_id, emp.id, lt, year)
    available = float(bal.entitled) - float(bal.used) - float(bal.pending)
    if lt.annual_entitlement and days > available + 1e-9:
        raise HTTPException(
            400,
            f"Insufficient leave balance: available {available}, requested {days}",
        )
    req = LeaveRequest(
        tenant_id=user.tenant_id,
        employee_id=emp.id,
        leave_type_id=lt.id,
        from_date=body.from_date,
        to_date=body.to_date,
        days=days,
        status="pending",
        reason=body.reason,
        created_by_id=user.id,
    )
    session.add(req)
    bal.pending = float(bal.pending) + days
    session.add(bal)
    session.flush()
    log_audit(session, user, "CREATE", "leave_request", req.id, {"days": days})
    session.commit()
    session.refresh(req)
    return _serialize_request(session, req)


@router.post("/requests/{req_id}/approve", dependencies=[perm_dep("leave", "edit")])
def approve_request(req_id: int, session: SessionDep, user: WriteUserDep):
    req = session.get(LeaveRequest, req_id)
    if not req or req.tenant_id != user.tenant_id:
        raise HTTPException(404, "Leave request not found")
    if req.status != "pending":
        raise HTTPException(400, f"Cannot approve status={req.status}")
    if req.created_by_id == user.id:
        raise HTTPException(400, "Cannot self-approve leave request")
    year = int(req.from_date[:4])
    lt = session.get(LeaveType, req.leave_type_id)
    bal = _get_or_create_balance(session, user.tenant_id, req.employee_id, lt, year)
    bal.pending = max(0.0, float(bal.pending) - float(req.days))
    bal.used = float(bal.used) + float(req.days)
    session.add(bal)
    req.status = "approved"
    req.approved_by_id = user.id
    req.approved_at = datetime.utcnow()
    session.add(req)
    log_audit(session, user, "APPROVE", "leave_request", req.id, {})
    session.commit()
    session.refresh(req)
    return _serialize_request(session, req)


@router.post("/requests/{req_id}/reject", dependencies=[perm_dep("leave", "edit")])
def reject_request(
    req_id: int, body: RejectIn, session: SessionDep, user: WriteUserDep
):
    req = session.get(LeaveRequest, req_id)
    if not req or req.tenant_id != user.tenant_id:
        raise HTTPException(404, "Leave request not found")
    if req.status != "pending":
        raise HTTPException(400, f"Cannot reject status={req.status}")
    year = int(req.from_date[:4])
    lt = session.get(LeaveType, req.leave_type_id)
    bal = _get_or_create_balance(session, user.tenant_id, req.employee_id, lt, year)
    bal.pending = max(0.0, float(bal.pending) - float(req.days))
    session.add(bal)
    req.status = "rejected"
    req.approved_by_id = user.id
    req.approved_at = datetime.utcnow()
    req.reject_reason = body.reason
    session.add(req)
    log_audit(session, user, "REJECT", "leave_request", req.id, {})
    session.commit()
    session.refresh(req)
    return _serialize_request(session, req)


def unpaid_leave_days(
    session, tenant_id: int, employee_id: int, period_start: str, period_end: str
) -> float:
    """Sum approved unpaid leave days overlapping [period_start, period_end]."""
    rows = session.exec(
        select(LeaveRequest, LeaveType)
        .join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id)  # type: ignore[arg-type]
        .where(
            LeaveRequest.tenant_id == tenant_id,
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveType.is_paid == False,  # noqa: E712
            LeaveRequest.from_date <= period_end,
            LeaveRequest.to_date >= period_start,
        )
    ).all()
    total = 0.0
    ps = date.fromisoformat(period_start)
    pe = date.fromisoformat(period_end)
    for req, _lt in rows:
        a = max(date.fromisoformat(req.from_date), ps)
        b = min(date.fromisoformat(req.to_date), pe)
        if b >= a:
            total += float((b - a).days + 1)
    return total
