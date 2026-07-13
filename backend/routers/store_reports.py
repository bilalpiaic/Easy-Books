"""Store-domain reports (#137 Phase 2b): gate-outward register + dispatch
reconciliation. Kept separate from purchase_reports.py — Gate Outward spans
Sales/Purchases/Inventory, not purely the purchase chain."""
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import func, literal, or_, union_all
from sqlmodel import select

from models import (Account, AnalyticAccount, DebitNote, GateOutward,
                     GateOutwardLine, Invoice, Product, StockLocation,
                     StockMovement, StoreIssue, StoreIssueLine)
from routers.common import SessionDep, WriteUserDep
from services.money import D
from services.permissions import apply_own_filter, perm_dep

router = APIRouter(prefix="/api/store-reports", tags=["store-reports"])


@router.get("/gate-outward-register", dependencies=[perm_dep("store.gate_outward")])
def gate_outward_register(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    q: Optional[str] = None, source_doc_type: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    query = select(GateOutward).where(GateOutward.tenant_id == user.tenant_id)
    if start:
        query = query.where(GateOutward.gate_date >= start)
    if end:
        query = query.where(GateOutward.gate_date <= end)
    if source_doc_type:
        query = query.where(GateOutward.source_doc_type == source_doc_type)
    if q:
        like = f"%{q}%"
        query = query.where(or_(
            GateOutward.vehicle_no.ilike(like), GateOutward.challan_no.ilike(like),
        ))
    query = apply_own_filter(query, GateOutward, user, session)
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    gos = session.exec(
        query.order_by(GateOutward.id.desc()).offset(skip).limit(limit)
    ).all()

    out = []
    for go in gos:
        lines = session.exec(
            select(GateOutwardLine).where(GateOutwardLine.gate_outward_id == go.id)
        ).all()
        row = go.model_dump()
        if go.source_doc_type == "invoice" and go.source_doc_id:
            inv = session.get(Invoice, go.source_doc_id)
            row["reference"] = inv.number if inv else None
        elif go.source_doc_type == "debit_note" and go.source_doc_id:
            dn = session.get(DebitNote, go.source_doc_id)
            row["reference"] = dn.number if dn else None
        else:
            row["reference"] = "Scrap"
        row["item_count"] = len(lines)
        row["total_qty"] = sum(D(l.qty) for l in lines)
        out.append(row)
    return {"total": total, "items": out}


@router.get("/dispatch-reconciliation", dependencies=[perm_dep("store.gate_outward")])
def dispatch_reconciliation(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None, q: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    """Invoices and debit notes are one SQL UNION so search, ordering
    (newest first) and pagination all happen database-side across both."""
    inv_sel = select(
        Invoice.id.label("doc_id"),
        literal("invoice").label("doc_type"),
        Invoice.number.label("doc_number"),
        Invoice.customer_name.label("party"),
        Invoice.issue_date.label("doc_date"),
    ).where(Invoice.tenant_id == user.tenant_id, Invoice.status != "void")
    dn_sel = select(
        DebitNote.id.label("doc_id"),
        literal("debit_note").label("doc_type"),
        DebitNote.number.label("doc_number"),
        DebitNote.vendor_name.label("party"),
        DebitNote.issue_date.label("doc_date"),
    ).where(DebitNote.tenant_id == user.tenant_id, DebitNote.status != "draft")
    if start:
        inv_sel = inv_sel.where(Invoice.issue_date >= start)
        dn_sel = dn_sel.where(DebitNote.issue_date >= start)
    if end:
        inv_sel = inv_sel.where(Invoice.issue_date <= end)
        dn_sel = dn_sel.where(DebitNote.issue_date <= end)
    if q:
        like = f"%{q}%"
        inv_sel = inv_sel.where(or_(
            Invoice.number.ilike(like), Invoice.customer_name.ilike(like),
        ))
        dn_sel = dn_sel.where(or_(
            DebitNote.number.ilike(like), DebitNote.vendor_name.ilike(like),
        ))
    union = union_all(inv_sel, dn_sel).subquery()

    total = session.exec(select(func.count()).select_from(union)).one()
    docs = session.execute(
        select(union)
        .order_by(union.c.doc_date.desc(), union.c.doc_number.desc())
        .offset(skip).limit(limit)
    ).mappings().all()

    # Resolve gate exits for just this page's documents.
    exits_by_doc: dict[tuple[str, int], str] = {}
    doc_ids = [d["doc_id"] for d in docs]
    if doc_ids:
        exits_query = select(GateOutward).where(
            GateOutward.tenant_id == user.tenant_id,
            GateOutward.status != "cancelled",
            GateOutward.source_doc_type.in_(["invoice", "debit_note"]),
            GateOutward.source_doc_id.in_(doc_ids),
        )
        exits_query = apply_own_filter(exits_query, GateOutward, user, session)
        for go in session.exec(exits_query).all():
            exits_by_doc[(go.source_doc_type, go.source_doc_id)] = go.number

    items = []
    for d in docs:
        go_number = exits_by_doc.get((d["doc_type"], d["doc_id"]))
        items.append({
            "doc_type": d["doc_type"], "doc_number": d["doc_number"],
            "party": d["party"], "doc_date": d["doc_date"],
            "has_gate_exit": go_number is not None, "go_number": go_number,
        })
    return {"total": total, "items": items}


@router.get("/issue-register", dependencies=[perm_dep("store.issue")])
def issue_register(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    analytic_account_id: Optional[int] = None, q: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    query = select(StoreIssue).where(StoreIssue.tenant_id == user.tenant_id)
    if start:
        query = query.where(StoreIssue.issue_date >= start)
    if end:
        query = query.where(StoreIssue.issue_date <= end)
    if analytic_account_id:
        query = query.where(StoreIssue.analytic_account_id == analytic_account_id)
    if q:
        like = f"%{q}%"
        query = query.where(or_(
            StoreIssue.number.ilike(like), StoreIssue.notes.ilike(like),
        ))
    query = apply_own_filter(query, StoreIssue, user, session)
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    rows = session.exec(
        query.order_by(StoreIssue.id.desc()).offset(skip).limit(limit)
    ).all()

    out = []
    for si in rows:
        lines = session.exec(
            select(StoreIssueLine).where(StoreIssueLine.store_issue_id == si.id)
        ).all()
        row = si.model_dump()
        loc = session.get(StockLocation, si.from_location_id)
        row["location_name"] = loc.name if loc else None
        acct = session.get(Account, si.debit_account_id)
        row["debit_account_name"] = acct.name if acct else None
        if si.analytic_account_id:
            aa = session.get(AnalyticAccount, si.analytic_account_id)
            row["analytic_account_name"] = aa.name if aa else None
        row["item_count"] = len(lines)
        row["total_cost"] = sum(D(l.qty) * D(l.unit_cost) for l in lines)
        out.append(row)
    return {"total": total, "items": out}


# Sign map: how each StockMovement.direction affects Product.stock_qty.
# Derived by reading each writer (not assumed) — a "true" tie-out has to sum
# every movement type that actually touches stock_qty, signed correctly:
#
#   +1  RECEIPT      services/inventory.py:135 record_purchase increments
#                     prod.stock_qty, then writes the RECEIPT row (:157,
#                     source_doc_type always "bill").
#   +1  COMPLETION    routers/production_orders.py:381 calls record_purchase
#                     (same +qty increment as above) for finished-goods
#                     capitalisation, then :406 reclassifies that same row's
#                     direction RECEIPT -> COMPLETION after the fact.
#   -1  SHIPMENT      services/inventory.py:247 consume_stock decrements
#                     prod.stock_qty, then writes the SHIPMENT row (:272).
#                     source_doc_type varies (invoice/store_issue/
#                     gate_outward) but the decrement is unconditional.
#   -1  DELIVERY      routers/production_orders.py:453 calls consume_stock
#                     (same -qty decrement as above) to ship finished goods,
#                     then :471 reclassifies that same row's direction
#                     SHIPMENT -> DELIVERY after the fact.
#   -1  ISSUE         routers/production_orders.py:274
#                     `prod.stock_qty = D(prod.stock_qty) - required` — own
#                     -stock component consumption issued to WIP.
#
#   ADJUSTMENT is not a single fixed sign — it has three writers with
#   different (or absent) sign encoding:
#     -1  source_doc_type == "debit_note"  services/inventory.py:434
#         return_to_vendor always decrements prod.stock_qty (purchase
#         return); deterministic.
#     -1  source_doc_type == "bill_void"   services/inventory.py
#         reverse_purchase (bill void/edit) always decrements
#         prod.stock_qty by the layer's unsold remainder; deterministic,
#         same shape as the debit-note writer.
#     ??  source_doc_type == "adjustment"  routers/products.py:290
#         adjust_stock (manual physical-count correction) stores
#         qty=abs(variance) with NO sign persisted on the row — it
#         overwrites prod.stock_qty to the counted value directly rather
#         than applying a signed delta. The sign cannot be reconstructed
#         from the movement log, so these rows are deliberately EXCLUDED
#         from expected_closing: any residual variance left after a manual
#         count override is the correct signal (an operator changed the
#         number outside the normal receive/issue flow) rather than
#         something to silently net away.
#
#   EXCLUDED entirely — CUSTODIAL_RECEIPT (routers/grn.py:174-183) and
#   CUSTODIAL_ISSUE (routers/production_orders.py:289-333) never assign to
#   prod.stock_qty at all; they only move InventoryLayer.qty_remaining for
#   customer-owned goods held in the godown. CUSTODIAL_COMPLETION is
#   declared in the models.py CHECK constraint but no writer in the
#   codebase emits it (dead direction) — excluded, nothing to sign.
_STOCK_QTY_SIGN = {
    "RECEIPT": 1,
    "COMPLETION": 1,
    "SHIPMENT": -1,
    "DELIVERY": -1,
    "ISSUE": -1,
}


def _movement_sign(direction: str, source_doc_type: Optional[str]) -> Optional[int]:
    """Effect of one StockMovement row on Product.stock_qty: +1/-1, or None
    if it doesn't affect stock_qty (custodial) or its sign can't be
    recovered from the row (manual physical-count adjustment) — see
    _STOCK_QTY_SIGN comment above."""
    if direction == "ADJUSTMENT":
        return -1 if source_doc_type in ("debit_note", "bill_void") else None
    return _STOCK_QTY_SIGN.get(direction)


@router.get("/stock-tie-out", dependencies=[perm_dep("store.issue")])
def stock_tie_out(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    product_id: Optional[int] = None,
):
    """Product-level, tenant-wide (not per-location — consume_stock has no
    location_id, so per-location tie-out would silently misreport; see
    design decision #5).

    `received_qty`/`issued_qty` stay scoped to bill receipts / store-issue
    consumption — they're the report's featured, human-meaningful columns.
    `expected_closing` (and therefore `variance`) is computed from ALL
    movement types that affect Product.stock_qty (see _STOCK_QTY_SIGN), so a
    product with sales, production activity, or purchase returns still ties
    out correctly instead of showing false variance."""
    prod_query = select(Product).where(Product.tenant_id == user.tenant_id, Product.product_type == "stock")
    if product_id:
        prod_query = prod_query.where(Product.id == product_id)
    products = session.exec(prod_query).all()

    out = []
    for prod in products:
        mv_query = select(StockMovement).where(
            StockMovement.tenant_id == user.tenant_id, StockMovement.product_id == prod.id,
        )
        movements = session.exec(mv_query).all()

        received_qty = D("0")
        issued_qty = D("0")
        opening_qty = D("0")      # signed, all-types, pre-window sum
        window_delta = D("0")     # signed, all-types, in-window sum
        for mv in movements:
            # StockMovement's timestamp field is `occurred_at`, NOT
            # `created_at` (models.py:646) — verified before writing this.
            mv_date = mv.occurred_at.strftime("%Y-%m-%d")
            in_window = (not start or mv_date >= start) and (not end or mv_date <= end)

            # Display-only columns — bill receipts / store-issue consumption.
            if in_window:
                if mv.direction == "RECEIPT" and mv.source_doc_type == "bill":
                    received_qty += D(mv.qty)
                elif mv.direction == "SHIPMENT" and mv.source_doc_type == "store_issue":
                    issued_qty += D(mv.qty)

            sign = _movement_sign(mv.direction, mv.source_doc_type)
            if sign is None:
                continue
            if in_window:
                window_delta += sign * D(mv.qty)
            elif start and mv_date < start:
                opening_qty += sign * D(mv.qty)

        # actual_closing is live stock (today); comparing it against a
        # window truncated at a past `end` would report window-truncation
        # as fake variance — so the reconciliation columns are only
        # returned for the as-of-now view (end unset).
        if end:
            expected_closing = None
            actual_closing = None
            variance = None
        else:
            expected_closing = opening_qty + window_delta
            actual_closing = D(prod.stock_qty)
            variance = actual_closing - expected_closing
        out.append({
            "product_id": prod.id, "product_name": prod.name,
            "opening_qty": opening_qty, "received_qty": received_qty,
            "issued_qty": issued_qty, "expected_closing": expected_closing,
            "actual_closing": actual_closing,
            "variance": variance,
        })
    return out
