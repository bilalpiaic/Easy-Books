"""India GST country pack (#265).

Reuses TaxCode + tax_engine (#263) for CGST/SGST/IGST. Place-of-supply
compares seller (tenant) vs buyer (customer) 2-digit state codes:

- Same state → CGST 9% + SGST 9% (intrastate)
- Different state → IGST 18% (interstate)

Invoice lines hold a single tax_code_id; intrastate auto-apply stores the
CGST primary code and mirrors an equal SGST leg into GL + GSTR aggregates.
"""
from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session, select

from models import (
    Account,
    Customer,
    Invoice,
    InvoiceLine,
    Product,
    Settings,
    TaxCode,
    Tenant,
)
from services.money import ZERO, money
from services.tax_engine import DocumentTaxAggregate, LineTaxResult, ensure_initial_rate_history


D = Decimal

CGST_RATE = D("9")
SGST_RATE = D("9")
IGST_RATE = D("18")

OUTPUT_CODES = (
    ("CGST_9", "CGST 9% (Output)", CGST_RATE, "2211", "CGST Payable", "Liability", "21"),
    ("SGST_9", "SGST 9% (Output)", SGST_RATE, "2212", "SGST Payable", "Liability", "21"),
    ("IGST_18", "IGST 18% (Output)", IGST_RATE, "2213", "IGST Payable", "Liability", "21"),
)
INPUT_CODES = (
    ("CGST_9_IN", "CGST 9% (Input)", CGST_RATE, "1261", "CGST Receivable", "Asset", "11"),
    ("SGST_9_IN", "SGST 9% (Input)", SGST_RATE, "1262", "SGST Receivable", "Asset", "11"),
    ("IGST_18_IN", "IGST 18% (Input)", IGST_RATE, "1263", "IGST Receivable", "Asset", "11"),
)


def _get_setting(session: Session, tenant_id: int, key: str, default: str = "") -> str:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return (row.value if row else default) or default


def _set_setting(session: Session, tenant_id: int, key: str, value: str) -> None:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    if row:
        row.value = value
        session.add(row)
    else:
        session.add(Settings(key=key, value=value, tenant_id=tenant_id))


def module_installed(session: Session, tenant_id: int) -> bool:
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return False
    try:
        enabled = json.loads(tenant.enabled_modules or "[]")
    except (TypeError, json.JSONDecodeError):
        return False
    return "in_gst" in enabled


def is_india_gst_enabled(session: Session, tenant_id: int) -> bool:
    if not module_installed(session, tenant_id):
        return False
    return _get_setting(session, tenant_id, "in_gst_enabled", "true") != "false"


def place_of_supply_interstate(
    seller_state: Optional[str], buyer_state: Optional[str]
) -> bool:
    """True when place of supply is interstate (IGST); False for intrastate (CGST+SGST)."""
    s = (seller_state or "").strip()
    b = (buyer_state or "").strip()
    if not s or not b:
        return False
    return s != b


def _get_or_create_account(
    session: Session,
    tenant_id: int,
    code: str,
    name: str,
    atype: str,
    parent_code: str,
) -> Account:
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
    return acc


def ensure_india_gst_tax_and_coa(session: Session, tenant_id: int) -> dict:
    """Idempotent: CGST/SGST/IGST TaxCodes + payable/receivable CoA leaves."""
    created_accounts: list[str] = []
    created_taxes: list[str] = []

    for code, name, rate, acct_code, acct_name, atype, parent in (*OUTPUT_CODES, *INPUT_CODES):
        existing_acc = session.exec(
            select(Account).where(Account.tenant_id == tenant_id, Account.code == acct_code)
        ).first()
        gl = _get_or_create_account(session, tenant_id, acct_code, acct_name, atype, parent)
        if existing_acc is None:
            created_accounts.append(acct_code)

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
                rate=money(rate),
                type="input" if code.endswith("_IN") else "output",
                gl_account_id=gl.id,
            )
        )
        created_taxes.append(code)

    session.flush()
    for tc in session.exec(select(TaxCode).where(TaxCode.tenant_id == tenant_id)).all():
        ensure_initial_rate_history(session, tc)
    return {"accounts": sorted(set(created_accounts)), "tax_codes": created_taxes}


def _tax_code_map(session: Session, tenant_id: int) -> dict[str, TaxCode]:
    ensure_india_gst_tax_and_coa(session, tenant_id)
    rows = session.exec(select(TaxCode).where(TaxCode.tenant_id == tenant_id)).all()
    return {tc.code: tc for tc in rows}


def suggest_tax_split(
    session: Session,
    tenant_id: int,
    seller_state: Optional[str],
    buyer_state: Optional[str],
    taxable: Decimal | float | str,
) -> list[dict[str, Any]]:
    """Return CGST+SGST or IGST legs for a taxable base amount."""
    base = money(D(taxable))
    codes = _tax_code_map(session, tenant_id)
    interstate = place_of_supply_interstate(seller_state, buyer_state)
    if interstate:
        tc = codes["IGST_18"]
        amt = money(base * IGST_RATE / D("100"))
        return [
            {
                "code": tc.code,
                "rate": float(IGST_RATE),
                "amount": float(amt),
                "tax_code_id": tc.id,
            }
        ]
    cgst = codes["CGST_9"]
    sgst = codes["SGST_9"]
    half = money(base * CGST_RATE / D("100"))
    return [
        {
            "code": cgst.code,
            "rate": float(CGST_RATE),
            "amount": float(half),
            "tax_code_id": cgst.id,
        },
        {
            "code": sgst.code,
            "rate": float(SGST_RATE),
            "amount": float(half),
            "tax_code_id": sgst.id,
        },
    ]


def resolve_seller_buyer_states(
    session: Session,
    tenant_id: int,
    customer_id: Optional[int],
) -> tuple[str, str]:
    seller = _get_setting(session, tenant_id, "in_state_code", "").strip()
    buyer = ""
    if customer_id:
        cust = session.exec(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        ).first()
        if cust and cust.state_code:
            buyer = cust.state_code.strip()
    return seller, buyer


def maybe_auto_apply_india_gst(
    session: Session,
    tenant_id: int,
    customer_id: Optional[int],
    lines: list[Any],
) -> dict[str, Any]:
    """If module on and no line has a tax_code_id, assign CGST or IGST primary."""
    empty: dict[str, Any] = {"applied": False, "interstate": False}
    if not is_india_gst_enabled(session, tenant_id):
        return empty
    if not lines:
        return empty
    if any(getattr(ln, "tax_code_id", None) for ln in lines):
        return empty

    seller, buyer = resolve_seller_buyer_states(session, tenant_id, customer_id)
    interstate = place_of_supply_interstate(seller, buyer)
    codes = _tax_code_map(session, tenant_id)
    primary = codes["IGST_18"] if interstate else codes["CGST_9"]
    for ln in lines:
        ln.tax_code_id = primary.id
    return {
        "applied": True,
        "interstate": interstate,
        "seller_state": seller,
        "buyer_state": buyer,
        "primary_code": primary.code,
    }


def finalize_india_gst_sgst_mirror(
    session: Session,
    tenant_id: int,
    meta: dict[str, Any],
    tax_results: list[Optional[LineTaxResult]],
    tax_agg: DocumentTaxAggregate,
    use_per_line_tax: bool,
) -> tuple[list[Optional[LineTaxResult]], DocumentTaxAggregate, bool, dict[int, Decimal]]:
    """After prepare_line_taxes: mirror CGST → SGST GL + header tax for intrastate."""
    per_gl: dict[int, Decimal] = dict(tax_agg.per_gl_tax) if use_per_line_tax else {}
    if not (meta.get("applied") and not meta.get("interstate") and use_per_line_tax):
        return tax_results, tax_agg, use_per_line_tax, per_gl

    codes = _tax_code_map(session, tenant_id)
    sgst = codes.get("SGST_9")
    if not sgst or not sgst.gl_account_id:
        return tax_results, tax_agg, use_per_line_tax, per_gl

    extra = ZERO
    for tr in tax_results:
        if tr is None or tr.tax <= 0:
            continue
        per_gl[sgst.gl_account_id] = money(per_gl.get(sgst.gl_account_id, ZERO) + tr.tax)
        extra = money(extra + tr.tax)

    new_agg = DocumentTaxAggregate(
        per_gl_tax=per_gl,
        total_tax_in_total=money(tax_agg.total_tax_in_total + extra),
        total_tax_rc_only=tax_agg.total_tax_rc_only,
        taxable_base=tax_agg.taxable_base,
    )
    return tax_results, new_agg, use_per_line_tax, per_gl


def _classify_tax_amount(code: Optional[str], tax_amount: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    z = ZERO
    if not code or tax_amount <= 0:
        return z, z, z
    c = code.upper()
    if c.startswith("IGST"):
        return z, z, money(tax_amount)
    if c.startswith("CGST"):
        return money(tax_amount), z, z
    if c.startswith("SGST"):
        return z, money(tax_amount), z
    return z, z, z


def build_gstr1_summary(
    session: Session,
    tenant_id: int,
    start: str,
    end: str,
) -> dict[str, Any]:
    """B2B invoice rows with GSTIN + taxable + CGST/SGST/IGST for a period."""
    invoices = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.issue_date >= start,
            Invoice.issue_date <= end,
            Invoice.status != "cancelled",  # type: ignore[comparison-overlap]
        )
    ).all()

    tax_codes = {
        tc.id: tc
        for tc in session.exec(select(TaxCode).where(TaxCode.tenant_id == tenant_id)).all()
    }
    customers = {
        c.id: c
        for c in session.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all()
    }
    products = {
        p.id: p
        for p in session.exec(select(Product).where(Product.tenant_id == tenant_id)).all()
    }

    b2b: list[dict[str, Any]] = []
    tot_taxable = ZERO
    tot_cgst = ZERO
    tot_sgst = ZERO
    tot_igst = ZERO

    for inv in invoices:
        lines = list(
            session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)).all()
        )
        if not lines:
            continue
        taxable = money(sum((D(ln.amount) for ln in lines), ZERO))
        cgst = ZERO
        sgst = ZERO
        igst = ZERO
        for ln in lines:
            tc = tax_codes.get(ln.tax_code_id) if ln.tax_code_id else None
            code = tc.code if tc else None
            ta = D(ln.tax_amount or 0)
            c, s, i = _classify_tax_amount(code, ta)
            cgst = money(cgst + c)
            sgst = money(sgst + s)
            igst = money(igst + i)
        if cgst > 0 and sgst == 0 and igst == 0:
            sgst = cgst
        if cgst == 0 and sgst == 0 and igst == 0 and D(inv.gst_amount or 0) > 0:
            seller, buyer = resolve_seller_buyer_states(session, tenant_id, inv.customer_id)
            if place_of_supply_interstate(seller, buyer):
                igst = money(inv.gst_amount)
            else:
                half = money(D(inv.gst_amount) / D("2"))
                cgst = half
                sgst = money(D(inv.gst_amount) - half)

        cust = customers.get(inv.customer_id) if inv.customer_id else None
        hsn_codes = sorted({
            (products[ln.product_id].hsn_sac or "")
            for ln in lines
            if ln.product_id and ln.product_id in products and products[ln.product_id].hsn_sac
        })
        row = {
            "invoice_id": inv.id,
            "invoice_number": inv.number,
            "issue_date": inv.issue_date,
            "customer_name": inv.customer_name or (cust.name if cust else ""),
            "gstin": (cust.gstin if cust else None) or "",
            "state_code": (cust.state_code if cust else None) or "",
            "taxable": float(taxable),
            "cgst": float(cgst),
            "sgst": float(sgst),
            "igst": float(igst),
            "total_tax": float(money(cgst + sgst + igst)),
            "invoice_total": float(inv.total or 0),
            "hsn_sac": ",".join(hsn_codes),
        }
        b2b.append(row)
        tot_taxable = money(tot_taxable + taxable)
        tot_cgst = money(tot_cgst + cgst)
        tot_sgst = money(tot_sgst + sgst)
        tot_igst = money(tot_igst + igst)

    b2b.sort(key=lambda r: (r["issue_date"], r["invoice_number"]))
    return {
        "period": {"start": start, "end": end},
        "gstin": _get_setting(session, tenant_id, "in_gstin"),
        "state_code": _get_setting(session, tenant_id, "in_state_code"),
        "b2b": b2b,
        "totals": {
            "invoice_count": len(b2b),
            "taxable": float(tot_taxable),
            "cgst": float(tot_cgst),
            "sgst": float(tot_sgst),
            "igst": float(tot_igst),
            "total_tax": float(money(tot_cgst + tot_sgst + tot_igst)),
        },
    }


def build_gstr3b_summary(
    session: Session,
    tenant_id: int,
    start: str,
    end: str,
) -> dict[str, Any]:
    gstr1 = build_gstr1_summary(session, tenant_id, start, end)
    t = gstr1["totals"]
    return {
        "period": gstr1["period"],
        "gstin": gstr1["gstin"],
        "state_code": gstr1["state_code"],
        "outward_supplies": {
            "taxable": t["taxable"],
            "cgst": t["cgst"],
            "sgst": t["sgst"],
            "igst": t["igst"],
            "total_tax": t["total_tax"],
        },
        "invoice_count": t["invoice_count"],
        "itc_available": {"cgst": 0.0, "sgst": 0.0, "igst": 0.0},
    }


def gstr1_to_csv(summary: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "invoice_number", "issue_date", "customer_name", "gstin", "state_code",
            "hsn_sac", "taxable", "cgst", "sgst", "igst", "total_tax", "invoice_total",
        ],
    )
    writer.writeheader()
    for row in summary.get("b2b", []):
        writer.writerow({k: row.get(k, "") for k in writer.fieldnames})
    return buf.getvalue()


def enable_india_gst_settings(session: Session, tenant_id: int) -> None:
    ensure_india_gst_tax_and_coa(session, tenant_id)
    _set_setting(session, tenant_id, "in_gst_enabled", "true")
    if not _get_setting(session, tenant_id, "in_state_code"):
        _set_setting(session, tenant_id, "in_state_code", "27")
    session.commit()
