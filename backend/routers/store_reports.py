"""Store-domain reports (#137 Phase 2b): gate-outward register + dispatch
reconciliation. Kept separate from purchase_reports.py — Gate Outward spans
Sales/Purchases/Inventory, not purely the purchase chain."""
from typing import Optional

from fastapi import APIRouter
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
):
    query = select(GateOutward).where(GateOutward.tenant_id == user.tenant_id)
    if start:
        query = query.where(GateOutward.gate_date >= start)
    if end:
        query = query.where(GateOutward.gate_date <= end)
    if source_doc_type:
        query = query.where(GateOutward.source_doc_type == source_doc_type)
    query = apply_own_filter(query, GateOutward, user, session)
    gos = session.exec(query.order_by(GateOutward.id.desc())).all()

    out = []
    for go in gos:
        if q:
            needle = q.lower()
            hay = f"{go.vehicle_no or ''} {go.challan_no or ''}".lower()
            if needle not in hay:
                continue
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
    return out


@router.get("/dispatch-reconciliation", dependencies=[perm_dep("store.gate_outward")])
def dispatch_reconciliation(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    exits_by_doc: dict[tuple[str, int], str] = {}
    exits_query = select(GateOutward).where(
        GateOutward.tenant_id == user.tenant_id,
        GateOutward.status != "cancelled",
        GateOutward.source_doc_type.in_(["invoice", "debit_note"]),
    )
    exits_query = apply_own_filter(exits_query, GateOutward, user, session)
    for go in session.exec(exits_query).all():
        exits_by_doc[(go.source_doc_type, go.source_doc_id)] = go.number

    out = []

    inv_query = select(Invoice).where(
        Invoice.tenant_id == user.tenant_id, Invoice.status != "void"
    )
    if start:
        inv_query = inv_query.where(Invoice.issue_date >= start)
    if end:
        inv_query = inv_query.where(Invoice.issue_date <= end)
    for inv in session.exec(inv_query).all():
        go_number = exits_by_doc.get(("invoice", inv.id))
        out.append({
            "doc_type": "invoice", "doc_number": inv.number,
            "party": inv.customer_name, "doc_date": inv.issue_date,
            "has_gate_exit": go_number is not None, "go_number": go_number,
        })

    dn_query = select(DebitNote).where(
        DebitNote.tenant_id == user.tenant_id, DebitNote.status != "draft"
    )
    if start:
        dn_query = dn_query.where(DebitNote.issue_date >= start)
    if end:
        dn_query = dn_query.where(DebitNote.issue_date <= end)
    for dn in session.exec(dn_query).all():
        go_number = exits_by_doc.get(("debit_note", dn.id))
        out.append({
            "doc_type": "debit_note", "doc_number": dn.number,
            "party": dn.vendor_name, "doc_date": dn.issue_date,
            "has_gate_exit": go_number is not None, "go_number": go_number,
        })

    return out


@router.get("/issue-register", dependencies=[perm_dep("store.issue")])
def issue_register(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    analytic_account_id: Optional[int] = None, q: Optional[str] = None,
):
    query = select(StoreIssue).where(StoreIssue.tenant_id == user.tenant_id)
    if start:
        query = query.where(StoreIssue.issue_date >= start)
    if end:
        query = query.where(StoreIssue.issue_date <= end)
    if analytic_account_id:
        query = query.where(StoreIssue.analytic_account_id == analytic_account_id)
    query = apply_own_filter(query, StoreIssue, user, session)
    rows = session.exec(query.order_by(StoreIssue.id.desc())).all()

    out = []
    for si in rows:
        if q:
            needle = q.lower()
            hay = f"{si.number} {si.notes or ''}".lower()
            if needle not in hay:
                continue
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
    return out


@router.get("/stock-tie-out", dependencies=[perm_dep("store.issue")])
def stock_tie_out(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    product_id: Optional[int] = None,
):
    """Product-level, tenant-wide (not per-location — consume_stock has no
    location_id, so per-location tie-out would silently misreport; see
    design decision #5)."""
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
        opening_qty = D("0")
        for mv in movements:
            # StockMovement's timestamp field is `occurred_at`, NOT
            # `created_at` (models.py:646) — verified before writing this.
            mv_date = mv.occurred_at.strftime("%Y-%m-%d")
            in_window = (not start or mv_date >= start) and (not end or mv_date <= end)
            if mv.direction == "RECEIPT" and mv.source_doc_type == "bill":
                if in_window:
                    received_qty += D(mv.qty)
                elif start and mv_date < start:
                    opening_qty += D(mv.qty)
            elif mv.direction == "SHIPMENT" and mv.source_doc_type == "store_issue":
                if in_window:
                    issued_qty += D(mv.qty)
                elif start and mv_date < start:
                    opening_qty -= D(mv.qty)

        # actual_closing is live stock (today); comparing it against a
        # window truncated at a past `end` would report window-truncation
        # as fake variance — so the reconciliation columns are only
        # returned for the as-of-now view (end unset).
        if end:
            expected_closing = None
            actual_closing = None
            variance = None
        else:
            expected_closing = opening_qty + received_qty - issued_qty
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
