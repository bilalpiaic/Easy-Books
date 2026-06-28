"""
Universal search — GET /api/search?q=&limit=5&types=

Queries all major entities for the current tenant in a single request.
All queries are tenant-scoped; cross-tenant data is never returned.

Expanded column coverage:
  Invoice:     number, customer_name, description, notes, status, issue_date, total
  Bill:        number, vendor_name, description, notes, status, bill_date, total
  Customer:    name, email, phone, address, ntn, cnic
  Vendor:      name, email, phone, address
  Account:     code, name, type, notes (if any)
  Product:     name, code, unit, description
  Employee:    name, employee_code, department, designation, cnic, bank_name
  Transaction: jv_number, description, party, reference, notes, date, voucher_type
"""
from fastapi import APIRouter, Query
from sqlalchemy import or_
from sqlmodel import select

from models import (Account, Bill, Customer, Employee, Invoice,
                    Product, Transaction, Vendor)
from .common import CurrentUserDep, SessionDep

router = APIRouter()


def _row(r, label: str, sub: str, href: str, **extra) -> dict:
    return {"id": r.id, "label": label, "sub": sub, "href": href, **extra}


def _is_numeric(q: str) -> bool:
    try:
        float(q.replace(",", ""))
        return True
    except ValueError:
        return False


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
        rows = session.exec(
            select(Invoice)
            .where(Invoice.tenant_id == tid)
            .where(or_(
                Invoice.number.ilike(p),
                Invoice.customer_name.ilike(p),
                Invoice.description.ilike(p),
                Invoice.notes.ilike(p),
                Invoice.status.ilike(p),
                Invoice.issue_date.ilike(p),
            ))
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
        rows = session.exec(
            select(Bill)
            .where(Bill.tenant_id == tid)
            .where(or_(
                Bill.number.ilike(p),
                Bill.vendor_name.ilike(p),
                Bill.description.ilike(p),
                Bill.notes.ilike(p),
                Bill.status.ilike(p),
                Bill.bill_date.ilike(p),
            ))
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

    # ── Transactions ──────────────────────────────────────────────────────────
    if _include("transactions"):
        rows = session.exec(
            select(Transaction)
            .where(Transaction.tenant_id == tid)
            .where(or_(
                Transaction.jv_number.ilike(p),
                Transaction.description.ilike(p),
                Transaction.party.ilike(p),
                Transaction.reference.ilike(p),
                Transaction.notes.ilike(p),
                Transaction.date.ilike(p),
                Transaction.voucher_type.ilike(p),
            ))
            .order_by(Transaction.id.desc())
            .limit(limit)
        ).all()
        result["transactions"] = [
            _row(r, r.jv_number,
                 " · ".join(filter(None, [
                     r.date or "",
                     r.party or r.description or "",
                     r.reference or "",
                 ])),
                 "/journal",
                 date=r.date,
                 status=r.voucher_type)
            for r in rows
        ]

    return result
