"""Healthcare module — patients, doctors, OPD, IPD, lab, procedures, store."""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session, func, select

from models import Account, Customer, Settings
from models_healthcare import (
    HcAdmission, HcAdmissionCharge, HcBed, HcDoctor, HcLabOrder,
    HcLabOrderItem, HcLabTest, HcOpdToken, HcOpdVisit, HcPatient,
    HcPrescription, HcPrescriptionItem, HcProcedureCatalog,
    HcProcedureConsumable, HcProcedureOrder, HcSampleCollection,
    HcStoreIssue, HcStoreIssueItem, HcWard,
)
from routers.common import (
    CurrentUserDep, SessionDep, WriteUserDep, log_audit, next_number,
)
from services.healthcare_posting import (
    post_discharge_bill, post_ipd_deposit, post_lab_order,
    post_opd_consultation, post_procedure, post_store_issue,
)
from services.money import D, ZERO
from services.permissions import perm_dep

router = APIRouter(prefix="/api/healthcare", tags=["healthcare"])

# Max serial points per analyte on a printed report (CLSI cumulative / trend).
_LAB_HISTORY_LIMIT = 10


# ── helpers ──────────────────────────────────────────────────────────────────

def _patient_or_404(session: Session, tenant_id: int, patient_id: int) -> HcPatient:
    p = session.exec(
        select(HcPatient).where(HcPatient.id == patient_id, HcPatient.tenant_id == tenant_id)
    ).first()
    if not p:
        raise HTTPException(404, "Patient not found")
    return p


def _doctor_or_404(session: Session, tenant_id: int, doctor_id: int) -> HcDoctor:
    d = session.exec(
        select(HcDoctor).where(HcDoctor.id == doctor_id, HcDoctor.tenant_id == tenant_id)
    ).first()
    if not d:
        raise HTTPException(404, "Doctor not found")
    return d


def _parse_lab_numeric(value: Optional[str]) -> Optional[float]:
    """Extract a float from a lab result string; None for qualitative text."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
    if not m:
        return None
    # Reject when the string is mostly words ("Non-Reactive", "Normal study")
    if re.search(r"[A-Za-z]{3,}", text) and not re.fullmatch(r"[-+]?\d*\.?\d+", text):
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _parse_reference_interval(ref: Optional[str]) -> dict:
    """Parse catalogue reference text into {low, high} for trend banding.
    Supports '12–17', '12-17', '0.4–4.0', '<140', '>70'. Qualitative → empty."""
    if not ref:
        return {}
    text = str(ref).strip().replace("–", "-").replace("—", "-").replace("−", "-")
    if not text or text.lower() in ("varies", "negative", "normal", "n/a", "na"):
        return {}
    m = re.fullmatch(r"<\s*([-+]?\d*\.?\d+)", text)
    if m:
        return {"high": float(m.group(1))}
    m = re.fullmatch(r">\s*([-+]?\d*\.?\d+)", text)
    if m:
        return {"low": float(m.group(1))}
    m = re.fullmatch(r"([-+]?\d*\.?\d+)\s*-\s*([-+]?\d*\.?\d+)", text)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return {"low": lo, "high": hi}
    return {}


_POSITIVE_WORDS = re.compile(
    r"\b(positive|reactive|detected|present|abnormal|elevated|high|growth)\b",
    re.I,
)
_NEGATIVE_WORDS = re.compile(
    r"\b(negative|non[-\s]?reactive|not\s+detected|absent|nil|clear|normal\s+study|wnl|"
    r"within\s+normal|desirable|sinus\s+rhythm|no\s+growth)\b",
    re.I,
)


def _classify_lab_flag(
    result_value: Optional[str],
    *,
    reference_interval: Optional[dict] = None,
    reference_range: Optional[str] = None,
    is_abnormal: bool = False,
) -> dict:
    """International H/L / Pos/Neg interpretation for a single result.

    Returns {code, label, symbol} where code is one of:
      high | low | positive | negative | normal | abnormal | pending
    """
    if result_value is None or not str(result_value).strip():
        return {"code": "pending", "label": "Pending", "symbol": "…"}

    text = str(result_value).strip()
    interval = reference_interval if reference_interval is not None else _parse_reference_interval(reference_range)
    numeric = _parse_lab_numeric(text)

    if numeric is not None and interval:
        lo = interval.get("low")
        hi = interval.get("high")
        if hi is not None and numeric > hi:
            return {"code": "high", "label": "Excess (High)", "symbol": "H"}
        if lo is not None and numeric < lo:
            return {"code": "low", "label": "Reduced (Low)", "symbol": "L"}
        if lo is not None or hi is not None:
            return {"code": "normal", "label": "Within range", "symbol": "N"}

    # Qualitative / semi-quantitative text
    if _NEGATIVE_WORDS.search(text):
        return {"code": "negative", "label": "Negative", "symbol": "−"}
    if _POSITIVE_WORDS.search(text):
        return {"code": "positive", "label": "Positive", "symbol": "+"}

    if is_abnormal:
        return {"code": "abnormal", "label": "Abnormal", "symbol": "!"}
    if numeric is not None:
        return {"code": "normal", "label": "Within range", "symbol": "N"}
    return {"code": "normal", "label": "Normal", "symbol": "N"}


def _patient_lab_history(
    session: Session,
    *,
    tenant_id: int,
    patient_id: int,
    test_ids: set[int],
    current_order_id: int,
    current_order_date: Optional[str] = None,
    limit: int = _LAB_HISTORY_LIMIT,
    catalogue_ranges: Optional[dict[int, Optional[str]]] = None,
) -> dict[int, list[dict]]:
    """Prior + current resulted values per test for this patient (chronological).
    Aligns with cumulative / serial reporting used in ISO 15189 / CLSI lab reports.

    Points after the current order (by date, then id) are excluded so reprinting
    an older report never pulls in later visits.
    """
    if not test_ids:
        return {}
    ranges = catalogue_ranges or {}
    rows = session.exec(
        select(HcLabOrderItem, HcLabOrder)
        .join(HcLabOrder, HcLabOrderItem.lab_order_id == HcLabOrder.id)
        .where(
            HcLabOrder.tenant_id == tenant_id,
            HcLabOrder.patient_id == patient_id,
            HcLabOrderItem.test_id.in_(test_ids),
            HcLabOrderItem.resulted_at.is_not(None),  # type: ignore[attr-defined]
            HcLabOrderItem.result_value.is_not(None),  # type: ignore[attr-defined]
        )
        .order_by(HcLabOrder.order_date.asc(), HcLabOrder.id.asc(), HcLabOrderItem.resulted_at.asc())  # type: ignore[attr-defined]
    ).all()

    by_test: dict[int, list[dict]] = {tid: [] for tid in test_ids}
    for item, order in rows:
        # Skip visits after the report being rendered
        if current_order_date:
            od = order.order_date or ""
            if od > current_order_date:
                continue
            if od == current_order_date and order.id > current_order_id:
                continue
        ref = item.reference_range or ranges.get(item.test_id)
        flag = _classify_lab_flag(
            item.result_value,
            reference_range=ref,
            is_abnormal=bool(item.is_abnormal),
        )
        by_test.setdefault(item.test_id, []).append({
            "order_id": order.id,
            "order_number": order.order_number,
            "order_date": order.order_date,
            "result_value": item.result_value,
            "result_unit": item.result_unit,
            "reference_range": ref,
            "is_abnormal": bool(item.is_abnormal) or flag["code"] in ("high", "low", "positive", "abnormal"),
            "numeric_value": _parse_lab_numeric(item.result_value),
            "flag": flag,
            "is_current": order.id == current_order_id,
            "resulted_at": item.resulted_at.isoformat() if item.resulted_at else None,
        })

    # Keep the most recent `limit` points per analyte (includes current when present)
    trimmed: dict[int, list[dict]] = {}
    for tid, points in by_test.items():
        if not points:
            continue
        series = points[-limit:]
        # Only useful when there is at least one prior (or current alone for table)
        if len(series) >= 2 or (len(series) == 1 and series[0]["is_current"]):
            trimmed[tid] = series
    return trimmed


def _patient_age(dob: Optional[str]) -> Optional[int]:
    """Derive age in whole years from an ISO YYYY-MM-DD DOB string."""
    if not dob:
        return None
    try:
        born = date.fromisoformat(dob[:10])
    except ValueError:
        return None
    today = date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return max(0, years)


def _serialize_lab_order(session: Session, order: HcLabOrder) -> dict:
    """Report-ready lab order payload with patient, doctor, tests, sample, history."""
    patient = session.get(HcPatient, order.patient_id)
    doctor = session.get(HcDoctor, order.doctor_id) if order.doctor_id else None
    items = session.exec(
        select(HcLabOrderItem).where(HcLabOrderItem.lab_order_id == order.id)
    ).all()
    test_ids = {i.test_id for i in items}
    tests_by_id: dict[int, HcLabTest] = {}
    if test_ids:
        for t in session.exec(select(HcLabTest).where(HcLabTest.id.in_(test_ids))).all():
            tests_by_id[t.id] = t

    history_by_test = _patient_lab_history(
        session,
        tenant_id=order.tenant_id,
        patient_id=order.patient_id,
        test_ids=test_ids,
        current_order_id=order.id,
        current_order_date=order.order_date,
        catalogue_ranges={tid: t.normal_range for tid, t in tests_by_id.items()},
    )

    serialized_items = []
    for item in items:
        test = tests_by_id.get(item.test_id)
        series = history_by_test.get(item.test_id, [])
        priors = [p for p in series if not p["is_current"]]
        last_prior = priors[-1] if priors else None
        ref_text = item.reference_range or (test.normal_range if test else None)
        interval = _parse_reference_interval(ref_text)
        flag = _classify_lab_flag(
            item.result_value,
            reference_interval=interval,
            reference_range=ref_text,
            is_abnormal=bool(item.is_abnormal),
        )
        # Enrich prior point with flag if serializer already attached one
        if last_prior and "flag" not in last_prior:
            last_prior = {
                **last_prior,
                "flag": _classify_lab_flag(
                    last_prior.get("result_value"),
                    reference_range=last_prior.get("reference_range") or ref_text,
                    is_abnormal=bool(last_prior.get("is_abnormal")),
                ),
            }
        serialized_items.append({
            **item.model_dump(),
            "test_code": test.code if test else None,
            "test_name": test.name if test else f"Test #{item.test_id}",
            "category": test.category if test else "other",
            "catalogue_unit": test.unit if test else None,
            "catalogue_normal_range": test.normal_range if test else None,
            "reference_interval": interval,
            "flag": flag,
            "previous_result": last_prior,
            "history": series,
        })

    sample = session.exec(
        select(HcSampleCollection)
        .where(HcSampleCollection.lab_order_id == order.id)
        .order_by(HcSampleCollection.id.desc())
    ).first()

    payload: dict = {
        **order.model_dump(),
        "patient": None,
        "doctor": None,
        "sample": None,
        "items": serialized_items,
        "history_by_test": history_by_test,
    }
    if patient:
        payload["patient"] = {
            "id": patient.id,
            "name": patient.name,
            "mr_number": patient.mr_number,
            "gender": patient.gender,
            "dob": patient.dob,
            "age": _patient_age(patient.dob),
            "phone": patient.phone,
            "email": getattr(patient, "email", None),
            "blood_group": patient.blood_group,
        }
    if doctor:
        payload["doctor"] = {
            "id": doctor.id,
            "name": doctor.name,
            "specialization": doctor.specialization,
        }
    if sample:
        payload["sample"] = {
            "id": sample.id,
            "collected_at": sample.collected_at.isoformat() if sample.collected_at else None,
            "collection_point": sample.collection_point,
            "specimen_type": sample.specimen_type,
            "barcode": sample.barcode,
            "status": sample.status,
        }
    return payload


def _ward_or_404(session: Session, tenant_id: int, ward_id: int) -> HcWard:
    w = session.exec(
        select(HcWard).where(HcWard.id == ward_id, HcWard.tenant_id == tenant_id)
    ).first()
    if not w:
        raise HTTPException(404, "Ward not found")
    return w


def _bed_or_404(session: Session, tenant_id: int, bed_id: int) -> HcBed:
    b = session.exec(
        select(HcBed).where(HcBed.id == bed_id, HcBed.tenant_id == tenant_id)
    ).first()
    if not b:
        raise HTTPException(404, "Bed not found")
    return b


def _patient_customer_id(session: Session, patient: HcPatient) -> Optional[int]:
    return patient.customer_id


# ════════════════════════════════════════════════════════════════════════════
# PATIENTS
# ════════════════════════════════════════════════════════════════════════════

class PatientCreate(BaseModel):
    name: str
    dob: Optional[str] = None
    gender: str = "other"
    blood_group: Optional[str] = None
    cnic: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    allergies: Optional[str] = None


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    cnic: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    allergies: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/patients", dependencies=[perm_dep("healthcare.patients")])
def list_patients(
    user: CurrentUserDep, session: SessionDep,
    search: str = "", skip: int = 0, limit: int = 50,
):
    q = select(HcPatient).where(HcPatient.tenant_id == user.tenant_id)
    if search:
        q = q.where(
            HcPatient.name.ilike(f"%{search}%")
            | HcPatient.mr_number.ilike(f"%{search}%")
            | HcPatient.cnic.ilike(f"%{search}%")
        )
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(HcPatient.name).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.post("/patients", status_code=201, dependencies=[perm_dep("healthcare.patients", "edit")])
def create_patient(user: WriteUserDep, session: SessionDep, body: PatientCreate):
    mr = next_number(session, user.tenant_id, "hc_mr", "MR", fmt="{prefix}-{YYYY}{seq:04d}")

    # Auto-create a Customer record so AR billing works out-of-the-box
    customer = Customer(
        tenant_id=user.tenant_id,
        name=body.name,
        phone=body.phone or "",
        email=body.email or "",
    )
    session.add(customer)
    session.flush()

    patient = HcPatient(
        **body.model_dump(),
        tenant_id=user.tenant_id,
        mr_number=mr,
        customer_id=customer.id,
        created_by_id=user.id,
    )
    session.add(patient)
    log_audit(session, user, "CREATE", "hc_patient", None, {"name": body.name, "mr": mr})
    session.commit()
    session.refresh(patient)
    return patient


@router.get("/patients/{patient_id}", dependencies=[perm_dep("healthcare.patients")])
def get_patient(user: CurrentUserDep, session: SessionDep, patient_id: int):
    return _patient_or_404(session, user.tenant_id, patient_id)


@router.put("/patients/{patient_id}", dependencies=[perm_dep("healthcare.patients", "edit")])
def update_patient(user: WriteUserDep, session: SessionDep, patient_id: int, body: PatientUpdate):
    p = _patient_or_404(session, user.tenant_id, patient_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    # Sync name / email / phone to linked Customer
    if p.customer_id and (body.name or body.email is not None or body.phone is not None):
        c = session.get(Customer, p.customer_id)
        if c:
            if body.name:
                c.name = body.name
            if body.email is not None:
                c.email = body.email or ""
            if body.phone is not None:
                c.phone = body.phone or ""
            session.add(c)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@router.get("/patients/{patient_id}/visits", dependencies=[perm_dep("healthcare.patients")])
def patient_visits(user: CurrentUserDep, session: SessionDep, patient_id: int):
    _patient_or_404(session, user.tenant_id, patient_id)
    return session.exec(
        select(HcOpdVisit)
        .where(HcOpdVisit.tenant_id == user.tenant_id, HcOpdVisit.patient_id == patient_id)
        .order_by(HcOpdVisit.visit_date.desc())
    ).all()


@router.get("/patients/{patient_id}/admissions", dependencies=[perm_dep("healthcare.patients")])
def patient_admissions(user: CurrentUserDep, session: SessionDep, patient_id: int):
    _patient_or_404(session, user.tenant_id, patient_id)
    return session.exec(
        select(HcAdmission)
        .where(HcAdmission.tenant_id == user.tenant_id, HcAdmission.patient_id == patient_id)
        .order_by(HcAdmission.admission_date.desc())
    ).all()


@router.get("/patients/{patient_id}/lab-orders", dependencies=[perm_dep("healthcare.patients")])
def patient_lab_orders(user: CurrentUserDep, session: SessionDep, patient_id: int):
    _patient_or_404(session, user.tenant_id, patient_id)
    return session.exec(
        select(HcLabOrder)
        .where(HcLabOrder.tenant_id == user.tenant_id, HcLabOrder.patient_id == patient_id)
        .order_by(HcLabOrder.order_date.desc())
    ).all()


# ════════════════════════════════════════════════════════════════════════════
# DOCTORS
# ════════════════════════════════════════════════════════════════════════════

class DoctorCreate(BaseModel):
    name: str
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    phone: Optional[str] = None
    opd_fee: Decimal = ZERO
    employee_id: Optional[int] = None
    consultation_account_id: Optional[int] = None


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    phone: Optional[str] = None
    opd_fee: Optional[Decimal] = None
    employee_id: Optional[int] = None
    consultation_account_id: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/doctors", dependencies=[perm_dep("healthcare.opd")])
def list_doctors(user: CurrentUserDep, session: SessionDep, active_only: bool = True):
    q = select(HcDoctor).where(HcDoctor.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(HcDoctor.is_active == True)  # noqa: E712
    return session.exec(q.order_by(HcDoctor.name)).all()


@router.post("/doctors", status_code=201, dependencies=[perm_dep("healthcare.opd", "edit")])
def create_doctor(user: WriteUserDep, session: SessionDep, body: DoctorCreate):
    doctor = HcDoctor(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


@router.get("/doctors/{doctor_id}", dependencies=[perm_dep("healthcare.opd")])
def get_doctor(user: CurrentUserDep, session: SessionDep, doctor_id: int):
    return _doctor_or_404(session, user.tenant_id, doctor_id)


@router.put("/doctors/{doctor_id}", dependencies=[perm_dep("healthcare.opd", "edit")])
def update_doctor(user: WriteUserDep, session: SessionDep, doctor_id: int, body: DoctorUpdate):
    d = _doctor_or_404(session, user.tenant_id, doctor_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


@router.get("/doctors/{doctor_id}/schedule", dependencies=[perm_dep("healthcare.opd")])
def doctor_schedule(user: CurrentUserDep, session: SessionDep, doctor_id: int, date: str):
    """Today's OPD token queue for a doctor."""
    _doctor_or_404(session, user.tenant_id, doctor_id)
    return session.exec(
        select(HcOpdToken)
        .where(
            HcOpdToken.tenant_id == user.tenant_id,
            HcOpdToken.doctor_id == doctor_id,
            HcOpdToken.visit_date == date,
        )
        .order_by(HcOpdToken.token_number)
    ).all()


# ════════════════════════════════════════════════════════════════════════════
# WARDS & BEDS
# ════════════════════════════════════════════════════════════════════════════

class WardCreate(BaseModel):
    name: str
    ward_type: str = "general"
    total_beds: int = 0
    daily_charge: Decimal = ZERO
    revenue_account_id: Optional[int] = None


class WardUpdate(BaseModel):
    name: Optional[str] = None
    ward_type: Optional[str] = None
    total_beds: Optional[int] = None
    daily_charge: Optional[Decimal] = None
    revenue_account_id: Optional[int] = None
    is_active: Optional[bool] = None


class BedCreate(BaseModel):
    bed_number: str
    status: str = "available"


class BedUpdate(BaseModel):
    bed_number: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/wards", dependencies=[perm_dep("healthcare.ipd")])
def list_wards(user: CurrentUserDep, session: SessionDep):
    wards = session.exec(
        select(HcWard).where(HcWard.tenant_id == user.tenant_id, HcWard.is_active == True)  # noqa: E712
    ).all()
    result = []
    for w in wards:
        beds = session.exec(
            select(HcBed).where(HcBed.ward_id == w.id, HcBed.tenant_id == user.tenant_id)
        ).all()
        result.append({
            **w.model_dump(),
            "available_beds": sum(1 for b in beds if b.status == "available"),
            "occupied_beds": sum(1 for b in beds if b.status == "occupied"),
        })
    return result


@router.post("/wards", status_code=201, dependencies=[perm_dep("healthcare.ipd", "edit")])
def create_ward(user: WriteUserDep, session: SessionDep, body: WardCreate):
    ward = HcWard(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(ward)
    session.commit()
    session.refresh(ward)
    return ward


@router.put("/wards/{ward_id}", dependencies=[perm_dep("healthcare.ipd", "edit")])
def update_ward(user: WriteUserDep, session: SessionDep, ward_id: int, body: WardUpdate):
    w = _ward_or_404(session, user.tenant_id, ward_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(w, k, v)
    session.add(w)
    session.commit()
    session.refresh(w)
    return w


@router.get("/wards/{ward_id}/beds", dependencies=[perm_dep("healthcare.ipd")])
def list_beds(user: CurrentUserDep, session: SessionDep, ward_id: int):
    _ward_or_404(session, user.tenant_id, ward_id)
    return session.exec(
        select(HcBed).where(HcBed.ward_id == ward_id, HcBed.tenant_id == user.tenant_id)
        .order_by(HcBed.bed_number)
    ).all()


@router.post("/wards/{ward_id}/beds", status_code=201, dependencies=[perm_dep("healthcare.ipd", "edit")])
def create_bed(user: WriteUserDep, session: SessionDep, ward_id: int, body: BedCreate):
    _ward_or_404(session, user.tenant_id, ward_id)
    bed = HcBed(**body.model_dump(), ward_id=ward_id, tenant_id=user.tenant_id)
    session.add(bed)
    session.commit()
    session.refresh(bed)
    return bed


@router.put("/beds/{bed_id}", dependencies=[perm_dep("healthcare.ipd", "edit")])
def update_bed(user: WriteUserDep, session: SessionDep, bed_id: int, body: BedUpdate):
    b = _bed_or_404(session, user.tenant_id, bed_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(b, k, v)
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


# ════════════════════════════════════════════════════════════════════════════
# PROCEDURE CATALOGUE
# ════════════════════════════════════════════════════════════════════════════

class ProcedureCreate(BaseModel):
    code: str
    name: str
    category: str = "minor"
    standard_fee: Decimal = ZERO
    revenue_account_id: Optional[int] = None


class ProcedureUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    standard_fee: Optional[Decimal] = None
    revenue_account_id: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/procedures/catalog", dependencies=[perm_dep("healthcare.procedures")])
def list_procedures(user: CurrentUserDep, session: SessionDep, active_only: bool = True):
    q = select(HcProcedureCatalog).where(HcProcedureCatalog.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(HcProcedureCatalog.is_active == True)  # noqa: E712
    return session.exec(q.order_by(HcProcedureCatalog.name)).all()


@router.post("/procedures/catalog", status_code=201, dependencies=[perm_dep("healthcare.procedures", "edit")])
def create_procedure(user: WriteUserDep, session: SessionDep, body: ProcedureCreate):
    proc = HcProcedureCatalog(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(proc)
    session.commit()
    session.refresh(proc)
    return proc


@router.put("/procedures/catalog/{proc_id}", dependencies=[perm_dep("healthcare.procedures", "edit")])
def update_procedure(user: WriteUserDep, session: SessionDep, proc_id: int, body: ProcedureUpdate):
    p = session.exec(
        select(HcProcedureCatalog).where(
            HcProcedureCatalog.id == proc_id, HcProcedureCatalog.tenant_id == user.tenant_id
        )
    ).first()
    if not p:
        raise HTTPException(404, "Procedure not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


# ════════════════════════════════════════════════════════════════════════════
# OPD TOKENS
# ════════════════════════════════════════════════════════════════════════════

class TokenCreate(BaseModel):
    doctor_id: int
    visit_date: str
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None


@router.get("/opd/tokens", dependencies=[perm_dep("healthcare.opd")])
def list_tokens(
    user: CurrentUserDep, session: SessionDep,
    doctor_id: Optional[int] = None,
    date: Optional[str] = None,
    status: Optional[str] = None,
):
    q = select(HcOpdToken).where(HcOpdToken.tenant_id == user.tenant_id)
    if doctor_id:
        q = q.where(HcOpdToken.doctor_id == doctor_id)
    if date:
        q = q.where(HcOpdToken.visit_date == date)
    if status:
        q = q.where(HcOpdToken.status == status)
    return session.exec(q.order_by(HcOpdToken.visit_date.desc(), HcOpdToken.token_number)).all()


@router.post("/opd/tokens", status_code=201, dependencies=[perm_dep("healthcare.opd", "edit")])
def create_token(user: WriteUserDep, session: SessionDep, body: TokenCreate):
    _doctor_or_404(session, user.tenant_id, body.doctor_id)

    # Next token number for this doctor+date (reset daily)
    last = session.exec(
        select(func.max(HcOpdToken.token_number)).where(
            HcOpdToken.tenant_id == user.tenant_id,
            HcOpdToken.doctor_id == body.doctor_id,
            HcOpdToken.visit_date == body.visit_date,
        )
    ).one()
    token_number = (last or 0) + 1

    token = HcOpdToken(
        tenant_id=user.tenant_id,
        doctor_id=body.doctor_id,
        patient_id=body.patient_id,
        patient_name=body.patient_name,
        visit_date=body.visit_date,
        token_number=token_number,
        created_at=datetime.utcnow(),
    )
    session.add(token)
    session.commit()
    session.refresh(token)
    return token


@router.put("/opd/tokens/{token_id}/call", dependencies=[perm_dep("healthcare.opd", "edit")])
def call_token(user: WriteUserDep, session: SessionDep, token_id: int):
    t = session.exec(
        select(HcOpdToken).where(HcOpdToken.id == token_id, HcOpdToken.tenant_id == user.tenant_id)
    ).first()
    if not t:
        raise HTTPException(404, "Token not found")
    t.status = "called"
    session.add(t)
    session.commit()
    return t


@router.put("/opd/tokens/{token_id}/cancel", dependencies=[perm_dep("healthcare.opd", "edit")])
def cancel_token(user: WriteUserDep, session: SessionDep, token_id: int):
    t = session.exec(
        select(HcOpdToken).where(HcOpdToken.id == token_id, HcOpdToken.tenant_id == user.tenant_id)
    ).first()
    if not t:
        raise HTTPException(404, "Token not found")
    t.status = "cancelled"
    session.add(t)
    session.commit()
    return t


# ════════════════════════════════════════════════════════════════════════════
# OPD VISITS
# ════════════════════════════════════════════════════════════════════════════

class VitalsModel(BaseModel):
    bp: Optional[str] = None
    temp: Optional[str] = None
    pulse: Optional[str] = None
    weight: Optional[str] = None
    spo2: Optional[str] = None


class VisitCreate(BaseModel):
    patient_id: int
    doctor_id: int
    visit_date: str
    token_id: Optional[int] = None
    visit_type: str = "first"
    chief_complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    vitals: Optional[VitalsModel] = None
    advice: Optional[str] = None
    follow_up_date: Optional[str] = None


class VisitUpdate(BaseModel):
    chief_complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    vitals: Optional[VitalsModel] = None
    advice: Optional[str] = None
    follow_up_date: Optional[str] = None


@router.get("/opd/visits", dependencies=[perm_dep("healthcare.opd")])
def list_visits(
    user: CurrentUserDep, session: SessionDep,
    doctor_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    q = select(HcOpdVisit).where(HcOpdVisit.tenant_id == user.tenant_id)
    if doctor_id:
        q = q.where(HcOpdVisit.doctor_id == doctor_id)
    if from_date:
        q = q.where(HcOpdVisit.visit_date >= from_date)
    if to_date:
        q = q.where(HcOpdVisit.visit_date <= to_date)
    return session.exec(q.order_by(HcOpdVisit.visit_date.desc()).offset(skip).limit(limit)).all()


@router.post("/opd/visits", status_code=201, dependencies=[perm_dep("healthcare.opd", "edit")])
def create_visit(user: WriteUserDep, session: SessionDep, body: VisitCreate):
    _patient_or_404(session, user.tenant_id, body.patient_id)
    _doctor_or_404(session, user.tenant_id, body.doctor_id)

    vitals_json = json.dumps(body.vitals.model_dump()) if body.vitals else None
    visit = HcOpdVisit(
        tenant_id=user.tenant_id,
        patient_id=body.patient_id,
        doctor_id=body.doctor_id,
        visit_date=body.visit_date,
        token_id=body.token_id,
        visit_type=body.visit_type,
        chief_complaint=body.chief_complaint,
        diagnosis=body.diagnosis,
        vitals_json=vitals_json,
        advice=body.advice,
        follow_up_date=body.follow_up_date,
        created_by_id=user.id,
        created_at=datetime.utcnow(),
    )
    session.add(visit)
    # Mark token as visited
    if body.token_id:
        tok = session.get(HcOpdToken, body.token_id)
        if tok:
            tok.status = "visited"
            session.add(tok)
    session.commit()
    session.refresh(visit)
    return visit


@router.get("/opd/visits/{visit_id}", dependencies=[perm_dep("healthcare.opd")])
def get_visit(user: CurrentUserDep, session: SessionDep, visit_id: int):
    v = session.exec(
        select(HcOpdVisit).where(HcOpdVisit.id == visit_id, HcOpdVisit.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(404, "Visit not found")
    return v


@router.put("/opd/visits/{visit_id}", dependencies=[perm_dep("healthcare.opd", "edit")])
def update_visit(user: WriteUserDep, session: SessionDep, visit_id: int, body: VisitUpdate):
    v = session.exec(
        select(HcOpdVisit).where(HcOpdVisit.id == visit_id, HcOpdVisit.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(404, "Visit not found")
    if body.chief_complaint is not None:
        v.chief_complaint = body.chief_complaint
    if body.diagnosis is not None:
        v.diagnosis = body.diagnosis
    if body.vitals is not None:
        v.vitals_json = json.dumps(body.vitals.model_dump())
    if body.advice is not None:
        v.advice = body.advice
    if body.follow_up_date is not None:
        v.follow_up_date = body.follow_up_date
    session.add(v)
    session.commit()
    session.refresh(v)
    return v


@router.post("/opd/visits/{visit_id}/bill", dependencies=[perm_dep("healthcare.opd", "edit")])
def bill_visit(user: WriteUserDep, session: SessionDep, visit_id: int):
    """Post OPD consultation invoice. Idempotent — returns existing if already billed."""
    v = session.exec(
        select(HcOpdVisit).where(HcOpdVisit.id == visit_id, HcOpdVisit.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(404, "Visit not found")
    if v.transaction_id:
        return {"message": "Already billed", "transaction_id": v.transaction_id}

    patient = _patient_or_404(session, user.tenant_id, v.patient_id)
    doctor = _doctor_or_404(session, user.tenant_id, v.doctor_id)

    # Resolve OPD fee from doctor or default
    fee = doctor.opd_fee or ZERO

    revenue_code = "4101" if v.visit_type == "follow_up" else "4100"
    rev_acc = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id, Account.code == revenue_code)
    ).first()
    if rev_acc and doctor.consultation_account_id:
        revenue_code_to_use = revenue_code
    elif doctor.consultation_account_id:
        acc = session.get(Account, doctor.consultation_account_id)
        revenue_code_to_use = acc.code if acc else revenue_code
    else:
        revenue_code_to_use = revenue_code

    txn = post_opd_consultation(
        session, user,
        amount=fee,
        date=v.visit_date,
        patient_name=patient.name,
        doctor_name=doctor.name,
        revenue_account_code=revenue_code_to_use,
        customer_id=patient.customer_id,
    )
    v.transaction_id = txn.id
    session.add(v)
    session.commit()
    return {"message": "Billed", "transaction_id": txn.id, "amount": str(fee)}


# ════════════════════════════════════════════════════════════════════════════
# PRESCRIPTIONS
# ════════════════════════════════════════════════════════════════════════════

class PrescriptionCreate(BaseModel):
    notes: Optional[str] = None


class PrescriptionItemCreate(BaseModel):
    medicine_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: str = "oral"
    instructions: Optional[str] = None
    qty: Decimal = Decimal("1")
    product_id: Optional[int] = None


class PrescriptionItemUpdate(BaseModel):
    medicine_name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    instructions: Optional[str] = None
    qty: Optional[Decimal] = None
    product_id: Optional[int] = None


@router.post("/opd/visits/{visit_id}/prescriptions", status_code=201,
             dependencies=[perm_dep("healthcare.opd", "edit")])
def create_prescription(user: WriteUserDep, session: SessionDep, visit_id: int,
                        body: PrescriptionCreate):
    v = session.exec(
        select(HcOpdVisit).where(HcOpdVisit.id == visit_id, HcOpdVisit.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(404, "Visit not found")
    from datetime import date
    rx = HcPrescription(
        tenant_id=user.tenant_id,
        visit_id=visit_id,
        patient_id=v.patient_id,
        doctor_id=v.doctor_id,
        prescribed_date=v.visit_date,
        notes=body.notes,
        created_at=datetime.utcnow(),
    )
    session.add(rx)
    session.commit()
    session.refresh(rx)
    return rx


@router.get("/opd/visits/{visit_id}/prescriptions", dependencies=[perm_dep("healthcare.opd")])
def get_prescriptions(user: CurrentUserDep, session: SessionDep, visit_id: int):
    rxs = session.exec(
        select(HcPrescription).where(
            HcPrescription.visit_id == visit_id, HcPrescription.tenant_id == user.tenant_id
        )
    ).all()
    result = []
    for rx in rxs:
        items = session.exec(
            select(HcPrescriptionItem).where(HcPrescriptionItem.prescription_id == rx.id)
        ).all()
        result.append({**rx.model_dump(), "items": items})
    return result


@router.post("/prescriptions/{rx_id}/items", status_code=201,
             dependencies=[perm_dep("healthcare.opd", "edit")])
def add_prescription_item(user: WriteUserDep, session: SessionDep, rx_id: int,
                          body: PrescriptionItemCreate):
    rx = session.exec(
        select(HcPrescription).where(
            HcPrescription.id == rx_id, HcPrescription.tenant_id == user.tenant_id
        )
    ).first()
    if not rx:
        raise HTTPException(404, "Prescription not found")
    item = HcPrescriptionItem(**body.model_dump(), prescription_id=rx_id)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/prescriptions/{rx_id}/items/{item_id}",
            dependencies=[perm_dep("healthcare.opd", "edit")])
def update_prescription_item(user: WriteUserDep, session: SessionDep,
                              rx_id: int, item_id: int, body: PrescriptionItemUpdate):
    item = session.exec(
        select(HcPrescriptionItem).where(
            HcPrescriptionItem.id == item_id, HcPrescriptionItem.prescription_id == rx_id
        )
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(item, k, v)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/prescriptions/{rx_id}/items/{item_id}", status_code=204,
               dependencies=[perm_dep("healthcare.opd", "edit")])
def delete_prescription_item(user: WriteUserDep, session: SessionDep, rx_id: int, item_id: int):
    item = session.exec(
        select(HcPrescriptionItem).where(
            HcPrescriptionItem.id == item_id, HcPrescriptionItem.prescription_id == rx_id
        )
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    session.delete(item)
    session.commit()


# ════════════════════════════════════════════════════════════════════════════
# IPD ADMISSIONS
# ════════════════════════════════════════════════════════════════════════════

class AdmissionCreate(BaseModel):
    patient_id: int
    doctor_id: int
    ward_id: int
    bed_id: int
    admission_date: str
    diagnosis: Optional[str] = None
    admission_type: str = "planned"
    deposit_amount: Decimal = ZERO
    cash_account_code: str = "1000"


class ChargeCreate(BaseModel):
    charge_date: str
    charge_type: str = "bed"
    description: str
    amount: Decimal
    procedure_id: Optional[int] = None


@router.get("/admissions", dependencies=[perm_dep("healthcare.ipd")])
def list_admissions(
    user: CurrentUserDep, session: SessionDep,
    status: Optional[str] = None,
    ward_id: Optional[int] = None,
    skip: int = 0, limit: int = 50,
):
    q = select(HcAdmission).where(HcAdmission.tenant_id == user.tenant_id)
    if status:
        q = q.where(HcAdmission.status == status)
    if ward_id:
        q = q.where(HcAdmission.ward_id == ward_id)
    return session.exec(q.order_by(HcAdmission.admission_date.desc()).offset(skip).limit(limit)).all()


@router.post("/admissions", status_code=201, dependencies=[perm_dep("healthcare.ipd", "edit")])
def create_admission(user: WriteUserDep, session: SessionDep, body: AdmissionCreate):
    _patient_or_404(session, user.tenant_id, body.patient_id)
    _doctor_or_404(session, user.tenant_id, body.doctor_id)
    _ward_or_404(session, user.tenant_id, body.ward_id)
    bed = _bed_or_404(session, user.tenant_id, body.bed_id)

    if bed.status == "occupied":
        raise HTTPException(400, "Bed is already occupied")

    adm_number = next_number(session, user.tenant_id, "hc_adm", "ADM",
                             fmt="{prefix}-{YYYY}{seq:04d}")

    admission = HcAdmission(
        tenant_id=user.tenant_id,
        patient_id=body.patient_id,
        doctor_id=body.doctor_id,
        ward_id=body.ward_id,
        bed_id=body.bed_id,
        admission_number=adm_number,
        admission_date=body.admission_date,
        diagnosis=body.diagnosis,
        admission_type=body.admission_type,
        deposit_amount=body.deposit_amount,
        created_by_id=user.id,
        created_at=datetime.utcnow(),
    )
    session.add(admission)
    session.flush()

    # Post deposit GL if amount > 0
    if body.deposit_amount > ZERO:
        patient = _patient_or_404(session, user.tenant_id, body.patient_id)
        txn = post_ipd_deposit(
            session, user,
            amount=body.deposit_amount,
            date=body.admission_date,
            patient_name=patient.name,
            admission_number=adm_number,
            cash_account_code=body.cash_account_code,
        )
        admission.deposit_transaction_id = txn.id

    # Mark bed as occupied
    bed.status = "occupied"
    bed.current_admission_id = admission.id
    session.add(bed)

    session.commit()
    session.refresh(admission)
    return admission


@router.get("/admissions/{admission_id}", dependencies=[perm_dep("healthcare.ipd")])
def get_admission(user: CurrentUserDep, session: SessionDep, admission_id: int):
    adm = session.exec(
        select(HcAdmission).where(
            HcAdmission.id == admission_id, HcAdmission.tenant_id == user.tenant_id
        )
    ).first()
    if not adm:
        raise HTTPException(404, "Admission not found")
    charges = session.exec(
        select(HcAdmissionCharge).where(HcAdmissionCharge.admission_id == admission_id)
    ).all()
    return {
        **adm.model_dump(),
        "charges": charges,
        "total_charges": sum(c.amount for c in charges),
    }


@router.post("/admissions/{admission_id}/charges", status_code=201,
             dependencies=[perm_dep("healthcare.ipd", "edit")])
def add_charge(user: WriteUserDep, session: SessionDep, admission_id: int, body: ChargeCreate):
    adm = session.exec(
        select(HcAdmission).where(
            HcAdmission.id == admission_id, HcAdmission.tenant_id == user.tenant_id
        )
    ).first()
    if not adm:
        raise HTTPException(404, "Admission not found")
    if adm.status == "discharged":
        raise HTTPException(400, "Cannot add charges to a discharged admission")

    charge = HcAdmissionCharge(
        tenant_id=user.tenant_id,
        admission_id=admission_id,
        charge_date=body.charge_date,
        charge_type=body.charge_type,
        description=body.description,
        amount=body.amount,
        procedure_id=body.procedure_id,
        created_by_id=user.id,
        created_at=datetime.utcnow(),
    )
    session.add(charge)
    session.commit()
    session.refresh(charge)
    return charge


@router.delete("/admissions/{admission_id}/charges/{charge_id}", status_code=204,
               dependencies=[perm_dep("healthcare.ipd", "edit")])
def delete_charge(user: WriteUserDep, session: SessionDep, admission_id: int, charge_id: int):
    adm = session.exec(
        select(HcAdmission).where(
            HcAdmission.id == admission_id, HcAdmission.tenant_id == user.tenant_id
        )
    ).first()
    if not adm or adm.status == "discharged":
        raise HTTPException(400, "Cannot modify a discharged admission")
    charge = session.exec(
        select(HcAdmissionCharge).where(
            HcAdmissionCharge.id == charge_id, HcAdmissionCharge.admission_id == admission_id
        )
    ).first()
    if not charge:
        raise HTTPException(404, "Charge not found")
    session.delete(charge)
    session.commit()


@router.post("/admissions/{admission_id}/discharge",
             dependencies=[perm_dep("healthcare.ipd", "edit")])
def discharge_patient(user: WriteUserDep, session: SessionDep, admission_id: int,
                      discharge_date: str = ""):
    """Roll up all charges into one invoice, settle deposit, free the bed."""
    if not discharge_date:
        discharge_date = date.today().isoformat()
    adm = session.exec(
        select(HcAdmission).where(
            HcAdmission.id == admission_id, HcAdmission.tenant_id == user.tenant_id
        )
    ).first()
    if not adm:
        raise HTTPException(404, "Admission not found")
    if adm.status == "discharged":
        raise HTTPException(400, "Already discharged")

    patient = _patient_or_404(session, user.tenant_id, adm.patient_id)
    charges = session.exec(
        select(HcAdmissionCharge).where(HcAdmissionCharge.admission_id == admission_id)
    ).all()
    total = sum(c.amount for c in charges)

    if total > ZERO or adm.deposit_amount > ZERO:
        charge_breakdown = {c.charge_type: str(c.amount) for c in charges}
        txn = post_discharge_bill(
            session, user,
            total_charges=total,
            deposit_amount=adm.deposit_amount,
            date=discharge_date,
            patient_name=patient.name,
            admission_number=adm.admission_number,
            customer_id=patient.customer_id,
            charge_breakdown=charge_breakdown,
        )
        adm.discharge_invoice_id = txn.id

    adm.status = "discharged"
    adm.discharge_date = discharge_date

    # Free the bed
    bed = session.get(HcBed, adm.bed_id)
    if bed:
        bed.status = "available"
        bed.current_admission_id = None
        session.add(bed)

    session.add(adm)
    session.commit()
    return {
        "message": "Discharged",
        "admission_number": adm.admission_number,
        "total_charges": str(total),
        "deposit_amount": str(adm.deposit_amount),
        "balance_due": str(max(total - adm.deposit_amount, ZERO)),
    }


# ════════════════════════════════════════════════════════════════════════════
# LAB TESTS CATALOGUE
# ════════════════════════════════════════════════════════════════════════════

class LabTestCreate(BaseModel):
    code: str
    name: str
    category: str = "other"
    normal_range: Optional[str] = None
    unit: Optional[str] = None
    standard_fee: Decimal = ZERO
    revenue_account_id: Optional[int] = None
    product_id: Optional[int] = None
    qty_per_test: Decimal = Decimal("1")


class LabTestUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    normal_range: Optional[str] = None
    unit: Optional[str] = None
    standard_fee: Optional[Decimal] = None
    revenue_account_id: Optional[int] = None
    product_id: Optional[int] = None
    qty_per_test: Optional[Decimal] = None
    is_active: Optional[bool] = None


@router.get("/lab/tests", dependencies=[perm_dep("healthcare.lab")])
def list_lab_tests(user: CurrentUserDep, session: SessionDep, active_only: bool = True):
    q = select(HcLabTest).where(HcLabTest.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(HcLabTest.is_active == True)  # noqa: E712
    return session.exec(q.order_by(HcLabTest.category, HcLabTest.name)).all()


@router.post("/lab/tests", status_code=201, dependencies=[perm_dep("healthcare.lab", "edit")])
def create_lab_test(user: WriteUserDep, session: SessionDep, body: LabTestCreate):
    t = HcLabTest(**body.model_dump(), tenant_id=user.tenant_id, created_at=datetime.utcnow())
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@router.put("/lab/tests/{test_id}", dependencies=[perm_dep("healthcare.lab", "edit")])
def update_lab_test(user: WriteUserDep, session: SessionDep, test_id: int, body: LabTestUpdate):
    t = session.exec(
        select(HcLabTest).where(HcLabTest.id == test_id, HcLabTest.tenant_id == user.tenant_id)
    ).first()
    if not t:
        raise HTTPException(404, "Test not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(t, k, v)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


# ════════════════════════════════════════════════════════════════════════════
# LAB ORDERS
# ════════════════════════════════════════════════════════════════════════════

class LabOrderCreate(BaseModel):
    patient_id: int
    order_date: str
    source: str = "walkin"
    doctor_id: Optional[int] = None
    admission_id: Optional[int] = None
    test_ids: list[int] = []


class ResultEntry(BaseModel):
    result_value: Optional[str] = None
    result_unit: Optional[str] = None
    reference_range: Optional[str] = None
    is_abnormal: bool = False


@router.get("/lab/orders", dependencies=[perm_dep("healthcare.lab")])
def list_lab_orders(
    user: CurrentUserDep, session: SessionDep,
    source: Optional[str] = None,
    status: Optional[str] = None,
    patient_id: Optional[int] = None,
    admission_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    q = select(HcLabOrder).where(HcLabOrder.tenant_id == user.tenant_id)
    if source:
        q = q.where(HcLabOrder.source == source)
    if status:
        q = q.where(HcLabOrder.status == status)
    if patient_id is not None:
        q = q.where(HcLabOrder.patient_id == patient_id)
    if admission_id is not None:
        q = q.where(HcLabOrder.admission_id == admission_id)
    if from_date:
        q = q.where(HcLabOrder.order_date >= from_date)
    if to_date:
        q = q.where(HcLabOrder.order_date <= to_date)
    return session.exec(q.order_by(HcLabOrder.order_date.desc()).offset(skip).limit(limit)).all()


@router.post("/lab/orders", status_code=201, dependencies=[perm_dep("healthcare.lab", "edit")])
def create_lab_order(user: WriteUserDep, session: SessionDep, body: LabOrderCreate):
    _patient_or_404(session, user.tenant_id, body.patient_id)
    order_number = next_number(session, user.tenant_id, "hc_lab", "LO",
                               fmt="{prefix}-{YYYY}{seq:04d}")
    order = HcLabOrder(
        tenant_id=user.tenant_id,
        patient_id=body.patient_id,
        doctor_id=body.doctor_id,
        admission_id=body.admission_id,
        order_number=order_number,
        order_date=body.order_date,
        source=body.source,
        created_by_id=user.id,
        created_at=datetime.utcnow(),
    )
    session.add(order)
    session.flush()

    # Add test items
    for test_id in body.test_ids:
        test = session.exec(
            select(HcLabTest).where(HcLabTest.id == test_id, HcLabTest.tenant_id == user.tenant_id)
        ).first()
        if test:
            item = HcLabOrderItem(lab_order_id=order.id, test_id=test_id, fee=test.standard_fee)
            session.add(item)

    session.commit()
    session.refresh(order)
    return order


@router.get("/lab/orders/{order_id}", dependencies=[perm_dep("healthcare.lab")])
def get_lab_order(user: CurrentUserDep, session: SessionDep, order_id: int):
    order = session.exec(
        select(HcLabOrder).where(
            HcLabOrder.id == order_id, HcLabOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not order:
        raise HTTPException(404, "Lab order not found")
    return _serialize_lab_order(session, order)


@router.put("/lab/orders/{order_id}/items/{item_id}/result",
            dependencies=[perm_dep("healthcare.lab", "edit")])
def enter_result(user: WriteUserDep, session: SessionDep,
                 order_id: int, item_id: int, body: ResultEntry):
    item = session.exec(
        select(HcLabOrderItem).where(
            HcLabOrderItem.id == item_id, HcLabOrderItem.lab_order_id == order_id
        )
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    item.result_value = body.result_value
    item.result_unit = body.result_unit
    item.reference_range = body.reference_range
    # Prefer range / Pos-Neg classification; fall back to tech checkbox
    flag = _classify_lab_flag(
        body.result_value,
        reference_range=body.reference_range,
        is_abnormal=body.is_abnormal,
    )
    item.is_abnormal = flag["code"] in ("high", "low", "positive", "abnormal")
    item.resulted_at = datetime.utcnow()
    item.resulted_by_id = user.id
    session.add(item)

    # Auto-update order status to resulted if all items have results
    order = session.get(HcLabOrder, order_id)
    all_items = session.exec(
        select(HcLabOrderItem).where(HcLabOrderItem.lab_order_id == order_id)
    ).all()
    if all(i.resulted_at for i in all_items) and order:
        order.status = "resulted"
        session.add(order)

    session.commit()
    return item


@router.put("/lab/orders/{order_id}/deliver", dependencies=[perm_dep("healthcare.lab", "edit")])
def deliver_results(user: WriteUserDep, session: SessionDep, order_id: int):
    order = session.exec(
        select(HcLabOrder).where(
            HcLabOrder.id == order_id, HcLabOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not order:
        raise HTTPException(404, "Lab order not found")
    order.status = "delivered"
    session.add(order)
    session.commit()
    return order


_CATEGORY_LABELS = {
    "hematology": "Hematology",
    "biochemistry": "Biochemistry",
    "microbiology": "Microbiology",
    "radiology": "Radiology",
    "other": "Other",
}


def _lab_pdf_context(session: Session, order: HcLabOrder) -> dict:
    """Build template context from a serialized lab order."""
    from services.lab_pdf_charts import serial_trends_for_items

    payload = _serialize_lab_order(session, order)
    items = payload.get("items") or []
    if not items or any(not i.get("resulted_at") for i in items):
        raise HTTPException(400, "All test results must be entered before generating PDF")

    grouped: dict[str, list] = {}
    for item in items:
        cat = item.get("category") or "other"
        label = _CATEGORY_LABELS.get(cat, cat)
        row = dict(item)
        ra = item.get("resulted_at")
        if isinstance(ra, datetime):
            row["resulted_at_display"] = ra.date().isoformat()
        elif isinstance(ra, str) and ra:
            row["resulted_at_display"] = ra[:10]
        else:
            row["resulted_at_display"] = None
        # Compact flag display for PDF (symbol, not long label)
        flag = item.get("flag") or {}
        row["flag_symbol"] = flag.get("symbol") or ("!" if item.get("is_abnormal") else "N")
        prev = item.get("previous_result")
        row["previous_value"] = (prev or {}).get("result_value") if prev else None
        grouped.setdefault(label, []).append(row)

    sample = payload.get("sample")
    if sample and sample.get("collected_at"):
        ca = sample["collected_at"]
        sample = {**sample, "collected_at": ca[:10] if isinstance(ca, str) else ca}

    serial = serial_trends_for_items(items)

    return {
        "order_number": payload.get("order_number"),
        "order_date": payload.get("order_date"),
        "status": payload.get("status"),
        "source": (payload.get("source") or "").replace("_", " "),
        "patient": payload.get("patient"),
        "doctor": payload.get("doctor"),
        "sample": sample,
        "grouped_items": list(grouped.items()),
        "serial_trends": serial,
        "has_serial_trends": bool(serial["chartable"] or serial["table_only"]),
    }


def _company_branding(session: Session, tenant_id: int) -> tuple[str, str]:
    settings = {
        s.key: s.value
        for s in session.exec(select(Settings).where(Settings.tenant_id == tenant_id)).all()
    }
    return settings.get("company_name", "Easy-Books"), settings.get("business_tagline", "")


def _phone_digits(phone: str | None) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    return digits


def _resolve_patient_email(session: Session, patient: HcPatient) -> str | None:
    if patient.email and patient.email.strip():
        return patient.email.strip()
    if patient.customer_id:
        cust = session.get(Customer, patient.customer_id)
        if cust and cust.email and cust.email.strip():
            return cust.email.strip()
    return None


def _mint_or_reuse_patient_portal(session, tenant_id: int, patient_id: int) -> str:
    """Mint a fresh patient portal token for share links."""
    from routers.portal import mint_portal_token

    return mint_portal_token(
        session, tenant_id, "patient", patient_id, days=90,
        permissions=["view_lab_reports"],
    )


@router.get("/lab/orders/{order_id}/pdf", dependencies=[perm_dep("healthcare.lab")])
def lab_order_pdf(user: CurrentUserDep, session: SessionDep, order_id: int):
    order = session.exec(
        select(HcLabOrder).where(
            HcLabOrder.id == order_id, HcLabOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not order:
        raise HTTPException(404, "Lab order not found")
    report = _lab_pdf_context(session, order)
    company, tagline = _company_branding(session, user.tenant_id)
    from services.pdf import render_lab_report_pdf
    pdf = render_lab_report_pdf(report, company, tagline)
    filename = f"{order.order_number}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class LabPublishBody(BaseModel):
    channels: list[str] = ["portal"]
    mark_delivered: bool = True


@router.post("/lab/orders/{order_id}/publish", dependencies=[perm_dep("healthcare.lab", "edit")])
def publish_lab_order(
    user: WriteUserDep, session: SessionDep, order_id: int, body: LabPublishBody,
):
    """Publish resulted lab report via portal link, email, and/or WhatsApp (wa.me)."""
    import os
    from urllib.parse import quote
    from services.email import queue_email

    order = session.exec(
        select(HcLabOrder).where(
            HcLabOrder.id == order_id, HcLabOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not order:
        raise HTTPException(404, "Lab order not found")

    # Validate results complete (same gate as PDF)
    _lab_pdf_context(session, order)

    channels = {c.lower() for c in (body.channels or ["portal"])}
    if not channels:
        channels = {"portal"}
    allowed = {"portal", "email", "whatsapp"}
    unknown = channels - allowed
    if unknown:
        raise HTTPException(400, f"Unknown channels: {sorted(unknown)}")

    patient = _patient_or_404(session, user.tenant_id, order.patient_id)
    front = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").rstrip("/")
    raw_token = _mint_or_reuse_patient_portal(session, user.tenant_id, patient.id)
    portal_path = f"/portal/{raw_token}"
    portal_url = f"{front}{portal_path}"

    emailed = False
    whatsapp_url = None

    if "email" in channels:
        to = _resolve_patient_email(session, patient)
        if not to:
            raise HTTPException(
                400,
                "No email on patient or linked customer — add an email before publishing via email",
            )
        company, _tag = _company_branding(session, user.tenant_id)
        queue_email(
            to,
            f"Lab report ready — {order.order_number}",
            (
                f"<p>Dear {patient.name},</p>"
                f"<p>Your laboratory report <strong>{order.order_number}</strong> "
                f"from {company} is ready.</p>"
                f'<p><a href="{portal_url}">View your report and download PDF</a></p>'
                f"<p>This link is private — do not share it publicly.</p>"
            ),
        )
        emailed = True

    if "whatsapp" in channels:
        digits = _phone_digits(patient.phone)
        if not digits:
            raise HTTPException(400, "Patient has no phone number for WhatsApp share")
        text = (
            f"Your lab report {order.order_number} is ready. "
            f"View and download: {portal_url}"
        )
        whatsapp_url = f"https://wa.me/{digits}?text={quote(text)}"

    if body.mark_delivered and order.status == "resulted":
        order.status = "delivered"
        session.add(order)
        session.commit()

    log_audit(session, user, "PUBLISH", "hc_lab_order", order.id, {
        "order_number": order.order_number,
        "channels": sorted(channels),
        "emailed": emailed,
    })

    return {
        "portal_url": portal_url,
        "portal_path": portal_path,
        "whatsapp_url": whatsapp_url,
        "emailed": emailed,
        "status": order.status,
    }


@router.post("/lab/orders/{order_id}/bill", dependencies=[perm_dep("healthcare.lab", "edit")])
def bill_lab_order(user: WriteUserDep, session: SessionDep, order_id: int):
    """Bill a walk-in/OPD lab order. Idempotent."""
    order = session.exec(
        select(HcLabOrder).where(
            HcLabOrder.id == order_id, HcLabOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not order:
        raise HTTPException(404, "Lab order not found")
    if order.transaction_id:
        return {"message": "Already billed", "transaction_id": order.transaction_id}

    patient = _patient_or_404(session, user.tenant_id, order.patient_id)
    items = session.exec(
        select(HcLabOrderItem).where(HcLabOrderItem.lab_order_id == order_id)
    ).all()
    total = sum(i.fee for i in items)

    txn = post_lab_order(
        session, user,
        amount=total,
        date=order.order_date,
        patient_name=patient.name,
        order_number=order.order_number,
        customer_id=patient.customer_id,
    )
    order.transaction_id = txn.id
    session.add(order)
    session.commit()
    return {"message": "Billed", "transaction_id": txn.id, "amount": str(total)}


# ════════════════════════════════════════════════════════════════════════════
# SAMPLE COLLECTION
# ════════════════════════════════════════════════════════════════════════════

class SampleCollectBody(BaseModel):
    collected_at: Optional[str] = None
    collection_point: str = "lab"
    specimen_type: str = "blood"
    barcode: Optional[str] = None
    notes: Optional[str] = None


@router.get("/lab/collections", dependencies=[perm_dep("healthcare.lab")])
def list_collections(user: CurrentUserDep, session: SessionDep, status: Optional[str] = None):
    q = select(HcSampleCollection).where(HcSampleCollection.tenant_id == user.tenant_id)
    if status:
        q = q.where(HcSampleCollection.status == status)
    return session.exec(q.order_by(HcSampleCollection.collected_at.desc())).all()


@router.post("/lab/orders/{order_id}/collect", status_code=201,
             dependencies=[perm_dep("healthcare.lab", "edit")])
def collect_sample(user: WriteUserDep, session: SessionDep, order_id: int, body: SampleCollectBody):
    order = session.exec(
        select(HcLabOrder).where(
            HcLabOrder.id == order_id, HcLabOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not order:
        raise HTTPException(404, "Lab order not found")

    sample = HcSampleCollection(
        tenant_id=user.tenant_id,
        lab_order_id=order_id,
        collected_by_id=user.id,
        collected_at=datetime.utcnow() if not body.collected_at else datetime.fromisoformat(body.collected_at),
        collection_point=body.collection_point,
        specimen_type=body.specimen_type,
        barcode=body.barcode,
        notes=body.notes,
        status="collected",
    )
    session.add(sample)

    order.status = "sample_collected"
    session.add(order)
    session.commit()
    session.refresh(sample)
    return sample


@router.put("/lab/collections/{collection_id}/dispatch",
            dependencies=[perm_dep("healthcare.lab", "edit")])
def dispatch_sample(user: WriteUserDep, session: SessionDep, collection_id: int):
    s = session.exec(
        select(HcSampleCollection).where(
            HcSampleCollection.id == collection_id, HcSampleCollection.tenant_id == user.tenant_id
        )
    ).first()
    if not s:
        raise HTTPException(404, "Sample collection not found")
    s.status = "dispatched"
    session.add(s)
    session.commit()
    return s


@router.put("/lab/collections/{collection_id}/receive",
            dependencies=[perm_dep("healthcare.lab", "edit")])
def receive_sample(user: WriteUserDep, session: SessionDep, collection_id: int):
    s = session.exec(
        select(HcSampleCollection).where(
            HcSampleCollection.id == collection_id, HcSampleCollection.tenant_id == user.tenant_id
        )
    ).first()
    if not s:
        raise HTTPException(404, "Sample collection not found")
    s.status = "received"
    session.add(s)
    # Also advance lab order to processing
    order = session.get(HcLabOrder, s.lab_order_id)
    if order and order.status == "sample_collected":
        order.status = "processing"
        session.add(order)
    session.commit()
    return s


# ════════════════════════════════════════════════════════════════════════════
# PROCEDURE ORDERS
# ════════════════════════════════════════════════════════════════════════════

class ProcedureOrderCreate(BaseModel):
    patient_id: int
    procedure_id: int
    order_date: str
    doctor_id: Optional[int] = None
    admission_id: Optional[int] = None
    notes: Optional[str] = None


@router.get("/procedure-orders", dependencies=[perm_dep("healthcare.procedures")])
def list_procedure_orders(
    user: CurrentUserDep, session: SessionDep,
    status: Optional[str] = None, skip: int = 0, limit: int = 50,
):
    q = select(HcProcedureOrder).where(HcProcedureOrder.tenant_id == user.tenant_id)
    if status:
        q = q.where(HcProcedureOrder.status == status)
    return session.exec(q.order_by(HcProcedureOrder.order_date.desc()).offset(skip).limit(limit)).all()


@router.post("/procedure-orders", status_code=201,
             dependencies=[perm_dep("healthcare.procedures", "edit")])
def create_procedure_order(user: WriteUserDep, session: SessionDep, body: ProcedureOrderCreate):
    patient = _patient_or_404(session, user.tenant_id, body.patient_id)
    proc = session.exec(
        select(HcProcedureCatalog).where(
            HcProcedureCatalog.id == body.procedure_id,
            HcProcedureCatalog.tenant_id == user.tenant_id,
        )
    ).first()
    if not proc:
        raise HTTPException(404, "Procedure not found")

    order = HcProcedureOrder(
        tenant_id=user.tenant_id,
        patient_id=body.patient_id,
        doctor_id=body.doctor_id,
        admission_id=body.admission_id,
        procedure_id=body.procedure_id,
        order_date=body.order_date,
        fee=proc.standard_fee,
        notes=body.notes,
        created_by_id=user.id,
        created_at=datetime.utcnow(),
    )
    session.add(order)
    session.flush()

    # For OPD procedures (no admission_id): bill immediately
    if not body.admission_id:
        rev_code = "4120"
        if proc.revenue_account_id:
            acc = session.get(Account, proc.revenue_account_id)
            if acc:
                rev_code = acc.code
        txn = post_procedure(
            session, user,
            amount=proc.standard_fee,
            date=body.order_date,
            patient_name=patient.name,
            procedure_name=proc.name,
            customer_id=patient.customer_id,
            revenue_account_code=rev_code,
        )
        order.transaction_id = txn.id
    else:
        # For IPD: add to admission charges instead
        charge = HcAdmissionCharge(
            tenant_id=user.tenant_id,
            admission_id=body.admission_id,
            charge_date=body.order_date,
            charge_type="procedure",
            description=proc.name,
            amount=proc.standard_fee,
            procedure_id=body.procedure_id,
            created_by_id=user.id,
            created_at=datetime.utcnow(),
        )
        session.add(charge)

    session.commit()
    session.refresh(order)
    return order


@router.put("/procedure-orders/{order_id}/perform",
            dependencies=[perm_dep("healthcare.procedures", "edit")])
def perform_procedure(user: WriteUserDep, session: SessionDep, order_id: int,
                      performed_date: Optional[str] = None):
    from datetime import date
    order = session.exec(
        select(HcProcedureOrder).where(
            HcProcedureOrder.id == order_id, HcProcedureOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not order:
        raise HTTPException(404, "Procedure order not found")
    order.status = "performed"
    order.performed_date = performed_date or str(date.today())
    session.add(order)
    session.commit()
    return order


# ════════════════════════════════════════════════════════════════════════════
# HOSPITAL STORE
# ════════════════════════════════════════════════════════════════════════════

class StoreIssueCreate(BaseModel):
    issue_date: str
    from_location_id: int
    to_location_id: Optional[int] = None
    patient_id: Optional[int] = None
    admission_id: Optional[int] = None
    purpose: str = "ward"
    items: list[dict]   # [{product_id, qty, charge_to_patient, charge_amount}]


@router.get("/store/issues", dependencies=[perm_dep("healthcare.store")])
def list_store_issues(
    user: CurrentUserDep, session: SessionDep,
    purpose: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    q = select(HcStoreIssue).where(HcStoreIssue.tenant_id == user.tenant_id)
    if purpose:
        q = q.where(HcStoreIssue.purpose == purpose)
    if from_date:
        q = q.where(HcStoreIssue.issue_date >= from_date)
    if to_date:
        q = q.where(HcStoreIssue.issue_date <= to_date)
    return session.exec(q.order_by(HcStoreIssue.issue_date.desc()).offset(skip).limit(limit)).all()


@router.post("/store/issues", status_code=201, dependencies=[perm_dep("healthcare.store", "edit")])
def create_store_issue(user: WriteUserDep, session: SessionDep, body: StoreIssueCreate):
    issue_number = next_number(session, user.tenant_id, "hc_store", "HSI",
                               fmt="{prefix}-{YYYY}{seq:04d}")
    issue = HcStoreIssue(
        tenant_id=user.tenant_id,
        issue_number=issue_number,
        issue_date=body.issue_date,
        from_location_id=body.from_location_id,
        to_location_id=body.to_location_id,
        patient_id=body.patient_id,
        admission_id=body.admission_id,
        purpose=body.purpose,
        created_by_id=user.id,
        created_at=datetime.utcnow(),
    )
    session.add(issue)
    session.flush()

    total_charged = ZERO
    for item_data in body.items:
        item = HcStoreIssueItem(
            issue_id=issue.id,
            product_id=item_data["product_id"],
            qty=Decimal(str(item_data.get("qty", 1))),
            unit_cost=Decimal(str(item_data.get("unit_cost", 0))),
            charge_to_patient=item_data.get("charge_to_patient", False),
            charge_amount=Decimal(str(item_data.get("charge_amount", 0))),
        )
        session.add(item)
        if item.charge_to_patient:
            total_charged += item.charge_amount

        # Add to admission charges if patient-charged and IPD
        if item.charge_to_patient and body.admission_id:
            from models import Product
            product = session.get(Product, item_data["product_id"])
            adm_charge = HcAdmissionCharge(
                tenant_id=user.tenant_id,
                admission_id=body.admission_id,
                charge_date=body.issue_date,
                charge_type="pharmacy" if body.purpose == "pharmacy" else "other",
                description=f"Store: {product.name if product else 'Item'}",
                amount=item.charge_amount,
                created_by_id=user.id,
                created_at=datetime.utcnow(),
            )
            session.add(adm_charge)

    # Post GL for charged issues
    if total_charged > ZERO:
        txn = post_store_issue(
            session, user,
            amount=total_charged,
            date=body.issue_date,
            issue_number=issue_number,
            purpose=body.purpose,
            charge_to_patient=bool(body.patient_id),
            customer_id=None,  # resolved at discharge
        )
        issue.transaction_id = txn.id

    session.commit()
    session.refresh(issue)
    return issue


@router.get("/store/issues/{issue_id}", dependencies=[perm_dep("healthcare.store")])
def get_store_issue(user: CurrentUserDep, session: SessionDep, issue_id: int):
    issue = session.exec(
        select(HcStoreIssue).where(
            HcStoreIssue.id == issue_id, HcStoreIssue.tenant_id == user.tenant_id
        )
    ).first()
    if not issue:
        raise HTTPException(404, "Store issue not found")
    items = session.exec(
        select(HcStoreIssueItem).where(HcStoreIssueItem.issue_id == issue_id)
    ).all()
    return {**issue.model_dump(), "items": items}


@router.get("/store/pharmacy/pending", dependencies=[perm_dep("healthcare.store")])
def pending_dispensing(user: CurrentUserDep, session: SessionDep):
    """Prescription items not yet dispensed."""
    from sqlmodel import col
    items = session.exec(
        select(HcPrescriptionItem)
        .join(HcPrescription, HcPrescriptionItem.prescription_id == HcPrescription.id)
        .where(
            HcPrescription.tenant_id == user.tenant_id,
            HcPrescriptionItem.dispensed_qty.is_(None),
        )
    ).all()
    return items


@router.post("/store/pharmacy/dispense", dependencies=[perm_dep("healthcare.store", "edit")])
def dispense_item(user: WriteUserDep, session: SessionDep,
                  item_id: int, dispensed_qty: Decimal):
    item = session.exec(select(HcPrescriptionItem).where(HcPrescriptionItem.id == item_id)).first()
    if not item:
        raise HTTPException(404, "Prescription item not found")
    item.dispensed_qty = dispensed_qty
    item.dispensed_by_id = user.id
    item.dispensed_at = datetime.utcnow()
    session.add(item)
    session.commit()
    return item
