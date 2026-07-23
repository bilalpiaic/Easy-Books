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

from models import Customer, Invoice, InvoiceLine, PortalToken, Settings, Tenant
from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/portal", tags=["portal"])


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mint_portal_token(
    session, tenant_id: int, entity_type: str, entity_id: int, days: int = 90
) -> str:
    raw = secrets.token_urlsafe(32)
    row = PortalToken(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        token_hash=_hash(raw),
        expires_at=datetime.utcnow() + timedelta(days=days),
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
    if entity_type not in ("customer", "vendor"):
        raise HTTPException(400, "entity_type must be customer or vendor")
    raw = mint_portal_token(session, user.tenant_id, entity_type, entity_id)
    return {"token": raw, "path": f"/portal/{raw}"}


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
    return {
        "tenant_name": tenant.name if tenant else "",
        "company_name": settings.get("company_name", tenant.name if tenant else ""),
        "entity_type": pt.entity_type,
        "entity_name": entity_name,
        "permissions": pt.permissions or [],
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
    from services.pdf import render_invoice_pdf
    pdf = render_invoice_pdf(
        inv.model_dump(), [ln.model_dump() for ln in lines],
        settings.get("company_name", ""), settings.get("business_tagline", ""),
    )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{inv.number}.pdf"'},
    )


class PayBody(BaseModel):
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@router.post("/{token}/invoices/{invoice_id}/pay")
def portal_pay(token: str, invoice_id: int, session: SessionDep, body: PayBody | None = None):
    pt = _resolve(session, token)
    inv = session.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != pt.tenant_id or inv.customer_id != pt.entity_id:
        raise HTTPException(404, "Invoice not found")
    import os
    secret = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        return {
            "ok": False,
            "mode": "offline",
            "message": "Stripe not configured — contact the company to pay",
            "checkout_url": None,
        }
    import stripe
    stripe.api_key = secret
    front = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").rstrip("/")
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
        success_url=body.success_url or f"{front}/portal/{token}?paid=1",
        cancel_url=body.cancel_url or f"{front}/portal/{token}",
        metadata={"invoice_id": str(inv.id), "tenant_id": str(inv.tenant_id)},
    )
    inv.payment_link_url = session_obj.url
    inv.payment_link_status = "unpaid"
    session.add(inv)
    session.commit()
    return {"ok": True, "mode": "stripe", "checkout_url": session_obj.url}
