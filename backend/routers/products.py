"""Product CRUD + stock-summary endpoint."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Bill, BillLine, Customer, Invoice, InvoiceLine, InventoryLayer, Product, Vendor
from services.inventory import record_movement, record_purchase
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, get_or_create_account, log_audit
from services.permissions import perm_dep, apply_own_filter
from services.custom_fields import apply_incoming as apply_custom_fields

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[perm_dep("products")])


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
    hs_code: Optional[str] = None
    pct_code: Optional[str] = None     # PRA 8-digit product classification (PCTCode)
    hsn_sac: Optional[str] = None      # India GST HSN/SAC (#265)
    cost_method: Optional[str] = None  # 'wavg' | 'fifo' | None (inherit from tenant)
    track_lot: bool = False
    track_serial: bool = False
    nrv_unit: Optional[Decimal] = None
    standalone_selling_price: Optional[Decimal] = None
    custom_fields: Optional[dict] = None
    opening_qty: Decimal = Decimal("0")
    opening_cost: Decimal = Decimal("0")


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


@router.get("/{product_id}")
def get_product(session: SessionDep, user: CurrentUserDep, product_id: int):
    p = session.exec(
        select(Product).where(Product.id == product_id, Product.tenant_id == user.tenant_id)
    ).first()
    if not p:
        raise HTTPException(404, "Product not found")
    return p


@router.get("/{product_id}/layers")
def get_product_layers(session: SessionDep, user: CurrentUserDep, product_id: int):
    """Open FIFO cost layers for a stock product (qty_remaining > 0, oldest first)."""
    p = session.exec(
        select(Product).where(Product.id == product_id, Product.tenant_id == user.tenant_id)
    ).first()
    if not p:
        raise HTTPException(404, "Product not found")
    layers = session.exec(
        select(InventoryLayer)
        .where(
            InventoryLayer.tenant_id == user.tenant_id,
            InventoryLayer.product_id == product_id,
            InventoryLayer.qty_remaining > 0,
            InventoryLayer.owner_customer_id.is_(None),  # exclude custodial stock
        )
        .order_by(InventoryLayer.id.asc())
    ).all()
    return [
        {
            "id": l.id,
            "qty_received": str(l.qty_received),
            "qty_remaining": str(l.qty_remaining),
            "unit_cost": str(l.unit_cost),
            "lot_no": l.lot_no,
            "source_doc": l.source_doc,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in layers
    ]


@router.post("", status_code=201)
def create_product(session: SessionDep, user: WriteUserDep, body: ProductCreate):
    if body.cost_method and body.cost_method not in ("wavg", "fifo"):
        raise HTTPException(400, "cost_method must be 'wavg', 'fifo', or null")
    _bootstrap = {"opening_qty", "opening_cost"}
    data = body.model_dump(exclude=_bootstrap)
    data["custom_fields"] = apply_custom_fields(
        session, user.tenant_id, "product", data.get("custom_fields")
    )
    p = Product(tenant_id=user.tenant_id, **data)
    session.add(p)
    if body.product_type == "stock" and body.opening_qty > 0:
        # Route the opening balance through record_purchase so it leaves a
        # StockMovement + InventoryLayer — a bare stock_qty assignment shows
        # a permanent Stock Tie-out variance and gives FIFO nothing to
        # deplete (#145 follow-up).
        session.flush()
        record_purchase(
            session, tenant_id=user.tenant_id, product_id=p.id,
            qty=body.opening_qty, unit_cost=body.opening_cost,
            source_doc="OPENING", source_doc_type="opening", posted_to_gl=False,
        )
    log_audit(session, user, "CREATE", "product", None, {"name": body.name})
    session.commit()
    session.refresh(p)
    return p


@router.put("/{product_id}")
def update_product(
    session: SessionDep, user: WriteUserDep, product_id: int, body: ProductCreate
):
    if body.cost_method and body.cost_method not in ("wavg", "fifo"):
        raise HTTPException(400, "cost_method must be 'wavg', 'fifo', or null")
    p = session.exec(
        select(Product).where(Product.id == product_id, Product.tenant_id == user.tenant_id)
    ).first()
    if not p:
        raise HTTPException(404, "Product not found")
    data = body.model_dump(exclude={"opening_qty", "opening_cost"})
    data["custom_fields"] = apply_custom_fields(
        session, user.tenant_id, "product", data.get("custom_fields"), existing=p.custom_fields
    )
    for k, v in data.items():
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


class StockAdjustIn(BaseModel):
    counted_qty: Decimal
    date: str
    notes: Optional[str] = None


@router.post("/{product_id}/adjust-stock", status_code=201)
def adjust_stock(session: SessionDep, user: WriteUserDep, product_id: int, body: StockAdjustIn):
    """Physical count → stock adjustment. Posts a GL variance entry and records the movement."""
    p = session.exec(
        select(Product).where(Product.id == product_id, Product.tenant_id == user.tenant_id)
    ).first()
    if not p:
        raise HTTPException(404, "Product not found")
    if p.product_type != "stock":
        raise HTTPException(400, "Stock adjustments are only valid for stock-type products")

    system_qty = D(p.stock_qty)
    counted_qty = D(body.counted_qty)
    variance = counted_qty - system_qty
    if variance == ZERO:
        return {"variance": "0", "jv_number": None, "message": "No variance — qty unchanged"}

    avg_cost = D(p.avg_cost)
    variance_value = abs(variance) * avg_cost

    # GL accounts
    inv_acc  = get_or_create_account(session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset")
    adj_acc  = get_or_create_account(session, user.tenant_id, "5040", "Inventory Adjustments", "Expense")

    if variance > 0:
        # Found more stock: Dr Inventory / Cr Inventory Adjustments
        entries = [
            EntryInput(account_id=inv_acc.id, debit=money(variance_value)),
            EntryInput(account_id=adj_acc.id, credit=money(variance_value)),
        ]
    else:
        # Stock short: Dr Inventory Adjustments / Cr Inventory
        entries = [
            EntryInput(account_id=adj_acc.id, debit=money(variance_value)),
            EntryInput(account_id=inv_acc.id, credit=money(variance_value)),
        ]

    txn = post_transaction(
        session, user,
        date=body.date,
        description=f"Stock adjustment — {p.name} (counted {counted_qty}, system {system_qty})",
        entries=entries,
        voucher_type="JV",
        audit_entity_type="product",
        audit_detail={"product_id": p.id, "variance": str(variance), "notes": body.notes},
    )

    # Update product qty
    p.stock_qty = money(counted_qty)
    session.add(p)

    # Record movement
    record_movement(
        session,
        tenant_id=user.tenant_id,
        product_id=product_id,
        direction="ADJUSTMENT",
        qty=abs(variance),
        unit_cost=avg_cost,
        source_doc_type="adjustment",
        posted_to_gl=True,
        notes=body.notes or f"Physical count: counted={counted_qty}, system={system_qty}",
    )

    session.commit()
    log_audit(session, user, "ADJUST_STOCK", "product", p.id, {"variance": str(variance), "counted_qty": str(counted_qty)})
    return {
        "variance": str(variance),
        "variance_value": str(variance_value),
        "jv_number": txn.jv_number,
        "system_qty": str(system_qty),
        "counted_qty": str(counted_qty),
        "message": f"Adjusted stock by {'+' if variance > 0 else ''}{variance} units",
    }
