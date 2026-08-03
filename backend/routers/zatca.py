"""Saudi ZATCA e-Invoice endpoints (#264).

POST /api/zatca/test                          — verify credentials / sandbox reachability
GET  /api/zatca/invoices/{invoice_id}/status  — zatca_* fields on the invoice
POST /api/zatca/invoices/{invoice_id}/submit  — sandbox clear/report submit
GET  /api/zatca/logs                          — ZatcaSubmissionLog listing
"""
from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from models import Invoice, Tenant, ZatcaSubmissionLog
from routers.common import CurrentUserDep, SessionDep
from routers.modules import _get_enabled
from services.permissions import perm_dep
from services.zatca import get_zatca_config, submit_to_zatca

zatca_router = APIRouter(prefix="/zatca", tags=["zatca"], dependencies=[perm_dep("invoices")])


def _require_zatca_module(user: CurrentUserDep, session: SessionDep) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "sa_zatca" not in _get_enabled(tenant):
        raise HTTPException(
            status_code=403,
            detail="The Saudi ZATCA e-Invoice module is not installed. Install it from System → Apps.",
        )


@zatca_router.post("/test", dependencies=[Depends(_require_zatca_module), perm_dep("invoices", "edit")])
def test_zatca_connection(user: CurrentUserDep, session: SessionDep):
    """Ping sandbox endpoint (or validate config) to verify credentials."""
    config = get_zatca_config(session, user.tenant_id)
    if not config:
        raise HTTPException(400, "ZATCA is not enabled or VAT number is missing in Settings.")

    if not config["sandbox"]:
        return {
            "ok": False,
            "sandbox": False,
            "message": "Production clearance path requires a live CSID — enable sandbox mode to test.",
            "endpoint": config["endpoint"],
            "vat_number": config["vat_number"],
        }

    # Lightweight HEAD/GET-style probe: POST a minimal empty body and accept
    # any HTTP response (auth errors still prove reachability).
    try:
        with httpx.Client(timeout=10.0) as client:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if config.get("csid_token"):
                headers["Authorization"] = f"Basic {config['csid_token']}"
            resp = client.post(
                config["endpoint"],
                content=json.dumps({"probe": True}),
                headers=headers,
            )
        return {
            "ok": True,
            "sandbox": True,
            "http_status": resp.status_code,
            "message": f"Sandbox reachable (HTTP {resp.status_code})",
            "endpoint": config["endpoint"],
            "vat_number": config["vat_number"],
        }
    except Exception as exc:
        raise HTTPException(502, f"Could not reach ZATCA sandbox: {exc}") from exc


@zatca_router.get(
    "/invoices/{invoice_id}/status",
    dependencies=[Depends(_require_zatca_module)],
)
def get_invoice_zatca_status(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return {
        "invoice_id": invoice.id,
        "zatca_status": invoice.zatca_status,
        "zatca_uuid": invoice.zatca_uuid,
        "zatca_hash": invoice.zatca_hash,
        "zatca_qr": invoice.zatca_qr,
        "zatca_submitted_at": invoice.zatca_submitted_at,
    }


@zatca_router.post(
    "/invoices/{invoice_id}/submit",
    dependencies=[Depends(_require_zatca_module), perm_dep("invoices", "edit")],
)
def submit_zatca_invoice(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not get_zatca_config(session, user.tenant_id):
        raise HTTPException(400, "ZATCA is not enabled or VAT number is missing in Settings.")
    return submit_to_zatca(session, user, invoice_id)


@zatca_router.get("/logs", dependencies=[Depends(_require_zatca_module)])
def list_zatca_logs(
    user: CurrentUserDep,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    invoice_id: int | None = Query(None),
):
    q = select(ZatcaSubmissionLog).where(ZatcaSubmissionLog.tenant_id == user.tenant_id)
    if invoice_id is not None:
        q = q.where(ZatcaSubmissionLog.invoice_id == invoice_id)
    q = q.order_by(ZatcaSubmissionLog.created_at.desc()).offset(skip).limit(limit)  # type: ignore[attr-defined]
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
        }
        for r in rows
    ]
