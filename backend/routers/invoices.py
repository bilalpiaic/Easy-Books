"""Invoice CRUD + auto-posting + aging."""
from datetime import date as DateType
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session, asc, desc, func, select

from datetime import timedelta

from models import Account, Customer, Invoice, InvoiceLine, JournalEntry, PaymentTerm, Product, Settings, TaxCode, Tenant, Transaction
from services.fx import rate_to_base
from services.inventory import consume_stock
from services.money import D, ONE, ZERO, money, sum_money
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, get_default_account, get_or_create_account, log_audit, mark_onboarding_step, next_number

router = APIRouter(tags=["invoices"])


# ── DTOs ──────────────────────────────────────────────────────────────────────


class InvoiceLineCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")
    tax_code_id: Optional[int] = None


class InvoiceCreate(BaseModel):
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    issue_date: str
    due_date: str = ""
    payment_term_id: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    internal_memo: Optional[str] = None
    lines: List[InvoiceLineCreate] = []
    gst_rate: Decimal = Decimal("17")
    ar_account_id: Optional[int] = None
    revenue_account_id: Optional[int] = None
    currency: Optional[str] = None       # defaults to tenant base
    exchange_rate: Optional[Decimal] = None  # override; else resolved from ExchangeRate


def _next_invoice_number(session: Session, tenant_id: int, prefix: str, fmt: Optional[str] = None) -> str:
    """Atomic per-tenant invoice number via SequenceCounter."""
    return next_number(session, tenant_id, "invoice", prefix, fmt=fmt)


def _auto_overdue(session: Session, invoices: list) -> None:
    """Mark past-due unpaid invoices as overdue in-place and persist."""
    today = DateType.today()
    changed = []
    for inv in invoices:
        if inv.status not in ("paid", "partial", "overdue") and inv.due_date:
            due = DateType.fromisoformat(str(inv.due_date)) if isinstance(inv.due_date, str) else inv.due_date
            if due < today:
                inv.status = "overdue"
                changed.append(inv)
    if changed:
        for inv in changed:
            session.add(inv)
        session.commit()


_SORTABLE = {
    "number":        Invoice.number,
    "customer_name": Invoice.customer_name,
    "issue_date":    Invoice.issue_date,
    "due_date":      Invoice.due_date,
    "total":         Invoice.total,
    "status":        Invoice.status,
}


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/api/invoices")
def list_invoices(
    session: SessionDep, user: CurrentUserDep,
    search: str = "", skip: int = 0, limit: int = 50, status: str = "",
    sort_by: str = "issue_date", sort_dir: str = "desc",
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    customer_id: Optional[int] = None,
):
    q = select(Invoice).where(Invoice.tenant_id == user.tenant_id)
    if search:
        q = q.where(
            (Invoice.number.ilike(f"%{search}%"))
            | (Invoice.customer_name.ilike(f"%{search}%"))
        )
    if status:
        q = q.where(Invoice.status == status)
    if date_from:
        q = q.where(Invoice.issue_date >= date_from)
    if date_to:
        q = q.where(Invoice.issue_date <= date_to)
    if customer_id:
        q = q.where(Invoice.customer_id == customer_id)

    col = _SORTABLE.get(sort_by, Invoice.issue_date)
    q = q.order_by(asc(col) if sort_dir == "asc" else desc(col))

    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset(skip).limit(limit)).all()
    _auto_overdue(session, list(items))
    result_items = []
    for inv in items:
        d = inv.model_dump()
        d["lines"] = [
            l.model_dump()
            for l in session.exec(
                select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)
            ).all()
        ]
        result_items.append(d)
    return {"total": total, "items": result_items}


@router.get("/api/invoices/{invoice_id}")
def get_invoice(session: SessionDep, user: CurrentUserDep, invoice_id: int):
    """Single invoice with its lines + customer name."""
    inv = session.exec(
        select(Invoice).where(
            Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id
        )
    ).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    _auto_overdue(session, [inv])
    session.refresh(inv)
    lines = session.exec(
        select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.id)
    ).all()
    return {**inv.model_dump(), "lines": [ln.model_dump() for ln in lines]}


@router.post("/api/invoices", status_code=201)
def create_invoice(session: SessionDep, user: WriteUserDep, body: InvoiceCreate):
    prefix_row = session.exec(
        select(Settings).where(
            Settings.tenant_id == user.tenant_id, Settings.key == "invoice_prefix"
        )
    ).first()
    prefix = prefix_row.value if prefix_row else "INV"
    fmt_row = session.exec(
        select(Settings).where(
            Settings.tenant_id == user.tenant_id, Settings.key == "invoice_number_format"
        )
    ).first()
    inv_fmt = fmt_row.value if fmt_row else None

    subtotal = money(sum_money(D(l.qty) * D(l.rate) for l in body.lines))
    gst_amount = money(subtotal * D(body.gst_rate) / D("100"))
    total = money(subtotal + gst_amount)

    # FX resolution: doc currency defaults to tenant base. Rate defaults to
    # 1.0 when doc==base, otherwise to the latest known rate on/before
    # issue_date. Caller can override with an explicit exchange_rate.
    tenant = session.get(Tenant, user.tenant_id)
    base_currency = tenant.base_currency if tenant else "USD"
    doc_currency = body.currency or base_currency
    if body.exchange_rate is not None:
        fx_rate = D(body.exchange_rate)
    elif doc_currency == base_currency:
        fx_rate = ONE
    else:
        try:
            fx_rate = rate_to_base(session, user.tenant_id, doc_currency, body.issue_date)
        except LookupError as e:
            raise HTTPException(400, str(e))

    cname = body.customer_name
    term_id = body.payment_term_id
    if body.customer_id:
        c = session.exec(
            select(Customer).where(
                Customer.id == body.customer_id, Customer.tenant_id == user.tenant_id
            )
        ).first()
        if not c:
            raise HTTPException(404, "Customer not found")
        cname = c.name
        if not term_id and c.payment_term_id:
            term_id = c.payment_term_id

    # Auto-compute due_date from payment term when not explicitly provided
    due_date = body.due_date
    if term_id:
        term = session.exec(
            select(PaymentTerm).where(
                PaymentTerm.id == term_id, PaymentTerm.tenant_id == user.tenant_id
            )
        ).first()
        if term and not due_date:
            issue = DateType.fromisoformat(body.issue_date)
            due_date = str(issue + timedelta(days=term.days))
    if not due_date:
        due_date = body.issue_date  # fallback: same day

    invoice = Invoice(
        tenant_id=user.tenant_id,
        number=_next_invoice_number(session, user.tenant_id, prefix, inv_fmt),
        customer_id=body.customer_id,
        customer_name=cname,
        issue_date=body.issue_date,
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
        ar_account_id=body.ar_account_id,
        revenue_account_id=body.revenue_account_id,
    )
    session.add(invoice)
    session.flush()

    # Persist line items; for stock lines, relieve inventory at WAvg cost and
    # accumulate total COGS so we can post one Dr COGS / Cr Inventory JV.
    # For lines with tax_code_id, accumulate per-GL tax amounts.
    total_cogs = ZERO
    per_gl_tax: dict[int, Decimal] = {}  # gl_account_id → total_tax for per-line mode
    for line_data in body.lines:
        amount = money(D(line_data.qty) * D(line_data.rate))
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
            InvoiceLine(
                invoice_id=invoice.id,
                product_id=line_data.product_id,
                description=line_data.description,
                qty=D(line_data.qty),
                unit=line_data.unit,
                rate=D(line_data.rate),
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
                total_cogs += consume_stock(
                    session,
                    tenant_id=user.tenant_id,
                    product_id=prod.id,
                    qty=D(line_data.qty),
                )

    # If per-line taxes were collected, override the header gst_amount.
    use_per_line_tax = bool(per_gl_tax)
    if use_per_line_tax:
        gst_amount = sum_money(per_gl_tax.values())
        total = money(subtotal + gst_amount)
        invoice.gst_amount = gst_amount
        invoice.total = total
        session.add(invoice)

    ar_acc = (
        session.get(Account, body.ar_account_id)
        if body.ar_account_id
        else get_default_account(session, user.tenant_id, "default_ar_account", "1100", "Accounts Receivable", "Asset")
    )
    rev_acc = (
        session.get(Account, body.revenue_account_id)
        if body.revenue_account_id
        else get_default_account(session, user.tenant_id, "default_revenue_account", "4000", "Sales Revenue", "Revenue")
    )

    # Convert document amounts → base currency for GL posting.
    total_base = money(total * fx_rate)
    subtotal_base = money(subtotal * fx_rate)
    gst_base = money(gst_amount * fx_rate)

    entries = [EntryInput(account_id=ar_acc.id, debit=total_base)]
    if use_per_line_tax and per_gl_tax:
        # Post each distinct tax GL account separately.
        entries.append(EntryInput(account_id=rev_acc.id, credit=subtotal_base))
        for gl_id, tax_amt in per_gl_tax.items():
            entries.append(EntryInput(account_id=gl_id, credit=money(tax_amt * fx_rate)))
    elif gst_amount > 0:
        gst_acc = get_or_create_account(
            session, user.tenant_id, "2200", "GST Payable (Output)", "Liability"
        )
        entries.append(EntryInput(account_id=rev_acc.id, credit=subtotal_base))
        entries.append(EntryInput(account_id=gst_acc.id, credit=gst_base))
    else:
        entries.append(EntryInput(account_id=rev_acc.id, credit=total_base))

    txn = post_transaction(
        session, user,
        date=invoice.issue_date,
        description=f"Invoice {invoice.number} — {cname or ''}",
        entries=entries,
        audit_entity_type="invoice",
        audit_detail={"invoice_number": invoice.number, "total": str(total)},
    )
    invoice.transaction_id = txn.id
    session.add(invoice)

    # Separate JV for COGS so the sale and cost-relief are individually
    # inspectable and a reversal of one doesn't unintentionally undo the other.
    if total_cogs > 0:
        cogs_acc = get_or_create_account(
            session, user.tenant_id, "5010", "Cost of Goods Sold", "Expense"
        )
        inv_acc = get_or_create_account(
            session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset"
        )
        post_transaction(
            session, user,
            date=invoice.issue_date,
            description=f"COGS for {invoice.number}",
            entries=[
                EntryInput(account_id=cogs_acc.id, debit=total_cogs),
                EntryInput(account_id=inv_acc.id, credit=total_cogs),
            ],
            audit_entity_type="invoice",
            audit_detail={"invoice_number": invoice.number, "cogs": str(total_cogs)},
        )

    log_audit(
        session, user, "CREATE", "invoice", invoice.id,
        {"number": invoice.number, "total": str(total)},
    )
    mark_onboarding_step(session, user.tenant_id, "first_invoice")
    session.commit()
    session.refresh(invoice)

    lines_out = session.exec(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
    ).all()
    result = invoice.model_dump()
    result["lines"] = [l.model_dump() for l in lines_out]
    return result


@router.put("/api/invoices/{invoice_id}")
def update_invoice(session: SessionDep, user: WriteUserDep, invoice_id: int, body: InvoiceCreate):
    """Edit a draft invoice. Raises 403 if the invoice has already been posted."""
    inv = session.exec(
        select(Invoice).where(
            Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id
        )
    ).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.status != "draft":
        raise HTTPException(403, f"Cannot edit invoice with status '{inv.status}'. Only draft invoices can be edited.")

    # Resolve customer name and default payment term
    cname = body.customer_name
    term_id = body.payment_term_id
    if body.customer_id:
        c = session.exec(
            select(Customer).where(
                Customer.id == body.customer_id, Customer.tenant_id == user.tenant_id
            )
        ).first()
        if not c:
            raise HTTPException(404, "Customer not found")
        cname = c.name
        if not term_id and c.payment_term_id:
            term_id = c.payment_term_id

    # Auto-compute due_date from payment term when not explicitly provided
    due_date = body.due_date
    if term_id:
        term = session.exec(
            select(PaymentTerm).where(
                PaymentTerm.id == term_id, PaymentTerm.tenant_id == user.tenant_id
            )
        ).first()
        if term and not due_date:
            issue = DateType.fromisoformat(body.issue_date)
            due_date = str(issue + timedelta(days=term.days))
    if not due_date:
        due_date = body.issue_date

    # Recalculate totals
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
            fx_rate = rate_to_base(session, user.tenant_id, doc_currency, body.issue_date)
        except LookupError as e:
            raise HTTPException(400, str(e))

    # If the draft was already GL-posted, reverse the old JV before re-posting.
    if inv.transaction_id:
        old_txn = session.get(Transaction, inv.transaction_id)
        if old_txn and not old_txn.is_reversed:
            old_entries = session.exec(
                select(JournalEntry).where(JournalEntry.transaction_id == old_txn.id)
            ).all()
            rev_txn = post_transaction(
                session, user,
                date=str(DateType.today()),
                description=f"Reversal of {old_txn.jv_number} (invoice edit)",
                entries=[
                    EntryInput(account_id=je.account_id, debit=D(je.credit), credit=D(je.debit))
                    for je in old_entries
                ],
                audit_entity_type="invoice",
                audit_detail={"invoice_number": inv.number, "action": "edit_reversal"},
            )
            old_txn.is_reversed = True
            old_txn.reversed_by_id = rev_txn.id
            session.add(old_txn)
        inv.transaction_id = None

    # Delete existing lines
    existing_lines = session.exec(
        select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)
    ).all()
    for ln in existing_lines:
        session.delete(ln)
    session.flush()

    # Update invoice fields
    inv.customer_id = body.customer_id
    inv.customer_name = cname
    inv.issue_date = body.issue_date
    inv.due_date = due_date
    inv.payment_term_id = term_id
    inv.description = body.description
    inv.notes = body.notes
    inv.internal_memo = body.internal_memo
    inv.subtotal = subtotal
    inv.gst_rate = D(body.gst_rate)
    inv.gst_amount = gst_amount
    inv.total = total
    inv.currency = doc_currency
    inv.exchange_rate = fx_rate
    inv.ar_account_id = body.ar_account_id
    inv.revenue_account_id = body.revenue_account_id
    session.add(inv)
    session.flush()

    # Insert new lines
    total_cogs = ZERO
    for line_data in body.lines:
        amount = money(D(line_data.qty) * D(line_data.rate))
        session.add(InvoiceLine(
            invoice_id=inv.id,
            product_id=line_data.product_id,
            description=line_data.description,
            qty=D(line_data.qty),
            unit=line_data.unit,
            rate=D(line_data.rate),
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
                total_cogs += consume_stock(
                    session, tenant_id=user.tenant_id,
                    product_id=prod.id, qty=D(line_data.qty),
                )

    # Re-post GL entries
    ar_acc = (
        session.get(Account, body.ar_account_id)
        if body.ar_account_id
        else get_default_account(session, user.tenant_id, "default_ar_account", "1100", "Accounts Receivable", "Asset")
    )
    rev_acc = (
        session.get(Account, body.revenue_account_id)
        if body.revenue_account_id
        else get_default_account(session, user.tenant_id, "default_revenue_account", "4000", "Sales Revenue", "Revenue")
    )
    total_base = money(total * fx_rate)
    subtotal_base = money(subtotal * fx_rate)
    gst_base = money(gst_amount * fx_rate)

    entries = [EntryInput(account_id=ar_acc.id, debit=total_base)]
    if gst_amount > 0:
        gst_acc = get_or_create_account(
            session, user.tenant_id, "2200", "GST Payable (Output)", "Liability"
        )
        entries.append(EntryInput(account_id=rev_acc.id, credit=subtotal_base))
        entries.append(EntryInput(account_id=gst_acc.id, credit=gst_base))
    else:
        entries.append(EntryInput(account_id=rev_acc.id, credit=total_base))

    txn = post_transaction(
        session, user,
        date=inv.issue_date,
        description=f"Invoice {inv.number} — {cname or ''} (edited)",
        entries=entries,
        audit_entity_type="invoice",
        audit_detail={"invoice_number": inv.number, "total": str(total)},
    )
    inv.transaction_id = txn.id
    session.add(inv)

    log_audit(
        session, user, "UPDATE", "invoice", inv.id,
        {"number": inv.number, "total": str(total)},
    )
    session.commit()
    session.refresh(inv)

    lines_out = session.exec(
        select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)
    ).all()
    result = inv.model_dump()
    result["lines"] = [l.model_dump() for l in lines_out]
    return result


@router.patch("/api/invoices/{invoice_id}/status")
def update_invoice_status(
    session: SessionDep, user: WriteUserDep, invoice_id: int, status: str
):
    inv = session.exec(
        select(Invoice).where(
            Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id
        )
    ).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.status = status
    session.add(inv)
    log_audit(
        session, user, "UPDATE", "invoice", inv.id,
        {"number": inv.number, "status": status},
    )
    session.commit()
    session.refresh(inv)

    # Send email notification when invoice is marked "sent"
    if status == "sent":
        _send_invoice_notification(session, inv)

    return inv


def _send_invoice_notification(session, inv: Invoice) -> None:
    """Email the customer a notification when an invoice is sent."""
    from services.email import send_email
    # Check email_notifications setting
    settings_rows = session.exec(
        select(Settings).where(Settings.tenant_id == inv.tenant_id)
    ).all()
    settings_map = {s.key: s.value for s in settings_rows}
    if settings_map.get("email_notifications") != "true":
        return
    if not inv.customer_id:
        return
    cust = session.get(Customer, inv.customer_id)
    if not cust or not getattr(cust, "email", None):
        return
    company = settings_map.get("company_name", "Your supplier")
    send_email(
        to=cust.email,
        subject=f"Invoice {inv.number} from {company}",
        html_body=(
            f"<p>Dear {cust.name},</p>"
            f"<p>Please find invoice <strong>{inv.number}</strong> for "
            f"{inv.currency} {float(inv.total):,.2f} due by {inv.due_date}.</p>"
            f"<p>Thank you for your business.</p>"
            f"<p><em>{company}</em></p>"
        ),
    )


# ── Bulk actions ─────────────────────────────────────────────────────────────

from typing import Literal  # noqa: E402

class BulkInvoiceAction(BaseModel):
    ids: list[int]
    action: Literal["mark_sent", "void", "delete"]


@router.post("/api/invoices/bulk")
def bulk_invoice_action(session: SessionDep, user: WriteUserDep, body: BulkInvoiceAction):
    """Bulk mark_sent / void / delete on a list of invoice IDs (tenant-scoped)."""
    invoices = session.exec(
        select(Invoice).where(
            Invoice.id.in_(body.ids),
            Invoice.tenant_id == user.tenant_id,
        )
    ).all()

    affected = 0
    errors: list[str] = []

    for inv in invoices:
        if body.action == "mark_sent":
            if inv.status not in ("draft", "sent"):
                errors.append(f"Invoice {inv.number}: cannot mark_sent (status={inv.status})")
                continue
            inv.status = "sent"
            session.add(inv)
            log_audit(session, user, "UPDATE", "invoice", inv.id, {"number": inv.number, "status": "sent"})
            affected += 1

        elif body.action == "void":
            if inv.status in ("paid",):
                errors.append(f"Invoice {inv.number}: cannot void a paid invoice")
                continue
            inv.status = "void"
            session.add(inv)
            log_audit(session, user, "UPDATE", "invoice", inv.id, {"number": inv.number, "status": "void"})
            affected += 1

        elif body.action == "delete":
            if inv.status != "draft":
                errors.append(f"Invoice {inv.number}: only draft invoices can be deleted (status={inv.status})")
                continue
            lines = session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)).all()
            for ln in lines:
                session.delete(ln)
            session.delete(inv)
            log_audit(session, user, "DELETE", "invoice", inv.id, {"number": inv.number})
            affected += 1

    session.commit()
    return {"affected": affected, "errors": errors}


@router.post("/api/invoices/{invoice_id}/payment-link")
def create_payment_link(session: SessionDep, user: WriteUserDep, invoice_id: int):
    """Create a Stripe Checkout payment link for the invoice. G-12."""
    import os
    import stripe as _stripe
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        raise HTTPException(400, "Stripe not configured. Set STRIPE_SECRET_KEY.")
    _stripe.api_key = stripe_key

    inv = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.status == "paid":
        raise HTTPException(400, "Invoice is already paid")

    frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    checkout = _stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": inv.currency.lower(),
                "product_data": {"name": f"Invoice {inv.number}"},
                "unit_amount": int(D(str(inv.total)) * 100),
            },
            "quantity": 1,
        }],
        metadata={"invoice_id": str(inv.id), "tenant_id": str(inv.tenant_id)},
        success_url=f"{frontend_origin}/dashboard/invoices?paid={inv.id}",
        cancel_url=f"{frontend_origin}/dashboard/invoices",
    )
    inv.payment_link_url = checkout.url
    inv.payment_link_status = "unpaid"
    session.add(inv)
    log_audit(session, user, "UPDATE", "invoice", inv.id,
              {"action": "payment_link_created", "url": checkout.url})
    session.commit()
    return {"payment_link_url": checkout.url}


@router.get("/api/invoices/{invoice_id}/pdf")
def download_invoice_pdf(session: SessionDep, user: CurrentUserDep, invoice_id: int):
    """Generate and return a PDF for the given invoice. G-14 server-side PDF."""
    inv = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")

    lines = session.exec(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)
    ).all()

    settings_rows = session.exec(
        select(Settings).where(Settings.tenant_id == user.tenant_id)
    ).all()
    settings_map = {s.key: s.value for s in settings_rows}

    from services.pdf import render_invoice_pdf
    pdf_bytes = render_invoice_pdf(
        invoice=inv.model_dump(),
        lines=[ln.model_dump() for ln in lines],
        company_name=settings_map.get("company_name", ""),
        tagline=settings_map.get("business_tagline", ""),
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{inv.number}.pdf"'},
    )
