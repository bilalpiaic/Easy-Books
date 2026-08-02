"""Landed-cost allocation onto inventory layers (#257 / IAS 2).

Posts Dr Inventory / Cr Landed Cost Clearing and bumps each target layer's
`unit_cost` (and the product's running avg_cost) by the allocated amount.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from models import (
    Account, InventoryLayer, LandedCost, LandedCostAllocation, Product, User,
)
from routers.common import get_or_create_account, next_number
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction


class LandedCostError(Exception):
    pass


def _clearing_account(session: Session, tenant_id: int) -> Account:
    return get_or_create_account(
        session, tenant_id, "1290", "Landed Cost Clearing", "Asset",
    )


def _inventory_account(session: Session, tenant_id: int) -> Account:
    return get_or_create_account(
        session, tenant_id, "1200", "Inventory (Raw Material)", "Asset",
    )


def layers_for_source_doc(session: Session, tenant_id: int, source_doc: str) -> list[InventoryLayer]:
    return list(session.exec(
        select(InventoryLayer).where(
            InventoryLayer.tenant_id == tenant_id,
            InventoryLayer.source_doc == source_doc,
            InventoryLayer.qty_remaining > 0,
        ).order_by(InventoryLayer.id)
    ).all())


def plan_allocation(
    layers: list[InventoryLayer],
    amount: Decimal,
    method: str = "value",
) -> list[dict]:
    """Pure allocation math — returns [{layer, amount, qty_basis, value_basis}]."""
    amount = money(amount)
    if amount <= ZERO or not layers:
        return []
    bases: list[tuple[InventoryLayer, Decimal]] = []
    for ly in layers:
        qty = D(ly.qty_remaining)
        if method == "qty":
            bases.append((ly, qty))
        else:
            bases.append((ly, money(qty * D(ly.unit_cost))))
    total_basis = sum((b for _, b in bases), ZERO)
    if total_basis <= ZERO:
        return []
    out: list[dict] = []
    allocated = ZERO
    for i, (ly, basis) in enumerate(bases):
        if i == len(bases) - 1:
            share = money(amount - allocated)
        else:
            share = money(amount * (basis / total_basis))
            allocated += share
        out.append({
            "layer": ly,
            "amount": share,
            "qty_basis": D(ly.qty_remaining),
            "value_basis": money(D(ly.qty_remaining) * D(ly.unit_cost)),
        })
    return out


def post_landed_cost(
    session: Session,
    actor: User,
    lc: LandedCost,
) -> LandedCost:
    if lc.status != "draft":
        raise LandedCostError("Only draft landed costs can be posted")
    source = lc.goods_source_doc
    if not source and lc.goods_bill_id:
        from models import Bill
        bill = session.get(Bill, lc.goods_bill_id)
        if bill and bill.tenant_id == lc.tenant_id:
            source = bill.number
            lc.goods_source_doc = source
    if not source:
        raise LandedCostError("goods_source_doc or goods_bill_id is required")

    layers = layers_for_source_doc(session, lc.tenant_id, source)
    if not layers:
        raise LandedCostError(f"No open inventory layers for {source}")

    plan = plan_allocation(layers, D(lc.amount), lc.allocation_method or "value")
    if not plan:
        raise LandedCostError("Nothing to allocate")

    # Clear prior allocations if re-posting draft scratch
    for old in session.exec(
        select(LandedCostAllocation).where(LandedCostAllocation.landed_cost_id == lc.id)
    ).all():
        session.delete(old)
    session.flush()

    for row in plan:
        ly: InventoryLayer = row["layer"]
        share = row["amount"]
        qty = D(ly.qty_remaining)
        if qty > ZERO and share > ZERO:
            # Spread share across remaining qty → bump unit cost
            ly.unit_cost = money(D(ly.unit_cost) + (share / qty))
            session.add(ly)
        session.add(LandedCostAllocation(
            tenant_id=lc.tenant_id,
            landed_cost_id=lc.id,  # type: ignore
            product_id=ly.product_id,
            layer_id=ly.id,  # type: ignore
            amount=share,
            qty_basis=row["qty_basis"],
            value_basis=row["value_basis"],
        ))
        # Refresh product avg_cost from remaining layers
        _recompute_avg(session, lc.tenant_id, ly.product_id)

    inv = _inventory_account(session, lc.tenant_id)
    clearing = _clearing_account(session, lc.tenant_id)
    amt = money(lc.amount)
    txn = post_transaction(
        session, actor,
        date=lc.cost_date,
        description=f"Landed cost {lc.number} → {source}",
        entries=[
            EntryInput(account_id=inv.id, debit=amt),
            EntryInput(account_id=clearing.id, credit=amt),
        ],
        reference=lc.number,
        audit_entity_type="landed_cost",
        audit_detail={"amount": str(amt), "source_doc": source},
        voucher_type="JV",
    )
    lc.status = "posted"
    lc.transaction_id = txn.id
    session.add(lc)
    session.flush()
    return lc


def _recompute_avg(session: Session, tenant_id: int, product_id: int) -> None:
    prod = session.exec(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
        .with_for_update()
    ).first()
    if not prod:
        return
    layers = session.exec(
        select(InventoryLayer).where(
            InventoryLayer.tenant_id == tenant_id,
            InventoryLayer.product_id == product_id,
            InventoryLayer.qty_remaining > 0,
        )
    ).all()
    total_qty = sum((D(l.qty_remaining) for l in layers), ZERO)
    if total_qty <= ZERO:
        return
    total_val = sum((D(l.qty_remaining) * D(l.unit_cost) for l in layers), ZERO)
    prod.avg_cost = money(total_val / total_qty)
    session.add(prod)


def create_draft(
    session: Session,
    actor: User,
    *,
    cost_date: str,
    amount: Decimal,
    goods_source_doc: Optional[str] = None,
    goods_bill_id: Optional[int] = None,
    charge_bill_id: Optional[int] = None,
    allocation_method: str = "value",
    description: Optional[str] = None,
) -> LandedCost:
    if allocation_method not in ("value", "qty"):
        raise LandedCostError("allocation_method must be value or qty")
    number = next_number(session, actor.tenant_id, "landed_cost", "LC")
    lc = LandedCost(
        tenant_id=actor.tenant_id,
        number=number,
        cost_date=cost_date,
        amount=money(amount),
        goods_source_doc=goods_source_doc,
        goods_bill_id=goods_bill_id,
        charge_bill_id=charge_bill_id,
        allocation_method=allocation_method,
        description=description,
        status="draft",
        created_by_id=actor.id,
    )
    session.add(lc)
    session.flush()
    return lc
