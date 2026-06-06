"""Sub-ledgers — drill-down views for customers, vendors, and products.

These endpoints power the hyperlinked-reports UX. Each returns a
chronological list of "entries" with a running balance so the same
shape feeds both the customer/vendor party ledger pages and the
product stock card page.

All monetary amounts are converted to the tenant's base currency
using the snapshotted exchange_rate stored on each invoice/bill.
Qty columns surface only on stock-product lines.
"""
from __future__ import annotations

from datetime import date as DateType
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from models import (
    Bill, BillLine, BillPayment, Customer, Invoice, InvoiceLine,
    PaymentAllocation, PaymentReceived, Product, StockMovement, Vendor,
)
from services.money import D, ZERO, money

from .common import CurrentUserDep, SessionDep

router = APIRouter(tags=["sub-ledger"])


# ── Shared party-movement helpers ─────────────────────────────────────────────


def ar_party_movement(session, tenant_id: int, customer, start: Optional[str], end: Optional[str]) -> dict:
    """Return {opening, debit, credit, closing} for one customer's AR over the window.

    - opening = customer.opening_balance + Σ invoice totals before `start`
                - Σ payments applied to this customer's invoices before `start`
    - debit   = Σ invoice totals in [start, end]
    - credit  = Σ payments applied to this customer's invoices in [start, end]
    - closing = opening + debit - credit

    AR is debit-normal (Asset). A positive closing means the customer owes money.
    This is a pure computation with no HTTP side-effects.
    """
    invoices = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.customer_id == customer.id,
        ).order_by(Invoice.issue_date, Invoice.id)
    ).all()
    payments = session.exec(
        select(PaymentReceived).where(
            PaymentReceived.tenant_id == tenant_id,
        ).order_by(PaymentReceived.payment_date, PaymentReceived.id)
    ).all()
    customer_invoice_ids = {i.id for i in invoices}

    # ── Opening balance (before start) ──────────────────────────────────────
    opening = D(customer.opening_balance)
    pre_invoices = [i for i in invoices if start and i.issue_date < start]
    opening += sum(
        (_to_base(D(i.total), D(i.exchange_rate)) for i in pre_invoices),
        start=ZERO,
    )
    for p in payments:
        if not (start and p.payment_date < start):
            continue
        applied = _payment_applied_to_invoices(session, tenant_id, p, customer_invoice_ids)
        opening -= applied

    # ── Period debit (invoices in window) ────────────────────────────────────
    period_dr = ZERO
    for i in invoices:
        if not _in_range(i.issue_date, start, end):
            continue
        period_dr += _to_base(D(i.total), D(i.exchange_rate))

    # ── Period credit (payments in window) ───────────────────────────────────
    period_cr = ZERO
    for p in payments:
        if not _in_range(p.payment_date, start, end):
            continue
        period_cr += _payment_applied_to_invoices(session, tenant_id, p, customer_invoice_ids)

    closing = opening + period_dr - period_cr
    return {
        "opening": money(opening),
        "debit": money(period_dr),
        "credit": money(period_cr),
        "closing": money(closing),
    }


def ap_party_movement(session, tenant_id: int, vendor, start: Optional[str], end: Optional[str]) -> dict:
    """Return {opening, debit, credit, closing} for one vendor's AP over the window.

    AP is credit-normal (Liability): a positive closing means money owed to vendor.
    - opening = vendor.opening_balance + Σ bill totals before `start`
                - Σ payments applied to this vendor's bills before `start`
    - credit  = Σ bill totals in [start, end]   (bills increase AP liability → credit)
    - debit   = Σ payments applied to this vendor's bills in [start, end]  (payments reduce AP → debit)
    - closing = opening + credit - debit

    Sign convention matches vendor_ledger: running += credit - debit.
    """
    bills = session.exec(
        select(Bill).where(
            Bill.tenant_id == tenant_id,
            Bill.vendor_id == vendor.id,
        ).order_by(Bill.bill_date, Bill.id)
    ).all()
    payments = session.exec(
        select(BillPayment).where(
            BillPayment.tenant_id == tenant_id,
        ).order_by(BillPayment.payment_date, BillPayment.id)
    ).all()
    vendor_bill_ids = {b.id for b in bills}

    # ── Opening balance (before start) ──────────────────────────────────────
    opening = D(vendor.opening_balance)
    for b in bills:
        if start and b.bill_date < start:
            opening += _to_base(D(b.total), D(b.exchange_rate))
    for p in payments:
        if not (start and p.payment_date < start):
            continue
        applied = _bill_payment_applied_to_vendor(session, tenant_id, p, vendor_bill_ids)
        opening -= applied

    # ── Period credit (bills in window) ─────────────────────────────────────
    period_cr = ZERO
    for b in bills:
        if not _in_range(b.bill_date, start, end):
            continue
        period_cr += _to_base(D(b.total), D(b.exchange_rate))

    # ── Period debit (payments in window) ────────────────────────────────────
    period_dr = ZERO
    for p in payments:
        if not _in_range(p.payment_date, start, end):
            continue
        period_dr += _bill_payment_applied_to_vendor(session, tenant_id, p, vendor_bill_ids)

    closing = opening + period_cr - period_dr
    return {
        "opening": money(opening),
        "debit": money(period_dr),
        "credit": money(period_cr),
        "closing": money(closing),
    }


def _payment_applied_to_invoices(
    session, tenant_id: int, p: "PaymentReceived", invoice_ids: set
) -> Decimal:
    """Sum of payment amount applied to the given invoice ids."""
    if p.invoice_id and p.invoice_id in invoice_ids:
        return D(p.amount)
    allocs = session.exec(
        select(PaymentAllocation).where(
            PaymentAllocation.tenant_id == tenant_id,
            PaymentAllocation.payment_received_id == p.id,
        )
    ).all()
    return sum((D(a.amount) for a in allocs if a.invoice_id in invoice_ids), start=ZERO)


def _bill_payment_applied_to_vendor(
    session, tenant_id: int, p: "BillPayment", bill_ids: set
) -> Decimal:
    """Sum of bill-payment amount applied to the given bill ids."""
    if p.bill_id and p.bill_id in bill_ids:
        return D(p.amount)
    allocs = session.exec(
        select(PaymentAllocation).where(
            PaymentAllocation.tenant_id == tenant_id,
            PaymentAllocation.bill_payment_id == p.id,
        )
    ).all()
    return sum((D(a.amount) for a in allocs if a.bill_id in bill_ids), start=ZERO)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _to_base(amount: Decimal, fx: Decimal) -> Decimal:
    """Snapshot-FX conversion: amount × exchange_rate (doc→base)."""
    return money(D(amount) * D(fx))


def _invoice_stock_qty(session, invoice_id: int) -> tuple[Decimal, Optional[str]]:
    """Sum of qty on stock-product lines of an invoice + a representative
    unit label (the first stock line's unit). Returns (qty, unit)."""
    rows = session.exec(
        select(InvoiceLine, Product)
        .join(Product, Product.id == InvoiceLine.product_id, isouter=True)
        .where(InvoiceLine.invoice_id == invoice_id)
    ).all()
    qty = ZERO
    unit: Optional[str] = None
    for ln, prod in rows:
        if prod is not None and prod.product_type == "stock":
            qty += D(ln.qty)
            if unit is None:
                unit = ln.unit or prod.unit
    return qty, unit


def _bill_stock_qty(session, bill_id: int) -> tuple[Decimal, Optional[str]]:
    rows = session.exec(
        select(BillLine, Product)
        .join(Product, Product.id == BillLine.product_id, isouter=True)
        .where(BillLine.bill_id == bill_id)
    ).all()
    qty = ZERO
    unit: Optional[str] = None
    for ln, prod in rows:
        if prod is not None and prod.product_type == "stock":
            qty += D(ln.qty)
            if unit is None:
                unit = ln.unit or prod.unit
    return qty, unit


def _in_range(d: str, start: Optional[str], end: Optional[str]) -> bool:
    if start and d < start:
        return False
    if end and d > end:
        return False
    return True


# ── Customer ledger ─────────────────────────────────────────────────────────


@router.get("/api/customers/{customer_id}/ledger")
def customer_ledger(
    session: SessionDep, user: CurrentUserDep, customer_id: int,
    start: Optional[str] = None, end: Optional[str] = None,
):
    """Chronological AR sub-ledger for a customer.

    Rows:
      - Invoices (debit AR)  — qty_out shows stock lines sold to customer
      - PaymentReceived (credit AR) via direct invoice_id link or allocations

    All amounts in tenant base currency. Running balance is opening AR
    + ΣDr − ΣCr over the period.
    """
    cust = session.exec(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == user.tenant_id,
        )
    ).first()
    if not cust:
        raise HTTPException(404, "Customer not found")

    # Opening balance and period aggregates via shared helper (single source of truth)
    movement = ar_party_movement(session, user.tenant_id, cust, start, end)
    period_opening = D(movement["opening"])

    invoices = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.customer_id == customer_id,
        ).order_by(Invoice.issue_date, Invoice.id)
    ).all()
    payments = session.exec(
        select(PaymentReceived).where(
            PaymentReceived.tenant_id == user.tenant_id,
        ).order_by(PaymentReceived.payment_date, PaymentReceived.id)
    ).all()

    # Build raw event list
    events: list[dict] = []

    # In-period invoices
    for inv in invoices:
        if not _in_range(inv.issue_date, start, end):
            continue
        amt_base = _to_base(D(inv.total), D(inv.exchange_rate))
        qty, unit = _invoice_stock_qty(session, inv.id)
        events.append({
            "date": inv.issue_date,
            "doc_type": "invoice",
            "doc_id": inv.id,
            "doc_number": inv.number,
            "description": inv.description or f"Invoice {inv.number}",
            "debit": str(amt_base),
            "credit": "0",
            "qty_out": str(qty) if qty > 0 else None,
            "qty_in": None,
            "unit": unit,
            "currency": inv.currency,
            "doc_amount": str(D(inv.total)),
        })

    # In-period payments — direct or via allocations targeting this customer's invoices
    customer_invoice_ids = {i.id for i in invoices}
    for p in payments:
        if not _in_range(p.payment_date, start, end):
            continue
        applied = ZERO
        if p.invoice_id and p.invoice_id in customer_invoice_ids:
            applied = D(p.amount)
        else:
            allocs = session.exec(
                select(PaymentAllocation).where(
                    PaymentAllocation.tenant_id == user.tenant_id,
                    PaymentAllocation.payment_received_id == p.id,
                )
            ).all()
            for a in allocs:
                if a.invoice_id and a.invoice_id in customer_invoice_ids:
                    applied += D(a.amount)
        if applied <= 0:
            continue
        events.append({
            "date": p.payment_date,
            "doc_type": "payment_received",
            "doc_id": p.id,
            "doc_number": f"REC-{p.id:05d}",
            "description": f"Payment via {p.method}" + (f" ({p.reference})" if p.reference else ""),
            "debit": "0",
            "credit": str(applied),
            "qty_out": None,
            "qty_in": None,
            "unit": None,
            "currency": "—",
            "doc_amount": str(applied),
        })

    # Sort chronologically (stable) + compute running balance
    events.sort(key=lambda e: (e["date"], e["doc_id"]))
    running = period_opening
    total_dr = ZERO
    total_cr = ZERO
    total_qty_out = ZERO
    for e in events:
        running += D(e["debit"]) - D(e["credit"])
        e["running_balance"] = str(money(running))
        total_dr += D(e["debit"])
        total_cr += D(e["credit"])
        if e["qty_out"]:
            total_qty_out += D(e["qty_out"])

    return {
        "customer": {
            "id": cust.id, "name": cust.name,
            "email": cust.email, "phone": cust.phone,
            "opening_balance": str(D(cust.opening_balance)),
        },
        "period": {"start": start, "end": end},
        "opening_balance": str(money(period_opening)),
        "entries": events,
        "closing_balance": str(money(running)),
        "totals": {
            "debit": str(money(total_dr)),
            "credit": str(money(total_cr)),
            "qty_out": str(total_qty_out) if total_qty_out > 0 else None,
        },
    }


# ── Vendor ledger ───────────────────────────────────────────────────────────


@router.get("/api/vendors/{vendor_id}/ledger")
def vendor_ledger(
    session: SessionDep, user: CurrentUserDep, vendor_id: int,
    start: Optional[str] = None, end: Optional[str] = None,
):
    """Chronological AP sub-ledger for a vendor.

    Rows:
      - Bills (credit AP)  — qty_in shows stock lines purchased from vendor
      - BillPayment (debit AP) via direct bill_id link or allocations
    """
    v = session.exec(
        select(Vendor).where(
            Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id,
        )
    ).first()
    if not v:
        raise HTTPException(404, "Vendor not found")

    # Opening balance and period aggregates via shared helper (single source of truth)
    movement = ap_party_movement(session, user.tenant_id, v, start, end)
    period_opening = D(movement["opening"])

    bills = session.exec(
        select(Bill).where(
            Bill.tenant_id == user.tenant_id, Bill.vendor_id == vendor_id,
        ).order_by(Bill.bill_date, Bill.id)
    ).all()
    payments = session.exec(
        select(BillPayment).where(
            BillPayment.tenant_id == user.tenant_id,
        ).order_by(BillPayment.payment_date, BillPayment.id)
    ).all()
    bill_ids_for_vendor = {b.id for b in bills}

    events: list[dict] = []
    for b in bills:
        if not _in_range(b.bill_date, start, end):
            continue
        amt_base = _to_base(D(b.total), D(b.exchange_rate))
        qty, unit = _bill_stock_qty(session, b.id)
        events.append({
            "date": b.bill_date,
            "doc_type": "bill",
            "doc_id": b.id,
            "doc_number": b.number,
            "description": b.description or f"Bill {b.number}",
            "debit": "0",
            "credit": str(amt_base),
            "qty_in": str(qty) if qty > 0 else None,
            "qty_out": None,
            "unit": unit,
            "currency": b.currency,
            "doc_amount": str(D(b.total)),
        })

    for p in payments:
        if not _in_range(p.payment_date, start, end):
            continue
        applied = ZERO
        if p.bill_id and p.bill_id in bill_ids_for_vendor:
            applied = D(p.amount)
        else:
            allocs = session.exec(
                select(PaymentAllocation).where(
                    PaymentAllocation.tenant_id == user.tenant_id,
                    PaymentAllocation.bill_payment_id == p.id,
                )
            ).all()
            for a in allocs:
                if a.bill_id and a.bill_id in bill_ids_for_vendor:
                    applied += D(a.amount)
        if applied <= 0:
            continue
        events.append({
            "date": p.payment_date,
            "doc_type": "bill_payment",
            "doc_id": p.id,
            "doc_number": f"PAY-{p.id:05d}",
            "description": f"Payment via {p.method}" + (f" ({p.reference})" if p.reference else ""),
            "debit": str(applied),
            "credit": "0",
            "qty_in": None,
            "qty_out": None,
            "unit": None,
            "currency": "—",
            "doc_amount": str(applied),
        })

    events.sort(key=lambda e: (e["date"], e["doc_id"]))
    # AP is credit-normal: running balance = ΣCr − ΣDr, so a positive number
    # represents "amount we owe the vendor".
    running = period_opening
    total_dr = ZERO
    total_cr = ZERO
    total_qty_in = ZERO
    for e in events:
        running += D(e["credit"]) - D(e["debit"])
        e["running_balance"] = str(money(running))
        total_dr += D(e["debit"])
        total_cr += D(e["credit"])
        if e["qty_in"]:
            total_qty_in += D(e["qty_in"])

    return {
        "vendor": {
            "id": v.id, "name": v.name,
            "email": v.email, "phone": v.phone,
            "opening_balance": str(D(v.opening_balance)),
        },
        "period": {"start": start, "end": end},
        "opening_balance": str(money(period_opening)),
        "entries": events,
        "closing_balance": str(money(running)),
        "totals": {
            "debit": str(money(total_dr)),
            "credit": str(money(total_cr)),
            "qty_in": str(total_qty_in) if total_qty_in > 0 else None,
        },
    }


# ── Customer statement ──────────────────────────────────────────────────────


@router.get("/api/customers/{customer_id}/statement")
def customer_statement(
    session: SessionDep, user: CurrentUserDep, customer_id: int,
    from_date: Optional[str] = None, to_date: Optional[str] = None,
):
    """Account statement for a customer: open invoices, payments, balances.

    Returns a print-ready structure with:
      - customer info
      - period
      - opening_balance (AR balance before from_date)
      - invoices in period with outstanding amount per invoice
      - payments in period
      - closing_balance
    """
    cust = session.exec(
        select(Customer).where(
            Customer.id == customer_id, Customer.tenant_id == user.tenant_id,
        )
    ).first()
    if not cust:
        raise HTTPException(404, "Customer not found")

    invoices = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.customer_id == customer_id,
        ).order_by(Invoice.issue_date, Invoice.id)
    ).all()

    payments_all = session.exec(
        select(PaymentReceived).where(
            PaymentReceived.tenant_id == user.tenant_id,
        ).order_by(PaymentReceived.payment_date, PaymentReceived.id)
    ).all()
    customer_invoice_ids = {i.id for i in invoices}

    # Opening balance: all invoices before from_date minus payments before from_date
    opening = D(cust.opening_balance)
    if from_date:
        pre_inv = [i for i in invoices if i.issue_date < from_date]
        opening += sum((_to_base(D(i.total), D(i.exchange_rate)) for i in pre_inv), start=ZERO)
        for p in payments_all:
            if p.payment_date >= from_date:
                continue
            applied = _payment_applied_to_customer(session, p, customer_invoice_ids)
            opening -= applied

    # In-period invoices
    period_invoices = []
    for inv in invoices:
        if not _in_range(inv.issue_date, from_date, to_date):
            continue
        # Outstanding = total - sum of allocations
        alloc_total = session.exec(
            select(PaymentAllocation).where(
                PaymentAllocation.invoice_id == inv.id,
                PaymentAllocation.tenant_id == user.tenant_id,
            )
        ).all()
        allocated = sum((D(a.amount) for a in alloc_total), start=ZERO)
        outstanding = max(ZERO, _to_base(D(inv.total), D(inv.exchange_rate)) - allocated)
        period_invoices.append({
            "id": inv.id,
            "number": inv.number,
            "date": inv.issue_date,
            "due_date": inv.due_date,
            "status": inv.status,
            "total": str(_to_base(D(inv.total), D(inv.exchange_rate))),
            "outstanding": str(money(outstanding)),
            "currency": inv.currency,
        })

    # In-period payments
    period_payments = []
    for p in payments_all:
        if not _in_range(p.payment_date, from_date, to_date):
            continue
        applied = _payment_applied_to_customer(session, p, customer_invoice_ids)
        if applied <= 0:
            continue
        period_payments.append({
            "id": p.id,
            "date": p.payment_date,
            "method": p.method,
            "reference": p.reference,
            "amount": str(money(applied)),
        })

    # Closing balance
    closing = opening
    for inv_row in period_invoices:
        closing += D(inv_row["total"])
    for pay_row in period_payments:
        closing -= D(pay_row["amount"])

    return {
        "customer": {
            "id": cust.id, "name": cust.name,
            "email": cust.email, "phone": cust.phone, "address": cust.address,
        },
        "period": {"from": from_date, "to": to_date},
        "opening_balance": str(money(opening)),
        "invoices": period_invoices,
        "payments": period_payments,
        "closing_balance": str(money(closing)),
    }


def _payment_applied_to_customer(
    session, p: "PaymentReceived", customer_invoice_ids: set
) -> Decimal:
    if p.invoice_id and p.invoice_id in customer_invoice_ids:
        return D(p.amount)
    allocs = session.exec(
        select(PaymentAllocation).where(
            PaymentAllocation.payment_received_id == p.id,
        )
    ).all()
    return sum((D(a.amount) for a in allocs if a.invoice_id in customer_invoice_ids), start=ZERO)


# ── Vendor statement ─────────────────────────────────────────────────────────


@router.get("/api/vendors/{vendor_id}/statement")
def vendor_statement(
    session: SessionDep, user: CurrentUserDep, vendor_id: int,
    from_date: Optional[str] = None, to_date: Optional[str] = None,
):
    """Account statement for a vendor: open bills, payments, balances."""
    from models import BillPayment as BillPaymentModel

    v = session.exec(
        select(Vendor).where(
            Vendor.id == vendor_id, Vendor.tenant_id == user.tenant_id,
        )
    ).first()
    if not v:
        raise HTTPException(404, "Vendor not found")

    bills = session.exec(
        select(Bill).where(
            Bill.tenant_id == user.tenant_id,
            Bill.vendor_id == vendor_id,
        ).order_by(Bill.bill_date, Bill.id)
    ).all()
    vendor_bill_ids = {b.id for b in bills}

    bp_all = session.exec(
        select(BillPaymentModel).where(
            BillPaymentModel.tenant_id == user.tenant_id,
        ).order_by(BillPaymentModel.payment_date, BillPaymentModel.id)
    ).all()

    opening = D(v.opening_balance)
    if from_date:
        pre_bills = [b for b in bills if b.bill_date < from_date]
        opening += sum((_to_base(D(b.total), D(b.exchange_rate)) for b in pre_bills), start=ZERO)
        for bp in bp_all:
            if bp.payment_date >= from_date:
                continue
            applied = _bp_applied_to_vendor(session, bp, vendor_bill_ids)
            opening -= applied

    period_bills = []
    for bill in bills:
        if not _in_range(bill.bill_date, from_date, to_date):
            continue
        from models import PaymentAllocation as PA
        alloc_total = session.exec(
            select(PA).where(PA.bill_id == bill.id, PA.tenant_id == user.tenant_id)
        ).all()
        allocated = sum((D(a.amount) for a in alloc_total), start=ZERO)
        outstanding = max(ZERO, _to_base(D(bill.total), D(bill.exchange_rate)) - allocated)
        period_bills.append({
            "id": bill.id,
            "number": bill.number,
            "date": bill.bill_date,
            "due_date": bill.due_date,
            "status": bill.status,
            "total": str(_to_base(D(bill.total), D(bill.exchange_rate))),
            "outstanding": str(money(outstanding)),
            "currency": bill.currency,
        })

    period_payments = []
    for bp in bp_all:
        if not _in_range(bp.payment_date, from_date, to_date):
            continue
        applied = _bp_applied_to_vendor(session, bp, vendor_bill_ids)
        if applied <= 0:
            continue
        period_payments.append({
            "id": bp.id,
            "date": bp.payment_date,
            "method": bp.method,
            "reference": bp.reference,
            "amount": str(money(applied)),
        })

    closing = opening
    for b_row in period_bills:
        closing += D(b_row["total"])
    for p_row in period_payments:
        closing -= D(p_row["amount"])

    return {
        "vendor": {
            "id": v.id, "name": v.name,
            "email": v.email, "phone": v.phone, "address": v.address,
        },
        "period": {"from": from_date, "to": to_date},
        "opening_balance": str(money(opening)),
        "bills": period_bills,
        "payments": period_payments,
        "closing_balance": str(money(closing)),
    }


def _bp_applied_to_vendor(session, bp, vendor_bill_ids: set) -> Decimal:
    from models import PaymentAllocation as PA
    if bp.bill_id and bp.bill_id in vendor_bill_ids:
        return D(bp.amount)
    allocs = session.exec(select(PA).where(PA.bill_payment_id == bp.id)).all()
    return sum((D(a.amount) for a in allocs if a.bill_id in vendor_bill_ids), start=ZERO)


# ── Product stock card ──────────────────────────────────────────────────────


_INFLOW_DIRECTIONS = {"RECEIPT", "CUSTODIAL_RECEIPT", "COMPLETION", "CUSTODIAL_COMPLETION"}


@router.get("/api/products/{product_id}/stock-card")
def product_stock_card(
    session: SessionDep, user: CurrentUserDep, product_id: int,
    start: Optional[str] = None, end: Optional[str] = None,
):
    """Movement-based stock card: opening qty/value at the start date,
    each movement with running qty/value, closing at the end date.

    Driven by StockMovement (V2.2). For products with no movements yet,
    we fall back to the snapshot on Product.stock_qty / avg_cost.
    """
    prod = session.exec(
        select(Product).where(
            Product.id == product_id, Product.tenant_id == user.tenant_id,
        )
    ).first()
    if not prod:
        raise HTTPException(404, "Product not found")

    movements = session.exec(
        select(StockMovement).where(
            StockMovement.tenant_id == user.tenant_id,
            StockMovement.product_id == product_id,
        ).order_by(StockMovement.occurred_at, StockMovement.id)
    ).all()

    # Opening qty/value = sum of in-flows minus out-flows that occurred
    # strictly before `start`.
    opening_qty = ZERO
    opening_value = ZERO
    cursor_qty = ZERO
    cursor_value = ZERO

    def _is_inflow(m: StockMovement) -> bool:
        return m.direction in _INFLOW_DIRECTIONS

    for mv in movements:
        d = mv.occurred_at.date().isoformat() if hasattr(mv.occurred_at, "date") else str(mv.occurred_at)
        if start and d < start:
            if _is_inflow(mv):
                opening_qty += D(mv.qty)
                opening_value += D(mv.total_cost)
            else:
                opening_qty -= D(mv.qty)
                opening_value -= D(mv.total_cost)

    cursor_qty = opening_qty
    cursor_value = opening_value

    entries: list[dict] = []
    total_in = ZERO
    total_out = ZERO
    for mv in movements:
        d = mv.occurred_at.date().isoformat() if hasattr(mv.occurred_at, "date") else str(mv.occurred_at)
        if not _in_range(d, start, end):
            continue
        inflow = _is_inflow(mv)
        qty_signed = D(mv.qty) if inflow else -D(mv.qty)
        cost_signed = D(mv.total_cost) if inflow else -D(mv.total_cost)
        cursor_qty += qty_signed
        cursor_value += cost_signed
        if inflow:
            total_in += D(mv.qty)
        else:
            total_out += D(mv.qty)
        entries.append({
            "date": d,
            "direction": mv.direction,
            "lot_no": mv.lot_no,
            "from_location_id": mv.from_location_id,
            "to_location_id": mv.to_location_id,
            "qty_in": str(D(mv.qty)) if inflow else None,
            "qty_out": str(D(mv.qty)) if not inflow else None,
            "unit_cost": str(D(mv.unit_cost)),
            "total_cost": str(D(mv.total_cost)),
            "running_qty": str(cursor_qty),
            "running_value": str(money(cursor_value)),
            "source_doc_type": mv.source_doc_type,
            "source_doc_id": mv.source_doc_id,
            "posted_to_gl": mv.posted_to_gl,
            "notes": mv.notes,
        })

    return {
        "product": {
            "id": prod.id, "code": prod.code, "name": prod.name,
            "unit": prod.unit, "product_type": prod.product_type,
            "stock_qty_snapshot": str(D(prod.stock_qty)),
            "avg_cost_snapshot": str(D(prod.avg_cost)),
        },
        "period": {"start": start, "end": end},
        "opening_qty": str(opening_qty),
        "opening_value": str(money(opening_value)),
        "entries": entries,
        "closing_qty": str(cursor_qty),
        "closing_value": str(money(cursor_value)),
        "totals": {
            "qty_in": str(total_in),
            "qty_out": str(total_out),
        },
    }
