"""UK Making Tax Digital VAT endpoints (#306).

POST /api/uk-mtd/test                          — verify credentials / sandbox reachability
GET  /api/uk-mtd/vat-return                    — period VAT boxes (filing export)
POST /api/uk-mtd/vat-return/submit             — sandbox HMRC VAT return submit
GET  /api/uk-mtd/invoices/{invoice_id}/status  — uk_mtd_* fields on the invoice
POST /api/uk-mtd/invoices/{invoice_id}/submit  — include invoice in period sandbox submit
GET  /api/uk-mtd/logs                          — UkMtdSubmissionLog listing
"""
from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from models import Invoice, Tenant, UkMtdSubmissionLog
from routers.common import CurrentUserDep, SessionDep
from routers.modules import _get_enabled
from services.permissions import perm_dep
from services.uk_mtd import (
    compute_vat_boxes,
    get_uk_mtd_config,
    hmrc_return_payload,
    resolve_period,
    submit_invoice_to_uk_mtd,
    submit_vat_return,
)

uk_mtd_router = APIRouter(prefix="/uk-mtd", tags=["uk-mtd"], dependencies=[perm_dep("invoices")])


def _require_uk_mtd_module(user: CurrentUserDep, session: SessionDep) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "uk_mtd" not in _get_enabled(tenant):
        raise HTTPException(
            status_code=403,
            detail="The UK MTD VAT module is not installed. Install it from System → Apps.",
        )


@uk_mtd_router.post("/test", dependencies=[Depends(_require_uk_mtd_module), perm_dep("invoices", "edit")])
def test_uk_mtd_connection(user: CurrentUserDep, session: SessionDep):
    config = get_uk_mtd_config(session, user.tenant_id)
    if not config:
        raise HTTPException(400, "UK MTD is not enabled or VRN is missing in Settings.")

    if not config["sandbox"]:
        return {
            "ok": False,
            "sandbox": False,
            "message": "Production HMRC path requires a live OAuth token — enable sandbox mode to test.",
            "endpoint": config["endpoint"],
            "vrn": config["vrn"],
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                config["endpoint"],
                content=json.dumps({"probe": True}),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
        return {
            "ok": True,
            "sandbox": True,
            "http_status": resp.status_code,
            "message": f"Sandbox reachable (HTTP {resp.status_code})",
            "endpoint": config["endpoint"],
            "vrn": config["vrn"],
        }
    except Exception as exc:
        raise HTTPException(502, f"Could not reach HMRC sandbox: {exc}") from exc


@uk_mtd_router.get("/vat-return", dependencies=[Depends(_require_uk_mtd_module)])
def get_vat_return(
    user: CurrentUserDep,
    session: SessionDep,
    period_key: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    key, start_d, end_d = resolve_period(period_key, start, end)
    boxes = compute_vat_boxes(session, user.tenant_id, start_d, end_d)
    return {
        "period_key": key,
        "start": start_d,
        "end": end_d,
        "boxes": boxes,
        "payload": hmrc_return_payload(key, boxes),
    }


@uk_mtd_router.post(
    "/vat-return/submit",
    dependencies=[Depends(_require_uk_mtd_module), perm_dep("invoices", "edit")],
)
def post_vat_return(
    user: CurrentUserDep,
    session: SessionDep,
    period_key: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    if not get_uk_mtd_config(session, user.tenant_id):
        raise HTTPException(400, "UK MTD is not enabled or VRN is missing in Settings.")
    return submit_vat_return(session, user, period_key=period_key, start=start, end=end)


@uk_mtd_router.get(
    "/invoices/{invoice_id}/status",
    dependencies=[Depends(_require_uk_mtd_module)],
)
def get_invoice_uk_mtd_status(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return {
        "invoice_id": invoice.id,
        "uk_mtd_status": invoice.uk_mtd_status,
        "uk_mtd_period": invoice.uk_mtd_period,
        "uk_mtd_correlation_id": invoice.uk_mtd_correlation_id,
        "uk_mtd_submitted_at": invoice.uk_mtd_submitted_at,
    }


@uk_mtd_router.post(
    "/invoices/{invoice_id}/submit",
    dependencies=[Depends(_require_uk_mtd_module), perm_dep("invoices", "edit")],
)
def submit_uk_mtd_invoice(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not get_uk_mtd_config(session, user.tenant_id):
        raise HTTPException(400, "UK MTD is not enabled or VRN is missing in Settings.")
    return submit_invoice_to_uk_mtd(session, user, invoice_id)


@uk_mtd_router.get("/logs", dependencies=[Depends(_require_uk_mtd_module)])
def list_uk_mtd_logs(
    user: CurrentUserDep,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    invoice_id: int | None = Query(None),
    period_key: str | None = Query(None),
):
    q = select(UkMtdSubmissionLog).where(UkMtdSubmissionLog.tenant_id == user.tenant_id)
    if invoice_id is not None:
        q = q.where(UkMtdSubmissionLog.invoice_id == invoice_id)
    if period_key:
        q = q.where(UkMtdSubmissionLog.period_key == period_key)
    q = q.order_by(UkMtdSubmissionLog.created_at.desc()).offset(skip).limit(limit)  # type: ignore[attr-defined]
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
            "period_key": r.period_key,
        }
        for r in rows
    ]
