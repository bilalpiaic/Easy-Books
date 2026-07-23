"""ProductionOrder lifecycle: draft → started → completed → delivered → billed.

Each transition is its own endpoint so the UI can guide the user step by
step, and so each event lives as a separate Transaction in the GL (easier
to reverse, audit, and reason about than a giant multi-stage JE).

Cost flow (per user directive 8.3.8 — "all absorbed costs flow through WIP"):

  start    : Dr 1201 WIP                Cr 1200 Raw Material  (own_stock only)
             Customer-supplied components → CUSTODIAL_ISSUE movement, no JE
  complete : Dr 1202 Finished Goods     Cr 1201 WIP            (cost from start)
  deliver  : Dr 5010 COGS               Cr 1202 Finished Goods (FG → expense)
             Dr 2150 Cust Goods Liab    Cr 1210 Cust Goods on Hand  (memo release,
             only if the related GRNs posted a memo JE)
  bill     : Invoice via RatePlan (per_unit_rate × qty + optional materials
             passthrough + overhead% + margin%). Invoice posting handled by
             /api/invoices machinery via direct call to post_transaction.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import (
    BomHeader, BomLine, BomOutput, Customer, CustomerRatePlan, GoodsReceiptNote,
    GRNLine, InventoryLayer, Invoice, InvoiceLine, Product, ProductionOrder,
    ProductionOrderOutput, ProductionScrap, RatePlan, ScrapReason, StockLocation,
    StockMovement, Transaction,
)
from services.inventory import (
    InventoryError, consume_stock, record_movement, record_purchase, reverse_purchase,
)
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction

from services.permissions import perm_dep, apply_own_filter
from .common import (
    CurrentUserDep, SessionDep, WriteUserDep,
    get_default_account, get_or_create_account, log_audit, next_number,
)

router = APIRouter(prefix="/api/production-orders", tags=["production-orders"], dependencies=[perm_dep("production_orders")])


# ── Helpers ─────────────────────────────────────────────────────────────────


def _get_po(session, tenant_id: int, po_id: int) -> ProductionOrder:
    po = session.exec(
        select(ProductionOrder).where(
            ProductionOrder.id == po_id,
            ProductionOrder.tenant_id == tenant_id,
        )
    ).first()
    if not po:
        raise HTTPException(404, "Production order not found")
    return po


def _resolve_wip_location(session, tenant_id: int) -> StockLocation:
    loc = session.exec(
        select(StockLocation).where(
            StockLocation.tenant_id == tenant_id,
            StockLocation.type == "wip",
            StockLocation.is_active == True,  # noqa: E712
        ).order_by(StockLocation.id)
    ).first()
    if not loc:
        raise HTTPException(
            400,
            "No WIP location configured. Manufacturing tenants get one at signup; "
            "create a StockLocation with type='wip' first.",
        )
    return loc


def _resolve_main_own(session, tenant_id: int) -> StockLocation:
    loc = session.exec(
        select(StockLocation).where(
            StockLocation.tenant_id == tenant_id,
            StockLocation.type == "own",
            StockLocation.is_active == True,  # noqa: E712
        ).order_by(StockLocation.id)
    ).first()
    if not loc:
        raise HTTPException(400, "No 'own' stock location configured")
    return loc


def _bom_lines(session, bom_id: int) -> List[BomLine]:
    return session.exec(
        select(BomLine).where(BomLine.bom_id == bom_id).order_by(BomLine.id)
    ).all()


def _serialise(po: ProductionOrder, session=None) -> dict:
    out = po.model_dump()
    for k in ("created_at", "started_at", "completed_at", "delivered_at",
              "billed_at", "cancelled_at"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    if session is not None:
        outs = session.exec(
            select(ProductionOrderOutput)
            .where(ProductionOrderOutput.po_id == po.id)
            .order_by(ProductionOrderOutput.id)
        ).all()
        out["outputs"] = [o.model_dump() for o in outs]
        scraps = session.exec(
            select(ProductionScrap)
            .where(ProductionScrap.po_id == po.id)
            .order_by(ProductionScrap.id)
        ).all()
        scrap_rows = []
        for s in scraps:
            d = s.model_dump()
            if isinstance(d.get("created_at"), datetime):
                d["created_at"] = d["created_at"].isoformat()
            scrap_rows.append(d)
        out["scraps"] = scrap_rows
    else:
        out["outputs"] = []
        out["scraps"] = []
    return out


def _bom_outputs(session, bom: BomHeader) -> list:
    """Return BomOutput rows, or synthesize primary from header (legacy)."""
    rows = session.exec(
        select(BomOutput).where(BomOutput.bom_id == bom.id).order_by(BomOutput.id)
    ).all()
    if rows:
        return list(rows)
    return [
        BomOutput(
            bom_id=bom.id,
            product_id=bom.output_product_id,
            qty_per_batch=D(bom.output_qty),
            role="primary",
            alloc_pct=None,
            sales_price_hint=None,
        )
    ]


def _allocate_output_costs(
    session, bom: BomHeader, bom_outputs: list, batches: Decimal, total_cost: Decimal,
) -> list[tuple]:
    """Return [(product_id, role, qty, unit_cost), ...] for complete."""
    method = getattr(bom, "cost_alloc_method", None) or "primary_only"
    planned: list[tuple] = []
    for o in bom_outputs:
        qty = money(D(o.qty_per_batch) * batches)
        planned.append((o, qty))

    if not planned:
        return []

    costs: dict[int, Decimal] = {}
    if method == "primary_only" or len(planned) == 1:
        for o, qty in planned:
            costs[id(o)] = total_cost if o.role == "primary" else ZERO
    elif method == "fixed_pct":
        for o, qty in planned:
            pct = D(o.alloc_pct or 0)
            costs[id(o)] = money(total_cost * pct / Decimal("100"))
        # Fix rounding drift onto primary
        assigned = sum(costs.values(), start=ZERO)
        drift = money(total_cost - assigned)
        if drift != 0:
            for o, _qty in planned:
                if o.role == "primary":
                    costs[id(o)] = money(costs[id(o)] + drift)
                    break
    elif method == "relative_sales_value":
        weights: list[tuple] = []
        for o, qty in planned:
            hint = o.sales_price_hint
            if hint is None:
                prod = session.get(Product, o.product_id)
                hint = D(prod.default_rate) if prod else ZERO
            else:
                hint = D(hint)
            w = qty * hint
            weights.append((o, qty, w))
        total_w = sum((w for _o, _q, w in weights), start=ZERO)
        if total_w <= 0:
            for o, qty in planned:
                costs[id(o)] = total_cost if o.role == "primary" else ZERO
        else:
            assigned = ZERO
            for o, qty, w in weights:
                share = money(total_cost * w / total_w)
                costs[id(o)] = share
                assigned += share
            drift = money(total_cost - assigned)
            if drift != 0:
                for o, _qty, _w in weights:
                    if o.role == "primary":
                        costs[id(o)] = money(costs[id(o)] + drift)
                        break
    else:
        for o, qty in planned:
            costs[id(o)] = total_cost if o.role == "primary" else ZERO

    result = []
    for o, qty in planned:
        cost = costs.get(id(o), ZERO)
        unit = money(cost / qty) if qty > 0 else ZERO
        result.append((o.product_id, o.role, qty, unit, cost))
    return result


def _tag_completion_movement(session, user, po, product_id, wip_id):
    last_mv = session.exec(
        select(StockMovement)
        .where(
            StockMovement.tenant_id == user.tenant_id,
            StockMovement.product_id == product_id,
            StockMovement.direction == "RECEIPT",
        )
        .order_by(StockMovement.id.desc())
    ).first()
    if last_mv and last_mv.notes == po.number:
        last_mv.direction = "COMPLETION"
        last_mv.from_location_id = wip_id
        last_mv.source_doc_type = "production_order"
        last_mv.source_doc_id = po.id
        session.add(last_mv)


def _find_open_txn(session, tenant_id: int, description: str) -> Optional[Transaction]:
    return session.exec(
        select(Transaction).where(
            Transaction.tenant_id == tenant_id,
            Transaction.description == description,
            Transaction.is_reversed == False,  # noqa: E712
        )
    ).first()


def _mirror_txn(session, user, txn: Transaction) -> Transaction:
    """Post the mirror JV and mark the original reversed (same as journal reverse)."""
    from models import JournalEntry
    jes = session.exec(
        select(JournalEntry).where(JournalEntry.transaction_id == txn.id)
    ).all()
    if not jes:
        raise HTTPException(400, f"Transaction {txn.jv_number} has no journal lines to reverse")
    rev = post_transaction(
        session, user,
        date=datetime.utcnow().date().isoformat(),
        description=f"Reversal of {txn.jv_number}",
        entries=[
            EntryInput(account_id=je.account_id, debit=D(je.credit), credit=D(je.debit))
            for je in jes
        ],
        audit_entity_type="production_order",
        audit_detail={"original_jv": txn.jv_number, "stage": "reverse"},
        voucher_type=txn.voucher_type,
    )
    txn.is_reversed = True
    txn.reversed_by_id = rev.id
    session.add(txn)
    return rev


def _mirror_po_stage(session, user, po: ProductionOrder, stage_suffix: str) -> Optional[str]:
    """Reverse the stage JE for `{po.number} — {stage_suffix}` if still open."""
    desc = f"{po.number} — {stage_suffix}"
    txn = _find_open_txn(session, user.tenant_id, desc)
    if not txn:
        return None
    rev = _mirror_txn(session, user, txn)
    return rev.jv_number


def _recompute_avg_cost(session, tenant_id: int, product_id: int) -> None:
    prod = session.get(Product, product_id)
    if not prod or prod.tenant_id != tenant_id:
        return
    remaining = session.exec(
        select(InventoryLayer).where(
            InventoryLayer.tenant_id == tenant_id,
            InventoryLayer.product_id == product_id,
            InventoryLayer.qty_remaining > 0,
            InventoryLayer.owner_customer_id.is_(None),
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


def _mirror_po_stages_prefix(session, user, po: ProductionOrder, prefix: str) -> list[str]:
    """Reverse every open JE whose description starts with prefix (partial delivers)."""
    txns = session.exec(
        select(Transaction).where(
            Transaction.tenant_id == user.tenant_id,
            Transaction.description.like(f"{prefix}%"),  # type: ignore[attr-defined]
            Transaction.is_reversed == False,  # noqa: E712
        )
    ).all()
    out: list[str] = []
    for txn in txns:
        rev = _mirror_txn(session, user, txn)
        out.append(rev.jv_number)
    return out


def _unwind_deliver(session, user, po: ProductionOrder, bom: BomHeader) -> list[str]:
    """Undo delivery(ies): reverse COGS (+ memo) GL and restock FG at cost."""
    reversed_jvs: list[str] = []
    reversed_jvs.extend(_mirror_po_stages_prefix(session, user, po, f"{po.number} — deliver / COGS"))
    # Legacy full-deliver description (pre-#222) without qty suffix
    jv = _mirror_po_stage(session, user, po, "deliver / COGS")
    if jv:
        reversed_jvs.append(jv)
    jv = _mirror_po_stage(session, user, po, "release customer custody")
    if jv:
        reversed_jvs.append(jv)

    qty = D(po.delivered_qty) if D(po.delivered_qty) > 0 else D(po.output_qty)
    unit = D(po.output_unit_cost)
    if qty > 0:
        main_own = _resolve_main_own(session, user.tenant_id)
        record_purchase(
            session,
            tenant_id=user.tenant_id,
            product_id=bom.output_product_id,
            qty=qty,
            unit_cost=unit if unit > 0 else ZERO,
            source_doc=po.number,
            location_id=main_own.id,
            lot_no=po.number,
        )
        last_mv = session.exec(
            select(StockMovement)
            .where(
                StockMovement.tenant_id == user.tenant_id,
                StockMovement.product_id == bom.output_product_id,
                StockMovement.direction == "RECEIPT",
            )
            .order_by(StockMovement.id.desc())
        ).first()
        if last_mv and last_mv.notes == po.number:
            last_mv.direction = "ADJUSTMENT"
            last_mv.source_doc_type = "production_order"
            last_mv.source_doc_id = po.id
            last_mv.notes = f"Reversal of delivery for {po.number}"
            session.add(last_mv)

    po.state = "completed"
    po.delivered_at = None
    po.delivered_qty = ZERO
    for row in session.exec(
        select(ProductionOrderOutput).where(ProductionOrderOutput.po_id == po.id)
    ).all():
        row.delivered_qty = ZERO
        session.add(row)
    session.add(po)
    return reversed_jvs


def _unwind_complete(session, user, po: ProductionOrder, bom: BomHeader) -> list[str]:
    """Undo completion: remove FG receipt(s) + reverse capitalise JE."""
    reversed_jvs: list[str] = []
    reverse_purchase(session, tenant_id=user.tenant_id, source_doc=po.number)
    jv = _mirror_po_stage(session, user, po, "capitalise FG")
    if jv:
        reversed_jvs.append(jv)
    for row in session.exec(
        select(ProductionOrderOutput).where(ProductionOrderOutput.po_id == po.id)
    ).all():
        session.delete(row)
    po.state = "started"
    po.completed_at = None
    po.output_unit_cost = ZERO
    session.add(po)
    return reversed_jvs


def _unwind_start(session, user, po: ProductionOrder) -> list[str]:
    """Undo start: restore component/custodial stock + reverse WIP JE."""
    reversed_jvs: list[str] = []
    all_mv = session.exec(
        select(StockMovement).where(
            StockMovement.tenant_id == user.tenant_id,
            StockMovement.source_doc_type == "production_order",
            StockMovement.source_doc_id == po.id,
        )
    ).all()
    movements = [m for m in all_mv if m.direction in ("ISSUE", "CUSTODIAL_ISSUE")]

    for mv in movements:
        qty = D(mv.qty)
        if qty <= 0:
            continue
        unit_cost = D(mv.unit_cost)
        if mv.direction == "ISSUE":
            prod = session.get(Product, mv.product_id)
            if not prod:
                continue
            prod.stock_qty = D(prod.stock_qty) + qty
            session.add(prod)
            session.add(InventoryLayer(
                tenant_id=user.tenant_id,
                product_id=prod.id,
                location_id=mv.from_location_id,
                owner_customer_id=None,
                lot_no=mv.lot_no,
                qty_received=money(qty),
                qty_remaining=money(qty),
                unit_cost=money(unit_cost),
                source_doc=f"REV-{po.number}",
            ))
            record_movement(
                session,
                tenant_id=user.tenant_id,
                product_id=prod.id,
                direction="ADJUSTMENT",
                qty=qty,
                to_location_id=mv.from_location_id,
                from_location_id=mv.to_location_id,
                lot_no=mv.lot_no,
                unit_cost=unit_cost,
                source_doc_type="production_order",
                source_doc_id=po.id,
                posted_to_gl=True,
                notes=f"Reversal of issue for {po.number}",
            )
            session.flush()
            _recompute_avg_cost(session, user.tenant_id, prod.id)
        elif mv.direction == "CUSTODIAL_ISSUE":
            session.add(InventoryLayer(
                tenant_id=user.tenant_id,
                product_id=mv.product_id,
                location_id=mv.from_location_id,
                owner_customer_id=mv.owner_customer_id or po.customer_id,
                lot_no=mv.lot_no,
                qty_received=money(qty),
                qty_remaining=money(qty),
                unit_cost=money(unit_cost),
                source_doc=f"REV-{po.number}",
            ))
            record_movement(
                session,
                tenant_id=user.tenant_id,
                product_id=mv.product_id,
                direction="ADJUSTMENT",
                qty=qty,
                to_location_id=mv.from_location_id,
                from_location_id=mv.to_location_id,
                lot_no=mv.lot_no,
                owner_customer_id=mv.owner_customer_id or po.customer_id,
                unit_cost=unit_cost,
                source_doc_type="production_order",
                source_doc_id=po.id,
                posted_to_gl=False,
                notes=f"Reversal of custodial issue for {po.number}",
            )

    jv = _mirror_po_stage(session, user, po, "issue to WIP")
    if jv:
        reversed_jvs.append(jv)
    jv = _mirror_po_stage(session, user, po, "absorb labour")
    if jv:
        reversed_jvs.append(jv)
    jv = _mirror_po_stage(session, user, po, "absorb overhead")
    if jv:
        reversed_jvs.append(jv)

    po.state = "cancelled"
    po.cancelled_at = datetime.utcnow()
    po.started_at = None
    po.own_material_cost = ZERO
    po.labour_cost = ZERO
    po.overhead_cost = ZERO
    session.add(po)
    return reversed_jvs


# ── CRUD ────────────────────────────────────────────────────────────────────


class PoCreate(BaseModel):
    bom_id: int
    customer_id: int
    output_qty: Decimal
    rate_plan_id: Optional[int] = None
    notes: Optional[str] = None


@router.get("")
def list_pos(
    session: SessionDep, user: CurrentUserDep,
    state: Optional[str] = None,
    customer_id: Optional[int] = None,
    skip: int = 0, limit: int = 100,
):
    q = select(ProductionOrder).where(ProductionOrder.tenant_id == user.tenant_id)
    if state:
        q = q.where(ProductionOrder.state == state)
    if customer_id:
        q = q.where(ProductionOrder.customer_id == customer_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(ProductionOrder.id.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": [_serialise(p, session) for p in items]}


@router.get("/{po_id}")
def get_po(session: SessionDep, user: CurrentUserDep, po_id: int):
    po = _get_po(session, user.tenant_id, po_id)
    return _serialise(po, session)


@router.post("", status_code=201)
def create_po(session: SessionDep, user: WriteUserDep, body: PoCreate):
    if D(body.output_qty) <= 0:
        raise HTTPException(400, "output_qty must be > 0")
    bom = session.get(BomHeader, body.bom_id)
    if not bom or bom.tenant_id != user.tenant_id:
        raise HTTPException(400, "BoM not found")
    cust = session.get(Customer, body.customer_id)
    if not cust or cust.tenant_id != user.tenant_id:
        raise HTTPException(400, "Customer not found")
    if body.rate_plan_id is not None:
        rp = session.get(RatePlan, body.rate_plan_id)
        if not rp or rp.tenant_id != user.tenant_id:
            raise HTTPException(400, "Rate plan not found")
    else:
        # Auto-pick the customer's active rate plan if any
        crp = session.exec(
            select(CustomerRatePlan).where(
                CustomerRatePlan.tenant_id == user.tenant_id,
                CustomerRatePlan.customer_id == body.customer_id,
                CustomerRatePlan.is_active == True,  # noqa: E712
            )
        ).first()
        body.rate_plan_id = crp.rate_plan_id if crp else None

    number = next_number(session, user.tenant_id, "po", "PO", width=4)
    po = ProductionOrder(
        tenant_id=user.tenant_id,
        number=number,
        bom_id=body.bom_id,
        customer_id=body.customer_id,
        rate_plan_id=body.rate_plan_id,
        output_qty=money(D(body.output_qty)),
        state="draft",
        notes=body.notes,
    )
    session.add(po)
    session.flush()
    log_audit(
        session, user, "CREATE", "production_order", po.id,
        {"number": number, "bom_id": body.bom_id, "output_qty": str(body.output_qty)},
    )
    session.commit()
    session.refresh(po)
    return _serialise(po, session)


# ── State transitions ───────────────────────────────────────────────────────


def _require_state(po: ProductionOrder, expected: str) -> None:
    if po.state != expected:
        raise HTTPException(
            400, f"PO is in state '{po.state}'; transition requires '{expected}'"
        )


@router.post("/{po_id}/start")
def start_po(session: SessionDep, user: WriteUserDep, po_id: int):
    """Issue components from MAIN/GODOWN → WIP. Own-stock consumption posts
    a WIP/Raw-Material JE; customer-supplied components emit only a
    CUSTODIAL_ISSUE movement (their cost lives in memo accounts)."""
    po = _get_po(session, user.tenant_id, po_id)
    _require_state(po, "draft")

    bom = session.get(BomHeader, po.bom_id)
    lines = _bom_lines(session, bom.id)
    if not lines:
        raise HTTPException(400, "BoM has no lines")

    wip = _resolve_wip_location(session, user.tenant_id)
    main_own = _resolve_main_own(session, user.tenant_id)
    output_qty = D(po.output_qty)
    batches = output_qty / D(bom.output_qty)

    own_material_cost = ZERO

    for ln in lines:
        required = D(ln.qty_per_output) * batches
        if required <= 0:
            continue

        prod = session.get(Product, ln.component_product_id)

        if ln.source == "own_stock":
            # Consume from our inventory at WAvg cost. consume_stock handles
            # the qty + layer maths; we also need to redirect the JE since
            # the default treats this as a sale (Dr COGS) — instead we want
            # Dr WIP / Cr Raw Material.
            # Approach: relieve stock manually via record_movement at avg
            # cost, then post the JE ourselves.
            if prod.product_type != "stock":
                raise HTTPException(
                    400,
                    f"Component {prod.code or prod.id} is a service, cannot consume",
                )
            available = D(prod.stock_qty)
            if available < required:
                raise HTTPException(
                    400,
                    f"Insufficient stock for {prod.code or prod.id}: "
                    f"need {required}, have {available}",
                )
            unit_cost = D(prod.avg_cost)
            line_cost = money(required * unit_cost)
            own_material_cost += D(line_cost)

            # Deplete layers FIFO across own locations
            remaining = required
            consumed_from_loc = None
            consumed_lot = None
            layers = session.exec(
                select(InventoryLayer)
                .where(
                    InventoryLayer.tenant_id == user.tenant_id,
                    InventoryLayer.product_id == prod.id,
                    InventoryLayer.owner_customer_id.is_(None),
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
                if consumed_from_loc is None:
                    consumed_from_loc = layer.location_id or main_own.id
                    consumed_lot = layer.lot_no

            prod.stock_qty = D(prod.stock_qty) - required
            session.add(prod)

            record_movement(
                session,
                tenant_id=user.tenant_id, product_id=prod.id,
                direction="ISSUE", qty=required,
                from_location_id=consumed_from_loc or main_own.id,
                to_location_id=wip.id,
                lot_no=consumed_lot,
                unit_cost=unit_cost,
                source_doc_type="production_order", source_doc_id=po.id,
                posted_to_gl=True,
            )

        elif ln.source == "customer_supplied":
            # Pull from GODOWN custodial layers (owner = po.customer_id).
            # No GL effect — just movement + layer drain.
            layers = session.exec(
                select(InventoryLayer)
                .where(
                    InventoryLayer.tenant_id == user.tenant_id,
                    InventoryLayer.product_id == prod.id,
                    InventoryLayer.owner_customer_id == po.customer_id,
                    InventoryLayer.qty_remaining > 0,
                )
                .order_by(InventoryLayer.id.asc())
            ).all()
            available = sum((D(l.qty_remaining) for l in layers), start=ZERO)
            if available < required:
                raise HTTPException(
                    400,
                    f"Insufficient custodial stock for {prod.code or prod.id}: "
                    f"need {required}, have {available}",
                )
            remaining = required
            consumed_from_loc = None
            consumed_lot = None
            for layer in layers:
                if remaining <= 0:
                    break
                take = min(D(layer.qty_remaining), remaining)
                layer.qty_remaining = D(layer.qty_remaining) - take
                remaining -= take
                session.add(layer)
                if consumed_from_loc is None:
                    consumed_from_loc = layer.location_id
                    consumed_lot = layer.lot_no

            record_movement(
                session,
                tenant_id=user.tenant_id, product_id=prod.id,
                direction="CUSTODIAL_ISSUE", qty=required,
                from_location_id=consumed_from_loc,
                to_location_id=wip.id,
                lot_no=consumed_lot,
                owner_customer_id=po.customer_id,
                source_doc_type="production_order", source_doc_id=po.id,
                posted_to_gl=False,
            )

    # Post the WIP capitalisation JE (only if own materials consumed)
    if own_material_cost > 0:
        wip_acc = get_or_create_account(
            session, user.tenant_id, "1201", "Work-in-Progress", "Asset"
        )
        rm_acc = get_or_create_account(
            session, user.tenant_id, "1200", "Raw Material Inventory", "Asset"
        )
        post_transaction(
            session, user,
            date=datetime.utcnow().date().isoformat(),
            description=f"{po.number} — issue to WIP",
            entries=[
                EntryInput(account_id=wip_acc.id, debit=own_material_cost),
                EntryInput(account_id=rm_acc.id, credit=own_material_cost),
            ],
            audit_entity_type="production_order",
            audit_detail={"number": po.number, "stage": "start", "own_material_cost": str(own_material_cost)},
        )

    # Absorb labour + manufacturing overhead into WIP from the rate plan (#222)
    labour_cost = ZERO
    overhead_cost = ZERO
    if po.rate_plan_id:
        rp = session.get(RatePlan, po.rate_plan_id)
        if rp and rp.tenant_id == user.tenant_id:
            labour_cost = money(D(rp.labour_per_unit) * output_qty)
            overhead_cost = money(D(rp.overhead_per_unit) * output_qty)

    wip_acc = get_or_create_account(
        session, user.tenant_id, "1201", "Work-in-Progress", "Asset"
    )
    if labour_cost > 0:
        labour_acc = get_default_account(
            session, user.tenant_id,
            "default_mfg_labour_account", "5100", "Direct Labour", "Expense",
        )
        post_transaction(
            session, user,
            date=datetime.utcnow().date().isoformat(),
            description=f"{po.number} — absorb labour",
            entries=[
                EntryInput(account_id=wip_acc.id, debit=labour_cost),
                EntryInput(account_id=labour_acc.id, credit=labour_cost),
            ],
            audit_entity_type="production_order",
            audit_detail={"number": po.number, "stage": "start", "labour_cost": str(labour_cost)},
        )
    if overhead_cost > 0:
        oh_acc = get_default_account(
            session, user.tenant_id,
            "default_mfg_overhead_account", "5200", "Manufacturing Overhead", "Expense",
        )
        post_transaction(
            session, user,
            date=datetime.utcnow().date().isoformat(),
            description=f"{po.number} — absorb overhead",
            entries=[
                EntryInput(account_id=wip_acc.id, debit=overhead_cost),
                EntryInput(account_id=oh_acc.id, credit=overhead_cost),
            ],
            audit_entity_type="production_order",
            audit_detail={"number": po.number, "stage": "start", "overhead_cost": str(overhead_cost)},
        )

    po.state = "started"
    po.started_at = datetime.utcnow()
    po.own_material_cost = money(own_material_cost)
    po.labour_cost = money(labour_cost)
    po.overhead_cost = money(overhead_cost)
    session.add(po)
    log_audit(session, user, "START", "production_order", po.id, {
        "number": po.number,
        "own_material_cost": str(own_material_cost),
        "labour_cost": str(labour_cost),
        "overhead_cost": str(overhead_cost),
    })
    session.commit()
    session.refresh(po)
    return _serialise(po, session)


@router.post("/{po_id}/complete")
def complete_po(session: SessionDep, user: WriteUserDep, po_id: int):
    """Capitalise output(s): WIP → Finished Goods.

    Multi-output BoMs (#223): each BomOutput is received into MAIN at its
    allocated unit cost; one WIP→FG JE posts the full absorbed total_cost.
    """
    po = _get_po(session, user.tenant_id, po_id)
    _require_state(po, "started")

    bom = session.get(BomHeader, po.bom_id)
    main_own = _resolve_main_own(session, user.tenant_id)
    wip = _resolve_wip_location(session, user.tenant_id)
    output_qty = D(po.output_qty)
    batches = output_qty / D(bom.output_qty) if D(bom.output_qty) > 0 else ZERO
    total_cost = D(po.own_material_cost) + D(po.labour_cost) + D(po.overhead_cost)

    bom_outs = _bom_outputs(session, bom)
    allocated = _allocate_output_costs(session, bom, bom_outs, batches, total_cost)

    primary_unit = ZERO
    for product_id, role, qty, unit_cost, _cost in allocated:
        record_purchase(
            session,
            tenant_id=user.tenant_id,
            product_id=product_id,
            qty=qty,
            unit_cost=unit_cost,
            source_doc=po.number,
            location_id=main_own.id,
            lot_no=po.number,
        )
        _tag_completion_movement(session, user, po, product_id, wip.id)
        session.add(ProductionOrderOutput(
            tenant_id=user.tenant_id,
            po_id=po.id,
            product_id=product_id,
            role=role,
            qty=qty,
            unit_cost=unit_cost,
            delivered_qty=ZERO,
        ))
        if role == "primary":
            primary_unit = unit_cost

    if total_cost > 0:
        fg_acc = get_or_create_account(
            session, user.tenant_id, "1202", "Finished Goods Inventory", "Asset"
        )
        wip_acc = get_or_create_account(
            session, user.tenant_id, "1201", "Work-in-Progress", "Asset"
        )
        post_transaction(
            session, user,
            date=datetime.utcnow().date().isoformat(),
            description=f"{po.number} — capitalise FG",
            entries=[
                EntryInput(account_id=fg_acc.id, debit=total_cost),
                EntryInput(account_id=wip_acc.id, credit=total_cost),
            ],
            audit_entity_type="production_order",
            audit_detail={"number": po.number, "stage": "complete", "total_cost": str(total_cost)},
        )

    po.state = "completed"
    po.completed_at = datetime.utcnow()
    po.output_unit_cost = primary_unit
    session.add(po)
    log_audit(session, user, "COMPLETE", "production_order", po.id, {
        "number": po.number,
        "outputs": len(allocated),
    })
    session.commit()
    session.refresh(po)
    return _serialise(po, session)


class DeliverBody(BaseModel):
    qty: Optional[Decimal] = None


@router.post("/{po_id}/deliver")
def deliver_po(
    session: SessionDep,
    user: WriteUserDep,
    po_id: int,
    body: Optional[DeliverBody] = None,
):
    """Ship finished goods to customer (partial deliveries supported — #222).

    Body `{qty}` defaults to remaining qty. State stays `completed` until
    cumulative delivered_qty reaches output_qty, then flips to `delivered`.
    Custodial memo release runs only on the final delivery.
    """
    po = _get_po(session, user.tenant_id, po_id)
    if po.state not in ("completed",):
        raise HTTPException(
            400, f"PO is in state '{po.state}'; delivery requires 'completed'"
        )

    bom = session.get(BomHeader, po.bom_id)
    output_qty = D(po.output_qty)
    already = D(po.delivered_qty)
    remaining = output_qty - already
    if remaining <= 0:
        raise HTTPException(400, "Production order is already fully delivered")

    qty = D(body.qty) if body and body.qty is not None else remaining
    if qty <= 0:
        raise HTTPException(400, "qty must be > 0")
    if qty > remaining:
        raise HTTPException(
            400, f"qty {qty} exceeds remaining {remaining} (output {output_qty}, delivered {already})"
        )

    # Relieve FG at cost via consume_stock (handles layers + COGS calc).
    cogs = consume_stock(
        session,
        tenant_id=user.tenant_id,
        product_id=bom.output_product_id,
        qty=qty,
    )
    last_mv = session.exec(
        select(StockMovement)
        .where(
            StockMovement.tenant_id == user.tenant_id,
            StockMovement.product_id == bom.output_product_id,
            StockMovement.direction == "SHIPMENT",
        )
        .order_by(StockMovement.id.desc())
    ).first()
    if last_mv:
        last_mv.direction = "DELIVERY"
        last_mv.source_doc_type = "production_order"
        last_mv.source_doc_id = po.id
        last_mv.notes = f"{po.number} deliver {qty}"
        session.add(last_mv)

    if cogs > 0:
        cogs_acc = get_or_create_account(
            session, user.tenant_id, "5010", "Cost of Goods Sold", "Expense"
        )
        fg_acc = get_or_create_account(
            session, user.tenant_id, "1202", "Finished Goods Inventory", "Asset"
        )
        post_transaction(
            session, user,
            date=datetime.utcnow().date().isoformat(),
            description=f"{po.number} — deliver / COGS ({qty})",
            entries=[
                EntryInput(account_id=cogs_acc.id, debit=cogs),
                EntryInput(account_id=fg_acc.id, credit=cogs),
            ],
            audit_entity_type="production_order",
            audit_detail={
                "number": po.number, "stage": "deliver",
                "qty": str(qty), "cogs": str(cogs),
            },
        )

    new_delivered = already + qty
    fully = new_delivered >= output_qty

    # Memo release only when the order is fully shipped (avoids double-release)
    if fully:
        memo_release = _release_customer_memo(session, user, po.customer_id)
        if memo_release > 0:
            memo_asset = get_or_create_account(
                session, user.tenant_id, "1210", "Customer Goods on Hand", "Asset"
            )
            memo_liab = get_or_create_account(
                session, user.tenant_id, "2150", "Customer Goods Liability", "Liability"
            )
            for acc in (memo_asset, memo_liab):
                if not acc.is_memo:
                    acc.is_memo = True
                    session.add(acc)
            post_transaction(
                session, user,
                date=datetime.utcnow().date().isoformat(),
                description=f"{po.number} — release customer custody",
                entries=[
                    EntryInput(account_id=memo_liab.id, debit=memo_release),
                    EntryInput(account_id=memo_asset.id, credit=memo_release),
                ],
                audit_entity_type="production_order",
                audit_detail={"number": po.number, "stage": "deliver", "memo_release": str(memo_release)},
            )

    po.delivered_qty = money(new_delivered)
    primary_out = session.exec(
        select(ProductionOrderOutput).where(
            ProductionOrderOutput.po_id == po.id,
            ProductionOrderOutput.role == "primary",
        )
    ).first()
    if primary_out:
        primary_out.delivered_qty = money(new_delivered)
        session.add(primary_out)
    if fully:
        po.state = "delivered"
        po.delivered_at = datetime.utcnow()
    session.add(po)
    log_audit(
        session, user, "DELIVER", "production_order", po.id,
        {"number": po.number, "qty": str(qty), "delivered_qty": str(new_delivered), "fully": fully},
    )
    session.commit()
    session.refresh(po)
    return _serialise(po, session)


def _release_customer_memo(session, user, customer_id: int) -> Decimal:
    """Sum declared_value of GRNs where all custodial layers are drained."""
    grns = session.exec(
        select(GoodsReceiptNote).where(
            GoodsReceiptNote.tenant_id == user.tenant_id,
            GoodsReceiptNote.customer_id == customer_id,
            GoodsReceiptNote.declared_value > 0,
        )
    ).all()
    released = ZERO
    for g in grns:
        # Have all layers tied to this GRN been drained?
        layers = session.exec(
            select(InventoryLayer).where(
                InventoryLayer.tenant_id == user.tenant_id,
                InventoryLayer.owner_customer_id == customer_id,
                InventoryLayer.source_doc == g.number,
            )
        ).all()
        if layers and all(D(l.qty_remaining) == 0 for l in layers):
            released += D(g.declared_value)
            # Zero out so we don't release the same GRN twice
            g.declared_value = ZERO
            session.add(g)
    return released


@router.post("/{po_id}/bill")
def bill_po(session: SessionDep, user: WriteUserDep, po_id: int):
    """Create an Invoice via the rate plan attached to this PO."""
    po = _get_po(session, user.tenant_id, po_id)
    _require_state(po, "delivered")
    if po.rate_plan_id is None:
        raise HTTPException(
            400,
            "PO has no rate plan; assign one to the customer or set rate_plan_id "
            "on the PO before billing.",
        )

    rp = session.get(RatePlan, po.rate_plan_id)
    if not rp or rp.tenant_id != user.tenant_id:
        raise HTTPException(400, "Rate plan not found")

    qty = D(po.output_qty)
    base = qty * D(rp.per_unit_rate)
    materials = D(po.own_material_cost) if rp.includes_materials_at_cost else ZERO
    subtotal_pre = base + materials
    overhead = subtotal_pre * D(rp.overhead_pct) / Decimal("100")
    subtotal = subtotal_pre + overhead
    margin = subtotal * D(rp.margin_pct) / Decimal("100")
    total_net = subtotal + margin   # excl GST; matches Invoice.subtotal contract

    # Build Invoice + InvoiceLine via direct construction (mirrors invoices.py)
    cust = session.get(Customer, po.customer_id)
    bom = session.get(BomHeader, po.bom_id)
    output_prod = session.get(Product, bom.output_product_id)

    invoice_number = next_number(session, user.tenant_id, "invoice", "INV", width=4)
    today = datetime.utcnow().date().isoformat()
    invoice = Invoice(
        tenant_id=user.tenant_id,
        number=invoice_number,
        customer_id=cust.id,
        customer_name=cust.name,
        issue_date=today,
        due_date=today,
        description=f"Value-addition services for {po.number}",
        subtotal=money(total_net),
        gst_rate=ZERO,
        gst_amount=ZERO,
        total=money(total_net),
        status="posted",
    )
    session.add(invoice)
    session.flush()

    # Line 1: value-add charge
    session.add(InvoiceLine(
        invoice_id=invoice.id,
        product_id=output_prod.id,
        description=f"{rp.name} ({qty} {output_prod.unit} × {rp.per_unit_rate})",
        qty=money(qty),
        unit=output_prod.unit,
        rate=money(D(rp.per_unit_rate)),
        amount=money(base),
    ))
    if materials > 0:
        session.add(InvoiceLine(
            invoice_id=invoice.id,
            product_id=None,
            description="Materials passthrough (at cost)",
            qty=money(Decimal("1")),
            rate=money(materials),
            amount=money(materials),
        ))
    if overhead > 0:
        session.add(InvoiceLine(
            invoice_id=invoice.id,
            product_id=None,
            description=f"Overhead ({rp.overhead_pct}%)",
            qty=money(Decimal("1")),
            rate=money(overhead),
            amount=money(overhead),
        ))
    if margin > 0:
        session.add(InvoiceLine(
            invoice_id=invoice.id,
            product_id=None,
            description=f"Margin ({rp.margin_pct}%)",
            qty=money(Decimal("1")),
            rate=money(margin),
            amount=money(margin),
        ))

    # GL: Dr AR / Cr Service Revenue (Value-Add)
    ar_acc = get_or_create_account(
        session, user.tenant_id, "1100", "Accounts Receivable", "Asset"
    )
    rev_acc = get_or_create_account(
        session, user.tenant_id, "4010", "Service Revenue (Value-Add)", "Revenue"
    )
    txn = post_transaction(
        session, user,
        date=today,
        description=f"Invoice {invoice_number} — {po.number}",
        entries=[
            EntryInput(account_id=ar_acc.id, debit=money(total_net)),
            EntryInput(account_id=rev_acc.id, credit=money(total_net)),
        ],
        audit_entity_type="invoice",
        audit_detail={"invoice_number": invoice_number, "po_number": po.number},
    )
    invoice.transaction_id = txn.id
    session.add(invoice)

    po.state = "billed"
    po.billed_at = datetime.utcnow()
    po.invoice_id = invoice.id
    session.add(po)
    log_audit(
        session, user, "BILL", "production_order", po.id,
        {"number": po.number, "invoice_number": invoice_number, "total": str(total_net)},
    )
    session.commit()
    session.refresh(po)
    session.refresh(invoice)
    return {"production_order": _serialise(po, session), "invoice": invoice.model_dump()}


@router.post("/{po_id}/cancel")
def cancel_po(session: SessionDep, user: WriteUserDep, po_id: int):
    """Soft-cancel a PO. Only legal in draft state (other states have
    materially committed inventory + JEs — use POST /{id}/reverse)."""
    po = _get_po(session, user.tenant_id, po_id)
    if po.state not in ("draft",):
        raise HTTPException(
            400,
            f"Cancel only allowed from 'draft' (current: '{po.state}'). "
            "Use POST /api/production-orders/{id}/reverse to undo a started/completed/delivered PO.",
        )
    po.state = "cancelled"
    po.cancelled_at = datetime.utcnow()
    session.add(po)
    log_audit(session, user, "CANCEL", "production_order", po.id, {"number": po.number})
    session.commit()
    session.refresh(po)
    return _serialise(po, session)


@router.post("/{po_id}/reverse")
def reverse_po(session: SessionDep, user: WriteUserDep, po_id: int):
    """Guided reverse of a started / completed / delivered production order (#221).

    Unwinds stock + stage JEs newest→oldest, then marks the PO cancelled.
    Billed POs must void their invoice first via the journal reverse flow.
    """
    po = _get_po(session, user.tenant_id, po_id)
    if po.state == "draft":
        raise HTTPException(400, "Draft POs have no postings — use Cancel instead")
    if po.state == "cancelled":
        raise HTTPException(400, "Production order is already cancelled")
    if po.state == "billed":
        raise HTTPException(
            400,
            "Billed POs cannot be reversed here. Void the linked invoice first "
            f"(invoice_id={po.invoice_id}), then reverse the PO.",
        )
    if po.state not in ("started", "completed", "delivered"):
        raise HTTPException(400, f"Cannot reverse PO in state '{po.state}'")

    scrap_count = session.exec(
        select(func.count(ProductionScrap.id)).where(ProductionScrap.po_id == po.id)
    ).one()
    if scrap_count:
        raise HTTPException(
            400,
            f"Cannot reverse PO with {scrap_count} scrap record(s). "
            "Void scrap entries first (not yet supported) or keep the order.",
        )

    bom = session.get(BomHeader, po.bom_id)
    if not bom:
        raise HTTPException(400, "BoM not found")

    from_state = po.state
    reversed_jvs: list[str] = []

    # Unwind deliveries first (fully delivered, or partial while still completed)
    if po.state == "delivered" or (po.state == "completed" and D(po.delivered_qty) > 0):
        reversed_jvs.extend(_unwind_deliver(session, user, po, bom))
    if po.state == "completed":
        reversed_jvs.extend(_unwind_complete(session, user, po, bom))
    if po.state == "started":
        reversed_jvs.extend(_unwind_start(session, user, po))

    log_audit(
        session, user, "REVERSE", "production_order", po.id,
        {
            "number": po.number,
            "from_state": from_state,
            "reversed_jvs": reversed_jvs,
        },
    )
    session.commit()
    session.refresh(po)
    return {
        **_serialise(po, session),
        "from_state": from_state,
        "reversed_jvs": reversed_jvs,
    }


class ScrapBody(BaseModel):
    reason_id: int
    product_id: int
    qty: Decimal
    notes: Optional[str] = None
    post_gl: bool = True


@router.post("/{po_id}/scrap")
def record_scrap(session: SessionDep, user: WriteUserDep, po_id: int, body: ScrapBody):
    """Record scrap/damage against a started or completed PO (#224).

    Relieves own stock via consume_stock. When post_gl and cost > 0, posts
    Dr Scrap Expense / Cr Inventory.
    """
    po = _get_po(session, user.tenant_id, po_id)
    if po.state not in ("started", "completed"):
        raise HTTPException(
            400,
            f"Scrap only allowed while PO is started or completed (current: '{po.state}')",
        )
    qty = D(body.qty)
    if qty <= 0:
        raise HTTPException(400, "qty must be > 0")

    reason = session.get(ScrapReason, body.reason_id)
    if not reason or reason.tenant_id != user.tenant_id or not reason.is_active:
        raise HTTPException(400, "reason_id not found or inactive")

    prod = session.get(Product, body.product_id)
    if not prod or prod.tenant_id != user.tenant_id:
        raise HTTPException(400, "product_id not found for tenant")
    if prod.product_type != "stock":
        raise HTTPException(400, "Only stock products can be scrapped")

    try:
        total_cost = consume_stock(
            session,
            tenant_id=user.tenant_id,
            product_id=prod.id,
            qty=qty,
            block_negative=True,
            source_doc_id=po.id,
            source_doc_type="production_scrap",
        )
    except InventoryError as exc:
        raise HTTPException(400, str(exc)) from exc

    unit_cost = money(total_cost / qty) if qty > 0 else ZERO
    gl_posted = False
    if body.post_gl and total_cost > 0:
        scrap_acc = get_default_account(
            session, user.tenant_id,
            "default_scrap_expense_account", "5901", "Scrap Disposal Expense", "Expense",
        )
        bom = session.get(BomHeader, po.bom_id)
        is_fg = (
            bom is not None and bom.output_product_id == prod.id
        ) or session.exec(
            select(ProductionOrderOutput).where(
                ProductionOrderOutput.po_id == po.id,
                ProductionOrderOutput.product_id == prod.id,
            )
        ).first() is not None
        inv_acc = get_or_create_account(
            session, user.tenant_id,
            "1202" if is_fg else "1200",
            "Finished Goods Inventory" if is_fg else "Raw Material Inventory",
            "Asset",
        )
        post_transaction(
            session, user,
            date=datetime.utcnow().date().isoformat(),
            description=f"{po.number} — scrap {reason.code} ({prod.code or prod.id})",
            entries=[
                EntryInput(account_id=scrap_acc.id, debit=total_cost),
                EntryInput(account_id=inv_acc.id, credit=total_cost),
            ],
            audit_entity_type="production_order",
            audit_detail={
                "number": po.number,
                "stage": "scrap",
                "reason": reason.code,
                "product_id": prod.id,
                "qty": str(qty),
                "cost": str(total_cost),
            },
        )
        gl_posted = True

    row = ProductionScrap(
        tenant_id=user.tenant_id,
        po_id=po.id,
        reason_id=reason.id,
        product_id=prod.id,
        qty=qty,
        unit_cost=unit_cost,
        total_cost=money(total_cost),
        gl_posted=gl_posted,
        notes=body.notes,
        created_by_id=user.id,
    )
    session.add(row)
    log_audit(session, user, "SCRAP", "production_order", po.id, {
        "number": po.number,
        "reason": reason.code,
        "product_id": prod.id,
        "qty": str(qty),
        "total_cost": str(total_cost),
        "gl_posted": gl_posted,
    })
    session.commit()
    session.refresh(po)
    return _serialise(po, session)

