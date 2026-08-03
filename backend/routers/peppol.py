"""Peppol / EU VAT e-Invoice endpoints (#266).

POST /api/peppol/test                          — verify AP credentials / reachability
GET  /api/peppol/invoices/{invoice_id}/status  — peppol_* fields on the invoice
POST /api/peppol/invoices/{invoice_id}/submit  — POST UBL to Access Point
GET  /api/peppol/invoices/{invoice_id}/export  — download BIS Billing 3.0 UBL XML
GET  /api/peppol/logs                          — PeppolSubmissionLog listing
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlmodel import select

from models import Invoice, PeppolSubmissionLog, Tenant
from routers.common import CurrentUserDep, SessionDep
from routers.modules import _get_enabled
from services.permissions import perm_dep
from services.peppol import export_ubl_xml, get_peppol_config, submit_to_peppol

peppol_router = APIRouter(prefix="/peppol", tags=["peppol"], dependencies=[perm_dep("invoices")])


def _require_peppol_module(user: CurrentUserDep, session: SessionDep) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "eu_peppol" not in _get_enabled(tenant):
        raise HTTPException(
            status_code=403,
            detail="The Peppol / EU VAT e-Invoice module is not installed. Install it from System → Apps.",
        )


@peppol_router.post("/test", dependencies=[Depends(_require_peppol_module), perm_dep("invoices", "edit")])
def test_peppol_connection(user: CurrentUserDep, session: SessionDep):
    """Probe the Access Point URL to verify credentials / reachability."""
    config = get_peppol_config(session, user.tenant_id)
    if not config:
        raise HTTPException(
            400,
            "Peppol is not enabled or participant ID / Access Point URL is missing in Settings.",
        )

    try:
        with httpx.Client(timeout=10.0) as client:
            headers = {
                "Content-Type": "application/xml",
                "Accept": "application/json, application/xml, text/plain",
                "X-Peppol-Participant-ID": config["participant_id"],
            }
            if config.get("api_key"):
                headers["Authorization"] = f"Bearer {config['api_key']}"
            # Minimal probe body — any HTTP response proves reachability
            resp = client.post(
                config["ap_url"],
                content=b'<?xml version="1.0"?><Probe/>',
                headers=headers,
            )
        return {
            "ok": True,
            "sandbox": config["sandbox"],
            "http_status": resp.status_code,
            "message": f"Access Point reachable (HTTP {resp.status_code})",
            "endpoint": config["ap_url"],
            "participant_id": config["participant_id"],
        }
    except Exception as exc:
        raise HTTPException(502, f"Could not reach Peppol Access Point: {exc}") from exc


@peppol_router.get(
    "/invoices/{invoice_id}/status",
    dependencies=[Depends(_require_peppol_module)],
)
def get_invoice_peppol_status(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return {
        "invoice_id": invoice.id,
        "peppol_status": invoice.peppol_status,
        "peppol_document_id": invoice.peppol_document_id,
        "peppol_submitted_at": invoice.peppol_submitted_at,
    }


@peppol_router.post(
    "/invoices/{invoice_id}/submit",
    dependencies=[Depends(_require_peppol_module), perm_dep("invoices", "edit")],
)
def submit_peppol_invoice(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not get_peppol_config(session, user.tenant_id):
        raise HTTPException(
            400,
            "Peppol is not enabled or participant ID / Access Point URL is missing in Settings.",
        )
    return submit_to_peppol(session, user, invoice_id)


@peppol_router.get(
    "/invoices/{invoice_id}/export",
    dependencies=[Depends(_require_peppol_module)],
)
def export_peppol_xml(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    """Download Peppol BIS Billing 3.0 UBL Invoice XML."""
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    xml_body, err = export_ubl_xml(session, user, invoice_id)
    if err or not xml_body:
        raise HTTPException(400, err or "Could not build UBL XML")
    filename = f"{invoice.number}-peppol.xml".replace("/", "-")
    return Response(
        content=xml_body,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@peppol_router.get("/logs", dependencies=[Depends(_require_peppol_module)])
def list_peppol_logs(
    user: CurrentUserDep,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    invoice_id: int | None = Query(None),
):
    q = select(PeppolSubmissionLog).where(PeppolSubmissionLog.tenant_id == user.tenant_id)
    if invoice_id is not None:
        q = q.where(PeppolSubmissionLog.invoice_id == invoice_id)
    q = q.order_by(PeppolSubmissionLog.created_at.desc()).offset(skip).limit(limit)  # type: ignore[attr-defined]
    rows = session.exec(q).all()
    return [
        {
            "id": r.id,
            "invoice_id": r.invoice_id,
            "created_at": r.created_at,
            "status": r.status,
            "http_status": r.http_status,
            "endpoint": r.endpoint,
            "error_message": r.error_message,
            "sandbox": r.sandbox,
            "document_id": r.document_id,
        }
        for r in rows
    ]
