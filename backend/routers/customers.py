"""Customer CRUD."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Customer, Invoice, PaymentReceived

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Decimal = Decimal("0")


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Optional[Decimal] = None
    is_active: Optional[bool] = None


@router.get("")
def list_customers(
    session: SessionDep, user: CurrentUserDep,
    search: str = "", skip: int = 0, limit: int = 50,
    sort_by: str = "name", sort_dir: str = "asc",
):
    from sqlmodel import asc as _asc, desc as _desc
    _sortable = {"name": Customer.name, "email": Customer.email, "opening_balance": Customer.opening_balance}
    col = _sortable.get(sort_by, Customer.name)
    q = select(Customer).where(Customer.tenant_id == user.tenant_id)
    if search:
        q = q.where(Customer.name.ilike(f"%{search}%"))
    q = q.order_by(_asc(col) if sort_dir == "asc" else _desc(col))
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.post("", status_code=201)
def create_customer(session: SessionDep, user: WriteUserDep, body: CustomerCreate):
    c = Customer(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(c)
    session.flush()
    log_audit(session, user, "CREATE", "customer", c.id, {"name": c.name})
    session.commit()
    session.refresh(c)
    return c


@router.put("/{customer_id}")
def update_customer(
    session: SessionDep, user: WriteUserDep, customer_id: int, body: CustomerUpdate
):
    c = session.exec(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    session.add(c)
    log_audit(session, user, "UPDATE", "customer", c.id, {"name": c.name})
    session.commit()
    session.refresh(c)
    return c


@router.delete("/{customer_id}", status_code=204)
def delete_customer(session: SessionDep, user: WriteUserDep, customer_id: int):
    """Hard-delete only when no document references the customer. Otherwise
    set is_active=False via PUT to preserve the audit trail.
    """
    c = session.exec(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    if session.exec(select(Invoice).where(Invoice.customer_id == customer_id)).first():
        raise HTTPException(
            400, "Cannot delete customer with invoices — deactivate (set is_active=False) instead",
        )
    if session.exec(select(PaymentReceived).where(PaymentReceived.invoice_id != None)).first():
        # Cross-check: any payment whose invoice belongs to this customer
        bad = session.exec(
            select(PaymentReceived)
            .join(Invoice, Invoice.id == PaymentReceived.invoice_id)
            .where(Invoice.customer_id == customer_id)
        ).first()
        if bad:
            raise HTTPException(
                400, "Cannot delete customer with payment history — deactivate instead",
            )
    log_audit(session, user, "DELETE", "customer", c.id, {"name": c.name})
    session.delete(c)
    session.commit()
