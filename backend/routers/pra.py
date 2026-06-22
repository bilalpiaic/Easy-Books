"""PRA e-Invoice management endpoints.

POST /api/pra/test                          — verify credentials (sandbox ping)
GET  /api/pra/invoices/{invoice_id}/status  — pra_status + fiscal_number
POST /api/pra/invoices/{invoice_id}/submit  — manual retry
GET  /api/pra/logs                          — PRASubmissionLog listing
"""
import json
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from models import Invoice, PRASubmissionLog
from routers.common import CurrentUserDep, SessionDep
from services.pra import get_pra_config, submit_to_pra
from services.permissions import perm_dep, apply_own_filter

pra_router = APIRouter(prefix="/pra", tags=["pra"], dependencies=[perm_dep("invoices")])


@pra_router.post("/test", dependencies=[perm_dep("invoices", "edit")])
def test_pra_connection(user: CurrentUserDep, session: SessionDep):
    """Send a minimal test payload to PRA sandbox to verify credentials."""
    config = get_pra_config(session, user.tenant_id)
    if not config:
        raise HTTPException(400, "PRA is not enabled or POS ID is missing in Settings.")

    test_payload = {
        "InvoiceNumber": "", "POSID": int(config["pos_id"]),
        "USIN": "TEST-001", "DateTime": "2020-01-01 00:00:00",
        "BuyerName": "", "BuyerPNTN": "", "BuyerCNIC": "",
        "BuyerPhoneNumber": "", "TotalBillAmount": 0.0, "TotalQuantity": 0.0,
        "TotalSaleValue": 0.0, "TotalTaxCharged": 0.0, "Discount": 0.0,
        "FurtherTax": 0.0, "PaymentMode": 1, "RefUSIN": None, "InvoiceType": 1,
        "Items": [],
    }
    try:
        resp = httpx.post(
            config["endpoint"],
            content=json.dumps(test_payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config['token']}",
            },
            timeout=10.0,
        )
        data = resp.json()
        return {
            "http_status": resp.status_code,
            "pra_code": data.get("Code"),
            "pra_response": data.get("Response"),
            "sandbox": config["sandbox"],
            "endpoint": config["endpoint"],
        }
    except Exception as exc:
        raise HTTPException(502, f"Could not reach PRA API: {exc}")


@pra_router.get("/invoices/{invoice_id}/status")
def get_invoice_pra_status(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return {
        "invoice_id": invoice.id,
        "pra_status": invoice.pra_status,
        "pra_fiscal_number": invoice.pra_fiscal_number,
        "pra_usin": invoice.pra_usin,
        "pra_submitted_at": invoice.pra_submitted_at,
    }


@pra_router.post("/invoices/{invoice_id}/submit", dependencies=[perm_dep("invoices", "edit")])
def retry_pra_submission(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    """Manually (re-)submit an invoice to PRA. Safe to retry."""
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not get_pra_config(session, user.tenant_id):
        raise HTTPException(400, "PRA is not enabled or configured in Settings.")
    # Set USIN if not already stamped
    if not invoice.pra_usin:
        invoice.pra_usin = invoice.number
        session.add(invoice)
        session.commit()
    success = submit_to_pra(session, invoice_id)
    return {
        "success": success,
        "pra_status": invoice.pra_status,
        "pra_fiscal_number": invoice.pra_fiscal_number,
    }


@pra_router.get("/logs")
def list_pra_logs(
    user: CurrentUserDep,
    session: SessionDep,
    invoice_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
):
    # Join through Invoice so that my_data_only users only see logs for their own invoices
    inv_q = select(Invoice).where(Invoice.tenant_id == user.tenant_id)
    inv_q = apply_own_filter(inv_q, Invoice, user, session)
    allowed_invoice_ids = [r.id for r in session.exec(inv_q).all()]

    q = select(PRASubmissionLog).where(
        PRASubmissionLog.tenant_id == user.tenant_id,
        PRASubmissionLog.invoice_id.in_(allowed_invoice_ids),  # type: ignore[attr-defined]
    )
    if invoice_id:
        q = q.where(PRASubmissionLog.invoice_id == invoice_id)
    q = q.order_by(PRASubmissionLog.attempt_at.desc()).limit(limit)  # type: ignore[attr-defined]
    logs = session.exec(q).all()
    return [
        {
            "id": l.id,
            "invoice_id": l.invoice_id,
            "attempt_at": l.attempt_at,
            "endpoint": l.endpoint,
            "http_status": l.http_status,
            "response_code": l.response_code,
            "success": l.success,
            "error_message": l.error_message,
        }
        for l in logs
    ]
