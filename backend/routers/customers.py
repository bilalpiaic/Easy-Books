"""Customer CRUD."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Customer

from .common import CurrentUserDep, SessionDep, log_audit

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
):
    q = select(Customer).where(Customer.tenant_id == user.tenant_id)
    if search:
        q = q.where(Customer.name.ilike(f"%{search}%"))
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.post("", status_code=201)
def create_customer(session: SessionDep, user: CurrentUserDep, body: CustomerCreate):
    c = Customer(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(c)
    session.flush()
    log_audit(session, user, "CREATE", "customer", c.id, {"name": c.name})
    session.commit()
    session.refresh(c)
    return c


@router.put("/{customer_id}")
def update_customer(
    session: SessionDep, user: CurrentUserDep, customer_id: int, body: CustomerUpdate
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
def delete_customer(session: SessionDep, user: CurrentUserDep, customer_id: int):
    c = session.exec(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    log_audit(session, user, "DELETE", "customer", c.id, {"name": c.name})
    session.delete(c)
    session.commit()
