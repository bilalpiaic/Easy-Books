"""Saudi ZATCA (Fatoora) e-Invoice adapter — KSA Phase 2 sandbox pack (#264).

Mirrors services/pra.py's graceful no-op pattern:
- Returns immediately when zatca_enabled != "true" or sa_zatca module not installed
- Sandbox POSTs to ZATCA_SANDBOX_URL (mockable via httpx in tests)
- Never raises — failures are logged to ZatcaSubmissionLog and surfaced via invoice.zatca_status
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid as uuid_mod
import xml.sax.saxutils as xml_escape
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlmodel import Session, select

from models import Customer, Invoice, InvoiceLine, Settings, Tenant, ZatcaSubmissionLog

DEFAULT_SANDBOX_URL = (
    "https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal/invoices/reporting/single"
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
    return "sa_zatca" in enabled


def get_zatca_config(session: Session, tenant_id: int) -> Optional[dict]:
    """Return ZATCA config, or None if module missing / disabled / incomplete."""
    if not _module_installed(session, tenant_id):
        return None
    if _get_setting(session, tenant_id, "zatca_enabled") != "true":
        return None
    vat = _get_setting(session, tenant_id, "zatca_vat_number").strip()
    if not vat:
        return None
    sandbox = _get_setting(session, tenant_id, "zatca_sandbox_mode", "true") == "true"
    endpoint = os.environ.get("ZATCA_SANDBOX_URL", DEFAULT_SANDBOX_URL) if sandbox else (
        "https://gw-fatoora.zatca.gov.sa/e-invoicing/core/invoices/clearance/single"
    )
    return {
        "vat_number": vat,
        "cr_number": _get_setting(session, tenant_id, "zatca_cr_number"),
        "device_id": _get_setting(session, tenant_id, "zatca_device_id"),
        "csid_token": _get_setting(session, tenant_id, "zatca_csid_token"),
        "sandbox": sandbox,
        "endpoint": endpoint,
        "seller_name": _get_setting(session, tenant_id, "company_name")
        or _get_setting(session, tenant_id, "zatca_legal_name")
        or "Seller",
    }


def build_zatca_qr_tlv(
    seller_name: str,
    vat_number: str,
    timestamp: str,
    total_with_vat: str,
    vat_amount: str,
) -> str:
    """Phase-1 style TLV → base64 QR payload (tags 1–5)."""

    def _tlv(tag: int, value: str) -> bytes:
        raw = value.encode("utf-8")
        return bytes([tag, len(raw)]) + raw

    payload = b"".join([
        _tlv(1, seller_name),
        _tlv(2, vat_number),
        _tlv(3, timestamp),
        _tlv(4, total_with_vat),
        _tlv(5, vat_amount),
    ])
    return base64.b64encode(payload).decode("ascii")


def build_zatca_invoice_xml(
    *,
    invoice: Invoice,
    lines: list[InvoiceLine],
    customer: Optional[Customer],
    config: dict,
    invoice_uuid: str,
) -> str:
    """Simplified UBL-ish / ZATCA simplified invoice XML (enough for tests + sandbox)."""
    buyer_name = (customer.name if customer else invoice.customer_name) or "Cash Customer"
    buyer_vat = (getattr(customer, "ntn", None) or "") if customer else ""
    esc = xml_escape.escape

    line_xml = []
    for i, line in enumerate(lines, start=1):
        line_xml.append(
            f"""    <cac:InvoiceLine>
      <cbc:ID>{i}</cbc:ID>
      <cbc:InvoicedQuantity unitCode="PCE">{float(line.qty)}</cbc:InvoicedQuantity>
      <cbc:LineExtensionAmount currencyID="SAR">{float(line.amount):.2f}</cbc:LineExtensionAmount>
      <cac:Item>
        <cbc:Name>{esc((line.description or "Item")[:200])}</cbc:Name>
      </cac:Item>
      <cac:Price>
        <cbc:PriceAmount currencyID="SAR">{float(line.rate):.2f}</cbc:PriceAmount>
      </cac:Price>
    </cac:InvoiceLine>"""
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ProfileID>reporting:1.0</cbc:ProfileID>
  <cbc:ID>{esc(invoice.number)}</cbc:ID>
  <cbc:UUID>{invoice_uuid}</cbc:UUID>
  <cbc:IssueDate>{esc(str(invoice.issue_date))}</cbc:IssueDate>
  <cbc:InvoiceTypeCode name="0200000">388</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>SAR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyIdentification>
        <cbc:ID schemeID="CRN">{esc(config.get("cr_number") or "")}</cbc:ID>
      </cac:PartyIdentification>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{esc(config["vat_number"])}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>{esc(config.get("seller_name") or "Seller")}</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{esc(buyer_vat)}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>{esc(buyer_name)}</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="SAR">{float(invoice.gst_amount):.2f}</cbc:TaxAmount>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="SAR">{float(invoice.subtotal):.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="SAR">{float(invoice.subtotal):.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="SAR">{float(invoice.total):.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="SAR">{float(invoice.total):.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
{chr(10).join(line_xml)}
</Invoice>
"""


def _hash_xml(xml_str: str) -> str:
    return hashlib.sha256(xml_str.encode("utf-8")).hexdigest()


def submit_to_zatca(session: Session, user: Any, invoice_id: int) -> dict:
    """Submit an invoice to ZATCA (sandbox clear/report). Never raises.

    Returns a result dict: success, zatca_status, zatca_uuid, zatca_hash, zatca_qr,
    error_message, log_id. Graceful no-op when not configured.
    """
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        return {
            "success": False,
            "zatca_status": None,
            "error_message": "Invoice not found",
            "log_id": None,
        }

    config = get_zatca_config(session, invoice.tenant_id)
    if not config:
        return {
            "success": False,
            "zatca_status": invoice.zatca_status,
            "zatca_uuid": invoice.zatca_uuid,
            "zatca_hash": invoice.zatca_hash,
            "zatca_qr": invoice.zatca_qr,
            "error_message": "ZATCA is not enabled or VAT number is missing in Settings.",
            "log_id": None,
        }

    lines = list(
        session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)).all()
    )
    customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    buyer_vat = (getattr(customer, "ntn", None) or "") if customer else ""
    # B2B with buyer VAT → clearance; otherwise reporting (simplified / B2C)
    clearance = bool(buyer_vat and buyer_vat.strip())
    path_hint = "clearance" if clearance else "reporting"
    endpoint = config["endpoint"]
    if config["sandbox"] and "reporting" in endpoint and clearance:
        endpoint = endpoint.replace("reporting", "clearance")

    invoice_uuid = invoice.zatca_uuid or str(uuid_mod.uuid4())
    xml_body = build_zatca_invoice_xml(
        invoice=invoice, lines=lines, customer=customer, config=config, invoice_uuid=invoice_uuid,
    )
    invoice_hash = _hash_xml(xml_body)
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    qr = build_zatca_qr_tlv(
        config.get("seller_name") or "Seller",
        config["vat_number"],
        ts,
        f"{float(invoice.total):.2f}",
        f"{float(invoice.gst_amount):.2f}",
    )

    request_payload = json.dumps({
        "invoiceHash": invoice_hash,
        "uuid": invoice_uuid,
        "invoice": base64.b64encode(xml_body.encode("utf-8")).decode("ascii"),
        "path": path_hint,
    })

    invoice.zatca_status = "submitted"
    session.add(invoice)
    session.flush()

    log = ZatcaSubmissionLog(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice_id,
        request_payload=request_payload[:8000],
        endpoint=endpoint,
        sandbox=config["sandbox"],
        status="submitted",
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Clearance-Status": "1" if clearance else "0",
    }
    if config.get("csid_token"):
        headers["Authorization"] = f"Basic {config['csid_token']}"
    if config.get("device_id"):
        headers["X-Device-Id"] = config["device_id"]

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(endpoint, content=request_payload, headers=headers)
        log.http_status = resp.status_code
        log.response_payload = (resp.text or "")[:4000]

        ok = 200 <= resp.status_code < 300
        resp_data: dict = {}
        try:
            resp_data = resp.json()
        except Exception:
            pass

        if ok:
            status = "cleared" if clearance else "reported"
            # Prefer API-returned UUID/hash when present
            api_uuid = resp_data.get("uuid") or resp_data.get("invoiceUuid")
            if isinstance(api_uuid, str) and api_uuid:
                invoice_uuid = api_uuid
            api_hash = resp_data.get("invoiceHash") or resp_data.get("hash")
            if isinstance(api_hash, str) and api_hash:
                invoice_hash = api_hash
            api_qr = resp_data.get("qrSellertStatus") or resp_data.get("qr") or qr
            if isinstance(api_qr, str) and api_qr:
                qr = api_qr

            log.status = status
            invoice.zatca_status = status
            invoice.zatca_uuid = invoice_uuid
            invoice.zatca_hash = invoice_hash
            invoice.zatca_qr = qr
            invoice.zatca_submitted_at = datetime.utcnow()
            session.add(invoice)
        else:
            # Treat 4xx business rejects as rejected; other failures as error
            status = "rejected" if 400 <= resp.status_code < 500 else "error"
            log.status = status
            log.error_message = (
                resp_data.get("message")
                or resp_data.get("error")
                or f"HTTP {resp.status_code}"
            )[:500]
            invoice.zatca_status = status
            session.add(invoice)
    except Exception as exc:
        log.status = "error"
        log.error_message = str(exc)[:500]
        invoice.zatca_status = "error"
        session.add(invoice)

    session.add(log)
    session.commit()
    session.refresh(log)
    session.refresh(invoice)

    return {
        "success": log.status in ("cleared", "reported"),
        "zatca_status": invoice.zatca_status,
        "zatca_uuid": invoice.zatca_uuid,
        "zatca_hash": invoice.zatca_hash,
        "zatca_qr": invoice.zatca_qr,
        "error_message": log.error_message,
        "log_id": log.id,
        "sandbox": config["sandbox"],
        "http_status": log.http_status,
    }
