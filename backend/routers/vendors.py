"""Vendor CRUD."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Bill, BillPayment, PaymentAllocation, Vendor

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/vendors", tags=["vendors"], dependencies=[perm_dep("vendors")])


class VendorCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Decimal = Decimal("0")
    payment_term_id: Optional[int] = None


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Optional[Decimal] = None
    is_active: Optional[bool] = None
    payment_term_id: Optional[int] = None


@router.get("")
def list_vendors(
    session: SessionDep, user: CurrentUserDep,
    search: str = "", skip: int = 0, limit: int = 50,
    sort_by: str = "name", sort_dir: str = "asc",
):
    from sqlmodel import asc as _asc, desc as _desc
    _sortable = {"name": Vendor.name, "email": Vendor.email, "opening_balance": Vendor.opening_balance}
    col = _sortable.get(sort_by, Vendor.name)
    q = select(Vendor).where(Vendor.tenant_id == user.tenant_id)
    if search:
        q = q.where(Vendor.name.ilike(f"%{search}%"))
    q = q.order_by(_asc(col) if sort_dir == "asc" else _desc(col))
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.get("/{vendor_id}")
def get_vendor(session: SessionDep, user: CurrentUserDep, vendor_id: int):
    v = session.exec(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    return v


@router.post("", status_code=201)
def create_vendor(session: SessionDep, user: WriteUserDep, body: VendorCreate):
    v = Vendor(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(v)
    session.flush()
    log_audit(session, user, "CREATE", "vendor", v.id, {"name": v.name})
    session.commit()
    session.refresh(v)
    return v


@router.put("/{vendor_id}")
def update_vendor(
    session: SessionDep, user: WriteUserDep, vendor_id: int, body: VendorUpdate
):
    v = session.exec(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    for k, val in body.model_dump(exclude_none=True).items():
        setattr(v, k, val)
    session.add(v)
    log_audit(session, user, "UPDATE", "vendor", v.id, {"name": v.name})
    session.commit()
    session.refresh(v)
    return v


@router.get("/{vendor_id}/statement", dependencies=[perm_dep("vendor_ledger")])
def vendor_statement(
    session: SessionDep, user: CurrentUserDep, vendor_id: int,
    from_date: str, to_date: str,
):
    """Account statement for a vendor: opening balance, bills, payments, closing balance."""
    v = session.exec(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(404, "Vendor not found")

    D = lambda x: Decimal(str(x)) if x is not None else Decimal("0")

    # All GL-posted bills (excluding void/cancelled)
    all_bills = session.exec(
        select(Bill).where(
            Bill.vendor_id == vendor_id,
            Bill.tenant_id == user.tenant_id,
            Bill.status.not_in(["void", "cancelled"]),
            Bill.transaction_id.is_not(None),
        ).order_by(Bill.bill_date.asc(), Bill.id.asc())
    ).all()

    all_bill_ids = [b.id for b in all_bills]
    pre_bills = [b for b in all_bills if b.bill_date < from_date]
    pre_bill_ids = [b.id for b in pre_bills]

    # Pre-period payments against pre-period bills
    pre_bill_paid: dict[int, Decimal] = {}
    if pre_bill_ids:
        for bill_id, paid in session.exec(
            select(PaymentAllocation.bill_id, func.sum(PaymentAllocation.amount))
            .join(BillPayment, BillPayment.id == PaymentAllocation.bill_payment_id)
            .where(
                PaymentAllocation.tenant_id == user.tenant_id,
                PaymentAllocation.bill_id.in_(pre_bill_ids),
                BillPayment.payment_date < from_date,
            )
            .group_by(PaymentAllocation.bill_id)
        ).all():
            pre_bill_paid[bill_id] = D(paid)

    # Opening balance: vendor pre-system balance + net AP from bills before from_date
    opening_balance = D(v.opening_balance)
    for b in pre_bills:
        opening_balance += D(b.total) - pre_bill_paid.get(b.id, Decimal("0"))

    # All-time allocations per bill (for outstanding per period bill)
    bill_paid: dict[int, Decimal] = {}
    if all_bill_ids:
        for bill_id, paid in session.exec(
            select(PaymentAllocation.bill_id, func.sum(PaymentAllocation.amount))
            .where(
                PaymentAllocation.tenant_id == user.tenant_id,
                PaymentAllocation.bill_id.in_(all_bill_ids),
            )
            .group_by(PaymentAllocation.bill_id)
        ).all():
            bill_paid[bill_id] = D(paid)

    # Period bills
    period_bills = [b for b in all_bills if from_date <= b.bill_date <= to_date]
    bills_out = [
        {
            "id": b.id,
            "number": b.number,
            "date": b.bill_date,
            "due_date": b.due_date,
            "status": b.status,
            "total": str(D(b.total)),
            "outstanding": str(max(D(b.total) - bill_paid.get(b.id, Decimal("0")), Decimal("0"))),
            "currency": b.currency,
        }
        for b in period_bills
    ]

    # Payments in period: BillPayment with allocations to this vendor's bills
    period_payments: list[dict] = []
    if all_bill_ids:
        pay_rows = session.exec(
            select(
                BillPayment.id,
                BillPayment.payment_date,
                BillPayment.method,
                BillPayment.reference,
                func.sum(PaymentAllocation.amount).label("allocated"),
            )
            .join(PaymentAllocation, PaymentAllocation.bill_payment_id == BillPayment.id)
            .where(
                BillPayment.tenant_id == user.tenant_id,
                BillPayment.payment_date >= from_date,
                BillPayment.payment_date <= to_date,
                PaymentAllocation.bill_id.in_(all_bill_ids),
            )
            .group_by(
                BillPayment.id,
                BillPayment.payment_date,
                BillPayment.method,
                BillPayment.reference,
            )
            .order_by(BillPayment.payment_date.asc())
        ).all()
        for row in pay_rows:
            period_payments.append({
                "id": row.id,
                "date": row.payment_date,
                "method": row.method,
                "reference": row.reference,
                "amount": str(D(row.allocated)),
            })

    period_bill_total = sum(D(b["total"]) for b in bills_out)
    period_paid_total = sum(D(p["amount"]) for p in period_payments)
    closing_balance = opening_balance + period_bill_total - period_paid_total

    return {
        "vendor": {
            "id": v.id,
            "name": v.name,
            "email": v.email,
            "phone": v.phone,
            "address": v.address,
        },
        "period": {"from": from_date, "to": to_date},
        "opening_balance": str(opening_balance),
        "bills": bills_out,
        "payments": period_payments,
        "closing_balance": str(closing_balance),
    }


@router.delete("/{vendor_id}", status_code=204)
def delete_vendor(session: SessionDep, user: WriteUserDep, vendor_id: int):
    """Hard-delete only when no document references the vendor. Otherwise
    set is_active=False via PUT to preserve the audit trail.
    """
    v = session.exec(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    if session.exec(select(Bill).where(Bill.vendor_id == vendor_id)).first():
        raise HTTPException(
            400, "Cannot delete vendor with bills — deactivate (set is_active=False) instead",
        )
    bp = session.exec(
        select(BillPayment)
        .join(Bill, Bill.id == BillPayment.bill_id)
        .where(Bill.vendor_id == vendor_id)
    ).first()
    if bp:
        raise HTTPException(
            400, "Cannot delete vendor with payment history — deactivate instead",
        )
    log_audit(session, user, "DELETE", "vendor", v.id, {"name": v.name})
    session.delete(v)
    session.commit()
