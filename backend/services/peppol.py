"""Peppol / EU VAT e-Invoice adapter — BIS Billing 3.0 UBL pack (#266).

Mirrors services/zatca.py / services/pra.py:
- Returns immediately when peppol_enabled != "true" or eu_peppol module not installed
- POSTs UBL XML to a configurable Access Point URL (sandbox mockable via httpx)
- Never raises — failures are logged to PeppolSubmissionLog and surfaced via invoice.peppol_status
"""
from __future__ import annotations

import json
import os
import uuid as uuid_mod
import xml.sax.saxutils as xml_escape
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import httpx
from sqlmodel import Session, select

from models import Customer, Invoice, InvoiceLine, PeppolSubmissionLog, Settings, Tenant

# Peppol BIS Billing 3.0 customization + process identifiers (EN 16931 compliant)
BIS_BILLING_CUSTOMIZATION_ID = (
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
)
BIS_BILLING_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

DEFAULT_SANDBOX_AP_URL = "https://api.peppol-sandbox.example/v1/send"


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
    return "eu_peppol" in enabled


def map_vat_category(
    rate: Decimal | float | int | None,
    *,
    reverse_charge: bool = False,
) -> tuple[str, str]:
    """Map a VAT rate to UNCL 5305 tax category code + name (EN 16931).

    Returns (category_id, name):
      AE — reverse charge (cross-border B2B)
      Z  — zero-rated
      E  — exempt (rate None and not reverse-charge treated as exempt only when flagged)
      S  — standard rated
    """
    if reverse_charge:
        return ("AE", "VAT Reverse Charge")
    r = Decimal(str(rate if rate is not None else 0))
    if r == 0:
        return ("Z", "Zero rated goods")
    return ("S", "Standard rated")


def get_peppol_config(session: Session, tenant_id: int) -> Optional[dict]:
    """Return Peppol AP config, or None if module missing / disabled / incomplete."""
    if not _module_installed(session, tenant_id):
        return None
    if _get_setting(session, tenant_id, "peppol_enabled") != "true":
        return None
    participant = _get_setting(session, tenant_id, "peppol_participant_id").strip()
    if not participant:
        return None
    sandbox = _get_setting(session, tenant_id, "peppol_sandbox_mode", "true") == "true"
    ap_url = _get_setting(session, tenant_id, "peppol_ap_url").strip()
    if not ap_url:
        ap_url = os.environ.get("PEPPOL_AP_URL", DEFAULT_SANDBOX_AP_URL) if sandbox else ""
    if not ap_url:
        return None
    return {
        "participant_id": participant,
        "ap_url": ap_url,
        "api_key": _get_setting(session, tenant_id, "peppol_api_key"),
        "sandbox": sandbox,
        "seller_name": _get_setting(session, tenant_id, "company_name") or "Seller",
        "seller_vat": _get_setting(session, tenant_id, "tax_id")
        or _get_setting(session, tenant_id, "peppol_vat_number"),
        "seller_country": (_get_setting(session, tenant_id, "country") or "NL")[:2].upper(),
        "currency": _get_setting(session, tenant_id, "currency") or "EUR",
        "address_line1": _get_setting(session, tenant_id, "address_line1"),
        "city": _get_setting(session, tenant_id, "city"),
    }


def build_ubl_bis_billing_xml(
    invoice: Invoice,
    lines: list[InvoiceLine],
    company_settings: dict,
    *,
    customer: Optional[Customer] = None,
    document_id: Optional[str] = None,
    buyer_participant_id: Optional[str] = None,
    reverse_charge: bool = False,
) -> str:
    """Build Peppol BIS Billing 3.0 (UBL 2.1 Invoice) XML string.

    ``company_settings`` is the dict from get_peppol_config (or a test double)
    plus any extra seller fields. Tests assert Invoice / cac: / cbc: structure
    and CustomizationID for BIS Billing 3.0.
    """
    esc = xml_escape.escape
    currency = (getattr(invoice, "currency", None) or company_settings.get("currency") or "EUR")
    seller_name = company_settings.get("seller_name") or "Seller"
    seller_vat = (company_settings.get("seller_vat") or "").strip()
    seller_country = (company_settings.get("seller_country") or "NL")[:2].upper()
    participant = company_settings.get("participant_id") or ""
    buyer_name = (customer.name if customer else invoice.customer_name) or "Customer"
    buyer_vat = ""
    if customer:
        buyer_vat = (getattr(customer, "ntn", None) or getattr(customer, "gstin", None) or "") or ""
    buyer_vat = buyer_vat.strip()
    buyer_endpoint = buyer_participant_id or ""

    rate = Decimal(str(invoice.gst_rate or 0))
    # Cross-border B2B with buyer VAT and zero GST → reverse charge
    if not reverse_charge and buyer_vat and rate == 0:
        reverse_charge = True
    cat_id, _cat_name = map_vat_category(rate, reverse_charge=reverse_charge)

    taxable = Decimal(str(invoice.subtotal or 0))
    tax_amt = Decimal("0") if reverse_charge else Decimal(str(invoice.gst_amount or 0))
    payable = Decimal(str(invoice.total or 0))
    if reverse_charge:
        payable = taxable  # tax exclusive; buyer accounts for VAT

    doc_id = document_id or invoice.peppol_document_id or str(uuid_mod.uuid4())

    line_xml: list[str] = []
    for i, line in enumerate(lines, start=1):
        line_rate = (
            Decimal(str(line.tax_rate))
            if getattr(line, "tax_rate", None) is not None
            else rate
        )
        line_cat, _ = map_vat_category(
            Decimal("0") if reverse_charge else line_rate,
            reverse_charge=reverse_charge,
        )
        line_tax = (
            Decimal("0")
            if reverse_charge
            else Decimal(str(getattr(line, "tax_amount", None) or 0))
        )
        if not reverse_charge and line_tax == 0 and line_rate > 0:
            line_tax = (Decimal(str(line.amount)) * line_rate / Decimal("100")).quantize(
                Decimal("0.01")
            )
        unit = (line.unit or "C62")[:10]
        line_xml.append(
            f"""  <cac:InvoiceLine>
    <cbc:ID>{i}</cbc:ID>
    <cbc:InvoicedQuantity unitCode="{esc(unit)}">{float(line.qty)}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="{esc(currency)}">{float(line.amount):.2f}</cbc:LineExtensionAmount>
    <cac:Item>
      <cbc:Name>{esc((line.description or "Item")[:200])}</cbc:Name>
      <cac:ClassifiedTaxCategory>
        <cbc:ID>{line_cat}</cbc:ID>
        <cbc:Percent>{float(Decimal("0") if reverse_charge else line_rate):.2f}</cbc:Percent>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:ClassifiedTaxCategory>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="{esc(currency)}">{float(line.rate):.2f}</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>"""
        )

    tax_exemption = ""
    if reverse_charge:
        tax_exemption = (
            "\n        <cbc:TaxExemptionReasonCode>vatex-eu-ae</cbc:TaxExemptionReasonCode>"
            "\n        <cbc:TaxExemptionReason>Reverse charge</cbc:TaxExemptionReason>"
        )

    buyer_endpoint_xml = ""
    if buyer_endpoint:
        scheme, _, value = buyer_endpoint.partition(":")
        if value:
            buyer_endpoint_xml = (
                f'\n      <cbc:EndpointID schemeID="{esc(scheme)}">{esc(value)}</cbc:EndpointID>'
            )
        else:
            buyer_endpoint_xml = f"\n      <cbc:EndpointID>{esc(buyer_endpoint)}</cbc:EndpointID>"

    seller_scheme, _, seller_value = participant.partition(":")
    if not seller_value:
        seller_scheme, seller_value = "0088", participant

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>{BIS_BILLING_CUSTOMIZATION_ID}</cbc:CustomizationID>
  <cbc:ProfileID>{BIS_BILLING_PROFILE_ID}</cbc:ProfileID>
  <cbc:ID>{esc(invoice.number)}</cbc:ID>
  <cbc:UUID>{esc(doc_id)}</cbc:UUID>
  <cbc:IssueDate>{esc(str(invoice.issue_date))}</cbc:IssueDate>
  <cbc:DueDate>{esc(str(invoice.due_date))}</cbc:DueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>{esc(currency)}</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cbc:EndpointID schemeID="{esc(seller_scheme)}">{esc(seller_value)}</cbc:EndpointID>
      <cac:PartyName>
        <cbc:Name>{esc(seller_name)}</cbc:Name>
      </cac:PartyName>
      <cac:PostalAddress>
        <cbc:StreetName>{esc(company_settings.get("address_line1") or "")}</cbc:StreetName>
        <cbc:CityName>{esc(company_settings.get("city") or "")}</cbc:CityName>
        <cac:Country>
          <cbc:IdentificationCode>{esc(seller_country)}</cbc:IdentificationCode>
        </cac:Country>
      </cac:PostalAddress>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{esc(seller_vat)}</cbc:CompanyID>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:PartyTaxScheme>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>{esc(seller_name)}</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>{buyer_endpoint_xml}
      <cac:PartyName>
        <cbc:Name>{esc(buyer_name)}</cbc:Name>
      </cac:PartyName>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{esc(buyer_vat)}</cbc:CompanyID>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:PartyTaxScheme>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>{esc(buyer_name)}</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="{esc(currency)}">{float(tax_amt):.2f}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="{esc(currency)}">{float(taxable):.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="{esc(currency)}">{float(tax_amt):.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>{cat_id}</cbc:ID>
        <cbc:Percent>{float(Decimal("0") if reverse_charge else rate):.2f}</cbc:Percent>{tax_exemption}
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="{esc(currency)}">{float(taxable):.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="{esc(currency)}">{float(taxable):.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="{esc(currency)}">{float(payable):.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="{esc(currency)}">{float(payable):.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
{chr(10).join(line_xml)}
</Invoice>
"""


def export_ubl_xml(session: Session, user: Any, invoice_id: int) -> tuple[Optional[str], Optional[str]]:
    """Return (xml_string, error_message). Does not mutate the invoice."""
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        return None, "Invoice not found"
    config = get_peppol_config(session, invoice.tenant_id)
    if not config:
        # Allow export with partial settings when module is installed (for offline review)
        if not _module_installed(session, invoice.tenant_id):
            return None, "The Peppol / EU VAT e-Invoice module is not installed."
        config = {
            "participant_id": _get_setting(session, invoice.tenant_id, "peppol_participant_id")
            or "0088:0000000000000",
            "seller_name": _get_setting(session, invoice.tenant_id, "company_name") or "Seller",
            "seller_vat": _get_setting(session, invoice.tenant_id, "tax_id"),
            "seller_country": (_get_setting(session, invoice.tenant_id, "country") or "NL")[:2].upper(),
            "currency": getattr(invoice, "currency", None)
            or _get_setting(session, invoice.tenant_id, "currency")
            or "EUR",
            "address_line1": _get_setting(session, invoice.tenant_id, "address_line1"),
            "city": _get_setting(session, invoice.tenant_id, "city"),
        }
    lines = list(
        session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)).all()
    )
    customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    xml_body = build_ubl_bis_billing_xml(invoice, lines, config, customer=customer)
    return xml_body, None


def submit_to_peppol(session: Session, user: Any, invoice_id: int) -> dict:
    """POST UBL XML to the configured Access Point. Never raises.

    Returns success, peppol_status, peppol_document_id, error_message, log_id.
    """
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        return {
            "success": False,
            "peppol_status": None,
            "error_message": "Invoice not found",
            "log_id": None,
        }

    config = get_peppol_config(session, invoice.tenant_id)
    if not config:
        return {
            "success": False,
            "peppol_status": invoice.peppol_status,
            "peppol_document_id": invoice.peppol_document_id,
            "error_message": (
                "Peppol is not enabled or participant ID / Access Point URL is missing in Settings."
            ),
            "log_id": None,
        }

    lines = list(
        session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)).all()
    )
    customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    document_id = invoice.peppol_document_id or str(uuid_mod.uuid4())
    xml_body = build_ubl_bis_billing_xml(
        invoice, lines, config, customer=customer, document_id=document_id,
    )
    endpoint = config["ap_url"]

    invoice.peppol_status = "submitted"
    session.add(invoice)
    session.flush()

    log = PeppolSubmissionLog(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice_id,
        request_payload=xml_body[:8000],
        endpoint=endpoint,
        sandbox=config["sandbox"],
        status="submitted",
        document_id=document_id,
    )

    headers = {
        "Content-Type": "application/xml",
        "Accept": "application/json, application/xml, text/plain",
        "X-Peppol-Participant-ID": config["participant_id"],
    }
    if config.get("api_key"):
        headers["Authorization"] = f"Bearer {config['api_key']}"

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(endpoint, content=xml_body.encode("utf-8"), headers=headers)
        log.http_status = resp.status_code
        log.response_payload = (resp.text or "")[:4000]

        ok = 200 <= resp.status_code < 300
        resp_data: dict = {}
        try:
            resp_data = resp.json()
        except Exception:
            pass

        if ok:
            api_doc = (
                resp_data.get("documentId")
                or resp_data.get("document_id")
                or resp_data.get("id")
            )
            if isinstance(api_doc, str) and api_doc:
                document_id = api_doc
            log.status = "accepted"
            log.document_id = document_id
            invoice.peppol_status = "accepted"
            invoice.peppol_document_id = document_id
            invoice.peppol_submitted_at = datetime.utcnow()
            session.add(invoice)
        else:
            status = "rejected" if 400 <= resp.status_code < 500 else "error"
            log.status = status
            log.error_message = (
                resp_data.get("message")
                or resp_data.get("error")
                or f"HTTP {resp.status_code}"
            )[:500]
            invoice.peppol_status = status
            session.add(invoice)
    except Exception as exc:
        log.status = "error"
        log.error_message = str(exc)[:500]
        invoice.peppol_status = "error"
        session.add(invoice)

    session.add(log)
    session.commit()
    session.refresh(log)
    session.refresh(invoice)

    return {
        "success": log.status == "accepted",
        "peppol_status": invoice.peppol_status,
        "peppol_document_id": invoice.peppol_document_id,
        "peppol_submitted_at": invoice.peppol_submitted_at,
        "error_message": log.error_message,
        "log_id": log.id,
        "sandbox": config["sandbox"],
        "http_status": log.http_status,
    }
