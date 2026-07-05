"""Gate Outward — dispatch exit at the gate (#137 Phase 2b).

invoice/debit_note sources are pure memo: stock already left the books
when the source document was created/posted, so this only records the
physical exit for reconciliation. Scrap has no source document and its
own approval endpoint (see Task 4) is the transaction that consumes stock
and posts GL — this file's create/list/get/cancel handle all three types,
but only invoice/debit_note reach 'approved' immediately at creation.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import DebitNote, GateOutward, GateOutwardLine, Invoice
from routers.common import AdminUserDep, SessionDep, WriteUserDep, get_or_create_account, log_audit, next_number
from services.inventory import consume_stock
from services.money import D, money
from services.permissions import perm_dep, apply_own_filter
from services.posting import EntryInput, post_transaction

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
        # Only 'void' is rejected here (not 'draft'), intentionally asymmetric
        # with the debit-note check below: create_invoice() consumes stock at
        # creation time while the invoice is still status="draft", so a draft
        # invoice's goods have already physically left — a gate exit against
        # it is a legitimate memo. Debit notes only move stock once posted,
        # so rejecting a draft debit note (below) is correct.
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


@router.post("", status_code=201, dependencies=[perm_dep("store.gate_outward", "edit")])
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


@router.patch("/{go_id}/approve")
def approve_go(session: SessionDep, user: AdminUserDep, go_id: int):
    # Row-locked fetch: two concurrent approve calls must not both pass the
    # status check and both post GL + relieve stock. The lock is acquired
    # BEFORE the status check so a second concurrent request blocks until
    # the first commits, then observes status == 'approved' and 400s cleanly
    # instead of double-posting (see services/inventory.py:203 / routers/
    # common.py:166 for the same with_for_update() idiom).
    go = session.exec(
        select(GateOutward)
        .where(GateOutward.id == go_id, GateOutward.tenant_id == user.tenant_id)
        .with_for_update()
    ).first()
    if not go:
        raise HTTPException(404, "Gate outward not found")
    if go.source_doc_type != "scrap":
        raise HTTPException(400, "Only scrap gate-outward entries require approval")
    if go.status != "draft":
        raise HTTPException(400, f"Cannot approve a gate outward with status '{go.status}'")
    if go.created_by_id == user.id:
        raise HTTPException(400, "A gate outward cannot be approved by its creator")

    lines = session.exec(
        select(GateOutwardLine).where(GateOutwardLine.gate_outward_id == go.id)
    ).all()

    total_cost = D("0")
    total_value = D("0")
    for l in lines:
        cogs = consume_stock(
            session, tenant_id=user.tenant_id, product_id=l.product_id,
            qty=D(l.qty), source_doc_id=go.id, source_doc_type="gate_outward",
        )
        total_cost += cogs
        total_value += D(l.qty) * D(l.unit_value)

    if total_value > 0:
        cash_acc = get_or_create_account(session, user.tenant_id, "1000", "Cash in Hand", "Asset")
        scrap_rev_acc = get_or_create_account(session, user.tenant_id, "4902", "Scrap Sales", "Revenue")
        post_transaction(
            session, user, date=go.gate_date,
            description=f"Scrap sale proceeds — {go.number}",
            entries=[
                EntryInput(account_id=cash_acc.id, debit=money(total_value)),
                EntryInput(account_id=scrap_rev_acc.id, credit=money(total_value)),
            ],
            voucher_type="JV",
            audit_entity_type="gate_outward",
            audit_detail={"go_number": go.number, "leg": "scrap_revenue"},
        )

    if total_cost > 0:
        scrap_exp_acc = get_or_create_account(session, user.tenant_id, "5901", "Scrap Disposal Expense", "Expense")
        inv_acc = get_or_create_account(session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset")
        post_transaction(
            session, user, date=go.gate_date,
            description=f"Scrap disposal cost — {go.number}",
            entries=[
                EntryInput(account_id=scrap_exp_acc.id, debit=money(total_cost)),
                EntryInput(account_id=inv_acc.id, credit=money(total_cost)),
            ],
            voucher_type="JV",
            audit_entity_type="gate_outward",
            audit_detail={"go_number": go.number, "leg": "scrap_cost"},
        )

    go.status = "approved"
    go.approved_by_id = user.id
    go.approved_at = datetime.utcnow()
    session.add(go)
    log_audit(session, user, "UPDATE", "gate_outward", go.id, {"action": "approved"})
    session.commit()
    return {"success": True, "status": "approved"}


@router.patch("/{go_id}/cancel", dependencies=[perm_dep("store.gate_outward", "edit")])
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
