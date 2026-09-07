"""UK Making Tax Digital VAT adapter — HMRC sandbox pack (#306).

Mirrors services/zatca.py:
- Returns immediately when uk_mtd_enabled != "true" or uk_mtd module not installed
- Sandbox POSTs to HMRC test-api (mockable via httpx in tests)
- Never raises on submit — failures are logged to UkMtdSubmissionLog
"""
from __future__ import annotations

import calendar
import json
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

import httpx
from sqlmodel import Session, select

from models import Bill, Invoice, Settings, Tenant, UkMtdSubmissionLog

DEFAULT_SANDBOX_URL = "https://test-api.service.hmrc.gov.uk/organisations/vat"


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
    return "uk_mtd" in enabled


def get_uk_mtd_config(session: Session, tenant_id: int) -> Optional[dict]:
    """Return HMRC MTD config, or None if module missing / disabled / incomplete."""
    if not _module_installed(session, tenant_id):
        return None
    if _get_setting(session, tenant_id, "uk_mtd_enabled") != "true":
        return None
    vrn = _get_setting(session, tenant_id, "uk_mtd_vrn").strip()
    if not vrn:
        return None
    sandbox = _get_setting(session, tenant_id, "uk_mtd_sandbox_mode", "true") == "true"
    base = os.environ.get("UK_MTD_SANDBOX_URL", DEFAULT_SANDBOX_URL) if sandbox else (
        "https://api.service.hmrc.gov.uk/organisations/vat"
    )
    return {
        "vrn": vrn,
        "client_id": _get_setting(session, tenant_id, "uk_mtd_client_id"),
        "client_secret": _get_setting(session, tenant_id, "uk_mtd_client_secret"),
        "sandbox": sandbox,
        "endpoint": f"{base.rstrip('/')}/{vrn}/returns",
        "seller_name": _get_setting(session, tenant_id, "company_name") or "Seller",
    }


def period_for_date(iso_date: str) -> tuple[str, str, str]:
    """Map YYYY-MM-DD → (period_key YYYY-Qn, start, end) calendar quarter."""
    y, m, _ = (int(p) for p in iso_date[:10].split("-"))
    q = (m - 1) // 3 + 1
    start_m = (q - 1) * 3 + 1
    end_m = start_m + 2
    last = calendar.monthrange(y, end_m)[1]
    return f"{y}-Q{q}", f"{y:04d}-{start_m:02d}-01", f"{y:04d}-{end_m:02d}-{last:02d}"


def resolve_period(
    period_key: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[str, str, str]:
    if start and end:
        key = period_key or period_for_date(start)[0]
        return key, start, end
    if period_key and len(period_key) >= 6 and "-Q" in period_key.upper():
        raw = period_key.upper().replace(" ", "")
        year_s, q_s = raw.split("-Q", 1)
        y, q = int(year_s), int(q_s[0])
        start_m = (q - 1) * 3 + 1
        end_m = start_m + 2
        last = calendar.monthrange(y, end_m)[1]
        return f"{y}-Q{q}", f"{y:04d}-{start_m:02d}-01", f"{y:04d}-{end_m:02d}-{last:02d}"
    today = date.today().isoformat()
    return period_for_date(today)


def _money(val: Any) -> float:
    try:
        return float(Decimal(str(val or 0)))
    except Exception:
        return 0.0


def compute_vat_boxes(session: Session, tenant_id: int, start: str, end: str) -> dict:
    """HMRC VAT return boxes 1–9 from posted invoices + bills in the window."""
    invoices = list(
        session.exec(
            select(Invoice).where(
                Invoice.tenant_id == tenant_id,
                Invoice.issue_date >= start,
                Invoice.issue_date <= end,
            )
        ).all()
    )
    bills = list(
        session.exec(
            select(Bill).where(
                Bill.tenant_id == tenant_id,
                Bill.bill_date >= start,
                Bill.bill_date <= end,
            )
        ).all()
    )
    skip = {"draft", "void", "cancelled", "voided"}
    sales = [i for i in invoices if (i.status or "").lower() not in skip]
    purchases = [b for b in bills if (b.status or "").lower() not in skip]

    box1 = round(sum(_money(i.gst_amount) for i in sales), 2)
    box2 = 0.0
    box3 = round(box1 + box2, 2)
    box4 = round(sum(_money(b.gst_amount) for b in purchases), 2)
    box5 = round(abs(box3 - box4), 2)
    box6 = int(round(sum(_money(i.subtotal) for i in sales)))
    box7 = int(round(sum(_money(b.subtotal) for b in purchases)))
    box8 = 0
    box9 = 0
    return {
        "vatDueSales": box1,
        "vatDueAcquisitions": box2,
        "totalVatDue": box3,
        "vatReclaimedCurrPeriod": box4,
        "netVatDue": box5,
        "totalValueSalesExVAT": box6,
        "totalValuePurchasesExVAT": box7,
        "totalValueGoodsSuppliedExVAT": box8,
        "totalAcquisitionsExVAT": box9,
        "invoice_count": len(sales),
        "bill_count": len(purchases),
    }


def hmrc_return_payload(period_key: str, boxes: dict, *, finalised: bool = True) -> dict:
    return {
        "periodKey": period_key,
        "vatDueSales": boxes["vatDueSales"],
        "vatDueAcquisitions": boxes["vatDueAcquisitions"],
        "totalVatDue": boxes["totalVatDue"],
        "vatReclaimedCurrPeriod": boxes["vatReclaimedCurrPeriod"],
        "netVatDue": boxes["netVatDue"],
        "totalValueSalesExVAT": boxes["totalValueSalesExVAT"],
        "totalValuePurchasesExVAT": boxes["totalValuePurchasesExVAT"],
        "totalValueGoodsSuppliedExVAT": boxes["totalValueGoodsSuppliedExVAT"],
        "totalAcquisitionsExVAT": boxes["totalAcquisitionsExVAT"],
        "finalised": finalised,
    }


def _headers(config: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/vnd.hmrc.1.0+json",
    }
    secret = (config.get("client_secret") or "").strip()
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    cid = (config.get("client_id") or "").strip()
    if cid:
        headers["X-Client-Id"] = cid
    return headers


def submit_vat_return(
    session: Session,
    user: Any,
    *,
    period_key: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Submit a period VAT return to HMRC sandbox. Never raises."""
    config = get_uk_mtd_config(session, user.tenant_id)
    key, start_d, end_d = resolve_period(period_key, start, end)
    if not config:
        return {
            "success": False,
            "period_key": key,
            "error_message": "UK MTD is not enabled or VRN is missing in Settings.",
            "log_id": None,
            "boxes": compute_vat_boxes(session, user.tenant_id, start_d, end_d),
        }

    boxes = compute_vat_boxes(session, user.tenant_id, start_d, end_d)
    payload = hmrc_return_payload(key, boxes)
    request_payload = json.dumps(payload)
    endpoint = config["endpoint"]

    log = UkMtdSubmissionLog(
        tenant_id=user.tenant_id,
        invoice_id=0,
        request_payload=request_payload[:8000],
        endpoint=endpoint,
        sandbox=config["sandbox"],
        status="submitted",
        period_key=key,
    )

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(endpoint, content=request_payload, headers=_headers(config))
        log.http_status = resp.status_code
        log.response_payload = (resp.text or "")[:4000]
        resp_data: dict = {}
        try:
            resp_data = resp.json()
        except Exception:
            pass
        ok = 200 <= resp.status_code < 300
        if ok:
            log.status = "accepted"
            correlation = (
                resp_data.get("processingDate")
                or resp_data.get("formBundleNumber")
                or resp_data.get("correlationId")
                or f"MTD-{key}"
            )
            _stamp_invoices(session, user.tenant_id, start_d, end_d, key, str(correlation))
        else:
            log.status = "rejected" if 400 <= resp.status_code < 500 else "error"
            log.error_message = (
                resp_data.get("message") or resp_data.get("error") or f"HTTP {resp.status_code}"
            )[:500]
    except Exception as exc:
        log.status = "error"
        log.error_message = str(exc)[:500]

    session.add(log)
    session.commit()
    session.refresh(log)
    return {
        "success": log.status == "accepted",
        "period_key": key,
        "start": start_d,
        "end": end_d,
        "boxes": boxes,
        "uk_mtd_status": log.status,
        "error_message": log.error_message,
        "log_id": log.id,
        "sandbox": config["sandbox"],
        "http_status": log.http_status,
        "payload": payload,
    }


def _stamp_invoices(
    session: Session, tenant_id: int, start: str, end: str, period_key: str, correlation: str,
) -> None:
    now = datetime.utcnow()
    skip = {"draft", "void", "cancelled", "voided"}
    rows = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.issue_date >= start,
            Invoice.issue_date <= end,
        )
    ).all()
    for inv in rows:
        if (inv.status or "").lower() in skip:
            continue
        inv.uk_mtd_status = "accepted"
        inv.uk_mtd_period = period_key
        inv.uk_mtd_correlation_id = correlation[:120]
        inv.uk_mtd_submitted_at = now
        session.add(inv)


def submit_invoice_to_uk_mtd(session: Session, user: Any, invoice_id: int) -> dict:
    """Mark one invoice against the period return (sandbox POST). Never raises."""
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        return {
            "success": False,
            "uk_mtd_status": None,
            "error_message": "Invoice not found",
            "log_id": None,
        }

    config = get_uk_mtd_config(session, invoice.tenant_id)
    if not config:
        return {
            "success": False,
            "uk_mtd_status": invoice.uk_mtd_status,
            "uk_mtd_period": invoice.uk_mtd_period,
            "uk_mtd_correlation_id": invoice.uk_mtd_correlation_id,
            "error_message": "UK MTD is not enabled or VRN is missing in Settings.",
            "log_id": None,
        }

    key, start_d, end_d = period_for_date(str(invoice.issue_date))
    boxes = compute_vat_boxes(session, invoice.tenant_id, start_d, end_d)
    payload = {
        "kind": "invoice",
        "invoice_number": invoice.number,
        "invoice_id": invoice.id,
        "periodKey": key,
        "vatDueSales": float(_money(invoice.gst_amount)),
        "totalValueSalesExVAT": float(_money(invoice.subtotal)),
        "boxes": boxes,
    }
    request_payload = json.dumps(payload)
    endpoint = config["endpoint"]

    invoice.uk_mtd_status = "submitted"
    invoice.uk_mtd_period = key
    session.add(invoice)
    session.flush()

    log = UkMtdSubmissionLog(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice_id,
        request_payload=request_payload[:8000],
        endpoint=endpoint,
        sandbox=config["sandbox"],
        status="submitted",
        period_key=key,
    )

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(endpoint, content=request_payload, headers=_headers(config))
        log.http_status = resp.status_code
        log.response_payload = (resp.text or "")[:4000]
        resp_data: dict = {}
        try:
            resp_data = resp.json()
        except Exception:
            pass
        ok = 200 <= resp.status_code < 300
        if ok:
            log.status = "accepted"
            correlation = (
                resp_data.get("correlationId")
                or resp_data.get("formBundleNumber")
                or f"MTD-INV-{invoice.id}"
            )
            invoice.uk_mtd_status = "accepted"
            invoice.uk_mtd_correlation_id = str(correlation)[:120]
            invoice.uk_mtd_submitted_at = datetime.utcnow()
            session.add(invoice)
        else:
            status = "rejected" if 400 <= resp.status_code < 500 else "error"
            log.status = status
            log.error_message = (
                resp_data.get("message") or resp_data.get("error") or f"HTTP {resp.status_code}"
            )[:500]
            invoice.uk_mtd_status = status
            session.add(invoice)
    except Exception as exc:
        log.status = "error"
        log.error_message = str(exc)[:500]
        invoice.uk_mtd_status = "error"
        session.add(invoice)

    session.add(log)
    session.commit()
    session.refresh(log)
    session.refresh(invoice)
    return {
        "success": log.status == "accepted",
        "uk_mtd_status": invoice.uk_mtd_status,
        "uk_mtd_period": invoice.uk_mtd_period,
        "uk_mtd_correlation_id": invoice.uk_mtd_correlation_id,
        "error_message": log.error_message,
        "log_id": log.id,
        "sandbox": config["sandbox"],
        "http_status": log.http_status,
    }
