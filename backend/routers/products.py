"""Product CRUD + stock-summary endpoint."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import BillLine, InvoiceLine, Product
from services.money import D, money

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductCreate(BaseModel):
    code: Optional[str] = None
    name: str
    unit: str = "pcs"
    product_type: str = "service"
    default_rate: Decimal = Decimal("0")
    reorder_level: Decimal = Decimal("0")
    stock_account_id: Optional[int] = None
    revenue_account_id: Optional[int] = None
    cogs_account_id: Optional[int] = None


@router.get("")
def list_products(
    session: SessionDep,
    user: CurrentUserDep,
    search: str = "",
    product_type: str = "",
    skip: int = 0,
    limit: int = 100,
):
    q = select(Product).where(Product.tenant_id == user.tenant_id)
    if search:
        q = q.where(
            (Product.name.ilike(f"%{search}%")) | (Product.code.ilike(f"%{search}%"))
        )
    if product_type:
        q = q.where(Product.product_type == product_type)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(Product.name).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.get("/stock-summary")
def products_stock_summary(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(Product).where(
            Product.tenant_id == user.tenant_id, Product.product_type == "stock"
        )
    ).all()
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "unit": p.unit,
            "stock_qty": p.stock_qty,
            "reorder_level": p.reorder_level,
            "default_rate": p.default_rate,
            "value": money(D(p.stock_qty) * D(p.default_rate)),
            "low_stock": D(p.stock_qty) <= D(p.reorder_level),
        }
        for p in items
    ]


@router.post("", status_code=201)
def create_product(session: SessionDep, user: WriteUserDep, body: ProductCreate):
    p = Product(tenant_id=user.tenant_id, **body.model_dump())
    session.add(p)
    log_audit(session, user, "CREATE", "product", None, {"name": body.name})
    session.commit()
    session.refresh(p)
    return p


@router.put("/{product_id}")
def update_product(
    session: SessionDep, user: WriteUserDep, product_id: int, body: ProductCreate
):
    p = session.exec(
        select(Product).where(Product.id == product_id, Product.tenant_id == user.tenant_id)
    ).first()
    if not p:
        raise HTTPException(404, "Product not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    session.add(p)
    log_audit(session, user, "UPDATE", "product", p.id, {"name": p.name})
    session.commit()
    session.refresh(p)
    return p


@router.delete("/{product_id}", status_code=204)
def delete_product(session: SessionDep, user: WriteUserDep, product_id: int):
    p = session.exec(
        select(Product).where(Product.id == product_id, Product.tenant_id == user.tenant_id)
    ).first()
    if not p:
        raise HTTPException(404, "Product not found")
    if session.exec(select(InvoiceLine).where(InvoiceLine.product_id == product_id)).first():
        raise HTTPException(400, "Cannot delete product used in invoice lines")
    if session.exec(select(BillLine).where(BillLine.product_id == product_id)).first():
        raise HTTPException(400, "Cannot delete product used in bill lines")
    log_audit(session, user, "DELETE", "product", p.id, {"name": p.name})
    session.delete(p)
    session.commit()
