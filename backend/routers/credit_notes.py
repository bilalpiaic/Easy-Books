"""Credit Notes — document-based AR reduction (ISA 240 document integrity)."""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, CreditNote, CreditNoteLine, Customer, Invoice, Product, Tenant
from routers.common import (
    SessionDep,
    WriteUserDep,
    get_or_create_account,
    log_audit,
    next_number,
)
from services.inventory import reverse_consumption
from services.money import D, ONE, ZERO, money
from services.posting import EntryInput, post_transaction
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/credit-notes", tags=["credit-notes"], dependencies=[perm_dep("credit_notes")])


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
    # None → inherit from linked invoice, else tenant base @ 1 (#300)
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    gst_amount: Decimal = Decimal("0")   # GST-output to reverse (sales return)
    restock: bool = True                 # restock stock-product lines (sales return)


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

    # Validate all tenant-owned foreign keys (IDOR protection)
    inv = None
    if body.invoice_id:
        inv = session.exec(
            select(Invoice).where(Invoice.id == body.invoice_id, Invoice.tenant_id == user.tenant_id)
        ).first()
        if not inv:
            raise HTTPException(400, "Invoice not found for this tenant")
    if body.customer_id:
        cust = session.exec(
            select(Customer).where(Customer.id == body.customer_id, Customer.tenant_id == user.tenant_id)
        ).first()
        if not cust:
            raise HTTPException(400, "Customer not found for this tenant")

    tenant = session.get(Tenant, user.tenant_id)
    base_ccy = tenant.base_currency if tenant else "PKR"
    if body.currency is not None:
        currency = body.currency
    elif inv is not None:
        currency = inv.currency
    else:
        currency = base_ccy
    if body.exchange_rate is not None:
        exchange_rate = D(str(body.exchange_rate))
    elif inv is not None:
        exchange_rate = D(str(inv.exchange_rate))
    else:
        exchange_rate = ONE
    if exchange_rate <= ZERO:
        raise HTTPException(400, "exchange_rate must be > 0")

    subtotal = money(sum(D(ln.qty) * D(ln.rate) for ln in body.lines))
    gst = money(D(str(body.gst_amount)))   # GST-output to reverse (sales return)
    total = money(subtotal + gst)

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
        gst_amount=gst,
        total=total,
        currency=currency,
        exchange_rate=exchange_rate,
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

    # GL posting (value side): Dr Revenue (+ Dr GST Payable) / Cr AR
    fx = exchange_rate
    subtotal_base = money(subtotal * fx)
    gst_base = money(gst * fx)
    total_base = money(total * fx)

    if body.ar_account_id:
        ar_acc = session.exec(
            select(Account).where(Account.id == body.ar_account_id, Account.tenant_id == user.tenant_id)
        ).first()
        if not ar_acc:
            raise HTTPException(400, "AR account not found for this tenant")
    else:
        ar_acc = get_or_create_account(session, user.tenant_id, "1100", "Accounts Receivable", "Asset")

    if body.revenue_account_id:
        rev_acc = session.exec(
            select(Account).where(Account.id == body.revenue_account_id, Account.tenant_id == user.tenant_id)
        ).first()
        if not rev_acc:
            raise HTTPException(400, "Revenue account not found for this tenant")
    else:
        rev_acc = get_or_create_account(session, user.tenant_id, "4000", "Sales Revenue", "Revenue")

    entries = [
        EntryInput(account_id=rev_acc.id, debit=subtotal_base),   # reduce revenue
    ]
    if gst_base > ZERO:
        gst_acc = get_or_create_account(
            session, user.tenant_id, "2200", "GST Payable (Output)", "Liability"
        )
        entries.append(EntryInput(account_id=gst_acc.id, debit=gst_base))  # reverse output GST
    entries.append(EntryInput(account_id=ar_acc.id, credit=total_base))    # reduce AR

    txn = post_transaction(
        session,
        user,
        date=body.issue_date,
        description=body.description or f"Credit Note {number}",
        entries=entries,
        audit_entity_type="credit_note",
        audit_detail={"cn_number": number, "total": str(total)},
        voucher_type="CN",
    )

    cn.transaction_id = txn.id
    cn.ar_account_id = ar_acc.id
    cn.revenue_account_id = rev_acc.id
    cn.status = "posted"
    session.add(cn)

    # Sales-return restock: for each stock-product line, restore inventory and
    # reverse COGS with a separate sub-JV (mirror of the COGS sub-JV on invoices).
    if body.restock:
        total_cogs = ZERO
        for ln in body.lines:
            if not ln.product_id:
                continue
            prod = session.exec(
                select(Product).where(
                    Product.id == ln.product_id, Product.tenant_id == user.tenant_id
                )
            ).first()
            if not prod or prod.product_type != "stock":
                continue
            qty = D(ln.qty)
            cogs = money(qty * D(prod.avg_cost))
            if cogs <= ZERO:
                continue
            reverse_consumption(
                session, tenant_id=user.tenant_id,
                product_id=ln.product_id, qty=qty, cogs_total=cogs,
            )
            total_cogs += cogs
        if total_cogs > ZERO:
            inv_acc = get_or_create_account(
                session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset"
            )
            cogs_acc = get_or_create_account(
                session, user.tenant_id, "5010", "Cost of Goods Sold", "Expense"
            )
            post_transaction(
                session, user,
                date=body.issue_date,
                description=f"Sales return restock for {number}",
                entries=[
                    EntryInput(account_id=inv_acc.id, debit=total_cogs),   # stock back in
                    EntryInput(account_id=cogs_acc.id, credit=total_cogs), # reverse COGS
                ],
                audit_entity_type="credit_note",
                audit_detail={"cn_number": number, "cogs_reversed": str(total_cogs)},
            )

    log_audit(session, user, "CREATE", "credit_note", cn.id, {"number": number})
    session.commit()
    session.refresh(cn)
    return cn
