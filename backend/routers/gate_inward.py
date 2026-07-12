"""Gate Inward — receipt control at the gate (#137 Phase 2). Memo, no GL."""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import GateInward, GateInwardLine, PurchaseOrder, PurchaseOrderLine
from routers.common import SessionDep, WriteUserDep, log_audit, next_number
from services.gate import gi_coverage
from services.money import D
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(
    prefix="/api/gate-inwards", tags=["gate-inwards"],
    dependencies=[perm_dep("purchase.gate")],
)


class GILineIn(BaseModel):
    po_line_id: int
    qty_received: Decimal


class GIIn(BaseModel):
    po_id: int
    gate_date: str
    time_in: Optional[str] = None
    vehicle_no: Optional[str] = None
    challan_no: Optional[str] = None
    remarks: Optional[str] = None
    lines: List[GILineIn] = []


class GICancel(BaseModel):
    reason: str


def _get_gi(session, user, gi_id: int) -> GateInward:
    gi = session.exec(
        select(GateInward).where(
            GateInward.id == gi_id, GateInward.tenant_id == user.tenant_id
        )
    ).first()
    if not gi:
        raise HTTPException(404, "Gate inward not found")
    return gi


def _serialize(session, gi: GateInward) -> dict:
    lines = session.exec(
        select(GateInwardLine).where(GateInwardLine.gate_inward_id == gi.id)
    ).all()
    po = session.get(PurchaseOrder, gi.po_id)
    out = gi.model_dump()
    out["lines"] = [l.model_dump() for l in lines]
    out["po_number"] = po.number if po else None
    out["vendor_name"] = po.vendor_name if po else None
    return out


def _recompute_po_status(session, tenant_id: int, po: PurchaseOrder) -> None:
    """Coverage is the single source of truth for approved ↔ received."""
    from services.gate import po_fully_covered
    full = po_fully_covered(session, tenant_id, po.id)
    if full and po.status == "approved":
        po.status = "received"
        session.add(po)
    elif not full and po.status == "received":
        po.status = "approved"
        session.add(po)


@router.get("")
def list_gis(
    session: SessionDep, user: WriteUserDep,
    po_id: Optional[int] = None, status: Optional[str] = None,
):
    q = select(GateInward).where(GateInward.tenant_id == user.tenant_id)
    if po_id:
        q = q.where(GateInward.po_id == po_id)
    if status:
        q = q.where(GateInward.status == status)
    q = apply_own_filter(q, GateInward, user, session)
    rows = session.exec(q.order_by(GateInward.id.desc())).all()
    return [_serialize(session, gi) for gi in rows]


@router.get("/{gi_id}")
def get_gi(session: SessionDep, user: WriteUserDep, gi_id: int):
    return _serialize(session, _get_gi(session, user, gi_id))


@router.post("", status_code=201, dependencies=[perm_dep("purchase.gate", "edit")])
def create_gi(session: SessionDep, user: WriteUserDep, body: GIIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")
    # Row-locked fetch (see routers/gate_outward.py:172 for the idiom): two
    # concurrent GI creates against the same PO must not both read the same
    # coverage snapshot and jointly over-receive. SQLite ignores the lock;
    # Postgres serializes on the PO row.
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == body.po_id, PurchaseOrder.tenant_id == user.tenant_id
        ).with_for_update()
    ).first()
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po.status not in ("approved", "received"):
        raise HTTPException(
            400, f"Gate inward requires an approved PO (status is '{po.status}')"
        )

    po_lines = {
        l.id: l for l in session.exec(
            select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
        ).all()
    }
    cov = gi_coverage(session, user.tenant_id, po.id)
    for l in body.lines:
        po_line = po_lines.get(l.po_line_id)
        if not po_line:
            raise HTTPException(400, f"po_line_id {l.po_line_id} is not on this PO")
        if D(l.qty_received) <= 0:
            raise HTTPException(400, "qty_received must be positive")
        remaining = D(po_line.qty) - cov.get(l.po_line_id, D(0))
        if D(l.qty_received) > remaining:
            raise HTTPException(
                400,
                f"Line '{po_line.description}': received qty would exceed the PO "
                f"(ordered {po_line.qty}, remaining {remaining})",
            )
        # Accumulate into the snapshot so duplicate po_line_id entries within
        # the same request are capped against the running total, not just the DB.
        cov[l.po_line_id] = cov.get(l.po_line_id, D(0)) + D(l.qty_received)

    number = next_number(
        session, user.tenant_id, "gate_inward", "GI", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    gi = GateInward(
        tenant_id=user.tenant_id, number=number, po_id=po.id,
        gate_date=body.gate_date, time_in=body.time_in,
        vehicle_no=body.vehicle_no, challan_no=body.challan_no,
        remarks=body.remarks, status="open", created_by_id=user.id,
    )
    session.add(gi)
    session.flush()
    for l in body.lines:
        session.add(GateInwardLine(
            gate_inward_id=gi.id, po_line_id=l.po_line_id,
            product_id=po_lines[l.po_line_id].product_id,
            qty_received=D(l.qty_received),
        ))
    session.flush()
    _recompute_po_status(session, user.tenant_id, po)
    log_audit(session, user, "CREATE", "gate_inward", gi.id, {"number": number})
    session.commit()
    return _serialize(session, gi)


@router.patch("/{gi_id}/cancel", dependencies=[perm_dep("purchase.gate", "edit")])
def cancel_gi(session: SessionDep, user: WriteUserDep, gi_id: int, body: GICancel):
    gi = _get_gi(session, user, gi_id)
    if not body.reason.strip():
        raise HTTPException(400, "A cancellation reason is required")
    if gi.status == "cancelled":
        raise HTTPException(400, "Gate inward is already cancelled")
    # Lock the PO so cancel can't race a concurrent convert-to-bill past the
    # billed check (same idiom as create_gi above).
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == gi.po_id, PurchaseOrder.tenant_id == user.tenant_id
        ).with_for_update()
    ).first()
    if gi.status == "billed" or (po and po.status == "billed"):
        raise HTTPException(400, "Cannot cancel a gate inward on a billed PO")
    gi.status = "cancelled"
    gi.cancel_reason = body.reason.strip()
    session.add(gi)
    session.flush()
    if po:
        _recompute_po_status(session, user.tenant_id, po)
    log_audit(session, user, "UPDATE", "gate_inward", gi.id,
              {"action": "cancelled", "reason": gi.cancel_reason})
    session.commit()
    return {"success": True, "status": "cancelled"}
