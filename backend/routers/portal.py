"""Customer/vendor magic-link portal (#120)."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import select

from models import (
    Bill, BillPayment, Customer, Invoice, InvoiceLine, PortalDispute, PortalToken,
    PurchaseOrder, Settings, Tenant, Vendor,
)
from services.alerts import emit_alert, _staff_users, STAFF_ROLES
from services.portal_pay import apply_checkout_payment
from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/portal", tags=["portal"])


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mint_portal_token(
    session, tenant_id: int, entity_type: str, entity_id: int, days: int = 90,
    permissions: list | None = None,
) -> str:
    raw = secrets.token_urlsafe(32)
    if permissions is None:
        if entity_type == "patient":
            permissions = ["view_lab_reports"]
        elif entity_type == "vendor":
            permissions = ["view_bills"]
        else:
            permissions = ["view_invoices", "pay"]
    row = PortalToken(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        token_hash=_hash(raw),
        expires_at=datetime.utcnow() + timedelta(days=days),
        permissions=permissions,
    )
    session.add(row)
    session.commit()
    return raw


def _resolve(session, token: str) -> PortalToken:
    row = session.exec(
        select(PortalToken).where(PortalToken.token_hash == _hash(token))
    ).first()
    if not row or row.expires_at < datetime.utcnow():
        raise HTTPException(404, "Invalid or expired portal link")
    row.last_accessed = datetime.utcnow()
    session.add(row)
    session.commit()
    return row


@router.post("/mint")
def mint(session: SessionDep, user: WriteUserDep, entity_type: str, entity_id: int):
    if entity_type not in ("customer", "vendor", "patient"):
        raise HTTPException(400, "entity_type must be customer, vendor, or patient")
    if entity_type == "patient":
        from models_healthcare import HcPatient
        p = session.get(HcPatient, entity_id)
        if not p or p.tenant_id != user.tenant_id:
            raise HTTPException(404, "Patient not found")
    raw = mint_portal_token(session, user.tenant_id, entity_type, entity_id)
    settings = {
        s.key: s.value
        for s in session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id)).all()
    }
    import os
    custom = (settings.get("portal_custom_domain") or "").strip().rstrip("/")
    if custom:
        if not custom.startswith("http"):
            custom = f"https://{custom}"
        base = custom
    else:
        base = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").rstrip("/")
    path = f"/portal/{raw}"
    return {"token": raw, "path": path, "url": f"{base}{path}"}


@router.get("/{token}")
def portal_home(token: str, session: SessionDep):
    pt = _resolve(session, token)
    tenant = session.get(Tenant, pt.tenant_id)
    settings = {
        s.key: s.value
        for s in session.exec(select(Settings).where(Settings.tenant_id == pt.tenant_id)).all()
    }
    entity_name = None
    if pt.entity_type == "customer":
        cust = session.get(Customer, pt.entity_id)
        entity_name = cust.name if cust else None
    elif pt.entity_type == "vendor":
        vend = session.get(Vendor, pt.entity_id)
        entity_name = vend.name if vend else None
    elif pt.entity_type == "patient":
        from models_healthcare import HcPatient
        patient = session.get(HcPatient, pt.entity_id)
        entity_name = patient.name if patient else None
    return {
        "tenant_name": tenant.name if tenant else "",
        "company_name": settings.get("company_name", tenant.name if tenant else ""),
        "business_tagline": settings.get("business_tagline", ""),
        "logo_url": settings.get("logo_url") or None,
        "entity_type": pt.entity_type,
        "entity_name": entity_name,
        "permissions": pt.permissions or [],
        "portal_custom_domain": settings.get("portal_custom_domain") or None,
    }


@router.get("/{token}/invoices")
def portal_invoices(token: str, session: SessionDep):
    pt = _resolve(session, token)
    if pt.entity_type != "customer":
        raise HTTPException(400, "Invoices only available for customer portals")
    rows = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == pt.tenant_id,
            Invoice.customer_id == pt.entity_id,
            Invoice.status.in_(["sent", "overdue", "partial", "unpaid", "posted"]),  # type: ignore
        ).order_by(Invoice.issue_date.desc())  # type: ignore
    ).all()
    # Fallback if status filter too strict — show non-draft/void
    if not rows:
        rows = session.exec(
            select(Invoice).where(
                Invoice.tenant_id == pt.tenant_id,
                Invoice.customer_id == pt.entity_id,
            ).order_by(Invoice.id.desc())  # type: ignore
        ).all()
        rows = [r for r in rows if r.status not in ("draft", "void", "voided")]
    return [
        {
            "id": r.id, "number": r.number, "issue_date": r.issue_date,
            "due_date": r.due_date, "total": float(r.total), "status": r.status,
            "currency": r.currency,
            "payment_link_status": r.payment_link_status,
        }
        for r in rows
    ]


@router.get("/{token}/invoices/{invoice_id}/pdf")
def portal_invoice_pdf(token: str, invoice_id: int, session: SessionDep):
    pt = _resolve(session, token)
    inv = session.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != pt.tenant_id or inv.customer_id != pt.entity_id:
        raise HTTPException(404, "Invoice not found")
    lines = session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)).all()
    settings = {
        s.key: s.value
        for s in session.exec(select(Settings).where(Settings.tenant_id == pt.tenant_id)).all()
    }
    from services.pdf import PdfEngineError, pdf_http, render_invoice_pdf
    try:
        pdf = render_invoice_pdf(
            inv.model_dump(), [ln.model_dump() for ln in lines],
            settings.get("company_name", ""), settings.get("business_tagline", ""),
            logo_url=settings.get("logo_url") or "",
        )
    except PdfEngineError as e:
        raise pdf_http(e) from e
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{inv.number}.pdf"'},
    )


@router.get("/{token}/lab-orders")
def portal_lab_orders(token: str, session: SessionDep):
    """Resulted/delivered lab orders for a patient portal token."""
    from models_healthcare import HcLabOrder

    pt = _resolve(session, token)
    if pt.entity_type != "patient":
        raise HTTPException(400, "Lab orders only available for patient portals")
    rows = session.exec(
        select(HcLabOrder).where(
            HcLabOrder.tenant_id == pt.tenant_id,
            HcLabOrder.patient_id == pt.entity_id,
            HcLabOrder.status.in_(["resulted", "delivered"]),  # type: ignore
        ).order_by(HcLabOrder.order_date.desc(), HcLabOrder.id.desc())  # type: ignore
    ).all()
    return [
        {
            "id": r.id,
            "order_number": r.order_number,
            "order_date": r.order_date,
            "status": r.status,
            "source": r.source,
        }
        for r in rows
    ]


@router.get("/{token}/lab-orders/{order_id}/pdf")
def portal_lab_order_pdf(token: str, order_id: int, session: SessionDep):
    from models_healthcare import HcLabOrder
    from routers.healthcare import _company_branding, _lab_pdf_context
    from services.pdf import PdfEngineError, pdf_http, render_lab_report_pdf

    pt = _resolve(session, token)
    if pt.entity_type != "patient":
        raise HTTPException(400, "Lab PDFs only available for patient portals")
    order = session.get(HcLabOrder, order_id)
    if (
        not order
        or order.tenant_id != pt.tenant_id
        or order.patient_id != pt.entity_id
        or order.status not in ("resulted", "delivered")
    ):
        raise HTTPException(404, "Lab order not found")
    report = _lab_pdf_context(session, order)
    company, tagline = _company_branding(session, pt.tenant_id)
    try:
        pdf = render_lab_report_pdf(report, company, tagline)
    except PdfEngineError as e:
        raise pdf_http(e) from e
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{order.order_number}.pdf"'},
    )


@router.get("/{token}/bills")
def portal_bills(token: str, session: SessionDep):
    """Open bills for a vendor portal token (#214)."""
    pt = _resolve(session, token)
    if pt.entity_type != "vendor":
        raise HTTPException(400, "Bills only available for vendor portals")
    rows = session.exec(
        select(Bill).where(
            Bill.tenant_id == pt.tenant_id,
            Bill.vendor_id == pt.entity_id,
        ).order_by(Bill.bill_date.desc())  # type: ignore
    ).all()
    rows = [r for r in rows if r.status not in ("draft", "void", "voided", "reversed")]
    return [
        {
            "id": r.id, "number": r.number, "bill_date": r.bill_date,
            "due_date": r.due_date, "total": float(r.total), "status": r.status,
            "currency": r.currency,
        }
        for r in rows
    ]


@router.get("/{token}/statement")
def portal_vendor_statement(token: str, session: SessionDep):
    """Lightweight vendor statement: open bills + recent bill payments (#214)."""
    pt = _resolve(session, token)
    if pt.entity_type != "vendor":
        raise HTTPException(400, "Statement only available for vendor portals")
    bills = session.exec(
        select(Bill).where(
            Bill.tenant_id == pt.tenant_id,
            Bill.vendor_id == pt.entity_id,
        ).order_by(Bill.bill_date.desc())  # type: ignore
    ).all()
    open_bills = [
        b for b in bills
        if b.status not in ("draft", "void", "voided", "reversed", "paid")
    ]
    bill_ids = [b.id for b in bills if b.id is not None]
    payments = []
    if bill_ids:
        payments = session.exec(
            select(BillPayment).where(
                BillPayment.tenant_id == pt.tenant_id,
                BillPayment.bill_id.in_(bill_ids),  # type: ignore
            ).order_by(BillPayment.payment_date.desc()).limit(50)  # type: ignore
        ).all()
    outstanding = sum(float(b.total or 0) for b in open_bills)
    return {
        "entity_type": "vendor",
        "outstanding": outstanding,
        "open_bills": [
            {
                "id": b.id, "number": b.number, "bill_date": b.bill_date,
                "due_date": b.due_date, "total": float(b.total), "status": b.status,
                "currency": b.currency,
            }
            for b in open_bills
        ],
        "payments": [
            {
                "id": p.id, "bill_id": p.bill_id, "payment_date": p.payment_date,
                "amount": float(p.amount), "method": p.method, "reference": p.reference,
            }
            for p in payments
        ],
    }


class PayBody(BaseModel):
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class DisputeIn(BaseModel):
    body: str


class SimulatePayBody(BaseModel):
    """Test/demo helper when Stripe is unset — still idempotent on checkout_session_id."""
    checkout_session_id: str
    amount: Optional[float] = None


@router.post("/{token}/invoices/{invoice_id}/pay")
def portal_pay(token: str, invoice_id: int, session: SessionDep, body: PayBody | None = None):
    pt = _resolve(session, token)
    if pt.entity_type != "customer":
        raise HTTPException(400, "Pay is only available on customer portals")
    if "pay" not in (pt.permissions or ["pay"]):
        raise HTTPException(403, "This portal link cannot pay invoices")
    inv = session.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != pt.tenant_id or inv.customer_id != pt.entity_id:
        raise HTTPException(404, "Invoice not found")
    if inv.status == "paid":
        raise HTTPException(400, "Invoice is already paid")
    import os
    secret = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        return {
            "ok": False,
            "mode": "offline",
            "message": "Stripe not configured — contact the company to pay, or use simulate-pay in demo",
            "checkout_url": None,
        }
    import stripe
    stripe.api_key = secret
    front = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").rstrip("/")
    settings = {
        s.key: s.value
        for s in session.exec(select(Settings).where(Settings.tenant_id == pt.tenant_id)).all()
    }
    custom = (settings.get("portal_custom_domain") or "").strip().rstrip("/")
    if custom:
        if not custom.startswith("http"):
            custom = f"https://{custom}"
        front = custom
    body = body or PayBody()
    session_obj = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": (inv.currency or "usd").lower(),
                "product_data": {"name": f"Invoice {inv.number}"},
                "unit_amount": int(float(inv.total) * 100),
            },
            "quantity": 1,
        }],
        success_url=body.success_url or f"{front}/portal/{token}?paid=1&invoice={inv.id}",
        cancel_url=body.cancel_url or f"{front}/portal/{token}",
        metadata={
            "invoice_id": str(inv.id),
            "tenant_id": str(inv.tenant_id),
            "source": "portal",
            "portal_token_hash": pt.token_hash[:16],
        },
    )
    inv.payment_link_url = session_obj.url
    inv.payment_link_status = "unpaid"
    session.add(inv)
    session.commit()
    return {"ok": True, "mode": "stripe", "checkout_url": session_obj.url}


@router.post("/{token}/invoices/{invoice_id}/simulate-pay")
def portal_simulate_pay(
    token: str, invoice_id: int, body: SimulatePayBody, session: SessionDep,
):
    """Apply a portal payment without Stripe (tests + offline demo).

    Only available when STRIPE_SECRET_KEY is unset — production Stripe tenants
    must use the webhook path.
    """
    import os
    if os.environ.get("STRIPE_SECRET_KEY", "").strip():
        raise HTTPException(400, "simulate-pay disabled while Stripe is configured")
    pt = _resolve(session, token)
    if pt.entity_type != "customer":
        raise HTTPException(400, "Pay is only available on customer portals")
    inv = session.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != pt.tenant_id or inv.customer_id != pt.entity_id:
        raise HTTPException(404, "Invoice not found")
    from decimal import Decimal
    try:
        result = apply_checkout_payment(
            session,
            tenant_id=pt.tenant_id,
            invoice_id=inv.id,
            checkout_session_id=body.checkout_session_id,
            amount=Decimal(str(body.amount)) if body.amount is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    session.commit()
    return result


@router.post("/{token}/invoices/{invoice_id}/disputes", status_code=201)
def portal_create_dispute(
    token: str, invoice_id: int, body: DisputeIn, session: SessionDep,
):
    pt = _resolve(session, token)
    if pt.entity_type != "customer":
        raise HTTPException(400, "Disputes only available for customer portals")
    if not (body.body or "").strip():
        raise HTTPException(400, "Dispute note is required")
    inv = session.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != pt.tenant_id or inv.customer_id != pt.entity_id:
        raise HTTPException(404, "Invoice not found")
    row = PortalDispute(
        tenant_id=pt.tenant_id,
        invoice_id=inv.id,
        customer_id=pt.entity_id,
        body=body.body.strip()[:4000],
        status="open",
    )
    session.add(row)
    session.flush()
    staff = _staff_users(session, pt.tenant_id, STAFF_ROLES)
    for u in staff:
        emit_alert(
            session,
            tenant_id=pt.tenant_id,
            user_id=u.id,
            kind="invoice_dispute",
            severity="warning",
            title=f"Dispute on invoice {inv.number}",
            body=body.body.strip()[:240],
            href=f"/invoices/{inv.id}",
            entity_type="invoice",
            entity_id=inv.id,
            dedupe_key=f"dispute:inv:{inv.id}:d:{row.id}",
        )
    session.commit()
    session.refresh(row)
    return row.model_dump()


@router.get("/{token}/invoices/{invoice_id}/disputes")
def portal_list_disputes(token: str, invoice_id: int, session: SessionDep):
    pt = _resolve(session, token)
    if pt.entity_type != "customer":
        raise HTTPException(400, "Disputes only available for customer portals")
    inv = session.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != pt.tenant_id or inv.customer_id != pt.entity_id:
        raise HTTPException(404, "Invoice not found")
    rows = session.exec(
        select(PortalDispute).where(
            PortalDispute.tenant_id == pt.tenant_id,
            PortalDispute.invoice_id == inv.id,
        ).order_by(PortalDispute.id.desc())  # type: ignore
    ).all()
    return [r.model_dump() for r in rows]


@router.get("/{token}/purchase-orders")
def portal_vendor_pos(token: str, session: SessionDep):
    """Vendor portal: PO status list (#270 parity)."""
    pt = _resolve(session, token)
    if pt.entity_type != "vendor":
        raise HTTPException(400, "Purchase orders only available for vendor portals")
    rows = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.tenant_id == pt.tenant_id,
            PurchaseOrder.vendor_id == pt.entity_id,
        ).order_by(PurchaseOrder.id.desc())  # type: ignore
    ).all()
    rows = [r for r in rows if r.status not in ("cancelled",)]
    return [
        {
            "id": r.id,
            "number": r.number,
            "order_date": getattr(r, "order_date", None) or getattr(r, "po_date", None),
            "status": r.status,
            "total": float(getattr(r, "total", 0) or 0),
        }
        for r in rows
    ]
