"""Store-domain reports (#137 Phase 2b): gate-outward register + dispatch
reconciliation. Kept separate from purchase_reports.py — Gate Outward spans
Sales/Purchases/Inventory, not purely the purchase chain."""
from typing import Optional

from fastapi import APIRouter
from sqlmodel import select

from models import DebitNote, GateOutward, GateOutwardLine, Invoice
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
