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


def reverse_purchase(
    session: Session,
    *,
    tenant_id: int,
    source_doc: str,
) -> None:
    """Undo a stock receipt previously created by `record_purchase`.

    Subtracts the layer's remaining qty from `Product.stock_qty` and drops
    the layer entirely. Recomputes `Product.avg_cost` as the weighted
    average of whatever layers remain.

    Caller invariants:
      - source_doc uniquely identifies the receipt (bill.number).
      - If some of the layer has already been consumed (FIFO depleted),
        only the unsold remainder is removed — the consumed portion
        already affected COGS and stays in history.
    """
    layers = session.exec(
        select(InventoryLayer).where(
            InventoryLayer.tenant_id == tenant_id,
            InventoryLayer.source_doc == source_doc,
        )
    ).all()
    if not layers:
        return

    for layer in layers:
        prod = session.exec(
            select(Product)
            .where(Product.id == layer.product_id, Product.tenant_id == tenant_id)
            .with_for_update()
        ).first()
        if not prod:
            continue
        prod.stock_qty = D(prod.stock_qty) - D(layer.qty_remaining)
        session.add(prod)
        session.delete(layer)
        session.flush()

        # Recompute avg_cost from remaining layers for this product
        remaining = session.exec(
            select(InventoryLayer).where(
                InventoryLayer.tenant_id == tenant_id,
                InventoryLayer.product_id == prod.id,
                InventoryLayer.qty_remaining > 0,
            )
        ).all()
        total_qty = sum((D(l.qty_remaining) for l in remaining), start=ZERO)
        if total_qty > 0:
            weighted = sum(
                (D(l.qty_remaining) * D(l.unit_cost) for l in remaining), start=ZERO
            )
            prod.avg_cost = money(weighted / total_qty)
        else:
            prod.avg_cost = ZERO
        session.add(prod)


def reverse_consumption(
    session: Session,
    *,
    tenant_id: int,
    product_id: int,
    qty: Decimal,
    cogs_total: Decimal,
) -> None:
    """Undo a `consume_stock` call by restoring stock at the COGS unit cost.

    Equivalent to recording a new purchase at unit_cost = cogs_total / qty,
    tagged so it doesn't collide with real purchases.
    """
    qty = D(qty)
    if qty <= 0:
        return
    unit_cost = D(cogs_total) / qty
    record_purchase(
        session,
        tenant_id=tenant_id,
        product_id=product_id,
        qty=qty,
        unit_cost=unit_cost,
        source_doc="REVERSAL",
    )
