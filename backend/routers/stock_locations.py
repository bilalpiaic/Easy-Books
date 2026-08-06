"""Stock locations CRUD + per-location stock view.

Multi-location inventory: a tenant can have several `own` stores
(RM-1, RM-2, MAIN), `customer_custodial` godowns (one per customer or
shared), and `wip` buckets. The same product can hold separate qty in
each location.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import InventoryLayer, Product, StockLocation, StockMovement
from services.money import D

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/stock-locations", tags=["stock-locations"], dependencies=[perm_dep("stock_locations")])

_VALID_TYPES = {"own", "customer_custodial", "wip", "in_transit"}


class LocationCreate(BaseModel):
    code: str
    name: str
    type: str   # own | customer_custodial | wip


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
def list_locations(
    session: SessionDep, user: CurrentUserDep,
    type: Optional[str] = None,
):
    q = select(StockLocation).where(StockLocation.tenant_id == user.tenant_id)
    if type:
        q = q.where(StockLocation.type == type)
    items = session.exec(q.order_by(StockLocation.code)).all()
    return {"total": len(items), "items": items}


@router.post("", status_code=201)
def create_location(
    session: SessionDep, user: WriteUserDep, body: LocationCreate
):
    if body.type not in _VALID_TYPES:
        raise HTTPException(
            400, f"type must be one of {sorted(_VALID_TYPES)}"
        )
    existing = session.exec(
        select(StockLocation).where(
            StockLocation.tenant_id == user.tenant_id,
            StockLocation.code == body.code,
        )
    ).first()
    if existing:
        raise HTTPException(400, f"Location code '{body.code}' already exists")
    loc = StockLocation(
        tenant_id=user.tenant_id,
        code=body.code, name=body.name, type=body.type,
    )
    session.add(loc)
    session.flush()
    log_audit(
        session, user, "CREATE", "stock_location", loc.id,
        {"code": loc.code, "name": loc.name, "type": loc.type},
    )
    session.commit()
    session.refresh(loc)
    return loc


@router.put("/{loc_id}")
def update_location(
    session: SessionDep, user: WriteUserDep, loc_id: int, body: LocationUpdate
):
    loc = session.exec(
        select(StockLocation).where(
            StockLocation.id == loc_id, StockLocation.tenant_id == user.tenant_id
        )
    ).first()
    if not loc:
        raise HTTPException(404, "Location not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(loc, k, v)
    session.add(loc)
    log_audit(
        session, user, "UPDATE", "stock_location", loc.id,
        {"code": loc.code, "name": loc.name},
    )
    session.commit()
    session.refresh(loc)
    return loc


@router.get("/{loc_id}/stock")
def stock_at_location(
    session: SessionDep, user: CurrentUserDep, loc_id: int,
):
    """Per-product qty + value sitting at one location, grouped by lot."""
    loc = session.exec(
        select(StockLocation).where(
            StockLocation.id == loc_id, StockLocation.tenant_id == user.tenant_id
        )
    ).first()
    if not loc:
        raise HTTPException(404, "Location not found")

    rows = session.exec(
        select(
            Product.id, Product.code, Product.name,
            InventoryLayer.lot_no,
            func.sum(InventoryLayer.qty_remaining).label("qty"),
            func.sum(InventoryLayer.qty_remaining * InventoryLayer.unit_cost).label("value"),
        )
        .join(InventoryLayer, InventoryLayer.product_id == Product.id)
        .where(
            InventoryLayer.tenant_id == user.tenant_id,
            InventoryLayer.location_id == loc_id,
            InventoryLayer.qty_remaining > 0,
        )
        .group_by(Product.id, InventoryLayer.lot_no)
        .order_by(Product.code, InventoryLayer.lot_no)
    ).all()

    items = [
        {
            "product_id": r.id,
            "product_code": r.code,
            "product_name": r.name,
            "lot_no": r.lot_no,
            "qty": r.qty,
            "value": r.value,
        }
        for r in rows
    ]
    return {"location": loc, "items": items, "total_lines": len(items)}


# ── Movements (read-only event-log view) ────────────────────────────────────


@router.get("/movements")
def list_movements(
    session: SessionDep, user: CurrentUserDep,
    product_id: Optional[int] = None,
    location_id: Optional[int] = None,
    direction: Optional[str] = None,
    skip: int = 0, limit: int = 100,
):
    q = select(StockMovement).where(StockMovement.tenant_id == user.tenant_id)
    if product_id:
        q = q.where(StockMovement.product_id == product_id)
    if location_id:
        q = q.where(
            (StockMovement.from_location_id == location_id)
            | (StockMovement.to_location_id == location_id)
        )
    if direction:
        q = q.where(StockMovement.direction == direction)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(StockMovement.occurred_at.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


# ── Custody report (manufacturing) ──────────────────────────────────────────


@router.get("/custody")
def customer_goods_custody(session: SessionDep, user: CurrentUserDep):
    """Per-customer, per-lot view of customer goods currently in our custody.

    Aggregates `InventoryLayer` rows where `owner_customer_id` is set —
    these are goods belonging to a customer that we haven't yet delivered
    back. Returns one row per (customer, product, lot_no).
    """
    rows = session.exec(
        select(
            InventoryLayer.owner_customer_id,
            Product.id, Product.code, Product.name,
            InventoryLayer.lot_no,
            InventoryLayer.location_id,
            func.sum(InventoryLayer.qty_remaining).label("qty_on_hand"),
        )
        .join(Product, Product.id == InventoryLayer.product_id)
        .where(
            InventoryLayer.tenant_id == user.tenant_id,
            InventoryLayer.owner_customer_id.is_not(None),
            InventoryLayer.qty_remaining > 0,
        )
        .group_by(
            InventoryLayer.owner_customer_id,
            Product.id,
            InventoryLayer.lot_no,
            InventoryLayer.location_id,
        )
        .order_by(InventoryLayer.owner_customer_id, Product.code)
    ).all()
    return [
        {
            "customer_id": r.owner_customer_id,
            "product_id": r.id,
            "product_code": r.code,
            "product_name": r.name,
            "lot_no": r.lot_no,
            "location_id": r.location_id,
            "qty_on_hand": r.qty_on_hand,
        }
        for r in rows
    ]
