"""Inter-warehouse stock transfers (#302).

Lifecycle: draft → ship (in_transit via INTR) → receive → received.
Cancel only while draft. Own↔own moves do not touch Product.stock_qty or GL.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import func, select

from models import Product, StockLocation, StockTransfer, StockTransferLine
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit, next_number
from services.inventory import (
    InventoryError,
    ensure_in_transit_location,
    location_on_hand,
    transfer_stock,
)
from services.money import D, money
from services.permissions import apply_own_filter, perm_dep

router = APIRouter(
    prefix="/api/stock-transfers",
    tags=["stock-transfers"],
    dependencies=[perm_dep("inventory.transfer")],
)


class LineIn(BaseModel):
    product_id: int
    qty: Decimal
    lot_no: Optional[str] = None


class TransferIn(BaseModel):
    transfer_date: str
    from_location_id: int
    to_location_id: int
    notes: Optional[str] = None
    lines: List[LineIn]


class CancelIn(BaseModel):
    reason: Optional[str] = None


def _own_location(session, tenant_id: int, loc_id: int) -> StockLocation:
    loc = session.get(StockLocation, loc_id)
    if not loc or loc.tenant_id != tenant_id or not loc.is_active:
        raise HTTPException(400, "Invalid location")
    if loc.type != "own":
        raise HTTPException(400, "Transfers only between active own warehouses")
    return loc


def _get(session, user, transfer_id: int) -> StockTransfer:
    row = session.exec(
        select(StockTransfer).where(
            StockTransfer.id == transfer_id,
            StockTransfer.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Transfer not found")
    return row


def _serialize(session, st: StockTransfer) -> dict:
    lines = session.exec(
        select(StockTransferLine).where(StockTransferLine.transfer_id == st.id)
    ).all()
    src = session.get(StockLocation, st.from_location_id)
    dst = session.get(StockLocation, st.to_location_id)
    out = st.model_dump()
    out["from_location_code"] = src.code if src else None
    out["from_location_name"] = src.name if src else None
    out["to_location_code"] = dst.code if dst else None
    out["to_location_name"] = dst.name if dst else None
    enriched = []
    for ln in lines:
        d = ln.model_dump()
        for k, v in list(d.items()):
            if isinstance(v, Decimal):
                d[k] = float(v)
        prod = session.get(Product, ln.product_id)
        d["product_name"] = prod.name if prod else None
        d["product_code"] = prod.code if prod else None
        enriched.append(d)
    out["lines"] = enriched
    for k, v in list(out.items()):
        if isinstance(v, Decimal):
            out[k] = float(v)
    return out


@router.get("")
def list_transfers(
    session: SessionDep,
    user: CurrentUserDep,
    status: Optional[str] = None,
    q: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    base = select(StockTransfer).where(StockTransfer.tenant_id == user.tenant_id)
    base = apply_own_filter(base, StockTransfer, user, session)
    if status:
        base = base.where(StockTransfer.status == status)
    if q:
        like = f"%{q.strip()}%"
        base = base.where(StockTransfer.number.ilike(like))  # type: ignore[attr-defined]
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    rows = session.exec(
        base.order_by(StockTransfer.id.desc()).offset(skip).limit(limit)  # type: ignore
    ).all()
    return {"total": total, "items": [_serialize(session, r) for r in rows]}


@router.get("/register")
def transfer_register(
    session: SessionDep,
    user: CurrentUserDep,
    start: Optional[str] = None,
    end: Optional[str] = None,
    q: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Paginated transfer register (all statuses except cancelled by default filter via q)."""
    base = select(StockTransfer).where(StockTransfer.tenant_id == user.tenant_id)
    if start:
        base = base.where(StockTransfer.transfer_date >= start)
    if end:
        base = base.where(StockTransfer.transfer_date <= end)
    if q:
        like = f"%{q.strip()}%"
        base = base.where(StockTransfer.number.ilike(like))  # type: ignore[attr-defined]
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    rows = session.exec(
        base.order_by(StockTransfer.transfer_date.desc(), StockTransfer.id.desc())  # type: ignore
        .offset(skip)
        .limit(limit)
    ).all()
    return {"total": total, "items": [_serialize(session, r) for r in rows]}


@router.post("", status_code=201, dependencies=[perm_dep("inventory.transfer", "edit")])
def create_transfer(body: TransferIn, session: SessionDep, user: WriteUserDep):
    if not body.lines:
        raise HTTPException(400, "Transfer needs at least one line")
    if body.from_location_id == body.to_location_id:
        raise HTTPException(400, "From and to warehouses must differ")
    _own_location(session, user.tenant_id, body.from_location_id)
    _own_location(session, user.tenant_id, body.to_location_id)

    number = next_number(
        session, user.tenant_id, "stock_transfer", "ST", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    st = StockTransfer(
        tenant_id=user.tenant_id,
        number=number,
        transfer_date=body.transfer_date,
        from_location_id=body.from_location_id,
        to_location_id=body.to_location_id,
        notes=body.notes,
        status="draft",
        created_by_id=user.id,
    )
    session.add(st)
    session.flush()
    for ln in body.lines:
        prod = session.get(Product, ln.product_id)
        if not prod or prod.tenant_id != user.tenant_id or prod.product_type != "stock":
            raise HTTPException(400, f"Invalid stock product {ln.product_id}")
        qty = money(ln.qty)
        if qty <= 0:
            raise HTTPException(400, "Line qty must be > 0")
        session.add(
            StockTransferLine(
                transfer_id=st.id,
                product_id=prod.id,
                qty=qty,
                lot_no=(ln.lot_no or None),
            )
        )
    log_audit(session, user, "CREATE", "stock_transfer", st.id, {"number": number})
    session.commit()
    session.refresh(st)
    return _serialize(session, st)


@router.get("/meta/on-hand")
def on_hand_at_location(
    session: SessionDep,
    user: CurrentUserDep,
    product_id: int,
    location_id: int,
):
    """Helper for the transfer form — qty available at source warehouse."""
    prod = session.get(Product, product_id)
    if not prod or prod.tenant_id != user.tenant_id:
        raise HTTPException(404, "Product not found")
    qty = location_on_hand(
        session, tenant_id=user.tenant_id, product_id=product_id, location_id=location_id
    )
    return {"product_id": product_id, "location_id": location_id, "qty": float(qty)}


@router.get("/{transfer_id}")
def get_transfer(transfer_id: int, session: SessionDep, user: CurrentUserDep):
    return _serialize(session, _get(session, user, transfer_id))


@router.post("/{transfer_id}/ship", dependencies=[perm_dep("inventory.transfer", "edit")])
def ship_transfer(transfer_id: int, session: SessionDep, user: WriteUserDep):
    st = _get(session, user, transfer_id)
    if st.status != "draft":
        raise HTTPException(400, f"Only draft transfers can ship (status={st.status})")
    lines = session.exec(
        select(StockTransferLine).where(StockTransferLine.transfer_id == st.id)
    ).all()
    if not lines:
        raise HTTPException(400, "Transfer has no lines")

    intr = ensure_in_transit_location(session, user.tenant_id)
    try:
        for ln in lines:
            cost = transfer_stock(
                session,
                tenant_id=user.tenant_id,
                product_id=ln.product_id,
                qty=D(ln.qty),
                from_location_id=st.from_location_id,
                to_location_id=intr.id,
                source_doc_type="stock_transfer",
                source_doc_id=st.id,
                lot_no=ln.lot_no,
                notes=f"Ship {st.number}",
            )
            ln.unit_cost = money(cost / D(ln.qty)) if D(ln.qty) else money(0)
            session.add(ln)
    except InventoryError as exc:
        session.rollback()
        raise HTTPException(400, str(exc)) from exc

    st.status = "in_transit"
    st.shipped_by_id = user.id
    st.shipped_at = datetime.utcnow()
    session.add(st)
    log_audit(session, user, "SHIP", "stock_transfer", st.id, {"number": st.number})
    session.commit()
    session.refresh(st)
    return _serialize(session, st)


@router.post("/{transfer_id}/receive", dependencies=[perm_dep("inventory.transfer", "edit")])
def receive_transfer(transfer_id: int, session: SessionDep, user: WriteUserDep):
    st = _get(session, user, transfer_id)
    if st.status != "in_transit":
        raise HTTPException(400, f"Only in-transit transfers can receive (status={st.status})")
    lines = session.exec(
        select(StockTransferLine).where(StockTransferLine.transfer_id == st.id)
    ).all()
    intr = ensure_in_transit_location(session, user.tenant_id)
    try:
        for ln in lines:
            transfer_stock(
                session,
                tenant_id=user.tenant_id,
                product_id=ln.product_id,
                qty=D(ln.qty),
                from_location_id=intr.id,
                to_location_id=st.to_location_id,
                source_doc_type="stock_transfer",
                source_doc_id=st.id,
                lot_no=ln.lot_no,
                notes=f"Receive {st.number}",
            )
    except InventoryError as exc:
        session.rollback()
        raise HTTPException(400, str(exc)) from exc

    st.status = "received"
    st.received_by_id = user.id
    st.received_at = datetime.utcnow()
    session.add(st)
    log_audit(session, user, "RECEIVE", "stock_transfer", st.id, {"number": st.number})
    session.commit()
    session.refresh(st)
    return _serialize(session, st)


@router.post("/{transfer_id}/cancel", dependencies=[perm_dep("inventory.transfer", "edit")])
def cancel_transfer(
    transfer_id: int, body: CancelIn, session: SessionDep, user: WriteUserDep
):
    st = _get(session, user, transfer_id)
    if st.status != "draft":
        raise HTTPException(400, "Only draft transfers can be cancelled")
    st.status = "cancelled"
    st.cancel_reason = body.reason
    session.add(st)
    log_audit(session, user, "CANCEL", "stock_transfer", st.id, {"number": st.number})
    session.commit()
    session.refresh(st)
    return _serialize(session, st)
