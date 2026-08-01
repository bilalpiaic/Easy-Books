"""UAE VAT / FTA e-Invoice endpoints (localization pack).

POST /api/uae/test                          — sandbox stub ping (needs TRN)
GET  /api/uae/invoices/{invoice_id}/status  — latest log for an invoice
POST /api/uae/invoices/{invoice_id}/submit  — stub (or future live) submit
GET  /api/uae/logs                          — UaeEinvoiceLog listing
"""
from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from models import Invoice, UaeEinvoiceLog
from routers.common import CurrentUserDep, SessionDep
from services.permissions import perm_dep
from services.uae_einvoice import get_uae_config, submit_to_uae

uae_router = APIRouter(prefix="/uae", tags=["uae"], dependencies=[perm_dep("invoices")])


@uae_router.post("/test", dependencies=[perm_dep("invoices", "edit")])
def test_uae_connection(user: CurrentUserDep, session: SessionDep):
    """Verify Settings TRN + sandbox stub path (no live FTA call)."""
    config = get_uae_config(session, user.tenant_id)
    if not config:
        raise HTTPException(400, "UAE VAT is not enabled or TRN is missing in Settings.")
    if not config["sandbox"]:
        return {
            "ok": False,
            "sandbox": False,
            "message": "Production connector not wired — enable sandbox mode to test the stub.",
            "endpoint": config["endpoint"],
            "trn": config["trn"],
        }
    return {
        "ok": True,
        "sandbox": True,
        "message": "Sandbox stub ready — submissions will mint a synthetic UUID.",
        "endpoint": config["endpoint"],
        "trn": config["trn"],
    }


@uae_router.get("/invoices/{invoice_id}/status")
def get_invoice_uae_status(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    log = session.exec(
        select(UaeEinvoiceLog)
        .where(
            UaeEinvoiceLog.tenant_id == user.tenant_id,
            UaeEinvoiceLog.invoice_id == invoice_id,
        )
        .order_by(UaeEinvoiceLog.attempt_at.desc())  # type: ignore[attr-defined]
    ).first()
    if not log:
        return {
            "invoice_id": invoice.id,
            "status": "not_submitted",
            "uuid": None,
            "success": None,
        }
    return {
        "invoice_id": invoice.id,
        "status": "submitted" if log.success else "failed",
        "uuid": log.response_uuid,
        "success": log.success,
        "attempt_at": log.attempt_at,
        "error_message": log.error_message,
        "sandbox": log.sandbox,
    }


@uae_router.post("/invoices/{invoice_id}/submit", dependencies=[perm_dep("invoices", "edit")])
def submit_uae_invoice(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    log = submit_to_uae(session, invoice)
    return {
        "invoice_id": invoice.id,
        "success": log.success,
        "uuid": log.response_uuid,
        "sandbox": log.sandbox,
        "error_message": log.error_message,
        "log_id": log.id,
    }


@uae_router.get("/logs")
def list_uae_logs(
    user: CurrentUserDep,
    session: SessionDep,
    limit: int = Query(100, ge=1, le=500),
):
    rows = session.exec(
        select(UaeEinvoiceLog)
        .where(UaeEinvoiceLog.tenant_id == user.tenant_id)
        .order_by(UaeEinvoiceLog.attempt_at.desc())  # type: ignore[attr-defined]
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "invoice_id": r.invoice_id,
            "attempt_at": r.attempt_at,
            "endpoint": r.endpoint,
            "http_status": r.http_status,
            "response_uuid": r.response_uuid,
            "success": r.success,
            "error_message": r.error_message,
            "sandbox": r.sandbox,
        }
        for r in rows
    ]
