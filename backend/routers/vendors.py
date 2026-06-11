"""Vendor CRUD."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Bill, BillPayment, Vendor

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


class VendorCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Decimal = Decimal("0")


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Optional[Decimal] = None
    is_active: Optional[bool] = None


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
