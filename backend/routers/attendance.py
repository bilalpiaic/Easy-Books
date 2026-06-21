"""Attendance Register — single-record CRUD, bulk entry, monthly summary, biometric import stub."""
from __future__ import annotations

import calendar
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from models import AttendanceRecord, Employee
from routers.common import CurrentUserDep, SessionDep
from services.permissions import perm_dep

router = APIRouter(
    prefix="/api/attendance",
    tags=["attendance"],
    dependencies=[perm_dep("attendance")],
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class AttendanceCreate(BaseModel):
    employee_id: int
    date: str
    time_in: Optional[str] = None
    time_out: Optional[str] = None
    status: str = "present"
    notes: Optional[str] = None


class AttendanceUpdate(BaseModel):
    time_in: Optional[str] = None
    time_out: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class BulkAttendanceItem(BaseModel):
    employee_id: int
    date: str
    time_in: Optional[str] = None
    time_out: Optional[str] = None
    status: str = "present"
    notes: Optional[str] = None


class BulkAttendanceBody(BaseModel):
    records: List[BulkAttendanceItem]


class BiometricImportItem(BaseModel):
    employee_code: str
    date: str
    time_in: Optional[str] = None
    time_out: Optional[str] = None
    raw_data: Optional[str] = None


class BiometricImportBody(BaseModel):
    records: List[BiometricImportItem]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_hours(time_in: str | None, time_out: str | None) -> float | None:
    if not time_in or not time_out:
        return None
    try:
        ih, im = map(int, time_in.split(":"))
        oh, om = map(int, time_out.split(":"))
        mins = (oh * 60 + om) - (ih * 60 + im)
        return round(max(0.0, mins / 60.0), 2)
    except Exception:
        return None


def _serialize(rec: AttendanceRecord, emp_name: str) -> dict:
    return {
        "id": rec.id,
        "tenant_id": rec.tenant_id,
        "employee_id": rec.employee_id,
        "employee_name": emp_name,
        "date": rec.date,
        "time_in": rec.time_in,
        "time_out": rec.time_out,
        "hours_worked": rec.hours_worked,
        "status": rec.status,
        "notes": rec.notes,
        "source": rec.source,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "created_by_id": rec.created_by_id,
    }


def _get_emp_name(session: Session, employee_id: int, tenant_id: int) -> str:
    emp = session.get(Employee, employee_id)
    if emp and emp.tenant_id == tenant_id:
        return emp.name
    return f"#{employee_id}"


# ── List ───────────────────────────────────────────────────────────────────────

@router.get("")
def list_attendance(
    user: CurrentUserDep,
    session: SessionDep,
    employee_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
):
    q = select(AttendanceRecord).where(AttendanceRecord.tenant_id == user.tenant_id)
    if employee_id is not None:
        q = q.where(AttendanceRecord.employee_id == employee_id)
    if from_date:
        q = q.where(AttendanceRecord.date >= from_date)
    if to_date:
        q = q.where(AttendanceRecord.date <= to_date)
    if status:
        q = q.where(AttendanceRecord.status == status)
    if source:
        q = q.where(AttendanceRecord.source == source)
    q = q.order_by(AttendanceRecord.date.desc(), AttendanceRecord.employee_id)  # type: ignore[attr-defined]
    records = session.exec(q).all()

    # Pre-load employees to avoid N+1
    emp_map: dict[int, str] = {}
    for rec in records:
        if rec.employee_id not in emp_map:
            emp_map[rec.employee_id] = _get_emp_name(session, rec.employee_id, user.tenant_id)

    return [_serialize(rec, emp_map[rec.employee_id]) for rec in records]


# ── Create ─────────────────────────────────────────────────────────────────────

@router.post("", dependencies=[perm_dep("attendance", "edit")])
def create_attendance(body: AttendanceCreate, user: CurrentUserDep, session: SessionDep):
    # Validate employee belongs to tenant
    emp = session.get(Employee, body.employee_id)
    if not emp or emp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Employee not found")

    # Reject duplicate (tenant, employee, date)
    existing = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.tenant_id == user.tenant_id,
            AttendanceRecord.employee_id == body.employee_id,
            AttendanceRecord.date == body.date,
        )
    ).first()
    if existing:
        raise HTTPException(400, f"Attendance record for employee {body.employee_id} on {body.date} already exists")

    hours = _compute_hours(body.time_in, body.time_out)
    rec = AttendanceRecord(
        tenant_id=user.tenant_id,
        employee_id=body.employee_id,
        date=body.date,
        time_in=body.time_in,
        time_out=body.time_out,
        hours_worked=hours,
        status=body.status,
        notes=body.notes,
        source="manual",
        created_by_id=user.id,
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return {"id": rec.id, "hours_worked": rec.hours_worked}


# ── Get single ────────────────────────────────────────────────────────────────

@router.get("/summary")
def get_summary(
    user: CurrentUserDep,
    session: SessionDep,
    year: int,
    month: int,
):
    """Per-employee totals for a given year/month."""
    from_date = f"{year:04d}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    to_date = f"{year:04d}-{month:02d}-{last_day:02d}"

    records = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.tenant_id == user.tenant_id,
            AttendanceRecord.date >= from_date,
            AttendanceRecord.date <= to_date,
        )
    ).all()

    # Group by employee
    summary: dict[int, dict] = {}
    for rec in records:
        eid = rec.employee_id
        if eid not in summary:
            summary[eid] = {
                "employee_id": eid,
                "name": _get_emp_name(session, eid, user.tenant_id),
                "present": 0,
                "absent": 0,
                "half_day": 0,
                "leave": 0,
                "holiday": 0,
                "off": 0,
                "total_hours": 0.0,
            }
        s = rec.status
        if s in summary[eid]:
            summary[eid][s] += 1
        summary[eid]["total_hours"] = round(
            summary[eid]["total_hours"] + (rec.hours_worked or 0.0), 2
        )

    return list(summary.values())


@router.get("/{record_id}")
def get_attendance(record_id: int, user: CurrentUserDep, session: SessionDep):
    rec = session.get(AttendanceRecord, record_id)
    if not rec or rec.tenant_id != user.tenant_id:
        raise HTTPException(404, "Attendance record not found")
    return _serialize(rec, _get_emp_name(session, rec.employee_id, user.tenant_id))


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{record_id}", dependencies=[perm_dep("attendance", "edit")])
def update_attendance(record_id: int, body: AttendanceUpdate, user: CurrentUserDep, session: SessionDep):
    rec = session.get(AttendanceRecord, record_id)
    if not rec or rec.tenant_id != user.tenant_id:
        raise HTTPException(404, "Attendance record not found")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(rec, k, v)

    # Recompute hours_worked
    rec.hours_worked = _compute_hours(rec.time_in, rec.time_out)

    session.add(rec)
    session.commit()
    return {"ok": True, "hours_worked": rec.hours_worked}


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{record_id}", dependencies=[perm_dep("attendance", "edit")])
def delete_attendance(record_id: int, user: CurrentUserDep, session: SessionDep):
    rec = session.get(AttendanceRecord, record_id)
    if not rec or rec.tenant_id != user.tenant_id:
        raise HTTPException(404, "Attendance record not found")
    if rec.source == "biometric":
        raise HTTPException(400, "Biometric records cannot be deleted manually")
    session.delete(rec)
    session.commit()
    return {"ok": True}


# ── Bulk entry ────────────────────────────────────────────────────────────────

@router.post("/bulk", dependencies=[perm_dep("attendance", "edit")])
def bulk_attendance(body: BulkAttendanceBody, user: CurrentUserDep, session: SessionDep):
    created = 0
    updated = 0
    errors: list[str] = []

    for item in body.records:
        try:
            emp = session.get(Employee, item.employee_id)
            if not emp or emp.tenant_id != user.tenant_id:
                errors.append(f"Employee {item.employee_id} not found")
                continue

            existing = session.exec(
                select(AttendanceRecord).where(
                    AttendanceRecord.tenant_id == user.tenant_id,
                    AttendanceRecord.employee_id == item.employee_id,
                    AttendanceRecord.date == item.date,
                )
            ).first()

            hours = _compute_hours(item.time_in, item.time_out)

            if existing:
                existing.time_in = item.time_in
                existing.time_out = item.time_out
                existing.status = item.status
                existing.notes = item.notes
                existing.hours_worked = hours
                session.add(existing)
                updated += 1
            else:
                rec = AttendanceRecord(
                    tenant_id=user.tenant_id,
                    employee_id=item.employee_id,
                    date=item.date,
                    time_in=item.time_in,
                    time_out=item.time_out,
                    hours_worked=hours,
                    status=item.status,
                    notes=item.notes,
                    source="manual",
                    created_by_id=user.id,
                )
                session.add(rec)
                created += 1
        except Exception as e:
            errors.append(f"Row employee={item.employee_id} date={item.date}: {e}")

    session.commit()
    return {"created": created, "updated": updated, "errors": errors}


# ── Biometric import stub ──────────────────────────────────────────────────────

@router.post("/import/biometric", dependencies=[perm_dep("attendance", "edit")])
def import_biometric(body: BiometricImportBody, user: CurrentUserDep, session: SessionDep):
    """Accepts biometric device export data. Matches employee_code to Employee table.
    Upserts records with source='biometric'. Stores raw_data as JSON string.
    Device connection (ZKTeco TCP/IP etc.) is not yet implemented.
    """
    import json

    matched = 0
    unmatched = 0
    created = 0
    updated = 0

    for item in body.records:
        emp = session.exec(
            select(Employee).where(
                Employee.tenant_id == user.tenant_id,
                Employee.employee_code == item.employee_code,
            )
        ).first()

        if not emp:
            unmatched += 1
            continue

        matched += 1
        raw_str = json.dumps(item.raw_data) if item.raw_data else None
        hours = _compute_hours(item.time_in, item.time_out)

        existing = session.exec(
            select(AttendanceRecord).where(
                AttendanceRecord.tenant_id == user.tenant_id,
                AttendanceRecord.employee_id == emp.id,
                AttendanceRecord.date == item.date,
            )
        ).first()

        if existing:
            existing.time_in = item.time_in
            existing.time_out = item.time_out
            existing.hours_worked = hours
            existing.source = "biometric"
            existing.raw_data = raw_str
            session.add(existing)
            updated += 1
        else:
            rec = AttendanceRecord(
                tenant_id=user.tenant_id,
                employee_id=emp.id,
                date=item.date,
                time_in=item.time_in,
                time_out=item.time_out,
                hours_worked=hours,
                status="present",
                source="biometric",
                raw_data=raw_str,
                created_by_id=user.id,
            )
            session.add(rec)
            created += 1

    session.commit()
    return {
        "matched": matched,
        "unmatched": unmatched,
        "created": created,
        "updated": updated,
    }
