"""
Universal search — GET /api/search?q=&limit=5&types=

Queries all major entities for the current tenant in a single request.
All queries are tenant-scoped; cross-tenant data is never returned.

Expanded column coverage:
  Invoice:     number, customer_name, description, notes, status, issue_date, total
  Bill:        number, vendor_name, description, notes, status, bill_date, total
  Customer:    name, email, phone, address, ntn, cnic
  Vendor:      name, email, phone, address
  Account:     code, name, type
  Product:     name, code, unit, description
  Employee:    name, employee_code, department, designation, cnic, bank_name
  Transaction: jv_number, description, party, reference, notes, date, voucher_type,
               journal line debit/credit + voucher debit total
  Payments:    customer/vendor name, reference, amount
  Credit/Debit notes: number, party, description, notes, total

Numeric queries (e.g. 100000 or 100,000.00) also match document/payment
amounts and journal-line debits/credits within ±0.01.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, or_
from sqlmodel import select

from models import (
    Account, Bill, BillPayment, CreditNote, Customer, DebitNote, Employee,
    Invoice, JournalEntry, PaymentReceived, Product, Tenant, Transaction, Vendor,
)
from models_weighbridge import WbTicket
from routers.modules import _get_enabled
from .common import CurrentUserDep, SessionDep

router = APIRouter()

# Half-cent style tolerance so 100000 matches 100000.00 stored as Numeric(18,4)
_AMOUNT_TOL = 0.01


def _row(r, label: str, sub: str, href: str, **extra) -> dict:
    return {"id": r.id, "label": label, "sub": sub, "href": href, **extra}


def _is_numeric(q: str) -> bool:
    try:
        float(q.replace(",", "").strip())
        return True
    except ValueError:
        return False


def _parse_amount(q: str) -> float | None:
    """Return a float amount when q is purely numeric (commas / spaces allowed)."""
    s = q.strip().replace(",", "").replace(" ", "")
    if not s or "e" in s.lower() or not _is_numeric(s):
        return None
    return float(s)


def _near(col, amount: float):
    return col.between(amount - _AMOUNT_TOL, amount + _AMOUNT_TOL)


@router.get("/api/search")
def global_search(
    session: SessionDep,
    current_user: CurrentUserDep,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(5, ge=1, le=20),
    types: str = Query("", description="Comma-separated entity types to search. Empty = all."),
):
    tid = current_user.tenant_id
    p   = f"%{q}%"
    amount = _parse_amount(q)
    want = set(t.strip() for t in types.split(",") if t.strip()) if types else None

    def _include(key: str) -> bool:
        return want is None or key in want

    result: dict = {}

    # ── Customers ─────────────────────────────────────────────────────────────
    if _include("customers"):
        rows = session.exec(
            select(Customer)
            .where(Customer.tenant_id == tid)
            .where(or_(
                Customer.name.ilike(p),
                Customer.email.ilike(p),
                Customer.phone.ilike(p),
                Customer.address.ilike(p),
                Customer.ntn.ilike(p),
                Customer.cnic.ilike(p),
            ))
            .limit(limit)
        ).all()
        result["customers"] = [
            _row(r, r.name,
                 " · ".join(filter(None, [r.email, r.phone])) or r.address or "",
                 f"/customers")
            for r in rows
        ]

    # ── Vendors ───────────────────────────────────────────────────────────────
    if _include("vendors"):
        rows = session.exec(
            select(Vendor)
            .where(Vendor.tenant_id == tid)
            .where(or_(
                Vendor.name.ilike(p),
                Vendor.email.ilike(p),
                Vendor.phone.ilike(p),
                Vendor.address.ilike(p),
            ))
            .limit(limit)
        ).all()
        result["vendors"] = [
            _row(r, r.name,
                 " · ".join(filter(None, [r.email, r.phone])) or r.address or "",
                 f"/vendors")
            for r in rows
        ]

    # ── Invoices ──────────────────────────────────────────────────────────────
    if _include("invoices"):
        text_or = or_(
            Invoice.number.ilike(p),
            Invoice.customer_name.ilike(p),
            Invoice.description.ilike(p),
            Invoice.notes.ilike(p),
            Invoice.status.ilike(p),
            Invoice.issue_date.ilike(p),
        )
        where = or_(text_or, _near(Invoice.total, amount)) if amount is not None else text_or
        rows = session.exec(
            select(Invoice)
            .where(Invoice.tenant_id == tid)
            .where(where)
            .order_by(Invoice.id.desc())
            .limit(limit)
        ).all()
        result["invoices"] = [
            _row(r, r.number,
                 " · ".join(filter(None, [
                     r.customer_name or "",
                     r.issue_date or "",
                     r.description or "",
                 ])),
                 f"/invoices/{r.id}",
                 date=r.issue_date,
                 amount=float(r.total),
                 status=r.status)
            for r in rows
        ]

    # ── Bills ─────────────────────────────────────────────────────────────────
    if _include("bills"):
        text_or = or_(
            Bill.number.ilike(p),
            Bill.vendor_name.ilike(p),
            Bill.description.ilike(p),
            Bill.notes.ilike(p),
            Bill.status.ilike(p),
            Bill.bill_date.ilike(p),
        )
        where = or_(text_or, _near(Bill.total, amount)) if amount is not None else text_or
        rows = session.exec(
            select(Bill)
            .where(Bill.tenant_id == tid)
            .where(where)
            .order_by(Bill.id.desc())
            .limit(limit)
        ).all()
        result["bills"] = [
            _row(r, r.number,
                 " · ".join(filter(None, [
                     r.vendor_name or "",
                     r.bill_date or "",
                     r.description or "",
                 ])),
                 f"/bills/{r.id}",
                 date=r.bill_date,
                 amount=float(r.total),
                 status=r.status)
            for r in rows
        ]

    # ── Payments received ─────────────────────────────────────────────────────
    if _include("payments_received"):
        text_or = or_(
            PaymentReceived.customer_name.ilike(p),
            PaymentReceived.reference.ilike(p),
            PaymentReceived.method.ilike(p),
            PaymentReceived.payment_date.ilike(p),
        )
        where = or_(text_or, _near(PaymentReceived.amount, amount)) if amount is not None else text_or
        rows = session.exec(
            select(PaymentReceived)
            .where(PaymentReceived.tenant_id == tid)
            .where(where)
            .order_by(PaymentReceived.id.desc())
            .limit(limit)
        ).all()
        result["payments_received"] = [
            _row(r, r.customer_name or "Payment received",
                 " · ".join(filter(None, [
                     r.payment_date or "",
                     r.method or "",
                     r.reference or "",
                 ])),
                 f"/payments-received/{r.id}",
                 date=r.payment_date,
                 amount=float(r.amount),
                 status=r.method)
            for r in rows
        ]

    # ── Bill payments ─────────────────────────────────────────────────────────
    if _include("bill_payments"):
        text_or = or_(
            BillPayment.vendor_name.ilike(p),
            BillPayment.reference.ilike(p),
            BillPayment.method.ilike(p),
            BillPayment.payment_date.ilike(p),
        )
        where = or_(text_or, _near(BillPayment.amount, amount)) if amount is not None else text_or
        rows = session.exec(
            select(BillPayment)
            .where(BillPayment.tenant_id == tid)
            .where(where)
            .order_by(BillPayment.id.desc())
            .limit(limit)
        ).all()
        result["bill_payments"] = [
            _row(r, r.vendor_name or "Bill payment",
                 " · ".join(filter(None, [
                     r.payment_date or "",
                     r.method or "",
                     r.reference or "",
                 ])),
                 f"/bill-payments/{r.id}",
                 date=r.payment_date,
                 amount=float(r.amount),
                 status=r.method)
            for r in rows
        ]

    # ── Credit notes ──────────────────────────────────────────────────────────
    if _include("credit_notes"):
        text_or = or_(
            CreditNote.number.ilike(p),
            CreditNote.customer_name.ilike(p),
            CreditNote.description.ilike(p),
            CreditNote.notes.ilike(p),
            CreditNote.status.ilike(p),
            CreditNote.issue_date.ilike(p),
        )
        where = or_(text_or, _near(CreditNote.total, amount)) if amount is not None else text_or
        rows = session.exec(
            select(CreditNote)
            .where(CreditNote.tenant_id == tid)
            .where(where)
            .order_by(CreditNote.id.desc())
            .limit(limit)
        ).all()
        result["credit_notes"] = [
            _row(r, r.number,
                 " · ".join(filter(None, [
                     r.customer_name or "",
                     r.issue_date or "",
                     r.description or "",
                 ])),
                 f"/credit-notes/{r.id}",
                 date=r.issue_date,
                 amount=float(r.total),
                 status=r.status)
            for r in rows
        ]

    # ── Debit notes ───────────────────────────────────────────────────────────
    if _include("debit_notes"):
        text_or = or_(
            DebitNote.number.ilike(p),
            DebitNote.vendor_name.ilike(p),
            DebitNote.description.ilike(p),
            DebitNote.notes.ilike(p),
            DebitNote.status.ilike(p),
            DebitNote.issue_date.ilike(p),
        )
        where = or_(text_or, _near(DebitNote.total, amount)) if amount is not None else text_or
        rows = session.exec(
            select(DebitNote)
            .where(DebitNote.tenant_id == tid)
            .where(where)
            .order_by(DebitNote.id.desc())
            .limit(limit)
        ).all()
        result["debit_notes"] = [
            _row(r, r.number,
                 " · ".join(filter(None, [
                     r.vendor_name or "",
                     r.issue_date or "",
                     r.description or "",
                 ])),
                 f"/debit-notes/{r.id}",
                 date=r.issue_date,
                 amount=float(r.total),
                 status=r.status)
            for r in rows
        ]

    # ── Accounts ──────────────────────────────────────────────────────────────
    if _include("accounts"):
        rows = session.exec(
            select(Account)
            .where(Account.tenant_id == tid)
            .where(or_(
                Account.code.ilike(p),
                Account.name.ilike(p),
                Account.type.ilike(p),
            ))
            .limit(limit)
        ).all()
        result["accounts"] = [
            _row(r, f"{r.code} — {r.name}",
                 r.type + (" (Group)" if r.is_group else ""),
                 "/coa")
            for r in rows
        ]

    # ── Products ──────────────────────────────────────────────────────────────
    if _include("products"):
        rows = session.exec(
            select(Product)
            .where(Product.tenant_id == tid)
            .where(or_(
                Product.name.ilike(p),
                Product.code.ilike(p),
                Product.unit.ilike(p),
                Product.product_type.ilike(p),
            ))
            .limit(limit)
        ).all()
        result["products"] = [
            _row(r, r.name,
                 " · ".join(filter(None, [r.code or "", r.unit or "", r.product_type or ""])),
                 f"/products")
            for r in rows
        ]

    # ── Employees ─────────────────────────────────────────────────────────────
    if _include("employees"):
        rows = session.exec(
            select(Employee)
            .where(Employee.tenant_id == tid)
            .where(or_(
                Employee.name.ilike(p),
                Employee.employee_code.ilike(p),
                Employee.department.ilike(p),
                Employee.designation.ilike(p),
                Employee.cnic.ilike(p),
                Employee.bank_name.ilike(p),
            ))
            .limit(limit)
        ).all()
        result["employees"] = [
            _row(r, r.name,
                 " · ".join(filter(None, [
                     r.employee_code,
                     r.designation or "",
                     r.department or "",
                 ])),
                 f"/employees/{r.id}/edit")
            for r in rows
        ]

    # ── Transactions (JV) ─────────────────────────────────────────────────────
    if _include("transactions"):
        text_or = or_(
            Transaction.jv_number.ilike(p),
            Transaction.description.ilike(p),
            Transaction.party.ilike(p),
            Transaction.reference.ilike(p),
            Transaction.notes.ilike(p),
            Transaction.date.ilike(p),
            Transaction.voucher_type.ilike(p),
        )
        if amount is not None:
            # Line-level match OR voucher debit-total match
            total_ids = select(JournalEntry.transaction_id).where(
                JournalEntry.tenant_id == tid,
            ).group_by(JournalEntry.transaction_id).having(
                func.sum(JournalEntry.debit).between(amount - _AMOUNT_TOL, amount + _AMOUNT_TOL)
            )
            line_ids = select(JournalEntry.transaction_id).where(
                JournalEntry.tenant_id == tid,
                or_(
                    _near(JournalEntry.debit, amount),
                    _near(JournalEntry.credit, amount),
                ),
            )
            where = or_(
                text_or,
                Transaction.id.in_(total_ids),
                Transaction.id.in_(line_ids),
            )
        else:
            where = text_or

        rows = session.exec(
            select(Transaction)
            .where(Transaction.tenant_id == tid)
            .where(where)
            .order_by(Transaction.id.desc())
            .limit(limit)
        ).all()

        totals: dict[int, float] = {}
        if rows:
            for tid_, debit_sum in session.exec(
                select(JournalEntry.transaction_id, func.coalesce(func.sum(JournalEntry.debit), 0))
                .where(JournalEntry.transaction_id.in_([r.id for r in rows]))
                .group_by(JournalEntry.transaction_id)
            ).all():
                totals[int(tid_)] = float(debit_sum)

        result["transactions"] = [
            _row(r, r.jv_number,
                 " · ".join(filter(None, [
                     r.date or "",
                     r.party or r.description or "",
                     r.reference or "",
                 ])),
                 f"/journal/{r.id}",
                 date=r.date,
                 amount=totals.get(r.id),
                 status=r.voucher_type)
            for r in rows
        ]

    # ── Weighbridge tickets (module-gated) ──────────────────────────────────
    if _include("weighbridge"):
        tenant = session.get(Tenant, tid)
        if tenant is not None and "weighbridge" in _get_enabled(tenant):
            rows = session.exec(
                select(WbTicket)
                .where(WbTicket.tenant_id == tid)
                .where(or_(
                    WbTicket.number.ilike(p),
                    WbTicket.vehicle_no.ilike(p),
                    WbTicket.driver_name.ilike(p),
                    WbTicket.party_name.ilike(p),
                    WbTicket.commodity.ilike(p),
                    WbTicket.lot_ref.ilike(p),
                ))
                .order_by(WbTicket.id.desc())
                .limit(limit)
            ).all()
            result["weighbridge"] = [
                _row(
                    r, r.number,
                    " · ".join(filter(None, [r.vehicle_no, r.party_name, r.commodity])) or r.direction,
                    f"/weighbridge/tickets/{r.id}",
                    date=r.ticket_date,
                    status=r.status,
                )
                for r in rows
            ]

    return result
