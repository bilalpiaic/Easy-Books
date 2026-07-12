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

from models import InventoryLayer, Product, StockLocation, StockMovement
from services.money import D, ZERO, money


class InventoryError(Exception):
    """Raised when stock would go negative or product is misconfigured."""


def _default_own_location(session: Session, tenant_id: int) -> Optional[int]:
    """Returns the first 'own'-type StockLocation id for the tenant, or None
    if multi-location isn't initialised yet. Existing call sites that don't
    specify a location use this so behaviour is backwards-compatible."""
    loc = session.exec(
        select(StockLocation).where(
            StockLocation.tenant_id == tenant_id,
            StockLocation.type == "own",
            StockLocation.is_active == True,  # noqa: E712
        ).order_by(StockLocation.id)
    ).first()
    return loc.id if loc else None


def record_movement(
    session: Session,
    *,
    tenant_id: int,
    product_id: int,
    direction: str,
    qty: Decimal,
    from_location_id: Optional[int] = None,
    to_location_id: Optional[int] = None,
    lot_no: Optional[str] = None,
    owner_customer_id: Optional[int] = None,
    unit_cost: Decimal = ZERO,
    source_doc_type: Optional[str] = None,
    source_doc_id: Optional[int] = None,
    transaction_id: Optional[int] = None,
    posted_to_gl: bool = False,
    notes: Optional[str] = None,
) -> StockMovement:
    """Append a row to the stock movement log. Returns the persisted row.

    Pure event-sourcing helper — does NOT touch InventoryLayer / Product
    state. Callers that need to mutate layers should use record_purchase /
    consume_stock which call this helper as part of their work.
    """
    qty = D(qty)
    if qty <= 0:
        raise InventoryError(f"qty must be > 0; got {qty}")
    mv = StockMovement(
        tenant_id=tenant_id,
        product_id=product_id,
        direction=direction,
        qty=qty,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        lot_no=lot_no,
        owner_customer_id=owner_customer_id,
        unit_cost=money(unit_cost),
        total_cost=money(qty * D(unit_cost)),
        source_doc_type=source_doc_type,
        source_doc_id=source_doc_id,
        transaction_id=transaction_id,
        posted_to_gl=posted_to_gl,
        notes=notes,
    )
    session.add(mv)
    session.flush()
    return mv


def record_purchase(
    session: Session,
    *,
    tenant_id: int,
    product_id: int,
    qty: Decimal,
    unit_cost: Decimal,
    source_doc: Optional[str] = None,
    location_id: Optional[int] = None,
    lot_no: Optional[str] = None,
    source_doc_type: str = "bill",
    posted_to_gl: bool = True,
) -> None:
    """
    Record a stock receipt: append a cost layer + update product avg_cost and stock_qty.
    Only effective for product_type == "stock"; services are no-ops.

    source_doc_type/posted_to_gl default to the historical bill-receipt
    values; the opening-balance bootstrap passes ("opening", False) since
    no GL entry backs an opening quantity.

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

    # Resolve location: explicit > tenant's default 'own' location > none
    loc_id = location_id or _default_own_location(session, tenant_id)
    session.add(
        InventoryLayer(
            tenant_id=tenant_id,
            product_id=product_id,
            location_id=loc_id,
            lot_no=lot_no,
            qty_received=qty,
            qty_remaining=qty,
            unit_cost=unit_cost,
            source_doc=source_doc,
        )
    )
    # Event log
    record_movement(
        session,
        tenant_id=tenant_id,
        product_id=product_id,
        direction="RECEIPT",
        qty=qty,
        to_location_id=loc_id,
        lot_no=lot_no,
        unit_cost=unit_cost,
        source_doc_type=source_doc_type,
        notes=source_doc,
        posted_to_gl=posted_to_gl,
    )


def consume_stock(
    session: Session,
    *,
    tenant_id: int,
    product_id: int,
    qty: Decimal,
    block_negative: bool = False,
    source_doc_id: Optional[int] = None,
    source_doc_type: str = "invoice",
) -> Decimal:
    """
    Relieve stock for a sale. Returns total COGS.

    Cost method is read from Tenant.cost_method (IAS 2.25):
    - wavg (default): charge COGS at the running weighted-average cost.
    - fifo: charge COGS at each layer's own unit_cost (first-in first-out).

    If block_negative is True, raises InventoryError before any mutation
    when the sale would drive stock below zero.

    source_doc_id: the originating document's id so the resulting
    StockMovement can be looked up by (source_doc_type, source_doc_id).
    source_doc_type: defaults to 'invoice' (existing behavior for every
    current caller); pass an override for non-invoice consumers (e.g.
    'gate_outward' for scrap disposal).
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

    if block_negative and D(prod.stock_qty) < qty:
        raise InventoryError(
            f"Insufficient stock for {prod.name}: on hand {money(prod.stock_qty)}, "
            f"sale {money(qty)}"
        )

    # Effective cost method: product override → tenant setting → wavg default
    from models import Tenant as _Tenant
    _tenant = session.get(_Tenant, tenant_id)
    _tenant_cost_method = getattr(_tenant, "cost_method", "wavg") if _tenant else "wavg"
    _cost_method = getattr(prod, "cost_method", None) or _tenant_cost_method

    avg_cost = D(prod.avg_cost)

    # Fetch layers first (needed for both FIFO and WAvg layer depletion)
    layers = session.exec(
        select(InventoryLayer)
        .where(
            InventoryLayer.tenant_id == tenant_id,
            InventoryLayer.product_id == product_id,
            InventoryLayer.qty_remaining > 0,
        )
        .order_by(InventoryLayer.id.asc())
    ).all()

    if _cost_method == "fifo":
        # Accumulate COGS layer by layer at each layer's unit_cost
        fifo_cogs = ZERO
        fifo_remaining = qty
        for _lyr in layers:
            if fifo_remaining <= ZERO:
                break
            _take = min(D(_lyr.qty_remaining), fifo_remaining)
            fifo_cogs += money(_take * D(_lyr.unit_cost))
            fifo_remaining -= _take
        cogs = fifo_cogs
    else:
        cogs = money(qty * avg_cost)

    prod.stock_qty = D(prod.stock_qty) - qty
    session.add(prod)

    # Deplete layers FIFO (layers already fetched above for cost calculation).
    remaining = qty
    consumed_from_location_id: Optional[int] = None
    consumed_lot_no: Optional[str] = None
    for layer in layers:
        if remaining <= 0:
            break
        take = min(D(layer.qty_remaining), remaining)
        layer.qty_remaining = D(layer.qty_remaining) - take
        remaining -= take
        session.add(layer)
        # Track the first layer touched so the movement row carries
        # provenance (which lot/location got drained).
        if consumed_from_location_id is None:
            consumed_from_location_id = layer.location_id
            consumed_lot_no = layer.lot_no

    if qty > 0:
        record_movement(
            session,
            tenant_id=tenant_id,
            product_id=product_id,
            direction="SHIPMENT",
            qty=qty,
            from_location_id=consumed_from_location_id or _default_own_location(session, tenant_id),
            lot_no=consumed_lot_no,
            unit_cost=avg_cost,
            source_doc_type=source_doc_type,
            source_doc_id=source_doc_id,
            posted_to_gl=True,
        )

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
        reversed_qty = D(layer.qty_remaining)
        layer_loc, layer_lot, layer_cost = layer.location_id, layer.lot_no, D(layer.unit_cost)
        prod.stock_qty = D(prod.stock_qty) - reversed_qty
        session.add(prod)
        session.delete(layer)
        session.flush()

        # Event log — without this row the Stock Tie-out shows a permanent
        # negative variance for every voided/edited bill (#145 follow-up).
        if reversed_qty > 0:
            record_movement(
                session,
                tenant_id=tenant_id,
                product_id=prod.id,
                direction="ADJUSTMENT",
                qty=reversed_qty,
                from_location_id=layer_loc or _default_own_location(session, tenant_id),
                lot_no=layer_lot,
                unit_cost=layer_cost,
                source_doc_type="bill_void",
                posted_to_gl=True,
                notes=f"Reversal of receipt from {source_doc}",
            )

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


def return_to_vendor(
    session: Session,
    *,
    tenant_id: int,
    product_id: int,
    qty: Decimal,
    source_doc: str,
) -> Decimal:
    """Purchase Return: remove `qty` of a product from the layers created by the
    original bill (`source_doc == bill.number`), at those layers' original cost.

    Returns the total cost removed (used as the GL inventory credit). Reduces
    `Product.stock_qty` and recomputes `avg_cost` from the remaining layers.

    Raises InventoryError if the bill's layers no longer hold enough remaining
    quantity to cover the return (e.g. already sold under WAvg/FIFO).
    """
    qty = D(qty)
    if qty <= 0:
        return ZERO

    layers = session.exec(
        select(InventoryLayer)
        .where(
            InventoryLayer.tenant_id == tenant_id,
            InventoryLayer.product_id == product_id,
            InventoryLayer.source_doc == source_doc,
            InventoryLayer.qty_remaining > 0,
        )
        .order_by(InventoryLayer.id.asc())
    ).all()

    available = sum((D(l.qty_remaining) for l in layers), start=ZERO)
    if available < qty:
        raise InventoryError(
            f"Cannot return {qty} of product {product_id}: only {available} "
            f"remain from bill {source_doc} (rest already consumed)."
        )

    prod = session.exec(
        select(Product)
        .where(Product.id == product_id, Product.tenant_id == tenant_id)
        .with_for_update()
    ).first()
    if not prod:
        raise InventoryError(f"Product {product_id} not found")

    remaining_to_remove = qty
    cost_removed = ZERO
    from_loc: Optional[int] = None
    lot: Optional[str] = None
    for layer in layers:
        if remaining_to_remove <= 0:
            break
        take = min(D(layer.qty_remaining), remaining_to_remove)
        layer.qty_remaining = D(layer.qty_remaining) - take
        cost_removed += money(take * D(layer.unit_cost))
        remaining_to_remove -= take
        session.add(layer)
        if from_loc is None:
            from_loc = layer.location_id
            lot = layer.lot_no

    prod.stock_qty = D(prod.stock_qty) - qty
    session.add(prod)
    session.flush()

    # Recompute avg_cost from whatever layers remain for this product.
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

    record_movement(
        session,
        tenant_id=tenant_id,
        product_id=product_id,
        direction="ADJUSTMENT",
        qty=qty,
        from_location_id=from_loc or _default_own_location(session, tenant_id),
        lot_no=lot,
        unit_cost=money(cost_removed / qty) if qty > 0 else ZERO,
        source_doc_type="debit_note",
        posted_to_gl=True,
        notes=f"Purchase return against {source_doc}",
    )
    return money(cost_removed)
