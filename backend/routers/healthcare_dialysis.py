"""Healthcare Dialysis Treatment Unit — machines, shifts, session schedule."""
from __future__ import annotations

from datetime import date as date_cls, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, func, select

from models import Account
from models_healthcare import (
    HcDialysisMachine,
    HcDialysisSession,
    HcDialysisShift,
    HcDialysisUnit,
    HcDoctor,
    HcPatient,
    HcProcedureCatalog,
)
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, next_number
from services.healthcare_posting import post_procedure
from services.money import D
from services.permissions import perm_dep

router = APIRouter(prefix="/api/healthcare/dialysis", tags=["healthcare-dialysis"])

_BOOKED_STATUSES = ("scheduled", "in_progress", "completed", "no_show")


# ── helpers ──────────────────────────────────────────────────────────────────


def _unit_or_none(session: Session, tenant_id: int) -> Optional[HcDialysisUnit]:
    return session.exec(
        select(HcDialysisUnit).where(
            HcDialysisUnit.tenant_id == tenant_id,
            HcDialysisUnit.is_active == True,  # noqa: E712
        )
    ).first()


def _unit_or_404(session: Session, tenant_id: int) -> HcDialysisUnit:
    unit = _unit_or_none(session, tenant_id)
    if not unit:
        raise HTTPException(404, "Dialysis unit not found — create one first")
    return unit


def _machine_or_404(session: Session, tenant_id: int, machine_id: int) -> HcDialysisMachine:
    m = session.exec(
        select(HcDialysisMachine).where(
            HcDialysisMachine.id == machine_id,
            HcDialysisMachine.tenant_id == tenant_id,
        )
    ).first()
    if not m:
        raise HTTPException(404, "Machine not found")
    return m


def _shift_or_404(session: Session, tenant_id: int, shift_id: int) -> HcDialysisShift:
    s = session.exec(
        select(HcDialysisShift).where(
            HcDialysisShift.id == shift_id,
            HcDialysisShift.tenant_id == tenant_id,
        )
    ).first()
    if not s:
        raise HTTPException(404, "Shift not found")
    return s


def _session_or_404(session: Session, tenant_id: int, session_id: int) -> HcDialysisSession:
    row = session.exec(
        select(HcDialysisSession).where(
            HcDialysisSession.id == session_id,
            HcDialysisSession.tenant_id == tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Dialysis session not found")
    return row


def _patient_or_404(session: Session, tenant_id: int, patient_id: int) -> HcPatient:
    p = session.exec(
        select(HcPatient).where(HcPatient.id == patient_id, HcPatient.tenant_id == tenant_id)
    ).first()
    if not p:
        raise HTTPException(404, "Patient not found")
    return p


def _capacity(session: Session, tenant_id: int, unit_id: int) -> dict:
    n_machines = session.exec(
        select(func.count(HcDialysisMachine.id)).where(
            HcDialysisMachine.tenant_id == tenant_id,
            HcDialysisMachine.unit_id == unit_id,
            HcDialysisMachine.is_active == True,  # noqa: E712
            HcDialysisMachine.status != "maintenance",
        )
    ).one() or 0
    n_shifts = session.exec(
        select(func.count(HcDialysisShift.id)).where(
            HcDialysisShift.tenant_id == tenant_id,
            HcDialysisShift.unit_id == unit_id,
            HcDialysisShift.is_active == True,  # noqa: E712
        )
    ).one() or 0
    # Structural capacity uses all active machines (incl. maintenance offline reduces usable)
    n_all_active = session.exec(
        select(func.count(HcDialysisMachine.id)).where(
            HcDialysisMachine.tenant_id == tenant_id,
            HcDialysisMachine.unit_id == unit_id,
            HcDialysisMachine.is_active == True,  # noqa: E712
        )
    ).one() or 0
    return {
        "active_machines": int(n_all_active),
        "usable_machines": int(n_machines),
        "active_shifts": int(n_shifts),
        "capacity": int(n_all_active) * int(n_shifts),
        "usable_capacity": int(n_machines) * int(n_shifts),
    }


def _booked_count(session: Session, tenant_id: int, session_date: str) -> int:
    return int(
        session.exec(
            select(func.count(HcDialysisSession.id)).where(
                HcDialysisSession.tenant_id == tenant_id,
                HcDialysisSession.session_date == session_date,
                HcDialysisSession.status.in_(list(_BOOKED_STATUSES)),
            )
        ).one()
        or 0
    )


def _slot_taken(
    session: Session,
    *,
    tenant_id: int,
    machine_id: int,
    shift_id: int,
    session_date: str,
    exclude_id: Optional[int] = None,
) -> bool:
    q = select(HcDialysisSession).where(
        HcDialysisSession.tenant_id == tenant_id,
        HcDialysisSession.machine_id == machine_id,
        HcDialysisSession.shift_id == shift_id,
        HcDialysisSession.session_date == session_date,
        HcDialysisSession.status != "cancelled",
    )
    if exclude_id is not None:
        q = q.where(HcDialysisSession.id != exclude_id)
    return session.exec(q).first() is not None


def _serialize_session(session: Session, row: HcDialysisSession) -> dict:
    patient = session.get(HcPatient, row.patient_id)
    doctor = session.get(HcDoctor, row.doctor_id) if row.doctor_id else None
    machine = session.get(HcDialysisMachine, row.machine_id)
    shift = session.get(HcDialysisShift, row.shift_id)
    return {
        **row.model_dump(),
        "patient_name": patient.name if patient else None,
        "patient_mr": patient.mr_number if patient else None,
        "doctor_name": doctor.name if doctor else None,
        "machine_code": machine.code if machine else None,
        "machine_name": machine.name if machine else None,
        "shift_code": shift.code if shift else None,
        "shift_name": shift.name if shift else None,
        "shift_start": shift.start_time if shift else None,
        "shift_end": shift.end_time if shift else None,
    }


def _default_hd_procedure(session: Session, tenant_id: int) -> Optional[HcProcedureCatalog]:
    return session.exec(
        select(HcProcedureCatalog).where(
            HcProcedureCatalog.tenant_id == tenant_id,
            HcProcedureCatalog.code == "HD-SESSION",
        )
    ).first()


# ── Unit ─────────────────────────────────────────────────────────────────────


class UnitCreate(BaseModel):
    name: str = "Dialysis Treatment Unit"
    open_time: str = "08:00"
    close_time: str = "20:00"
    shift_hours: int = 4


class UnitUpdate(BaseModel):
    name: Optional[str] = None
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    shift_hours: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/unit", dependencies=[perm_dep("healthcare.dialysis")])
def get_unit(user: CurrentUserDep, session: SessionDep):
    unit = _unit_or_none(session, user.tenant_id)
    if not unit:
        return None
    cap = _capacity(session, user.tenant_id, unit.id)  # type: ignore[arg-type]
    return {**unit.model_dump(), **cap}


@router.post("/unit", status_code=201, dependencies=[perm_dep("healthcare.dialysis", "edit")])
def create_unit(user: WriteUserDep, session: SessionDep, body: UnitCreate):
    existing = _unit_or_none(session, user.tenant_id)
    if existing:
        raise HTTPException(400, "Dialysis unit already exists for this tenant")
    unit = HcDialysisUnit(
        tenant_id=user.tenant_id,
        name=body.name,
        open_time=body.open_time,
        close_time=body.close_time,
        shift_hours=body.shift_hours,
        created_at=datetime.utcnow(),
    )
    session.add(unit)
    session.commit()
    session.refresh(unit)
    return unit


@router.put("/unit", dependencies=[perm_dep("healthcare.dialysis", "edit")])
def update_unit(user: WriteUserDep, session: SessionDep, body: UnitUpdate):
    unit = _unit_or_404(session, user.tenant_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(unit, k, v)
    session.add(unit)
    session.commit()
    session.refresh(unit)
    return unit


# ── Machines ─────────────────────────────────────────────────────────────────


class MachineCreate(BaseModel):
    code: str
    name: str
    status: str = "available"
    unit_id: Optional[int] = None


class MachineUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/machines", dependencies=[perm_dep("healthcare.dialysis")])
def list_machines(user: CurrentUserDep, session: SessionDep):
    rows = session.exec(
        select(HcDialysisMachine)
        .where(HcDialysisMachine.tenant_id == user.tenant_id)
        .order_by(HcDialysisMachine.code)
    ).all()
    return rows


@router.post("/machines", status_code=201, dependencies=[perm_dep("healthcare.dialysis", "edit")])
def create_machine(user: WriteUserDep, session: SessionDep, body: MachineCreate):
    unit = _unit_or_404(session, user.tenant_id) if not body.unit_id else session.exec(
        select(HcDialysisUnit).where(
            HcDialysisUnit.id == body.unit_id,
            HcDialysisUnit.tenant_id == user.tenant_id,
        )
    ).first()
    if not unit:
        raise HTTPException(404, "Dialysis unit not found")
    dup = session.exec(
        select(HcDialysisMachine).where(
            HcDialysisMachine.tenant_id == user.tenant_id,
            HcDialysisMachine.code == body.code,
        )
    ).first()
    if dup:
        raise HTTPException(400, f"Machine code {body.code} already exists")
    if body.status not in ("available", "in_use", "maintenance"):
        raise HTTPException(400, "Invalid machine status")
    m = HcDialysisMachine(
        tenant_id=user.tenant_id,
        unit_id=unit.id,  # type: ignore[arg-type]
        code=body.code.strip().upper(),
        name=body.name.strip(),
        status=body.status,
        created_at=datetime.utcnow(),
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


@router.put("/machines/{machine_id}", dependencies=[perm_dep("healthcare.dialysis", "edit")])
def update_machine(user: WriteUserDep, session: SessionDep, machine_id: int, body: MachineUpdate):
    m = _machine_or_404(session, user.tenant_id, machine_id)
    data = body.model_dump(exclude_none=True)
    if "status" in data and data["status"] not in ("available", "in_use", "maintenance"):
        raise HTTPException(400, "Invalid machine status")
    for k, v in data.items():
        setattr(m, k, v)
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


# ── Shifts ───────────────────────────────────────────────────────────────────


class ShiftCreate(BaseModel):
    code: str
    name: str
    start_time: str
    end_time: str
    sort_order: int = 0
    unit_id: Optional[int] = None


class ShiftUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/shifts", dependencies=[perm_dep("healthcare.dialysis")])
def list_shifts(user: CurrentUserDep, session: SessionDep):
    return session.exec(
        select(HcDialysisShift)
        .where(HcDialysisShift.tenant_id == user.tenant_id)
        .order_by(HcDialysisShift.sort_order, HcDialysisShift.code)
    ).all()


@router.post("/shifts", status_code=201, dependencies=[perm_dep("healthcare.dialysis", "edit")])
def create_shift(user: WriteUserDep, session: SessionDep, body: ShiftCreate):
    unit = _unit_or_404(session, user.tenant_id) if not body.unit_id else session.exec(
        select(HcDialysisUnit).where(
            HcDialysisUnit.id == body.unit_id,
            HcDialysisUnit.tenant_id == user.tenant_id,
        )
    ).first()
    if not unit:
        raise HTTPException(404, "Dialysis unit not found")
    dup = session.exec(
        select(HcDialysisShift).where(
            HcDialysisShift.tenant_id == user.tenant_id,
            HcDialysisShift.unit_id == unit.id,
            HcDialysisShift.code == body.code,
        )
    ).first()
    if dup:
        raise HTTPException(400, f"Shift code {body.code} already exists")
    s = HcDialysisShift(
        tenant_id=user.tenant_id,
        unit_id=unit.id,  # type: ignore[arg-type]
        code=body.code.strip().upper(),
        name=body.name.strip(),
        start_time=body.start_time,
        end_time=body.end_time,
        sort_order=body.sort_order,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


@router.put("/shifts/{shift_id}", dependencies=[perm_dep("healthcare.dialysis", "edit")])
def update_shift(user: WriteUserDep, session: SessionDep, shift_id: int, body: ShiftUpdate):
    s = _shift_or_404(session, user.tenant_id, shift_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


# ── Schedule grid ────────────────────────────────────────────────────────────


@router.get("/schedule", dependencies=[perm_dep("healthcare.dialysis")])
def get_schedule(user: CurrentUserDep, session: SessionDep, date: Optional[str] = None):
    """Machines × shifts grid for a day, with capacity counters."""
    day = date or str(date_cls.today())
    unit = _unit_or_none(session, user.tenant_id)
    if not unit:
        return {
            "date": day,
            "unit": None,
            "machines": [],
            "shifts": [],
            "slots": [],
            "capacity": 0,
            "usable_capacity": 0,
            "booked": 0,
            "available": 0,
        }

    machines = session.exec(
        select(HcDialysisMachine)
        .where(
            HcDialysisMachine.tenant_id == user.tenant_id,
            HcDialysisMachine.unit_id == unit.id,
            HcDialysisMachine.is_active == True,  # noqa: E712
        )
        .order_by(HcDialysisMachine.code)
    ).all()
    shifts = session.exec(
        select(HcDialysisShift)
        .where(
            HcDialysisShift.tenant_id == user.tenant_id,
            HcDialysisShift.unit_id == unit.id,
            HcDialysisShift.is_active == True,  # noqa: E712
        )
        .order_by(HcDialysisShift.sort_order, HcDialysisShift.code)
    ).all()

    sessions = session.exec(
        select(HcDialysisSession).where(
            HcDialysisSession.tenant_id == user.tenant_id,
            HcDialysisSession.session_date == day,
            HcDialysisSession.status != "cancelled",
        )
    ).all()
    by_slot: dict[tuple[int, int], HcDialysisSession] = {
        (s.machine_id, s.shift_id): s for s in sessions
    }

    slots = []
    for m in machines:
        for sh in shifts:
            row = by_slot.get((m.id, sh.id))  # type: ignore[arg-type]
            slots.append({
                "machine_id": m.id,
                "machine_code": m.code,
                "machine_status": m.status,
                "shift_id": sh.id,
                "shift_code": sh.code,
                "shift_name": sh.name,
                "start_time": sh.start_time,
                "end_time": sh.end_time,
                "session": _serialize_session(session, row) if row else None,
            })

    cap = _capacity(session, user.tenant_id, unit.id)  # type: ignore[arg-type]
    booked = _booked_count(session, user.tenant_id, day)
    return {
        "date": day,
        "unit": unit.model_dump(),
        "machines": [m.model_dump() for m in machines],
        "shifts": [s.model_dump() for s in shifts],
        "slots": slots,
        "capacity": cap["capacity"],
        "usable_capacity": cap["usable_capacity"],
        "booked": booked,
        "available": max(0, cap["usable_capacity"] - booked),
        "active_machines": cap["active_machines"],
        "usable_machines": cap["usable_machines"],
        "active_shifts": cap["active_shifts"],
    }


# ── Sessions ─────────────────────────────────────────────────────────────────


class SessionCreate(BaseModel):
    patient_id: int
    machine_id: int
    shift_id: int
    session_date: str
    doctor_id: Optional[int] = None
    procedure_id: Optional[int] = None
    fee: Optional[Decimal] = None
    notes: Optional[str] = None


@router.get("/sessions", dependencies=[perm_dep("healthcare.dialysis")])
def list_sessions(
    user: CurrentUserDep,
    session: SessionDep,
    date: Optional[str] = None,
    patient_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    q = select(HcDialysisSession).where(HcDialysisSession.tenant_id == user.tenant_id)
    if date:
        q = q.where(HcDialysisSession.session_date == date)
    if patient_id is not None:
        q = q.where(HcDialysisSession.patient_id == patient_id)
    if status:
        q = q.where(HcDialysisSession.status == status)
    rows = session.exec(
        q.order_by(HcDialysisSession.session_date.desc(), HcDialysisSession.id.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return [_serialize_session(session, r) for r in rows]


@router.post("/sessions", status_code=201, dependencies=[perm_dep("healthcare.dialysis", "edit")])
def book_session(user: WriteUserDep, session: SessionDep, body: SessionCreate):
    patient = _patient_or_404(session, user.tenant_id, body.patient_id)
    machine = _machine_or_404(session, user.tenant_id, body.machine_id)
    shift = _shift_or_404(session, user.tenant_id, body.shift_id)

    if not machine.is_active or machine.status == "maintenance":
        raise HTTPException(400, f"Machine {machine.code} is offline / under maintenance")
    if not shift.is_active:
        raise HTTPException(400, f"Shift {shift.code} is inactive")
    if machine.unit_id != shift.unit_id:
        raise HTTPException(400, "Machine and shift must belong to the same unit")

    if _slot_taken(
        session,
        tenant_id=user.tenant_id,
        machine_id=body.machine_id,
        shift_id=body.shift_id,
        session_date=body.session_date,
    ):
        raise HTTPException(400, "That machine × shift slot is already booked")

    cap = _capacity(session, user.tenant_id, machine.unit_id)
    booked = _booked_count(session, user.tenant_id, body.session_date)
    if booked >= cap["usable_capacity"]:
        raise HTTPException(
            400,
            f"Daily capacity full ({booked}/{cap['usable_capacity']} usable slots)",
        )

    if body.doctor_id is not None:
        doc = session.exec(
            select(HcDoctor).where(
                HcDoctor.id == body.doctor_id,
                HcDoctor.tenant_id == user.tenant_id,
            )
        ).first()
        if not doc:
            raise HTTPException(404, "Doctor not found")

    proc: Optional[HcProcedureCatalog] = None
    if body.procedure_id:
        proc = session.exec(
            select(HcProcedureCatalog).where(
                HcProcedureCatalog.id == body.procedure_id,
                HcProcedureCatalog.tenant_id == user.tenant_id,
            )
        ).first()
        if not proc:
            raise HTTPException(404, "Procedure not found")
    else:
        proc = _default_hd_procedure(session, user.tenant_id)

    fee = body.fee if body.fee is not None else (proc.standard_fee if proc else D(0))
    session_number = next_number(
        session, user.tenant_id, "hc_dialysis", "DS", fmt="{prefix}-{YYYY}{seq:04d}"
    )
    row = HcDialysisSession(
        tenant_id=user.tenant_id,
        session_number=session_number,
        patient_id=patient.id,  # type: ignore[arg-type]
        doctor_id=body.doctor_id,
        machine_id=machine.id,  # type: ignore[arg-type]
        shift_id=shift.id,  # type: ignore[arg-type]
        session_date=body.session_date,
        status="scheduled",
        fee=fee,
        procedure_id=proc.id if proc else None,
        notes=body.notes,
        created_at=datetime.utcnow(),
        created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize_session(session, row)


@router.put("/sessions/{session_id}/start", dependencies=[perm_dep("healthcare.dialysis", "edit")])
def start_session(user: WriteUserDep, session: SessionDep, session_id: int):
    row = _session_or_404(session, user.tenant_id, session_id)
    if row.status != "scheduled":
        raise HTTPException(400, f"Cannot start session in status '{row.status}'")
    machine = _machine_or_404(session, user.tenant_id, row.machine_id)
    row.status = "in_progress"
    row.started_at = datetime.utcnow()
    machine.status = "in_use"
    session.add(row)
    session.add(machine)
    session.commit()
    session.refresh(row)
    return _serialize_session(session, row)


@router.put("/sessions/{session_id}/complete", dependencies=[perm_dep("healthcare.dialysis", "edit")])
def complete_session(user: WriteUserDep, session: SessionDep, session_id: int):
    row = _session_or_404(session, user.tenant_id, session_id)
    if row.status not in ("scheduled", "in_progress"):
        raise HTTPException(400, f"Cannot complete session in status '{row.status}'")
    if row.transaction_id:
        raise HTTPException(400, "Session already billed")

    patient = _patient_or_404(session, user.tenant_id, row.patient_id)
    proc_name = "Hemodialysis Session"
    rev_code = "4120"
    if row.procedure_id:
        proc = session.get(HcProcedureCatalog, row.procedure_id)
        if proc:
            proc_name = proc.name
            if proc.revenue_account_id:
                acc = session.get(Account, proc.revenue_account_id)
                if acc:
                    rev_code = acc.code

    fee = D(row.fee)
    if fee > 0:
        txn = post_procedure(
            session,
            user,
            amount=fee,
            date=row.session_date,
            patient_name=patient.name,
            procedure_name=proc_name,
            customer_id=patient.customer_id,
            revenue_account_code=rev_code,
        )
        row.transaction_id = txn.id

    row.status = "completed"
    row.completed_at = datetime.utcnow()
    if not row.started_at:
        row.started_at = row.completed_at

    machine = _machine_or_404(session, user.tenant_id, row.machine_id)
    # Free machine unless another in-progress session uses it today
    other_active = session.exec(
        select(HcDialysisSession).where(
            HcDialysisSession.tenant_id == user.tenant_id,
            HcDialysisSession.machine_id == machine.id,
            HcDialysisSession.status == "in_progress",
            HcDialysisSession.id != row.id,
        )
    ).first()
    if not other_active and machine.status == "in_use":
        machine.status = "available"
        session.add(machine)

    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize_session(session, row)


@router.put("/sessions/{session_id}/cancel", dependencies=[perm_dep("healthcare.dialysis", "edit")])
def cancel_session(user: WriteUserDep, session: SessionDep, session_id: int):
    row = _session_or_404(session, user.tenant_id, session_id)
    if row.status in ("completed", "cancelled"):
        raise HTTPException(400, f"Cannot cancel session in status '{row.status}'")
    if row.transaction_id:
        raise HTTPException(400, "Cannot cancel a billed session")
    was_in_progress = row.status == "in_progress"
    row.status = "cancelled"
    session.add(row)
    if was_in_progress:
        machine = _machine_or_404(session, user.tenant_id, row.machine_id)
        if machine.status == "in_use":
            machine.status = "available"
            session.add(machine)
    session.commit()
    session.refresh(row)
    return _serialize_session(session, row)
