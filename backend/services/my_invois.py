"""Malaysia LHDN MyInvois e-Invoice adapter — sandbox pack (#306).

Mirrors services/zatca.py:
- Returns immediately when my_invois_enabled != "true" or my_invois module not installed
- Sandbox POSTs to MyInvois preprod (mockable via httpx in tests)
- Never raises — failures are logged to MyInvoisSubmissionLog
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid as uuid_mod
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlmodel import Session, select

from models import Customer, Invoice, InvoiceLine, MyInvoisSubmissionLog, Settings, Tenant

DEFAULT_SANDBOX_URL = (
    "https://preprod-api.myinvois.hasil.gov.my/api/v1.0/documentsubmissions"
)


def _get_setting(session: Session, tenant_id: int, key: str, default: str = "") -> str:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row else default


def _module_installed(session: Session, tenant_id: int) -> bool:
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return False
    try:
        enabled = json.loads(tenant.enabled_modules or "[]")
    except Exception:
        enabled = []
    return "my_invois" in enabled


def get_my_invois_config(session: Session, tenant_id: int) -> Optional[dict]:
    """Return MyInvois config, or None if module missing / disabled / incomplete."""
    if not _module_installed(session, tenant_id):
        return None
    if _get_setting(session, tenant_id, "my_invois_enabled") != "true":
        return None
    tin = _get_setting(session, tenant_id, "my_invois_tin").strip()
    if not tin:
        return None
    sandbox = _get_setting(session, tenant_id, "my_invois_sandbox_mode", "true") == "true"
    endpoint = os.environ.get("MY_INVOIS_SANDBOX_URL", DEFAULT_SANDBOX_URL) if sandbox else (
        "https://api.myinvois.hasil.gov.my/api/v1.0/documentsubmissions"
    )
    return {
        "tin": tin,
        "client_id": _get_setting(session, tenant_id, "my_invois_client_id"),
        "client_secret": _get_setting(session, tenant_id, "my_invois_client_secret"),
        "sandbox": sandbox,
        "endpoint": endpoint,
        "seller_name": _get_setting(session, tenant_id, "company_name")
        or _get_setting(session, tenant_id, "my_invois_legal_name")
        or "Seller",
    }


def build_my_invois_document(
    *,
    invoice: Invoice,
    lines: list[InvoiceLine],
    customer: Optional[Customer],
    config: dict,
    doc_uuid: str,
) -> dict:
    buyer_name = (customer.name if customer else invoice.customer_name) or "Cash Customer"
    buyer_tin = (getattr(customer, "ntn", None) or "") if customer else ""
    return {
        "codeNumber": invoice.number,
        "uuid": doc_uuid,
        "issueDate": str(invoice.issue_date),
        "documentCurrencyCode": invoice.currency or "MYR",
        "supplier": {
            "tin": config["tin"],
            "name": config.get("seller_name") or "Seller",
        },
        "buyer": {
            "tin": buyer_tin,
            "name": buyer_name,
        },
        "taxTotal": float(invoice.gst_amount or 0),
        "legalMonetaryTotal": {
            "taxExclusive": float(invoice.subtotal or 0),
            "taxInclusive": float(invoice.total or 0),
            "payable": float(invoice.total or 0),
        },
        "lines": [
            {
                "description": (line.description or "Item")[:200],
                "qty": float(line.qty or 0),
                "rate": float(line.rate or 0),
                "amount": float(line.amount or 0),
            }
            for line in lines
        ],
    }


def submit_to_my_invois(session: Session, user: Any, invoice_id: int) -> dict:
    """Submit an invoice to LHDN MyInvois sandbox. Never raises."""
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        return {
            "success": False,
            "my_invois_status": None,
            "error_message": "Invoice not found",
            "log_id": None,
        }

    config = get_my_invois_config(session, invoice.tenant_id)
    if not config:
        return {
            "success": False,
            "my_invois_status": invoice.my_invois_status,
            "my_invois_uuid": invoice.my_invois_uuid,
            "error_message": "MyInvois is not enabled or TIN is missing in Settings.",
            "log_id": None,
        }

    lines = list(
        session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)).all()
    )
    customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    doc_uuid = invoice.my_invois_uuid or str(uuid_mod.uuid4())
    document = build_my_invois_document(
        invoice=invoice, lines=lines, customer=customer, config=config, doc_uuid=doc_uuid,
    )
    raw = json.dumps(document, separators=(",", ":"), sort_keys=True)
    doc_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    request_payload = json.dumps({
        "documents": [{
            "format": "JSON",
            "documentHash": doc_hash,
            "codeNumber": invoice.number,
            "document": document,
        }],
    })
    endpoint = config["endpoint"]

    invoice.my_invois_status = "submitted"
    session.add(invoice)
    session.flush()

    log = MyInvoisSubmissionLog(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice_id,
        request_payload=request_payload[:8000],
        endpoint=endpoint,
        sandbox=config["sandbox"],
        status="submitted",
        uuid=doc_uuid,
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    secret = (config.get("client_secret") or "").strip()
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    cid = (config.get("client_id") or "").strip()
    if cid:
        headers["X-Client-Id"] = cid
    headers["X-TIN"] = config["tin"]

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(endpoint, content=request_payload, headers=headers)
        log.http_status = resp.status_code
        log.response_payload = (resp.text or "")[:4000]
        resp_data: dict = {}
        try:
            resp_data = resp.json()
        except Exception:
            pass
        ok = 200 <= resp.status_code < 300
        if ok:
            accepted = resp_data.get("acceptedDocuments")
            accepted_uuid = None
            if isinstance(accepted, list) and accepted and isinstance(accepted[0], dict):
                accepted_uuid = accepted[0].get("uuid")
            api_uuid = resp_data.get("uuid") or resp_data.get("submissionUid") or accepted_uuid
            if isinstance(api_uuid, str) and api_uuid:
                doc_uuid = api_uuid
            log.status = "accepted"
            log.uuid = doc_uuid
            invoice.my_invois_status = "accepted"
            invoice.my_invois_uuid = doc_uuid
            invoice.my_invois_submitted_at = datetime.utcnow()
            session.add(invoice)
        else:
            status = "rejected" if 400 <= resp.status_code < 500 else "error"
            log.status = status
            log.error_message = (
                resp_data.get("message")
                or resp_data.get("error")
                or f"HTTP {resp.status_code}"
            )[:500]
            invoice.my_invois_status = status
            session.add(invoice)
    except Exception as exc:
        log.status = "error"
        log.error_message = str(exc)[:500]
        invoice.my_invois_status = "error"
        session.add(invoice)

    session.add(log)
    session.commit()
    session.refresh(log)
    session.refresh(invoice)
    return {
        "success": log.status == "accepted",
        "my_invois_status": invoice.my_invois_status,
        "my_invois_uuid": invoice.my_invois_uuid,
        "error_message": log.error_message,
        "log_id": log.id,
        "sandbox": config["sandbox"],
        "http_status": log.http_status,
    }
