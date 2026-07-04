"""Vendor Quotations against approved Purchase Demands (#137 Phase 1). Memo documents."""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    ComparativeStatement, PurchaseDemand, PurchaseDemandLine,
    Vendor, VendorQuotation, VendorQuotationLine,
)
from routers.common import SessionDep, WriteUserDep, log_audit, next_number
from services.money import D, money
from services.permissions import perm_dep

router = APIRouter(
    prefix="/api/quotations", tags=["quotations"],
    dependencies=[perm_dep("purchase.comparative")],
)


class QuoteLineIn(BaseModel):
    demand_line_id: int
    rate: Decimal
    qty: Decimal = Decimal("1")


class QuoteIn(BaseModel):
    demand_id: int
    vendor_id: int
    quote_date: str
    valid_until: Optional[str] = None
    delivery_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    lines: List[QuoteLineIn] = []


def _serialize(session, q: VendorQuotation) -> dict:
    lines = session.exec(
        select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
    ).all()
    out = q.model_dump()
    out["lines"] = [l.model_dump() for l in lines]
    out["total"] = sum(D(l.amount) for l in lines)
    return out


def _frozen(session, tenant_id: int, demand_id: int) -> bool:
    """Quotations freeze once the demand's CS is approved or converted."""
    cs = session.exec(
        select(ComparativeStatement).where(
            ComparativeStatement.tenant_id == tenant_id,
            ComparativeStatement.demand_id == demand_id,
        )
    ).first()
    return bool(cs and cs.status in ("approved", "converted"))


def _get_quote(session, user, quote_id: int) -> VendorQuotation:
    q = session.exec(
        select(VendorQuotation).where(
            VendorQuotation.id == quote_id, VendorQuotation.tenant_id == user.tenant_id
        )
    ).first()
    if not q:
        raise HTTPException(404, "Quotation not found")
    return q


def _validate_and_write_lines(session, user, body: QuoteIn, q: VendorQuotation) -> None:
    demand_line_ids = {
        l.id for l in session.exec(
            select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == body.demand_id)
        ).all()
    }
    for l in body.lines:
        if l.demand_line_id not in demand_line_ids:
            raise HTTPException(400, f"demand_line_id {l.demand_line_id} is not on this demand")
        session.add(VendorQuotationLine(
            quotation_id=q.id, demand_line_id=l.demand_line_id,
            rate=D(l.rate), qty=D(l.qty), amount=money(D(l.rate) * D(l.qty)),
        ))


@router.get("")
def list_quotes(session: SessionDep, user: WriteUserDep, demand_id: Optional[int] = None):
    q = select(VendorQuotation).where(VendorQuotation.tenant_id == user.tenant_id)
    if demand_id:
        q = q.where(VendorQuotation.demand_id == demand_id)
    return [_serialize(session, r) for r in session.exec(q.order_by(VendorQuotation.id)).all()]


@router.get("/{quote_id}")
def get_quote(session: SessionDep, user: WriteUserDep, quote_id: int):
    return _serialize(session, _get_quote(session, user, quote_id))


@router.post("", status_code=201)
def create_quote(session: SessionDep, user: WriteUserDep, body: QuoteIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    demand = session.exec(
        select(PurchaseDemand).where(
            PurchaseDemand.id == body.demand_id, PurchaseDemand.tenant_id == user.tenant_id
        )
    ).first()
    if not demand:
        raise HTTPException(404, "Demand not found")
    if demand.status != "approved":
        raise HTTPException(400, "Quotations can only be added to an approved demand")
    if _frozen(session, user.tenant_id, demand.id):
        raise HTTPException(400, "Comparative already approved — quotations are frozen")
    vendor = session.exec(
        select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)
    ).first()
    if not vendor:
        raise HTTPException(400, "Vendor not found for this tenant")

    number = next_number(
        session, user.tenant_id, "vendor_quotation", "VQ", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    q = VendorQuotation(
        tenant_id=user.tenant_id, number=number, demand_id=body.demand_id,
        vendor_id=body.vendor_id, quote_date=body.quote_date, valid_until=body.valid_until,
        delivery_terms=body.delivery_terms, payment_terms=body.payment_terms, notes=body.notes,
    )
    session.add(q)
    session.flush()
    _validate_and_write_lines(session, user, body, q)
    log_audit(session, user, "CREATE", "vendor_quotation", q.id, {"number": number})
    session.commit()
    return _serialize(session, q)


@router.put("/{quote_id}")
def update_quote(session: SessionDep, user: WriteUserDep, quote_id: int, body: QuoteIn):
    q = _get_quote(session, user, quote_id)
    if _frozen(session, user.tenant_id, q.demand_id):
        raise HTTPException(400, "Comparative already approved — quotations are frozen")
    if body.demand_id != q.demand_id:
        raise HTTPException(400, "A quotation cannot move to a different demand")
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    q.vendor_id = body.vendor_id
    q.quote_date = body.quote_date
    q.valid_until = body.valid_until
    q.delivery_terms = body.delivery_terms
    q.payment_terms = body.payment_terms
    q.notes = body.notes
    for old in session.exec(
        select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
    ).all():
        session.delete(old)
    _validate_and_write_lines(session, user, body, q)
    session.add(q)
    log_audit(session, user, "UPDATE", "vendor_quotation", q.id, {"number": q.number})
    session.commit()
    return _serialize(session, q)


@router.delete("/{quote_id}")
def delete_quote(session: SessionDep, user: WriteUserDep, quote_id: int):
    q = _get_quote(session, user, quote_id)
    if _frozen(session, user.tenant_id, q.demand_id):
        raise HTTPException(400, "Comparative already approved — quotations are frozen")
    for l in session.exec(
        select(VendorQuotationLine).where(VendorQuotationLine.quotation_id == q.id)
    ).all():
        session.delete(l)
    session.delete(q)
    log_audit(session, user, "DELETE", "vendor_quotation", quote_id, {"number": q.number})
    session.commit()
    return {"success": True}
