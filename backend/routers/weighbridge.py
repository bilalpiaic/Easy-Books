"""Weighbridge mill workspace (#391) — ticket register (memo/ops, no GL).

v1 records vehicle weights. It does not import services.posting and never
writes journal entries. Optional copy of the ticket number onto a linked
invoice's custom_fields['x.gate_pass_no'] is a JSON merge only.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlmodel import Session, select

from models import Customer, Invoice, Tenant, Vendor
from models_weighbridge import WbTicket
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit, next_number
from routers.modules import _get_enabled
from services import weaving_calc as calc
from services.money import ZERO, money
from services.permissions import perm_dep

router = APIRouter(prefix="/api/weighbridge", tags=["weighbridge"])

_STATUSES = {"draft", "weighed_in", "completed", "cancelled"}
_DIRECTIONS = {"inbound", "outbound"}
_PARTY_TYPES = {"vendor", "customer", "other"}
_WEIGH_KINDS = {"gross", "tare"}
_MODULE_MSG = "The Weighbridge module is not installed. Install it from System → Apps."


def _require_weighbridge(session: Session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "weighbridge" not in _get_enabled(tenant):
        raise HTTPException(403, _MODULE_MSG)


def _ticket_or_404(session: Session, tenant_id: int, tid: int) -> WbTicket:
    row = session.exec(
        select(WbTicket).where(WbTicket.id == tid, WbTicket.tenant_id == tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Ticket not found")
    return row


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _ser(row: WbTicket) -> dict:
    gross = calc.weight_triple(row.gross_kg)
    tare = calc.weight_triple(row.tare_kg)
    net = calc.weight_triple(row.net_kg)
    return {
        "id": row.id,
        "number": row.number,
        "ticket_date": row.ticket_date,
        "direction": row.direction,
        "vehicle_no": row.vehicle_no,
        "driver_name": row.driver_name,
        "party_type": row.party_type,
        "party_id": row.party_id,
        "party_name": row.party_name,
        "commodity": row.commodity,
        "lot_ref": row.lot_ref,
        "gross_kg": float(row.gross_kg or 0),
        "tare_kg": float(row.tare_kg or 0),
        "net_kg": float(row.net_kg or 0),
        "gross": gross,
        "tare": tare,
        "net": net,
        "first_weigh_kind": row.first_weigh_kind,
        "first_weigh_at": _iso(row.first_weigh_at),
        "second_weigh_at": _iso(row.second_weigh_at),
        "status": row.status,
        "operator_id": row.operator_id,
        "notes": row.notes,
        "po_id": row.po_id,
        "gate_inward_id": row.gate_inward_id,
        "invoice_id": row.invoice_id,
        "sp_bale_receipt_id": row.sp_bale_receipt_id,
        "cancel_reason": row.cancel_reason,
        "created_at": _iso(row.created_at),
        "created_by_id": row.created_by_id,
    }


def _resolve_party_name(session: Session, tenant_id: int, party_type: str, party_id: int | None, fallback: str | None) -> str | None:
    if fallback:
        return fallback.strip() or None
    if party_id is None:
        return None
    if party_type == "vendor":
        v = session.exec(
            select(Vendor).where(Vendor.id == party_id, Vendor.tenant_id == tenant_id)
        ).first()
        return v.name if v else None
    if party_type == "customer":
        c = session.exec(
            select(Customer).where(Customer.id == party_id, Customer.tenant_id == tenant_id)
        ).first()
        return c.name if c else None
    return None


def _assert_party(session: Session, tenant_id: int, party_type: str, party_id: int | None, party_name: str | None) -> None:
    if party_type not in _PARTY_TYPES:
        raise HTTPException(400, f"Invalid party_type; expected one of {sorted(_PARTY_TYPES)}")
    if party_type == "other":
        return
    if party_id is None:
        if party_name:
            return
        raise HTTPException(400, f"{party_type} requires party_id or party_name")
    if party_type == "vendor":
        row = session.exec(
            select(Vendor).where(Vendor.id == party_id, Vendor.tenant_id == tenant_id)
        ).first()
        if not row:
            raise HTTPException(400, "Vendor not found")
    elif party_type == "customer":
        row = session.exec(
            select(Customer).where(Customer.id == party_id, Customer.tenant_id == tenant_id)
        ).first()
        if not row:
            raise HTTPException(400, "Customer not found")


def _apply_weigh(row: WbTicket, kind: str, kg, *, now: datetime, operator_id: int) -> None:
    if kind not in _WEIGH_KINDS:
        raise HTTPException(400, f"Invalid weigh kind; expected one of {sorted(_WEIGH_KINDS)}")
    amount = money(kg)
    if amount <= ZERO:
        raise HTTPException(400, "Weight must be greater than zero")
    if row.status == "cancelled":
        raise HTTPException(400, "Cannot weigh a cancelled ticket")
    if row.status == "completed":
        raise HTTPException(400, "Ticket is already completed")

    if row.status == "draft":
        if kind == "gross":
            row.gross_kg = amount
        else:
            row.tare_kg = amount
        row.first_weigh_kind = kind
        row.first_weigh_at = now
        row.operator_id = operator_id
        row.status = "weighed_in"
        return

    if row.status != "weighed_in":
        raise HTTPException(400, f"Cannot weigh from status {row.status}")
    if kind == row.first_weigh_kind:
        raise HTTPException(400, f"Second weigh must be the other side of {row.first_weigh_kind}")
    if kind == "gross":
        row.gross_kg = amount
    else:
        row.tare_kg = amount
    row.net_kg = money(abs(calc.net_kg(row.gross_kg, row.tare_kg)))
    row.second_weigh_at = now
    row.operator_id = operator_id
    row.status = "completed"


class TicketCreate(BaseModel):
    ticket_date: Optional[str] = None
    direction: str = "inbound"
    vehicle_no: str
    driver_name: Optional[str] = None
    party_type: str = "other"
    party_id: Optional[int] = None
    party_name: Optional[str] = None
    commodity: Optional[str] = None
    lot_ref: Optional[str] = None
    notes: Optional[str] = None
    po_id: Optional[int] = None
    gate_inward_id: Optional[int] = None
    invoice_id: Optional[int] = None
    sp_bale_receipt_id: Optional[int] = None
    first_weigh_kind: Optional[str] = None
    first_kg: Optional[float] = None
    gross_kg: Optional[float] = None
    tare_kg: Optional[float] = None


class WeighBody(BaseModel):
    kind: str
    kg: float = Field(gt=0)


class CancelBody(BaseModel):
    reason: str = Field(min_length=1)


class CopyGatePassBody(BaseModel):
    invoice_id: Optional[int] = None


def _list_query(
    session: Session,
    tenant_id: int,
    *,
    q: str | None,
    status: str | None,
    start: str | None,
    end: str | None,
):
    stmt = select(WbTicket).where(WbTicket.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(WbTicket.status == status)
    if start:
        stmt = stmt.where(WbTicket.ticket_date >= start)
    if end:
        stmt = stmt.where(WbTicket.ticket_date <= end)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                WbTicket.number.ilike(like),
                WbTicket.vehicle_no.ilike(like),
                WbTicket.driver_name.ilike(like),
                WbTicket.party_name.ilike(like),
                WbTicket.commodity.ilike(like),
                WbTicket.lot_ref.ilike(like),
            )
        )
    return stmt


@router.get("/summary", dependencies=[perm_dep("weighbridge.tickets", "view")])
def hub_summary(user: CurrentUserDep, session: SessionDep):
    _require_weighbridge(session, user)
    tid = user.tenant_id
    today = date.today().isoformat()
    today_count = session.exec(
        select(func.count(WbTicket.id)).where(
            WbTicket.tenant_id == tid,
            WbTicket.ticket_date == today,
            WbTicket.status != "cancelled",
        )
    ).one() or 0
    on_site = session.exec(
        select(func.count(WbTicket.id)).where(
            WbTicket.tenant_id == tid,
            WbTicket.status == "weighed_in",
        )
    ).one() or 0
    net_today = session.exec(
        select(func.coalesce(func.sum(WbTicket.net_kg), 0)).where(
            WbTicket.tenant_id == tid,
            WbTicket.ticket_date == today,
            WbTicket.status == "completed",
        )
    ).one() or 0
    recent = session.exec(
        select(WbTicket)
        .where(WbTicket.tenant_id == tid)
        .order_by(WbTicket.id.desc())
        .limit(8)
    ).all()
    net_val = money(net_today)
    return {
        "today_count": int(today_count),
        "on_site": int(on_site),
        "net_kg_today": float(net_val),
        "net_today": calc.weight_triple(net_val),
        "recent": [_ser(r) for r in recent],
    }


@router.get("/tickets", dependencies=[perm_dep("weighbridge.tickets", "view")])
def list_tickets(
    user: CurrentUserDep,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: Optional[str] = None,
    status: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    _require_weighbridge(session, user)
    stmt = _list_query(session, user.tenant_id, q=q, status=status, start=start, end=end)
    total = session.exec(
        select(func.count()).select_from(stmt.subquery())
    ).one() or 0
    rows = session.exec(stmt.order_by(WbTicket.id.desc()).offset(skip).limit(limit)).all()
    return {"total": int(total), "items": [_ser(r) for r in rows]}


@router.get("/reports/register", dependencies=[perm_dep("weighbridge.reports", "view")])
def ticket_register(
    user: CurrentUserDep,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: Optional[str] = None,
    status: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Same rows as the ticket list; gated by the reports right for gate clerks vs office."""
    return list_tickets(user, session, skip=skip, limit=limit, q=q, status=status, start=start, end=end)


@router.get("/tickets/{id}", dependencies=[perm_dep("weighbridge.tickets", "view")])
def get_ticket(id: int, user: CurrentUserDep, session: SessionDep):
    _require_weighbridge(session, user)
    return _ser(_ticket_or_404(session, user.tenant_id, id))


@router.post("/tickets", status_code=201, dependencies=[perm_dep("weighbridge.tickets", "edit")])
def create_ticket(user: WriteUserDep, session: SessionDep, body: TicketCreate):
    _require_weighbridge(session, user)
    if body.direction not in _DIRECTIONS:
        raise HTTPException(400, f"Invalid direction; expected one of {sorted(_DIRECTIONS)}")
    vehicle = (body.vehicle_no or "").strip()
    if not vehicle:
        raise HTTPException(400, "vehicle_no is required")
    _assert_party(session, user.tenant_id, body.party_type, body.party_id, body.party_name)
    ticket_date = (body.ticket_date or date.today().isoformat()).strip()
    num = next_number(session, user.tenant_id, "wb_ticket", "WB", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = WbTicket(
        tenant_id=user.tenant_id,
        number=num,
        ticket_date=ticket_date,
        direction=body.direction,
        vehicle_no=vehicle,
        driver_name=(body.driver_name or "").strip() or None,
        party_type=body.party_type,
        party_id=body.party_id,
        party_name=_resolve_party_name(
            session, user.tenant_id, body.party_type, body.party_id, body.party_name
        ),
        commodity=(body.commodity or "").strip() or None,
        lot_ref=(body.lot_ref or "").strip() or None,
        notes=(body.notes or "").strip() or None,
        po_id=body.po_id,
        gate_inward_id=body.gate_inward_id,
        invoice_id=body.invoice_id,
        sp_bale_receipt_id=body.sp_bale_receipt_id,
        status="draft",
        created_by_id=user.id,
    )
    now = datetime.utcnow()
    # Both weights on create → complete in one shot (seed + desk with two readings).
    if body.gross_kg and body.tare_kg:
        g, t = money(body.gross_kg), money(body.tare_kg)
        if g <= ZERO or t <= ZERO:
            raise HTTPException(400, "Weight must be greater than zero")
        row.gross_kg = g
        row.tare_kg = t
        row.net_kg = money(abs(calc.net_kg(g, t)))
        row.first_weigh_kind = "gross"
        row.first_weigh_at = now
        row.second_weigh_at = now
        row.operator_id = user.id
        row.status = "completed"
    elif body.first_weigh_kind and body.first_kg is not None:
        _apply_weigh(row, body.first_weigh_kind, body.first_kg, now=now, operator_id=user.id)
    session.add(row)
    session.commit()
    session.refresh(row)
    log_audit(session, user, "create", "wb_ticket", row.id, {"number": num})
    session.commit()
    return _ser(row)


@router.post("/tickets/{id}/weigh", dependencies=[perm_dep("weighbridge.tickets", "edit")])
def weigh_ticket(id: int, user: WriteUserDep, session: SessionDep, body: WeighBody):
    _require_weighbridge(session, user)
    row = _ticket_or_404(session, user.tenant_id, id)
    _apply_weigh(row, body.kind, body.kg, now=datetime.utcnow(), operator_id=user.id)
    session.add(row)
    session.commit()
    session.refresh(row)
    log_audit(session, user, "weigh", "wb_ticket", row.id, {"number": row.number, "kind": body.kind, "status": row.status})
    session.commit()
    return _ser(row)


@router.post("/tickets/{id}/cancel", dependencies=[perm_dep("weighbridge.tickets", "edit")])
def cancel_ticket(id: int, user: WriteUserDep, session: SessionDep, body: CancelBody):
    _require_weighbridge(session, user)
    row = _ticket_or_404(session, user.tenant_id, id)
    if row.status == "completed":
        raise HTTPException(400, "Cannot cancel a completed ticket")
    if row.status == "cancelled":
        raise HTTPException(400, "Ticket is already cancelled")
    row.status = "cancelled"
    row.cancel_reason = body.reason.strip()
    session.add(row)
    session.commit()
    session.refresh(row)
    log_audit(session, user, "cancel", "wb_ticket", row.id, {"number": row.number, "reason": row.cancel_reason})
    session.commit()
    return _ser(row)


@router.post("/tickets/{id}/copy-gate-pass", dependencies=[perm_dep("weighbridge.tickets", "edit")])
def copy_gate_pass(id: int, user: WriteUserDep, session: SessionDep, body: CopyGatePassBody):
    """Merge ticket number onto invoice.custom_fields['x.gate_pass_no'].

    Does not require invoices edit rights — the weighbridge clerk owns the slip.
    Unknown Studio keys still persist on the JSON dict (apply_incoming is not used).
    """
    _require_weighbridge(session, user)
    row = _ticket_or_404(session, user.tenant_id, id)
    if row.status != "completed":
        raise HTTPException(400, "Copy Gate pass is only available on completed tickets")
    if row.direction != "inbound":
        raise HTTPException(400, "Copy Gate pass is only available on completed inbound tickets")
    invoice_id = body.invoice_id or row.invoice_id
    if not invoice_id:
        raise HTTPException(400, "Link an invoice on the ticket or pass invoice_id")
    inv = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    cf = dict(inv.custom_fields or {})
    cf["x.gate_pass_no"] = row.number
    if row.lot_ref and not cf.get("x.lot_ref"):
        cf["x.lot_ref"] = row.lot_ref
    inv.custom_fields = cf
    if row.invoice_id != inv.id:
        row.invoice_id = inv.id
        session.add(row)
    session.add(inv)
    session.commit()
    session.refresh(inv)
    log_audit(
        session, user, "copy_gate_pass", "wb_ticket", row.id,
        {"number": row.number, "invoice_id": inv.id, "invoice_number": inv.number},
    )
    session.commit()
    return {
        "ok": True,
        "invoice_id": inv.id,
        "invoice_number": inv.number,
        "gate_pass_no": cf["x.gate_pass_no"],
        "custom_fields": inv.custom_fields,
    }
