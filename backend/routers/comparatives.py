"""Comparative Statements — quotation comparison + vendor selection (#137 Phase 1).
Control rules: one CS per demand; approver ≠ creator; lowest-or-justify."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    ComparativeStatement, PurchaseDemand, PurchaseDemandLine, PurchaseOrder,
    PurchaseOrderLine, Vendor, VendorQuotation, VendorQuotationLine,
)
from routers.common import AdminUserDep, SessionDep, WriteUserDep, log_audit, next_number
from services.money import D, money
from services.permissions import perm_dep

router = APIRouter(
    prefix="/api/comparatives", tags=["comparatives"],
    dependencies=[perm_dep("purchase.comparative")],
)


class CSCreate(BaseModel):
    demand_id: int
    cs_date: str


class CSUpdate(BaseModel):
    selected_quotation_id: Optional[int] = None
    justification: Optional[str] = None


def _get_cs(session, user, cs_id: int) -> ComparativeStatement:
    cs = session.exec(
        select(ComparativeStatement).where(
            ComparativeStatement.id == cs_id,
            ComparativeStatement.tenant_id == user.tenant_id,
        )
    ).first()
    if not cs:
        raise HTTPException(404, "Comparative not found")
    return cs


def _quote_totals(session, demand_id: int) -> dict[int, object]:
    """quotation_id → Decimal total, for every quotation on the demand."""
    totals: dict[int, object] = {}
    for q in session.exec(
        select(VendorQuotation).where(VendorQuotation.demand_id == demand_id)
    ).all():
        lines = session.exec(
            select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
        ).all()
        totals[q.id] = sum(D(l.amount) for l in lines)
    return totals


def _serialize(session, user, cs: ComparativeStatement) -> dict:
    demand = session.get(PurchaseDemand, cs.demand_id)
    demand_lines = session.exec(
        select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == cs.demand_id)
    ).all()
    quotes = session.exec(
        select(VendorQuotation).where(
            VendorQuotation.demand_id == cs.demand_id,
            VendorQuotation.tenant_id == user.tenant_id,
        ).order_by(VendorQuotation.id)
    ).all()
    totals = _quote_totals(session, cs.demand_id)
    vendors = {
        v.id: v.name for v in session.exec(
            select(Vendor).where(Vendor.tenant_id == user.tenant_id)
        ).all()
    }
    quote_lines = {
        q.id: {
            l.demand_line_id: l for l in session.exec(
                select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
            ).all()
        }
        for q in quotes
    }
    out = cs.model_dump()
    out["demand"] = {**demand.model_dump(), "lines": [dl.model_dump() for dl in demand_lines]}
    out["quotations"] = [
        {**q.model_dump(), "vendor_name": vendors.get(q.vendor_id, "—"),
         "total": totals.get(q.id, 0)}
        for q in quotes
    ]
    out["matrix"] = [
        {
            "demand_line": dl.model_dump(),
            "cells": [
                {
                    "quotation_id": q.id,
                    "rate": (quote_lines[q.id].get(dl.id).rate
                             if quote_lines[q.id].get(dl.id) else None),
                    "amount": (quote_lines[q.id].get(dl.id).amount
                               if quote_lines[q.id].get(dl.id) else None),
                }
                for q in quotes
            ],
        }
        for dl in demand_lines
    ]
    return out


@router.get("")
def list_cs(session: SessionDep, user: WriteUserDep, status: Optional[str] = None):
    q = select(ComparativeStatement).where(ComparativeStatement.tenant_id == user.tenant_id)
    if status:
        q = q.where(ComparativeStatement.status == status)
    return [
        _serialize(session, user, cs)
        for cs in session.exec(q.order_by(ComparativeStatement.id.desc())).all()
    ]


@router.get("/{cs_id}")
def get_cs(session: SessionDep, user: WriteUserDep, cs_id: int):
    return _serialize(session, user, _get_cs(session, user, cs_id))


@router.post("", status_code=201)
def create_cs(session: SessionDep, user: WriteUserDep, body: CSCreate):
    demand = session.exec(
        select(PurchaseDemand).where(
            PurchaseDemand.id == body.demand_id,
            PurchaseDemand.tenant_id == user.tenant_id,
        )
    ).first()
    if not demand:
        raise HTTPException(404, "Demand not found")
    if demand.status != "approved":
        raise HTTPException(400, "A comparative requires an approved demand")
    existing = session.exec(
        select(ComparativeStatement).where(
            ComparativeStatement.tenant_id == user.tenant_id,
            ComparativeStatement.demand_id == body.demand_id,
        )
    ).first()
    if existing:
        raise HTTPException(400, f"Comparative {existing.number} already exists for this demand")
    number = next_number(
        session, user.tenant_id, "comparative_statement", "CS", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    cs = ComparativeStatement(
        tenant_id=user.tenant_id, number=number, demand_id=body.demand_id,
        cs_date=body.cs_date, status="draft", created_by_id=user.id,
    )
    session.add(cs)
    log_audit(session, user, "CREATE", "comparative_statement", None, {"number": number})
    session.commit()
    session.refresh(cs)
    return _serialize(session, user, cs)


@router.put("/{cs_id}")
def update_cs(session: SessionDep, user: WriteUserDep, cs_id: int, body: CSUpdate):
    cs = _get_cs(session, user, cs_id)
    if cs.status != "draft":
        raise HTTPException(400, f"Cannot edit a comparative with status '{cs.status}'")
    if body.selected_quotation_id is not None:
        q = session.exec(
            select(VendorQuotation).where(
                VendorQuotation.id == body.selected_quotation_id,
                VendorQuotation.demand_id == cs.demand_id,
                VendorQuotation.tenant_id == user.tenant_id,
            )
        ).first()
        if not q:
            raise HTTPException(400, "Selected quotation is not on this demand")
    cs.selected_quotation_id = body.selected_quotation_id
    cs.justification = body.justification
    session.add(cs)
    log_audit(session, user, "UPDATE", "comparative_statement", cs.id, {"number": cs.number})
    session.commit()
    return _serialize(session, user, cs)


@router.patch("/{cs_id}/approve")
def approve_cs(session: SessionDep, user: AdminUserDep, cs_id: int):
    cs = _get_cs(session, user, cs_id)
    if cs.status != "draft":
        raise HTTPException(400, f"Cannot approve a comparative with status '{cs.status}'")
    if cs.created_by_id == user.id:
        raise HTTPException(400, "A comparative cannot be approved by its creator")
    if not cs.selected_quotation_id:
        raise HTTPException(400, "Select a winning quotation before approval")
    totals = _quote_totals(session, cs.demand_id)
    if not totals:
        raise HTTPException(400, "No quotations on this demand")
    selected_total = totals.get(cs.selected_quotation_id)
    if selected_total is None:
        raise HTTPException(400, "Selected quotation no longer exists — re-select a winner")
    lowest_total = min(totals.values())
    needs_justification = len(totals) < 2 or selected_total != lowest_total
    if needs_justification and not (cs.justification and cs.justification.strip()):
        raise HTTPException(
            400,
            "Justification required: fewer than two quotations, or the selected "
            "quotation is not the lowest",
        )
    demand_line_ids = {
        dl.id for dl in session.exec(
            select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == cs.demand_id)
        ).all()
    }
    quoted_line_ids = {
        ql.demand_line_id for ql in session.exec(
            select(VendorQuotationLine).where(
                VendorQuotationLine.quotation_id == cs.selected_quotation_id
            )
        ).all()
    }
    missing = demand_line_ids - quoted_line_ids
    if missing:
        raise HTTPException(
            400,
            f"Selected quotation does not price {len(missing)} demand line(s) — "
            "a comparative can only be approved on a complete quotation",
        )
    cs.status = "approved"
    cs.approved_by_id = user.id
    cs.approved_at = datetime.utcnow()
    session.add(cs)
    log_audit(session, user, "UPDATE", "comparative_statement", cs.id, {"action": "approved"})
    session.commit()
    return {"success": True, "status": "approved"}


@router.post("/{cs_id}/convert-to-po", status_code=201)
def convert_to_po(session: SessionDep, user: WriteUserDep, cs_id: int):
    cs = _get_cs(session, user, cs_id)
    if cs.status != "approved":
        raise HTTPException(400, "Only an approved comparative can convert to a PO")
    quote = session.get(VendorQuotation, cs.selected_quotation_id)
    if not quote:
        raise HTTPException(400, "Selected quotation no longer exists")
    vendor = session.get(Vendor, quote.vendor_id)
    demand = session.get(PurchaseDemand, cs.demand_id)
    if demand.status != "approved":
        raise HTTPException(
            400, f"Cannot convert — the demand is '{demand.status}', not approved"
        )
    demand_lines = {
        dl.id: dl for dl in session.exec(
            select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == cs.demand_id)
        ).all()
    }
    quote_lines = session.exec(
        select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == quote.id)
    ).all()

    subtotal = money(sum(D(l.amount) for l in quote_lines))
    po_number = next_number(session, user.tenant_id, "purchase_order", "PO")
    po = PurchaseOrder(
        tenant_id=user.tenant_id, number=po_number, vendor_id=vendor.id,
        vendor_name=vendor.name, order_date=cs.cs_date,
        description=f"Converted from {cs.number} ({demand.number})",
        subtotal=subtotal, total=subtotal, status="draft",
        demand_id=cs.demand_id, comparative_id=cs.id,
    )
    session.add(po)
    session.flush()
    for ql in quote_lines:
        dl = demand_lines[ql.demand_line_id]
        session.add(PurchaseOrderLine(
            po_id=po.id, product_id=dl.product_id, description=dl.description,
            qty=D(ql.qty), unit=dl.unit, rate=D(ql.rate), amount=money(D(ql.qty) * D(ql.rate)),
        ))
    cs.status = "converted"
    cs.po_id = po.id
    demand.status = "converted"
    session.add(cs)
    session.add(demand)
    log_audit(session, user, "CREATE", "purchase_order", po.id,
              {"number": po_number, "from_comparative": cs.number})
    session.commit()
    session.refresh(po)
    return po
