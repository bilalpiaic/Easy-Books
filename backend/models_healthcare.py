"""
SQLModel tables for the Healthcare module.

Covers the full hospital/clinic workflow:
  Patient master (linked to Customer for AR billing)
  Doctors roster (optional link to Employee for payroll integration)
  OPD — token queue, consultations, prescriptions
  IPD — ward/bed management, admissions, daily charges, discharge billing
  Laboratory — test catalogue, orders, results, sample collection
  Procedures — catalogue + orders with consumables
  Hospital Store — stock issues from pharmacy/lab/ward stores

All tables include tenant_id (required for multi-tenancy), money columns are
NUMERIC(18,4) via _money(), and billable events carry FK to invoice.id and
transaction.id to wire each event to its posted GL JV.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from services.money import ZERO


def _money(default: Decimal = ZERO, **kw):
    from sqlalchemy import Column
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


# ── Patient ──────────────────────────────────────────────────────────────────


class HcPatient(SQLModel, table=True):
    __tablename__ = "hc_patient"
    __table_args__ = (
        UniqueConstraint("tenant_id", "mr_number", name="uq_hc_patient_mr_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    # Links to Customer for AR billing — auto-created on patient registration
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    mr_number: str = Field(index=True)          # MR-YYYYNNNN
    name: str
    dob: Optional[str] = None                   # ISO date YYYY-MM-DD
    gender: str = Field(default="other")        # male|female|other
    blood_group: Optional[str] = None
    cnic: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    allergies: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


# ── Doctor ───────────────────────────────────────────────────────────────────


class HcDoctor(SQLModel, table=True):
    __tablename__ = "hc_doctor"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    # Optional link to Employee (for staff doctors on payroll)
    employee_id: Optional[int] = Field(default=None, foreign_key="employee.id")
    name: str
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    phone: Optional[str] = None
    opd_fee: Decimal = _money()
    # GL account to post consultation revenue (defaults to 4100 via posting service)
    consultation_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Ward ─────────────────────────────────────────────────────────────────────


class HcWard(SQLModel, table=True):
    __tablename__ = "hc_ward"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    ward_type: str = Field(default="general")   # general|icu|private|semi-private|maternity
    total_beds: int = Field(default=0)
    daily_charge: Decimal = _money()
    revenue_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    is_active: bool = Field(default=True)


# ── Bed ──────────────────────────────────────────────────────────────────────


class HcBed(SQLModel, table=True):
    __tablename__ = "hc_bed"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    ward_id: int = Field(foreign_key="hc_ward.id", index=True)
    bed_number: str
    status: str = Field(default="available")    # available|occupied|maintenance
    # Nullable FK — set when bed is occupied by an admission. use_alter breaks
    # the HcBed<->HcAdmission FK cycle in metadata.sorted_tables; the demo
    # purge nulls this column before bulk deletes (routers/admin.py).
    current_admission_id: Optional[int] = Field(
        default=None,
        sa_column=sa.Column(
            "current_admission_id", sa.Integer, sa.ForeignKey("hc_admission.id", use_alter=True)
        ),
    )
    is_active: bool = Field(default=True)


# ── Procedure Catalogue ───────────────────────────────────────────────────────


class HcProcedureCatalog(SQLModel, table=True):
    __tablename__ = "hc_procedure_catalog"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str
    name: str
    category: str = Field(default="minor")      # surgery|diagnostic|therapy|minor
    standard_fee: Decimal = _money()
    revenue_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Procedure Consumable (links procedure to products consumed per run) ───────


class HcProcedureConsumable(SQLModel, table=True):
    __tablename__ = "hc_procedure_consumable"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    procedure_id: int = Field(foreign_key="hc_procedure_catalog.id", index=True)
    product_id: int = Field(foreign_key="product.id")
    qty_per_procedure: Decimal = _money(default=Decimal("1"))
    # If set, stock is pulled from this location; otherwise from the default OT Store
    location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id")


# ── OPD Token (queue management) ─────────────────────────────────────────────


class HcOpdToken(SQLModel, table=True):
    __tablename__ = "hc_opd_token"
    __table_args__ = (
        UniqueConstraint("tenant_id", "doctor_id", "visit_date", "token_number",
                         name="uq_hc_token_per_doctor_day"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    doctor_id: int = Field(foreign_key="hc_doctor.id", index=True)
    # Nullable — walk-in patients may not be registered
    patient_id: Optional[int] = Field(default=None, foreign_key="hc_patient.id")
    patient_name: Optional[str] = None          # free-text for walk-ins
    token_number: int
    visit_date: str = Field(index=True)         # ISO date; token# resets daily per doctor
    status: str = Field(default="waiting")      # waiting|called|visited|cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── OPD Visit ────────────────────────────────────────────────────────────────


class HcOpdVisit(SQLModel, table=True):
    __tablename__ = "hc_opd_visit"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    token_id: Optional[int] = Field(default=None, foreign_key="hc_opd_token.id")
    patient_id: int = Field(foreign_key="hc_patient.id", index=True)
    doctor_id: int = Field(foreign_key="hc_doctor.id", index=True)
    visit_date: str = Field(index=True)
    visit_type: str = Field(default="first")    # first|follow_up
    chief_complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    vitals_json: Optional[str] = None           # JSON: {bp, temp, pulse, weight, spo2}
    advice: Optional[str] = None
    follow_up_date: Optional[str] = None
    # Set when consultation is billed
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


# ── Prescription ──────────────────────────────────────────────────────────────


class HcPrescription(SQLModel, table=True):
    __tablename__ = "hc_prescription"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    visit_id: int = Field(foreign_key="hc_opd_visit.id", index=True)
    patient_id: int = Field(foreign_key="hc_patient.id")
    doctor_id: int = Field(foreign_key="hc_doctor.id")
    prescribed_date: str
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HcPrescriptionItem(SQLModel, table=True):
    __tablename__ = "hc_prescription_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    prescription_id: int = Field(foreign_key="hc_prescription.id", index=True)
    medicine_name: str                          # free-text — always filled by doctor
    # Nullable — set by pharmacist when dispensing from inventory
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    dosage: Optional[str] = None
    frequency: Optional[str] = None            # e.g., "1-1-1", "BID", "TDS"
    duration: Optional[str] = None             # e.g., "5 days"
    route: str = Field(default="oral")         # oral|iv|im|topical|inhalation
    instructions: Optional[str] = None
    qty: Decimal = _money(default=Decimal("1"))
    # Pharmacy dispensing
    dispensed_qty: Optional[Decimal] = Field(default=None, sa_column=sa.Column(sa.Numeric(18, 4), nullable=True))
    dispensed_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    dispensed_at: Optional[datetime] = None


# ── IPD Admission ─────────────────────────────────────────────────────────────


class HcAdmission(SQLModel, table=True):
    __tablename__ = "hc_admission"
    __table_args__ = (
        UniqueConstraint("tenant_id", "admission_number", name="uq_hc_admission_number_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    patient_id: int = Field(foreign_key="hc_patient.id", index=True)
    doctor_id: int = Field(foreign_key="hc_doctor.id")
    ward_id: int = Field(foreign_key="hc_ward.id")
    bed_id: int = Field(foreign_key="hc_bed.id")
    admission_number: str = Field(index=True)   # ADM-YYYYNNNN
    admission_date: str
    discharge_date: Optional[str] = None
    diagnosis: Optional[str] = None
    admission_type: str = Field(default="planned")  # emergency|planned|referred
    status: str = Field(default="admitted")     # admitted|discharged|aua
    deposit_amount: Decimal = _money()
    deposit_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    discharge_invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class HcAdmissionCharge(SQLModel, table=True):
    __tablename__ = "hc_admission_charge"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    admission_id: int = Field(foreign_key="hc_admission.id", index=True)
    charge_date: str = Field(index=True)
    charge_type: str = Field(default="bed")    # bed|procedure|lab|nursing|pharmacy|other
    description: str
    amount: Decimal = _money()
    procedure_id: Optional[int] = Field(default=None, foreign_key="hc_procedure_catalog.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


# ── Lab Test Catalogue ────────────────────────────────────────────────────────


class HcLabTest(SQLModel, table=True):
    __tablename__ = "hc_lab_test"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str
    name: str
    category: str = Field(default="other")     # hematology|biochemistry|microbiology|radiology|other
    normal_range: Optional[str] = None
    unit: Optional[str] = None
    standard_fee: Decimal = _money()
    revenue_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    # Reagent/consumable consumed per test run
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    qty_per_test: Decimal = _money(default=Decimal("1"))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Lab Order ─────────────────────────────────────────────────────────────────


class HcLabOrder(SQLModel, table=True):
    __tablename__ = "hc_lab_order"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_number", name="uq_hc_lab_order_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    patient_id: int = Field(foreign_key="hc_patient.id", index=True)
    doctor_id: Optional[int] = Field(default=None, foreign_key="hc_doctor.id")
    # Set for IPD lab orders (billed at discharge)
    admission_id: Optional[int] = Field(default=None, foreign_key="hc_admission.id")
    order_number: str = Field(index=True)       # LO-YYYYNNNN
    order_date: str = Field(index=True)
    source: str = Field(default="walkin")       # opd|ipd|walkin|collection_centre
    status: str = Field(default="ordered")      # ordered|sample_collected|processing|resulted|delivered
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class HcLabOrderItem(SQLModel, table=True):
    __tablename__ = "hc_lab_order_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    lab_order_id: int = Field(foreign_key="hc_lab_order.id", index=True)
    test_id: int = Field(foreign_key="hc_lab_test.id")
    fee: Decimal = _money()                     # price snapshot at time of order
    result_value: Optional[str] = None
    result_unit: Optional[str] = None
    reference_range: Optional[str] = None
    is_abnormal: bool = Field(default=False)
    resulted_at: Optional[datetime] = None
    resulted_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


# ── Sample Collection ─────────────────────────────────────────────────────────


class HcSampleCollection(SQLModel, table=True):
    __tablename__ = "hc_sample_collection"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    lab_order_id: int = Field(foreign_key="hc_lab_order.id", index=True)
    collected_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    collected_at: Optional[datetime] = None
    collection_point: str = Field(default="lab")    # lab|home|centre
    specimen_type: str = Field(default="blood")     # blood|urine|stool|swab|other
    barcode: Optional[str] = None
    notes: Optional[str] = None
    status: str = Field(default="collected")        # collected|dispatched|received


# ── Procedure Order ───────────────────────────────────────────────────────────


class HcProcedureOrder(SQLModel, table=True):
    __tablename__ = "hc_procedure_order"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    patient_id: int = Field(foreign_key="hc_patient.id", index=True)
    doctor_id: Optional[int] = Field(default=None, foreign_key="hc_doctor.id")
    admission_id: Optional[int] = Field(default=None, foreign_key="hc_admission.id")
    procedure_id: int = Field(foreign_key="hc_procedure_catalog.id")
    order_date: str
    performed_date: Optional[str] = None
    status: str = Field(default="ordered")      # ordered|performed|cancelled
    fee: Decimal = _money()                     # price snapshot
    notes: Optional[str] = None
    # For OPD procedures: billed immediately; for IPD: null (captured in HcAdmissionCharge)
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


# ── Hospital Store Issue ──────────────────────────────────────────────────────


class HcStoreIssue(SQLModel, table=True):
    __tablename__ = "hc_store_issue"
    __table_args__ = (
        UniqueConstraint("tenant_id", "issue_number", name="uq_hc_store_issue_per_tenant"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    issue_number: str = Field(index=True)       # HSI-YYYYNNNN
    issue_date: str = Field(index=True)
    from_location_id: int = Field(foreign_key="stocklocation.id")
    to_location_id: Optional[int] = Field(default=None, foreign_key="stocklocation.id")
    patient_id: Optional[int] = Field(default=None, foreign_key="hc_patient.id")
    admission_id: Optional[int] = Field(default=None, foreign_key="hc_admission.id")
    purpose: str = Field(default="ward")        # pharmacy|lab|procedure|ward|transfer
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class HcStoreIssueItem(SQLModel, table=True):
    __tablename__ = "hc_store_issue_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    issue_id: int = Field(foreign_key="hc_store_issue.id", index=True)
    product_id: int = Field(foreign_key="product.id")
    qty: Decimal = _money(default=Decimal("1"))
    unit_cost: Decimal = _money()               # avg cost snapshot
    charge_to_patient: bool = Field(default=False)
    charge_amount: Decimal = _money()           # markup price if charged to patient
