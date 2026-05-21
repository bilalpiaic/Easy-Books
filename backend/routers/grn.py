"""Goods Receipt Note — receive customer-supplied material into the godown.

A GRN is *custodial*: the goods belong to the customer, not us. We hold
them and later issue them to a production order. The receipt does NOT
debit our inventory asset. If a `declared_value` is supplied, a memo
JE pair (Dr 1210 / Cr 2150) is posted to keep an off-balance-sheet
record of our custodian liability.
"""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Customer, GoodsReceiptNote, GRNLine, Product, StockLocation
from services.inventory import record_movement
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction

from .common import (
    CurrentUserDep, SessionDep, WriteUserDep,
    get_or_create_account, log_audit, next_number,
)
from models import InventoryLayer

router = APIRouter(prefix="/api/grn", tags=["grn"])


class GRNLineIn(BaseModel):
    product_id: int
    qty: Decimal
    lot_no: Optional[str] = None
    declared_value: Decimal = Decimal("0")
    notes: Optional[str] = None


class GRNCreate(BaseModel):
    customer_id: int
    received_date: str
    location_id: Optional[int] = None        # defaults to first customer_custodial loc
    notes: Optional[str] = None
    lines: List[GRNLineIn]


def _resolve_godown(session, tenant_id: int) -> Optional[StockLocation]:
    return session.exec(
        select(StockLocation).where(
            StockLocation.tenant_id == tenant_id,
            StockLocation.type == "customer_custodial",
            StockLocation.is_active == True,  # noqa: E712
        ).order_by(StockLocation.id)
    ).first()


def _validate(session, tenant_id: int, body: GRNCreate) -> StockLocation:
    if not body.lines:
        raise HTTPException(400, "GRN must have at least one line")
    cust = session.get(Customer, body.customer_id)
    if not cust or cust.tenant_id != tenant_id:
        raise HTTPException(400, "Customer not found")
    if body.location_id is not None:
        loc = session.get(StockLocation, body.location_id)
        if not loc or loc.tenant_id != tenant_id:
            raise HTTPException(400, "Location not found")
        if loc.type != "customer_custodial":
            raise HTTPException(
                400, "Location must be of type 'customer_custodial' (a godown)"
            )
    else:
        loc = _resolve_godown(session, tenant_id)
        if not loc:
            raise HTTPException(
                400,
                "No customer_custodial location configured. "
                "Create a godown first or switch business model to manufacturing.",
            )
    # Validate products
    pids = {ln.product_id for ln in body.lines}
    rows = session.exec(
        select(Product.id).where(Product.id.in_(pids), Product.tenant_id == tenant_id)
    ).all()
    if len(set(rows)) != len(pids):
        raise HTTPException(400, "One or more line products not found")
    for ln in body.lines:
        if D(ln.qty) <= 0:
            raise HTTPException(400, "qty must be > 0 on every line")
        if D(ln.declared_value) < 0:
            raise HTTPException(400, "declared_value must be >= 0")
    return loc


def _serialise(session, h: GoodsReceiptNote) -> dict:
    lines = session.exec(
        select(GRNLine).where(GRNLine.grn_id == h.id).order_by(GRNLine.id)
    ).all()
    return {**h.model_dump(), "lines": [ln.model_dump() for ln in lines]}


@router.get("")
def list_grns(
    session: SessionDep, user: CurrentUserDep,
    customer_id: Optional[int] = None,
    skip: int = 0, limit: int = 100,
):
    q = select(GoodsReceiptNote).where(GoodsReceiptNote.tenant_id == user.tenant_id)
    if customer_id:
        q = q.where(GoodsReceiptNote.customer_id == customer_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(GoodsReceiptNote.id.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": [_serialise(session, h) for h in items]}


@router.get("/{grn_id}")
def get_grn(session: SessionDep, user: CurrentUserDep, grn_id: int):
    h = session.exec(
        select(GoodsReceiptNote).where(
            GoodsReceiptNote.id == grn_id,
            GoodsReceiptNote.tenant_id == user.tenant_id,
        )
    ).first()
    if not h:
        raise HTTPException(404, "GRN not found")
    return _serialise(session, h)


@router.post("", status_code=201)
def create_grn(session: SessionDep, user: WriteUserDep, body: GRNCreate):
    loc = _validate(session, user.tenant_id, body)

    number = next_number(session, user.tenant_id, "grn", "GRN", width=4)
    total_declared = sum((D(ln.declared_value) for ln in body.lines), start=ZERO)

    grn = GoodsReceiptNote(
        tenant_id=user.tenant_id,
        number=number,
        customer_id=body.customer_id,
        received_date=body.received_date,
        location_id=loc.id,
        declared_value=money(total_declared),
        notes=body.notes,
    )
    session.add(grn)
    session.flush()

    # Persist lines + inventory layers + stock movements
    for ln in body.lines:
        gline = GRNLine(
            grn_id=grn.id,
            product_id=ln.product_id,
            qty=money(D(ln.qty)),
            lot_no=ln.lot_no,
            declared_value=money(D(ln.declared_value)),
            notes=ln.notes,
        )
        session.add(gline)

        # Custodial layer at zero cost (they're not our asset). owner_customer_id
        # marks who owns this lot.
        session.add(InventoryLayer(
            tenant_id=user.tenant_id,
            product_id=ln.product_id,
            location_id=loc.id,
            owner_customer_id=body.customer_id,
            lot_no=ln.lot_no,
            qty_received=D(ln.qty),
            qty_remaining=D(ln.qty),
            unit_cost=ZERO,
            source_doc=number,
        ))

        record_movement(
            session,
            tenant_id=user.tenant_id,
            product_id=ln.product_id,
            direction="CUSTODIAL_RECEIPT",
            qty=D(ln.qty),
            to_location_id=loc.id,
            lot_no=ln.lot_no,
            owner_customer_id=body.customer_id,
            source_doc_type="grn",
            source_doc_id=grn.id,
            posted_to_gl=False,
        )

    # Optional memo JE — only when caller declared a value > 0
    if total_declared > 0:
        memo_asset = get_or_create_account(
            session, user.tenant_id, "1210", "Customer Goods on Hand", "Asset"
        )
        memo_liab = get_or_create_account(
            session, user.tenant_id, "2150", "Customer Goods Liability", "Liability"
        )
        # Ensure is_memo flag — both auto-resolution paths might create them
        # without it; force the flag now so they don't pollute the BS totals.
        for acc in (memo_asset, memo_liab):
            if not acc.is_memo:
                acc.is_memo = True
                session.add(acc)
        txn = post_transaction(
            session, user,
            date=body.received_date,
            description=f"GRN {number} — custodial receipt",
            entries=[
                EntryInput(account_id=memo_asset.id, debit=money(total_declared)),
                EntryInput(account_id=memo_liab.id, credit=money(total_declared)),
            ],
            audit_entity_type="grn",
            audit_detail={"number": number, "declared_value": str(total_declared)},
        )
        grn.transaction_id = txn.id
        session.add(grn)

    log_audit(
        session, user, "CREATE", "grn", grn.id,
        {"number": number, "customer_id": body.customer_id},
    )
    session.commit()
    session.refresh(grn)
    return _serialise(session, grn)
