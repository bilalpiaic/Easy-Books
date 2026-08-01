"""UAE FTA e-Invoice adapter (localization pack).

Mirrors services/pra.py's graceful no-op pattern:
- Returns immediately when uae_vat_enabled != "true"
- Sandbox mode is a local stub (no live FTA call) — succeeds with a synthetic UUID
- Production mode is reserved for a future Peppol/FTA connector; currently logs
  a clear "not configured" failure rather than pretending to post

API shape is intentionally small so the Apps install path + Settings card can
ship before a full live integration.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from models import (
    Account,
    Customer,
    Invoice,
    InvoiceLine,
    Settings,
    TaxCode,
    UaeEinvoiceLog,
)

SANDBOX_ENDPOINT = "stub://uae-fta/sandbox/einvoice"
PRODUCTION_ENDPOINT = "https://sdkta.tax.gov.ae/ (not wired — stub pack)"


def _get_setting(session: Session, tenant_id: int, key: str, default: str = "") -> str:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row else default


def get_uae_config(session: Session, tenant_id: int) -> Optional[dict]:
    """Return UAE VAT config, or None if the pack is disabled / missing TRN."""
    if _get_setting(session, tenant_id, "uae_vat_enabled") != "true":
        return None
    trn = _get_setting(session, tenant_id, "uae_trn").strip()
    if not trn:
        return None
    sandbox = _get_setting(session, tenant_id, "uae_sandbox_mode", "true") == "true"
    return {
        "trn": trn,
        "legal_name": _get_setting(session, tenant_id, "uae_legal_name"),
        "sandbox": sandbox,
        "endpoint": SANDBOX_ENDPOINT if sandbox else PRODUCTION_ENDPOINT,
        "api_key": _get_setting(session, tenant_id, "uae_api_key"),
    }


def build_uae_payload(
    invoice: Invoice,
    lines: list[InvoiceLine],
    customer: Optional[Customer],
    config: dict,
) -> dict:
    """Map an Easy-Books invoice to a minimal FTA-shaped stub payload."""
    vat_rate = float(invoice.gst_rate or Decimal("5"))
    return {
        "supplierTRN": config["trn"],
        "supplierName": config.get("legal_name") or "",
        "invoiceNumber": invoice.number,
        "issueDate": str(invoice.issue_date),
        "currency": invoice.currency or "AED",
        "buyerName": (customer.name if customer else invoice.customer_name) or "Walk-in",
        "buyerTRN": getattr(customer, "ntn", None) or "",
        "lines": [
            {
                "description": (line.description or "")[:200],
                "qty": float(line.qty),
                "amount": float(line.amount),
                "vatRate": vat_rate,
            }
            for line in lines
        ],
        "subtotal": float(invoice.subtotal),
        "vatAmount": float(invoice.gst_amount),
        "total": float(invoice.total),
    }


def submit_to_uae(session: Session, invoice: Invoice) -> UaeEinvoiceLog:
    """Submit (or stub-submit) an invoice. Never raises — always writes a log row."""
    config = get_uae_config(session, invoice.tenant_id)
    lines = list(
        session.exec(
            select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
        ).all()
    )
    customer = (
        session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    )

    if not config:
        log = UaeEinvoiceLog(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.id,
            endpoint="(disabled)",
            request_json="{}",
            success=False,
            error_message="UAE VAT is not enabled or TRN is missing in Settings.",
            sandbox=True,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return log

    payload = build_uae_payload(invoice, lines, customer, config)
    request_json = json.dumps(payload, default=str)

    if config["sandbox"]:
        stub_uuid = f"UAE-SBX-{uuid.uuid4().hex[:12].upper()}"
        response = {
            "status": "REPORTED",
            "uuid": stub_uuid,
            "message": "Sandbox stub — no live FTA call",
        }
        log = UaeEinvoiceLog(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.id,
            endpoint=config["endpoint"],
            request_json=request_json,
            response_uuid=stub_uuid,
            response_json=json.dumps(response),
            http_status=200,
            success=True,
            sandbox=True,
        )
    else:
        # Live Peppol/FTA connector not wired yet — fail loudly and log.
        log = UaeEinvoiceLog(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.id,
            endpoint=config["endpoint"],
            request_json=request_json,
            success=False,
            error_message=(
                "Production UAE FTA connector is not wired in this stub pack. "
                "Enable sandbox mode, or wait for the live Peppol integration."
            ),
            sandbox=False,
            http_status=501,
        )

    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def ensure_uae_tax_and_coa(session: Session, tenant_id: int) -> dict:
    """Idempotent: VAT Payable/Receivable CoA leaves + 5% tax codes for UAE."""
    created_accounts: list[str] = []
    created_taxes: list[str] = []

    def _get_or_create_account(code: str, name: str, atype: str, parent_code: str) -> Account:
        acc = session.exec(
            select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
        ).first()
        if acc:
            return acc
        parent = session.exec(
            select(Account).where(
                Account.tenant_id == tenant_id, Account.code == parent_code
            )
        ).first()
        acc = Account(
            tenant_id=tenant_id,
            code=code,
            name=name,
            type=atype,
            is_memo=False,
            is_group=False,
            parent_id=parent.id if parent else None,
            is_active=True,
        )
        session.add(acc)
        session.flush()
        created_accounts.append(code)
        return acc

    vat_payable = _get_or_create_account(
        "2210", "VAT Payable (UAE Output)", "Liability", "21"
    )
    vat_receivable = _get_or_create_account(
        "1260", "VAT Receivable (UAE Input)", "Asset", "11"
    )

    for code, name, rate, ttype, gl in (
        ("VAT5_OUT", "UAE Standard VAT 5% (Output)", 5, "output", vat_payable),
        ("VAT5_IN", "UAE Standard VAT 5% (Input)", 5, "input", vat_receivable),
        ("VAT0_OUT", "UAE Zero-rated (Output)", 0, "output", vat_payable),
    ):
        existing = session.exec(
            select(TaxCode).where(TaxCode.tenant_id == tenant_id, TaxCode.code == code)
        ).first()
        if existing:
            continue
        session.add(
            TaxCode(
                tenant_id=tenant_id,
                code=code,
                name=name,
                rate=Decimal(rate),
                type=ttype,
                gl_account_id=gl.id,
            )
        )
        created_taxes.append(code)

    session.flush()
    return {"accounts": created_accounts, "tax_codes": created_taxes}
