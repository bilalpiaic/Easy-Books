"""FBR Digital Invoicing (PRAL DI API v1.12).

The add-on key remains ``pra`` (historic module name). Payloads follow the
FBR DI object model — not the legacy Punjab eIMS USIN/POS/PCT shape.

- Never raises to the invoice save path; failures go to PRASubmissionLog
- Validate-then-post against gw.fbr.gov.pk
- ``scenarioId`` is attached in sandbox only
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import httpx
from sqlmodel import Session, select

from models import (
    Customer,
    Invoice,
    InvoiceLine,
    PRASubmissionLog,
    Product,
    Settings,
    TaxCode,
)

POST_SANDBOX = "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
POST_PRODUCTION = "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata"
VALIDATE_SANDBOX = "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata_sb"
VALIDATE_PRODUCTION = "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata"
SANDBOX_URL = POST_SANDBOX  # back-compat alias for older imports

REF_BASE = "https://gw.fbr.gov.pk/pdi"
DIST_BASE = "https://gw.fbr.gov.pk/dist/v1"

INVOICE_TYPE_SALE = "Sale Invoice"
INVOICE_TYPE_DEBIT = "Debit Note"

REG_REGISTERED = "Registered"
REG_UNREGISTERED = "Unregistered"

SALE_STANDARD = "Goods at standard rate (default)"
SALE_REDUCED = "Goods at Reduced Rate"
SALE_EXEMPT = "Exempt goods"
SALE_ZERO = "Goods at zero-rate"
SALE_THIRD = "3rd Schedule Goods"
SALE_SRO297 = "Goods as per SRO.297(|)/2023"
SALE_NON_ADJ = "Non-Adjustable Supplies"
SALE_SERVICES = "Services"

SALE_TYPES: tuple[str, ...] = (
    SALE_STANDARD,
    SALE_REDUCED,
    SALE_EXEMPT,
    SALE_ZERO,
    SALE_THIRD,
    "Steel melting and re-rolling",
    "Ship breaking",
    "Cotton Ginners",
    "Telecommunication services",
    "Toll Manufacturing",
    "Petroleum Products",
    "Electricity Supply to Retailers",
    "Gas to CNG stations",
    "Mobile Phones",
    "Processing/ Conversion of Goods",
    "Goods (FED in ST Mode)",
    "Services (FED in ST Mode)",
    SALE_SERVICES,
    "Electric Vehicle",
    "Cement /Concrete Block",
    "Potassium Chlorate",
    "CNG Sales",
    SALE_SRO297,
    SALE_NON_ADJ,
)

# SN → (description, saleType) from DI spec §9
SCENARIOS: dict[str, dict[str, str]] = {
    "SN001": {"label": "Standard rate to registered buyers", "sale_type": SALE_STANDARD},
    "SN002": {"label": "Standard rate to unregistered buyers", "sale_type": SALE_STANDARD},
    "SN003": {"label": "Steel melted and re-rolled", "sale_type": "Steel melting and re-rolling"},
    "SN004": {"label": "Steel scrap by ship breakers", "sale_type": "Ship breaking"},
    "SN005": {"label": "Reduced rate (Eighth Schedule)", "sale_type": SALE_REDUCED},
    "SN006": {"label": "Exempt goods (Sixth Schedule)", "sale_type": SALE_EXEMPT},
    "SN007": {"label": "Zero-rated goods (Fifth Schedule)", "sale_type": SALE_ZERO},
    "SN008": {"label": "3rd Schedule goods", "sale_type": SALE_THIRD},
    "SN009": {"label": "Purchase from registered cotton ginners", "sale_type": "Cotton Ginners"},
    "SN010": {"label": "Telecom services", "sale_type": "Telecommunication services"},
    "SN011": {"label": "Steel toll manufacturing", "sale_type": "Toll Manufacturing"},
    "SN012": {"label": "Petroleum products", "sale_type": "Petroleum Products"},
    "SN013": {"label": "Electricity to retailers", "sale_type": "Electricity Supply to Retailers"},
    "SN014": {"label": "Gas to CNG stations", "sale_type": "Gas to CNG stations"},
    "SN015": {"label": "Mobile phones", "sale_type": "Mobile Phones"},
    "SN016": {"label": "Processing / conversion of goods", "sale_type": "Processing/ Conversion of Goods"},
    "SN017": {"label": "Goods FED in ST mode", "sale_type": "Goods (FED in ST Mode)"},
    "SN018": {"label": "Services FED in ST mode", "sale_type": "Services (FED in ST Mode)"},
    "SN019": {"label": "Services (ICT Ordinance)", "sale_type": SALE_SERVICES},
    "SN020": {"label": "Electric vehicles", "sale_type": "Electric Vehicle"},
    "SN021": {"label": "Cement / concrete block", "sale_type": "Cement /Concrete Block"},
    "SN022": {"label": "Potassium chlorate", "sale_type": "Potassium Chlorate"},
    "SN023": {"label": "CNG", "sale_type": "CNG Sales"},
    "SN024": {"label": "Goods listed in SRO 297(I)/2023", "sale_type": SALE_SRO297},
    "SN025": {"label": "Drugs at fixed ST (Eighth Sch. Sr 81)", "sale_type": SALE_NON_ADJ},
    "SN026": {"label": "Retailer: standard rate to end consumer", "sale_type": SALE_STANDARD},
    "SN027": {"label": "Retailer: 3rd Schedule to end consumer", "sale_type": SALE_THIRD},
    "SN028": {"label": "Retailer: reduced rate to end consumer", "sale_type": SALE_REDUCED},
}

# Spec §10 — activity + sector → allowed SN codes. SN026–028 need retailer profile.
_COMMON = ("SN001", "SN002", "SN005", "SN006", "SN007", "SN015", "SN016", "SN017", "SN021", "SN022", "SN024")
_RETAIL_END = ("SN026", "SN027", "SN028", "SN008")

ACTIVITY_SECTOR_SCENARIOS: dict[tuple[str, str], tuple[str, ...]] = {}


def _reg(activity: str, sector: str, extra: tuple[str, ...] = ()) -> None:
    ACTIVITY_SECTOR_SCENARIOS[(activity, sector)] = _COMMON + extra


for _act in ("Manufacturer", "Importer", "Exporter", "Other"):
    _reg(_act, "All Other Sectors")
    _reg(_act, "Steel", ("SN003", "SN004", "SN011"))
    _reg(_act, "FMCG", ("SN008",))
    _reg(_act, "Textile", ("SN009",))
    _reg(_act, "Telecom", ("SN010",))
    _reg(_act, "Petroleum", ("SN012",))
    _reg(_act, "Electricity Distribution", ("SN013",))
    _reg(_act, "Gas Distribution", ("SN014",))
    _reg(_act, "Services", ("SN018", "SN019"))
    _reg(_act, "Automobile", ("SN020",))
    _reg(_act, "CNG Stations", ("SN023",))
    _reg(_act, "Pharmaceuticals", ("SN025",) if _act != "Manufacturer" else ())
    _reg(_act, "Wholesale / Retails", _RETAIL_END)

for _act in ("Distributor", "Wholesaler"):
    ACTIVITY_SECTOR_SCENARIOS[(_act, "All Other Sectors")] = _COMMON + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Steel")] = ("SN003", "SN004", "SN011") + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "FMCG")] = _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Textile")] = ("SN009",) + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Telecom")] = ("SN010",) + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Petroleum")] = ("SN012",) + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Electricity Distribution")] = ("SN013",) + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Gas Distribution")] = ("SN014",) + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Services")] = ("SN018", "SN019") + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Automobile")] = ("SN020",) + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "CNG Stations")] = ("SN023",) + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Pharmaceuticals")] = ("SN025",) + _RETAIL_END
    ACTIVITY_SECTOR_SCENARIOS[(_act, "Wholesale / Retails")] = ("SN001", "SN002") + _RETAIL_END

ACTIVITY_SECTOR_SCENARIOS[("Retailer", "All Other Sectors")] = _COMMON + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Steel")] = ("SN003", "SN004", "SN011")
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "FMCG")] = _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Textile")] = ("SN009",) + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Telecom")] = ("SN010",) + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Petroleum")] = ("SN012",) + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Electricity Distribution")] = ("SN013",) + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Gas Distribution")] = ("SN014",) + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Services")] = ("SN018", "SN019") + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Automobile")] = ("SN020",) + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "CNG Stations")] = ("SN023",) + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Pharmaceuticals")] = ("SN025",) + _RETAIL_END
ACTIVITY_SECTOR_SCENARIOS[("Retailer", "Wholesale / Retails")] = _RETAIL_END

ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "All Other Sectors")] = _COMMON + ("SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Steel")] = ("SN003", "SN004", "SN011", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "FMCG")] = ("SN008", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Textile")] = ("SN009", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Telecom")] = ("SN010", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Petroleum")] = ("SN012", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Electricity Distribution")] = ("SN013", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Gas Distribution")] = ("SN014", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Services")] = ("SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Automobile")] = ("SN020", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "CNG Stations")] = ("SN023", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Pharmaceuticals")] = ("SN025", "SN018", "SN019")
ACTIVITY_SECTOR_SCENARIOS[("Service Provider", "Wholesale / Retails")] = _RETAIL_END + ("SN018", "SN019")

ACTIVITIES = (
    "Manufacturer", "Importer", "Distributor", "Wholesaler",
    "Exporter", "Retailer", "Service Provider", "Other",
)
SECTORS = (
    "All Other Sectors", "Steel", "FMCG", "Textile", "Telecom", "Petroleum",
    "Electricity Distribution", "Gas Distribution", "Services", "Automobile",
    "CNG Stations", "Pharmaceuticals", "Wholesale / Retails",
)

PROVINCES_FALLBACK = (
    "Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan",
    "Islamabad Capital Territory", "Azad Jammu and Kashmir", "Gilgit-Baltistan",
)

UOM_FALLBACK = (
    "Numbers, pieces, units", "KG", "MT", "Litre", "Meter", "Square Metre",
    "Dozen", "KWH",
)

UNIT_TO_FBR = {
    "pcs": "Numbers, pieces, units",
    "kg": "KG",
    "mt": "MT",
    "mtr": "Meter",
    "ltr": "Litre",
    "doz": "Dozen",
    "box": "Numbers, pieces, units",
    "hrs": "Numbers, pieces, units",
}

THIRD_SCHEDULE_TYPES = {SALE_THIRD}
RETAILER_ONLY = {"SN026", "SN027", "SN028"}

# Local POS labels — never sent to FBR DI
PAYMENT_MODE_LABELS = {1: "Cash", 2: "Card", 3: "Gift Voucher", 4: "Loyalty Card", 5: "Mixed", 6: "Cheque"}

_REF_CACHE: dict[str, tuple[float, Any]] = {}
_REF_TTL = 300.0


def _get_setting(session: Session, tenant_id: int, key: str, default: str = "") -> str:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row else default


def _digits(value: Optional[str]) -> str:
    return re.sub(r"\D+", "", value or "")


def _f(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _money(value: float) -> float:
    return round(float(value), 2)


def format_rate_desc(rate: Any, sale_type: str = "") -> str:
    """FBR ``rate`` is a string from SaleTypeToRate.ratE_DESC (e.g. '18%', 'Exempt')."""
    if sale_type == SALE_EXEMPT:
        return "Exempt"
    if isinstance(rate, str) and rate.strip():
        text = rate.strip()
        if text[-1] == "%" or text.lower() == "exempt":
            return "Exempt" if text.lower() == "exempt" else text
        try:
            rate = float(text)
        except ValueError:
            return text
    num = _f(rate)
    if num == int(num):
        return f"{int(num)}%"
    return f"{num:g}%"


def map_uom(unit: Optional[str], override: Optional[str] = None) -> str:
    if override and str(override).strip():
        return str(override).strip()
    key = (unit or "pcs").strip().lower()
    return UNIT_TO_FBR.get(key, unit or "Numbers, pieces, units")


def scenarios_for(activity: str, sector: str) -> list[dict]:
    keys = ACTIVITY_SECTOR_SCENARIOS.get((activity, sector))
    if not keys:
        keys = ACTIVITY_SECTOR_SCENARIOS.get((activity, "All Other Sectors"), _COMMON)
    out = []
    for sn in keys:
        meta = SCENARIOS.get(sn)
        if not meta:
            continue
        out.append({"id": sn, "label": meta["label"], "sale_type": meta["sale_type"]})
    return out


def default_scenario_for(activity: str, sector: str, sale_type: Optional[str] = None) -> str:
    allowed = {row["id"] for row in scenarios_for(activity, sector)}
    if sale_type:
        for sn, meta in SCENARIOS.items():
            if meta["sale_type"] == sale_type and sn in allowed:
                return sn
    if "SN026" in allowed:
        return "SN026"
    if "SN001" in allowed:
        return "SN001"
    return next(iter(allowed), "SN001")


def get_pra_config(session: Session, tenant_id: int) -> Optional[dict]:
    """Return DI configuration, or None if the module switch is off."""
    if _get_setting(session, tenant_id, "pra_enabled") != "true":
        return None
    sandbox = _get_setting(session, tenant_id, "pra_sandbox_mode") != "false"
    token = _get_setting(session, tenant_id, "pra_api_token")
    addr1 = _get_setting(session, tenant_id, "address_line1")
    city = _get_setting(session, tenant_id, "city")
    address = ", ".join(p for p in (addr1, city) if p) or _get_setting(session, tenant_id, "pra_seller_address")
    activity = _get_setting(session, tenant_id, "pra_business_activity") or "Retailer"
    sector = _get_setting(session, tenant_id, "pra_sector") or "Wholesale / Retails"
    return {
        "sandbox": sandbox,
        "token": token,
        "post_url": POST_SANDBOX if sandbox else POST_PRODUCTION,
        "validate_url": VALIDATE_SANDBOX if sandbox else VALIDATE_PRODUCTION,
        "seller_ntn": _digits(_get_setting(session, tenant_id, "pra_ntn")),
        "seller_business_name": _get_setting(session, tenant_id, "company_name") or "Company",
        "seller_province": _get_setting(session, tenant_id, "pra_seller_province") or "Punjab",
        "seller_address": address or "Pakistan",
        "business_activity": activity,
        "sector": sector,
        "default_scenario": default_scenario_for(activity, sector),
        # kept so older callers that still read pos_id do not crash
        "pos_id": _get_setting(session, tenant_id, "pra_pos_id"),
        "endpoint": POST_SANDBOX if sandbox else POST_PRODUCTION,
    }


def _buyer_reg_type(invoice: Invoice, customer: Optional[Customer]) -> str:
    raw = getattr(invoice, "buyer_registration_type", None) or (
        getattr(customer, "registration_type", None) if customer else None
    )
    if raw and str(raw).lower().startswith("unreg"):
        return REG_UNREGISTERED
    if raw and str(raw).lower().startswith("reg"):
        return REG_REGISTERED
    ntn = invoice.buyer_ntn or (customer.ntn if customer else None)
    return REG_REGISTERED if _digits(ntn) else REG_UNREGISTERED


def _buyer_ntn_cnic(invoice: Invoice, customer: Optional[Customer], reg_type: str) -> str:
    ntn = invoice.buyer_ntn or (customer.ntn if customer else None)
    cnic = invoice.buyer_cnic or (customer.cnic if customer else None)
    digits = _digits(ntn) or _digits(cnic)
    if reg_type == REG_UNREGISTERED and not digits:
        return ""
    return digits


def _is_third_schedule(sale_type: str) -> bool:
    return sale_type in THIRD_SCHEDULE_TYPES


def _line_sale_type(line: InvoiceLine, product: Optional[Product], fallback: str) -> str:
    raw = getattr(line, "sale_type", None) or (getattr(product, "sale_type", None) if product else None)
    return (raw or fallback).strip() or SALE_STANDARD


def build_di_payload(
    invoice: Invoice,
    lines: list[InvoiceLine],
    customer: Optional[Customer],
    products_by_id: dict[int, Product],
    tax_codes_by_id: dict[int, TaxCode],
    config: dict,
    *,
    invoice_type: Optional[str] = None,
    invoice_ref_no: Optional[str] = None,
    scenario_id: Optional[str] = None,
    include_scenario: Optional[bool] = None,
) -> dict:
    """Map an Easy-Books invoice to the FBR DI JSON object model."""
    sandbox = bool(config.get("sandbox"))
    if include_scenario is None:
        include_scenario = sandbox

    doc_type = invoice_type or getattr(invoice, "di_invoice_type", None) or INVOICE_TYPE_SALE
    if doc_type not in (INVOICE_TYPE_SALE, INVOICE_TYPE_DEBIT):
        doc_type = INVOICE_TYPE_SALE
    ref_no = invoice_ref_no if invoice_ref_no is not None else (getattr(invoice, "di_invoice_ref_no", None) or "")

    activity = config.get("business_activity") or "Retailer"
    sector = config.get("sector") or "Wholesale / Retails"
    default_sale = SALE_STANDARD
    sn = scenario_id or getattr(invoice, "di_scenario_id", None) or config.get("default_scenario")
    if sn and sn in SCENARIOS:
        default_sale = SCENARIOS[sn]["sale_type"]

    reg_type = _buyer_reg_type(invoice, customer)
    buyer_name = (customer.name if customer else invoice.customer_name) or ""
    buyer_addr = (customer.address if customer else None) or ""
    buyer_prov = (
        getattr(invoice, "buyer_province", None)
        or (getattr(customer, "province", None) if customer else None)
        or config.get("seller_province")
        or "Punjab"
    )

    items: list[dict] = []
    for line in lines:
        product = products_by_id.get(line.product_id) if line.product_id else None
        tc = tax_codes_by_id.get(line.tax_code_id) if line.tax_code_id else None
        sale_type = _line_sale_type(line, product, default_sale)

        disc_pct = _f(getattr(line, "discount_pct", 0))
        line_amount = _f(line.amount)
        if disc_pct > 0:
            pre_disc = line_amount / (1 - disc_pct / 100)
            disc_amount = pre_disc - line_amount
        else:
            disc_amount = _f(getattr(line, "discount", None), 0.0)

        tax_rate = _f(getattr(line, "tax_rate", None))
        if not tax_rate and tc is not None:
            tax_rate = _f(tc.rate)
        if not tax_rate:
            tax_rate = _f(invoice.gst_rate, 18.0)

        rate_desc = getattr(line, "di_rate", None) or (getattr(product, "di_rate", None) if product else None)
        rate_desc = format_rate_desc(rate_desc or tax_rate, sale_type)

        mrp = _f(getattr(line, "fixed_notified_value", None))
        if not mrp and product is not None:
            mrp = _f(getattr(product, "fixed_notified_value", None))

        qty = _f(line.qty)
        if _is_third_schedule(sale_type):
            value_ex_st = _f(getattr(line, "value_sales_excluding_st", None), 0.0)
            base_for_tax = mrp * (qty if qty else 1.0)
        else:
            value_ex_st = _f(getattr(line, "value_sales_excluding_st", None), line_amount)
            base_for_tax = value_ex_st

        st_explicit = getattr(line, "sales_tax_applicable", None)
        if st_explicit is not None:
            st_amt = _f(st_explicit)
        elif getattr(line, "tax_amount", None) not in (None,):
            st_amt = _f(line.tax_amount)
        elif sale_type == SALE_EXEMPT or rate_desc == "Exempt":
            st_amt = 0.0
        else:
            st_amt = _money(base_for_tax * tax_rate / 100.0)

        further = _f(getattr(line, "further_tax", None))
        extra = getattr(line, "extra_tax", None)
        extra_out: Any = _f(extra) if extra not in (None, "") else 0.0
        fed = _f(getattr(line, "fed_payable", None))
        withheld = _f(getattr(line, "st_withheld", None))
        inclusive = _money(value_ex_st + st_amt + further + _f(extra_out) + fed)

        hs = (
            getattr(line, "hs_code", None)
            or (product.hs_code if product and product.hs_code else None)
            or ""
        )
        uom = map_uom(
            line.unit or (product.unit if product else None),
            getattr(line, "di_uom", None) or (getattr(product, "di_uom", None) if product else None),
        )
        sro = getattr(line, "sro_schedule_no", None) or (
            getattr(product, "sro_schedule_no", None) if product else None
        ) or ""
        sro_item = getattr(line, "sro_item_serial", None) or (
            getattr(product, "sro_item_serial", None) if product else None
        ) or ""

        items.append({
            "hsCode": str(hs).strip(),
            "productDescription": (line.description or "")[:500],
            "rate": rate_desc,
            "uoM": uom,
            "quantity": qty,
            "totalValues": inclusive,
            "valueSalesExcludingST": _money(value_ex_st),
            "fixedNotifiedValueOrRetailPrice": _money(mrp),
            "salesTaxApplicable": _money(st_amt),
            "salesTaxWithheldAtSource": _money(withheld),
            "extraTax": extra_out,
            "furtherTax": _money(further),
            "sroScheduleNo": str(sro),
            "fedPayable": _money(fed),
            "discount": _money(disc_amount),
            "saleType": sale_type,
            "sroItemSerialNo": str(sro_item),
        })

    payload: dict[str, Any] = {
        "invoiceType": doc_type,
        "invoiceDate": str(invoice.issue_date)[:10],
        "sellerNTNCNIC": config.get("seller_ntn") or "",
        "sellerBusinessName": config.get("seller_business_name") or "",
        "sellerProvince": config.get("seller_province") or "",
        "sellerAddress": config.get("seller_address") or "",
        "buyerNTNCNIC": _buyer_ntn_cnic(invoice, customer, reg_type),
        "buyerBusinessName": buyer_name,
        "buyerProvince": buyer_prov,
        "buyerAddress": buyer_addr,
        "buyerRegistrationType": reg_type,
        "invoiceRefNo": ref_no or "",
        "items": items,
    }
    if include_scenario:
        payload["scenarioId"] = sn or default_scenario_for(activity, sector, default_sale)
    return payload


# Back-compat alias used by older tests / imports
def build_pra_payload(*args, **kwargs):
    return build_di_payload(*args, **kwargs)


def local_validate_payload(payload: dict, *, sandbox: bool) -> list[str]:
    """Client-side gates matching the common FBR error codes (0002, 0010, …)."""
    errors: list[str] = []
    itype = payload.get("invoiceType")
    if itype not in (INVOICE_TYPE_SALE, INVOICE_TYPE_DEBIT):
        errors.append("0003: Provide proper invoice type.")
    date = payload.get("invoiceDate") or ""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date)):
        errors.append("0005: Provide date in YYYY-MM-DD format.")
    seller = _digits(payload.get("sellerNTNCNIC"))
    if len(seller) not in (7, 9, 13):
        errors.append("0108: Invalid Seller Registration No or NTN.")
    if not (payload.get("sellerBusinessName") or "").strip():
        errors.append("Seller business name is required.")
    if not (payload.get("sellerProvince") or "").strip():
        errors.append("0073: Provide Sale Origination Province of Supplier.")
    if not (payload.get("buyerBusinessName") or "").strip():
        errors.append("0010: Provide Buyer Name.")
    reg = payload.get("buyerRegistrationType")
    if reg not in (REG_REGISTERED, REG_UNREGISTERED):
        errors.append("0012: Provide Buyer Registration Type.")
    buyer = _digits(payload.get("buyerNTNCNIC"))
    if reg == REG_REGISTERED and len(buyer) not in (7, 9, 13):
        errors.append("0002: Invalid Buyer Registration No or NTN.")
    if itype == INVOICE_TYPE_DEBIT and not (payload.get("invoiceRefNo") or "").strip():
        errors.append("0026: Invoice Reference No. is required.")
    if sandbox and not payload.get("scenarioId"):
        errors.append("scenarioId is required for sandbox submissions.")
    if sandbox:
        sn = payload.get("scenarioId")
        if sn in RETAILER_ONLY:
            pass  # activity filter is applied in the UI / scenarios_for
    items = payload.get("items") or []
    if not items:
        errors.append("Invoice must have at least one item.")
    for i, item in enumerate(items, start=1):
        if not (item.get("hsCode") or "").strip():
            errors.append(f"0019: Please provide HSCode (item {i}).")
        if not (item.get("rate") or "").strip() and item.get("rate") != 0:
            errors.append(f"0020: Please provide Rate (item {i}).")
        if not (item.get("saleType") or "").strip():
            errors.append(f"0013: Provide valid Sale type (item {i}).")
        if not (item.get("uoM") or "").strip():
            errors.append(f"0099: Provide uom (item {i}).")
        if _is_third_schedule(item.get("saleType") or "") and _f(item.get("fixedNotifiedValueOrRetailPrice")) <= 0:
            errors.append(f"0090: Please provide Fixed / notified value or Retail Price (item {i}).")
    return errors


def parse_di_response(data: Any) -> dict:
    """Normalize post/validate JSON into {ok, invoice_number, status_code, error, item_errors}."""
    if not isinstance(data, dict):
        return {
            "ok": False,
            "invoice_number": "",
            "status_code": "",
            "error": "Unexpected response from FBR",
            "item_errors": [],
        }
    vr = data.get("validationResponse") or {}
    header_code = str(vr.get("statusCode") or "")
    header_status = str(vr.get("status") or "")
    item_errors: list[dict] = []
    item_invalid = False
    for row in vr.get("invoiceStatuses") or []:
        code = str(row.get("statusCode") or "")
        if code == "01" or str(row.get("status") or "").lower() == "invalid":
            item_invalid = True
            item_errors.append({
                "itemSNo": row.get("itemSNo"),
                "errorCode": row.get("errorCode") or "",
                "error": row.get("error") or "",
            })
    header_invalid = header_code == "01" or header_status.lower() == "invalid"
    ok = header_code == "00" and not header_invalid and not item_invalid
    error_parts = [p for p in (vr.get("errorCode"), vr.get("error")) if p]
    for ie in item_errors:
        bit = " ".join(x for x in (f"item {ie['itemSNo']}", ie.get("errorCode"), ie.get("error")) if x)
        if bit:
            error_parts.append(bit)
    return {
        "ok": ok,
        "invoice_number": data.get("invoiceNumber") or "",
        "status_code": header_code,
        "error": " | ".join(str(p) for p in error_parts if p),
        "item_errors": item_errors,
        "dated": data.get("dated") or "",
    }


def _headers(token: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def _post_json(url: str, payload: dict, token: str, timeout: float = 20.0) -> tuple[int, Any, str]:
    resp = httpx.post(url, json=payload, headers=_headers(token), timeout=timeout)
    text = resp.text
    try:
        data = resp.json()
    except Exception:
        data = None
    return resp.status_code, data, text


def submit_to_pra(session: Session, invoice_id: int) -> bool:
    """Validate then post an invoice to FBR DI. Updates invoice.pra_status in-place."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        return False

    config = get_pra_config(session, invoice.tenant_id)
    if not config:
        return False

    lines = session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)).all()
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

    payload = build_di_payload(invoice, lines, customer, products_by_id, tax_codes_by_id, config)
    payload_json = json.dumps(payload)

    log = PRASubmissionLog(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice_id,
        endpoint=config["validate_url"],
        request_json=payload_json,
    )

    local_errs = local_validate_payload(payload, sandbox=bool(config["sandbox"]))
    if local_errs:
        log.success = False
        log.error_message = "; ".join(local_errs)[:500]
        invoice.pra_status = "failed"
        invoice.pra_response_raw = log.error_message[:2000]
        session.add(invoice)
        session.add(log)
        session.commit()
        return False

    if not config.get("token"):
        log.success = False
        log.error_message = "FBR DI API token is missing in Settings."
        invoice.pra_status = "failed"
        invoice.pra_response_raw = log.error_message
        session.add(invoice)
        session.add(log)
        session.commit()
        return False

    try:
        v_status, v_data, v_text = _post_json(config["validate_url"], payload, config["token"])
        log.http_status = v_status
        log.response_json = (v_text or "")[:4000]
        if v_status == 401:
            parsed = {"ok": False, "status_code": "0401", "error": "Unauthorized (0401/401)", "invoice_number": ""}
        elif v_status >= 500:
            parsed = {"ok": False, "status_code": str(v_status), "error": "FBR server error (500)", "invoice_number": ""}
        else:
            parsed = parse_di_response(v_data)
        log.response_code = parsed.get("status_code") or str(v_status)
        if not parsed["ok"]:
            log.success = False
            log.error_message = (parsed.get("error") or f"Validate failed HTTP {v_status}")[:500]
            invoice.pra_status = "failed"
            invoice.pra_response_raw = (v_text or log.error_message)[:2000]
            session.add(invoice)
            session.add(log)
            session.commit()
            return False

        p_status, p_data, p_text = _post_json(config["post_url"], payload, config["token"])
        log.endpoint = config["post_url"]
        log.http_status = p_status
        log.response_json = (p_text or "")[:4000]
        if p_status == 401:
            parsed = {"ok": False, "status_code": "0401", "error": "Unauthorized (0401/401)", "invoice_number": ""}
        elif p_status >= 500:
            parsed = {"ok": False, "status_code": str(p_status), "error": "FBR server error (500)", "invoice_number": ""}
        else:
            parsed = parse_di_response(p_data)
        log.response_code = parsed.get("status_code") or str(p_status)
        if parsed["ok"]:
            log.success = True
            invoice.pra_status = "submitted"
            invoice.pra_fiscal_number = parsed.get("invoice_number") or invoice.pra_fiscal_number
            invoice.pra_submitted_at = datetime.utcnow()
            invoice.pra_response_raw = (p_text or "")[:2000]
            invoice.pra_usin = invoice.number
        else:
            log.success = False
            log.error_message = (parsed.get("error") or f"Post failed HTTP {p_status}")[:500]
            invoice.pra_status = "failed"
            invoice.pra_response_raw = (p_text or log.error_message)[:2000]
        session.add(invoice)
    except Exception as exc:
        log.success = False
        log.error_message = str(exc)[:500]
        invoice.pra_status = "failed"
        session.add(invoice)

    session.add(log)
    session.commit()
    return bool(log.success)


def _cache_get(key: str):
    hit = _REF_CACHE.get(key)
    if not hit:
        return None
    ts, val = hit
    if time.time() - ts > _REF_TTL:
        _REF_CACHE.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: Any) -> Any:
    _REF_CACHE[key] = (time.time(), val)
    return val


def fetch_reference(kind: str, token: str, params: Optional[dict] = None) -> Any:
    """Bearer-forward to FBR PDI/DIST reference APIs. Falls back to static lists."""
    params = params or {}
    cache_key = f"{kind}:{json.dumps(params, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    routes = {
        "provinces": f"{REF_BASE}/v1/provinces",
        "doctypes": f"{REF_BASE}/v1/doctypecode",
        "hs": f"{REF_BASE}/v1/itemdesccode",
        "uom": f"{REF_BASE}/v1/uom",
        "transtype": f"{REF_BASE}/v1/transtypecode",
        "sroitemcode": f"{REF_BASE}/v1/sroitemcode",
        "sroschedule": f"{REF_BASE}/v1/SroSchedule",
        "rates": f"{REF_BASE}/v2/SaleTypeToRate",
        "hsuom": f"{REF_BASE}/v2/HS_UOM",
        "sroitem": f"{REF_BASE}/v2/SROItem",
        "statl": f"{DIST_BASE}/statl",
        "regtype": f"{DIST_BASE}/Get_Reg_Type",
    }
    url = routes.get(kind)
    if not url:
        raise ValueError(f"Unknown reference kind: {kind}")

    fallback: Any
    if kind == "provinces":
        fallback = [{"stateProvinceCode": i + 1, "stateProvinceDesc": name} for i, name in enumerate(PROVINCES_FALLBACK)]
    elif kind == "uom":
        fallback = [{"uoM_ID": i + 1, "description": name} for i, name in enumerate(UOM_FALLBACK)]
    elif kind == "doctypes":
        fallback = [
            {"docTypeId": 4, "docDescription": INVOICE_TYPE_SALE},
            {"docTypeId": 9, "docDescription": INVOICE_TYPE_DEBIT},
        ]
    else:
        fallback = []

    if not token:
        return _cache_set(cache_key, fallback)

    try:
        if kind in ("statl", "regtype"):
            resp = httpx.get(url, headers=_headers(token), json=params or None, timeout=15.0)
            if resp.status_code >= 400:
                resp = httpx.post(url, headers=_headers(token), json=params, timeout=15.0)
        else:
            resp = httpx.get(url, headers=_headers(token), params=params or None, timeout=15.0)
        if resp.status_code == 200:
            data = resp.json()
            return _cache_set(cache_key, data)
    except Exception:
        pass
    return _cache_set(cache_key, fallback)


def lookup_reg_type(token: str, registration_no: str) -> dict:
    data = fetch_reference("regtype", token, {"Registration_No": _digits(registration_no)})
    if isinstance(data, dict):
        return data
    return {"statuscode": "", "REGISTRATION_TYPE": ""}
