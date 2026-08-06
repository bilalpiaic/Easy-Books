"""Point of Sale sale completion (#304).

Reuses ``create_invoice`` + ``create_payment_received`` so tax packs, stock
consumption, and GL all stay on the standard posting path.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, select

from models import Account, Customer, Product, User
from models_pos import PosRegister, PosSale, PosShift
from services.money import D, ZERO, money


def ensure_walk_in_customer(session: Session, tenant_id: int) -> Customer:
    row = session.exec(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.name == "Walk-in Customer",
        )
    ).first()
    if row:
        return row
    row = Customer(tenant_id=tenant_id, name="Walk-in Customer", is_active=True)
    session.add(row)
    session.flush()
    return row


def expected_cash_for_shift(session: Session, shift: PosShift) -> Decimal:
    sales = session.exec(
        select(PosSale).where(
            PosSale.shift_id == shift.id,
            PosSale.tenant_id == shift.tenant_id,
            PosSale.tender == "cash",
        )
    ).all()
    cash_in = ZERO
    for s in sales:
        # Net cash in drawer = tendered - change; fall back to invoice total via payment
        if s.cash_tendered is not None:
            cash_in = money(cash_in + D(s.cash_tendered) - D(s.change_given or 0))
        else:
            from models import Invoice
            inv = session.get(Invoice, s.invoice_id)
            if inv:
                cash_in = money(cash_in + D(inv.total))
    return money(D(shift.opening_float or 0) + cash_in)


def complete_pos_sale(
    session: Session,
    user: User,
    *,
    shift_id: int,
    lines: list[dict[str, Any]],
    tender: str = "cash",
    cash_tendered: Optional[Decimal] = None,
    payment_mode: Optional[int] = None,
    customer_id: Optional[int] = None,
    buyer_ntn: Optional[str] = None,
    buyer_cnic: Optional[str] = None,
    gst_rate: Optional[Decimal] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> dict[str, Any]:
    from routers.invoices import InvoiceCreate, InvoiceLineCreate, create_invoice
    from routers.payments import PaymentReceivedCreate, create_payment_received

    shift = session.get(PosShift, shift_id)
    if not shift or shift.tenant_id != user.tenant_id:
        raise HTTPException(404, "Shift not found")
    if shift.status != "open":
        raise HTTPException(400, "Shift is closed")

    reg = session.get(PosRegister, shift.register_id)
    if not reg or reg.tenant_id != user.tenant_id or not reg.is_active:
        raise HTTPException(400, "Register is not active")

    if not lines:
        raise HTTPException(400, "Sale needs at least one line")

    cust_id = customer_id or reg.default_customer_id
    if not cust_id:
        cust_id = ensure_walk_in_customer(session, user.tenant_id).id

    inv_lines: list[InvoiceLineCreate] = []
    for raw in lines:
        pid = raw.get("product_id")
        qty = D(raw.get("qty") or 1)
        rate = D(raw.get("rate") or 0)
        desc = (raw.get("description") or "").strip()
        tax_code_id = raw.get("tax_code_id")
        unit = raw.get("unit")
        if pid:
            prod = session.get(Product, pid)
            if not prod or prod.tenant_id != user.tenant_id:
                raise HTTPException(400, f"Invalid product {pid}")
            desc = desc or prod.name
            if rate == ZERO:
                rate = D(prod.default_rate or 0)
            unit = unit or prod.unit
        if not desc:
            raise HTTPException(400, "Line needs a description or product")
        inv_lines.append(
            InvoiceLineCreate(
                product_id=pid,
                description=desc,
                qty=qty,
                unit=unit,
                rate=rate,
                discount_pct=D(raw.get("discount_pct") or 0),
                tax_code_id=tax_code_id,
                tax_inclusive=bool(raw.get("tax_inclusive")),
            )
        )

    tender_l = (tender or "cash").lower()
    if tender_l not in ("cash", "card", "bank"):
        raise HTTPException(400, "tender must be cash, card, or bank")

    # PRA payment_mode: 1=Cash 2=Card …
    if payment_mode is None:
        payment_mode = {"cash": 1, "card": 2, "bank": 2}.get(tender_l, 1)

    today = date.today().isoformat()
    rate = D(gst_rate) if gst_rate is not None else ZERO
    bg = background_tasks or BackgroundTasks()

    invoice = create_invoice(
        session,
        user,
        InvoiceCreate(
            customer_id=cust_id,
            customer_name=None,
            issue_date=today,
            due_date=today,
            description=f"POS sale — {reg.name}",
            notes=f"POS shift #{shift.id}",
            lines=inv_lines,
            gst_rate=rate,
            payment_mode=payment_mode,
            buyer_ntn=buyer_ntn,
            buyer_cnic=buyer_cnic,
        ),
        bg,
    )
    # create_invoice returns a plain dict (model_dump), not an ORM/Pydantic row
    inv_id = invoice["id"] if isinstance(invoice, dict) else invoice.id
    inv_number = invoice["number"] if isinstance(invoice, dict) else invoice.number
    inv_total = D(invoice["total"] if isinstance(invoice, dict) else invoice.total)

    cash_account_id = reg.cash_account_id
    if tender_l in ("card", "bank") and reg.bank_account_id:
        cash_account_id = reg.bank_account_id
    if not cash_account_id:
        # Fall back to Cash in Hand (create_payment_received default)
        cash_account_id = None

    payment = create_payment_received(
        session,
        user,
        PaymentReceivedCreate(
            invoice_id=inv_id,
            customer_id=cust_id,
            payment_date=today,
            amount=inv_total,
            method=tender_l,
            reference=f"POS-{shift.id}-{inv_number}",
            cash_account_id=cash_account_id,
        ),
    )
    payment_id = payment["id"] if isinstance(payment, dict) else payment.id

    change = ZERO
    tendered = cash_tendered
    if tender_l == "cash":
        if tendered is None:
            tendered = inv_total
        tendered = money(tendered)
        if tendered < inv_total:
            raise HTTPException(400, "Cash tendered is less than sale total")
        change = money(tendered - inv_total)

    sale = PosSale(
        tenant_id=user.tenant_id,
        shift_id=shift.id,
        invoice_id=inv_id,
        payment_received_id=payment_id,
        tender=tender_l,
        cash_tendered=float(tendered) if tendered is not None else None,
        change_given=float(change) if tender_l == "cash" else None,
        created_by_id=user.id,
    )
    session.add(sale)
    session.commit()
    session.refresh(sale)

    return {
        "id": sale.id,
        "shift_id": shift.id,
        "invoice_id": inv_id,
        "invoice_number": inv_number,
        "payment_received_id": payment_id,
        "total": inv_total,
        "tender": tender_l,
        "cash_tendered": sale.cash_tendered,
        "change_given": sale.change_given,
    }


def resolve_default_cash_account(session: Session, tenant_id: int) -> Optional[int]:
    row = session.exec(
        select(Account).where(
            Account.tenant_id == tenant_id,
            Account.code == "1000",
            Account.is_group == False,  # noqa: E712
        )
    ).first()
    return row.id if row else None
