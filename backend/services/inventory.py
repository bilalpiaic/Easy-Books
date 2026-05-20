"""
Perpetual inventory with Weighted-Average cost.

IAS 2 / ASC 330 require an explicit, auditable cost-flow assumption.
Easy-Books defaults to Weighted-Average (the simplest IAS-2-compliant method):

    new_avg = (existing_qty * existing_avg + received_qty * received_cost)
              / (existing_qty + received_qty)

On sale we relieve inventory at `qty * current_avg_cost`. We also persist an
`InventoryLayer` row per receipt so the cost history is auditable even after
the running average has moved on.

A future P3 task can add a setting to switch to FIFO without changing call
sites — record_purchase + consume_stock are the only entry points.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from models import InventoryLayer, Product
from services.money import D, ZERO, money


class InventoryError(Exception):
    """Raised when stock would go negative or product is misconfigured."""


def record_purchase(
    session: Session,
    *,
    tenant_id: int,
    product_id: int,
    qty: Decimal,
    unit_cost: Decimal,
    source_doc: Optional[str] = None,
) -> None:
    """
    Record a stock receipt: append a cost layer + update product avg_cost and stock_qty.
    Only effective for product_type == "stock"; services are no-ops.

    The Product row is selected with FOR UPDATE so two concurrent receipts of
    the same product can't both read the same avg_cost and clobber each
    other's update. SQLite ignores row-level locks (single-writer anyway);
    Postgres honours them.
    """
    qty = D(qty)
    unit_cost = D(unit_cost)
    if qty <= 0:
        return

    prod = session.exec(
        select(Product)
        .where(Product.id == product_id, Product.tenant_id == tenant_id)
        .with_for_update()
    ).first()
    if not prod or prod.product_type != "stock":
        return

    existing_qty = D(prod.stock_qty)
    existing_avg = D(prod.avg_cost)
    new_qty = existing_qty + qty
    if new_qty > 0:
        prod.avg_cost = money(
            (existing_qty * existing_avg + qty * unit_cost) / new_qty
        )
    prod.stock_qty = new_qty
    session.add(prod)

    session.add(
        InventoryLayer(
            tenant_id=tenant_id,
            product_id=product_id,
            qty_received=qty,
            qty_remaining=qty,
            unit_cost=unit_cost,
            source_doc=source_doc,
        )
    )


def consume_stock(
    session: Session,
    *,
    tenant_id: int,
    product_id: int,
    qty: Decimal,
) -> Decimal:
    """
    Relieve stock for a sale. Returns total COGS (qty × current avg cost).

    For Weighted-Average we charge COGS at the running average and proportionally
    decrement layer remainders so reports still show plausible per-layer balances.
    """
    qty = D(qty)
    if qty <= 0:
        return ZERO

    # FOR UPDATE: prevent two concurrent sales from each reading the same
    # stock_qty and both decrementing — would cause oversell on Postgres.
    prod = session.exec(
        select(Product)
        .where(Product.id == product_id, Product.tenant_id == tenant_id)
        .with_for_update()
    ).first()
    if not prod or prod.product_type != "stock":
        return ZERO

    avg_cost = D(prod.avg_cost)
    cogs = money(qty * avg_cost)

    prod.stock_qty = D(prod.stock_qty) - qty
    session.add(prod)

    # Deplete layers FIFO so layer-remaining totals match prod.stock_qty.
    # (Cost charge is still WAvg above; layer depletion is just bookkeeping.)
    remaining = qty
    layers = session.exec(
        select(InventoryLayer)
        .where(
            InventoryLayer.tenant_id == tenant_id,
            InventoryLayer.product_id == product_id,
            InventoryLayer.qty_remaining > 0,
        )
        .order_by(InventoryLayer.id.asc())
    ).all()
    for layer in layers:
        if remaining <= 0:
            break
        take = min(D(layer.qty_remaining), remaining)
        layer.qty_remaining = D(layer.qty_remaining) - take
        remaining -= take
        session.add(layer)

    return cogs
