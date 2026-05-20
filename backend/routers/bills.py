"""Bill CRUD + auto-posting."""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, func, select

from models import Account, Bill, BillLine, Product, Settings, Tenant, Vendor
from services.fx import rate_to_base
from services.inventory import record_purchase
from services.money import D, ONE, ZERO, money, sum_money
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, get_or_create_account, log_audit

router = APIRouter(tags=["bills"])


class BillLineCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")


class BillCreate(BaseModel):
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    bill_date: str
    due_date: str
    description: Optional[str] = None
    lines: List[BillLineCreate] = []
    gst_rate: Decimal = Decimal("17")
    ap_account_id: Optional[int] = None
    expense_account_id: Optional[int] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None


def _next_bill_number(session: Session, tenant_id: int, prefix: str) -> str:
    count = session.exec(select(func.count(Bill.id)).where(Bill.tenant_id == tenant_id)).one()
    return f"{prefix}-{count + 1:04d}"


@router.get("/api/bills")
def list_bills(
    session: SessionDep, user: CurrentUserDep,
    search: str = "", skip: int = 0, limit: int = 50, status: str = "",
):
    q = select(Bill).where(Bill.tenant_id == user.tenant_id)
    if search:
        q = q.where((Bill.number.ilike(f"%{search}%")) | (Bill.vendor_name.ilike(f"%{search}%")))
    if status:
        q = q.where(Bill.status == status)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(Bill.bill_date.desc()).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.post("/api/bills", status_code=201)
def create_bill(session: SessionDep, user: WriteUserDep, body: BillCreate):
    prefix_row = session.exec(
        select(Settings).where(
            Settings.tenant_id == user.tenant_id, Settings.key == "bill_prefix"
        )
    ).first()
    prefix = prefix_row.value if prefix_row else "BILL"

    subtotal = money(sum_money(D(l.qty) * D(l.rate) for l in body.lines))
    gst_amount = money(subtotal * D(body.gst_rate) / D("100"))
    total = money(subtotal + gst_amount)

    tenant = session.get(Tenant, user.tenant_id)
    base_currency = tenant.base_currency if tenant else "USD"
    doc_currency = body.currency or base_currency
    if body.exchange_rate is not None:
        fx_rate = D(body.exchange_rate)
    elif doc_currency == base_currency:
        fx_rate = ONE
    else:
        try:
            fx_rate = rate_to_base(session, user.tenant_id, doc_currency, body.bill_date)
        except LookupError as e:
            raise HTTPException(400, str(e))

    vname = body.vendor_name
    if body.vendor_id:
        v = session.exec(
            select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)
        ).first()
        if not v:
            raise HTTPException(404, "Vendor not found")
        vname = v.name

    bill = Bill(
        tenant_id=user.tenant_id,
        number=_next_bill_number(session, user.tenant_id, prefix),
        vendor_id=body.vendor_id,
        vendor_name=vname,
        bill_date=body.bill_date,
        due_date=body.due_date,
        description=body.description,
        subtotal=subtotal,
        gst_rate=D(body.gst_rate),
        gst_amount=gst_amount,
        total=total,
        currency=doc_currency,
        exchange_rate=fx_rate,
        status="draft",
        ap_account_id=body.ap_account_id,
        expense_account_id=body.expense_account_id,
    )
    session.add(bill)
    session.flush()

    total_stock_value = ZERO
    for line_data in body.lines:
        line_qty = D(line_data.qty)
        line_rate = D(line_data.rate)
        amount = money(line_qty * line_rate)
        session.add(
            BillLine(
                bill_id=bill.id,
                product_id=line_data.product_id,
                description=line_data.description,
                qty=line_qty,
                unit=line_data.unit,
                rate=line_rate,
                amount=amount,
            )
        )
        if line_data.product_id:
            prod = session.exec(
                select(Product).where(
                    Product.id == line_data.product_id,
                    Product.tenant_id == user.tenant_id,
                )
            ).first()
            if prod and prod.product_type == "stock":
                record_purchase(
                    session,
                    tenant_id=user.tenant_id,
                    product_id=prod.id,
                    qty=line_qty,
                    unit_cost=line_rate,
                    source_doc=bill.number,
                )
                total_stock_value += amount

    ap_acc = (
        session.get(Account, body.ap_account_id)
        if body.ap_account_id
        else get_or_create_account(session, user.tenant_id, "2000", "Accounts Payable", "Liability")
    )
    # Convert document amounts → base currency for GL posting.
    total_base = money(total * fx_rate)
    total_stock_base = money(total_stock_value * fx_rate)
    gst_base = money(gst_amount * fx_rate)
    non_stock_base = money((subtotal - total_stock_value) * fx_rate)

    entries: list[EntryInput] = [EntryInput(account_id=ap_acc.id, credit=total_base)]
    if total_stock_value > 0:
        inv_acc = get_or_create_account(
            session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset"
        )
        entries.append(EntryInput(account_id=inv_acc.id, debit=total_stock_base))
    if non_stock_base > 0:
        exp_acc = (
            session.get(Account, body.expense_account_id)
            if body.expense_account_id
            else get_or_create_account(
                session, user.tenant_id, "5000", "General Expenses", "Expense"
            )
        )
        entries.append(EntryInput(account_id=exp_acc.id, debit=non_stock_base))
    if gst_amount > 0:
        gst_input_acc = get_or_create_account(
            session, user.tenant_id, "1250", "GST Receivable (Input)", "Asset"
        )
        entries.append(EntryInput(account_id=gst_input_acc.id, debit=gst_base))

    txn = post_transaction(
        session, user,
        date=bill.bill_date,
        description=f"Bill {bill.number} — {vname or ''}",
        entries=entries,
        audit_entity_type="bill",
        audit_detail={"bill_number": bill.number, "total": str(total)},
    )
    bill.transaction_id = txn.id
    session.add(bill)
    log_audit(
        session, user, "CREATE", "bill", bill.id,
        {"number": bill.number, "total": str(total)},
    )
    session.commit()
    session.refresh(bill)

    lines_out = session.exec(select(BillLine).where(BillLine.bill_id == bill.id)).all()
    result = bill.model_dump()
    result["lines"] = [l.model_dump() for l in lines_out]
    return result


@router.patch("/api/bills/{bill_id}/status")
def update_bill_status(
    session: SessionDep, user: WriteUserDep, bill_id: int, status: str
):
    b = session.exec(
        select(Bill).where(Bill.id == bill_id, Bill.tenant_id == user.tenant_id)
    ).first()
    if not b:
        raise HTTPException(404, "Bill not found")
    b.status = status
    session.add(b)
    log_audit(
        session, user, "UPDATE", "bill", b.id,
        {"number": b.number, "status": status},
    )
    session.commit()
    session.refresh(b)
    return b
