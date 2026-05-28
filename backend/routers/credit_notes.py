"""Credit Notes — document-based AR reduction (ISA 240 document integrity)."""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, CreditNote, CreditNoteLine
from routers.common import (
    SessionDep,
    WriteUserDep,
    get_or_create_account,
    log_audit,
    next_number,
)
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction

router = APIRouter(prefix="/api/credit-notes", tags=["credit-notes"])


class CNLineCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")


class CNCreate(BaseModel):
    invoice_id: Optional[int] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    issue_date: str
    description: Optional[str] = None
    notes: Optional[str] = None
    lines: List[CNLineCreate] = []
    ar_account_id: Optional[int] = None
    revenue_account_id: Optional[int] = None
    currency: str = "PKR"
    exchange_rate: Decimal = Decimal("1")


@router.get("")
def list_credit_notes(
    session: SessionDep, user: WriteUserDep, skip: int = 0, limit: int = 50
):
    q = select(CreditNote).where(CreditNote.tenant_id == user.tenant_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(CreditNote.issue_date.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


@router.get("/{cn_id}")
def get_credit_note(session: SessionDep, user: WriteUserDep, cn_id: int):
    cn = session.exec(
        select(CreditNote).where(
            CreditNote.id == cn_id, CreditNote.tenant_id == user.tenant_id
        )
    ).first()
    if not cn:
        raise HTTPException(404, "Credit note not found")
    lines = session.exec(
        select(CreditNoteLine).where(CreditNoteLine.credit_note_id == cn_id)
    ).all()
    return {**cn.model_dump(), "lines": [ln.model_dump() for ln in lines]}


@router.post("", status_code=201)
def create_credit_note(session: SessionDep, user: WriteUserDep, body: CNCreate):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")

    subtotal = money(sum(D(ln.qty) * D(ln.rate) for ln in body.lines))
    total = subtotal  # CN totals do not add new tax

    number = next_number(session, user.tenant_id, "credit_note", "CN")

    cn = CreditNote(
        tenant_id=user.tenant_id,
        number=number,
        invoice_id=body.invoice_id,
        customer_id=body.customer_id,
        customer_name=body.customer_name,
        issue_date=body.issue_date,
        description=body.description,
        notes=body.notes,
        subtotal=subtotal,
        gst_amount=ZERO,
        total=total,
        currency=body.currency,
        exchange_rate=D(str(body.exchange_rate)),
        status="draft",
    )
    session.add(cn)
    session.flush()

    for ln in body.lines:
        session.add(
            CreditNoteLine(
                credit_note_id=cn.id,
                product_id=ln.product_id,
                description=ln.description,
                qty=D(ln.qty),
                unit=ln.unit,
                rate=D(ln.rate),
                amount=money(D(ln.qty) * D(ln.rate)),
            )
        )

    # GL posting: Cr AR (reduces receivable), Dr Revenue (reduces revenue)
    fx = D(str(body.exchange_rate))
    total_base = money(total * fx)

    ar_acc = (
        session.get(Account, body.ar_account_id)
        if body.ar_account_id
        else get_or_create_account(
            session, user.tenant_id, "1100", "Accounts Receivable", "Asset"
        )
    )
    rev_acc = (
        session.get(Account, body.revenue_account_id)
        if body.revenue_account_id
        else get_or_create_account(
            session, user.tenant_id, "4000", "Sales Revenue", "Revenue"
        )
    )

    txn = post_transaction(
        session,
        user,
        date=body.issue_date,
        description=body.description or f"Credit Note {number}",
        entries=[
            EntryInput(account_id=rev_acc.id, debit=total_base),   # reduce revenue
            EntryInput(account_id=ar_acc.id, credit=total_base),   # reduce AR
        ],
        audit_entity_type="credit_note",
        audit_detail={"cn_number": number, "total": str(total)},
    )

    cn.transaction_id = txn.id
    cn.ar_account_id = ar_acc.id
    cn.revenue_account_id = rev_acc.id
    cn.status = "posted"
    session.add(cn)
    log_audit(session, user, "CREATE", "credit_note", cn.id, {"number": number})
    session.commit()
    session.refresh(cn)
    return cn
