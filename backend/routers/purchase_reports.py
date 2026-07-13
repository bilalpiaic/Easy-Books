"""Purchase-chain audit reports (#137 Phase 2): gate register + 3-way match."""
from datetime import date as _date
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import func, or_
from sqlmodel import select

from models import (BillLine, GateInward, GateInwardLine, Product, PurchaseOrder,
                    PurchaseOrderLine, PurchaseDemandLine, User, Vendor,
                    VendorQuotation, VendorQuotationLine)
from routers.common import SessionDep, WriteUserDep
from services.gate import gi_coverage
from services.money import D
from services.permissions import apply_own_filter, perm_dep

router = APIRouter(prefix="/api/purchase-reports", tags=["purchase-reports"])


@router.get("/gate-register", dependencies=[perm_dep("purchase.gate")])
def gate_register(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None, q: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    query = select(GateInward).where(GateInward.tenant_id == user.tenant_id)
    if start:
        query = query.where(GateInward.gate_date >= start)
    if end:
        query = query.where(GateInward.gate_date <= end)
    if q:
        like = f"%{q}%"
        query = query.where(or_(
            GateInward.vehicle_no.ilike(like), GateInward.challan_no.ilike(like),
        ))
    query = apply_own_filter(query, GateInward, user, session)
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    gis = session.exec(
        query.order_by(GateInward.id.desc()).offset(skip).limit(limit)
    ).all()

    users = {u.id: u.full_name for u in session.exec(
        select(User).where(User.tenant_id == user.tenant_id)).all()}
    out = []
    for gi in gis:
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
    return {"total": total, "items": out}


@router.get("/three-way-match", dependencies=[perm_dep("purchase.comparative")])
def three_way_match(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None, q: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    """Pagination is per PO (each PO expands to one row per line), and only
    POs with match activity — a bill or a non-cancelled Gate Inward — count."""
    has_gi = (
        select(GateInward.id)
        .where(GateInward.po_id == PurchaseOrder.id, GateInward.status != "cancelled")
        .exists()
    )
    query = select(PurchaseOrder).where(
        PurchaseOrder.tenant_id == user.tenant_id,
        or_(PurchaseOrder.bill_id.is_not(None), has_gi),
    )
    if start:
        query = query.where(PurchaseOrder.order_date >= start)
    if end:
        query = query.where(PurchaseOrder.order_date <= end)
    if q:
        like = f"%{q}%"
        query = query.where(or_(
            PurchaseOrder.number.ilike(like), PurchaseOrder.vendor_name.ilike(like),
        ))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    pos = session.exec(query.order_by(PurchaseOrder.id).offset(skip).limit(limit)).all()

    out = []
    for po in pos:
        cov = gi_coverage(session, user.tenant_id, po.id)
        has_bill = bool(po.bill_id)
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
    return {"total": total, "items": out}


@router.get("/vendor-performance", dependencies=[perm_dep("purchase.comparative")])
def vendor_performance(
    session: SessionDep, user: WriteUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    vendor_id: Optional[int] = None,
):
    vendor_query = select(Vendor).where(Vendor.tenant_id == user.tenant_id)
    if vendor_id:
        vendor_query = vendor_query.where(Vendor.id == vendor_id)
    vendors = session.exec(vendor_query).all()

    out = []
    for vendor in vendors:
        po_query = select(PurchaseOrder).where(
            PurchaseOrder.tenant_id == user.tenant_id, PurchaseOrder.vendor_id == vendor.id,
        )
        if start:
            po_query = po_query.where(PurchaseOrder.order_date >= start)
        if end:
            po_query = po_query.where(PurchaseOrder.order_date <= end)
        pos = session.exec(po_query).all()

        quotation_rows = session.exec(
            select(VendorQuotation, VendorQuotationLine, PurchaseDemandLine, Product)
            .join(VendorQuotationLine, VendorQuotationLine.quotation_id == VendorQuotation.id)
            .join(PurchaseDemandLine, PurchaseDemandLine.id == VendorQuotationLine.demand_line_id)
            .join(Product, Product.id == PurchaseDemandLine.product_id, isouter=True)
            .where(VendorQuotation.tenant_id == user.tenant_id, VendorQuotation.vendor_id == vendor.id)
            .order_by(VendorQuotation.quote_date)
        ).all()

        # Skip vendors with neither POs nor quotations
        if not pos and not quotation_rows:
            continue

        lead_times = []
        total_ordered = D("0")
        total_variance = D("0")
        for po in pos:
            gis = session.exec(
                select(GateInward).where(
                    GateInward.po_id == po.id, GateInward.status != "cancelled",
                ).order_by(GateInward.gate_date)
            ).all()
            if not gis:
                # No gate activity — the PO is still undelivered (or predates
                # the gate module). Counting it would report every pending
                # order as a 100% short receipt.
                continue
            po_lines = session.exec(
                select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
            ).all()
            total_ordered += sum(D(l.qty) for l in po_lines)
            cov = gi_coverage(session, user.tenant_id, po.id)
            for l in po_lines:
                total_variance += cov.get(l.id, D(0)) - D(l.qty)

            earliest_gi = gis[0]
            d_po = _date.fromisoformat(po.order_date)
            d_gi = _date.fromisoformat(earliest_gi.gate_date)
            lead_times.append((d_gi - d_po).days)

        rate_trend = [
            {
                "product_id": pdl.product_id, "product_name": prod.name if prod else None,
                "quote_date": vq.quote_date, "rate": float(D(vql.rate)),
            }
            for vq, vql, pdl, prod in quotation_rows
        ]

        out.append({
            "vendor_id": vendor.id, "vendor_name": vendor.name,
            "po_count": len(pos),
            "avg_lead_time_days": round(sum(lead_times) / len(lead_times), 2) if lead_times else None,
            # Proxy for rejection rate — this schema has no accepted/rejected
            # split anywhere (see spec decision #4). Negative variance only
            # (short-receipts), never counts over-receipt as "rejection".
            "short_receipt_rate_pct": (
                round(abs(min(total_variance, D(0))) / total_ordered * 100, 2)
                if total_ordered > 0 else 0.0
            ),
            "rate_trend": rate_trend,
        })
    return out
