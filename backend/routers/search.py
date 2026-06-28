"""
Universal search — GET /api/search?q=&limit=5

Queries all major entities for the current tenant in a single request.
All queries are tenant-scoped; cross-tenant data is never returned.
"""
from fastapi import APIRouter, Query
from sqlalchemy import or_
from sqlmodel import select

from models import (Account, Bill, Customer, Employee, Invoice,
                    Product, Transaction, Vendor)
from .common import CurrentUserDep, SessionDep

router = APIRouter()


def _rows(objs, label_fn, sub_fn, href_fn):
    return [
        {"id": r.id, "label": label_fn(r), "sub": sub_fn(r), "href": href_fn(r)}
        for r in objs
    ]


@router.get("/api/search")
def global_search(
    session: SessionDep,
    current_user: CurrentUserDep,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(5, ge=1, le=20),
):
    tid = current_user.tenant_id
    p = f"%{q}%"

    customers = session.exec(
        select(Customer)
        .where(Customer.tenant_id == tid)
        .where(or_(Customer.name.ilike(p), Customer.email.ilike(p), Customer.phone.ilike(p)))
        .limit(limit)
    ).all()

    vendors = session.exec(
        select(Vendor)
        .where(Vendor.tenant_id == tid)
        .where(or_(Vendor.name.ilike(p), Vendor.email.ilike(p), Vendor.phone.ilike(p)))
        .limit(limit)
    ).all()

    invoices = session.exec(
        select(Invoice)
        .where(Invoice.tenant_id == tid)
        .where(or_(Invoice.number.ilike(p), Invoice.customer_name.ilike(p)))
        .limit(limit)
    ).all()

    bills = session.exec(
        select(Bill)
        .where(Bill.tenant_id == tid)
        .where(or_(Bill.number.ilike(p), Bill.vendor_name.ilike(p)))
        .limit(limit)
    ).all()

    accounts = session.exec(
        select(Account)
        .where(Account.tenant_id == tid)
        .where(or_(Account.code.ilike(p), Account.name.ilike(p)))
        .limit(limit)
    ).all()

    products = session.exec(
        select(Product)
        .where(Product.tenant_id == tid)
        .where(or_(
            Product.name.ilike(p),
            Product.code.ilike(p) if Product.code else False,
        ))
        .limit(limit)
    ).all()

    employees = session.exec(
        select(Employee)
        .where(Employee.tenant_id == tid)
        .where(or_(
            Employee.name.ilike(p),
            Employee.employee_code.ilike(p),
            Employee.department.ilike(p),
        ))
        .limit(limit)
    ).all()

    transactions = session.exec(
        select(Transaction)
        .where(Transaction.tenant_id == tid)
        .where(or_(
            Transaction.jv_number.ilike(p),
            Transaction.description.ilike(p),
            Transaction.party.ilike(p),
        ))
        .limit(limit)
    ).all()

    return {
        "customers": _rows(
            customers,
            lambda r: r.name,
            lambda r: r.email or r.phone or "",
            lambda r: f"/customers",
        ),
        "vendors": _rows(
            vendors,
            lambda r: r.name,
            lambda r: r.email or r.phone or "",
            lambda r: f"/vendors",
        ),
        "invoices": _rows(
            invoices,
            lambda r: r.number,
            lambda r: f"{r.customer_name or ''} · {float(r.total):,.2f}",
            lambda r: f"/invoices/{r.id}",
        ),
        "bills": _rows(
            bills,
            lambda r: r.number,
            lambda r: f"{r.vendor_name or ''} · {float(r.total):,.2f}",
            lambda r: f"/bills/{r.id}",
        ),
        "accounts": _rows(
            accounts,
            lambda r: f"{r.code} — {r.name}",
            lambda r: r.type,
            lambda r: "/coa",
        ),
        "products": _rows(
            products,
            lambda r: r.name,
            lambda r: r.code or "",
            lambda r: f"/products",
        ),
        "employees": _rows(
            employees,
            lambda r: r.name,
            lambda r: r.employee_code + (f" · {r.department}" if r.department else ""),
            lambda r: f"/employees/{r.id}/edit",
        ),
        "transactions": _rows(
            transactions,
            lambda r: r.jv_number,
            lambda r: r.description or r.party or "",
            lambda r: f"/journal",
        ),
    }
