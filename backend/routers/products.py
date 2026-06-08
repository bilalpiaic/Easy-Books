"""Product CRUD + stock-summary endpoint."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Bill, BillLine, Customer, Invoice, InvoiceLine, Product, Vendor
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
    category_id: Optional[int] = None
    is_deferred: bool = False
    recognition_months: int = 12


@router.get("")
def list_products(
    session: SessionDep,
    user: CurrentUserDep,
    search: str = "",
    product_type: str = "",
    low_stock: bool = False,
    category_id: Optional[int] = None,
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
    if low_stock:
        q = q.where(Product.product_type == "stock", Product.stock_qty <= Product.reorder_level)
    if category_id is not None:
        q = q.where(Product.category_id == category_id)
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


@router.get("/{product_id}/last-price")
def product_last_price(
    session: SessionDep, user: CurrentUserDep, product_id: int,
    customer_id: Optional[int] = None, kind: str = "sale",
):
    """Most recent line rate for a product, scoped to a party with global
    fallback. kind='sale' uses invoices/customers, 'purchase' uses bills/vendors.
    Returns {rate, date, scope: 'customer'|'global'|None}."""

    if kind == "purchase":
        Line, Doc, party_col, date_col = BillLine, Bill, Bill.vendor_id, Bill.bill_date
        line_doc_fk = BillLine.bill_id
        PartyModel = Vendor
    else:
        Line, Doc, party_col, date_col = InvoiceLine, Invoice, Invoice.customer_id, Invoice.issue_date
        line_doc_fk = InvoiceLine.invoice_id
        PartyModel = Customer

    def latest(scoped: bool):
        q = (
            select(Line.rate, date_col, party_col)
            .join(Doc, Doc.id == line_doc_fk)
            .where(Doc.tenant_id == user.tenant_id, Line.product_id == product_id)
            .order_by(date_col.desc(), Doc.id.desc())
        )
        if scoped:
            q = q.where(party_col == customer_id)
        return session.exec(q.limit(1)).first()

    def resolve_party_name(party_id):
        if party_id is None:
            return None
        party = session.exec(
            select(PartyModel).where(
                PartyModel.id == party_id,
                PartyModel.tenant_id == user.tenant_id,
            )
        ).first()
        return party.name if party else None

    if customer_id is not None:
        row = latest(scoped=True)
        if row:
            return {"rate": float(row[0]), "date": row[1], "scope": "customer",
                    "party_name": resolve_party_name(row[2])}
    row = latest(scoped=False)
    if row:
        return {"rate": float(row[0]), "date": row[1], "scope": "global",
                "party_name": resolve_party_name(row[2])}
    return {"rate": None, "date": None, "scope": None, "party_name": None}


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
