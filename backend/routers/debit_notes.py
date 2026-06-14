"""Debit Notes — Purchase Returns (goods returned to a vendor).

Linked to the original bill; stock is reversed at the bill's original layer
cost via `services.inventory.return_to_vendor`. Posts:
    Dr 2000 Accounts Payable (total) / Cr 1200 Inventory (cost) + Cr 1250 GST Input (gst)
"""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, Bill, DebitNote, DebitNoteLine, Product, Vendor
from routers.common import (
    SessionDep,
    WriteUserDep,
    get_or_create_account,
    log_audit,
    next_number,
)
from services.inventory import InventoryError, return_to_vendor
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/debit-notes", tags=["debit-notes"], dependencies=[perm_dep("debit_notes")])


class DNLineCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")


class DNCreate(BaseModel):
    bill_id: int
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    issue_date: str
    description: Optional[str] = None
    notes: Optional[str] = None
    lines: List[DNLineCreate] = []
    gst_amount: Decimal = Decimal("0")
    ap_account_id: Optional[int] = None
    currency: str = "PKR"
    exchange_rate: Decimal = Decimal("1")


@router.get("")
def list_debit_notes(session: SessionDep, user: WriteUserDep, skip: int = 0, limit: int = 50):
    q = select(DebitNote).where(DebitNote.tenant_id == user.tenant_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(DebitNote.issue_date.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


@router.get("/{dn_id}")
def get_debit_note(session: SessionDep, user: WriteUserDep, dn_id: int):
    dn = session.exec(
        select(DebitNote).where(DebitNote.id == dn_id, DebitNote.tenant_id == user.tenant_id)
    ).first()
    if not dn:
        raise HTTPException(404, "Debit note not found")
    lines = session.exec(
        select(DebitNoteLine).where(DebitNoteLine.debit_note_id == dn_id)
    ).all()
    return {**dn.model_dump(), "lines": [ln.model_dump() for ln in lines]}


@router.post("", status_code=201)
def create_debit_note(session: SessionDep, user: WriteUserDep, body: DNCreate):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")

    # Validate the original bill belongs to this tenant (IDOR guard).
    bill = session.exec(
        select(Bill).where(Bill.id == body.bill_id, Bill.tenant_id == user.tenant_id)
    ).first()
    if not bill:
        raise HTTPException(400, "Original bill not found for this tenant")

    vendor_id = body.vendor_id or bill.vendor_id
    vendor_name = body.vendor_name or bill.vendor_name
    if vendor_id:
        v = session.exec(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id)
        ).first()
        if not v:
            raise HTTPException(400, "Vendor not found for this tenant")
        vendor_name = vendor_name or v.name

    subtotal = money(sum(D(ln.qty) * D(ln.rate) for ln in body.lines))
    gst = money(D(str(body.gst_amount)))
    total = money(subtotal + gst)

    number = next_number(session, user.tenant_id, "debit_note", "DN")

    dn = DebitNote(
        tenant_id=user.tenant_id, number=number, bill_id=bill.id,
        vendor_id=vendor_id, vendor_name=vendor_name, issue_date=body.issue_date,
        description=body.description, notes=body.notes, subtotal=subtotal,
        gst_amount=gst, total=total, currency=body.currency,
        exchange_rate=D(str(body.exchange_rate)), status="draft",
    )
    session.add(dn)
    session.flush()

    for ln in body.lines:
        session.add(
            DebitNoteLine(
                debit_note_id=dn.id, product_id=ln.product_id,
                description=ln.description, qty=D(ln.qty), unit=ln.unit,
                rate=D(ln.rate), amount=money(D(ln.qty) * D(ln.rate)),
            )
        )

    fx = D(str(body.exchange_rate))
    gst_base = money(gst * fx)

    ap_acc = (
        session.exec(
            select(Account).where(Account.id == body.ap_account_id, Account.tenant_id == user.tenant_id)
        ).first()
        if body.ap_account_id
        else get_or_create_account(session, user.tenant_id, "2000", "Accounts Payable", "Liability")
    )
    if not ap_acc:
        raise HTTPException(400, "AP account not found for this tenant")
    inv_acc = get_or_create_account(session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset")

    # Reverse stock at the original bill's layer cost. The actual cost removed
    # becomes the inventory credit so stock value stays exact.
    stock_cost_base = ZERO
    non_stock_base = ZERO
    for ln in body.lines:
        line_base = money(D(ln.qty) * D(ln.rate) * fx)
        is_stock = False
        if ln.product_id:
            prod = session.exec(
                select(Product).where(
                    Product.id == ln.product_id, Product.tenant_id == user.tenant_id
                )
            ).first()
            is_stock = bool(prod and prod.product_type == "stock")
        if is_stock:
            try:
                cost_removed = return_to_vendor(
                    session, tenant_id=user.tenant_id, product_id=ln.product_id,
                    qty=D(ln.qty), source_doc=bill.number,
                )
            except InventoryError as e:
                raise HTTPException(400, str(e))
            stock_cost_base += money(cost_removed * fx)
        else:
            non_stock_base += line_base

    # GL: Dr AP (total) / Cr Inventory (stock cost) + Cr expense-equiv (non-stock) + Cr GST input
    total_base = money(stock_cost_base + non_stock_base + gst_base)
    entries = [EntryInput(account_id=ap_acc.id, debit=total_base)]
    if stock_cost_base > ZERO:
        entries.append(EntryInput(account_id=inv_acc.id, credit=stock_cost_base))
    if non_stock_base > ZERO:
        exp_acc = get_or_create_account(session, user.tenant_id, "5000", "General Expenses", "Expense")
        entries.append(EntryInput(account_id=exp_acc.id, credit=non_stock_base))
    if gst_base > ZERO:
        gst_in_acc = get_or_create_account(session, user.tenant_id, "1250", "GST Receivable (Input)", "Asset")
        entries.append(EntryInput(account_id=gst_in_acc.id, credit=gst_base))

    txn = post_transaction(
        session, user, date=body.issue_date,
        description=body.description or f"Debit Note {number} (return vs {bill.number})",
        entries=entries,
        audit_entity_type="debit_note",
        audit_detail={"dn_number": number, "bill": bill.number},
        voucher_type="DN",
    )
    dn.transaction_id = txn.id
    dn.ap_account_id = ap_acc.id
    dn.subtotal = money(stock_cost_base + non_stock_base) / (fx if fx else D(1))
    dn.total = money(total_base / (fx if fx else D(1)))
    dn.status = "posted"
    session.add(dn)
    log_audit(session, user, "CREATE", "debit_note", dn.id, {"number": number})
    session.commit()
    session.refresh(dn)
    return dn
