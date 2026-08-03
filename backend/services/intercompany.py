"""Intercompany documents + reconciliation (#261).

Pairs with ConsolidationMember (#255). When an invoice/bill is flagged IC with a
counterparty in the same consolidation group, we optionally create a **draft**
mirror document on the sister tenant (no GL) and link ids both ways.

Reconciliation compares open (posted, unpaid) IC AR vs IC AP by counterparty
pair under a holding entity graph.
"""
from __future__ import annotations

from decimal import Decimal
from itertools import combinations
from typing import Optional

from sqlmodel import Session, col, or_, select

from models import (
    Bill,
    BillLine,
    ConsolidationMember,
    Customer,
    Invoice,
    InvoiceLine,
    Settings,
    Tenant,
    User,
    Vendor,
)
from routers.common import next_number
from services.money import D, ZERO, money

IC_VENDOR_NAME = "IC Counterpart"
IC_CUSTOMER_NAME = "IC Counterpart"
_OPEN_STATUSES_EXCLUDED = ("paid", "void")


class IntercompanyError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def assert_ic_member(session: Session, tenant_a: int, tenant_b: int) -> bool:
    """True if A↔B are linked via ConsolidationMember (holding↔member or same holding)."""
    if tenant_a == tenant_b:
        return False

    # Direct: either is a member row under the other as holding
    direct = session.exec(
        select(ConsolidationMember.id).where(
            ConsolidationMember.is_active == True,  # noqa: E712
            or_(
                (ConsolidationMember.holding_tenant_id == tenant_a)
                & (ConsolidationMember.member_tenant_id == tenant_b),
                (ConsolidationMember.holding_tenant_id == tenant_b)
                & (ConsolidationMember.member_tenant_id == tenant_a),
            ),
        )
    ).first()
    if direct is not None:
        return True

    # Same holding: both appear as members under one holding_tenant_id
    holdings_a = set(
        session.exec(
            select(ConsolidationMember.holding_tenant_id).where(
                ConsolidationMember.member_tenant_id == tenant_a,
                ConsolidationMember.is_active == True,  # noqa: E712
            )
        ).all()
    )
    if not holdings_a:
        return False
    shared = session.exec(
        select(ConsolidationMember.id).where(
            ConsolidationMember.member_tenant_id == tenant_b,
            ConsolidationMember.is_active == True,  # noqa: E712
            col(ConsolidationMember.holding_tenant_id).in_(holdings_a),
        )
    ).first()
    return shared is not None


def _setting(session: Session, tenant_id: int, key: str, default: str) -> str:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row and row.value else default


def get_or_create_ic_vendor(session: Session, tenant_id: int) -> Vendor:
    v = session.exec(
        select(Vendor).where(
            Vendor.tenant_id == tenant_id,
            Vendor.name == IC_VENDOR_NAME,
        )
    ).first()
    if v:
        return v
    v = Vendor(tenant_id=tenant_id, name=IC_VENDOR_NAME, is_active=True)
    session.add(v)
    session.flush()
    return v


def get_or_create_ic_customer(session: Session, tenant_id: int) -> Customer:
    c = session.exec(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.name == IC_CUSTOMER_NAME,
        )
    ).first()
    if c:
        return c
    c = Customer(tenant_id=tenant_id, name=IC_CUSTOMER_NAME, is_active=True)
    session.add(c)
    session.flush()
    return c


def _source_tenant_label(session: Session, tenant_id: int) -> str:
    t = session.get(Tenant, tenant_id)
    return (t.name if t else None) or f"Tenant {tenant_id}"


def create_ic_mirror_bill_from_invoice(
    session: Session, source_user: User, invoice: Invoice,
) -> Optional[Bill]:
    """Create a draft (no GL) Bill on the counterparty for an IC invoice."""
    if not invoice.is_intercompany or not invoice.ic_counterparty_tenant_id:
        return None
    if invoice.ic_mirror_bill_id:
        return session.get(Bill, invoice.ic_mirror_bill_id)

    cp_tid = invoice.ic_counterparty_tenant_id
    if not assert_ic_member(session, invoice.tenant_id, cp_tid):
        raise IntercompanyError(
            "IC counterparty is not in the same consolidation group", 400
        )

    vendor = get_or_create_ic_vendor(session, cp_tid)
    src_label = _source_tenant_label(session, invoice.tenant_id)
    total = money(invoice.total)
    prefix = _setting(session, cp_tid, "bill_prefix", "BILL")
    fmt = _setting(session, cp_tid, "bill_number_format", "") or None

    bill = Bill(
        tenant_id=cp_tid,
        number=next_number(session, cp_tid, "bill", prefix, fmt=fmt),
        vendor_id=vendor.id,
        vendor_name=vendor.name,
        bill_date=invoice.issue_date,
        due_date=invoice.due_date or invoice.issue_date,
        description=f"IC mirror of {invoice.number} ({src_label})",
        notes=invoice.notes,
        internal_memo=f"Auto-mirrored from invoice {invoice.id} tenant {invoice.tenant_id}",
        subtotal=total,
        gst_rate=ZERO,
        gst_amount=ZERO,
        total=total,
        currency=invoice.currency or "USD",
        exchange_rate=D(invoice.exchange_rate or 1),
        status="draft",
        created_by_id=source_user.id,
        is_intercompany=True,
        ic_counterparty_tenant_id=invoice.tenant_id,
        ic_mirror_invoice_id=invoice.id,
        # No transaction_id — draft mirror, no GL
    )
    session.add(bill)
    session.flush()

    session.add(
        BillLine(
            bill_id=bill.id,
            description=f"IC — {invoice.number} / {src_label}",
            qty=Decimal("1"),
            unit="ea",
            rate=total,
            amount=total,
            tax_amount=ZERO,
        )
    )
    invoice.ic_mirror_bill_id = bill.id
    session.add(invoice)
    session.flush()
    return bill


def create_ic_mirror_invoice_from_bill(
    session: Session, source_user: User, bill: Bill,
) -> Optional[Invoice]:
    """Create a draft (no GL) Invoice on the counterparty for an IC bill."""
    if not bill.is_intercompany or not bill.ic_counterparty_tenant_id:
        return None
    if bill.ic_mirror_invoice_id:
        return session.get(Invoice, bill.ic_mirror_invoice_id)

    cp_tid = bill.ic_counterparty_tenant_id
    if not assert_ic_member(session, bill.tenant_id, cp_tid):
        raise IntercompanyError(
            "IC counterparty is not in the same consolidation group", 400
        )

    customer = get_or_create_ic_customer(session, cp_tid)
    src_label = _source_tenant_label(session, bill.tenant_id)
    total = money(bill.total)
    prefix = _setting(session, cp_tid, "invoice_prefix", "INV")
    fmt = _setting(session, cp_tid, "invoice_number_format", "") or None

    inv = Invoice(
        tenant_id=cp_tid,
        number=next_number(session, cp_tid, "invoice", prefix, fmt=fmt),
        customer_id=customer.id,
        customer_name=customer.name,
        issue_date=bill.bill_date,
        due_date=bill.due_date or bill.bill_date,
        description=f"IC mirror of {bill.number} ({src_label})",
        notes=bill.notes,
        internal_memo=f"Auto-mirrored from bill {bill.id} tenant {bill.tenant_id}",
        subtotal=total,
        gst_rate=ZERO,
        gst_amount=ZERO,
        total=total,
        currency=bill.currency or "USD",
        exchange_rate=D(bill.exchange_rate or 1),
        status="draft",
        created_by_id=source_user.id,
        is_intercompany=True,
        ic_counterparty_tenant_id=bill.tenant_id,
        ic_mirror_bill_id=bill.id,
    )
    session.add(inv)
    session.flush()

    session.add(
        InvoiceLine(
            invoice_id=inv.id,
            description=f"IC — {bill.number} / {src_label}",
            qty=Decimal("1"),
            unit="ea",
            rate=total,
            amount=total,
            tax_amount=ZERO,
        )
    )
    bill.ic_mirror_invoice_id = inv.id
    session.add(bill)
    session.flush()
    return inv


def list_counterparties(session: Session, tenant_id: int) -> list[dict]:
    """ConsolidationMember tenants available as IC counterparties for current tenant."""
    holdings = set(
        session.exec(
            select(ConsolidationMember.holding_tenant_id).where(
                ConsolidationMember.member_tenant_id == tenant_id,
                ConsolidationMember.is_active == True,  # noqa: E712
            )
        ).all()
    )
    # Also treat current tenant as a holding if it owns members
    as_holding = session.exec(
        select(ConsolidationMember.id).where(
            ConsolidationMember.holding_tenant_id == tenant_id,
            ConsolidationMember.is_active == True,  # noqa: E712
        )
    ).first()
    if as_holding is not None:
        holdings.add(tenant_id)

    if not holdings:
        return []

    members = session.exec(
        select(ConsolidationMember).where(
            col(ConsolidationMember.holding_tenant_id).in_(holdings),
            ConsolidationMember.is_active == True,  # noqa: E712
        )
    ).all()
    seen: set[int] = set()
    out: list[dict] = []
    for m in members:
        tid = m.member_tenant_id
        if tid == tenant_id or tid in seen:
            continue
        seen.add(tid)
        t = session.get(Tenant, tid)
        out.append({
            "tenant_id": tid,
            "name": (t.name if t else None) or f"Tenant {tid}",
            "holding_tenant_id": m.holding_tenant_id,
            "relationship": m.relationship,
        })
    out.sort(key=lambda r: r["name"].lower())
    return out


def _open_ic_ar(session: Session, from_tenant: int, to_tenant: int) -> Decimal:
    """Sum of posted unpaid IC invoices (from → to). Draft mirrors (no GL) excluded."""
    rows = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == from_tenant,
            Invoice.is_intercompany == True,  # noqa: E712
            Invoice.ic_counterparty_tenant_id == to_tenant,
            Invoice.transaction_id.is_not(None),  # type: ignore[attr-defined]
            col(Invoice.status).notin_(list(_OPEN_STATUSES_EXCLUDED)),
        )
    ).all()
    return money(sum((D(r.total) for r in rows), ZERO))


def _open_ic_ap(session: Session, from_tenant: int, to_tenant: int) -> Decimal:
    """Sum of posted unpaid IC bills on *to* tenant owed to *from* (AP mirror of AR)."""
    rows = session.exec(
        select(Bill).where(
            Bill.tenant_id == to_tenant,
            Bill.is_intercompany == True,  # noqa: E712
            Bill.ic_counterparty_tenant_id == from_tenant,
            Bill.transaction_id.is_not(None),  # type: ignore[attr-defined]
            col(Bill.status).notin_(list(_OPEN_STATUSES_EXCLUDED)),
        )
    ).all()
    return money(sum((D(r.total) for r in rows), ZERO))


def recon_report(
    session: Session,
    holding_tenant_id: int,
    *,
    skip: int = 0,
    limit: int = 50,
    q: str = "",
) -> dict:
    """IC AR vs AP by ConsolidationMember pair under the holding.

    Returns ``{total, items:[{from_tenant, to_tenant, ar_open, ap_open, variance, status}]}``.
    """
    members = session.exec(
        select(ConsolidationMember).where(
            ConsolidationMember.holding_tenant_id == holding_tenant_id,
            ConsolidationMember.is_active == True,  # noqa: E712
        )
    ).all()
    tenant_ids = sorted({m.member_tenant_id for m in members})
    if holding_tenant_id not in tenant_ids:
        tenant_ids = sorted(set(tenant_ids) | {holding_tenant_id})

    name_cache: dict[int, str] = {}

    def _name(tid: int) -> str:
        if tid not in name_cache:
            t = session.get(Tenant, tid)
            name_cache[tid] = (t.name if t else None) or f"Tenant {tid}"
        return name_cache[tid]

    items: list[dict] = []
    for a, b in combinations(tenant_ids, 2):
        for frm, to in ((a, b), (b, a)):
            ar = _open_ic_ar(session, frm, to)
            ap = _open_ic_ap(session, frm, to)
            # Skip empty pairs with no activity either side
            if ar == ZERO and ap == ZERO:
                continue
            variance = money(ar - ap)
            status = "matched" if abs(variance) < Decimal("0.01") else "break"
            row = {
                "from_tenant_id": frm,
                "to_tenant_id": to,
                "from_tenant": _name(frm),
                "to_tenant": _name(to),
                "ar_open": float(ar),
                "ap_open": float(ap),
                "variance": float(variance),
                "status": status,
            }
            items.append(row)

    if q:
        ql = q.lower().strip()
        items = [
            r for r in items
            if ql in r["from_tenant"].lower()
            or ql in r["to_tenant"].lower()
            or ql in r["status"]
        ]

    items.sort(key=lambda r: (r["status"] != "break", r["from_tenant"], r["to_tenant"]))
    total = len(items)
    page = items[skip : skip + limit]
    return {"total": total, "items": page}
