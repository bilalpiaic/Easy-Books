"""Pick/pack worksheets + stock reservations (#302)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from models import Invoice, InvoiceLine, PickList, PickListLine, Product, StockReservation
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit, next_number
from services.inventory import (
    InventoryError,
    available_qty,
    create_reservation,
    release_reservation,
    reserved_qty,
)
from services.money import D, ZERO, money
from services.permissions import apply_own_filter, perm_dep

router = APIRouter(prefix="/api/pick-lists", tags=["pick-lists"])


class ReserveIn(BaseModel):
    product_id: int
    qty: Decimal
    location_id: Optional[int] = None
    source_doc_type: str = "manual"
    source_doc_id: Optional[int] = None
    notes: Optional[str] = None


class PickFromInvoiceIn(BaseModel):
    invoice_id: int
    location_id: Optional[int] = None
    notes: Optional[str] = None
    reserve: bool = True


class PickQtyIn(BaseModel):
    lines: List[dict] = Field(default_factory=list)  # [{line_id, qty_picked}]


def _ser_pick(session, pl: PickList) -> dict:
    lines = session.exec(
        select(PickListLine).where(PickListLine.pick_list_id == pl.id)
    ).all()
    inv = session.get(Invoice, pl.invoice_id)
    out_lines = []
    for ln in lines:
        prod = session.get(Product, ln.product_id)
        out_lines.append({
            "id": ln.id,
            "product_id": ln.product_id,
            "product_name": prod.name if prod else None,
            "product_code": prod.code if prod else None,
            "qty_ordered": float(ln.qty_ordered),
            "qty_picked": float(ln.qty_picked),
            "location_id": ln.location_id,
            "reservation_id": ln.reservation_id,
        })
    return {
        "id": pl.id,
        "number": pl.number,
        "invoice_id": pl.invoice_id,
        "invoice_number": inv.number if inv else None,
        "location_id": pl.location_id,
        "status": pl.status,
        "notes": pl.notes,
        "created_at": pl.created_at,
        "packed_at": pl.packed_at,
        "lines": out_lines,
    }


@router.get("/meta/available", dependencies=[perm_dep("inventory.pick")])
def meta_available(
    session: SessionDep,
    user: CurrentUserDep,
    product_id: int,
    location_id: Optional[int] = None,
):
    return {
        "product_id": product_id,
        "location_id": location_id,
        "reserved": float(reserved_qty(
            session, tenant_id=user.tenant_id, product_id=product_id, location_id=location_id
        )),
        "available": float(available_qty(
            session, tenant_id=user.tenant_id, product_id=product_id, location_id=location_id
        )),
    }


@router.post("/reservations", status_code=201, dependencies=[perm_dep("inventory.pick", "edit")])
def reserve_stock_api(body: ReserveIn, session: SessionDep, user: WriteUserDep):
    prod = session.get(Product, body.product_id)
    if not prod or prod.tenant_id != user.tenant_id or prod.product_type != "stock":
        raise HTTPException(400, "Stock product required")
    try:
        row = create_reservation(
            session,
            tenant_id=user.tenant_id,
            product_id=body.product_id,
            qty=D(body.qty),
            location_id=body.location_id,
            source_doc_type=body.source_doc_type,
            source_doc_id=body.source_doc_id,
            notes=body.notes,
            created_by_id=user.id,
        )
    except InventoryError as exc:
        raise HTTPException(400, str(exc)) from exc
    session.commit()
    session.refresh(row)
    log_audit(session, user, "CREATE", "stock_reservation", row.id, {"qty": float(row.qty)})
    session.commit()
    return row.model_dump()


@router.get("/reservations", dependencies=[perm_dep("inventory.pick")])
def list_reservations(
    session: SessionDep,
    user: CurrentUserDep,
    status: Optional[str] = "open",
    product_id: Optional[int] = None,
):
    q = select(StockReservation).where(StockReservation.tenant_id == user.tenant_id)
    if status:
        q = q.where(StockReservation.status == status)
    if product_id:
        q = q.where(StockReservation.product_id == product_id)
    rows = session.exec(q.order_by(StockReservation.id.desc())).all()  # type: ignore
    return [r.model_dump() for r in rows]


@router.post("/reservations/{res_id}/release", dependencies=[perm_dep("inventory.pick", "edit")])
def release_res(res_id: int, session: SessionDep, user: WriteUserDep):
    row = session.get(StockReservation, res_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "Reservation not found")
    if row.status != "open":
        raise HTTPException(400, f"Cannot release reservation in status {row.status}")
    release_reservation(session, row)
    session.commit()
    return {"ok": True, "status": row.status}


@router.get("", dependencies=[perm_dep("inventory.pick")])
def list_picks(
    session: SessionDep,
    user: CurrentUserDep,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    q = select(PickList).where(PickList.tenant_id == user.tenant_id)
    q = apply_own_filter(q, PickList, user, session)
    if status:
        q = q.where(PickList.status == status)
    total = len(session.exec(q).all())
    rows = session.exec(
        q.order_by(PickList.id.desc()).offset(skip).limit(limit)  # type: ignore
    ).all()
    return {"total": total, "items": [_ser_pick(session, r) for r in rows]}


@router.get("/{pick_id}", dependencies=[perm_dep("inventory.pick")])
def get_pick(pick_id: int, session: SessionDep, user: CurrentUserDep):
    pl = session.get(PickList, pick_id)
    if not pl or pl.tenant_id != user.tenant_id:
        raise HTTPException(404, "Pick list not found")
    return _ser_pick(session, pl)


@router.post("", status_code=201, dependencies=[perm_dep("inventory.pick", "edit")])
def create_from_invoice(body: PickFromInvoiceIn, session: SessionDep, user: WriteUserDep):
    inv = session.get(Invoice, body.invoice_id)
    if not inv or inv.tenant_id != user.tenant_id:
        raise HTTPException(404, "Invoice not found")
    existing = session.exec(
        select(PickList).where(
            PickList.tenant_id == user.tenant_id,
            PickList.invoice_id == inv.id,
            PickList.status != "cancelled",
        )
    ).first()
    if existing:
        raise HTTPException(400, f"Pick list {existing.number} already exists for this invoice")

    lines = session.exec(
        select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)
    ).all()
    stock_lines = []
    for ln in lines:
        if not ln.product_id:
            continue
        prod = session.get(Product, ln.product_id)
        if prod and prod.product_type == "stock" and D(ln.qty) > ZERO:
            stock_lines.append((ln, prod))
    if not stock_lines:
        raise HTTPException(400, "Invoice has no stock product lines to pick")

    number = next_number(
        session, user.tenant_id, "pick_list", "PL", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    pl = PickList(
        tenant_id=user.tenant_id,
        number=number,
        invoice_id=inv.id,
        location_id=body.location_id,
        status="draft",
        notes=body.notes,
        created_by_id=user.id,
    )
    session.add(pl)
    session.flush()

    for ln, prod in stock_lines:
        qty = D(ln.qty)
        res_id = None
        if body.reserve:
            try:
                res = create_reservation(
                    session,
                    tenant_id=user.tenant_id,
                    product_id=prod.id,
                    qty=qty,
                    location_id=body.location_id,
                    source_doc_type="invoice",
                    source_doc_id=inv.id,
                    notes=f"Pick {number}",
                    created_by_id=user.id,
                )
                res_id = res.id
            except InventoryError as exc:
                session.rollback()
                raise HTTPException(400, str(exc)) from exc
        session.add(PickListLine(
            pick_list_id=pl.id,
            product_id=prod.id,
            qty_ordered=qty,
            qty_picked=ZERO,
            location_id=body.location_id,
            reservation_id=res_id,
        ))

    session.commit()
    session.refresh(pl)
    log_audit(session, user, "CREATE", "pick_list", pl.id, {"number": number})
    session.commit()
    return _ser_pick(session, pl)


@router.post("/{pick_id}/start", dependencies=[perm_dep("inventory.pick", "edit")])
def start_picking(pick_id: int, session: SessionDep, user: WriteUserDep):
    pl = session.get(PickList, pick_id)
    if not pl or pl.tenant_id != user.tenant_id:
        raise HTTPException(404, "Pick list not found")
    if pl.status != "draft":
        raise HTTPException(400, f"Cannot start picking from status {pl.status}")
    pl.status = "picking"
    session.add(pl)
    session.commit()
    return _ser_pick(session, pl)


@router.post("/{pick_id}/pick", dependencies=[perm_dep("inventory.pick", "edit")])
def record_picks(pick_id: int, body: PickQtyIn, session: SessionDep, user: WriteUserDep):
    pl = session.get(PickList, pick_id)
    if not pl or pl.tenant_id != user.tenant_id:
        raise HTTPException(404, "Pick list not found")
    if pl.status not in ("draft", "picking"):
        raise HTTPException(400, f"Cannot pick in status {pl.status}")
    by_id = {int(x["line_id"]): D(x.get("qty_picked", 0)) for x in body.lines if "line_id" in x}
    lines = session.exec(
        select(PickListLine).where(PickListLine.pick_list_id == pl.id)
    ).all()
    for ln in lines:
        if ln.id in by_id:
            q = by_id[ln.id]
            if q < ZERO or q > D(ln.qty_ordered):
                raise HTTPException(400, f"Invalid qty_picked for line {ln.id}")
            ln.qty_picked = q
            session.add(ln)
    if pl.status == "draft":
        pl.status = "picking"
    # Fully picked?
    if all(D(ln.qty_picked) >= D(ln.qty_ordered) for ln in lines):
        pl.status = "picked"
    session.add(pl)
    session.commit()
    return _ser_pick(session, pl)


@router.post("/{pick_id}/pack", dependencies=[perm_dep("inventory.pick", "edit")])
def pack_pick(pick_id: int, session: SessionDep, user: WriteUserDep):
    pl = session.get(PickList, pick_id)
    if not pl or pl.tenant_id != user.tenant_id:
        raise HTTPException(404, "Pick list not found")
    if pl.status not in ("picked", "picking"):
        raise HTTPException(400, f"Cannot pack from status {pl.status}")
    lines = session.exec(
        select(PickListLine).where(PickListLine.pick_list_id == pl.id)
    ).all()
    if not lines or any(D(ln.qty_picked) <= ZERO for ln in lines):
        raise HTTPException(400, "Record picks before packing")
    pl.status = "packed"
    pl.packed_at = datetime.utcnow()
    session.add(pl)
    session.commit()
    log_audit(session, user, "PACK", "pick_list", pl.id, {"number": pl.number})
    session.commit()
    return _ser_pick(session, pl)


@router.post("/{pick_id}/cancel", dependencies=[perm_dep("inventory.pick", "edit")])
def cancel_pick(pick_id: int, session: SessionDep, user: WriteUserDep):
    pl = session.get(PickList, pick_id)
    if not pl or pl.tenant_id != user.tenant_id:
        raise HTTPException(404, "Pick list not found")
    if pl.status == "packed":
        raise HTTPException(400, "Cannot cancel a packed pick list")
    if pl.status == "cancelled":
        return _ser_pick(session, pl)
    lines = session.exec(
        select(PickListLine).where(PickListLine.pick_list_id == pl.id)
    ).all()
    for ln in lines:
        if ln.reservation_id:
            res = session.get(StockReservation, ln.reservation_id)
            if res and res.status == "open":
                release_reservation(session, res)
    pl.status = "cancelled"
    session.add(pl)
    session.commit()
    return _ser_pick(session, pl)
