"""Studio field catalog — type hints for Add Field LOV + form-layout rows.

Custom extras stay ``x.*`` (cap 12 per entity). Core form fields can be
hidden or required; locked keys cannot be hidden.
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from models import CustomFieldDef
from services.custom_fields import MAX_DEFS, KEY_RE, assert_entity
from services.form_schema import CORE_FIELDS, LOCKED_FIELDS

# Curated extra-column type hints (not tenant data). Users may still type a
# custom ``x.<ident>`` that is not in this list.
SUGGESTED_EXTRAS: dict[str, tuple[dict[str, str], ...]] = {
    "invoice": (
        {"key": "x.gate_pass_no", "label": "Gate pass", "type": "text",
         "hint": "Vehicle or site gate-pass number (Weighbridge / dispatch)."},
        {"key": "x.lot_ref", "label": "Lot ref", "type": "text",
         "hint": "Yarn, fabric, or shipment lot on the invoice."},
        {"key": "x.vehicle_no", "label": "Vehicle no", "type": "text",
         "hint": "Truck or van registration."},
        {"key": "x.container_no", "label": "Container no", "type": "text",
         "hint": "Shipping container identifier."},
        {"key": "x.driver_name", "label": "Driver", "type": "text",
         "hint": "Driver name for the load."},
        {"key": "x.seal_no", "label": "Seal no", "type": "text",
         "hint": "Container or vehicle seal."},
        {"key": "x.bl_number", "label": "B/L number", "type": "text",
         "hint": "Bill of lading."},
        {"key": "x.lc_no", "label": "LC no", "type": "text",
         "hint": "Letter of credit reference."},
        {"key": "x.delivery_note", "label": "Delivery note", "type": "text",
         "hint": "Customer delivery-note number."},
        {"key": "x.po_ref", "label": "Customer PO", "type": "text",
         "hint": "Buyer's purchase-order number."},
        {"key": "x.packing_list_no", "label": "Packing list", "type": "text",
         "hint": "Packing-list reference."},
        {"key": "x.export_permit", "label": "Export permit", "type": "text",
         "hint": "Export licence or permit."},
    ),
    "bill": (
        {"key": "x.gate_pass_no", "label": "Gate pass", "type": "text",
         "hint": "Inward gate-pass against the bill."},
        {"key": "x.grn_no", "label": "GRN no", "type": "text",
         "hint": "Goods-receipt number."},
        {"key": "x.vehicle_no", "label": "Vehicle no", "type": "text",
         "hint": "Inbound vehicle registration."},
        {"key": "x.lot_ref", "label": "Lot ref", "type": "text",
         "hint": "Supplier lot or batch."},
        {"key": "x.container_no", "label": "Container no", "type": "text",
         "hint": "Inbound container identifier."},
        {"key": "x.lc_no", "label": "LC no", "type": "text",
         "hint": "Letter of credit on the purchase."},
        {"key": "x.bl_number", "label": "B/L number", "type": "text",
         "hint": "Bill of lading."},
        {"key": "x.driver_name", "label": "Driver", "type": "text",
         "hint": "Inbound driver name."},
    ),
    "customer": (
        {"key": "x.trade_license", "label": "Trade licence", "type": "text",
         "hint": "Trade or commercial licence number."},
        {"key": "x.credit_ref", "label": "Credit ref", "type": "text",
         "hint": "Internal credit-control reference."},
        {"key": "x.region", "label": "Region", "type": "text",
         "hint": "Sales region or territory."},
        {"key": "x.sales_rep", "label": "Sales rep", "type": "text",
         "hint": "Assigned salesperson name or code."},
        {"key": "x.vat_group", "label": "VAT group", "type": "text",
         "hint": "VAT grouping code."},
        {"key": "x.route", "label": "Route", "type": "text",
         "hint": "Delivery route."},
    ),
    "vendor": (
        {"key": "x.trade_license", "label": "Trade licence", "type": "text",
         "hint": "Supplier trade licence."},
        {"key": "x.bank_iban", "label": "Bank IBAN", "type": "text",
         "hint": "Supplier IBAN for payments."},
        {"key": "x.msme_no", "label": "MSME no", "type": "text",
         "hint": "MSME / small-business registration."},
        {"key": "x.region", "label": "Region", "type": "text",
         "hint": "Sourcing region."},
        {"key": "x.contact_person", "label": "Contact person", "type": "text",
         "hint": "Primary vendor contact."},
        {"key": "x.lead_days", "label": "Lead days", "type": "number",
         "hint": "Typical delivery lead time in days."},
    ),
    "product": (
        {"key": "x.origin_country", "label": "Origin country", "type": "text",
         "hint": "Country of origin."},
        {"key": "x.color", "label": "Color", "type": "text",
         "hint": "Colour or shade."},
        {"key": "x.gsm", "label": "GSM", "type": "number",
         "hint": "Fabric grams per square metre."},
        {"key": "x.width", "label": "Width", "type": "text",
         "hint": "Width or size."},
        {"key": "x.composition", "label": "Composition", "type": "text",
         "hint": "Fibre or material mix."},
        {"key": "x.brand", "label": "Brand", "type": "text",
         "hint": "Brand or make."},
        {"key": "x.barcode_alt", "label": "Alt barcode", "type": "text",
         "hint": "Secondary barcode or SKU."},
    ),
}

_LABEL_OVERRIDES: dict[str, str] = {
    "issue_date": "Issue date",
    "bill_date": "Bill date",
    "due_date": "Due date",
    "customer_id": "Customer",
    "vendor_id": "Vendor",
    "customer_name": "Customer name",
    "vendor_name": "Vendor name",
    "subtotal": "Subtotal",
    "gst_amount": "GST amount",
    "gst_rate": "GST rate",
    "total": "Total",
    "qty": "Quantity",
    "rate": "Rate",
    "amount": "Line amount",
    "discount_pct": "Line discount %",
    "internal_memo": "Internal memo",
    "notes": "Notes",
    "description": "Description",
    "analytic_account_id": "Analytic 1",
    "analytic_2_id": "Analytic 2",
    "analytic_3_id": "Analytic 3",
    "assigned_to_id": "Assigned to",
    "payment_term_id": "Payment term",
    "ar_account_id": "AR account",
    "ap_account_id": "AP account",
    "revenue_account_id": "Revenue account",
    "expense_account_id": "Expense account",
    "payment_mode": "Payment mode",
    "buyer_ntn": "Buyer NTN",
    "buyer_cnic": "Buyer CNIC",
    "is_intercompany": "Intercompany",
    "ic_counterparty_tenant_id": "IC counterparty",
    "currency": "Currency",
    "exchange_rate": "Exchange rate",
    "email": "Email",
    "phone": "Phone",
    "address": "Address",
    "ntn": "NTN",
    "cnic": "CNIC",
    "gstin": "GSTIN",
    "state_code": "State code",
    "opening_balance": "Opening balance",
    "wht_tax_code_id": "WHT tax code",
    "wht_rate": "WHT rate",
    "code": "Code",
    "unit": "Unit",
    "product_type": "Product type",
    "default_rate": "Sale price",
    "reorder_level": "Reorder level",
    "category_id": "Category",
    "hs_code": "HS code",
    "pct_code": "PCT code",
    "hsn_sac": "HSN/SAC",
    "is_deferred": "Deferred revenue",
    "recognition_months": "Recognition months",
    "cost_method": "Cost method",
    "track_lot": "Track lot",
    "track_serial": "Track serial",
    "standalone_selling_price": "Standalone selling price",
    "name": "Name",
}

_NUMBER_KEYS = frozenset({
    "subtotal", "gst_amount", "gst_rate", "total", "qty", "rate", "amount",
    "discount_pct", "exchange_rate", "opening_balance", "default_rate",
    "reorder_level", "recognition_months", "standalone_selling_price",
    "wht_rate",
})
_DATE_SUFFIXES = ("_date",)
_BOOL_PREFIXES = ("is_", "track_")


def human_label(key: str) -> str:
    if key in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[key]
    if KEY_RE.match(key):
        return key[2:].replace("_", " ").capitalize()
    return key.replace("_id", "").replace("_", " ").strip().capitalize()


def infer_type(key: str) -> str:
    if key in _NUMBER_KEYS or key.endswith("_id"):
        return "number"
    if any(key.endswith(s) for s in _DATE_SUFFIXES):
        return "date"
    if any(key.startswith(p) for p in _BOOL_PREFIXES):
        return "bool"
    return "text"


def _locked_hint(entity: str, key: str) -> str:
    if key in LOCKED_FIELDS.get(entity, ()):
        return "Locked — required for posting; cannot hide."
    if KEY_RE.match(key):
        return "Extra column on this record. Never posts to the GL."
    return "Core form field. Hide or require without changing the GL."


def field_catalog(session: Session, tenant_id: int, entity: str) -> dict[str, Any]:
    entity = assert_entity(entity)
    defs = list(
        session.exec(
            select(CustomFieldDef).where(
                CustomFieldDef.tenant_id == tenant_id,
                CustomFieldDef.entity == entity,
            )
        ).all()
    )
    by_key = {d.key: d for d in defs}
    active = [d for d in defs if d.archived_at is None]
    used = len(active)
    existing_keys = set(by_key)

    suggestions: list[dict[str, Any]] = []
    for row in SUGGESTED_EXTRAS.get(entity, ()):
        existing = by_key.get(row["key"])
        suggestions.append({
            "key": row["key"],
            "label": row["label"],
            "type": row["type"],
            "hint": row["hint"],
            "added": existing is not None and existing.archived_at is None,
            "archived": existing is not None and existing.archived_at is not None,
            "source": "suggestion",
        })
    # Tenant-defined extras that are not in the curated list still appear
    # as type hints so the LOV stays complete.
    suggested_keys = {s["key"] for s in suggestions}
    for d in active:
        if d.key in suggested_keys:
            continue
        suggestions.append({
            "key": d.key,
            "label": d.label,
            "type": d.type,
            "hint": "Already added extra column.",
            "added": True,
            "archived": False,
            "source": "custom",
        })

    form_fields: list[dict[str, Any]] = []
    locked = LOCKED_FIELDS.get(entity, frozenset())
    for key in sorted(CORE_FIELDS.get(entity, ())):
        form_fields.append({
            "key": key,
            "label": human_label(key),
            "type": infer_type(key),
            "kind": "core",
            "locked": key in locked,
            "hint": _locked_hint(entity, key),
        })
    for d in sorted(active, key=lambda r: (r.sort_order or 0, r.id or 0)):
        form_fields.append({
            "key": d.key,
            "label": d.label,
            "type": d.type,
            "kind": "custom",
            "locked": False,
            "hint": _locked_hint(entity, d.key),
        })

    return {
        "entity": entity,
        "cap": MAX_DEFS,
        "used": used,
        "remaining": max(0, MAX_DEFS - used),
        "suggestions": suggestions,
        "form_fields": form_fields,
        "existing_keys": sorted(existing_keys),
    }
