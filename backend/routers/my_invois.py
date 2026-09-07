"""Malaysia MyInvois e-Invoice endpoints (#306).

POST /api/my-invois/test                          — verify credentials / sandbox reachability
GET  /api/my-invois/invoices/{invoice_id}/status  — my_invois_* fields on the invoice
POST /api/my-invois/invoices/{invoice_id}/submit  — sandbox document submit
GET  /api/my-invois/logs                          — MyInvoisSubmissionLog listing
"""
from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from models import Invoice, Tenant, MyInvoisSubmissionLog
from routers.common import CurrentUserDep, SessionDep
from routers.modules import _get_enabled
from services.permissions import perm_dep
from services.my_invois import get_my_invois_config, submit_to_my_invois

my_invois_router = APIRouter(
    prefix="/my-invois", tags=["my-invois"], dependencies=[perm_dep("invoices")],
)


def _require_my_invois_module(user: CurrentUserDep, session: SessionDep) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "my_invois" not in _get_enabled(tenant):
        raise HTTPException(
            status_code=403,
            detail="The Malaysia MyInvois module is not installed. Install it from System → Apps.",
        )


@my_invois_router.post(
    "/test",
    dependencies=[Depends(_require_my_invois_module), perm_dep("invoices", "edit")],
)
def test_my_invois_connection(user: CurrentUserDep, session: SessionDep):
    config = get_my_invois_config(session, user.tenant_id)
    if not config:
        raise HTTPException(400, "MyInvois is not enabled or TIN is missing in Settings.")

    if not config["sandbox"]:
        return {
            "ok": False,
            "sandbox": False,
            "message": "Production MyInvois path requires a live client secret — enable sandbox mode to test.",
            "endpoint": config["endpoint"],
            "tin": config["tin"],
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if config.get("client_secret"):
                headers["Authorization"] = f"Bearer {config['client_secret']}"
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
            "tin": config["tin"],
        }
    except Exception as exc:
        raise HTTPException(502, f"Could not reach MyInvois sandbox: {exc}") from exc


@my_invois_router.get(
    "/invoices/{invoice_id}/status",
    dependencies=[Depends(_require_my_invois_module)],
)
def get_invoice_my_invois_status(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return {
        "invoice_id": invoice.id,
        "my_invois_status": invoice.my_invois_status,
        "my_invois_uuid": invoice.my_invois_uuid,
        "my_invois_submitted_at": invoice.my_invois_submitted_at,
    }


@my_invois_router.post(
    "/invoices/{invoice_id}/submit",
    dependencies=[Depends(_require_my_invois_module), perm_dep("invoices", "edit")],
)
def submit_my_invois_invoice(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not get_my_invois_config(session, user.tenant_id):
        raise HTTPException(400, "MyInvois is not enabled or TIN is missing in Settings.")
    return submit_to_my_invois(session, user, invoice_id)


@my_invois_router.get("/logs", dependencies=[Depends(_require_my_invois_module)])
def list_my_invois_logs(
    user: CurrentUserDep,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    invoice_id: int | None = Query(None),
):
    q = select(MyInvoisSubmissionLog).where(MyInvoisSubmissionLog.tenant_id == user.tenant_id)
    if invoice_id is not None:
        q = q.where(MyInvoisSubmissionLog.invoice_id == invoice_id)
    q = q.order_by(MyInvoisSubmissionLog.created_at.desc()).offset(skip).limit(limit)  # type: ignore[attr-defined]
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
            "uuid": r.uuid,
        }
        for r in rows
    ]
