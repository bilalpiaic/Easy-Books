"""Customer CRUD."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Customer, Invoice, InvoiceLine, PaymentAllocation, PaymentReceived, Product

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit, mark_onboarding_step
from services.events import emit
from services.permissions import perm_dep, apply_own_filter
from services.custom_fields import apply_incoming as apply_custom_fields
from services.form_schema import apply_to_payload, skip_custom_required

router = APIRouter(prefix="/api/customers", tags=["customers"], dependencies=[perm_dep("customers")])


class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Decimal = Decimal("0")
    payment_term_id: Optional[int] = None
    ntn: Optional[str] = None   # PRA BuyerPNTN (7-digit NTN e.g. "1234567-8")
    cnic: Optional[str] = None  # PRA BuyerCNIC (13 digits)
    gstin: Optional[str] = None
    state_code: Optional[str] = None
    custom_fields: Optional[dict] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    opening_balance: Optional[Decimal] = None
    is_active: Optional[bool] = None
    payment_term_id: Optional[int] = None
    ntn: Optional[str] = None
    cnic: Optional[str] = None
    gstin: Optional[str] = None
    state_code: Optional[str] = None
    custom_fields: Optional[dict] = None


@router.get("")
def list_customers(
    session: SessionDep, user: CurrentUserDep,
    search: str = "", skip: int = 0, limit: int = 50,
    sort_by: str = "name", sort_dir: str = "asc",
):
    from sqlmodel import asc as _asc, desc as _desc
    from routers.subledger import ar_closing_balances
    from services.money import ZERO, money

    _sortable = {"name": Customer.name, "email": Customer.email, "opening_balance": Customer.opening_balance}
    col = _sortable.get(sort_by, Customer.name)
    q = select(Customer).where(Customer.tenant_id == user.tenant_id)
    if search:
        q = q.where(Customer.name.ilike(f"%{search}%"))
    q = q.order_by(_asc(col) if sort_dir == "asc" else _desc(col))
    all_matching = session.exec(q).all()
    total = len(all_matching)
    all_closing = ar_closing_balances(session, user.tenant_id, all_matching)
    closing_balance_total = money(sum(all_closing.values(), start=ZERO))

    items = all_matching[skip : skip + limit]
    page_out = []
    for c in items:
        row = c.model_dump()
        row["closing_balance"] = float(all_closing.get(c.id, money(c.opening_balance)))
        page_out.append(row)
    return {
        "total": total,
        "closing_balance_total": float(closing_balance_total),
        "items": page_out,
    }


@router.get("/{customer_id}")
def get_customer(session: SessionDep, user: CurrentUserDep, customer_id: int):
    c = session.exec(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    return c


@router.post("", status_code=201)
def create_customer(session: SessionDep, user: WriteUserDep, body: CustomerCreate):
    data = body.model_dump()
    data, hidden = apply_to_payload(session, user, "customer", data)
    data["custom_fields"] = apply_custom_fields(
        session, user.tenant_id, "customer", data.get("custom_fields"),
        skip_required=skip_custom_required(hidden),
    )
    c = Customer(**data, tenant_id=user.tenant_id)
    session.add(c)
    session.flush()
    log_audit(session, user, "CREATE", "customer", c.id, {"name": c.name})
    mark_onboarding_step(session, user.tenant_id, "first_customer")
    emit(session, user.tenant_id, "customer.created", {
        "customer_id": c.id, "name": c.name, "email": c.email,
    })
    session.commit()
    session.refresh(c)
    return c


@router.put("/{customer_id}")
def update_customer(
    session: SessionDep, user: WriteUserDep, customer_id: int, body: CustomerUpdate
):
    c = session.exec(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    data = body.model_dump(exclude_none=True)
    data, hidden = apply_to_payload(session, user, "customer", data, existing=c.model_dump())
    if "custom_fields" in data:
        data["custom_fields"] = apply_custom_fields(
            session, user.tenant_id, "customer", data["custom_fields"],
            existing=c.custom_fields,
            skip_required=skip_custom_required(hidden),
        )
    for k, v in data.items():
        setattr(c, k, v)
    session.add(c)
    log_audit(session, user, "UPDATE", "customer", c.id, {"name": c.name})
    session.commit()
    session.refresh(c)
    return c


@router.delete("/{customer_id}", status_code=204)
def delete_customer(session: SessionDep, user: WriteUserDep, customer_id: int):
    """Hard-delete only when no document references the customer. Otherwise
    set is_active=False via PUT to preserve the audit trail.
    """
    c = session.exec(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not c:
        raise HTTPException(404, "Customer not found")
    if session.exec(select(Invoice).where(Invoice.customer_id == customer_id)).first():
        raise HTTPException(
            400, "Cannot delete customer with invoices — deactivate (set is_active=False) instead",
        )
    if session.exec(select(PaymentReceived).where(PaymentReceived.invoice_id != None)).first():
        # Cross-check: any payment whose invoice belongs to this customer
        bad = session.exec(
            select(PaymentReceived)
            .join(Invoice, Invoice.id == PaymentReceived.invoice_id)
            .where(Invoice.customer_id == customer_id)
        ).first()
        if bad:
            raise HTTPException(
                400, "Cannot delete customer with payment history — deactivate instead",
            )
    log_audit(session, user, "DELETE", "customer", c.id, {"name": c.name})
    session.delete(c)
    session.commit()


@router.get("/{customer_id}/statement", dependencies=[perm_dep("customer_ledger")])
def customer_statement(
    session: SessionDep, user: CurrentUserDep, customer_id: int,
    from_date: str, to_date: str,
):
    """Account statement for a customer: opening balance, invoices, payments, closing balance."""
    c = session.exec(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not c:
        raise HTTPException(404, "Customer not found")

    D = lambda x: Decimal(str(x)) if x is not None else Decimal("0")

    # All invoices for this customer (pre-period + in-period), excluding void/cancelled
    all_invoices = session.exec(
        select(Invoice).where(
            Invoice.customer_id == customer_id,
            Invoice.tenant_id == user.tenant_id,
            Invoice.status.not_in(["void", "cancelled"]),
            Invoice.transaction_id.is_not(None),  # must be GL-posted
        ).order_by(Invoice.issue_date.asc(), Invoice.id.asc())
    ).all()

    all_inv_ids = [inv.id for inv in all_invoices]
    pre_invoices = [inv for inv in all_invoices if inv.issue_date < from_date]
    pre_inv_ids = [inv.id for inv in pre_invoices]

    # Pre-period payments: allocations paid BEFORE from_date against pre-period invoices
    pre_inv_paid: dict[int, Decimal] = {}
    if pre_inv_ids:
        for inv_id, paid in session.exec(
            select(PaymentAllocation.invoice_id, func.sum(PaymentAllocation.amount))
            .join(PaymentReceived, PaymentReceived.id == PaymentAllocation.payment_received_id)
            .where(
                PaymentAllocation.tenant_id == user.tenant_id,
                PaymentAllocation.invoice_id.in_(pre_inv_ids),
                PaymentReceived.payment_date < from_date,
            )
            .group_by(PaymentAllocation.invoice_id)
        ).all():
            pre_inv_paid[inv_id] = D(paid)

    # Opening balance: customer pre-system balance + net AR from invoices before from_date
    opening_balance = D(c.opening_balance)
    for inv in pre_invoices:
        opening_balance += D(inv.total) - pre_inv_paid.get(inv.id, Decimal("0"))

    # All allocations per invoice (for outstanding per line in the statement)
    inv_paid: dict[int, Decimal] = {}
    if all_inv_ids:
        for inv_id, paid in session.exec(
            select(PaymentAllocation.invoice_id, func.sum(PaymentAllocation.amount))
            .where(
                PaymentAllocation.tenant_id == user.tenant_id,
                PaymentAllocation.invoice_id.in_(all_inv_ids),
            )
            .group_by(PaymentAllocation.invoice_id)
        ).all():
            inv_paid[inv_id] = D(paid)

    # Period invoices
    period_invoices = [inv for inv in all_invoices if from_date <= inv.issue_date <= to_date]
    invoices_out = [
        {
            "id": inv.id,
            "number": inv.number,
            "date": inv.issue_date,
            "due_date": inv.due_date,
            "status": inv.status,
            "total": str(D(inv.total)),
            "outstanding": str(max(D(inv.total) - inv_paid.get(inv.id, Decimal("0")), Decimal("0"))),
            "currency": inv.currency,
        }
        for inv in period_invoices
    ]

    # Payments in period: PaymentReceived with allocations to this customer's invoices
    period_payments: list[dict] = []
    if all_inv_ids:
        pay_rows = session.exec(
            select(
                PaymentReceived.id,
                PaymentReceived.payment_date,
                PaymentReceived.method,
                PaymentReceived.reference,
                func.sum(PaymentAllocation.amount).label("allocated"),
            )
            .join(PaymentAllocation, PaymentAllocation.payment_received_id == PaymentReceived.id)
            .where(
                PaymentReceived.tenant_id == user.tenant_id,
                PaymentReceived.payment_date >= from_date,
                PaymentReceived.payment_date <= to_date,
                PaymentAllocation.invoice_id.in_(all_inv_ids),
            )
            .group_by(
                PaymentReceived.id,
                PaymentReceived.payment_date,
                PaymentReceived.method,
                PaymentReceived.reference,
            )
            .order_by(PaymentReceived.payment_date.asc())
        ).all()
        for row in pay_rows:
            period_payments.append({
                "id": row.id,
                "date": row.payment_date,
                "method": row.method,
                "reference": row.reference,
                "amount": str(D(row.allocated)),
            })

    period_inv_total = sum(D(i["total"]) for i in invoices_out)
    period_paid_total = sum(D(p["amount"]) for p in period_payments)
    closing_balance = opening_balance + period_inv_total - period_paid_total

    return {
        "customer": {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "address": c.address,
        },
        "period": {"from": from_date, "to": to_date},
        "opening_balance": str(opening_balance),
        "invoices": invoices_out,
        "payments": period_payments,
        "closing_balance": str(closing_balance),
    }


@router.get("/{customer_id}/products")
def customer_products(session: SessionDep, user: CurrentUserDep, customer_id: int):
    """Every product ever sold to this customer with last price/date, total qty,
    and invoice count."""

    rows = session.exec(
        select(InvoiceLine, Invoice.issue_date)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(Invoice.tenant_id == user.tenant_id,
               Invoice.customer_id == customer_id,
               InvoiceLine.product_id.is_not(None))
        .order_by(Invoice.issue_date.asc(), Invoice.id.asc())
    ).all()

    agg: dict = {}
    for line, issue_date in rows:
        a = agg.setdefault(line.product_id, {
            "product_id": line.product_id, "total_qty": 0.0,
            "_invoice_ids": set(), "last_rate": None, "last_date": None,
        })
        a["total_qty"] += float(line.qty)
        a["_invoice_ids"].add(line.invoice_id)
        a["last_rate"] = float(line.rate)     # rows ascending → last wins
        a["last_date"] = issue_date

    prod_ids = list(agg.keys())
    names = {}
    if prod_ids:
        for p in session.exec(
            select(Product).where(Product.id.in_(prod_ids),
                                  Product.tenant_id == user.tenant_id)
        ).all():
            names[p.id] = {"name": p.name, "code": p.code}
    items = []
    for pid, a in agg.items():
        a["invoice_count"] = len(a.pop("_invoice_ids"))
        a.update(names.get(pid, {"name": "—", "code": None}))
        items.append(a)
    items.sort(key=lambda r: r["total_qty"], reverse=True)
    return {"items": items}
