"""Gate Outward — dispatch exit at the gate (#137 Phase 2b).

invoice/debit_note sources are pure memo: stock already left the books
when the source document was created/posted, so this only records the
physical exit for reconciliation. Scrap has no source document and its
own approval endpoint (see Task 4) is the transaction that consumes stock
and posts GL — this file's create/list/get/cancel handle all three types,
but only invoice/debit_note reach 'approved' immediately at creation.
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import DebitNote, GateOutward, GateOutwardLine, Invoice
from routers.common import SessionDep, WriteUserDep, log_audit, next_number
from services.money import D
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(
    prefix="/api/gate-outwards", tags=["gate-outwards"],
    dependencies=[perm_dep("store.gate_outward")],
)


class GOLineIn(BaseModel):
    product_id: int
    qty: float
    unit_cost: float = 0
    unit_value: float = 0


class GOIn(BaseModel):
    source_doc_type: str
    source_doc_id: Optional[int] = None
    gate_date: str
    time_out: Optional[str] = None
    vehicle_no: Optional[str] = None
    challan_no: Optional[str] = None
    remarks: Optional[str] = None
    lines: List[GOLineIn] = []


class GOCancel(BaseModel):
    reason: str


def _get_go(session, user, go_id: int) -> GateOutward:
    go = session.exec(
        select(GateOutward).where(
            GateOutward.id == go_id, GateOutward.tenant_id == user.tenant_id
        )
    ).first()
    if not go:
        raise HTTPException(404, "Gate outward not found")
    return go


def _serialize(session, go: GateOutward) -> dict:
    lines = session.exec(
        select(GateOutwardLine).where(GateOutwardLine.gate_outward_id == go.id)
    ).all()
    out = go.model_dump()
    out["lines"] = [l.model_dump() for l in lines]
    if go.source_doc_type == "invoice" and go.source_doc_id:
        inv = session.get(Invoice, go.source_doc_id)
        out["reference"] = inv.number if inv else None
    elif go.source_doc_type == "debit_note" and go.source_doc_id:
        dn = session.get(DebitNote, go.source_doc_id)
        out["reference"] = dn.number if dn else None
    else:
        out["reference"] = "Scrap"
    return out


def _validate_source_doc(session, user, source_doc_type: str, source_doc_id: Optional[int]) -> None:
    if source_doc_type == "invoice":
        inv = session.exec(
            select(Invoice).where(Invoice.id == source_doc_id, Invoice.tenant_id == user.tenant_id)
        ).first()
        if not inv:
            raise HTTPException(404, "Invoice not found")
        if inv.status == "void":
            raise HTTPException(400, "Cannot record a gate exit against a void invoice")
    elif source_doc_type == "debit_note":
        dn = session.exec(
            select(DebitNote).where(DebitNote.id == source_doc_id, DebitNote.tenant_id == user.tenant_id)
        ).first()
        if not dn:
            raise HTTPException(404, "Debit note not found")
        if dn.status == "draft":
            raise HTTPException(400, "Cannot record a gate exit against a draft debit note")
    elif source_doc_type != "scrap":
        raise HTTPException(400, f"Unknown source_doc_type: {source_doc_type!r}")


@router.get("")
def list_gos(
    session: SessionDep, user: WriteUserDep,
    source_doc_type: Optional[str] = None, status: Optional[str] = None,
):
    q = select(GateOutward).where(GateOutward.tenant_id == user.tenant_id)
    if source_doc_type:
        q = q.where(GateOutward.source_doc_type == source_doc_type)
    if status:
        q = q.where(GateOutward.status == status)
    q = apply_own_filter(q, GateOutward, user, session)
    rows = session.exec(q.order_by(GateOutward.id.desc())).all()
    return [_serialize(session, go) for go in rows]


@router.get("/{go_id}")
def get_go(session: SessionDep, user: WriteUserDep, go_id: int):
    return _serialize(session, _get_go(session, user, go_id))


@router.post("", status_code=201)
def create_go(session: SessionDep, user: WriteUserDep, body: GOIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    if body.source_doc_type in ("invoice", "debit_note") and not body.source_doc_id:
        raise HTTPException(400, "source_doc_id is required for this source_doc_type")

    _validate_source_doc(session, user, body.source_doc_type, body.source_doc_id)

    # Memo exits (invoice/debit_note) go straight to 'approved' — nothing to
    # approve, no GL/stock effect. Scrap creation (draft + approval) is Task 4.
    status = "approved" if body.source_doc_type in ("invoice", "debit_note") else "draft"

    number = next_number(
        session, user.tenant_id, "gate_outward", "GO", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    go = GateOutward(
        tenant_id=user.tenant_id, number=number,
        source_doc_type=body.source_doc_type, source_doc_id=body.source_doc_id,
        gate_date=body.gate_date, time_out=body.time_out,
        vehicle_no=body.vehicle_no, challan_no=body.challan_no,
        remarks=body.remarks, status=status, created_by_id=user.id,
    )
    session.add(go)
    session.flush()
    for l in body.lines:
        if D(l.qty) <= 0:
            raise HTTPException(400, "qty must be positive")
        session.add(GateOutwardLine(
            gate_outward_id=go.id, product_id=l.product_id, qty=D(l.qty),
            unit_cost=D(l.unit_cost), unit_value=D(l.unit_value),
        ))
    log_audit(session, user, "CREATE", "gate_outward", go.id, {"number": number})
    session.commit()
    return _serialize(session, go)


@router.patch("/{go_id}/cancel")
def cancel_go(session: SessionDep, user: WriteUserDep, go_id: int, body: GOCancel):
    go = _get_go(session, user, go_id)
    if not body.reason.strip():
        raise HTTPException(400, "A cancellation reason is required")
    if go.status == "cancelled":
        raise HTTPException(400, "Gate outward is already cancelled")
    if go.source_doc_type == "scrap" and go.status == "approved":
        raise HTTPException(400, "Cannot cancel an approved scrap entry — GL has been posted")
    go.status = "cancelled"
    go.cancel_reason = body.reason.strip()
    session.add(go)
    log_audit(session, user, "UPDATE", "gate_outward", go.id,
              {"action": "cancelled", "reason": go.cancel_reason})
    session.commit()
    return {"success": True, "status": "cancelled"}
