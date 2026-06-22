"""PRA (Punjab Revenue Authority) e-Invoice / eIMS integration.

Follows the same graceful-no-op pattern as services/email.py:
- Returns immediately when pra_enabled != "true" in tenant settings
- Never raises — failures are logged to PRASubmissionLog and surfaced via invoice.pra_status
- Retries are safe because USIN = invoice.number (already unique per tenant)

API reference: https://e.pra.punjab.gov.pk/ (POS_COMPONENT_and_eIMS_User_Manual.pdf)
"""
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx
from sqlmodel import Session, select

from models import (
    Customer, Invoice, InvoiceLine, PRASubmissionLog, Product, Settings, TaxCode,
)

SANDBOX_URL = "https://ims.pral.com.pk/ims/sandbox/api/Live/PostData"
PRODUCTION_URL = "https://ims.pral.com.pk/ims/production/api/Live/PostData"
SANDBOX_TOKEN = "24d8fab3-f2e9-398f-ae17-b387125ec4a2"

PAYMENT_MODE_LABELS = {1: "Cash", 2: "Card", 3: "Gift Voucher", 4: "Loyalty Card", 5: "Mixed", 6: "Cheque"}


def _get_setting(session: Session, tenant_id: int, key: str, default: str = "") -> str:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row else default


def get_pra_config(session: Session, tenant_id: int) -> Optional[dict]:
    """Return PRA configuration dict, or None if not enabled/configured."""
    if _get_setting(session, tenant_id, "pra_enabled") != "true":
        return None
    pos_id = _get_setting(session, tenant_id, "pra_pos_id")
    if not pos_id:
        return None
    sandbox = _get_setting(session, tenant_id, "pra_sandbox_mode") == "true"
    token = SANDBOX_TOKEN if sandbox else _get_setting(session, tenant_id, "pra_api_token")
    return {
        "pos_id": pos_id,
        "token": token,
        "endpoint": SANDBOX_URL if sandbox else PRODUCTION_URL,
        "sandbox": sandbox,
    }


def build_pra_payload(
    invoice: Invoice,
    lines: list[InvoiceLine],
    customer: Optional[Customer],
    products_by_id: dict[int, Product],
    tax_codes_by_id: dict[int, TaxCode],
    config: dict,
) -> dict:
    """Map an Easy-Books invoice to the PRA e-IMS JSON payload."""
    gst_rate = float(invoice.gst_rate or Decimal("17"))

    # Invoice type: credit notes → 3, debit notes → 2, standard → 1
    invoice_type = 1

    total_qty = sum(float(l.qty) for l in lines)
    total_sale_value = float(invoice.subtotal)
    total_tax = float(invoice.gst_amount)
    total_bill = float(invoice.total)
    total_discount = 0.0

    pra_items = []
    for line in lines:
        product = products_by_id.get(line.product_id) if line.product_id else None
        tc = tax_codes_by_id.get(line.tax_code_id) if line.tax_code_id else None
        tax_rate = float(tc.rate) if tc else gst_rate

        line_amount = float(line.amount)
        # Reverse-compute pre-discount sale value for this line
        disc_pct = float(line.discount_pct or 0)
        if disc_pct > 0:
            pre_disc = line_amount / (1 - disc_pct / 100)
            disc_amount = pre_disc - line_amount
        else:
            pre_disc = line_amount
            disc_amount = 0.0
        total_discount += disc_amount

        line_tax = round(line_amount * tax_rate / 100, 2)
        line_total = line_amount + line_tax

        pra_items.append({
            "ItemCode": (product.code if product and product.code else None) or str(line.product_id or "SVC"),
            "ItemName": line.description[:150],
            "Quantity": float(line.qty),
            "PCTCode": (product.pct_code if product and product.pct_code else "00000000"),
            "TaxRate": tax_rate,
            "SaleValue": round(line_amount, 2),
            "TaxCharged": line_tax,
            "TotalAmount": round(line_total, 2),
            "Discount": round(disc_amount, 2),
            "FurtherTax": 0.0,
            "InvoiceType": invoice_type,
            "RefUSIN": None,
        })

    payload = {
        "InvoiceNumber": "",
        "POSID": int(config["pos_id"]),
        "USIN": invoice.number,
        "DateTime": f"{invoice.issue_date} 00:00:00",
        "BuyerName": (customer.name if customer else invoice.customer_name) or "",
        "BuyerPNTN": (customer.ntn if customer else None) or "",
        "BuyerCNIC": (customer.cnic if customer else None) or "",
        "BuyerPhoneNumber": (customer.phone if customer else None) or "",
        "TotalBillAmount": round(total_bill, 2),
        "TotalQuantity": round(total_qty, 2),
        "TotalSaleValue": round(total_sale_value, 2),
        "TotalTaxCharged": round(total_tax, 2),
        "Discount": round(total_discount, 2),
        "FurtherTax": 0.0,
        "PaymentMode": invoice.payment_mode or 1,
        "RefUSIN": None,
        "InvoiceType": invoice_type,
        "Items": pra_items,
    }
    return payload


def submit_to_pra(session: Session, invoice_id: int) -> bool:
    """
    Submit an invoice to PRA eIMS. Updates invoice.pra_status in-place.
    Returns True on success, False on any failure.
    Safe to retry: USIN = invoice.number is idempotent at PRA.
    """
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        return False

    config = get_pra_config(session, invoice.tenant_id)
    if not config:
        return False  # PRA not configured for this tenant

    lines = session.exec(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)
    ).all()
    customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None

    product_ids = [l.product_id for l in lines if l.product_id]
    products_by_id: dict[int, Product] = {}
    if product_ids:
        prods = session.exec(select(Product).where(Product.id.in_(product_ids))).all()  # type: ignore[attr-defined]
        products_by_id = {p.id: p for p in prods}

    tc_ids = [l.tax_code_id for l in lines if l.tax_code_id]
    tax_codes_by_id: dict[int, TaxCode] = {}
    if tc_ids:
        tcs = session.exec(select(TaxCode).where(TaxCode.id.in_(tc_ids))).all()  # type: ignore[attr-defined]
        tax_codes_by_id = {tc.id: tc for tc in tcs}

    payload = build_pra_payload(invoice, lines, customer, products_by_id, tax_codes_by_id, config)
    payload_json = json.dumps(payload)

    log = PRASubmissionLog(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice_id,
        endpoint=config["endpoint"],
        request_json=payload_json,
    )

    try:
        resp = httpx.post(
            config["endpoint"],
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config['token']}",
            },
            timeout=15.0,
        )
        log.http_status = resp.status_code
        log.response_json = resp.text[:4000]
        resp_data = resp.json()
        log.response_code = str(resp_data.get("Code", ""))
        if log.response_code == "100":
            fiscal_number = resp_data.get("InvoiceNumber", "")
            log.success = True
            invoice.pra_status = "submitted"
            invoice.pra_fiscal_number = fiscal_number
            invoice.pra_submitted_at = datetime.utcnow()
            invoice.pra_response_raw = resp.text[:2000]
            session.add(invoice)
        else:
            log.success = False
            log.error_message = resp_data.get("Response") or resp_data.get("Errors") or f"Code {log.response_code}"
            invoice.pra_status = "failed"
            invoice.pra_response_raw = resp.text[:2000]
            session.add(invoice)
    except Exception as exc:
        log.success = False
        log.error_message = str(exc)[:500]
        invoice.pra_status = "failed"
        session.add(invoice)

    session.add(log)
    session.commit()
    return log.success
