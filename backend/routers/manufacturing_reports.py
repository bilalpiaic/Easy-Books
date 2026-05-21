"""Manufacturing-specific reports for the manufacturing business model.

These endpoints aggregate ProductionOrder + GRN + StockMovement state into
the views a shop-floor manager actually wants:

  /api/manufacturing/dashboard  — pipeline KPIs + recent activity
  /api/manufacturing/wip-aging  — open POs grouped by age bucket
  /api/manufacturing/production-summary — counts/values by state
  /api/manufacturing/customer-custody — per-customer goods-on-hand
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter
from sqlmodel import func, select

from models import (
    Customer, GoodsReceiptNote, InventoryLayer, Product, ProductionOrder,
    StockLocation,
)
from services.money import D, ZERO

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/manufacturing", tags=["manufacturing-reports"])


@router.get("/dashboard")
def dashboard(session: SessionDep, user: CurrentUserDep):
    """High-level KPI tile data for the manufacturing landing page."""
    tid = user.tenant_id

    # Pipeline counts by state
    rows = session.exec(
        select(ProductionOrder.state, func.count(ProductionOrder.id))
        .where(ProductionOrder.tenant_id == tid)
        .group_by(ProductionOrder.state)
    ).all()
    counts = {state: cnt for state, cnt in rows}

    # Total WIP cost = sum(own_material_cost) for started POs
    wip_total = session.exec(
        select(func.coalesce(func.sum(ProductionOrder.own_material_cost), 0))
        .where(
            ProductionOrder.tenant_id == tid,
            ProductionOrder.state == "started",
        )
    ).one()

    # Total FG-on-hand cost = sum(output_unit_cost × output_qty) for completed
    fg_total = session.exec(
        select(func.coalesce(
            func.sum(ProductionOrder.output_unit_cost * ProductionOrder.output_qty), 0
        ))
        .where(
            ProductionOrder.tenant_id == tid,
            ProductionOrder.state == "completed",
        )
    ).one()

    # Customer goods held = sum of qty_remaining across custodial layers
    custodial = session.exec(
        select(func.coalesce(func.sum(InventoryLayer.qty_remaining), 0))
        .where(
            InventoryLayer.tenant_id == tid,
            InventoryLayer.owner_customer_id.is_not(None),
            InventoryLayer.qty_remaining > 0,
        )
    ).one()

    return {
        "pipeline": {
            "draft":     counts.get("draft", 0),
            "started":   counts.get("started", 0),
            "completed": counts.get("completed", 0),
            "delivered": counts.get("delivered", 0),
            "billed":    counts.get("billed", 0),
            "cancelled": counts.get("cancelled", 0),
        },
        "totals": {
            "wip_cost":           str(D(wip_total)),
            "finished_goods_cost": str(D(fg_total)),
            "custodial_qty":       str(D(custodial)),
        },
    }


@router.get("/wip-aging")
def wip_aging(session: SessionDep, user: CurrentUserDep):
    """Open production orders (started, not yet completed) grouped by age
    buckets in days since started_at."""
    pos = session.exec(
        select(ProductionOrder).where(
            ProductionOrder.tenant_id == user.tenant_id,
            ProductionOrder.state == "started",
        )
    ).all()

    now = datetime.utcnow()
    buckets = {"0-7d": [], "8-14d": [], "15-30d": [], "30d+": []}

    def _bucket_for(days: int) -> str:
        if days <= 7:
            return "0-7d"
        if days <= 14:
            return "8-14d"
        if days <= 30:
            return "15-30d"
        return "30d+"

    for po in pos:
        started = po.started_at or po.created_at
        age = (now - started).days
        buckets[_bucket_for(age)].append({
            "id": po.id, "number": po.number,
            "customer_id": po.customer_id,
            "output_qty": str(D(po.output_qty)),
            "own_material_cost": str(D(po.own_material_cost)),
            "started_at": started.isoformat(),
            "age_days": age,
        })

    summary = {
        bucket: {
            "count": len(items),
            "total_wip_cost": str(sum((D(i["own_material_cost"]) for i in items), start=ZERO)),
        }
        for bucket, items in buckets.items()
    }
    return {"summary": summary, "buckets": buckets}


@router.get("/production-summary")
def production_summary(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    """POs grouped by state, with value totals and revenue when billed.
    Optional date range filters on created_at."""
    q = select(ProductionOrder).where(ProductionOrder.tenant_id == user.tenant_id)
    pos = session.exec(q).all()

    def _in_range(po: ProductionOrder) -> bool:
        d = po.created_at.date().isoformat() if po.created_at else None
        if not d:
            return True
        if start and d < start:
            return False
        if end and d > end:
            return False
        return True

    pos = [p for p in pos if _in_range(p)]

    by_state: dict[str, dict] = {}
    for po in pos:
        s = by_state.setdefault(po.state, {"count": 0, "output_qty": ZERO, "cost": ZERO})
        s["count"] += 1
        s["output_qty"] += D(po.output_qty)
        s["cost"] += D(po.own_material_cost)
    # Stringify for JSON
    return {
        state: {
            "count": v["count"],
            "output_qty": str(v["output_qty"]),
            "cost": str(v["cost"]),
        }
        for state, v in by_state.items()
    }


@router.get("/customer-custody")
def customer_custody(session: SessionDep, user: CurrentUserDep):
    """Per-customer summary of goods we currently hold custodially.

    Computed from InventoryLayer.qty_remaining where owner_customer_id is
    set. Returns one row per (customer, product) with current on-hand qty
    and the total declared value of GRNs still unreleased.
    """
    rows = session.exec(
        select(
            InventoryLayer.owner_customer_id,
            InventoryLayer.product_id,
            func.sum(InventoryLayer.qty_remaining),
        )
        .where(
            InventoryLayer.tenant_id == user.tenant_id,
            InventoryLayer.owner_customer_id.is_not(None),
            InventoryLayer.qty_remaining > 0,
        )
        .group_by(InventoryLayer.owner_customer_id, InventoryLayer.product_id)
    ).all()

    if not rows:
        return []

    cust_ids = {r[0] for r in rows}
    prod_ids = {r[1] for r in rows}
    customers = {
        c.id: c.name for c in session.exec(
            select(Customer).where(Customer.id.in_(cust_ids))
        ).all()
    }
    products = {
        p.id: {"code": p.code, "name": p.name, "unit": p.unit}
        for p in session.exec(
            select(Product).where(Product.id.in_(prod_ids))
        ).all()
    }

    # Sum un-released declared values per customer
    grns = session.exec(
        select(GoodsReceiptNote).where(
            GoodsReceiptNote.tenant_id == user.tenant_id,
            GoodsReceiptNote.declared_value > 0,
        )
    ).all()
    declared_by_customer: dict[int, Decimal] = {}
    for g in grns:
        declared_by_customer[g.customer_id] = (
            declared_by_customer.get(g.customer_id, ZERO) + D(g.declared_value)
        )

    return [
        {
            "customer_id": cid,
            "customer_name": customers.get(cid, ""),
            "product_id": pid,
            "product": products.get(pid, {}),
            "qty_on_hand": str(D(qty)),
            "declared_value_open": str(declared_by_customer.get(cid, ZERO)),
        }
        for cid, pid, qty in rows
    ]
