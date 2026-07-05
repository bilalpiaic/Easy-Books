"""Purchase-chain audit reports (#137 Phase 2): gate register + 3-way match."""
from typing import Optional

from fastapi import APIRouter
from sqlmodel import select

from models import (Bill, BillLine, GateInward, GateInwardLine, PurchaseOrder,
                    PurchaseOrderLine, User)
from routers.common import SessionDep, WriteUserDep
from services.gate import gi_coverage
from services.money import D
from services.permissions import perm_dep

router = APIRouter(prefix="/api/purchase-reports", tags=["purchase-reports"])


@router.get("/gate-register", dependencies=[perm_dep("purchase.gate")])
def gate_register(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None, q: Optional[str] = None,
):
    query = select(GateInward).where(GateInward.tenant_id == user.tenant_id)
    if start:
        query = query.where(GateInward.gate_date >= start)
    if end:
        query = query.where(GateInward.gate_date <= end)
    gis = session.exec(query.order_by(GateInward.id.desc())).all()

    users = {u.id: u.full_name for u in session.exec(
        select(User).where(User.tenant_id == user.tenant_id)).all()}
    out = []
    for gi in gis:
        if q:
            needle = q.lower()
            hay = f"{gi.vehicle_no or ''} {gi.challan_no or ''}".lower()
            if needle not in hay:
                continue
        lines = session.exec(
            select(GateInwardLine).where(GateInwardLine.gate_inward_id == gi.id)
        ).all()
        po = session.get(PurchaseOrder, gi.po_id)
        row = gi.model_dump()
        row["po_number"] = po.number if po else None
        row["vendor_name"] = po.vendor_name if po else None
        row["item_count"] = len(lines)
        row["total_qty"] = sum(D(l.qty_received) for l in lines)
        row["recorded_by"] = users.get(gi.created_by_id, "—")
        out.append(row)
    return out


@router.get("/three-way-match", dependencies=[perm_dep("purchase.comparative")])
def three_way_match(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    query = select(PurchaseOrder).where(PurchaseOrder.tenant_id == user.tenant_id)
    if start:
        query = query.where(PurchaseOrder.order_date >= start)
    if end:
        query = query.where(PurchaseOrder.order_date <= end)
    pos = session.exec(query.order_by(PurchaseOrder.id)).all()

    out = []
    for po in pos:
        cov = gi_coverage(session, user.tenant_id, po.id)
        has_bill = bool(po.bill_id)
        if not cov and not has_bill:
            continue  # nothing received or billed — nothing to match
        po_lines = session.exec(
            select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
            .order_by(PurchaseOrderLine.id)
        ).all()
        # Bill lines are copies of PO lines made in order at conversion —
        # positional zip is the only available linkage (BillLine has no
        # po_line_id). Manually edited bills may mis-align; acceptable for
        # a variance-flagging report.
        bill_lines = []
        if has_bill:
            bill_lines = session.exec(
                select(BillLine).where(BillLine.bill_id == po.bill_id)
                .order_by(BillLine.id)
            ).all()
        for i, pl in enumerate(po_lines):
            bl = bill_lines[i] if i < len(bill_lines) else None
            gi_qty = cov.get(pl.id, D(0))
            bill_qty = D(bl.qty) if bl else D(0)
            bill_amount = D(bl.amount) if bl else D(0)
            qty_variance = gi_qty - D(pl.qty)
            amount_variance = bill_amount - D(pl.amount)
            out.append({
                "po_number": po.number,
                "vendor_name": po.vendor_name,
                "line_description": pl.description,
                "po_qty": pl.qty, "po_rate": pl.rate, "po_amount": pl.amount,
                "gi_qty": gi_qty,
                "bill_qty": bill_qty, "bill_amount": bill_amount,
                "qty_variance": qty_variance,
                "amount_variance": amount_variance,
                "flag": bool(qty_variance != 0 or amount_variance != 0),
            })
    return out
