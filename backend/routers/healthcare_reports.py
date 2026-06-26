"""Healthcare module — report endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from sqlmodel import Session, func, select

from models_healthcare import (
    HcAdmission, HcAdmissionCharge, HcBed, HcDoctor, HcLabOrder,
    HcLabOrderItem, HcOpdToken, HcOpdVisit, HcPatient, HcProcedureOrder,
    HcWard,
)
from models import Transaction, JournalEntry, Account
from routers.common import CurrentUserDep, SessionDep
from services.permissions import perm_dep

router = APIRouter(prefix="/api/healthcare/reports", tags=["healthcare-reports"])


# ── Dashboard KPIs ────────────────────────────────────────────────────────────

@router.get("/dashboard", dependencies=[perm_dep("healthcare.reports")])
def dashboard(user: CurrentUserDep, session: SessionDep, date: Optional[str] = None):
    """KPIs: tokens today, currently admitted, bed occupancy, pending lab results."""
    from datetime import date as date_cls
    today = date or str(date_cls.today())
    tid = user.tenant_id

    tokens_today = session.exec(
        select(func.count(HcOpdToken.id)).where(
            HcOpdToken.tenant_id == tid,
            HcOpdToken.visit_date == today,
        )
    ).one() or 0

    admitted = session.exec(
        select(func.count(HcAdmission.id)).where(
            HcAdmission.tenant_id == tid, HcAdmission.status == "admitted"
        )
    ).one() or 0

    total_beds = session.exec(
        select(func.count(HcBed.id)).where(HcBed.tenant_id == tid, HcBed.is_active == True)  # noqa: E712
    ).one() or 0

    occupied_beds = session.exec(
        select(func.count(HcBed.id)).where(
            HcBed.tenant_id == tid, HcBed.status == "occupied"
        )
    ).one() or 0

    pending_labs = session.exec(
        select(func.count(HcLabOrder.id)).where(
            HcLabOrder.tenant_id == tid,
            HcLabOrder.status.in_(["ordered", "sample_collected", "processing"]),
        )
    ).one() or 0

    visits_today = session.exec(
        select(func.count(HcOpdVisit.id)).where(
            HcOpdVisit.tenant_id == tid,
            HcOpdVisit.visit_date == today,
        )
    ).one() or 0

    return {
        "date": today,
        "tokens_today": tokens_today,
        "visits_today": visits_today,
        "currently_admitted": admitted,
        "total_beds": total_beds,
        "occupied_beds": occupied_beds,
        "bed_occupancy_pct": round(occupied_beds / total_beds * 100, 1) if total_beds else 0,
        "pending_lab_results": pending_labs,
    }


# ── OPD Summary ───────────────────────────────────────────────────────────────

@router.get("/opd-summary", dependencies=[perm_dep("healthcare.reports")])
def opd_summary(
    user: CurrentUserDep, session: SessionDep,
    from_date: str = "", to_date: str = "",
):
    """Daily OPD visit count and revenue by doctor."""
    tid = user.tenant_id
    q = select(
        HcDoctor.name.label("doctor"),
        HcOpdVisit.visit_date,
        func.count(HcOpdVisit.id).label("visits"),
        func.sum(HcOpdVisit.id).label("billed_visits"),
    ).join(
        HcDoctor, HcOpdVisit.doctor_id == HcDoctor.id
    ).where(HcOpdVisit.tenant_id == tid)

    if from_date:
        q = q.where(HcOpdVisit.visit_date >= from_date)
    if to_date:
        q = q.where(HcOpdVisit.visit_date <= to_date)

    q = q.group_by(HcDoctor.name, HcOpdVisit.visit_date).order_by(HcOpdVisit.visit_date.desc())
    rows = session.exec(q).all()

    return [
        {
            "doctor": r.doctor,
            "date": r.visit_date,
            "visits": r.visits,
        }
        for r in rows
    ]


# ── Doctor Collections ────────────────────────────────────────────────────────

@router.get("/doctor-collections", dependencies=[perm_dep("healthcare.reports")])
def doctor_collections(
    user: CurrentUserDep, session: SessionDep,
    from_date: str = "", to_date: str = "",
):
    """Total consultations and billed amounts per doctor."""
    tid = user.tenant_id
    doctors = session.exec(
        select(HcDoctor).where(HcDoctor.tenant_id == tid, HcDoctor.is_active == True)  # noqa: E712
    ).all()

    result = []
    for doctor in doctors:
        q = select(func.count(HcOpdVisit.id)).where(
            HcOpdVisit.tenant_id == tid,
            HcOpdVisit.doctor_id == doctor.id,
        )
        if from_date:
            q = q.where(HcOpdVisit.visit_date >= from_date)
        if to_date:
            q = q.where(HcOpdVisit.visit_date <= to_date)

        total_visits = session.exec(q).one() or 0
        billed = session.exec(
            q.where(HcOpdVisit.transaction_id.isnot(None))
        ).one() or 0

        result.append({
            "doctor_id": doctor.id,
            "doctor_name": doctor.name,
            "specialization": doctor.specialization,
            "total_visits": total_visits,
            "billed_visits": billed,
            "opd_fee": str(doctor.opd_fee),
            "estimated_revenue": str(doctor.opd_fee * billed),
        })

    return sorted(result, key=lambda r: r["total_visits"], reverse=True)


# ── Lab Summary ───────────────────────────────────────────────────────────────

@router.get("/lab-summary", dependencies=[perm_dep("healthcare.reports")])
def lab_summary(
    user: CurrentUserDep, session: SessionDep,
    from_date: str = "", to_date: str = "",
):
    """Lab orders by status and source."""
    tid = user.tenant_id

    # Count by status
    statuses = ["ordered", "sample_collected", "processing", "resulted", "delivered"]
    by_status = {}
    for s in statuses:
        q = select(func.count(HcLabOrder.id)).where(
            HcLabOrder.tenant_id == tid, HcLabOrder.status == s
        )
        if from_date:
            q = q.where(HcLabOrder.order_date >= from_date)
        if to_date:
            q = q.where(HcLabOrder.order_date <= to_date)
        by_status[s] = session.exec(q).one() or 0

    # Count by source
    sources = ["opd", "ipd", "walkin", "collection_centre"]
    by_source = {}
    for src in sources:
        q = select(func.count(HcLabOrder.id)).where(
            HcLabOrder.tenant_id == tid, HcLabOrder.source == src
        )
        if from_date:
            q = q.where(HcLabOrder.order_date >= from_date)
        if to_date:
            q = q.where(HcLabOrder.order_date <= to_date)
        by_source[src] = session.exec(q).one() or 0

    return {
        "period": {"from": from_date, "to": to_date},
        "by_status": by_status,
        "by_source": by_source,
        "total": sum(by_status.values()),
    }


# ── IPD Census ────────────────────────────────────────────────────────────────

@router.get("/ipd-census", dependencies=[perm_dep("healthcare.reports")])
def ipd_census(
    user: CurrentUserDep, session: SessionDep,
    from_date: str = "", to_date: str = "",
):
    """IPD admissions and average length of stay per ward."""
    tid = user.tenant_id
    wards = session.exec(
        select(HcWard).where(HcWard.tenant_id == tid)
    ).all()

    result = []
    for ward in wards:
        q = select(HcAdmission).where(
            HcAdmission.tenant_id == tid, HcAdmission.ward_id == ward.id
        )
        if from_date:
            q = q.where(HcAdmission.admission_date >= from_date)
        if to_date:
            q = q.where(HcAdmission.admission_date <= to_date)

        admissions = session.exec(q).all()
        discharged = [a for a in admissions if a.status == "discharged" and a.discharge_date]

        avg_los = 0.0
        if discharged:
            from datetime import datetime
            total_days = sum(
                (datetime.strptime(a.discharge_date, "%Y-%m-%d") -
                 datetime.strptime(a.admission_date, "%Y-%m-%d")).days
                for a in discharged
            )
            avg_los = round(total_days / len(discharged), 1)

        total_beds = session.exec(
            select(func.count(HcBed.id)).where(
                HcBed.ward_id == ward.id, HcBed.tenant_id == tid
            )
        ).one() or 0

        occupied = session.exec(
            select(func.count(HcBed.id)).where(
                HcBed.ward_id == ward.id, HcBed.tenant_id == tid, HcBed.status == "occupied"
            )
        ).one() or 0

        result.append({
            "ward_id": ward.id,
            "ward_name": ward.name,
            "ward_type": ward.ward_type,
            "total_beds": total_beds,
            "occupied_beds": occupied,
            "admissions": len(admissions),
            "discharges": len(discharged),
            "avg_length_of_stay_days": avg_los,
        })

    return result


# ── Revenue by Type ───────────────────────────────────────────────────────────

@router.get("/revenue-by-type", dependencies=[perm_dep("healthcare.reports")])
def revenue_by_type(
    user: CurrentUserDep, session: SessionDep,
    from_date: str = "", to_date: str = "",
):
    """Revenue split across OPD, Lab, Procedures, IPD using GL account codes."""
    tid = user.tenant_id

    # Map revenue account codes to labels
    revenue_accounts = {
        "4100": "OPD Consultation",
        "4101": "OPD Follow-up",
        "4110": "Laboratory",
        "4111": "Sample Collection",
        "4120": "Surgical / Procedure",
        "4121": "Ward / Bed Charges",
        "4122": "Nursing & Allied Services",
        "4130": "Pharmacy",
    }

    result = []
    for code, label in revenue_accounts.items():
        acc = session.exec(
            select(Account).where(Account.tenant_id == tid, Account.code == code)
        ).first()
        if not acc:
            continue

        q = select(func.sum(JournalEntry.credit)).where(
            JournalEntry.account_id == acc.id,
        )
        if from_date or to_date:
            q = q.join(Transaction, JournalEntry.transaction_id == Transaction.id)
            if from_date:
                q = q.where(Transaction.date >= from_date)
            if to_date:
                q = q.where(Transaction.date <= to_date)

        total = session.exec(q).one() or 0
        result.append({
            "account_code": code,
            "label": label,
            "revenue": str(total),
        })

    grand_total = sum(float(r["revenue"]) for r in result)
    for r in result:
        val = float(r["revenue"])
        r["pct"] = round(val / grand_total * 100, 1) if grand_total else 0

    return {
        "period": {"from": from_date, "to": to_date},
        "breakdown": result,
        "total": str(grand_total),
    }


# ── Patient Statement ─────────────────────────────────────────────────────────

@router.get("/patient-statement/{patient_id}", dependencies=[perm_dep("healthcare.reports")])
def patient_statement(
    user: CurrentUserDep, session: SessionDep,
    patient_id: int,
    from_date: str = "", to_date: str = "",
):
    """All clinical events + charges for a patient."""
    tid = user.tenant_id
    patient = session.exec(
        select(HcPatient).where(HcPatient.id == patient_id, HcPatient.tenant_id == tid)
    ).first()
    if not patient:
        from fastapi import HTTPException
        raise HTTPException(404, "Patient not found")

    # OPD visits
    q = select(HcOpdVisit).where(
        HcOpdVisit.tenant_id == tid, HcOpdVisit.patient_id == patient_id
    )
    if from_date:
        q = q.where(HcOpdVisit.visit_date >= from_date)
    if to_date:
        q = q.where(HcOpdVisit.visit_date <= to_date)
    visits = session.exec(q.order_by(HcOpdVisit.visit_date)).all()

    # Admissions
    q = select(HcAdmission).where(
        HcAdmission.tenant_id == tid, HcAdmission.patient_id == patient_id
    )
    if from_date:
        q = q.where(HcAdmission.admission_date >= from_date)
    if to_date:
        q = q.where(HcAdmission.admission_date <= to_date)
    admissions = session.exec(q.order_by(HcAdmission.admission_date)).all()

    # Lab orders
    q = select(HcLabOrder).where(
        HcLabOrder.tenant_id == tid, HcLabOrder.patient_id == patient_id
    )
    if from_date:
        q = q.where(HcLabOrder.order_date >= from_date)
    if to_date:
        q = q.where(HcLabOrder.order_date <= to_date)
    lab_orders = session.exec(q.order_by(HcLabOrder.order_date)).all()

    # Procedure orders
    q = select(HcProcedureOrder).where(
        HcProcedureOrder.tenant_id == tid, HcProcedureOrder.patient_id == patient_id
    )
    if from_date:
        q = q.where(HcProcedureOrder.order_date >= from_date)
    if to_date:
        q = q.where(HcProcedureOrder.order_date <= to_date)
    procedures = session.exec(q.order_by(HcProcedureOrder.order_date)).all()

    # Admission charges (for active admissions)
    adm_charges = {}
    for adm in admissions:
        charges = session.exec(
            select(HcAdmissionCharge).where(HcAdmissionCharge.admission_id == adm.id)
        ).all()
        adm_charges[adm.id] = {
            "charges": [c.model_dump() for c in charges],
            "total": str(sum(c.amount for c in charges)),
        }

    return {
        "patient": patient.model_dump(),
        "period": {"from": from_date, "to": to_date},
        "opd_visits": [v.model_dump() for v in visits],
        "admissions": [
            {**a.model_dump(), **adm_charges.get(a.id, {"charges": [], "total": "0"})}
            for a in admissions
        ],
        "lab_orders": [o.model_dump() for o in lab_orders],
        "procedure_orders": [p.model_dump() for p in procedures],
    }
