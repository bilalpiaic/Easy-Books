"""Bill CRUD + auto-posting."""
from datetime import date as DateType, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, asc, desc, func, select

from models import Account, Bill, BillLine, JournalEntry, PaymentTerm, Product, Settings, TaxCode, Tenant, Transaction, Vendor
from services.fx import rate_to_base
from services.inventory import record_purchase
from services.money import D, ONE, ZERO, money, sum_money
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, get_default_account, get_or_create_account, log_audit, mark_onboarding_step, next_number

router = APIRouter(tags=["bills"])


class BillLineCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")
    tax_code_id: Optional[int] = None


class BillCreate(BaseModel):
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    bill_date: str
    due_date: str = ""
    payment_term_id: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    internal_memo: Optional[str] = None
    lines: List[BillLineCreate] = []
    gst_rate: Decimal = Decimal("17")
    ap_account_id: Optional[int] = None
    expense_account_id: Optional[int] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None


def _next_bill_number(session: Session, tenant_id: int, prefix: str, fmt: Optional[str] = None) -> str:
    """Atomic per-tenant bill number via SequenceCounter."""
    return next_number(session, tenant_id, "bill", prefix, fmt=fmt)


def _auto_overdue(session: Session, bills: list) -> None:
    """Mark past-due unpaid bills as overdue in-place and persist."""
    today = DateType.today()
    changed = []
    for bill in bills:
        if bill.status not in ("paid", "partial", "overdue") and bill.due_date:
            due = DateType.fromisoformat(str(bill.due_date)) if isinstance(bill.due_date, str) else bill.due_date
            if due < today:
                bill.status = "overdue"
                changed.append(bill)
    if changed:
        for bill in changed:
            session.add(bill)
        session.commit()


_SORTABLE = {
    "number":      Bill.number,
    "vendor_name": Bill.vendor_name,
    "bill_date":   Bill.bill_date,
    "due_date":    Bill.due_date,
    "total":       Bill.total,
    "status":      Bill.status,
}


@router.get("/api/bills")
def list_bills(
    session: SessionDep, user: CurrentUserDep,
    search: str = "", skip: int = 0, limit: int = 50, status: str = "",
    sort_by: str = "bill_date", sort_dir: str = "desc",
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    vendor_id: Optional[int] = None,
):
    q = select(Bill).where(Bill.tenant_id == user.tenant_id)
    if search:
        q = q.where((Bill.number.ilike(f"%{search}%")) | (Bill.vendor_name.ilike(f"%{search}%")))
    if status:
        q = q.where(Bill.status == status)
    if date_from:
        q = q.where(Bill.bill_date >= date_from)
    if date_to:
        q = q.where(Bill.bill_date <= date_to)
    if vendor_id:
        q = q.where(Bill.vendor_id == vendor_id)

    col = _SORTABLE.get(sort_by, Bill.bill_date)
    q = q.order_by(asc(col) if sort_dir == "asc" else desc(col))

    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset(skip).limit(limit)).all()
    _auto_overdue(session, list(items))
    result_items = []
    for bill in items:
        d = bill.model_dump()
        d["lines"] = [
            l.model_dump()
            for l in session.exec(
                select(BillLine).where(BillLine.bill_id == bill.id)
            ).all()
        ]
        result_items.append(d)
    return {"total": total, "items": result_items}


@router.get("/api/bills/{bill_id}")
def get_bill(session: SessionDep, user: CurrentUserDep, bill_id: int):
    """Single bill with its lines + vendor info."""
    bill = session.exec(
        select(Bill).where(Bill.id == bill_id, Bill.tenant_id == user.tenant_id)
    ).first()
    if not bill:
        raise HTTPException(404, "Bill not found")
    _auto_overdue(session, [bill])
    session.refresh(bill)
    lines = session.exec(
        select(BillLine).where(BillLine.bill_id == bill.id).order_by(BillLine.id)
    ).all()
    product_ids = [ln.product_id for ln in lines if ln.product_id]
    hs_map: dict[int, str | None] = {}
    if product_ids:
        prods = session.exec(select(Product).where(Product.id.in_(product_ids))).all()
        hs_map = {p.id: p.hs_code for p in prods}
    enriched_lines = [{**ln.model_dump(), "hs_code": hs_map.get(ln.product_id)} for ln in lines]
    return {**bill.model_dump(), "lines": enriched_lines}


@router.post("/api/bills", status_code=201)
def create_bill(session: SessionDep, user: WriteUserDep, body: BillCreate):
    prefix_row = session.exec(
        select(Settings).where(
            Settings.tenant_id == user.tenant_id, Settings.key == "bill_prefix"
        )
    ).first()
    prefix = prefix_row.value if prefix_row else "BILL"
    fmt_row = session.exec(
        select(Settings).where(
            Settings.tenant_id == user.tenant_id, Settings.key == "bill_number_format"
        )
    ).first()
    bill_fmt = fmt_row.value if fmt_row else None

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
    term_id = body.payment_term_id
    if body.vendor_id:
        v = session.exec(
            select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)
        ).first()
        if not v:
            raise HTTPException(404, "Vendor not found")
        vname = v.name
        if not term_id and v.payment_term_id:
            term_id = v.payment_term_id

    due_date = body.due_date
    if term_id:
        term = session.exec(
            select(PaymentTerm).where(
                PaymentTerm.id == term_id, PaymentTerm.tenant_id == user.tenant_id
            )
        ).first()
        if term and not due_date:
            bill_dt = DateType.fromisoformat(body.bill_date)
            due_date = str(bill_dt + timedelta(days=term.days))
    if not due_date:
        due_date = body.bill_date

    bill = Bill(
        tenant_id=user.tenant_id,
        number=_next_bill_number(session, user.tenant_id, prefix, bill_fmt),
        vendor_id=body.vendor_id,
        vendor_name=vname,
        bill_date=body.bill_date,
        due_date=due_date,
        payment_term_id=term_id,
        description=body.description,
        notes=body.notes,
        internal_memo=body.internal_memo,
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
    per_gl_tax: dict[int, Decimal] = {}  # gl_account_id → total_tax for per-line mode
    for line_data in body.lines:
        line_qty = D(line_data.qty)
        line_rate = D(line_data.rate)
        amount = money(line_qty * line_rate)
        line_tax_code_id = line_data.tax_code_id
        if line_tax_code_id:
            tc = session.exec(
                select(TaxCode).where(
                    TaxCode.id == line_tax_code_id,
                    TaxCode.tenant_id == user.tenant_id,
                )
            ).first()
            if tc:
                line_tax = money(amount * tc.rate / D("100"))
                per_gl_tax[tc.gl_account_id] = per_gl_tax.get(tc.gl_account_id, ZERO) + line_tax
        session.add(
            BillLine(
                bill_id=bill.id,
                product_id=line_data.product_id,
                description=line_data.description,
                qty=line_qty,
                unit=line_data.unit,
                rate=line_rate,
                amount=amount,
                tax_code_id=line_tax_code_id,
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

    use_per_line_tax = bool(per_gl_tax)
    if use_per_line_tax:
        gst_amount = sum_money(per_gl_tax.values())
        total = money(subtotal + gst_amount)
        bill.gst_amount = gst_amount
        bill.total = total
        session.add(bill)

    ap_acc = (
        session.get(Account, body.ap_account_id)
        if body.ap_account_id
        else get_default_account(session, user.tenant_id, "default_ap_account", "2000", "Accounts Payable", "Liability")
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
            else get_default_account(session, user.tenant_id, "default_cogs_account", "5000", "General Expenses", "Expense")
        )
        entries.append(EntryInput(account_id=exp_acc.id, debit=non_stock_base))
    if use_per_line_tax and per_gl_tax:
        # Post per-line input tax to each distinct GL account.
        for gl_id, tax_amt in per_gl_tax.items():
            entries.append(EntryInput(account_id=gl_id, debit=money(tax_amt * fx_rate)))
    elif gst_amount > 0:
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
        voucher_type="PR",
    )
    bill.transaction_id = txn.id
    session.add(bill)
    log_audit(
        session, user, "CREATE", "bill", bill.id,
        {"number": bill.number, "total": str(total)},
    )
    mark_onboarding_step(session, user.tenant_id, "first_bill")
    session.commit()
    session.refresh(bill)

    lines_out = session.exec(select(BillLine).where(BillLine.bill_id == bill.id)).all()
    result = bill.model_dump()
    result["lines"] = [l.model_dump() for l in lines_out]
    return result


@router.put("/api/bills/{bill_id}")
def update_bill(session: SessionDep, user: WriteUserDep, bill_id: int, body: BillCreate):
    """Edit a draft or posted (unpaid, open-period) bill.

    Raises 400 if the bill has a payment allocated, its date is in a locked
    period, or it has already been reversed.
    """
    bill = session.exec(
        select(Bill).where(Bill.id == bill_id, Bill.tenant_id == user.tenant_id)
    ).first()
    if not bill:
        raise HTTPException(404, "Bill not found")
    from routers._edit_guards import assert_doc_editable
    assert_doc_editable(session, tenant_id=user.tenant_id, doc=bill, kind="bill")

    # Snapshot prior header + totals for audit diff (before any mutations).
    # Normalize monetary values via money() so before/after use the same format.
    _snap_bill = {
        "vendor_name": bill.vendor_name,
        "bill_date": str(bill.bill_date) if bill.bill_date else None,
        "due_date": str(bill.due_date) if bill.due_date else None,
        "subtotal": str(money(bill.subtotal)),
        "gst_amount": str(money(bill.gst_amount)),
        "total": str(money(bill.total)),
        "currency": bill.currency,
        "line_count": len(session.exec(
            select(BillLine).where(BillLine.bill_id == bill.id)
        ).all()),
    }

    vname = body.vendor_name
    term_id = body.payment_term_id
    if body.vendor_id:
        v = session.exec(
            select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)
        ).first()
        if not v:
            raise HTTPException(404, "Vendor not found")
        vname = v.name
        if not term_id and v.payment_term_id:
            term_id = v.payment_term_id

    due_date = body.due_date
    if term_id:
        term = session.exec(
            select(PaymentTerm).where(
                PaymentTerm.id == term_id, PaymentTerm.tenant_id == user.tenant_id
            )
        ).first()
        if term and not due_date:
            bill_dt = DateType.fromisoformat(body.bill_date)
            due_date = str(bill_dt + timedelta(days=term.days))
    if not due_date:
        due_date = body.bill_date

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

    # Reverse existing GL JV if present
    if bill.transaction_id:
        old_txn = session.get(Transaction, bill.transaction_id)
        if old_txn and not old_txn.is_reversed:
            old_entries = session.exec(
                select(JournalEntry).where(JournalEntry.transaction_id == old_txn.id)
            ).all()
            rev_txn = post_transaction(
                session, user,
                date=str(DateType.today()),
                description=f"Reversal of {old_txn.jv_number} (bill edit)",
                entries=[
                    EntryInput(account_id=je.account_id, debit=D(je.credit), credit=D(je.debit))
                    for je in old_entries
                ],
                audit_entity_type="bill",
                audit_detail={"bill_number": bill.number, "action": "edit_reversal"},
                voucher_type=old_txn.voucher_type,
            )
            old_txn.is_reversed = True
            old_txn.reversed_by_id = rev_txn.id
            session.add(old_txn)
        bill.transaction_id = None

    # Restore stock received by the original posting before re-applying lines.
    # Bills receive stock via record_purchase keyed on bill.number.
    # reverse_purchase removes layers by source_doc=bill.number and restores qty.
    from services.inventory import reverse_purchase
    reverse_purchase(session, tenant_id=user.tenant_id, source_doc=bill.number)

    # Delete existing lines
    for ln in session.exec(select(BillLine).where(BillLine.bill_id == bill.id)).all():
        session.delete(ln)
    session.flush()

    # Update bill fields
    bill.vendor_id = body.vendor_id
    bill.vendor_name = vname
    bill.bill_date = body.bill_date
    bill.due_date = due_date
    bill.payment_term_id = term_id
    bill.description = body.description
    bill.notes = body.notes
    bill.internal_memo = body.internal_memo
    bill.subtotal = subtotal
    bill.gst_rate = D(body.gst_rate)
    bill.gst_amount = gst_amount
    bill.total = total
    bill.currency = doc_currency
    bill.exchange_rate = fx_rate
    bill.ap_account_id = body.ap_account_id
    bill.expense_account_id = body.expense_account_id
    session.add(bill)
    session.flush()

    # Insert new lines
    total_stock_value = ZERO
    for line_data in body.lines:
        line_qty = D(line_data.qty)
        line_rate = D(line_data.rate)
        amount = money(line_qty * line_rate)
        session.add(BillLine(
            bill_id=bill.id,
            product_id=line_data.product_id,
            description=line_data.description,
            qty=line_qty,
            unit=line_data.unit,
            rate=line_rate,
            amount=amount,
        ))
        if line_data.product_id:
            prod = session.exec(
                select(Product).where(
                    Product.id == line_data.product_id,
                    Product.tenant_id == user.tenant_id,
                )
            ).first()
            if prod and prod.product_type == "stock":
                record_purchase(
                    session, tenant_id=user.tenant_id,
                    product_id=prod.id, qty=line_qty, unit_cost=line_rate, source_doc=bill.number,
                )
                total_stock_value += amount

    # Re-post GL
    ap_acc = (
        session.get(Account, body.ap_account_id)
        if body.ap_account_id
        else get_default_account(session, user.tenant_id, "default_ap_account", "2000", "Accounts Payable", "Liability")
    )
    total_base = money(total * fx_rate)
    total_stock_base = money(total_stock_value * fx_rate)
    gst_base = money(gst_amount * fx_rate)
    non_stock_base = money((subtotal - total_stock_value) * fx_rate)

    entries: list[EntryInput] = [EntryInput(account_id=ap_acc.id, credit=total_base)]
    if total_stock_value > 0:
        inv_acc = get_or_create_account(session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset")
        entries.append(EntryInput(account_id=inv_acc.id, debit=total_stock_base))
    if non_stock_base > 0:
        exp_acc = (
            session.get(Account, body.expense_account_id)
            if body.expense_account_id
            else get_or_create_account(session, user.tenant_id, "5000", "General Expenses", "Expense")
        )
        entries.append(EntryInput(account_id=exp_acc.id, debit=non_stock_base))
    if gst_amount > 0:
        gst_input_acc = get_or_create_account(session, user.tenant_id, "1250", "GST Receivable (Input)", "Asset")
        entries.append(EntryInput(account_id=gst_input_acc.id, debit=gst_base))

    txn = post_transaction(
        session, user,
        date=bill.bill_date,
        description=f"Bill {bill.number} — {vname or ''} (edited)",
        entries=entries,
        audit_entity_type="bill",
        audit_detail={"bill_number": bill.number, "total": str(total)},
        voucher_type="PR",
    )
    bill.transaction_id = txn.id
    session.add(bill)

    # Compute after-snapshot for diff (bill fields updated above via session.add/flush).
    _snap_bill_after = {
        "vendor_name": bill.vendor_name,
        "bill_date": str(bill.bill_date) if bill.bill_date else None,
        "due_date": str(bill.due_date) if bill.due_date else None,
        "subtotal": str(subtotal),
        "gst_amount": str(gst_amount),
        "total": str(total),
        "currency": doc_currency,
        "line_count": len(body.lines),
    }
    _changes = {
        field: {"before": _snap_bill[field], "after": _snap_bill_after[field]}
        for field in _snap_bill
        if str(_snap_bill[field]) != str(_snap_bill_after[field])
    }
    log_audit(session, user, "UPDATE", "bill", bill.id, {"number": bill.number, "total": str(total), "changes": _changes})
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


# ── Bulk actions ─────────────────────────────────────────────────────────────

from typing import Literal  # noqa: E402

class BulkBillAction(BaseModel):
    ids: list[int]
    action: Literal["mark_received", "void", "delete"]


@router.post("/api/bills/bulk")
def bulk_bill_action(session: SessionDep, user: WriteUserDep, body: BulkBillAction):
    """Bulk mark_received / void / delete on a list of bill IDs (tenant-scoped)."""
    bills = session.exec(
        select(Bill).where(
            Bill.id.in_(body.ids),
            Bill.tenant_id == user.tenant_id,
        )
    ).all()

    affected = 0
    errors: list[str] = []

    for bill in bills:
        if body.action == "mark_received":
            if bill.status not in ("draft", "received"):
                errors.append(f"Bill {bill.number}: cannot mark_received (status={bill.status})")
                continue
            bill.status = "received"
            session.add(bill)
            log_audit(session, user, "UPDATE", "bill", bill.id, {"number": bill.number, "status": "received"})
            affected += 1

        elif body.action == "void":
            if bill.status in ("paid",):
                errors.append(f"Bill {bill.number}: cannot void a paid bill")
                continue
            bill.status = "void"
            session.add(bill)
            log_audit(session, user, "UPDATE", "bill", bill.id, {"number": bill.number, "status": "void"})
            affected += 1

        elif body.action == "delete":
            if bill.status != "draft":
                errors.append(f"Bill {bill.number}: only draft bills can be deleted (status={bill.status})")
                continue
            lines = session.exec(select(BillLine).where(BillLine.bill_id == bill.id)).all()
            for ln in lines:
                session.delete(ln)
            session.delete(bill)
            log_audit(session, user, "DELETE", "bill", bill.id, {"number": bill.number})
            affected += 1

    session.commit()
    return {"affected": affected, "errors": errors}
