"""Seed the seven demo tenants (one per business model) with rich mock data
spanning at least the last two calendar years from the seed trigger date.

Idempotent — if a demo tenant already exists, the script reuses it and
skips entities that are already present. Safe to re-run.

Date window (computed at trigger time via date.today()):
  • Inclusive range [today − 2 years, today]
    e.g. triggered 2026-07-21 → 2024-07-21 … 2026-07-21
         triggered 2026-01-01 → 2024-01-01 … 2026-01-01
  • Transactional / ops dates stay inside that window (never future-dated
    except still-active contract/promo end dates)

Data coverage (v4 — Sprint 7–12 improvement roadmap):
  • 100 invoices + 100 bills per tenant, evenly spread across the 2-year window
  • Every model-specific COA account exercised (4010/4020/5100/5200/5030 etc.)
  • 2–3 bank accounts seeded per tenant, each on its own CoA leaf
    (1011 HBL, 1012 SCB, 1000 petty cash) so Bank Book / TB balances match
  • Payment terms randomly assigned to customers, vendors, invoices, bills
  • notes / internal_memo fields populated with realistic text
  • 60+ manual JVs covering all expense / revenue / balance-sheet accounts
  • Credit notes (G-02), fixed assets + depreciation (G-05), monthly budgets
    (G-10), purchase orders incl. convert-to-bill (G-06), analytic accounts
    (G-07), and deferred-revenue schedules for services tenants (G-08)
  (G-07) Analytic Accounts: 7 dimensions per tenant, ~30 % of invoices/bills/payments/JVs tagged
  • PRA e-Invoice demo tenant (demo.pra@easy-books.app) — Pakistani retail trader
    with PRA sandbox enabled, PKR currency, NTN/CNIC on customers, PCT codes on
    products, payment_mode set on invoices, realistic FINs stamped, and a
    PRASubmissionLog audit trail (successes + a failed-then-retried pair)
  • Promo rules (bulk %, giveaway, category-scoped, invoice-value threshold)
  • Commission plans + 3-month ledger (draft → approved → posted w/ GL entry);
    ~half of posted invoices get assigned_to_id so compute maths is real
  • Accounting periods (locked FY predating the data window + open FYs/quarters)
  • Bank reconciliations (one closed, one open ~70% matched) and an imported
    bank statement (~60% auto-matched) on the main bank account

Usage:
    PYTHONPATH=. uv run python -m scripts.seed_demo

Credentials:
    demo.simple@easy-books.app         / demo1234
    demo.services@easy-books.app       / demo1234
    demo.trader@easy-books.app         / demo1234
    demo.manufacturing@easy-books.app  / demo1234
    demo.telecom@easy-books.app        / demo1234
    demo.pra@easy-books.app            / demo1234  (PRA e-Invoice / Pakistan)
    demo.hospital@easy-books.app       / demo1234  (Healthcare / Hospital)
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from auth import get_password_hash
from db import MODULE_REGISTRY, MODULES_BY_MODEL, _coa_for, engine, seed_data
import json as _json

from models import (
    Account, AccountingPeriod, AnalyticAccount, AttendanceRecord, AuditLog, BankAccount,
    BankStatementImport, BomHeader,
    BomLine, Bill, BillLine, BillPayment, Budget, CommissionLedger, CommissionPlan,
    ComparativeStatement, CreditNote,
    CreditNoteLine, Customer, CustomerAdvance, CustomerRatePlan, DebitNote, DebitNoteLine,
    DeferredRevenueSchedule, DepreciationEntry, Employee, EmployeeSalaryStructure,
    ExchangeRate, FixedAsset, GateInward, GateInwardLine, GateOutward, GateOutwardLine,
    GRNLine, GoodsReceiptNote, InventoryLayer, Invoice,
    InvoiceLine, JournalEntry, PaymentAllocation, PaymentReceived, PaymentTerm, PayrollLine,
    PayrollLineDetail, PayrollRun, PRASubmissionLog, Product, ProductCategory, ProductionOrder,
    PromoRule, PurchaseDemand, PurchaseDemandLine, PurchaseOrder, PurchaseOrderLine,
    RatePlan, Reconciliation, ReconciliationLine, RecurringTemplate, ReportDefinition,
    SalaryComponent, SequenceCounter, Settings, StatementLine, StockLocation, StoreIssue,
    StoreIssueLine, TaxCode, Tenant, Transaction, User, Vendor,
    VendorAdvance, VendorQuotation, VendorQuotationLine,
)
from models_telecom import (
    AirtimeSale, AirtimeStock, CommissionLine, CommissionStatement,
    DeviceImei, FcaEvent, FranchiseAgreement, KpiTarget,
    MobileMoneyAccount, Operator, PostpaidBillCycle, PostpaidConnection,
    RetailOutlet, RsoAgent, RsoTarget, SimActivation, TrackerAccount,
)
from models_healthcare import (
    HcPatient, HcDoctor, HcWard, HcBed, HcProcedureCatalog,
    HcOpdToken, HcOpdVisit, HcPrescription, HcPrescriptionItem,
    HcAdmission, HcAdmissionCharge, HcLabTest, HcLabOrder, HcLabOrderItem,
    HcSampleCollection, HcProcedureOrder, HcStoreIssue, HcStoreIssueItem,
    HcDialysisUnit, HcDialysisMachine, HcDialysisShift, HcDialysisSession,
)
from models_weaving import (
    WvFabricQuality, WvLoom, WvYarnType, WvShift, WvOperator,
    WvContract, WvYarnInward, WvSizing, WvProduction, WvDispatch,
)
from routers.common import get_or_create_account, next_number
from services.franchise_posting import (
    post_commission_accrual, post_franchise_fee_amortisation,
    post_franchise_fee_capitalisation, post_mm_commission_credit,
    post_mm_customer_deposit, post_mm_float_top_up,
)
from services.healthcare_posting import (
    post_opd_consultation, post_ipd_deposit, post_lab_order,
    post_discharge_bill, post_store_issue, post_procedure,
)
from services.inventory import (
    InventoryError, consume_stock, record_movement, record_purchase,
    return_to_vendor, reverse_consumption,
)
from services.deferred import (
    DeferralPlan, LineDeferral,
    create_schedules, resolve_deferred_account,
    _add_months,
)
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction
from services.tracker_posting import (
    post_fca_target_commission, post_load_order, post_msr_to_rso_transfer,
    post_rso_daily_collection, post_rso_sim_issue, post_rso_to_retail_transfer,
    post_stock_debit, post_tracker_deposit,
)


# ── Configuration ─────────────────────────────────────────────────────────────

DEMO_PASSWORD = "demo1234"
DEMO_TENANTS = [
    ("demo.simple@easy-books.app",        "Demo Simple Co.",                   "simple"),
    ("demo.services@easy-books.app",      "Demo Services Ltd.",                "services"),
    ("demo.trader@easy-books.app",        "Demo Trading Co.",                  "trader"),
    ("demo.manufacturing@easy-books.app", "Demo Manufacturing Co.",            "manufacturing"),
    ("demo.telecom@easy-books.app",       "Demo Telecom Franchise",            "telecom_franchise"),
    ("demo.pra@easy-books.app",           "Lahore Retail Traders (PRA Demo)", "trader"),
    ("demo.hospital@easy-books.app",      "City General Hospital (Demo)",      "hospital"),
]

# PRA demo tenant — Pakistani customers with NTN/CNIC
PRA_CUSTOMER_NAMES = [
    "Al-Noor Traders", "Bismillah General Store", "Crescent Distributors",
    "Dawn Wholesale", "Excellence Retail", "Faisal Brothers",
    "Golden Bazaar", "Hamid & Sons", "Ibrahim Traders",
    "Johar Town Mart", "Khalid Enterprises", "Liberty Market Co.",
    "Moon Light Goods", "National Merchandise", "Orient Traders",
    "Punjab Distributors", "Quality Goods Pk", "Raja Brothers",
    "Sardar Traders", "Taj General Store", "United Traders Pak",
    "Vision Retail", "Western Goods", "Xpert Traders",
    "Zahid Enterprises",
]
# (NTN, CNIC) pairs — dummy but realistic-format
PRA_CUSTOMER_IDS = [
    ("1234567-8", "3520112345671"), ("2345678-9", "3520223456782"),
    ("3456789-0", "3510334567893"), ("4567890-1", "3520445678904"),
    ("5678901-2", "3510556789015"), ("6789012-3", "3520667890126"),
    ("7890123-4", "3510778901237"), ("8901234-5", "3520889012348"),
    ("9012345-6", "3510990123459"), ("0123456-7", "3520001234560"),
    ("1234560-1", "3520112345601"), ("2345671-2", "3520223456712"),
    ("3456782-3", "3510334567823"), ("4567893-4", "3520445678934"),
    ("5678904-5", "3510556789045"), ("6789015-6", "3520667890156"),
    ("7890126-7", "3510778901267"), ("8901237-8", "3520889012378"),
    ("9012348-9", "3510990123489"), ("0123459-0", "3520001234590"),
    ("1234561-2", "3520112345612"), ("2345672-3", "3520223456723"),
    ("3456783-4", "3510334567834"), ("4567894-5", "3520445678945"),
    ("5678905-6", "3510556789056"),
]
# Pakistani retail products with PCT codes
PRA_PRODUCTS = [
    ("PKR-A1", "Basmati Rice (50kg)",    "bag",  8500, 3800, "10063000"),
    ("PKR-A2", "Sugar (50kg)",           "bag",  7200, 3200, "17011200"),
    ("PKR-A3", "Cooking Oil (15L)",      "tin",  5800, 2600, "15071000"),
    ("PKR-A4", "Wheat Flour (20kg)",     "bag",  2200,  900, "11010000"),
    ("PKR-A5", "Tea (200g)",             "pkt",   450,  180, "09021000"),
    ("PKR-A6", "Milk Powder (900g)",     "tin",  2800, 1200, "04021000"),
    ("PKR-A7", "Laundry Detergent (1kg)","ea",    380,  150, "34012000"),
    ("PKR-A8", "Soap Bars (6pk)",        "pk",    320,  120, "34011100"),
]

CUSTOMER_NAMES = [
    "Alpha Retail Group", "Beacon Boutiques", "Cascade Holdings",
    "Delta Wholesale Co.", "Evergreen Brands", "Falcon Outfitters",
    "Greenline Imports", "Horizon Retailers", "Iris Apparel",
    "Junction Trading", "Karma Lifestyles", "Lakeside Markets",
    "Meridian Goods", "Nova Fashion House", "Orbit Distributors",
    "Pinnacle Stores", "Quest Apparel", "Radiant Retailers",
    "Stellar Brands", "Titan Marketplaces", "Urban Bazaar",
    "Vantage Wholesale", "Westfield Traders", "Xcel Boutiques",
    "Zenith Commerce",
]
VENDOR_NAMES = [
    "Acme Supplies", "Beacon Hardware", "Crescent Logistics",
    "Dynamo Industrial", "Echo Materials", "Fortune Components",
    "Golden Threads", "Helix Yarn Mills", "Imperial Tooling",
    "Junction Distributors", "Keystone Chemicals", "Lustre Packaging",
    "Metro Raw Goods", "Nexus Fabrics", "Omega Procurement",
    "Pioneer Resources", "Quality Inputs Ltd.", "Reliable Parts Co.",
    "Summit Sourcing", "Trident Supplies", "United Raw Materials",
    "Vertex Components", "Wholesale Direct", "XL Industrial",
    "Zenith Vendors",
]
SERVICE_PRODUCTS = [
    ("CONSULT-HR", "HR Consulting (per hour)",       "hr",   150),
    ("CONSULT-IT", "IT Consulting (per hour)",       "hr",   175),
    ("AUDIT",      "Internal Audit Engagement",      "ea",  5000),
    ("TRAIN",      "Corporate Training Day",         "day", 2500),
    ("SUPPORT",    "Annual Support Contract",        "yr", 12000),
]
STOCK_PRODUCTS_TRADER = [
    ("SKU-A1", "Premium Cotton Shirt", "ea",  45,  18),
    ("SKU-A2", "Polo Shirt",           "ea",  35,  14),
    ("SKU-A3", "Denim Jeans",          "ea",  80,  32),
    ("SKU-A4", "Canvas Tote Bag",      "ea",  18,   6),
    ("SKU-A5", "Wool Scarf",           "ea",  28,  10),
    ("SKU-A6", "Leather Belt",         "ea",  40,  16),
    ("SKU-A7", "Knit Beanie",          "ea",  15,   5),
    ("SKU-A8", "Cotton Socks (3pk)",   "pk",  12,   4),
]
RAW_MATERIALS = [
    ("RM-COT",  "Cotton Yarn",         "kg",   8),
    ("RM-POL",  "Polyester Yarn",      "kg",   6),
    ("RM-DYE",  "Reactive Dye",        "kg",  15),
    ("RM-BTN",  "Plastic Buttons",     "ea", 0.05),
    ("RM-LBL",  "Woven Labels",        "ea", 0.10),
    ("RM-THR",  "Sewing Thread",       "m",  0.02),
    ("RM-INT",  "Interlining",         "m",   3),
    ("RM-ZIP",  "Brass Zipper",        "ea",   1.20),
]
CUSTOMER_MATERIALS = [
    ("CUST-FAB-A", "Customer Fabric A", "m"),
    ("CUST-FAB-B", "Customer Fabric B", "m"),
    ("CUST-TRIM",  "Customer Trim",     "ea"),
]
FINISHED_GOODS_MFG = [
    ("FG-SHIRT", "Finished Shirt", "ea"),
    ("FG-POLO",  "Finished Polo",  "ea"),
    ("FG-PANT",  "Finished Pants", "ea"),
]
TELECOM_STOCK = [
    ("SIM-PRE",    "Prepaid SIM Card",       "ea",  5,  1),
    ("SIM-POST",   "Postpaid SIM Card",      "ea",  8,  2),
    ("ROUTER-4G",  "4G LTE Router",          "ea", 75, 38),
    ("ROUTER-5G",  "5G CPE Router",          "ea", 220, 110),
    ("MIFI",       "MiFi Mobile Hotspot",    "ea", 120,  55),
    ("DONGLE-USB", "USB Data Dongle",        "ea",  45,  18),
]
TELECOM_SERVICES = [
    ("BUNDLE-VOICE",  "Airtime Bundle (min)",   "min",   0.05),
    ("BUNDLE-DATA",   "Data Bundle (GB)",       "gb",    2.50),
    ("BUNDLE-SMS",    "SMS Bundle (msg)",       "msg",   0.02),
    ("ROAM-DAY",      "Daily Roaming Pass",     "day",   8.00),
    ("VAS-CALLERID",  "Caller ID Subscription", "mo",    1.50),
    ("VAS-VOICEMAIL", "Voicemail Subscription", "mo",    2.00),
    ("PLAN-POST-BASIC","Postpaid Basic Plan",   "mo",   25.00),
    ("PLAN-POST-PRO", "Postpaid Pro Plan",      "mo",   55.00),
]
# Pharmacy / ward consumables for the hospital demo (HC Store + dispense queue).
HOSPITAL_STOCK = [
    ("MED-PARA",  "Paracetamol 500mg",     "box", 120, 45),
    ("MED-AMOX",  "Amoxicillin 250mg",     "box", 280, 95),
    ("MED-IBU",   "Ibuprofen 400mg",       "box", 150, 55),
    ("MED-ORS",   "ORS Sachets",           "box",  80, 25),
    ("MED-INJ",   "Normal Saline 500ml",   "bag",  90, 35),
    ("MED-SYR",   "Disposable Syringe 5ml","box",  60, 18),
    ("MED-GLU",   "Gloves (pair)",         "box", 200, 70),
    ("MED-BAND",  "Bandage Roll",          "ea",   40, 12),
    ("MED-IV",    "IV Cannula 20G",        "ea",   55, 18),
    ("MED-MASK",  "Surgical Mask",         "box", 100, 30),
]
TAX_CODES = [
    ("GST-OUT-17", "GST Output 17%", 17, "output", "2200"),
    ("GST-OUT-5",  "GST Output 5%",   5, "output", "2200"),
    ("GST-OUT-0",  "GST Output 0% (export)", 0, "output", "2200"),
    ("GST-IN-17",  "GST Input 17%",  17, "input",  "1250"),
    ("GST-IN-5",   "GST Input 5%",    5, "input",  "1250"),
    ("GST-IN-0",   "GST Input 0%",    0, "input",  "1250"),
]

INVOICE_NOTES_POOL = [
    "Payment due within terms. Thank you for your business.",
    "All prices exclusive of applicable taxes.",
    "Please reference invoice number on remittance.",
    "Goods remain property of seller until full payment received.",
    "Late payments subject to 1.5% per month finance charge.",
    "Bank details on file. Please confirm before transfer.",
    "This invoice supersedes any verbal quotation.",
    "Thank you for your continued partnership.",
    "Prices valid as quoted. Subject to change without notice.",
    "Discount of 2% available for payment within 10 days.",
]
INVOICE_MEMO_POOL = [
    "Customer requested split shipment — verify delivery address.",
    "High-value account — expedite if queries arise.",
    "Discount negotiated by sales team for Q3 target.",
    "Follow up if not paid by due date.",
    "Credit limit reviewed — approved for this order.",
    "VIP customer — handle with priority.",
    "Contract reference attached to file.",
    "Pending final sign-off from operations.",
    "Part of annual framework agreement.",
    "Cross-sell opportunity identified — flag to account manager.",
]
BILL_NOTES_POOL = [
    "Please confirm receipt and process within payment terms.",
    "Prices as per agreed rate card.",
    "Subject to inspection and acceptance of goods.",
    "Returns policy: 30 days from invoice date.",
    "All amounts in USD unless stated otherwise.",
    "Ensure PO number quoted on remittance.",
    "Vendor bank details on file.",
    "Payment terms as per master supply agreement.",
    "GST registration number verified.",
    "Goods dispatched under separate cover.",
]
BILL_MEMO_POOL = [
    "Match against PO before approving payment.",
    "Cheaper alternative sourced — review for next order.",
    "Vendor delivered late — deduct penalty per SLA.",
    "Quality check passed — goods released to inventory.",
    "Three-way match complete.",
    "Hold payment pending credit note for damaged goods.",
    "Recurring supplier — auto-approve if within budget.",
    "Budget line: opex/supplies — approved.",
    "Price variance from last order — query with vendor.",
    "Approved by finance director 2024.",
]

# ── Date helpers ──────────────────────────────────────────────────────────────

# Rolling demo window anchored to the seed trigger day (date.today()).
# Inclusive [today − 2 calendar years, today] — at least a 2-year span.
SEED_SPAN_YEARS = 2


def _seed_today() -> date:
    """Seed trigger day — always evaluated at call time so re-seeds slide forward."""
    return date.today()


def _seed_window_start(today: date | None = None) -> date:
    """Inclusive start of the demo data window (today minus 2 calendar years)."""
    end = today or _seed_today()
    try:
        return end.replace(year=end.year - SEED_SPAN_YEARS)
    except ValueError:
        # Feb 29 → Feb 28 two years earlier
        return end.replace(year=end.year - SEED_SPAN_YEARS, month=2, day=28)


def _seed_span_days(today: date | None = None) -> int:
    """Days from window start → today (730 or 731 depending on leap days)."""
    end = today or _seed_today()
    return (end - _seed_window_start(end)).days


def _past_days(days_back: int, *, today: date | None = None) -> str:
    """ISO date `days_back` before today, clamped into the 2-year seed window."""
    end = today or _seed_today()
    start = _seed_window_start(end)
    span = (end - start).days
    clamped = max(0, min(int(days_back), span))
    return (end - timedelta(days=clamped)).isoformat()


def _spread_dates(
    count: int,
    days_ago: int | None = None,
    min_days_ago: int = 3,
) -> list[str]:
    """Return `count` ascending ISO dates spread across the past `days_ago`
    days (default = full 2-year seed window) with ±3 day jitter.

    Always clamped to [today − span, today]; never emits future dates.
    """
    today = _seed_today()
    span = _seed_span_days(today)
    if days_ago is None:
        days_ago = span
    else:
        days_ago = max(min_days_ago, min(int(days_ago), span))
    min_days_ago = max(0, min(min_days_ago, days_ago))
    dates: list[str] = []
    for i in range(count):
        frac = i / max(count - 1, 1)
        base_days = int(days_ago - frac * (days_ago - min_days_ago))
        jitter = random.randint(-3, 3)
        days_back = max(min_days_ago, min(span, base_days + jitter))
        dates.append((today - timedelta(days=days_back)).isoformat())
    return sorted(dates)


def _due_date(issue: str, term_days: int) -> str:
    """Return due date string `term_days` after `issue`."""
    return (date.fromisoformat(issue) + timedelta(days=term_days)).isoformat()


def _clamp_to_today(iso: str, *, today: date | None = None) -> str:
    """Clamp an ISO date so seeded GL / ops never post in the future."""
    end = today or _seed_today()
    d = date.fromisoformat(iso[:10])
    return (d if d <= end else end).isoformat()


# ── COA routing helpers ───────────────────────────────────────────────────────


def _expense_pool(s: Session, tid: int, model: str) -> list[Account]:
    """Return non-empty list of expense accounts to distribute bills across."""
    code_groups: dict[str, list[str]] = {
        "simple":            ["5000", "5050", "5900"],
        "services":          ["5000", "5050", "5110", "5900"],
        "trader":            ["5000", "5010", "5020", "5030", "5040", "5050"],
        "manufacturing":     ["5000", "5010", "5050", "5100", "5110", "5200", "5210"],
        "telecom_franchise": ["5000", "5010", "5011", "5012", "5020", "5021",
                              "5030", "5040", "5060", "5050"],
    }
    pool = []
    for code in code_groups.get(model, ["5000"]):
        a = _account(s, tid, code)
        if a:
            pool.append(a)
    if not pool:
        fallback = _account(s, tid, "5000")
        if fallback:
            pool.append(fallback)
    return pool


def _revenue_pool(s: Session, tid: int, model: str) -> list[Account]:
    """Return non-empty list of revenue accounts for invoices."""
    code_groups: dict[str, list[str]] = {
        "simple":            ["4000", "4900"],
        "services":          ["4000", "4010", "4020", "4900"],
        "trader":            ["4000", "4900"],
        "manufacturing":     ["4000", "4010", "4900"],
        "telecom_franchise": ["4000", "4010", "4020", "4021", "4022",
                              "4023", "4030", "4031", "4040", "4050",
                              "4060", "4061"],
    }
    pool = []
    for code in code_groups.get(model, ["4000"]):
        a = _account(s, tid, code)
        if a:
            pool.append(a)
    if not pool:
        fallback = _account(s, tid, "4000")
        if fallback:
            pool.append(fallback)
    return pool


# ── Basic entity seeders ──────────────────────────────────────────────────────


def _get_or_make_user(s: Session, email: str, full_name: str, tenant_id: int, role: str = "owner") -> User:
    u = s.exec(select(User).where(User.email == email)).first()
    if u:
        # Convergent reseed: always restore the canonical demo credentials so a
        # drifted password / must_change flag never leaves a demo account locked
        # out. (Idempotency must guarantee correct STATE, not just existence.)
        u.hashed_password = get_password_hash(DEMO_PASSWORD)
        u.is_active = True
        u.role = role
        if hasattr(u, "must_change_password"):
            u.must_change_password = False
        s.add(u); s.flush()
        return u
    u = User(
        email=email,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        full_name=full_name,
        tenant_id=tenant_id,
        role=role,
    )
    s.add(u); s.flush()
    return u


def _account(s: Session, tenant_id: int, code: str) -> Optional[Account]:
    return s.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
    ).first()


def _ensure_categories(s: Session, tenant_id: int, model: str) -> None:
    """Convergent category top-up: seed starter ProductCategory rows for tenants
    that were created before the ProductCategory feature existed. Idempotent —
    skips entirely if any category already exists for this tenant."""
    if s.exec(
        select(ProductCategory).where(ProductCategory.tenant_id == tenant_id)
    ).first():
        return
    STARTER_CATEGORIES: dict[str, dict[str, list[str]]] = {
        "simple":            {"General": ["Products", "Services"]},
        "services":          {"Services": ["Consulting", "Recurring"]},
        "trader":            {"Goods": ["General", "Imported"]},
        "manufacturing":     {"Raw Materials": ["Metals", "Consumables"],
                              "Finished Goods": ["Standard"]},
        "telecom_franchise": {"SIM": ["Prepaid", "Postpaid"],
                              "Devices": ["Handsets", "Accessories"]},
        "hospital":          {"Pharmacy": ["Medicines", "Consumables"],
                              "Services": ["OPD", "Lab", "IPD"]},
    }
    for parent_name, subs in STARTER_CATEGORIES.get(model, {}).items():
        parent = ProductCategory(tenant_id=tenant_id, name=parent_name)
        s.add(parent); s.flush()
        for sub in subs:
            s.add(ProductCategory(tenant_id=tenant_id, name=sub, parent_id=parent.id))
    s.flush()


def _ensure_coa(s: Session, tenant_id: int, model: str) -> None:
    """Convergent CoA top-up: insert any accounts from the model's template that
    this tenant is missing. Existing demo tenants pre-date newer backbone
    accounts (1090/4901 from Sprint 7-12, 1260/2310 from Sprint 13), so without
    this the advance/asset/FX seeders silently skip. Idempotent (by code)."""
    existing = {a.code: a for a in s.exec(
        select(Account).where(Account.tenant_id == tenant_id)
    ).all()}
    template = _coa_for(model)
    for code, name, atype, is_memo, parent_code, is_group in template:
        if code not in existing:
            acc = Account(code=code, name=name, type=atype, is_memo=is_memo,
                          is_group=is_group, tenant_id=tenant_id)
            s.add(acc); existing[code] = acc
    s.flush()
    for code, name, atype, is_memo, parent_code, is_group in template:
        if parent_code and existing[code].parent_id is None:
            existing[code].parent_id = existing[parent_code].id
    s.flush()


def _set_party_types(s: Session, tenant_id: int) -> None:
    """Set party_type on the canonical AR (1100) and AP (2000) accounts."""
    changed = False
    for acc in s.exec(select(Account).where(Account.tenant_id == tenant_id)).all():
        if acc.code == "1100" and acc.type == "Asset" and acc.party_type != "customer":
            acc.party_type = "customer"
            s.add(acc)
            changed = True
        elif acc.code == "2000" and acc.type == "Liability" and acc.party_type != "vendor":
            acc.party_type = "vendor"
            s.add(acc)
            changed = True
    if changed:
        s.flush()


def _seed_customers(s: Session, tenant_id: int) -> list[Customer]:
    out: list[Customer] = []
    for name in CUSTOMER_NAMES:
        existing = s.exec(
            select(Customer).where(Customer.tenant_id == tenant_id, Customer.name == name)
        ).first()
        if existing:
            out.append(existing); continue
        c = Customer(
            tenant_id=tenant_id, name=name,
            email=name.lower().replace(" ", ".") + "@example.com",
            phone=f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
        )
        s.add(c); s.flush()
        out.append(c)
    return out


def _seed_vendors(s: Session, tenant_id: int) -> list[Vendor]:
    out: list[Vendor] = []
    for name in VENDOR_NAMES:
        existing = s.exec(
            select(Vendor).where(Vendor.tenant_id == tenant_id, Vendor.name == name)
        ).first()
        if existing:
            out.append(existing); continue
        v = Vendor(
            tenant_id=tenant_id, name=name,
            email=name.lower().replace(" ", ".") + "@example.com",
            phone=f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
        )
        s.add(v); s.flush()
        out.append(v)
    return out


def _assign_payment_terms(s: Session, tenant_id: int,
                           customers: list[Customer],
                           vendors: list[Vendor]) -> list[PaymentTerm]:
    """Assign random payment terms to customers and vendors."""
    terms = s.exec(
        select(PaymentTerm).where(PaymentTerm.tenant_id == tenant_id)
    ).all()
    if not terms:
        return []
    for c in customers:
        if c.payment_term_id is None:
            c.payment_term_id = random.choice(terms).id
            s.add(c)
    for v in vendors:
        if v.payment_term_id is None:
            v.payment_term_id = random.choice(terms).id
            s.add(v)
    return terms


def _seed_products(
    s: Session, tenant_id: int, business_model: str
) -> tuple[list[Product], list[Product], list[Product]]:
    """Returns (service_products, stock_products, customer_supplied_products)."""
    services: list[Product] = []
    stock: list[Product] = []
    customer_supplied: list[Product] = []

    def upsert(code: str, name: str, unit: str, default_rate: Decimal,
               product_type: str) -> Product:
        existing = s.exec(
            select(Product).where(Product.tenant_id == tenant_id, Product.code == code)
        ).first()
        if existing:
            return existing
        p = Product(
            tenant_id=tenant_id, code=code, name=name, unit=unit,
            product_type=product_type, default_rate=money(D(default_rate)),
        )
        s.add(p); s.flush()
        return p

    if business_model == "telecom_franchise":
        for code, name, unit, rate in TELECOM_SERVICES:
            services.append(upsert(code, name, unit, D(rate), "service"))
        for code, name, unit, sale, cost in TELECOM_STOCK:
            stock.append(upsert(code, name, unit, D(sale), "stock"))
    else:
        for code, name, unit, rate in SERVICE_PRODUCTS:
            services.append(upsert(code, name, unit, D(rate), "service"))
        # Mark the "Annual Support Contract" as a deferred-revenue product so
        # _seed_invoices can originate real DeferredRevenueSchedule rows via
        # the same #47 production path (Dr AR / Cr Revenue + Cr 2300).
        if business_model == "services":
            support = s.exec(
                select(Product).where(
                    Product.tenant_id == tenant_id, Product.code == "SUPPORT"
                )
            ).first()
            if support and not support.is_deferred:
                support.is_deferred = True
                support.recognition_months = 12
                s.add(support)

    if business_model in ("trader", "manufacturing"):
        for code, name, unit, sale, cost in STOCK_PRODUCTS_TRADER:
            stock.append(upsert(code, name, unit, D(sale), "stock"))

    if business_model == "manufacturing":
        for code, name, unit, cost in RAW_MATERIALS:
            stock.append(upsert(code, name, unit, D(cost), "stock"))
        for code, name, unit in CUSTOMER_MATERIALS:
            customer_supplied.append(upsert(code, name, unit, ZERO, "stock"))
        for code, name, unit in FINISHED_GOODS_MFG:
            stock.append(upsert(code, name, unit, D(0), "stock"))

    if business_model == "hospital":
        for code, name, unit, sale, cost in HOSPITAL_STOCK:
            stock.append(upsert(code, name, unit, D(sale), "stock"))

    # Assign categories (idempotent — only sets category_id when currently None)
    cats = s.exec(
        select(ProductCategory).where(
            ProductCategory.tenant_id == tenant_id,
            ProductCategory.parent_id.is_not(None),
        ).order_by(ProductCategory.id)
    ).all()
    if not cats:
        cats = s.exec(
            select(ProductCategory).where(
                ProductCategory.tenant_id == tenant_id
            ).order_by(ProductCategory.id)
        ).all()
    if cats:
        prods = s.exec(select(Product).where(Product.tenant_id == tenant_id)).all()
        for i, prod in enumerate(prods):
            if prod.category_id is None:
                prod.category_id = cats[i % len(cats)].id
                s.add(prod)
        s.commit()

    return services, stock, customer_supplied


def _seed_tax_codes(s: Session, tenant_id: int) -> None:
    for code, name, rate, ttype, gl_code in TAX_CODES:
        existing = s.exec(
            select(TaxCode).where(TaxCode.tenant_id == tenant_id, TaxCode.code == code)
        ).first()
        if existing:
            continue
        acc = _account(s, tenant_id, gl_code)
        if acc is None:
            continue
        s.add(TaxCode(
            tenant_id=tenant_id, code=code, name=name,
            rate=D(rate), type=ttype, gl_account_id=acc.id,
        ))


def _seed_exchange_rates(s: Session, tenant_id: int) -> None:
    pairs = [
        ("USD", "EUR", D("0.92")), ("USD", "GBP", D("0.79")),
        ("USD", "PKR", D("280")),  ("USD", "INR", D("83")),
        ("USD", "AED", D("3.67")), ("USD", "SAR", D("3.75")),
        ("EUR", "USD", D("1.09")), ("GBP", "USD", D("1.27")),
        ("PKR", "USD", D("0.0036")), ("INR", "USD", D("0.012")),
        ("AED", "USD", D("0.272")), ("SAR", "USD", D("0.267")),
    ]
    today = date.today().isoformat()
    for f, t, r in pairs:
        existing = s.exec(
            select(ExchangeRate).where(
                ExchangeRate.tenant_id == tenant_id,
                ExchangeRate.from_currency == f,
                ExchangeRate.to_currency == t,
                ExchangeRate.date == today,
            )
        ).first()
        if existing:
            continue
        s.add(ExchangeRate(
            tenant_id=tenant_id, from_currency=f, to_currency=t,
            rate=r, date=today,
        ))


def _ensure_bank_leaf(s: Session, tenant_id: int, code: str, name: str) -> Account:
    """Create (or reuse) a dedicated Asset leaf under Current Assets for a bank."""
    existing = _account(s, tenant_id, code)
    if existing:
        return existing
    bank1010 = _account(s, tenant_id, "1010")
    parent_id = bank1010.parent_id if bank1010 else None
    if parent_id is None:
        ca = _account(s, tenant_id, "11")
        parent_id = ca.id if ca else None
    acc = Account(
        tenant_id=tenant_id,
        code=code,
        name=name,
        type="Asset",
        parent_id=parent_id,
        is_group=False,
        is_active=True,
    )
    s.add(acc)
    s.flush()
    return acc


def _bank_cash_pool(s: Session, tenant_id: int) -> list[Account]:
    """Cash/bank leaves linked to BankAccounts (preferred) with CoA fallbacks."""
    seen: dict[int, Account] = {}
    for ba in s.exec(
        select(BankAccount).where(BankAccount.tenant_id == tenant_id)
    ).all():
        if not ba.coa_account_id:
            continue
        acc = s.get(Account, ba.coa_account_id)
        if acc and acc.tenant_id == tenant_id:
            seen[acc.id] = acc
    if seen:
        return list(seen.values())
    out: list[Account] = []
    for code in ("1011", "1012", "1010", "1000"):
        a = _account(s, tenant_id, code)
        if a:
            out.append(a)
    return out


def _pick_cash_account(
    pool: list[Account], i: int, method: str,
) -> Account:
    """Prefer cash leaf for cash methods; rotate banks otherwise."""
    cash_leaves = [a for a in pool if a.code == "1000"]
    bank_leaves = [a for a in pool if a.code != "1000"] or pool
    if method == "cash" and cash_leaves:
        return cash_leaves[0]
    return bank_leaves[i % len(bank_leaves)]


def _seed_recurring_templates(s: Session, tenant_id: int) -> None:
    if s.exec(
        select(RecurringTemplate).where(RecurringTemplate.tenant_id == tenant_id)
    ).first():
        return
    today = date.today()
    # Prefer dedicated Main Current leaf; fall back to generic Bank.
    cash_code = "1011" if _account(s, tenant_id, "1011") else "1010"
    templates = [
        ("Office Rent",        "monthly",   "5000", cash_code, "Monthly office rent"),
        ("Internet & Phone",   "monthly",   "5000", cash_code, "Connectivity"),
        ("Cleaning Services",  "monthly",   "5000", cash_code, "Office cleaning"),
        ("Software Licenses",  "monthly",   "5000", cash_code, "SaaS subscriptions"),
        ("Bookkeeping Fee",    "quarterly", "5000", cash_code, "External bookkeeping"),
        ("Insurance Premium",  "yearly",    "5000", cash_code, "Annual policy"),
    ]
    for name, freq, expense_code, cash_code, descr in templates:
        exp = _account(s, tenant_id, expense_code)
        cash = _account(s, tenant_id, cash_code)
        if not exp or not cash:
            continue
        amount = D(random.randint(200, 2000))
        s.add(RecurringTemplate(
            tenant_id=tenant_id, name=name, frequency=freq,
            next_run=today.isoformat(), description=descr,
            entries_json=(
                '[{"account_id": ' + str(exp.id) + ', "debit": ' + str(amount) + ', "credit": 0},'
                ' {"account_id": ' + str(cash.id) + ', "debit": 0, "credit": ' + str(amount) + '}]'
            ),
        ))


# ── Bank accounts ─────────────────────────────────────────────────────────────


def _seed_bank_accounts(s: Session, tenant_id: int) -> None:
    """Seed 3 bank/cash accounts, each on its own CoA leaf (1011 / 1012 / 1000).

    Generic ``1010 Bank`` stays in the CoA as an unlinked default; dedicated
    leaves keep Bank Book, Bank Accounts balances, and Trial Balance aligned.
    """
    existing = s.exec(
        select(BankAccount).where(BankAccount.tenant_id == tenant_id)
    ).all()
    if existing:
        return

    leaf_hbl = _ensure_bank_leaf(s, tenant_id, "1011", "HBL Main Current")
    leaf_scb = _ensure_bank_leaf(s, tenant_id, "1012", "SCB USD Operating")
    cash_coa = _account(s, tenant_id, "1000")

    configs = [
        ("Main Current Account", "Habib Bank Ltd.",  "1234-5678-9012", leaf_hbl),
        ("USD Operating Account", "Standard Chartered", "9876-5432-1098", leaf_scb),
        ("Petty Cash Float",     None,               None,             cash_coa),
    ]
    for name, bank_name, acc_no, coa in configs:
        if coa is None:
            continue
        s.add(BankAccount(
            tenant_id=tenant_id,
            name=name,
            bank_name=bank_name,
            account_number=acc_no,
            coa_account_id=coa.id,
        ))
    s.flush()


# ── Bills (purchase) ──────────────────────────────────────────────────────────


def _seed_bills(
    s: Session, user: User, vendors: list[Vendor], products: list[Product],
    business_model: str, payment_terms: list[PaymentTerm], count: int = 100,
) -> list[Bill]:
    tid = user.tenant_id
    existing = s.exec(select(Bill).where(Bill.tenant_id == tid)).all()
    if len(existing) >= count:
        return list(existing)

    dates = _spread_dates(count, min_days_ago=5)
    bills: list[Bill] = list(existing)

    ap = _account(s, tid, "2000")
    gst_input = _account(s, tid, "1250") or _account(s, tid, "2200")
    exp_pool = _expense_pool(s, tid, business_model)

    purchasable = [p for p in products if p.product_type == "stock"] or products

    to_create = count - len(existing)
    for i in range(to_create):
        idx = len(existing) + i
        bill_date = dates[idx] if idx < len(dates) else dates[-1]
        vendor = vendors[idx % len(vendors)]

        # Pick payment term
        term = random.choice(payment_terms) if payment_terms else None
        term_days = term.days if term else 30
        due = _due_date(bill_date, term_days)

        n_lines = random.randint(1, 3)
        chosen = random.sample(purchasable, min(n_lines, len(purchasable)))
        subtotal = ZERO
        line_items: list[dict] = []
        for p in chosen:
            qty = D(random.randint(5, 25))
            rate = D(p.default_rate) / D(2) if p.default_rate > 0 else D(random.randint(2, 30))
            rate = money(rate if rate > 0 else D(5))
            amount = money(qty * rate)
            subtotal += amount
            line_items.append({"product": p, "qty": qty, "rate": rate, "amount": amount})

        # Seasonal uplift: Q3–Q4 (months 7-12 from year start) ×1.3
        month = date.fromisoformat(bill_date).month
        if month >= 7:
            subtotal = money(subtotal * D("1.3"))
            line_items = [{**li, "amount": money(li["amount"] * D("1.3"))} for li in line_items]

        gst_rate = D(17)
        gst_amount = money(subtotal * gst_rate / D(100))
        total = money(subtotal + gst_amount)

        number = next_number(s, tid, "bill", "BILL", width=4)
        status_cycle = ("posted", "posted", "posted", "partial", "paid", "posted")
        status = status_cycle[idx % len(status_cycle)]

        bill = Bill(
            tenant_id=tid, number=number, vendor_id=vendor.id,
            vendor_name=vendor.name,
            bill_date=bill_date, due_date=due,
            description=f"Purchase from {vendor.name}",
            notes=random.choice(BILL_NOTES_POOL),
            internal_memo=random.choice(BILL_MEMO_POOL) if random.random() > 0.5 else None,
            subtotal=money(subtotal), gst_rate=gst_rate, gst_amount=gst_amount,
            total=total, currency="USD", exchange_rate=D(1),
            status=status,
            payment_term_id=term.id if term else None,
            ap_account_id=ap.id if ap else None,
        )
        s.add(bill); s.flush()

        for li in line_items:
            s.add(BillLine(
                bill_id=bill.id, product_id=li["product"].id,
                description=li["product"].name,
                qty=li["qty"], unit=li["product"].unit,
                rate=li["rate"], amount=li["amount"],
            ))
            if li["product"].product_type == "stock":
                record_purchase(
                    s, tenant_id=tid, product_id=li["product"].id,
                    qty=li["qty"], unit_cost=li["rate"],
                    source_doc=number,
                )

        # JE: Dr model-specific expense + Dr GST / Cr AP
        exp_acc = exp_pool[idx % len(exp_pool)]
        entries = [EntryInput(account_id=exp_acc.id, debit=money(subtotal))]
        if gst_amount > 0 and gst_input:
            entries.append(EntryInput(account_id=gst_input.id, debit=gst_amount))
        if ap:
            entries.append(EntryInput(account_id=ap.id, credit=total))
        if len(entries) >= 2:
            txn = post_transaction(
                s, user, date=bill_date,
                description=f"Bill {number} — {vendor.name}",
                entries=entries,
                audit_entity_type="bill",
                audit_detail={"number": number, "total": str(total)},
                voucher_type="PU",
            )
            bill.transaction_id = txn.id
            s.add(bill)

        bills.append(bill)
    return bills


# ── Invoices (sales) ──────────────────────────────────────────────────────────


def _seed_invoices(
    s: Session, user: User, customers: list[Customer], products: list[Product],
    business_model: str, payment_terms: list[PaymentTerm], count: int = 100,
) -> list[Invoice]:
    tid = user.tenant_id
    existing = s.exec(select(Invoice).where(Invoice.tenant_id == tid)).all()
    if len(existing) >= count:
        return list(existing)

    dates = _spread_dates(count, min_days_ago=5)
    invoices: list[Invoice] = list(existing)

    ar = _account(s, tid, "1100")
    gst_out = _account(s, tid, "2200")
    cogs = _account(s, tid, "5010")
    inv_acc = _account(s, tid, "1200") or _account(s, tid, "1202")
    rev_pool = _revenue_pool(s, tid, business_model)

    sellable = [p for p in products if p.product_type in ("stock", "service")] or products

    status_cycle = ("draft", "posted", "posted", "partial", "paid",
                    "posted", "posted", "paid", "overdue", "posted")

    to_create = count - len(existing)
    for i in range(to_create):
        idx = len(existing) + i
        issue_date = dates[idx] if idx < len(dates) else dates[-1]
        customer = customers[idx % len(customers)]

        term = random.choice(payment_terms) if payment_terms else None
        term_days = term.days if term else 30
        due = _due_date(issue_date, term_days)

        n_lines = random.randint(1, 3)
        chosen = random.sample(sellable, min(n_lines, len(sellable)))
        subtotal = ZERO
        line_items: list[dict] = []
        total_cogs = ZERO

        for p in chosen:
            qty = D(random.randint(1, 6))
            rate = D(p.default_rate) if p.default_rate > 0 else D(random.randint(20, 100))
            amount = money(qty * rate)
            subtotal += amount
            line_items.append({"product": p, "qty": qty, "rate": rate, "amount": amount})
            if p.product_type == "stock":
                try:
                    cogs_amt = consume_stock(s, tenant_id=tid, product_id=p.id, qty=qty)
                    total_cogs += cogs_amt
                except Exception:
                    pass

        # Seasonal uplift Q3–Q4
        month = date.fromisoformat(issue_date).month
        if month >= 7:
            subtotal = money(subtotal * D("1.25"))
            line_items = [{**li, "amount": money(li["amount"] * D("1.25"))} for li in line_items]

        gst_rate = D(17)
        gst_amount = money(subtotal * gst_rate / D(100))
        total = money(subtotal + gst_amount)

        number = next_number(s, tid, "invoice", "INV", width=4)
        status = status_cycle[idx % len(status_cycle)]
        # Overdue: only if due date is in the past
        if status == "overdue" and date.fromisoformat(due) >= date.today():
            status = "posted"

        # Route to a model-specific revenue account
        rev_acc = rev_pool[idx % len(rev_pool)]

        invoice = Invoice(
            tenant_id=tid, number=number, customer_id=customer.id,
            customer_name=customer.name,
            issue_date=issue_date, due_date=due,
            description=f"Sale to {customer.name}",
            notes=random.choice(INVOICE_NOTES_POOL),
            internal_memo=random.choice(INVOICE_MEMO_POOL) if random.random() > 0.5 else None,
            subtotal=money(subtotal), gst_rate=gst_rate, gst_amount=gst_amount,
            total=total, currency="USD", exchange_rate=D(1),
            status=status,
            payment_term_id=term.id if term else None,
            ar_account_id=ar.id if ar else None,
            revenue_account_id=rev_acc.id if rev_acc else None,
        )
        s.add(invoice); s.flush()

        for li in line_items:
            s.add(InvoiceLine(
                invoice_id=invoice.id, product_id=li["product"].id,
                description=li["product"].name,
                qty=li["qty"], unit=li["product"].unit,
                rate=li["rate"], amount=li["amount"],
            ))

        if status != "draft" and ar and rev_acc:
            # Compute deferred-revenue split (mirrors create_invoice #47 path):
            # any line whose product.is_deferred contributes its net to 2300
            # instead of the normal revenue account.  fx_rate=1 throughout seeder.
            deferred_net = ZERO
            deferred_lines: list[LineDeferral] = []
            for li in line_items:
                prod = li["product"]
                if getattr(prod, "is_deferred", False):
                    net_base = money(li["qty"] * li["rate"])  # fx_rate = 1
                    if net_base > ZERO:
                        deferred_lines.append(LineDeferral(
                            net_base=net_base,
                            recognition_months=max(1, int(getattr(prod, "recognition_months", 12) or 12)),
                            revenue_account_id=getattr(prod, "revenue_account_id", None) or rev_acc.id,
                        ))
                        deferred_net += net_base

            # Clamp to subtotal to prevent sub-cent rounding imbalance
            deferred_credit = min(deferred_net, subtotal)
            revenue_net = money(subtotal - deferred_credit)

            entries = [EntryInput(account_id=ar.id, debit=total)]
            if revenue_net > ZERO:
                entries.append(EntryInput(account_id=rev_acc.id, credit=revenue_net))
            if deferred_credit > ZERO:
                deferred_acc_obj = resolve_deferred_account(s, tid)
                entries.append(EntryInput(account_id=deferred_acc_obj.id, credit=deferred_credit))
            if gst_amount > 0 and gst_out:
                entries.append(EntryInput(account_id=gst_out.id, credit=gst_amount))
            elif gst_amount > ZERO and not gst_out:
                # GST account missing: roll into revenue to keep JV balanced
                if revenue_net > ZERO:
                    # Replace revenue entry with revenue+gst combined
                    entries = [e for e in entries if e.account_id != rev_acc.id]
                    entries.append(EntryInput(account_id=rev_acc.id, credit=money(revenue_net + gst_amount)))
                else:
                    entries.append(EntryInput(account_id=rev_acc.id, credit=gst_amount))

            txn = post_transaction(
                s, user, date=issue_date,
                description=f"Invoice {number} — {customer.name}",
                entries=entries,
                audit_entity_type="invoice",
                audit_detail={"number": number, "total": str(total)},
                voucher_type="SL",
            )
            invoice.transaction_id = txn.id
            s.add(invoice)

            # Originate DeferredRevenueSchedule rows after invoice.id is set
            if deferred_credit > ZERO and deferred_lines:
                deferral_plan = DeferralPlan(
                    deferred_lines=deferred_lines,
                    deferred_net_base=deferred_credit,
                )
                create_schedules(s, user, invoice, deferral_plan)

            if total_cogs > 0 and cogs and inv_acc:
                post_transaction(
                    s, user, date=issue_date,
                    description=f"COGS for {number}",
                    entries=[
                        EntryInput(account_id=cogs.id, debit=total_cogs),
                        EntryInput(account_id=inv_acc.id, credit=total_cogs),
                    ],
                    audit_entity_type="invoice",
                    audit_detail={"number": number, "cogs": str(total_cogs)},
                )

        invoices.append(invoice)
    return invoices


# ── Payments ──────────────────────────────────────────────────────────────────


def _seed_payments_received(
    s: Session, user: User, invoices: list[Invoice], count: int = 70,
) -> None:
    tid = user.tenant_id
    posted = [i for i in invoices if i.status in ("posted", "partial", "paid", "overdue")]
    if not posted:
        return
    existing = s.exec(
        select(PaymentReceived).where(PaymentReceived.tenant_id == tid)
    ).all()
    if len(existing) >= count:
        return
    pool = _bank_cash_pool(s, tid)
    ar   = _account(s, tid, "1100")
    if not pool or not ar:
        return

    to_create = min(count - len(existing), len(posted))
    for i, inv in enumerate(posted[:to_create]):
        # Payment date: 5–45 days after invoice issue date (stays in past)
        inv_date = date.fromisoformat(inv.issue_date)
        pay_offset = random.randint(5, 45)
        pay_d = inv_date + timedelta(days=pay_offset)
        if pay_d > date.today():
            pay_d = date.today() - timedelta(days=random.randint(1, 5))
        pay_date = pay_d.isoformat()

        ratio = D("0.5") if inv.status == "partial" else D("1.0")
        amount = money(D(str(inv.total)) * ratio)
        if amount <= 0:
            continue

        method = random.choice(["bank", "cash", "cheque"])
        cash = _pick_cash_account(pool, i, method)
        # Voucher by instrument: cash → CR, bank/cheque → BR (CoA leaf may still
        # be the petty-cash BankAccount link for the cash path).
        voucher = "CR" if method == "cash" else "BR"

        pay = PaymentReceived(
            tenant_id=tid, invoice_id=inv.id, customer_name=inv.customer_name,
            payment_date=pay_date, amount=amount,
            method=method,
            cash_account_id=cash.id,
        )
        s.add(pay); s.flush()
        s.add(PaymentAllocation(
            tenant_id=tid, payment_id=pay.id, invoice_id=inv.id, amount=amount,
        ))
        txn = post_transaction(
            s, user, date=pay_date,
            description=f"Payment for {inv.number}",
            entries=[
                EntryInput(account_id=cash.id, debit=amount),
                EntryInput(account_id=ar.id,   credit=amount),
            ],
            audit_entity_type="payment",
            audit_detail={"invoice": inv.number, "amount": str(amount)},
            voucher_type=voucher,
        )
        pay.transaction_id = txn.id
        s.add(pay)


def _seed_bill_payments(
    s: Session, user: User, bills: list[Bill], count: int = 70,
) -> None:
    tid = user.tenant_id
    existing = s.exec(
        select(BillPayment).where(BillPayment.tenant_id == tid)
    ).all()
    if len(existing) >= count:
        return
    pool = _bank_cash_pool(s, tid)
    ap   = _account(s, tid, "2000")
    if not pool or not ap:
        return

    to_create = min(count - len(existing), len(bills))
    for i, bill in enumerate(bills[:to_create]):
        bill_date = date.fromisoformat(bill.bill_date)
        pay_offset = random.randint(5, 40)
        pay_d = bill_date + timedelta(days=pay_offset)
        if pay_d > date.today():
            pay_d = date.today() - timedelta(days=random.randint(1, 5))
        pay_date = pay_d.isoformat()

        ratio = D("0.7") if i % 4 == 0 else D("1.0")
        amount = money(D(str(bill.total)) * ratio)
        if amount <= 0:
            continue

        method = random.choice(["bank", "cheque", "cash"])
        cash = _pick_cash_account(pool, i, method)
        voucher = "CP" if method == "cash" else "BP"

        pay = BillPayment(
            tenant_id=tid, bill_id=bill.id, vendor_name=bill.vendor_name,
            payment_date=pay_date, amount=amount,
            method=method,
            cash_account_id=cash.id,
        )
        s.add(pay); s.flush()
        s.add(PaymentAllocation(
            tenant_id=tid, billpayment_id=pay.id, bill_id=bill.id, amount=amount,
        ))
        txn = post_transaction(
            s, user, date=pay_date,
            description=f"Payment for {bill.number}",
            entries=[
                EntryInput(account_id=ap.id,   debit=amount),
                EntryInput(account_id=cash.id, credit=amount),
            ],
            audit_entity_type="bill_payment",
            audit_detail={"bill": bill.number, "amount": str(amount)},
            voucher_type=voucher,
        )
        pay.transaction_id = txn.id
        s.add(pay)


# ── Manual JVs ────────────────────────────────────────────────────────────────


def _seed_manual_jvs(s: Session, user: User, count: int = 60) -> None:
    tid = user.tenant_id

    # Resolve accounts — fall back gracefully if a code doesn't exist for this model
    def acc(code: str) -> Optional[Account]:
        return _account(s, tid, code)

    cash       = acc("1000") or acc("1010")
    bank       = acc("1011") or acc("1010") or acc("1000")
    bank2      = acc("1012") or bank
    ar         = acc("1100")
    ap         = acc("2000")
    gst_out    = acc("2200")
    gst_in     = acc("1250")
    capital    = acc("3000")
    drawings   = acc("3010")
    retained   = acc("3100")
    revenue    = acc("4000")
    cons_rev   = acc("4010")  # services / manufacturing / telecom
    rec_rev    = acc("4020")  # services / telecom
    other_inc  = acc("4900")
    gen_exp    = acc("5000")
    cogs       = acc("5010")
    freight    = acc("5020")  # trader / mfg
    storage    = acc("5030")  # trader / mfg
    inv_adj    = acc("5040")  # trader
    depr_exp   = acc("5050")
    dir_labour = acc("5100")  # manufacturing
    sub_cost   = acc("5110")  # services / mfg
    mfg_oh     = acc("5200")  # manufacturing
    indirect   = acc("5210")  # manufacturing
    other_exp  = acc("5900")
    deferred   = acc("2300")  # services
    inventory  = acc("1200") or acc("1202")

    # Build pattern list — skip entries where both accounts don't exist
    raw_patterns: list[tuple[str, Optional[Account], Optional[Account], Decimal]] = [
        # Opening & capital
        ("Owner capital injection — Q1",    capital,   bank,      D(50000)),
        ("Owner capital top-up — Q2",       capital,   bank,      D(15000)),
        ("Owner capital top-up — Q3",       capital,   bank,      D(10000)),
        ("Owner drawings — Q1",             drawings,  cash,      D(800)),
        ("Owner drawings — Q2",             drawings,  cash,      D(900)),
        ("Owner drawings — Q3",             drawings,  cash,      D(700)),
        ("Owner drawings — Q4",             drawings,  cash,      D(1000)),
        ("Transfer to retained earnings",   retained,  revenue,   D(5000)),
        # Operating expenses — general
        ("Office rent — Jan",               gen_exp,   bank,      D(1500)),
        ("Office rent — Feb",               gen_exp,   bank,      D(1500)),
        ("Office rent — Mar",               gen_exp,   bank,      D(1500)),
        ("Office rent — Apr",               gen_exp,   bank,      D(1500)),
        ("Office rent — May",               gen_exp,   bank,      D(1500)),
        ("Office rent — Jun",               gen_exp,   bank,      D(1500)),
        ("Office rent — Jul",               gen_exp,   bank,      D(1500)),
        ("Office rent — Aug",               gen_exp,   bank,      D(1500)),
        ("Office rent — Sep",               gen_exp,   bank,      D(1500)),
        ("Office rent — Oct",               gen_exp,   bank,      D(1500)),
        ("Office rent — Nov",               gen_exp,   bank,      D(1500)),
        ("Office rent — Dec",               gen_exp,   bank,      D(1500)),
        ("Electricity bill — Q1",           gen_exp,   cash,      D(460)),
        ("Electricity bill — Q2",           gen_exp,   cash,      D(510)),
        ("Electricity bill — Q3",           gen_exp,   cash,      D(570)),
        ("Electricity bill — Q4",           gen_exp,   cash,      D(490)),
        ("Internet & phone",                gen_exp,   bank,      D(180)),
        ("Cleaning services",               gen_exp,   cash,      D(240)),
        ("Security deposit paid",           gen_exp,   bank,      D(3000)),
        ("Office supplies",                 gen_exp,   cash,      D(120)),
        ("Stationery & printing",           gen_exp,   cash,      D(85)),
        ("Courier & postage",               gen_exp,   cash,      D(60)),
        ("Bank charges — Q1",               gen_exp,   bank,      D(35)),
        ("Bank charges — Q2",               gen_exp,   bank,      D(40)),
        ("Bank charges — Q3",               gen_exp,   bank,      D(38)),
        ("Bank charges — Q4",               gen_exp,   bank,      D(42)),
        ("Vehicle running costs",           gen_exp,   cash,      D(520)),
        ("Fuel expense",                    gen_exp,   cash,      D(310)),
        ("Parking & toll",                  gen_exp,   cash,      D(75)),
        # Depreciation
        ("Depreciation — equipment Q1",     depr_exp,  bank,      D(400)),
        ("Depreciation — equipment Q2",     depr_exp,  bank,      D(400)),
        ("Depreciation — equipment Q3",     depr_exp,  bank,      D(400)),
        ("Depreciation — equipment Q4",     depr_exp,  bank,      D(400)),
        ("Yearend depreciation adjustment", depr_exp,  bank,      D(500)),
        # Salaries / labour
        ("Salary — Jan",                    dir_labour or gen_exp, cash, D(12000)),
        ("Salary — Feb",                    dir_labour or gen_exp, cash, D(12000)),
        ("Salary — Mar",                    dir_labour or gen_exp, cash, D(12000)),
        ("Salary — Apr",                    dir_labour or gen_exp, cash, D(12500)),
        ("Salary — May",                    dir_labour or gen_exp, cash, D(12500)),
        ("Salary — Jun",                    dir_labour or gen_exp, cash, D(12500)),
        ("Salary — Jul",                    dir_labour or gen_exp, cash, D(13000)),
        ("Salary — Aug",                    dir_labour or gen_exp, cash, D(13000)),
        ("Salary — Sep",                    dir_labour or gen_exp, cash, D(13000)),
        ("Salary — Oct",                    dir_labour or gen_exp, cash, D(13500)),
        ("Salary — Nov",                    dir_labour or gen_exp, cash, D(13500)),
        ("Salary — Dec — incl. bonus",      dir_labour or gen_exp, cash, D(18000)),
        ("Overtime payment",                dir_labour or gen_exp, cash, D(900)),
        ("Staff welfare",                   gen_exp,   cash,      D(350)),
        # Manufacturing overhead (mfg only — skipped if acc is None)
        ("Factory overhead — Q1",           mfg_oh,    bank,      D(8000)),
        ("Factory overhead — Q2",           mfg_oh,    bank,      D(8500)),
        ("Factory overhead — Q3",           mfg_oh,    bank,      D(9000)),
        ("Factory overhead — Q4",           mfg_oh,    bank,      D(8200)),
        ("Indirect materials consumed",     indirect,  inventory, D(2000)),
        ("Subcontractor cost — batch A",    sub_cost,  bank,      D(5000)),
        ("Subcontractor cost — batch B",    sub_cost,  bank,      D(4500)),
        # Trader freight & storage
        ("Freight in — shipment 1",         freight,   bank,      D(1200)),
        ("Freight in — shipment 2",         freight,   bank,      D(950)),
        ("Storage charges — Q1",            storage,   bank,      D(600)),
        ("Storage charges — Q2",            storage,   bank,      D(650)),
        ("Inventory adjustment write-off",  inv_adj,   inventory, D(800)),
        # Marketing & admin
        ("Marketing campaign — digital",    other_exp, bank,      D(3200)),
        ("Trade show expenses",             other_exp, bank,      D(2800)),
        ("Professional fees — legal",       other_exp, bank,      D(1800)),
        ("Yearend audit fee",               other_exp, bank,      D(2500)),
        ("Training & development",          other_exp, bank,      D(800)),
        ("Annual insurance premium",        gen_exp,   bank,      D(1200)),
        ("Office renovation",               gen_exp,   bank,      D(4500)),
        # Revenue / income
        ("Bank interest income",            bank,      other_inc, D(95)),
        ("Gain on asset disposal",          bank,      other_inc, D(1100)),
        ("Miscellaneous income",            bank,      other_inc, D(200)),
        # Services-specific revenue recognition
        ("Consulting revenue — project A",  bank,      cons_rev or revenue, D(8500)),
        ("Consulting revenue — project B",  bank,      cons_rev or revenue, D(6200)),
        ("Recurring support contract",      bank,      rec_rev or revenue,  D(3600)),
        ("Deferred revenue recognised",     deferred,  rec_rev or revenue,  D(2400)),
        # GST settlement
        ("GST payable settlement — Q1",     gst_out,   bank,      D(15000)),
        ("GST payable settlement — Q2",     gst_out,   bank,      D(18000)),
        ("GST payable settlement — Q3",     gst_out,   bank,      D(22000)),
        ("GST input credit claimed",        bank,      gst_in,    D(8000)),
        # Inter-bank transfers — give both dedicated bank leaves contra legs
        ("Inter-bank transfer HBL→SCB",     bank2,     bank,      D(8500)),
        ("Inter-bank transfer SCB→HBL",     bank,      bank2,     D(4200)),
        ("Petty cash replenishment",        cash,      bank,      D(1500)),
    ]

    # Filter to patterns where both accounts are non-None and distinct
    valid = [
        (desc, a, b, amt)
        for desc, a, b, amt in raw_patterns
        if a is not None and b is not None and a.id != b.id
    ]
    if not valid:
        return

    existing_count = len(s.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tid,
            AuditLog.entity_type == "manual_jv",
        )
    ).all())
    to_create = max(0, count - existing_count)
    if to_create == 0:
        return

    jv_dates = _spread_dates(to_create, min_days_ago=3)

    for i in range(to_create):
        desc, dr_acc, cr_acc, base_amt = valid[i % len(valid)]
        cycle = i // len(valid)
        amt = money(base_amt + D(cycle * 50))
        d = jv_dates[i]
        post_transaction(
            s, user, date=d,
            description=f"{desc}{f' (#{cycle + 1})' if cycle else ''}",
            entries=[
                EntryInput(account_id=dr_acc.id, debit=amt),
                EntryInput(account_id=cr_acc.id, credit=amt),
            ],
            audit_entity_type="manual_jv",
            audit_detail={"desc": desc, "amount": str(amt)},
        )


# ── Manufacturing-specific ────────────────────────────────────────────────────


def _seed_manufacturing(
    s: Session, user: User,
    customers: list[Customer],
    stock_products: list[Product],
    customer_supplied_products: list[Product],
) -> None:
    tid = user.tenant_id

    raw = [p for p in stock_products if p.code and p.code.startswith("RM-")]
    fg  = [p for p in stock_products if p.code and p.code.startswith("FG-")]
    if not raw or not fg or not customer_supplied_products:
        return

    # BoMs — 50, one per finished good × variations
    existing_boms = s.exec(select(BomHeader).where(BomHeader.tenant_id == tid)).all()
    if len(existing_boms) < 50:
        for i in range(50 - len(existing_boms)):
            output = fg[i % len(fg)]
            r1 = raw[i % len(raw)]
            r2 = raw[(i + 1) % len(raw)]
            cs = customer_supplied_products[i % len(customer_supplied_products)]

            existing_max = s.exec(
                select(BomHeader).where(
                    BomHeader.tenant_id == tid,
                    BomHeader.output_product_id == output.id,
                )
            ).all()
            for prev in existing_max:
                prev.is_active = False; s.add(prev)
            version = (max((b.version for b in existing_max), default=0)) + 1

            h = BomHeader(
                tenant_id=tid, output_product_id=output.id,
                output_qty=D(1), version=version, is_active=True,
                description=f"Recipe v{version} for {output.name}",
            )
            s.add(h); s.flush()
            s.add(BomLine(
                bom_id=h.id, component_product_id=r1.id,
                qty_per_output=D(random.randint(1, 3)),
                source="own_stock",
            ))
            s.add(BomLine(
                bom_id=h.id, component_product_id=r2.id,
                qty_per_output=D(random.randint(1, 2)),
                source="own_stock",
            ))
            s.add(BomLine(
                bom_id=h.id, component_product_id=cs.id,
                qty_per_output=D(1),
                source="customer_supplied",
            ))

    # Rate plans — 50
    existing_plans = s.exec(select(RatePlan).where(RatePlan.tenant_id == tid)).all()
    plans_to_create = max(0, 50 - len(existing_plans))
    plan_specs = [
        ("STITCH-STD",   "Standard Stitching",      10, True,  5, 10),
        ("STITCH-PREM",  "Premium Stitching",        15, True,  8, 15),
        ("CUT-STD",      "Standard Cutting",          5, False, 0,  0),
        ("FINISH-LITE",  "Light Finishing",            8, True,  3,  8),
        ("FINISH-HEAVY", "Heavy Finishing",           18, True,  6, 12),
        ("DYE-STD",      "Standard Dyeing",           12, True,  4,  9),
        ("DYE-PREM",     "Premium Dyeing",            22, True,  7, 14),
        ("EMBROIDERY",   "Embroidery Work",           25, True,  5, 20),
        ("PRINTING",     "Screen Printing",           14, True,  4, 12),
        ("ASSEMBLY",     "Assembly Work",             20, True,  6, 18),
        ("QC-EXPRESS",   "QC Express Lane",            6, False, 0,  5),
        ("PACKAGING",    "Packaging Service",          4, True,  2,  6),
        ("WASH-COLD",    "Cold Water Wash",            7, True,  2,  5),
        ("WASH-HOT",     "Hot Water Wash",             9, True,  3,  7),
        ("IRON-STD",     "Standard Ironing",           5, True,  2,  4),
        ("IRON-STEAM",   "Steam Pressing",             8, True,  3,  6),
        ("FOLD-PACK",    "Fold & Pack",                4, True,  1,  3),
        ("LABEL-SEW",    "Label Sewing",               3, True,  1,  2),
        ("INSPECT-QC",   "Quality Inspection",        10, False, 0,  8),
        ("OVERLOCK",     "Overlocking",                6, True,  2,  5),
        ("BUTTON-ATT",   "Button Attachment",          4, True,  1,  3),
        ("ZIPPER-FIT",   "Zipper Fitting",             5, True,  2,  4),
        ("TRIM-CUT",     "Trim Cutting",               3, True,  1,  2),
        ("SMOCKING",     "Smocking Work",             30, True,  8, 22),
        ("BEADWORK",     "Bead Work",                 35, True, 10, 25),
        ("HAND-EMBROI",  "Hand Embroidery",           40, True, 12, 28),
        ("LACE-ATT",     "Lace Attachment",           18, True,  5, 14),
        ("PATCH-SEW",    "Patch Sewing",              12, True,  4, 10),
        ("HEAT-PRESS",   "Heat Transfer Press",       16, True,  5, 11),
        ("SUBLIMATION",  "Sublimation Printing",      20, True,  6, 14),
        ("STONEWASH",    "Stone Washing",             15, True,  5, 10),
        ("ACID-WASH",    "Acid Wash Treatment",       17, True,  6, 12),
        ("ENZYME-WASH",  "Enzyme Washing",            13, True,  4,  9),
        ("PIGMENT-DYE",  "Pigment Dyeing",            19, True,  6, 13),
        ("DISCHARGE-PR", "Discharge Printing",        21, True,  7, 15),
        ("DEVORE",       "Devore Technique",          38, True, 11, 26),
        ("BURNOUT",      "Burnout Print",             28, True,  9, 20),
        ("RESIST-DYE",   "Resist Dyeing",             24, True,  7, 17),
        ("PLEATING",     "Pleating Work",             22, True,  7, 16),
        ("SMASH-PLEAT",  "Smash Pleating",            26, True,  8, 18),
        ("BOX-PLEAT",    "Box Pleating",              23, True,  7, 16),
        ("PINTUCK",      "Pintuck Stitching",         16, True,  5, 11),
        ("FAGOTING",     "Fagoting Work",             32, True,  9, 23),
        ("TRAPUNTO",     "Trapunto Quilting",         36, True, 10, 26),
        ("SHADOW-WORK",  "Shadow Work Embroidery",    42, True, 12, 30),
        ("CUTWORK",      "Cutwork Embroidery",        45, True, 13, 32),
        ("CHAIN-STITCH", "Chain Stitch",              18, True,  5, 12),
        ("CROSS-STITCH", "Cross Stitch",              28, True,  8, 20),
        ("SATIN-STITCH", "Satin Stitch",              22, True,  7, 15),
        ("FRENCH-KNOT",  "French Knot Work",          30, True,  9, 21),
    ]
    plan_objs: list[RatePlan] = list(existing_plans)
    for spec in plan_specs[:plans_to_create]:
        code, name, rate, mats, ovh, marg = spec
        plan_exists = s.exec(
            select(RatePlan).where(RatePlan.tenant_id == tid, RatePlan.code == code)
        ).first()
        if plan_exists:
            plan_objs.append(plan_exists); continue
        p = RatePlan(
            tenant_id=tid, code=code, name=name,
            per_unit_rate=D(rate), includes_materials_at_cost=mats,
            overhead_pct=D(ovh), margin_pct=D(marg),
            version=1, is_active=True,
        )
        s.add(p); s.flush()
        plan_objs.append(p)

    # Assign first plan to each customer
    for c in customers:
        existing_assign = s.exec(
            select(CustomerRatePlan).where(
                CustomerRatePlan.tenant_id == tid,
                CustomerRatePlan.customer_id == c.id,
            )
        ).first()
        if existing_assign or not plan_objs:
            continue
        s.add(CustomerRatePlan(
            tenant_id=tid, customer_id=c.id,
            rate_plan_id=plan_objs[0].id, is_active=True,
        ))

    # GRNs — 50, spread over the year
    godown = s.exec(
        select(StockLocation).where(
            StockLocation.tenant_id == tid,
            StockLocation.type == "customer_custodial",
        )
    ).first()
    if not godown:
        return
    existing_grns = s.exec(
        select(GoodsReceiptNote).where(GoodsReceiptNote.tenant_id == tid)
    ).all()
    grn_objs: list[GoodsReceiptNote] = list(existing_grns)
    grns_to_create = max(0, 50 - len(existing_grns))
    grn_dates = _spread_dates(grns_to_create, min_days_ago=10)
    for i in range(grns_to_create):
        customer = customers[i % len(customers)]
        cs = customer_supplied_products[i % len(customer_supplied_products)]
        qty = D(random.randint(20, 50))
        declared = D(random.randint(100, 500))
        number = next_number(s, tid, "grn", "GRN", width=4)
        grn = GoodsReceiptNote(
            tenant_id=tid, number=number, customer_id=customer.id,
            received_date=grn_dates[i],
            location_id=godown.id, declared_value=money(declared),
        )
        s.add(grn); s.flush()
        s.add(GRNLine(
            grn_id=grn.id, product_id=cs.id, qty=qty,
            lot_no=f"LOT-{i+1:03d}", declared_value=money(declared),
        ))
        s.add(InventoryLayer(
            tenant_id=tid, product_id=cs.id, location_id=godown.id,
            owner_customer_id=customer.id, lot_no=f"LOT-{i+1:03d}",
            qty_received=qty, qty_remaining=qty, unit_cost=ZERO,
            source_doc=number,
        ))
        record_movement(
            s, tenant_id=tid, product_id=cs.id, direction="CUSTODIAL_RECEIPT",
            qty=qty, to_location_id=godown.id, lot_no=f"LOT-{i+1:03d}",
            owner_customer_id=customer.id,
            source_doc_type="grn", source_doc_id=grn.id, posted_to_gl=False,
        )
        memo_a = _account(s, tid, "1210")
        memo_l = _account(s, tid, "2150")
        if memo_a and memo_l and declared > 0:
            for acc_obj in (memo_a, memo_l):
                if not acc_obj.is_memo:
                    acc_obj.is_memo = True; s.add(acc_obj)
            txn = post_transaction(
                s, user, date=grn.received_date,
                description=f"GRN {number} — custodial receipt",
                entries=[
                    EntryInput(account_id=memo_a.id, debit=money(declared)),
                    EntryInput(account_id=memo_l.id, credit=money(declared)),
                ],
                audit_entity_type="grn",
                audit_detail={"number": number},
            )
            grn.transaction_id = txn.id
            s.add(grn)
        grn_objs.append(grn)

    # Production orders — 50
    existing_pos = s.exec(
        select(ProductionOrder).where(ProductionOrder.tenant_id == tid)
    ).all()
    pos_to_create = max(0, 50 - len(existing_pos))
    state_pattern = [
        "draft", "draft", "draft", "started", "started", "started",
        "completed", "completed", "delivered", "delivered",
        "billed", "billed", "billed", "cancelled", "draft",
    ]
    for i in range(pos_to_create):
        active_bom = s.exec(
            select(BomHeader).where(
                BomHeader.tenant_id == tid, BomHeader.is_active == True,  # noqa: E712
            ).order_by(BomHeader.id)
        ).first()
        if not active_bom:
            break
        customer = customers[i % len(customers)]
        qty = D(random.randint(5, 20))
        rate_plan = plan_objs[i % len(plan_objs)] if plan_objs else None

        number = next_number(s, tid, "po", "PO", width=4)
        po = ProductionOrder(
            tenant_id=tid, number=number, bom_id=active_bom.id,
            customer_id=customer.id,
            rate_plan_id=rate_plan.id if rate_plan else None,
            output_qty=qty, state=state_pattern[i % len(state_pattern)],
            created_at=datetime.utcnow() - timedelta(days=random.randint(10, max(10, _seed_span_days()))),
        )
        s.add(po); s.flush()


def _seed_purchase_store_chain(
    s: Session, owner: User, accountant: User, clerk: User,
    vendors: list[Vendor], products: list[Product], invoices: list,
) -> None:
    """#137 Phases 1-2b — Purchase Demand -> Vendor Quotation -> Comparative
    Statement -> Purchase Order -> Gate Inward (-> Bill, 3-way match), plus
    Gate Outward (invoice/debit-note memo exits + scrap draft/approve with
    real GL posting). Manufacturing only (the one demo tenant with
    purchase_store pre-installed). Exercises every status on every document
    so no Purchases/Store screen or report is ever empty.

    Segregation of duties mirrors the real approval rules: `clerk` raises
    documents, `owner` approves them (approver != creator is enforced by the
    app on demands, comparatives, and scrap gate-outward approval).
    """
    tid = owner.tenant_id
    if s.exec(select(PurchaseDemand).where(PurchaseDemand.tenant_id == tid)).first():
        return
    stock_products = [p for p in products if p.product_type == "stock"]
    if len(vendors) < 2 or len(stock_products) < 3:
        return

    demand_dates = _spread_dates(6, min_days_ago=30)

    def _demand_line(pd: PurchaseDemand) -> PurchaseDemandLine:
        return s.exec(
            select(PurchaseDemandLine).where(PurchaseDemandLine.demand_id == pd.id)
        ).first()

    def _new_demand(i: int, product: Product) -> PurchaseDemand:
        number = next_number(s, tid, "purchase_demand", "PD", fmt="{prefix}-{YYYY}-{seq:04d}")
        pd = PurchaseDemand(
            tenant_id=tid, number=number, demand_date=demand_dates[i],
            required_by=_due_date(demand_dates[i], 21),
            purpose=f"Restock {product.name}", status="draft", created_by_id=clerk.id,
        )
        s.add(pd); s.flush()
        s.add(PurchaseDemandLine(
            demand_id=pd.id, product_id=product.id, description=product.name,
            qty=D(random.randint(80, 250)), unit=product.unit,
        ))
        s.flush()
        return pd

    def _approve_demand(pd: PurchaseDemand) -> None:
        pd.status = "approved"; pd.approved_by_id = owner.id
        pd.approved_at = datetime.utcnow()
        s.add(pd)

    def _quote(pd: PurchaseDemand, vendor: Vendor, rate: Decimal) -> tuple:
        dl = _demand_line(pd)
        number = next_number(s, tid, "vendor_quotation", "VQ", fmt="{prefix}-{YYYY}-{seq:04d}")
        vq = VendorQuotation(
            tenant_id=tid, number=number, demand_id=pd.id, vendor_id=vendor.id,
            quote_date=pd.demand_date, valid_until=_due_date(pd.demand_date, 30),
            delivery_terms="Ex-works, 7 days", payment_terms="Net 30",
        )
        s.add(vq); s.flush()
        amount = money(D(dl.qty) * D(rate))
        s.add(VendorQuotationLine(
            quotation_id=vq.id, demand_line_id=dl.id, rate=D(rate), qty=D(dl.qty), amount=amount,
        ))
        s.flush()
        return vq, amount

    def _build_cs(pd: PurchaseDemand, selected_vq: Optional[VendorQuotation],
                  justification: Optional[str], approve: bool) -> ComparativeStatement:
        number = next_number(s, tid, "comparative_statement", "CS", fmt="{prefix}-{YYYY}-{seq:04d}")
        cs = ComparativeStatement(
            tenant_id=tid, number=number, demand_id=pd.id,
            cs_date=_due_date(pd.demand_date, 5),
            selected_quotation_id=selected_vq.id if selected_vq else None,
            justification=justification, status="draft", created_by_id=clerk.id,
        )
        s.add(cs); s.flush()
        if approve:
            cs.status = "approved"; cs.approved_by_id = owner.id
            cs.approved_at = datetime.utcnow()
            s.add(cs)
        return cs

    def _convert_to_po(pd: PurchaseDemand, cs: ComparativeStatement, vendor: Vendor,
                       product: Product, rate: Decimal, amount: Decimal) -> PurchaseOrder:
        dl = _demand_line(pd)
        po_number = next_number(s, tid, "purchase_order", "PO")
        po = PurchaseOrder(
            tenant_id=tid, number=po_number, vendor_id=vendor.id, vendor_name=vendor.name,
            order_date=cs.cs_date, expected_date=_due_date(cs.cs_date, 14),
            description=f"From {cs.number}", subtotal=amount, total=amount,
            status="draft", demand_id=pd.id, comparative_id=cs.id,
        )
        s.add(po); s.flush()
        s.add(PurchaseOrderLine(
            po_id=po.id, product_id=product.id, description=product.name,
            qty=D(dl.qty), unit=product.unit, rate=D(rate), amount=amount,
        ))
        s.flush()
        cs.status = "converted"; cs.po_id = po.id; s.add(cs)
        pd.status = "converted"; s.add(pd)
        return po

    def _bare_po(vendor: Vendor, product: Product, qty: Decimal, rate: Decimal,
                order_date: str) -> PurchaseOrder:
        """A PO with no demand/comparative link — pre-existing/exception
        procurement that predates or bypasses the approval chain, coexisting
        realistically alongside the new chain-controlled POs."""
        amount = money(D(qty) * D(rate))
        po_number = next_number(s, tid, "purchase_order", "PO")
        po = PurchaseOrder(
            tenant_id=tid, number=po_number, vendor_id=vendor.id, vendor_name=vendor.name,
            order_date=order_date, expected_date=_due_date(order_date, 14),
            description=f"Direct procurement from {vendor.name}",
            subtotal=amount, total=amount, status="draft",
        )
        s.add(po); s.flush()
        s.add(PurchaseOrderLine(
            po_id=po.id, product_id=product.id, description=product.name,
            qty=D(qty), unit=product.unit, rate=D(rate), amount=amount,
        ))
        s.flush()
        return po

    def _gate_inward(po: PurchaseOrder, qty_received: Decimal, gate_date: str,
                     vehicle_no: str, challan_no: str) -> GateInward:
        po_line = s.exec(
            select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
        ).first()
        number = next_number(s, tid, "gate_inward", "GI", fmt="{prefix}-{YYYY}-{seq:04d}")
        gi = GateInward(
            tenant_id=tid, number=number, po_id=po.id, gate_date=gate_date,
            time_in="09:30", vehicle_no=vehicle_no, challan_no=challan_no,
            status="open", created_by_id=clerk.id,
        )
        s.add(gi); s.flush()
        s.add(GateInwardLine(
            gate_inward_id=gi.id, po_line_id=po_line.id,
            product_id=po_line.product_id, qty_received=D(qty_received),
        ))
        s.flush()
        if D(qty_received) >= D(po_line.qty):
            po.status = "received"; s.add(po)
        return gi

    def _flat_bill(po: PurchaseOrder, bill_qty: Decimal, bill_date: str) -> Bill:
        """Mirrors the real convert-to-bill endpoint exactly: a flat
        Dr General Expenses / Cr Accounts Payable JV, no inventory branching
        (routers/purchase_orders.py::convert_to_bill does the same)."""
        po_line = s.exec(
            select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
        ).first()
        amount = money(D(bill_qty) * D(po_line.rate))
        ap = get_or_create_account(s, tid, "2000", "Accounts Payable", "Liability")
        exp = get_or_create_account(s, tid, "5000", "General Expenses", "Expense")
        bill_number = next_number(s, tid, "bill", "BILL")
        bill = Bill(
            tenant_id=tid, number=bill_number, vendor_id=po.vendor_id,
            vendor_name=po.vendor_name, bill_date=bill_date,
            due_date=_due_date(bill_date, 30), description=f"From PO {po.number}",
            subtotal=amount, gst_rate=ZERO, gst_amount=ZERO, total=amount,
            status="posted", ap_account_id=ap.id, expense_account_id=exp.id,
        )
        s.add(bill); s.flush()
        s.add(BillLine(
            bill_id=bill.id, product_id=po_line.product_id, description=po_line.description,
            qty=D(bill_qty), unit=po_line.unit, rate=po_line.rate, amount=amount,
        ))
        txn = post_transaction(
            s, owner, date=bill_date, description=f"Bill from PO {po.number}",
            entries=[
                EntryInput(account_id=exp.id, debit=amount),
                EntryInput(account_id=ap.id, credit=amount),
            ],
            audit_entity_type="bill",
            audit_detail={"bill_number": bill_number, "po_number": po.number},
        )
        bill.transaction_id = txn.id
        po.bill_id = bill.id; po.status = "billed"; s.add(po)
        for gi in s.exec(select(GateInward).where(GateInward.po_id == po.id, GateInward.status == "open")):
            gi.status = "billed"; s.add(gi)
        s.add(bill)
        return bill

    # ── Demands: draft / approved-unquoted / cancelled / three quoted-and-compared ──
    pd_draft     = _new_demand(0, stock_products[0])                                    # left in draft
    pd_unquoted  = _new_demand(1, stock_products[1]); _approve_demand(pd_unquoted)       # approved, no VQ yet
    pd_cancelled = _new_demand(2, stock_products[2])
    pd_cancelled.status = "cancelled"; s.add(pd_cancelled)

    pd_a = _new_demand(3, stock_products[0]); _approve_demand(pd_a)
    pd_b = _new_demand(4, stock_products[1]); _approve_demand(pd_b)
    pd_c = _new_demand(5, stock_products[2]); _approve_demand(pd_c)
    s.flush()

    # CS-A: lowest quotation wins — no justification required
    vq_a1, amt_a1 = _quote(pd_a, vendors[0], D("15"))
    vq_a2, _      = _quote(pd_a, vendors[1], D("20"))
    cs_a = _build_cs(pd_a, selected_vq=vq_a1, justification=None, approve=True)
    po_a = _convert_to_po(pd_a, cs_a, vendors[0], stock_products[0], D("15"), amt_a1)
    po_a.status = "approved"; s.add(po_a)
    _gate_inward(po_a, money(D(_demand_line(pd_a).qty) * D("0.6")),
                gate_date=_due_date(po_a.order_date, 8), vehicle_no="LEB-4471", challan_no="CH-2201")
    # partial receipt only — PO stays "approved", demonstrates in-progress receiving

    # CS-B: non-lowest quotation wins — justification required and supplied
    vq_b1, amt_b1 = _quote(pd_b, vendors[0], D("18"))
    vq_b2, _      = _quote(pd_b, vendors[1], D("14"))
    cs_b = _build_cs(
        pd_b, selected_vq=vq_b1,
        justification="Vendor offers 3-day expedited delivery vs. 10-day lead time "
                       "from the lower bidder; production schedule requires faster receipt.",
        approve=True,
    )
    po_b = _convert_to_po(pd_b, cs_b, vendors[0], stock_products[1], D("18"), amt_b1)
    po_b.status = "approved"; s.add(po_b)
    s.flush()
    _gate_inward(po_b, _demand_line(pd_b).qty,
                gate_date=_due_date(po_b.order_date, 6), vehicle_no="LEB-5582", challan_no="CH-2202")
    _flat_bill(po_b, _demand_line(pd_b).qty, bill_date=_clamp_to_today(_due_date(po_b.order_date, 7)))
    # full receipt + billed — clean, matched 3-way-match row

    # CS-C: quotations gathered, winner selected via the matrix, approval still pending
    _quote(pd_c, vendors[0], D("22"))
    vq_c2, _ = _quote(pd_c, vendors[1], D("19"))
    _build_cs(pd_c, selected_vq=vq_c2, justification=None, approve=False)

    # PO-C: bare (pre-chain) PO, short-received but billed for the full ordered
    # qty — a genuine 3-way-match variance (received < ordered, billed = ordered).
    po_c_dates = _spread_dates(1, days_ago=90, min_days_ago=60)
    po_c = _bare_po(vendors[0], stock_products[0], D("40"), D("25"), po_c_dates[0])
    po_c.status = "approved"; s.add(po_c)
    s.flush()
    _gate_inward(po_c, D("30"), gate_date=_clamp_to_today(_due_date(po_c.order_date, 5)),
                vehicle_no="LEB-6693", challan_no="CH-2203")
    _flat_bill(po_c, D("40"), bill_date=_clamp_to_today(_due_date(po_c.order_date, 6)))

    # PO-D: bare PO, a Gate Inward recorded with the wrong details is cancelled
    # (append-only, reason required), then re-entered correctly — demonstrates
    # the cancel-with-reason state; left "received", not yet billed.
    po_d_dates = _spread_dates(1, days_ago=45, min_days_ago=20)
    po_d = _bare_po(vendors[1], stock_products[1], D("25"), D("30"), po_d_dates[0])
    po_d.status = "approved"; s.add(po_d)
    s.flush()
    gi_d1 = _gate_inward(po_d, D("25"), gate_date=_due_date(po_d.order_date, 4),
                         vehicle_no="LEB-0001", challan_no="CH-9001")
    gi_d1.status = "cancelled"
    gi_d1.cancel_reason = "Wrong vehicle number logged at the gate — re-entering with correct details."
    s.add(gi_d1)
    po_d.status = "approved"; s.add(po_d)  # coverage dropped to zero — reverts from "received"
    s.flush()
    _gate_inward(po_d, D("25"), gate_date=_due_date(po_d.order_date, 4),
                vehicle_no="LEB-7784", challan_no="CH-2204")

    # ── Gate Outward: invoice memo exits (recent activity gated; older backlog isn't,
    #    for dispatch-reconciliation to have something real to flag) ──
    stock_invoices = []
    for inv in invoices:
        lines = s.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)).all()
        if any(l.product_id for l in lines):
            stock_invoices.append((inv, lines))
    for i, (inv, lines) in enumerate(stock_invoices[-10:]):
        go_number = next_number(s, tid, "gate_outward", "GO", fmt="{prefix}-{YYYY}-{seq:04d}")
        go = GateOutward(
            tenant_id=tid, number=go_number, source_doc_type="invoice", source_doc_id=inv.id,
            gate_date=_due_date(inv.issue_date, 1), time_out="14:00",
            vehicle_no=f"LEB-{7100 + i}", challan_no=f"CH-OUT-{3100 + i}",
            status="approved", created_by_id=clerk.id,
        )
        s.add(go); s.flush()
        for l in lines:
            if l.product_id:
                s.add(GateOutwardLine(gate_outward_id=go.id, product_id=l.product_id, qty=D(l.qty)))
    s.flush()

    # ── Gate Outward: one debit-note (purchase return) memo exit ──
    first_dn = s.exec(select(DebitNote).where(DebitNote.tenant_id == tid)).first()
    if first_dn:
        dn_lines = s.exec(select(DebitNoteLine).where(DebitNoteLine.debit_note_id == first_dn.id)).all()
        if dn_lines:
            go_number = next_number(s, tid, "gate_outward", "GO", fmt="{prefix}-{YYYY}-{seq:04d}")
            go = GateOutward(
                tenant_id=tid, number=go_number, source_doc_type="debit_note",
                source_doc_id=first_dn.id, gate_date=_due_date(first_dn.issue_date, 1),
                time_out="11:15", vehicle_no="LEB-8820", challan_no="CH-OUT-4001",
                status="approved", created_by_id=clerk.id,
            )
            s.add(go); s.flush()
            for l in dn_lines:
                if l.product_id:
                    s.add(GateOutwardLine(gate_outward_id=go.id, product_id=l.product_id, qty=D(l.qty)))
            s.flush()

    # ── Gate Outward: scrap left in draft — shows the pending-approval UI state ──
    scrap_product = stock_products[2]
    go_draft_number = next_number(s, tid, "gate_outward", "GO", fmt="{prefix}-{YYYY}-{seq:04d}")
    go_draft = GateOutward(
        tenant_id=tid, number=go_draft_number, source_doc_type="scrap",
        gate_date=_past_days(8), time_out="16:30",
        vehicle_no="LEB-9931", remarks="Off-cuts from cutting floor, awaiting approval",
        status="draft", created_by_id=clerk.id,
    )
    s.add(go_draft); s.flush()
    s.add(GateOutwardLine(
        gate_outward_id=go_draft.id, product_id=scrap_product.id,
        qty=D("5"), unit_cost=D(scrap_product.avg_cost or 0), unit_value=D("0"),
    ))
    s.flush()

    # ── Gate Outward: scrap approved — the one path that posts real GL ──
    go_appr_number = next_number(s, tid, "gate_outward", "GO", fmt="{prefix}-{YYYY}-{seq:04d}")
    go_appr = GateOutward(
        tenant_id=tid, number=go_appr_number, source_doc_type="scrap",
        gate_date=_past_days(5), time_out="17:00",
        vehicle_no="LEB-9942", remarks="Fabric scrap sold to recycler",
        status="draft", created_by_id=clerk.id,
    )
    s.add(go_appr); s.flush()
    scrap_qty, scrap_unit_cost, scrap_unit_value = D("8"), D(scrap_product.avg_cost or 10), D("3")
    s.add(GateOutwardLine(
        gate_outward_id=go_appr.id, product_id=scrap_product.id,
        qty=scrap_qty, unit_cost=scrap_unit_cost, unit_value=scrap_unit_value,
    ))
    s.flush()

    total_cost = consume_stock(
        s, tenant_id=tid, product_id=scrap_product.id, qty=scrap_qty,
        source_doc_id=go_appr.id, source_doc_type="gate_outward",
    )
    total_value = money(scrap_qty * scrap_unit_value)
    if total_value > 0:
        cash_acc = get_or_create_account(s, tid, "1000", "Cash in Hand", "Asset")
        scrap_rev_acc = get_or_create_account(s, tid, "4902", "Scrap Sales", "Revenue")
        post_transaction(
            s, owner, date=go_appr.gate_date, description=f"Scrap sale proceeds — {go_appr.number}",
            entries=[
                EntryInput(account_id=cash_acc.id, debit=total_value),
                EntryInput(account_id=scrap_rev_acc.id, credit=total_value),
            ],
            voucher_type="JV", audit_entity_type="gate_outward",
            audit_detail={"go_number": go_appr.number, "leg": "scrap_revenue"},
        )
    if total_cost > 0:
        scrap_exp_acc = get_or_create_account(s, tid, "5901", "Scrap Disposal Expense", "Expense")
        inv_acc = get_or_create_account(s, tid, "1200", "Inventory (Raw Material)", "Asset")
        post_transaction(
            s, owner, date=go_appr.gate_date, description=f"Scrap disposal cost — {go_appr.number}",
            entries=[
                EntryInput(account_id=scrap_exp_acc.id, debit=total_cost),
                EntryInput(account_id=inv_acc.id, credit=total_cost),
            ],
            voucher_type="JV", audit_entity_type="gate_outward",
            audit_detail={"go_number": go_appr.number, "leg": "scrap_cost"},
        )
    go_appr.status = "approved"; go_appr.approved_by_id = owner.id
    go_appr.approved_at = datetime.utcnow()
    s.add(go_appr)
    s.flush()


def _seed_store_issues(
    s: Session, owner: User, clerk: User, products: list[Product],
) -> None:
    """Store Issues (#137 Phase 4) — departmental consumption for the
    manufacturing demo. Own idempotency (StoreIssue rows), so re-runs still
    backfill when the purchase-demand chain already exists — the previous
    early-return on PurchaseDemand left Issue Register empty forever.
    Seeds 60 rows (one page over the Issue Register's 50/page default)."""
    tid = owner.tenant_id
    if s.exec(select(StoreIssue).where(StoreIssue.tenant_id == tid)).first():
        return
    stock_products = [p for p in products if p.product_type == "stock"]
    if not stock_products:
        return
    own_location = s.exec(
        select(StockLocation).where(StockLocation.tenant_id == tid, StockLocation.type == "own")
    ).first()
    if not own_location:
        return

    expense_acct = get_or_create_account(s, tid, "5100", "Office Supplies Expense", "Expense")
    maint_acct = get_or_create_account(s, tid, "5150", "Maintenance Expense", "Expense")
    cost_centers = s.exec(
        select(AnalyticAccount).where(AnalyticAccount.tenant_id == tid)
    ).all()
    si_count = 60
    issue_dates = _spread_dates(si_count, min_days_ago=5)
    accts_cycle = [expense_acct, maint_acct]
    chosen_products = random.choices(stock_products, k=si_count)
    for i, product in enumerate(chosen_products):
        acct = accts_cycle[i % len(accts_cycle)]
        si_number = next_number(s, tid, "store_issue", "SI", fmt="{prefix}-{YYYY}-{seq:04d}")
        si = StoreIssue(
            tenant_id=tid, number=si_number, issue_date=issue_dates[i],
            from_location_id=own_location.id, debit_account_id=acct.id,
            analytic_account_id=cost_centers[i % len(cost_centers)].id if cost_centers else None,
            notes=f"Demo store issue #{i + 1}", created_by_id=clerk.id,
        )
        s.add(si); s.flush()
        qty = D(random.randint(2, 8))
        cost = consume_stock(
            s, tenant_id=tid, product_id=product.id, qty=qty,
            source_doc_id=si.id, source_doc_type="store_issue",
        )
        s.add(StoreIssueLine(
            store_issue_id=si.id, product_id=product.id, qty=qty,
            unit_cost=money(cost / qty) if qty else D("0"),
        ))
        if cost > 0:
            inv_acct = get_or_create_account(s, tid, "1200", "Inventory (Raw Material)", "Asset")
            txn = post_transaction(
                s, owner, date=issue_dates[i], description=f"Store issue — {si_number}",
                entries=[
                    EntryInput(account_id=acct.id, debit=money(cost),
                               analytic_account_id=si.analytic_account_id),
                    EntryInput(account_id=inv_acct.id, credit=money(cost)),
                ],
                voucher_type="JV", audit_entity_type="store_issue",
                audit_detail={"si_number": si_number},
            )
            si.transaction_id = txn.id
        s.flush()


# ── Telecom-franchise-specific ─────────────────────────────────────────────────


def _seed_telecom_franchise(s: Session, user: User) -> None:
    """Seed a full daily-operations slice: operator, tracker, load chain, RSO
    collections, SIM batch + activations, FCA events + target, and a franchise
    agreement with amortisation. Idempotent — core skips if an operator exists;
    extended screens (MM / devices / postpaid / …) backfill independently."""
    tid = user.tenant_id
    if s.exec(select(Operator).where(Operator.tenant_id == tid)).first():
        _seed_telecom_extended(s, user)
        return

    def acc_id(code: str) -> Optional[int]:
        a = _account(s, tid, code)
        return a.id if a else None

    today = date.today()
    span = _seed_span_days(today)
    # Open near the start of the 2-year window so subsequent ops fill the span.
    setup_day = _past_days(span - 5, today=today)

    op = Operator(
        tenant_id=tid, name="Jazz", operator_code="JAZZ",
        contact_person="Franchise Desk", contact_phone="0300-1112223",
        commission_settlement_cycle="monthly",
        deposit_account_id=acc_id("1210"), load_account_id=acc_id("1211"),
        payable_account_id=acc_id("2010"), commission_account_id=acc_id("4020"),
    )
    s.add(op); s.flush()

    ta = TrackerAccount(tenant_id=tid, operator_id=op.id, account_number="3001234567")
    s.add(ta); s.flush()
    post_tracker_deposit(s, user, tracker_account=ta, amount=D("500000"),
                         date=setup_day, reference="Opening deposit")
    post_load_order(s, user, tracker_account=ta, cash_debit=D("300000"),
                    uplift_pct=D("3.00"), date=setup_day, reference="Initial load")
    s.flush()

    batch, _ = post_stock_debit(
        s, user, tracker_account=ta, inventory_account_code="1200",
        qty=200, unit_cost=D("50"), date=setup_day, batch_number="SIMB-0001",
    )
    s.flush()

    rsos: list[RsoAgent] = []
    for name, terr in [("Imran Khan", "North Zone"), ("Sana Malik", "Central Zone"),
                        ("Bilal Ahmed", "South Zone")]:
        r = RsoAgent(tenant_id=tid, name=name, territory=terr,
                     receivable_account_id=acc_id("1120"))
        s.add(r); s.flush()
        rsos.append(r)
    outlets: list[RetailOutlet] = []
    for i, r in enumerate(rsos):
        o = RetailOutlet(tenant_id=tid, rso_id=r.id,
                         shop_name=f"{r.territory} Mobile Point",
                         owner_name=f"Owner {i+1}")
        s.add(o); s.flush()
        outlets.append(o)

    for r in rsos:
        post_msr_to_rso_transfer(
            s, user, tracker_account=ta, rso=r, amount=D("50000"),
            date=_past_days(int(span * 280 / 340), today=today),
        )
    s.flush()
    post_rso_to_retail_transfer(
        s, user, rso=rsos[0], retail_outlet_id=outlets[0].id,
        amount=D("20000"), date=_past_days(int(span * 270 / 340), today=today),
    )
    s.flush()

    if batch is not None:
        for i, r in enumerate(rsos):
            post_rso_sim_issue(
                s, user, rso=r, batch=batch, qty=20,
                retail_price=D("80"),
                date=_past_days(int(span * (250 - i) / 340), today=today),
            )
            batch.qty_activated += 20
        s.add(batch)
    s.flush()

    for i, r in enumerate(rsos):
        post_rso_daily_collection(
            s, user, rso=r, load_portion=D("30000"), stock_portion=D("1500"),
            total_deposited=D("31500"),
            date=_past_days(int(span * (200 - i) / 340), today=today),
        )
    s.flush()

    activations: list[SimActivation] = []
    for i in range(50):
        act = SimActivation(
            tenant_id=tid, operator_id=op.id,
            sim_number=f"0300{1000000 + i:07d}",
            batch_id=batch.id if batch else None,
            activation_date=_past_days(int(span * (300 - i * 6) / 340), today=today),
            customer_name=f"Customer {i+1}",
            activation_type="prepaid" if i % 3 != 0 else "postpaid",
            status="active", commission_rate=D("150"),
            commission_status="pending",
        )
        s.add(act); s.flush()
        activations.append(act)
    for act in activations[:25]:
        post_commission_accrual(
            s, user, activation=act, amount=D("150"),
            date=act.activation_date, revenue_account_code="4020",
        )
    s.flush()

    month = today.strftime("%Y-%m")
    target = KpiTarget(
        tenant_id=tid, operator_id=op.id,
        target_month=f"{month}-01",
        metric="fca", target_value=D("60"),
    )
    s.add(target); s.flush()
    for i in range(50):
        day = min((i % 28) + 1, today.day if today.day > 0 else 1)
        s.add(FcaEvent(
            tenant_id=tid, msisdn=f"0301{2000000 + i:07d}",
            event_date=f"{month}-{day:02d}", source_channel="rso_retail",
            kpi_target_id=target.id,
        ))
    s.flush()
    post_fca_target_commission(
        s, user, tracker_account=ta, amount=D("12000"),
        date=(today - timedelta(days=30)).isoformat(), credit_to="tracker",
    )
    s.flush()

    ag = FranchiseAgreement(
        tenant_id=tid, operator_id=op.id, agreement_number="FA-2024-JAZZ",
        start_date=setup_day, franchise_fee_paid=D("600000"),
        royalty_rate_pct=D("5"), min_monthly_target=D("250000"),
        penalty_rate_pct=D("2"), amortisation_months=60,
        intangible_account_id=acc_id("1300"),
        amortisation_account_id=acc_id("5030"),
    )
    s.add(ag); s.flush()
    post_franchise_fee_capitalisation(s, user, agreement=ag, fee=D("600000"),
                                      date=setup_day)
    post_franchise_fee_amortisation(
        s, user, agreement=ag,
        date=(today - timedelta(days=30)).isoformat(),
    )
    s.flush()

    # Extended screens (MM / devices / postpaid / airtime / commissions /
    # RSO targets) are backfillable on their own guards — see below.
    _seed_telecom_extended(s, user)


def _seed_telecom_extended(s: Session, user: User) -> None:
    """Fill every Telecom nav leaf that the core franchise seeder leaves empty.
    Each block is independently idempotent so re-runs backfill without
    requiring an Operator purge."""
    tid = user.tenant_id
    op = s.exec(select(Operator).where(Operator.tenant_id == tid)).first()
    if not op:
        return

    def acc_id(code: str) -> Optional[int]:
        a = _account(s, tid, code)
        return a.id if a else None

    today = date.today()
    span = _seed_span_days(today)
    rsos = s.exec(select(RsoAgent).where(RsoAgent.tenant_id == tid)).all()
    devices = s.exec(
        select(Product).where(
            Product.tenant_id == tid,
            Product.product_type == "stock",
            Product.code.in_(["ROUTER-4G", "ROUTER-5G", "MIFI", "DONGLE-USB"]),  # type: ignore[attr-defined]
        )
    ).all()
    if not devices:
        devices = s.exec(
            select(Product).where(Product.tenant_id == tid, Product.product_type == "stock")
        ).all()

    # ── Mobile Money (JazzCash + EasyPaisa) ───────────────────────────────────
    if not s.exec(select(MobileMoneyAccount).where(MobileMoneyAccount.tenant_id == tid)).first():
        mm_specs = [
            ("03001234567", "jazzcash"),
            ("03451234567", "easypaisa"),
        ]
        for acct_no, acct_type in mm_specs:
            mm = MobileMoneyAccount(
                tenant_id=tid, operator_id=op.id, account_number=acct_no,
                account_type=acct_type,
                float_asset_account_id=acc_id("1214"),
                float_liability_account_id=acc_id("2100"),
                commission_account_id=acc_id("4022"),
                current_float_balance=ZERO,
            )
            s.add(mm); s.flush()
            top_up_day = _past_days(int(span * 0.85), today=today)
            post_mm_float_top_up(
                s, user, mm_account=mm, amount=D("150000"), date=top_up_day,
            )
            for i in range(8):
                post_mm_customer_deposit(
                    s, user, mm_account=mm, amount=D(str(2000 + i * 250)),
                    date=_past_days(int(span * (0.7 - i * 0.05)), today=today),
                    customer_reference=f"CUST-{acct_type[:2].upper()}-{i + 1}",
                )
            post_mm_commission_credit(
                s, user, mm_account=mm, amount=D("3500"),
                date=_past_days(20, today=today),
            )
        s.flush()

    # ── Device IMEI tracking ──────────────────────────────────────────────────
    if devices and not s.exec(select(DeviceImei).where(DeviceImei.tenant_id == tid)).first():
        statuses = ["in_stock", "in_stock", "sold", "sold", "demo", "returned"]
        for i in range(30):
            prod = devices[i % len(devices)]
            status = statuses[i % len(statuses)]
            sale_date = _past_days(int(span * (0.4 - (i % 10) * 0.02)), today=today) if status == "sold" else None
            s.add(DeviceImei(
                tenant_id=tid, product_id=prod.id,
                imei_number=f"35{1000000000000 + i:013d}"[:15],
                serial_number=f"SN-{prod.code}-{i + 1:03d}",
                status=status, sale_date=sale_date,
            ))
        s.flush()

    # ── Postpaid connections + bill cycles ────────────────────────────────────
    if not s.exec(select(PostpaidConnection).where(PostpaidConnection.tenant_id == tid)).first():
        plans = [
            ("Postpaid Basic", D("1500"), D("8")),
            ("Postpaid Pro", D("3500"), D("10")),
            ("Postpaid Family", D("5500"), D("12")),
        ]
        connections: list[PostpaidConnection] = []
        for i in range(12):
            plan_name, rental, rate = plans[i % len(plans)]
            conn = PostpaidConnection(
                tenant_id=tid, operator_id=op.id,
                msisdn=f"0321{3000000 + i:07d}",
                customer_name=f"Postpaid Customer {i + 1}",
                customer_cnic=f"35201{1000000 + i:07d}",
                plan_name=plan_name, monthly_rental=rental,
                activation_date=_past_days(int(span * (0.9 - i * 0.05)), today=today),
                status="active" if i < 10 else "suspended",
                franchise_commission_rate=rate,
                last_billed_date=(today.replace(day=1) - timedelta(days=1)).isoformat(),
            )
            s.add(conn); s.flush()
            connections.append(conn)
        month_start = today.replace(day=1).isoformat()
        prev_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
        for conn in connections:
            for billing_month, collected in ((prev_month, True), (month_start, False)):
                commission = money(D(conn.monthly_rental) * D(conn.franchise_commission_rate) / D("100"))
                remittance = money(D(conn.monthly_rental) - commission)
                s.add(PostpaidBillCycle(
                    tenant_id=tid, connection_id=conn.id,
                    billing_month=billing_month,
                    gross_amount=conn.monthly_rental,
                    franchise_commission=commission,
                    net_remittance=remittance,
                    collection_status="collected" if collected else "pending",
                    remittance_status="remitted" if collected else "pending",
                ))
        s.flush()

    # ── Airtime / scratch-card stock + sales ──────────────────────────────────
    if not s.exec(select(AirtimeStock).where(AirtimeStock.tenant_id == tid)).first():
        stocks: list[AirtimeStock] = []
        for denom, qty, cost in ((D("100"), 200, D("92")), (D("500"), 80, D("460")), (D("1000"), 40, D("920"))):
            st = AirtimeStock(
                tenant_id=tid, operator_id=op.id, stock_type="scratch_card",
                denomination=denom, qty_received=qty, qty_sold=0,
                unit_cost=cost,
                purchase_date=_past_days(int(span * 0.6), today=today),
            )
            s.add(st); s.flush()
            stocks.append(st)
        for i, st in enumerate(stocks):
            sold = min(12, st.qty_received // 4)
            st.qty_sold = sold
            s.add(st)
            face = st.denomination
            sale_price = money(face * D("1.05"))
            s.add(AirtimeSale(
                tenant_id=tid, stock_id=st.id,
                sale_date=_past_days(10 + i * 3, today=today),
                qty=sold, face_value=money(face * D(sold)),
                sale_price=money(sale_price * D(sold)),
                margin=money((sale_price - st.unit_cost) * D(sold)),
                channel="rso" if rsos and i % 2 == 0 else "walk_in",
                rso_id=rsos[i % len(rsos)].id if rsos and i % 2 == 0 else None,
            ))
        s.flush()

    # ── Commission statements ─────────────────────────────────────────────────
    if not s.exec(select(CommissionStatement).where(CommissionStatement.tenant_id == tid)).first():
        period_to = today.replace(day=1) - timedelta(days=1)
        period_from = period_to.replace(day=1)
        stmt = CommissionStatement(
            tenant_id=tid, operator_id=op.id,
            statement_date=today.isoformat(),
            period_from=period_from.isoformat(),
            period_to=period_to.isoformat(),
            statement_reference="JAZZ-COMM-DEMO-01",
            total_commission=D("18500"),
            status="reconciled",
        )
        s.add(stmt); s.flush()
        for ctype, accrued, settled in (
            ("activation", D("7500"), D("7500")),
            ("recharge", D("4200"), D("4000")),
            ("load_uplift", D("3800"), D("3800")),
            ("fca_target", D("3000"), D("3000")),
        ):
            s.add(CommissionLine(
                tenant_id=tid, statement_id=stmt.id,
                commission_type=ctype,
                event_date=period_to.isoformat(),
                accrued_amount=accrued, settled_amount=settled,
                variance=money(accrued - settled),
                is_disputed=accrued != settled,
            ))
        s.flush()

    # ── RSO monthly targets ───────────────────────────────────────────────────
    if rsos and not s.exec(select(RsoTarget).where(RsoTarget.tenant_id == tid)).first():
        month = today.replace(day=1).isoformat()
        for i, rso in enumerate(rsos):
            target_act = 40 + i * 10
            actual_act = target_act - 5 + i * 3
            s.add(RsoTarget(
                tenant_id=tid, rso_id=rso.id, target_month=month,
                target_activations=target_act,
                target_recharge_value=D(str(80000 + i * 15000)),
                actual_activations=actual_act,
                actual_recharge_value=D(str(75000 + i * 12000)),
                incentive_earned=D("2500") if actual_act >= target_act else ZERO,
                penalty_applied=ZERO if actual_act >= target_act else D("500"),
            ))
        s.flush()



def _seed_credit_notes(s: Session, user: User, invoices: list, count: int = 6) -> None:
    """G-02: issue credit notes against a handful of posted invoices.
    Posts Dr Revenue / Cr AR — the reverse of an invoice."""
    tid = user.tenant_id
    if s.exec(select(CreditNote).where(CreditNote.tenant_id == tid)).first():
        return
    ar = _account(s, tid, "1100")
    rev = _account(s, tid, "4000")
    if not ar or not rev or not invoices:
        return

    # Credit a sample of invoices (returns / price adjustments)
    sample = [inv for inv in invoices if inv.customer_id][:count]
    reasons = [
        "Return — defective goods", "Price adjustment — discount agreed",
        "Short shipment credit", "Goods returned — wrong item",
        "Volume rebate", "Quality complaint settlement",
    ]
    cn_dates = _spread_dates(len(sample), min_days_ago=5)
    for i, inv in enumerate(sample):
        # Credit ~30% of the invoice subtotal
        amt = money(D(inv.subtotal) * D("0.30"))
        if amt <= ZERO:
            continue
        number = next_number(s, tid, "credit_note", "CN")
        cn = CreditNote(
            tenant_id=tid, number=number, invoice_id=inv.id,
            customer_id=inv.customer_id, customer_name=inv.customer_name,
            issue_date=cn_dates[i], description=reasons[i % len(reasons)],
            subtotal=amt, gst_amount=ZERO, total=amt,
            currency=inv.currency, exchange_rate=D(inv.exchange_rate),
            status="posted", ar_account_id=ar.id, revenue_account_id=rev.id,
        )
        s.add(cn); s.flush()
        s.add(CreditNoteLine(
            credit_note_id=cn.id, description=reasons[i % len(reasons)],
            qty=D(1), unit="ea", rate=amt, amount=amt,
        ))
        txn = post_transaction(
            s, user, date=cn_dates[i],
            description=f"Credit Note {number}",
            entries=[
                EntryInput(account_id=rev.id, debit=amt),
                EntryInput(account_id=ar.id, credit=amt),
            ],
            audit_entity_type="credit_note",
            audit_detail={"cn_number": number},
            voucher_type="CN",
        )
        cn.transaction_id = txn.id
        s.add(cn)


def _seed_fixed_assets(s: Session, user: User) -> None:
    """G-05: register fixed assets and post one month of depreciation each."""
    tid = user.tenant_id
    if s.exec(select(FixedAsset).where(FixedAsset.tenant_id == tid)).first():
        return
    asset_acc = _account(s, tid, "1010")   # bank stands in for the asset cost account
    accum = _account(s, tid, "1090")
    depr_exp = _account(s, tid, "5050")
    if not asset_acc or not accum or not depr_exp:
        return

    assets = [
        ("Office Laptops (fleet)", "FA-001", D(120000), D(0), 36),
        ("Delivery Vehicle",       "FA-002", D(2400000), D(200000), 60),
        ("Office Furniture",       "FA-003", D(350000), D(20000), 120),
        ("Production Machinery",   "FA-004", D(1800000), D(150000), 84),
    ]
    acq = _past_days(min(400, _seed_span_days() - 30))
    from services.depreciation import compute_depreciation
    for name, code, cost, salvage, life in assets:
        asset = FixedAsset(
            tenant_id=tid, name=name, code=code,
            asset_account_id=asset_acc.id, accum_depr_account_id=accum.id,
            depr_expense_account_id=depr_exp.id, acquisition_date=acq,
            acquisition_cost=cost, salvage_value=salvage,
            useful_life_months=life, method="straight_line",
            accumulated_depreciation=ZERO, book_value=cost,
        )
        s.add(asset); s.flush()
        # Post one month of depreciation
        charge = compute_depreciation(cost, salvage, life, ZERO, "straight_line")
        if charge <= ZERO:
            continue
        txn = post_transaction(
            s, user, date=date.today().isoformat(),
            description=f"Depreciation — {name}",
            entries=[
                EntryInput(account_id=depr_exp.id, debit=charge),
                EntryInput(account_id=accum.id, credit=charge),
            ],
            audit_entity_type="fixed_asset",
            audit_detail={"asset": code},
        )
        s.add(DepreciationEntry(
            tenant_id=tid, asset_id=asset.id,
            depreciation_date=date.today().isoformat(),
            depreciation_amount=charge, transaction_id=txn.id,
        ))
        asset.accumulated_depreciation = charge
        asset.book_value = money(cost - charge)
        asset.last_depreciation_date = date.today().isoformat()
        s.add(asset)


def _seed_budgets(s: Session, tenant_id: int) -> None:
    """G-10: monthly budgets for each expense account, current fiscal year."""
    if s.exec(select(Budget).where(Budget.tenant_id == tenant_id)).first():
        return
    year = date.today().year
    expense_accs = s.exec(
        select(Account).where(
            Account.tenant_id == tenant_id, Account.type == "Expense"
        )
    ).all()
    for acc in expense_accs:
        base = D(random.randint(5000, 40000))
        for month in range(1, 13):
            s.add(Budget(
                tenant_id=tenant_id, account_id=acc.id, fiscal_year=year,
                period_month=month, amount=money(base + D(month * 100)),
                label=f"Annual Budget {year}",
            ))


def _seed_purchase_orders(s: Session, user: User, vendors: list,
                          products: list, count: int = 8) -> None:
    """G-06: draft/approved purchase orders; convert a few to bills."""
    tid = user.tenant_id
    if s.exec(select(PurchaseOrder).where(PurchaseOrder.tenant_id == tid)).first():
        return
    if not vendors or not products:
        return
    ap = _account(s, tid, "2000")
    exp = _account(s, tid, "5000")
    if not ap or not exp:
        return

    po_dates = _spread_dates(count, min_days_ago=10)
    for i in range(count):
        vendor = vendors[i % len(vendors)]
        number = next_number(s, tid, "purchase_order", "PO")
        # 1–3 lines
        n_lines = random.randint(1, 3)
        lines = []
        subtotal = ZERO
        for _ in range(n_lines):
            p = random.choice(products)
            qty = D(random.randint(5, 50))
            rate = D(p.default_rate or random.randint(10, 200))
            amt = money(qty * rate)
            subtotal += amt
            lines.append((p, qty, rate, amt))
        # Half approved+billed, half left as draft/approved
        status = ["draft", "approved", "billed"][i % 3]
        po = PurchaseOrder(
            tenant_id=tid, number=number, vendor_id=vendor.id,
            vendor_name=vendor.name, order_date=po_dates[i],
            expected_date=_due_date(po_dates[i], 14),
            description=f"Procurement order from {vendor.name}",
            subtotal=money(subtotal), total=money(subtotal), status=status,
        )
        s.add(po); s.flush()
        for p, qty, rate, amt in lines:
            s.add(PurchaseOrderLine(
                po_id=po.id, product_id=p.id, description=p.name,
                qty=qty, unit=p.unit, rate=rate, amount=amt,
            ))
        # Convert "billed" POs to an actual bill + GL
        if status == "billed":
            bill_number = next_number(s, tid, "bill", "BILL")
            bill = Bill(
                tenant_id=tid, number=bill_number, vendor_id=vendor.id,
                vendor_name=vendor.name, bill_date=_clamp_to_today(_due_date(po_dates[i], 14)),
                due_date=_due_date(po_dates[i], 44),
                description=f"From PO {number}", subtotal=money(subtotal),
                gst_rate=ZERO, gst_amount=ZERO, total=money(subtotal),
                status="posted", ap_account_id=ap.id, expense_account_id=exp.id,
            )
            s.add(bill); s.flush()
            for p, qty, rate, amt in lines:
                s.add(BillLine(
                    bill_id=bill.id, product_id=p.id, description=p.name,
                    qty=qty, unit=p.unit, rate=rate, amount=amt,
                ))
            txn = post_transaction(
                s, user, date=bill.bill_date,
                description=f"Bill from PO {number}",
                entries=[
                    EntryInput(account_id=exp.id, debit=money(subtotal)),
                    EntryInput(account_id=ap.id, credit=money(subtotal)),
                ],
                audit_entity_type="bill",
                audit_detail={"bill_number": bill_number, "po_number": number},
            )
            bill.transaction_id = txn.id
            po.bill_id = bill.id
            s.add(bill); s.add(po)


def _seed_analytic_accounts(s: Session, tenant_id: int) -> None:
    """G-07: cost centers / projects / departments for segment reporting.
    Also back-fills ~30 % of seeded invoices, bills, payments, and JVs with
    analytic tags so Analytic P&L shows non-empty figures per tenant.
    """
    import random
    from models import Invoice, Bill, PaymentReceived, BillPayment, JournalEntry, Transaction

    # 1. Create the 7 dimensions (idempotent)
    existing = s.exec(select(AnalyticAccount).where(AnalyticAccount.tenant_id == tenant_id)).all()
    if not existing:
        dims = [
            ("CC-SALES", "Sales Department", "department"),
            ("CC-OPS",   "Operations",       "department"),
            ("CC-ADMIN", "Administration",   "department"),
            ("PRJ-A",    "Project Alpha",    "project"),
            ("PRJ-B",    "Project Beta",     "project"),
            ("CC-NORTH", "North Region",     "cost_center"),
            ("CC-SOUTH", "South Region",     "cost_center"),
        ]
        for code, name, typ in dims:
            s.add(AnalyticAccount(
                tenant_id=tenant_id, code=code, name=name, type=typ, is_active=True,
            ))
        s.flush()

    # 2. Load dimension IDs for tagging
    dim_ids = [
        a.id for a in s.exec(
            select(AnalyticAccount).where(AnalyticAccount.tenant_id == tenant_id)
        ).all()
    ]
    if not dim_ids:
        return

    rng = random.Random(tenant_id)  # deterministic per tenant

    # 3. Tag ~30 % of invoices + their JE rows
    invoices = s.exec(
        select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.analytic_account_id.is_(None))
    ).all()
    for inv in invoices:
        if rng.random() < 0.3:
            ana_id = rng.choice(dim_ids)
            inv.analytic_account_id = ana_id
            s.add(inv)
            # Propagate to JE rows so Analytic P&L picks them up
            if inv.transaction_id:
                for je in s.exec(
                    select(JournalEntry).where(JournalEntry.transaction_id == inv.transaction_id)
                ).all():
                    if je.analytic_account_id is None:
                        je.analytic_account_id = ana_id
                        s.add(je)

    # 4. Tag ~30 % of bills + their JE rows
    bills = s.exec(
        select(Bill).where(Bill.tenant_id == tenant_id, Bill.analytic_account_id.is_(None))
    ).all()
    for bill in bills:
        if rng.random() < 0.3:
            ana_id = rng.choice(dim_ids)
            bill.analytic_account_id = ana_id
            s.add(bill)
            if bill.transaction_id:
                for je in s.exec(
                    select(JournalEntry).where(JournalEntry.transaction_id == bill.transaction_id)
                ).all():
                    if je.analytic_account_id is None:
                        je.analytic_account_id = ana_id
                        s.add(je)

    # 5. Tag ~30 % of payments received + their JE rows
    payments = s.exec(
        select(PaymentReceived).where(
            PaymentReceived.tenant_id == tenant_id,
            PaymentReceived.analytic_account_id.is_(None),
        )
    ).all()
    for pmt in payments:
        if rng.random() < 0.3:
            ana_id = rng.choice(dim_ids)
            pmt.analytic_account_id = ana_id
            s.add(pmt)
            if pmt.transaction_id:
                for je in s.exec(
                    select(JournalEntry).where(JournalEntry.transaction_id == pmt.transaction_id)
                ).all():
                    if je.analytic_account_id is None:
                        je.analytic_account_id = ana_id
                        s.add(je)

    # 6. Tag ~30 % of bill payments + their JE rows
    bpayments = s.exec(
        select(BillPayment).where(
            BillPayment.tenant_id == tenant_id,
            BillPayment.analytic_account_id.is_(None),
        )
    ).all()
    for bp in bpayments:
        if rng.random() < 0.3:
            ana_id = rng.choice(dim_ids)
            bp.analytic_account_id = ana_id
            s.add(bp)
            if bp.transaction_id:
                for je in s.exec(
                    select(JournalEntry).where(JournalEntry.transaction_id == bp.transaction_id)
                ).all():
                    if je.analytic_account_id is None:
                        je.analytic_account_id = ana_id
                        s.add(je)

    # 7. Tag ~30 % of remaining manual JVs (not already tagged via invoice/bill/payment)
    # JVs linked to invoices/bills/payments were already handled above.
    tagged_txn_ids: set[int] = set()
    for inv in invoices:
        if inv.analytic_account_id is not None and inv.transaction_id:
            tagged_txn_ids.add(inv.transaction_id)
    for bill in bills:
        if bill.analytic_account_id is not None and bill.transaction_id:
            tagged_txn_ids.add(bill.transaction_id)
    for pmt in payments:
        if pmt.analytic_account_id is not None and pmt.transaction_id:
            tagged_txn_ids.add(pmt.transaction_id)
    for bp in bpayments:
        if bp.analytic_account_id is not None and bp.transaction_id:
            tagged_txn_ids.add(bp.transaction_id)

    jvs = s.exec(
        select(Transaction).where(Transaction.tenant_id == tenant_id)
    ).all()
    for txn in jvs:
        if txn.id in tagged_txn_ids:
            continue  # already tagged via document backfill above
        if rng.random() < 0.3:
            ana_id = rng.choice(dim_ids)
            for je in s.exec(
                select(JournalEntry).where(JournalEntry.transaction_id == txn.id)
            ).all():
                if je.analytic_account_id is None:
                    je.analytic_account_id = ana_id
                    s.add(je)

    s.flush()


def _seed_deferred_revenue(s: Session, user: User, invoices: list, count: int = 4) -> None:
    """G-08: recognise 1–2 periods for the deferred-revenue schedules that were
    originated by _seed_invoices (via the real #47 production path).  Schedules
    are already present in the DB (created by create_schedules inside the
    invoice loop).  We just advance recognised_amount for 2 periods so the
    demo shows meaningful progress.  Idempotent: skips if any schedule already
    has recognised_amount > 0."""
    tid = user.tenant_id
    scheds = s.exec(
        select(DeferredRevenueSchedule).where(
            DeferredRevenueSchedule.tenant_id == tid,
            DeferredRevenueSchedule.status == "active",
        )
    ).all()
    if not scheds:
        return
    # Skip if already partially recognised (re-run guard)
    if any(D(sc.recognised_amount) > ZERO for sc in scheds):
        return

    # Recognise 2 monthly periods for each schedule
    PERIODS = 2
    for sched in scheds:
        remaining = D(sched.total_amount) - D(sched.recognised_amount)
        if remaining <= ZERO:
            continue
        # Derive months from start/end dates (matches run_recognition logic)
        start_d = date.fromisoformat(sched.start_date)
        end_d   = date.fromisoformat(sched.end_date)
        months  = max(1, (end_d.year - start_d.year) * 12 + (end_d.month - start_d.month))
        per_month = money(D(sched.total_amount) / months)

        recognition_date = sched.start_date
        for _ in range(PERIODS):
            remaining = D(sched.total_amount) - D(sched.recognised_amount)
            if remaining <= ZERO:
                break
            charge = min(remaining, per_month)
            if charge <= ZERO:
                break
            # Never post recognition into the future (recent invoices' +1 month).
            rec_date = _clamp_to_today(recognition_date)
            post_transaction(
                s, user,
                date=rec_date,
                description=f"Deferred Revenue Recognition — Schedule {sched.id}",
                entries=[
                    EntryInput(account_id=sched.deferred_revenue_account_id, debit=charge),
                    EntryInput(account_id=sched.revenue_account_id, credit=charge),
                ],
                audit_entity_type="deferred_revenue",
                audit_detail={"schedule_id": sched.id, "charge": str(charge)},
            )
            sched.recognised_amount = money(D(sched.recognised_amount) + charge)
            recognition_date = _add_months(recognition_date, 1)

        if D(sched.recognised_amount) >= D(sched.total_amount):
            sched.status = "completed"
        else:
            sched.next_recognition_date = recognition_date
        s.add(sched)


# ── Returns & Advances (Sprint 13) ────────────────────────────────────────────


def _seed_sales_returns(s: Session, user: User, invoices: list, count: int = 4) -> None:
    """Credit-note a few invoices, restocking stock lines (sales return).

    Distinct from `_seed_credit_notes` (financial-only CNs) — guarded by the
    'Sales return' description so both coexist idempotently.
    """
    tid = user.tenant_id
    if s.exec(
        select(CreditNote).where(
            CreditNote.tenant_id == tid, CreditNote.description == "Sales return"
        )
    ).first():
        return
    ar = _account(s, tid, "1100")
    rev = _account(s, tid, "4000")
    inv_acc = _account(s, tid, "1200") or _account(s, tid, "1202")
    cogs_acc = _account(s, tid, "5010")
    if not ar or not rev or not invoices:
        return

    sample = [inv for inv in invoices if inv.customer_id][:count]
    for inv in sample:
        lines = s.exec(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)).all()
        if not lines:
            continue
        ln = lines[0]
        ret_qty = D(ln.qty) / D(2) if D(ln.qty) >= 2 else D(ln.qty)
        if ret_qty <= 0:
            continue
        amt = money(ret_qty * D(ln.rate))
        number = next_number(s, tid, "credit_note", "CN")
        cn = CreditNote(
            tenant_id=tid, number=number, invoice_id=inv.id, customer_id=inv.customer_id,
            customer_name=inv.customer_name, issue_date=inv.issue_date,
            description="Sales return", subtotal=amt, gst_amount=ZERO, total=amt,
            currency=inv.currency, exchange_rate=D(inv.exchange_rate), status="posted",
            ar_account_id=ar.id, revenue_account_id=rev.id,
        )
        s.add(cn); s.flush()
        s.add(CreditNoteLine(
            credit_note_id=cn.id, product_id=ln.product_id, description=ln.description,
            qty=ret_qty, unit=ln.unit, rate=D(ln.rate), amount=amt,
        ))
        txn = post_transaction(
            s, user, date=inv.issue_date, description=f"Credit Note {number}",
            entries=[
                EntryInput(account_id=rev.id, debit=amt),
                EntryInput(account_id=ar.id, credit=amt),
            ],
            audit_entity_type="credit_note", audit_detail={"cn_number": number},
        )
        cn.transaction_id = txn.id
        s.add(cn)
        # Restock if the line is a stock product
        if ln.product_id and inv_acc and cogs_acc:
            prod = s.get(Product, ln.product_id)
            if prod and prod.product_type == "stock":
                cogs = money(ret_qty * D(prod.avg_cost))
                if cogs > ZERO:
                    reverse_consumption(s, tenant_id=tid, product_id=ln.product_id,
                                        qty=ret_qty, cogs_total=cogs)
                    post_transaction(
                        s, user, date=inv.issue_date,
                        description=f"Sales return restock for {number}",
                        entries=[
                            EntryInput(account_id=inv_acc.id, debit=cogs),
                            EntryInput(account_id=cogs_acc.id, credit=cogs),
                        ],
                        audit_entity_type="credit_note",
                        audit_detail={"cn_number": number, "cogs": str(cogs)},
                    )


def _seed_purchase_returns(s: Session, user: User, bills: list, count: int = 3) -> None:
    """Debit-note a few stock bills (purchase return at original cost)."""
    tid = user.tenant_id
    if s.exec(select(DebitNote).where(DebitNote.tenant_id == tid)).first():
        return
    ap = _account(s, tid, "2000")
    inv_acc = _account(s, tid, "1200") or _account(s, tid, "1202")
    if not ap or not inv_acc or not bills:
        return

    done = 0
    for bill in bills:
        if done >= count:
            break
        lines = s.exec(select(BillLine).where(BillLine.bill_id == bill.id)).all()
        stock_lines = []
        for ln in lines:
            if ln.product_id:
                prod = s.get(Product, ln.product_id)
                if prod and prod.product_type == "stock":
                    stock_lines.append((ln, prod))
        if not stock_lines:
            continue

        ln, prod = stock_lines[0]
        ret_qty = D(ln.qty) / D(4) if D(ln.qty) >= 4 else D(1)
        try:
            cost_removed = return_to_vendor(
                s, tenant_id=tid, product_id=ln.product_id, qty=ret_qty,
                source_doc=bill.number,
            )
        except InventoryError:
            continue
        if cost_removed <= ZERO:
            continue
        number = next_number(s, tid, "debit_note", "DN")
        dn = DebitNote(
            tenant_id=tid, number=number, bill_id=bill.id, vendor_id=bill.vendor_id,
            vendor_name=bill.vendor_name, issue_date=bill.bill_date,
            description="Purchase return", subtotal=cost_removed, gst_amount=ZERO,
            total=cost_removed, currency="USD", exchange_rate=D(1), status="posted",
            ap_account_id=ap.id,
        )
        s.add(dn); s.flush()
        s.add(DebitNoteLine(
            debit_note_id=dn.id, product_id=ln.product_id, description=ln.description,
            qty=ret_qty, unit=ln.unit, rate=D(ln.rate), amount=cost_removed,
        ))
        txn = post_transaction(
            s, user, date=bill.bill_date,
            description=f"Debit Note {number} (return vs {bill.number})",
            entries=[
                EntryInput(account_id=ap.id, debit=cost_removed),
                EntryInput(account_id=inv_acc.id, credit=cost_removed),
            ],
            audit_entity_type="debit_note", audit_detail={"dn_number": number},
            voucher_type="DN",
        )
        dn.transaction_id = txn.id
        s.add(dn)
        done += 1


def _seed_customer_advances(s: Session, user: User, customers: list, invoices: list,
                            count: int = 4) -> None:
    """Record customer advances; partially apply some to invoices."""
    tid = user.tenant_id
    if s.exec(select(CustomerAdvance).where(CustomerAdvance.tenant_id == tid)).first():
        return
    bank = _account(s, tid, "1011") or _account(s, tid, "1010") or _account(s, tid, "1000")
    adv_acc = _account(s, tid, "2310")
    ar = _account(s, tid, "1100")
    if not bank or not adv_acc or not customers:
        return

    adv_dates = _spread_dates(count, min_days_ago=10)
    open_invoices = [i for i in invoices if i.customer_id]
    for idx in range(min(count, len(customers))):
        cust = customers[idx]
        amount = money(D(random.randint(500, 3000)))
        number = next_number(s, tid, "customer_advance", "CADV")
        txn = post_transaction(
            s, user, date=adv_dates[idx],
            description=f"Customer advance {number} — {cust.name}",
            entries=[
                EntryInput(account_id=bank.id, debit=amount),
                EntryInput(account_id=adv_acc.id, credit=amount),
            ],
            audit_entity_type="customer_advance", audit_detail={"number": number},
        )
        adv = CustomerAdvance(
            tenant_id=tid, number=number, customer_id=cust.id, date=adv_dates[idx],
            amount=amount, applied_amount=ZERO, cash_account_id=bank.id,
            advance_account_id=adv_acc.id, transaction_id=txn.id, status="open",
        )
        s.add(adv); s.flush()
        # Apply ~half to one of this customer's invoices, if any
        target = next((i for i in open_invoices if i.customer_id == cust.id), None)
        if target and ar:
            apply_amt = money(min(amount / D(2), D(target.total)))
            if apply_amt > ZERO:
                ptxn = post_transaction(
                    s, user, date=target.issue_date,
                    description=f"Apply advance {number} to {target.number}",
                    entries=[
                        EntryInput(account_id=adv_acc.id, debit=apply_amt),
                        EntryInput(account_id=ar.id, credit=apply_amt),
                    ],
                    audit_entity_type="payment_received",
                    audit_detail={"advance": number, "invoice": target.number},
                )
                pmt = PaymentReceived(
                    tenant_id=tid, invoice_id=target.id, customer_name=target.customer_name,
                    payment_date=target.issue_date, amount=apply_amt, method="advance",
                    reference=number, cash_account_id=adv_acc.id, transaction_id=ptxn.id,
                )
                s.add(pmt); s.flush()
                s.add(PaymentAllocation(
                    tenant_id=tid, payment_received_id=pmt.id, invoice_id=target.id,
                    amount=apply_amt,
                ))
                adv.applied_amount = apply_amt
                adv.status = "partial"
                s.add(adv)


def _seed_vendor_advances(s: Session, user: User, vendors: list, bills: list,
                          count: int = 4) -> None:
    """Record vendor advances; partially apply some to bills."""
    tid = user.tenant_id
    if s.exec(select(VendorAdvance).where(VendorAdvance.tenant_id == tid)).first():
        return
    bank = _account(s, tid, "1011") or _account(s, tid, "1010") or _account(s, tid, "1000")
    adv_acc = _account(s, tid, "1260")
    ap = _account(s, tid, "2000")
    if not bank or not adv_acc or not vendors:
        return

    adv_dates = _spread_dates(count, min_days_ago=10)
    for idx in range(min(count, len(vendors))):
        vendor = vendors[idx]
        amount = money(D(random.randint(500, 3000)))
        number = next_number(s, tid, "vendor_advance", "VADV")
        txn = post_transaction(
            s, user, date=adv_dates[idx],
            description=f"Vendor advance {number} — {vendor.name}",
            entries=[
                EntryInput(account_id=adv_acc.id, debit=amount),
                EntryInput(account_id=bank.id, credit=amount),
            ],
            audit_entity_type="vendor_advance", audit_detail={"number": number},
        )
        adv = VendorAdvance(
            tenant_id=tid, number=number, vendor_id=vendor.id, date=adv_dates[idx],
            amount=amount, applied_amount=ZERO, cash_account_id=bank.id,
            advance_account_id=adv_acc.id, transaction_id=txn.id, status="open",
        )
        s.add(adv); s.flush()
        target = next((b for b in bills if b.vendor_id == vendor.id), None)
        if target and ap:
            apply_amt = money(min(amount / D(2), D(target.total)))
            if apply_amt > ZERO:
                ptxn = post_transaction(
                    s, user, date=target.bill_date,
                    description=f"Apply advance {number} to {target.number}",
                    entries=[
                        EntryInput(account_id=ap.id, debit=apply_amt),
                        EntryInput(account_id=adv_acc.id, credit=apply_amt),
                    ],
                    audit_entity_type="bill_payment",
                    audit_detail={"advance": number, "bill": target.number},
                )
                pmt = BillPayment(
                    tenant_id=tid, bill_id=target.id, vendor_name=target.vendor_name,
                    payment_date=target.bill_date, amount=apply_amt, method="advance",
                    reference=number, cash_account_id=adv_acc.id, transaction_id=ptxn.id,
                )
                s.add(pmt); s.flush()
                s.add(PaymentAllocation(
                    tenant_id=tid, bill_payment_id=pmt.id, bill_id=target.id,
                    amount=apply_amt,
                ))
                adv.applied_amount = apply_amt
                adv.status = "partial"
                s.add(adv)


# ── HRM seed helpers ──────────────────────────────────────────────────────────

EMPLOYEE_NAMES = [
    ("Ahmed Ali",       "EMP-0001"),
    ("Sara Khan",       "EMP-0002"),
    ("Muhammad Raza",   "EMP-0003"),
    ("Fatima Malik",    "EMP-0004"),
    ("Usman Sheikh",    "EMP-0005"),
    ("Ayesha Qureshi",  "EMP-0006"),
    ("Bilal Ahmed",     "EMP-0007"),
    ("Zara Hussain",    "EMP-0008"),
    ("Tariq Mahmood",   "EMP-0009"),
    ("Nadia Iqbal",     "EMP-0010"),
    ("Imran Siddiqui",  "EMP-0011"),
    ("Hina Baig",       "EMP-0012"),
]

_DEPT_ROLES: dict[str, list[tuple[str, str]]] = {
    "simple": [
        ("Admin", "Office Administrator"),
        ("Admin", "Admin Assistant"),
        ("Sales", "Sales Executive"),
        ("Sales", "Sales Manager"),
        ("Finance", "Accountant"),
        ("Finance", "Finance Officer"),
        ("Admin", "Receptionist"),
        ("Sales", "Business Development Executive"),
    ],
    "services": [
        ("Consulting", "Senior Consultant"),
        ("Consulting", "Junior Consultant"),
        ("Project Management", "Project Manager"),
        ("Project Management", "Project Coordinator"),
        ("Finance", "Accountant"),
        ("IT Support", "IT Specialist"),
        ("Consulting", "Principal Consultant"),
        ("IT Support", "Systems Analyst"),
    ],
    "trader": [
        ("Warehouse", "Warehouse Supervisor"),
        ("Warehouse", "Warehouse Associate"),
        ("Procurement", "Procurement Officer"),
        ("Procurement", "Procurement Manager"),
        ("Sales", "Sales Executive"),
        ("Sales", "Account Manager"),
        ("Finance", "Accountant"),
        ("Warehouse", "Logistics Coordinator"),
    ],
    "manufacturing": [
        ("Production", "Production Supervisor"),
        ("Production", "Machine Operator"),
        ("Quality Control", "QC Inspector"),
        ("Engineering", "Process Engineer"),
        ("Warehouse", "Store Keeper"),
        ("Finance", "Accountant"),
        ("Production", "Line Leader"),
        ("Quality Control", "QA Manager"),
    ],
    "telecom_franchise": [
        ("Retail", "Retail Associate"),
        ("Retail", "Retail Supervisor"),
        ("Field Operations", "Field Technician"),
        ("Field Operations", "Field Operations Manager"),
        ("Finance", "Accountant"),
        ("Customer Service", "Customer Service Representative"),
        ("Retail", "Store Manager"),
        ("Customer Service", "Customer Service Manager"),
    ],
}

_SALARY_BANDS = [50_000, 65_000, 80_000, 100_000, 120_000, 150_000]

_STANDARD_COMPONENTS = [
    ("BASIC",   "Basic Salary",         "earnings",   True,  True),
    ("HRA",     "House Rent Allowance", "earnings",   True,  True),
    ("CONVEY",  "Conveyance Allowance", "earnings",   False, True),
    ("MEDICAL", "Medical Allowance",    "earnings",   False, True),
    ("EOBI",    "EOBI Deduction",       "deductions", False, True),
    ("TAX",     "Income Tax",           "deductions", True,  True),
]


def _seed_employees(s: Session, tenant_id: int, business_model: str) -> list:
    """Seed 8 realistic employees per tenant (idempotent)."""
    dept_roles = _DEPT_ROLES.get(business_model, _DEPT_ROLES["simple"])
    employees: list = []
    today = date.today()
    for i, (name, code) in enumerate(EMPLOYEE_NAMES):
        existing = s.exec(
            select(Employee).where(
                Employee.tenant_id == tenant_id,
                Employee.employee_code == code,
            )
        ).first()
        if existing:
            employees.append(existing)
            continue
        dept, designation = dept_roles[i % len(dept_roles)]
        # join date: spread across the 2-year seed window
        span = _seed_span_days(today)
        days_back = max(30, (i * 97) % max(span, 1))
        join_dt = today - timedelta(days=days_back)
        emp = Employee(
            tenant_id=tenant_id,
            employee_code=code,
            name=name,
            department=dept,
            designation=designation,
            join_date=join_dt.isoformat(),
            is_active=True,
        )
        s.add(emp)
        s.flush()
        employees.append(emp)
    return employees


def _seed_salary_components(s: Session, tenant_id: int) -> list:
    """Seed 6 standard salary components per tenant (idempotent)."""
    components: list = []
    for code, name, comp_type, is_taxable, is_fixed in _STANDARD_COMPONENTS:
        existing = s.exec(
            select(SalaryComponent).where(
                SalaryComponent.tenant_id == tenant_id,
                SalaryComponent.code == code,
            )
        ).first()
        if existing:
            components.append(existing)
            continue
        comp = SalaryComponent(
            tenant_id=tenant_id,
            code=code,
            name=name,
            component_type=comp_type,
            is_taxable=is_taxable,
            is_fixed=is_fixed,
            is_active=True,
        )
        s.add(comp)
        s.flush()
        components.append(comp)
    return components


def _seed_salary_structures(s: Session, employees: list, components: list) -> None:
    """Assign salary component amounts to each employee (idempotent)."""
    comp_by_code = {c.code: c for c in components}
    for idx, emp in enumerate(employees):
        basic = _SALARY_BANDS[idx % len(_SALARY_BANDS)]
        amounts = {
            "BASIC":   basic,
            "HRA":     round(basic * 0.4),
            "CONVEY":  5_000,
            "MEDICAL": 3_000,
            "EOBI":    round(basic * 0.05),
            "TAX":     round(basic * 0.08),
        }
        for code, amount in amounts.items():
            comp = comp_by_code.get(code)
            if not comp:
                continue
            existing = s.exec(
                select(EmployeeSalaryStructure).where(
                    EmployeeSalaryStructure.employee_id == emp.id,
                    EmployeeSalaryStructure.component_id == comp.id,
                )
            ).first()
            if existing:
                continue
            s.add(EmployeeSalaryStructure(
                employee_id=emp.id,
                component_id=comp.id,
                amount=float(amount),
            ))


def _seed_payroll_runs(
    s: Session, tenant_id: int, user, employees: list, components: list
) -> list:
    """Seed 3 monthly payroll runs (last 3 months) — idempotent."""
    today = date.today()
    runs: list = []
    jv_seq_start = 1

    for month_offset in range(3, 0, -1):  # 3, 2, 1 months ago → oldest first
        # Determine the target month
        target = today.replace(day=1) - timedelta(days=1)  # last day of previous month
        for _ in range(month_offset - 1):
            target = target.replace(day=1) - timedelta(days=1)
        period_end_dt = target
        period_start_dt = period_end_dt.replace(day=1)

        period_start = period_start_dt.isoformat()
        period_end   = period_end_dt.isoformat()

        existing = s.exec(
            select(PayrollRun).where(
                PayrollRun.tenant_id == tenant_id,
                PayrollRun.period_start == period_start,
            )
        ).first()
        if existing:
            runs.append(existing)
            jv_seq_start += 1
            continue

        # Most recent month = approved; two older months = posted with real GL entries
        is_most_recent = (month_offset == 1)

        run = PayrollRun(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            pay_date=period_end,
            status="approved",
            jv_number=None,
            transaction_id=None,
            created_by_id=user.id,
        )
        s.add(run)
        s.flush()

        # Build a quick lookup: employee_id → {comp_code: amount}
        comp_by_id = {c.id: c for c in components}
        emp_structures: dict[int, dict[str, float]] = {}
        for emp in employees:
            if not emp.is_active:
                continue
            structs = s.exec(
                select(EmployeeSalaryStructure).where(
                    EmployeeSalaryStructure.employee_id == emp.id
                )
            ).all()
            emp_structures[emp.id] = {
                comp_by_id[st.component_id].code: st.amount
                for st in structs
                if st.component_id in comp_by_id
            }

        for emp in employees:
            if not emp.is_active:
                continue
            struct = emp_structures.get(emp.id, {})
            gross = sum(
                v for k, v in struct.items()
                if any(
                    c.code == k and c.component_type == "earnings"
                    for c in components
                )
            )
            deductions = sum(
                v for k, v in struct.items()
                if any(
                    c.code == k and c.component_type == "deductions"
                    for c in components
                )
            )
            net = gross - deductions
            line = PayrollLine(
                payroll_run_id=run.id,
                employee_id=emp.id,
                gross_earnings=float(gross),
                total_deductions=float(deductions),
                net_pay=float(net),
            )
            s.add(line)
            s.flush()

            for comp in components:
                amount = struct.get(comp.code, 0.0)
                s.add(PayrollLineDetail(
                    payroll_line_id=line.id,
                    component_id=comp.id,
                    amount=float(amount),
                    is_override=False,
                ))

        s.flush()

        # Post real GL entry for older (non-most-recent) runs
        if not is_most_recent:
            all_lines = s.exec(
                select(PayrollLine).where(PayrollLine.payroll_run_id == run.id)
            ).all()
            total_gross = sum(l.gross_earnings for l in all_lines)
            total_net   = sum(l.net_pay for l in all_lines)
            total_ded   = sum(l.total_deductions for l in all_lines)

            expense_acct = s.exec(
                select(Account).where(Account.tenant_id == tenant_id, Account.code == "5100")
            ).first()
            payable_acct = s.exec(
                select(Account).where(Account.tenant_id == tenant_id, Account.code == "2250")
            ).first()

            if expense_acct and payable_acct and total_gross > 0:
                entries: list[EntryInput] = [
                    EntryInput(account_id=expense_acct.id, debit=float(total_gross), credit=0.0),
                    EntryInput(account_id=payable_acct.id, debit=0.0, credit=float(total_net)),
                ]
                if total_ded > 0:
                    entries.append(
                        EntryInput(account_id=payable_acct.id, debit=0.0, credit=float(total_ded))
                    )
                dr_sum = sum(e.debit for e in entries)
                cr_sum = sum(e.credit for e in entries)
                if abs(dr_sum - cr_sum) > 0.005:
                    diff = dr_sum - cr_sum
                    if diff > 0:
                        entries.append(EntryInput(account_id=payable_acct.id, debit=0.0, credit=diff))
                    else:
                        entries.append(EntryInput(account_id=expense_acct.id, debit=-diff, credit=0.0))
                txn = post_transaction(
                    s, user,
                    date=period_end,
                    description=f"Payroll — {period_start} to {period_end}",
                    voucher_type="JV",
                    entries=entries,
                    audit_detail={"payroll_run_id": run.id},
                )
                run.transaction_id = txn.id
                run.jv_number = txn.jv_number
                run.status = "posted"
                s.add(run)

        runs.append(run)
    return runs


def _vary_time(base_h: int, base_m: int, delta_m: int) -> str:
    total = base_h * 60 + base_m + random.randint(-delta_m, delta_m)
    total = max(0, min(23 * 60 + 59, total))
    return f"{total // 60:02d}:{total % 60:02d}"


def _hrs(tin: Optional[str], tout: Optional[str]) -> Optional[float]:
    if not tin or not tout:
        return None
    ih, im = map(int, tin.split(":"))
    oh, om = map(int, tout.split(":"))
    return round(max(0.0, (oh * 60 + om - ih * 60 - im) / 60.0), 2)


def _seed_attendance(s: Session, tenant_id: int, employees: list) -> None:
    """Seed 2 months of daily attendance for each employee (idempotent)."""
    today = date.today()
    # First day of 2 calendar months ago
    prev1 = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    start_dt = (prev1 - timedelta(days=1)).replace(day=1)

    current = start_dt
    while current <= today:
        dow = current.weekday()  # 0=Mon … 6=Sun
        date_str = current.isoformat()

        if dow < 5:  # weekday only
            for emp in employees:
                existing = s.exec(
                    select(AttendanceRecord).where(
                        AttendanceRecord.tenant_id == tenant_id,
                        AttendanceRecord.employee_id == emp.id,
                        AttendanceRecord.date == date_str,
                    )
                ).first()
                if existing:
                    continue  # skip this employee for this day

                roll = random.random()
                if roll < 0.85:
                    status = "present"
                    tin  = _vary_time(9, 0, 15)
                    tout = _vary_time(18, 0, 30)
                elif roll < 0.90:
                    status = "absent"
                    tin, tout = None, None
                elif roll < 0.95:
                    status = "half_day"
                    tin  = "09:00"
                    tout = "13:00"
                elif roll < 0.98:
                    status = "leave"
                    tin, tout = None, None
                else:
                    status = "holiday"
                    tin, tout = None, None

                s.add(AttendanceRecord(
                    tenant_id=tenant_id,
                    employee_id=emp.id,
                    date=date_str,
                    time_in=tin,
                    time_out=tout,
                    hours_worked=_hrs(tin, tout),
                    status=status,
                    source="manual",
                ))

        current += timedelta(days=1)


# ── Driver ────────────────────────────────────────────────────────────────────


def _seed_report_definitions(s: Session, tenant_id: int, user: User) -> None:
    """Seed one starter saved ReportDefinition per demo tenant (idempotent)."""
    existing = s.exec(
        select(ReportDefinition).where(
            ReportDefinition.tenant_id == tenant_id,
            ReportDefinition.name == "Outstanding Invoices",
        )
    ).first()
    if existing:
        return
    s.add(ReportDefinition(
        tenant_id=tenant_id,
        name="Outstanding Invoices",
        source_key="invoices",
        visibility="shared",
        owner_id=user.id,
        config=_json.dumps({
            "columns": ["number", "customer_name", "due_date", "total"],
            "filters": [{"field": "status", "op": "in", "value": ["sent", "partial"]}],
            "sort": [{"field": "due_date", "dir": "asc"}],
            "group_by": ["customer_name"],
            "aggregates": [{"field": "total", "fn": "sum"}],
            "date_range": None,
        }),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    ))


def _seed_notification_settings(s: Session, tenant_id: int) -> None:
    """Turn on email_notifications for every demo tenant so the overdue
    sweep + aging-reminder feature (services/overdue.py) is actually live
    against the seeded overdue invoices, not just dormant. Safe in dev/demo:
    send_email() no-ops silently when SMTP_HOST isn't configured, so this
    never dispatches a real email — it only exercises the tenant-eligibility
    query and the per-customer grouping/throttle logic end-to-end."""
    row = s.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == "email_notifications")
    ).first()
    if row:
        row.value = "true"
    else:
        row = Settings(key="email_notifications", value="true", tenant_id=tenant_id)
    s.add(row)


def _seed_pra_settings(s: Session, tenant_id: int) -> None:
    """Write PRA e-Invoice settings for the PRA demo tenant (sandbox mode)."""
    pra_kvs = {
        "currency":        "PKR",
        "pra_enabled":     "true",
        "pra_ntn":         "1234567-8",          # dummy PNTN matching the business
        "pra_pos_id":      "100001",              # sandbox POS ID
        "pra_sandbox_mode": "true",
        "pra_api_token":   "",                    # sandbox uses a shared static token
        "company_name":    "Lahore Retail Traders (PRA Demo)",
        "tax_id":          "1234567-8",
        "business_tagline": "Easy-Books · PRA e-Invoice Demo · Punjab, Pakistan",
    }
    for key, value in pra_kvs.items():
        row = s.exec(
            select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
        ).first()
        if row:
            row.value = value
        else:
            row = Settings(key=key, value=value, tenant_id=tenant_id)
        s.add(row)


def _seed_pra_customers(s: Session, tenant_id: int) -> list[Customer]:
    """Seed Pakistani customers with NTN and CNIC for PRA BuyerPNTN/BuyerCNIC."""
    out: list[Customer] = []
    for i, name in enumerate(PRA_CUSTOMER_NAMES):
        existing = s.exec(
            select(Customer).where(Customer.tenant_id == tenant_id, Customer.name == name)
        ).first()
        if existing:
            # Backfill NTN/CNIC if missing
            ntn, cnic = PRA_CUSTOMER_IDS[i % len(PRA_CUSTOMER_IDS)]
            if not existing.ntn:
                existing.ntn = ntn
                existing.cnic = cnic
                s.add(existing)
            out.append(existing)
            continue
        ntn, cnic = PRA_CUSTOMER_IDS[i % len(PRA_CUSTOMER_IDS)]
        c = Customer(
            tenant_id=tenant_id, name=name,
            email=name.lower().replace(" ", ".").replace("(", "").replace(")", "") + "@pk.example",
            phone=f"+92-{random.randint(300,349)}-{random.randint(1000000,9999999)}",
            ntn=ntn,
            cnic=cnic,
        )
        s.add(c)
        s.flush()
        out.append(c)
    return out


def _seed_pra_products(s: Session, tenant_id: int) -> list[Product]:
    """Seed Pakistani retail stock products with PCT codes for PRA ItemCode mapping."""
    out: list[Product] = []
    for code, name, unit, rate, cost, pct_code in PRA_PRODUCTS:
        existing = s.exec(
            select(Product).where(Product.tenant_id == tenant_id, Product.code == code)
        ).first()
        if existing:
            if not existing.pct_code:
                existing.pct_code = pct_code
                s.add(existing)
            out.append(existing)
            continue
        p = Product(
            tenant_id=tenant_id, code=code, name=name, unit=unit,
            product_type="stock", default_rate=D(rate), avg_cost=D(cost),
            stock_qty=D(random.randint(50, 500)), reorder_level=D(20),
            pct_code=pct_code,
        )
        s.add(p)
        s.flush()
        out.append(p)
    return out


def _stamp_pra_invoices(s: Session, invoices: list[Invoice]) -> None:
    """Stamp realistic PRA fiscal numbers on posted invoices (sandbox demo data)."""
    import hashlib
    fin_counter = 1000001
    for inv in invoices:
        if inv.pra_status in ("submitted",) or inv.status == "draft":
            continue
        inv.pra_usin = inv.number
        inv.payment_mode = random.choice([1, 1, 1, 2, 6])   # mostly Cash
        # Generate a deterministic but realistic-looking FIN
        h = hashlib.md5(f"DEMO-{inv.number}".encode()).hexdigest()[:8].upper()
        inv.pra_fiscal_number = f"PRA-{fin_counter}-{h}"
        inv.pra_status = "submitted"
        from datetime import datetime as _dt
        inv.pra_submitted_at = _dt.fromisoformat(inv.issue_date + "T09:30:00")
        s.add(inv)
        fin_counter += 1


def _seed_promo_rules(s: Session, tenant_id: int) -> None:
    """Seed 2–4 promotional price rules so the Promo Discounts page and the
    InvoiceForm "Apply Promos" button have live data (idempotent)."""
    if s.exec(select(PromoRule).where(PromoRule.tenant_id == tenant_id)).first():
        return
    today = date.today()
    stock = s.exec(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.product_type == "stock",
            Product.is_active == True,  # noqa: E712
        ).order_by(Product.id).limit(3)
    ).all()
    category = s.exec(
        select(ProductCategory).where(
            ProductCategory.tenant_id == tenant_id,
            ProductCategory.parent_id != None,  # noqa: E711 — sub-categories only
        ).order_by(ProductCategory.id)
    ).first()

    # Always applicable: invoice-value threshold discount (no product scope).
    s.add(PromoRule(
        tenant_id=tenant_id,
        name="Big Order 5% Off",
        description="5% off any invoice line once the invoice value crosses the threshold.",
        min_invoice_value=D("5000"),
        discount_type="percent", discount_value=D("5"),
        start_date=_past_days(min(180, _seed_span_days()), today=today),
    ))
    if stock:
        s.add(PromoRule(
            tenant_id=tenant_id,
            name=f"Bulk Buy — {stock[0].name}",
            description="10% off when ordering 10 or more units.",
            product_id=stock[0].id, min_qty=D("10"),
            discount_type="percent", discount_value=D("10"),
        ))
    if len(stock) >= 2:
        s.add(PromoRule(
            tenant_id=tenant_id,
            name=f"Baker's Dozen — {stock[1].name}",
            description="Buy 12, get 1 free.",
            product_id=stock[1].id, min_qty=D("12"),
            discount_type="giveaway",
            giveaway_product_id=stock[1].id, giveaway_qty=D("1"),
        ))
    if category:
        s.add(PromoRule(
            tenant_id=tenant_id,
            name=f"Seasonal — {category.name}",
            description="Limited-time 7.5% category-wide promotion.",
            category_id=category.id,
            discount_type="percent", discount_value=D("7.5"),
            start_date=_past_days(30, today=today),
            end_date=(today + timedelta(days=60)).isoformat(),
        ))


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    """(first-day, first-day-of-next-month) as ISO strings — [start, end)."""
    start = f"{year}-{month:02d}-01"
    if month == 12:
        return start, f"{year + 1}-01-01"
    return start, f"{year}-{month + 1:02d}-01"


def _seed_commissions(s: Session, owner: User, staff: list[User]) -> None:
    """Commission plans for the demo staff + a computed ledger over the last
    3 full months, exercising the whole draft → approved → posted flow.

    Mirrors routers/commissions.py's compute maths: assigns ~half the posted
    invoices to the staff users first (assigned_to_id was never set by the
    base seeder), then aggregates invoiced/recovered per period. Idempotent —
    skips once any CommissionPlan exists for the tenant."""
    tid = owner.tenant_id
    if s.exec(select(CommissionPlan).where(CommissionPlan.tenant_id == tid)).first():
        return

    today = date.today()
    # Plans became effective well before the seeded transaction window.
    eff_from = _past_days(_seed_span_days(today), today=today)
    plans = []
    for i, u in enumerate(staff):
        plan = CommissionPlan(
            tenant_id=tid, user_id=u.id,
            rate=D("2.5") if i == 0 else D("1.5"),
            sales_target=D("20000") if i == 0 else None,
            recovery_target=D("15000") if i == 0 else None,
            target_bonus=D("500") if i == 0 else None,
            effective_from=eff_from, active=True,
        )
        s.add(plan)
        plans.append(plan)
    s.flush()

    # Spread posted invoices across the sales staff so compute has inputs.
    invoices = s.exec(
        select(Invoice).where(
            Invoice.tenant_id == tid,
            Invoice.status != "draft",
            Invoice.assigned_to_id == None,  # noqa: E711
        ).order_by(Invoice.id)
    ).all()
    assigned = 0
    for i, inv in enumerate(invoices):
        if i % 2 == 0:                      # ~half stay unassigned (house accounts)
            continue
        inv.assigned_to_id = staff[assigned % len(staff)].id
        assigned += 1
        s.add(inv)
    s.flush()

    # Ledger for 3 consecutive full months anchored on the tenant's most
    # recent payment (so total_recovered is non-zero even when the payment
    # seeder left the last few months unpaid): oldest posted, middle
    # approved, newest draft — same upsert semantics as POST /api/commissions/compute.
    latest_pay = s.exec(
        select(PaymentReceived.payment_date).where(
            PaymentReceived.tenant_id == tid,
            PaymentReceived.payment_date < today.isoformat()[:8] + "01",
        ).order_by(PaymentReceived.payment_date.desc())  # type: ignore[attr-defined]
    ).first()
    anchor = date.fromisoformat(latest_pay) if latest_pay else today
    periods: list[tuple[int, int]] = [(anchor.year, anchor.month)]
    y, m = anchor.year, anchor.month
    for _ in range(2):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        periods.append((y, m))
    periods.reverse()                        # chronological: oldest first
    statuses = ["posted", "approved", "draft"]

    expense = get_or_create_account(s, tid, "5160", "Commission Expense", "Expense")
    payable = get_or_create_account(s, tid, "2260", "Commissions Payable", "Liability")

    for (py, pm), status in zip(periods, statuses):
        period = f"{py}-{pm:02d}"
        start, end = _month_bounds(py, pm)
        for plan in plans:
            uid = plan.user_id
            invoiced = s.exec(
                select(Invoice.total).where(
                    Invoice.tenant_id == tid,
                    Invoice.assigned_to_id == uid,
                    Invoice.issue_date >= start,
                    Invoice.issue_date < end,
                    Invoice.status != "cancelled",
                )
            ).all()
            total_invoiced = sum(invoiced, D("0"))
            recovered = s.exec(
                select(PaymentReceived.amount).join(
                    Invoice, PaymentReceived.invoice_id == Invoice.id
                ).where(
                    PaymentReceived.tenant_id == tid,
                    Invoice.assigned_to_id == uid,
                    PaymentReceived.payment_date >= start,
                    PaymentReceived.payment_date < end,
                )
            ).all()
            total_recovered = sum(recovered, D("0"))
            commission = (total_recovered * plan.rate / D("100")).quantize(D("0.01"))
            bonus = D("0")
            if plan.target_bonus:
                sales_ok = (not plan.sales_target) or (total_invoiced >= plan.sales_target)
                recovery_ok = (not plan.recovery_target) or (total_recovered >= plan.recovery_target)
                if sales_ok and recovery_ok:
                    bonus = plan.target_bonus
            total_payable = commission + bonus

            entry = CommissionLedger(
                tenant_id=tid, user_id=uid, period=period,
                total_invoiced=total_invoiced, total_recovered=total_recovered,
                rate=plan.rate, commission_amount=commission,
                bonus_amount=bonus, total_payable=total_payable,
                status="draft",
            )
            s.add(entry)
            s.flush()

            if status == "draft" or total_payable <= 0:
                continue
            entry.status = "approved"
            if status == "posted":
                staff_user = next(u for u in staff if u.id == uid)
                txn = post_transaction(
                    s, owner,
                    date=min(end, today.isoformat()),
                    description=f"Commission — {staff_user.full_name or staff_user.email} — {period}",
                    voucher_type="JV",
                    entries=[
                        EntryInput(account_id=expense.id, debit=float(total_payable), credit=0),
                        EntryInput(account_id=payable.id, debit=0, credit=float(total_payable)),
                    ],
                    audit_detail={"commission_ledger_id": entry.id, "period": period},
                )
                entry.transaction_id = txn.id
                entry.status = "posted"
            s.add(entry)


def _seed_accounting_periods(s: Session, tenant_id: int) -> None:
    """Named accounting periods for the Period Close page. The only *locked*
    period predates the seeded transaction window (~2 years), so re-running
    any top-up seeder can never trip posting.py's locked-period guard."""
    if s.exec(select(AccountingPeriod).where(AccountingPeriod.tenant_id == tenant_id)).first():
        return
    today = date.today()
    y = today.year
    s.add(AccountingPeriod(
        tenant_id=tenant_id, name=f"FY {y - 3}",
        period_start=f"{y - 3}-01-01", period_end=f"{y - 3}-12-31",
        is_locked=True,
    ))
    for fy in (y - 2, y - 1):
        s.add(AccountingPeriod(
            tenant_id=tenant_id, name=f"FY {fy}",
            period_start=f"{fy}-01-01", period_end=f"{fy}-12-31",
            is_locked=False,
        ))
    q = (today.month - 1) // 3 + 1
    for qi in range(1, q + 1):
        qs_month = (qi - 1) * 3 + 1
        qs, qe = _month_bounds(y, qs_month)[0], _month_bounds(y, qs_month + 2)[1]
        s.add(AccountingPeriod(
            tenant_id=tenant_id, name=f"Q{qi} {y}",
            period_start=qs,
            period_end=(date.fromisoformat(qe) - timedelta(days=1)).isoformat(),
            is_locked=False,
        ))


def _bank_gl_balance(s: Session, tenant_id: int, account_id: int, upto_exclusive: str) -> Decimal:
    """Net GL balance (Σdebit − Σcredit) of a bank CoA account before a date."""
    rows = s.exec(
        select(JournalEntry.debit, JournalEntry.credit)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.account_id == account_id,
            Transaction.date < upto_exclusive,
        )
    ).all()
    total = D("0")
    for dr, cr in rows:
        total += D(dr) - D(cr)
    return total


def _seed_reconciliations(s: Session, tenant_id: int) -> None:
    """Two bank reconciliations on the main bank account: the month before
    last fully matched + closed, the last full month left open with ~70%
    of lines ticked — so both states of the Reconciliations UI have data."""
    if s.exec(select(Reconciliation).where(Reconciliation.tenant_id == tenant_id)).first():
        return
    ba = s.exec(
        select(BankAccount).where(
            BankAccount.tenant_id == tenant_id,
            BankAccount.coa_account_id != None,  # noqa: E711
        ).order_by(BankAccount.id)
    ).first()
    if not ba:
        return
    today = date.today()
    for months_back, close_it in ((2, True), (1, False)):
        y, m = today.year, today.month
        for _ in range(months_back):
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        start, end_excl = _month_bounds(y, m)
        end = (date.fromisoformat(end_excl) - timedelta(days=1)).isoformat()
        entries = s.exec(
            select(JournalEntry)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                JournalEntry.tenant_id == tenant_id,
                JournalEntry.account_id == ba.coa_account_id,
                Transaction.date >= start,
                Transaction.date <= end,
            )
        ).all()
        if not entries:
            continue
        rec = Reconciliation(
            tenant_id=tenant_id, bank_account_id=ba.id,
            period_start=start, period_end=end,
            statement_balance=_bank_gl_balance(s, tenant_id, ba.coa_account_id, end_excl),
            status="closed" if close_it else "open",
        )
        s.add(rec)
        s.flush()
        for i, e in enumerate(entries):
            s.add(ReconciliationLine(
                reconciliation_id=rec.id, journal_entry_id=e.id,
                is_matched=close_it or (i % 10 < 7),
            ))


def _seed_bank_imports(s: Session, tenant_id: int) -> None:
    """One imported bank statement (last full month) built from the actual GL
    activity on the main bank account, ~60% auto-matched — feeds the Bank
    Imports page and leaves realistic unmatched lines to demo manual matching."""
    if s.exec(select(BankStatementImport).where(BankStatementImport.tenant_id == tenant_id)).first():
        return
    ba = s.exec(
        select(BankAccount).where(
            BankAccount.tenant_id == tenant_id,
            BankAccount.coa_account_id != None,  # noqa: E711
        ).order_by(BankAccount.id)
    ).first()
    if not ba:
        return
    today = date.today()
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    start, end_excl = _month_bounds(y, m)
    rows = s.exec(
        select(JournalEntry, Transaction)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.account_id == ba.coa_account_id,
            Transaction.date >= start,
            Transaction.date < end_excl,
        )
        .order_by(Transaction.date)
    ).all()
    if not rows:
        return
    imp = BankStatementImport(
        tenant_id=tenant_id, bank_account_id=ba.id,
        file_name=f"statement-{y}-{m:02d}.csv",
        file_hash=f"demo-{tenant_id}-{y}-{m:02d}",
        line_count=len(rows), status="matched",
    )
    s.add(imp)
    s.flush()
    balance = _bank_gl_balance(s, tenant_id, ba.coa_account_id, start)
    matched = 0
    for i, (je, txn) in enumerate(rows):
        # Bank's perspective: GL debit (money in) = statement credit column.
        stmt_credit = D(je.debit)
        stmt_debit = D(je.credit)
        balance += stmt_credit - stmt_debit
        is_matched = i % 5 < 3
        if is_matched:
            matched += 1
        s.add(StatementLine(
            tenant_id=tenant_id, import_id=imp.id,
            date=txn.date,
            description=(txn.description or txn.jv_number)[:120],
            debit=stmt_debit, credit=stmt_credit, balance=balance,
            matched_transaction_id=txn.id if is_matched else None,
            is_matched=is_matched,
        ))
    imp.matched_count = matched
    s.add(imp)


def _seed_pra_submission_logs(s: Session, tenant_id: int) -> None:
    """PRA e-IMS submission audit trail for the PRA demo tenant so the
    Submission Logs page has data: one success row per stamped invoice
    (capped at 20) plus a failed-then-retried pair on the first two —
    mirrors the log rows services/pra.py writes on a real submission.

    Convergent: if fewer than 20 success logs exist, keep adding for
    stamped invoices that have no log yet (older demos only had 1 row)."""
    existing_success = s.exec(
        select(PRASubmissionLog).where(
            PRASubmissionLog.tenant_id == tenant_id,
            PRASubmissionLog.success == True,  # noqa: E712
        )
    ).all()
    if len(existing_success) >= 20:
        return
    logged_invoice_ids = {
        row.invoice_id for row in s.exec(
            select(PRASubmissionLog).where(PRASubmissionLog.tenant_id == tenant_id)
        ).all()
        if row.invoice_id is not None
    }
    from services.pra import SANDBOX_URL
    invoices = s.exec(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.pra_status == "submitted",
        ).order_by(Invoice.issue_date.desc())  # type: ignore[attr-defined]
    ).all()
    added = 0
    for i, inv in enumerate(invoices):
        if len(existing_success) + added >= 20:
            break
        if inv.id in logged_invoice_ids:
            continue
        submitted_at = inv.pra_submitted_at or datetime.utcnow()
        request_json = _json.dumps({
            "InvoiceNumber": "", "POSID": 100001, "USIN": inv.pra_usin or inv.number,
            "DateTime": f"{inv.issue_date} 09:30:00",
            "TotalBillAmount": float(inv.total),
            "TotalSaleValue": float(inv.subtotal),
            "TotalTaxCharged": float(inv.gst_amount),
            "PaymentMode": inv.payment_mode or 1,
        })
        if added < 2 and len(existing_success) == 0:
            # A realistic first-attempt failure, retried successfully 3 min later.
            s.add(PRASubmissionLog(
                tenant_id=tenant_id, invoice_id=inv.id,
                attempt_at=submitted_at - timedelta(minutes=3),
                endpoint=SANDBOX_URL, request_json=request_json,
                response_code="102",
                response_json=_json.dumps({"Code": "102", "Response": "Invalid BuyerPNTN format"}),
                http_status=200, success=False,
                error_message="Invalid BuyerPNTN format",
            ))
        s.add(PRASubmissionLog(
            tenant_id=tenant_id, invoice_id=inv.id,
            attempt_at=submitted_at,
            endpoint=SANDBOX_URL, request_json=request_json,
            response_code="100",
            response_json=_json.dumps({
                "Code": "100", "Response": "Invoice statement submitted successfully.",
                "InvoiceNumber": inv.pra_fiscal_number,
            }),
            http_status=200, success=True,
        ))
        logged_invoice_ids.add(inv.id)
        added += 1


def _lab_demo_result(test: HcLabTest) -> tuple[str, str, str, bool]:
    """Return (value, unit, reference_range, is_abnormal) tuned to the catalogue
    row so the printable lab report looks realistic instead of a generic 5–15."""
    unit = test.unit or ""
    ref = test.normal_range or ""
    code = (test.code or "").upper()
    abnormal = random.random() < 0.15

    # Qualitative / imaging
    qualitative = {
        "URINE-R": ("Negative", "Trace", "Positive"),
        "HBSAG": ("Non-Reactive", "Reactive"),
        "HCV-AB": ("Non-Reactive", "Reactive"),
        "COVID-AG": ("Negative", "Positive"),
        "DENGUE": ("Negative", "Positive"),
        "PREG": ("Negative", "Positive"),
        "C/S": ("No growth", "E. coli isolated", "S. aureus isolated"),
        "CHEST-PA": ("Normal study", "Mild congestion", "Clear lung fields"),
        "USG-ABD": ("Normal study", "Mild fatty liver", "Normal visceral organs"),
        "ECG-LAB": ("Sinus rhythm", "Sinus tachycardia", "Normal ECG"),
        "LFT": ("Within normal limits", "Mild elevation", "WNL"),
        "RFT": ("Within normal limits", "Mild elevation", "WNL"),
        "LIPID": ("Desirable", "Borderline high", "High"),
    }
    if code in qualitative:
        choices = qualitative[code]
        if abnormal and len(choices) > 1:
            return choices[-1], unit, ref, True
        return choices[0], unit, ref, False

    # Numeric assays — mid-range normal with occasional outliers
    numeric = {
        "CBC": (4.0, 11.0, 1),
        "HB": (12.0, 17.0, 1),
        "ESR": (0.0, 20.0, 0),
        "PT-INR": (11.0, 13.5, 1),
        "BS-F": (70.0, 100.0, 0),
        "BS-R": (80.0, 140.0, 0),
        "TSH": (0.4, 4.0, 2),
    }
    if code in numeric:
        lo, hi, places = numeric[code]
        mid = (lo + hi) / 2
        span = (hi - lo) / 2
        if abnormal:
            val = hi + span * random.uniform(0.2, 0.8) if random.random() < 0.5 else max(0, lo - span * random.uniform(0.2, 0.6))
        else:
            val = mid + span * random.uniform(-0.6, 0.6)
        fmt = f"{{:.{places}f}}"
        return fmt.format(val), unit, ref, abnormal

    # Fallback: stay near catalogue range text or a mild numeric
    if abnormal:
        return "Elevated", unit, ref, True
    return "Normal", unit, ref, False


def _seed_healthcare(s: Session, user: User) -> None:
    """Seed hospital demo data: doctors, wards, beds, patients, OPD, IPD, lab, procedures.
    Idempotent — skips if HcDoctor rows already exist for this tenant."""
    tid = user.tenant_id
    today = date.today()

    if s.exec(select(HcDoctor).where(HcDoctor.tenant_id == tid)).first():
        return

    # ── Doctors ───────────────────────────────────────────────────────────────
    DOCTOR_DATA = [
        ("Dr. Asim Karim",     "Cardiology",      "MBBS, FCPS",  "0300-1111001", 1500),
        ("Dr. Rabia Siddiqui", "Gynecology",      "MBBS, FCPS",  "0300-1111002", 1200),
        ("Dr. Tariq Mehmood",  "General Surgery", "MBBS, FRCS",  "0300-1111003", 1000),
        ("Dr. Nadia Farooq",   "Pediatrics",      "MBBS, DCH",   "0300-1111004",  800),
        ("Dr. Khalid Hussain", "ENT",             "MBBS, DLO",   "0300-1111005",  700),
    ]
    doctors = []
    for nm, spec, qual, ph, fee in DOCTOR_DATA:
        doc = HcDoctor(tenant_id=tid, name=nm, specialization=spec,
                       qualification=qual, phone=ph, opd_fee=Decimal(fee))
        s.add(doc); s.flush(); doctors.append(doc)

    # ── Wards + Beds ──────────────────────────────────────────────────────────
    WARD_DATA = [
        ("Male General Ward",   "general",  12, Decimal("500")),
        ("Female General Ward", "general",  12, Decimal("500")),
        ("Private Suite",       "private",   8, Decimal("3000")),
        ("ICU",                 "icu",       6, Decimal("5000")),
    ]
    all_beds: list[HcBed] = []
    for wname, wtype, nbed, dcharge in WARD_DATA:
        ward = HcWard(tenant_id=tid, name=wname, ward_type=wtype,
                      total_beds=nbed, daily_charge=dcharge)
        s.add(ward); s.flush()
        for b in range(1, nbed + 1):
            bed = HcBed(tenant_id=tid, ward_id=ward.id,
                        bed_number=f"{wname[0]}{b:02d}", status="available")
            s.add(bed); s.flush()
            all_beds.append(bed)

    # ── Procedure Catalogue ───────────────────────────────────────────────────
    PROC_DATA = [
        ("PROC-001", "Dressing Change",    "minor",      Decimal("300")),
        ("PROC-002", "Suturing",           "minor",      Decimal("800")),
        ("PROC-003", "IV Cannulation",     "minor",      Decimal("200")),
        ("PROC-004", "Nebulisation",       "therapy",    Decimal("400")),
        ("PROC-005", "Appendectomy",       "surgery",    Decimal("25000")),
        ("PROC-006", "Cesarean Section",   "surgery",    Decimal("40000")),
        ("PROC-007", "ECG",                "diagnostic", Decimal("500")),
        ("PROC-008", "Ultrasound Abdomen", "diagnostic", Decimal("1500")),
        ("PROC-009", "X-Ray Chest PA",     "diagnostic", Decimal("700")),
        ("PROC-010", "Tonsillectomy",      "surgery",    Decimal("18000")),
    ]
    procedures = []
    for code, nm, cat, fee in PROC_DATA:
        p = HcProcedureCatalog(tenant_id=tid, code=code, name=nm, category=cat,
                               standard_fee=fee)
        s.add(p); s.flush(); procedures.append(p)

    # ── Lab Tests (20) ────────────────────────────────────────────────────────
    LAB_DATA = [
        ("CBC",      "Complete Blood Count",          "hematology",   "4.0–11.0", "×10³/μL", Decimal("400")),
        ("HB",       "Haemoglobin",                   "hematology",   "12–17",    "g/dL",     Decimal("200")),
        ("ESR",      "Erythrocyte Sedimentation Rate","hematology",   "0–20",     "mm/hr",    Decimal("200")),
        ("PT-INR",   "Prothrombin Time",              "hematology",   "11–13.5",  "sec",      Decimal("400")),
        ("BS-F",     "Blood Sugar Fasting",           "biochemistry", "70–100",   "mg/dL",    Decimal("150")),
        ("BS-R",     "Blood Sugar Random",            "biochemistry", "<140",     "mg/dL",    Decimal("150")),
        ("LFT",      "Liver Function Tests",          "biochemistry", "varies",   "U/L",      Decimal("900")),
        ("RFT",      "Renal Function Tests",          "biochemistry", "varies",   "mg/dL",    Decimal("800")),
        ("TSH",      "Thyroid Stimulating Hormone",   "biochemistry", "0.4–4.0",  "mIU/L",    Decimal("700")),
        ("LIPID",    "Lipid Profile",                 "biochemistry", "varies",   "mg/dL",    Decimal("1000")),
        ("URINE-R",  "Urine Routine",                 "microbiology", "negative", "",          Decimal("200")),
        ("C/S",      "Culture & Sensitivity",         "microbiology", "varies",   "",          Decimal("600")),
        ("HBsAG",    "Hepatitis B Surface Antigen",   "microbiology", "negative", "",          Decimal("350")),
        ("HCV-AB",   "Hepatitis C Antibodies",        "microbiology", "negative", "",          Decimal("400")),
        ("COVID-AG", "COVID-19 Antigen",              "microbiology", "negative", "",          Decimal("500")),
        ("DENGUE",   "Dengue NS1 Antigen",            "microbiology", "negative", "",          Decimal("800")),
        ("PREG",     "Pregnancy Test (urine)",        "other",        "negative", "",          Decimal("200")),
        ("CHEST-PA", "X-Ray Chest PA",                "radiology",    "normal",   "",          Decimal("700")),
        ("USG-ABD",  "Ultrasound Abdomen",            "radiology",    "normal",   "",          Decimal("1500")),
        ("ECG-LAB",  "Electrocardiogram",             "radiology",    "normal",   "",          Decimal("500")),
    ]
    lab_tests = []
    for code, nm, cat, rng, unit, fee in LAB_DATA:
        t = HcLabTest(tenant_id=tid, code=code, name=nm, category=cat,
                      normal_range=rng, unit=unit, standard_fee=fee)
        s.add(t); s.flush(); lab_tests.append(t)

    # ── Patients (50 Pakistani names) ─────────────────────────────────────────
    PAK_NAMES_M = [
        "Muhammad Ali", "Ahmed Hassan", "Usman Tariq", "Bilal Anwar", "Faisal Mahmood",
        "Zubair Khan", "Imran Ashraf", "Tahir Raza", "Salman Iqbal", "Kamran Butt",
        "Adeel Sarwar", "Junaid Malik", "Waseem Akram", "Naeem Akhtar", "Rizwan Aslam",
        "Shafiq Rehman", "Irfan Chaudhry", "Pervez Mirza", "Saeed Baig", "Hamid Sohail",
        "Asad Qureshi", "Waqas Ilyas", "Sohail Ahmed", "Javed Iqbal", "Naveed Zaman",
    ]
    PAK_NAMES_F = [
        "Fatima Bibi", "Ayesha Siddiqua", "Zainab Batool", "Maryam Noor", "Sana Rasheed",
        "Hina Tariq", "Nadia Aslam", "Rabia Parveen", "Amina Shahid", "Rukhsana Begum",
        "Saima Anwar", "Farzana Akbar", "Bushra Malik", "Naseem Akhtar", "Tahira Jabeen",
        "Shaista Bano", "Rehana Sultana", "Uzma Fayyaz", "Mehnaz Riaz", "Asma Cheema",
        "Lubna Wahid", "Samina Baig", "Nighat Mehmood", "Parveen Iqbal", "Khurshid Bibi",
    ]
    BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    patients = []
    for idx, nm in enumerate(PAK_NAMES_M + PAK_NAMES_F):
        gender = "male" if idx < 25 else "female"
        dob = (today - timedelta(days=random.randint(365 * 18, 365 * 75))).isoformat()
        cust = Customer(tenant_id=tid, name=nm,
                        phone=f"03{random.randint(10,49):02d}-{random.randint(1000000,9999999)}",
                        email="")
        s.add(cust); s.flush()
        mr = f"MR-{today.year}{idx + 1:04d}"
        pat = HcPatient(
            tenant_id=tid, customer_id=cust.id, mr_number=mr, name=nm,
            dob=dob, gender=gender,
            blood_group=random.choice(BLOOD_GROUPS),
            phone=cust.phone,
            created_by_id=user.id,
        )
        s.add(pat); s.flush(); patients.append(pat)

    # ── OPD Tokens + Visits (200 tokens, ~160 visits over 90 days) ───────────
    DIAGNOSES = [
        "Acute upper respiratory infection", "Type 2 Diabetes mellitus",
        "Hypertension, essential", "Acute gastroenteritis", "Anaemia",
        "Dengue fever", "Urinary tract infection", "Migraine",
        "Chest pain — non-cardiac", "Back pain, lumbar",
        "Pneumonia", "Asthma exacerbation", "Hypothyroidism",
        "Allergic rhinitis", "Dyspepsia",
    ]
    COMPLAINTS = ["Fever & chills", "Cough & cold", "Chest pain", "Abdominal pain",
                  "Headache", "Body aches", "Vomiting", "Diarrhoea", "Dizziness"]
    MEDICINES  = ["Tab Paracetamol 500mg", "Syp Augmentin", "Cap Amoxicillin 500mg",
                  "Tab Metronidazole 400mg", "ORS Sachets", "Tab Ibuprofen 400mg",
                  "Syp Benadryl", "Tab Omeprazole 20mg", "Tab Ciprofloxacin 500mg"]
    token_seq: dict[int, int] = {}
    visit_counter = 0
    span = _seed_span_days(today)
    # Dense recent band (last ≤90 days) keeps the live OPD queue; extra sample
    # days stretch the rest of the 2-year window so hospital reports have history.
    recent = list(range(min(90, span), -1, -1))
    historical: list[int] = []
    if span > 90:
        for i in range(60):
            historical.append(90 + int((span - 90) * (i + 1) / 61))
    day_offsets = sorted(set(recent + historical), reverse=True)
    for day_offset in day_offsets:
        visit_date = (today - timedelta(days=day_offset)).isoformat()
        # Fewer tokens today (3–5 waiting), more on past days
        n_tokens = random.randint(3, 5) if day_offset == 0 else random.randint(1, 4)
        for token_idx in range(n_tokens):
            doc = random.choice(doctors)
            pat = random.choice(patients)
            dn = token_seq.get(doc.id, 0) + 1
            token_seq[doc.id] = dn
            # Today's tokens are waiting/called; past tokens are visited
            if day_offset == 0:
                tok_status = "waiting" if token_idx < 2 else "called"
            else:
                tok_status = "visited"
            tok = HcOpdToken(
                tenant_id=tid, doctor_id=doc.id, patient_id=pat.id,
                patient_name=pat.name, token_number=dn,
                visit_date=visit_date, status=tok_status,
            )
            s.add(tok); s.flush()
            if day_offset > 0 and visit_counter < 160:
                visit = HcOpdVisit(
                    tenant_id=tid, token_id=tok.id, patient_id=pat.id,
                    doctor_id=doc.id, visit_date=visit_date,
                    visit_type=random.choice(["first", "follow_up"]),
                    chief_complaint=random.choice(COMPLAINTS),
                    diagnosis=random.choice(DIAGNOSES),
                    advice="Rest, fluids, follow-up in 1 week.",
                )
                s.add(visit); s.flush()
                # Post OPD consultation GL: Dr 1100 AR / Cr 4100 Revenue
                rev_code = "4101" if visit.visit_type == "follow_up" else "4100"
                txn = post_opd_consultation(
                    s, user, amount=doc.opd_fee, date=visit_date,
                    patient_name=pat.name, doctor_name=doc.name,
                    revenue_account_code=rev_code,
                    customer_id=pat.customer_id,
                )
                visit.transaction_id = txn.id
                s.add(visit)
                rx = HcPrescription(
                    tenant_id=tid, visit_id=visit.id,
                    patient_id=pat.id, doctor_id=doc.id,
                    prescribed_date=visit_date,
                )
                s.add(rx); s.flush()
                for med in random.sample(MEDICINES, k=random.randint(1, 3)):
                    s.add(HcPrescriptionItem(
                        tenant_id=tid, prescription_id=rx.id,
                        medicine_name=med, dosage="1 tablet",
                        frequency="TDS", duration="5 days",
                        route="oral", qty=Decimal("15"),
                    ))
                visit_counter += 1

    # ── IPD Admissions (20: 15 discharged, 5 active) ─────────────────────────
    available_beds = list(all_beds)
    random.shuffle(available_beds)
    for i in range(20):
        pat    = random.choice(patients)
        doc    = random.choice(doctors[:3])
        days_ago = max(5, int(span * (i + 1) / 22))
        adm_date = (today - timedelta(days=days_ago)).isoformat()
        adm_num  = f"ADM-{today.year}{i + 1:04d}"
        bed      = available_beds[i % len(available_beds)]
        deposit  = Decimal(random.choice([5000, 10000, 15000, 20000]))
        discharged = i < 15
        dis_date = (today - timedelta(days=random.randint(1, days_ago - 1))).isoformat() if discharged else None
        adm = HcAdmission(
            tenant_id=tid, admission_number=adm_num,
            patient_id=pat.id, doctor_id=doc.id,
            ward_id=bed.ward_id, bed_id=bed.id,
            admission_date=adm_date, discharge_date=dis_date,
            diagnosis=random.choice(DIAGNOSES),
            admission_type=random.choice(["planned", "emergency", "referred"]),
            status="discharged" if discharged else "admitted",
            deposit_amount=deposit,
        )
        s.add(adm); s.flush()
        if not discharged:
            bed.status = "occupied"
            bed.current_admission_id = adm.id
            s.add(bed)

        # Post admission deposit GL: Dr 1000 Cash / Cr 2310 Patient Advances
        dep_txn = post_ipd_deposit(
            s, user, amount=deposit, date=adm_date,
            patient_name=pat.name, admission_number=adm_num,
        )
        adm.deposit_transaction_id = dep_txn.id
        s.add(adm)

        stay_days = random.randint(2, 7) if discharged else days_ago
        total_charges = Decimal("0")
        for d in range(stay_days):
            charge_date = (today - timedelta(days=days_ago - d)).isoformat()
            s.add(HcAdmissionCharge(
                tenant_id=tid, admission_id=adm.id, charge_date=charge_date,
                charge_type="bed", description="Ward bed charge", amount=Decimal("500"),
            ))
            total_charges += Decimal("500")
        for _ in range(random.randint(0, 2)):
            proc = random.choice(procedures[:6])
            s.add(HcAdmissionCharge(
                tenant_id=tid, admission_id=adm.id, charge_date=adm_date,
                charge_type="procedure", description=proc.name, amount=proc.standard_fee,
            ))
            total_charges += proc.standard_fee

        # Post discharge GL for discharged admissions
        if discharged and total_charges > 0:
            dis_txn = post_discharge_bill(
                s, user,
                total_charges=total_charges, deposit_amount=deposit,
                date=dis_date, patient_name=pat.name, admission_number=adm_num,
                customer_id=pat.customer_id,
                charge_breakdown={"bed": str(total_charges)},
            )
            adm.discharge_invoice_id = dis_txn.id
            s.add(adm)

    # ── Lab Orders (80) ───────────────────────────────────────────────────────
    SOURCES   = ["walkin", "opd", "opd", "opd", "collection_centre"]
    STATUSES  = ["delivered", "delivered", "delivered", "resulted", "sample_collected"]
    for _ in range(80):
        order_date = _past_days(random.randint(1, max(1, span - 1)), today=today)
        pat    = random.choice(patients)
        source = random.choice(SOURCES)
        status = random.choice(STATUSES)
        lo_num = next_number(s, tid, "hc_lab_order", "LO")
        order = HcLabOrder(
            tenant_id=tid, order_number=lo_num, patient_id=pat.id,
            doctor_id=random.choice(doctors).id if source in ("opd", "ipd") else None,
            order_date=order_date, source=source, status=status,
        )
        s.add(order); s.flush()
        tests_chosen = random.sample(lab_tests, k=random.randint(1, 4))
        lab_total = Decimal("0")
        for test in tests_chosen:
            item = HcLabOrderItem(
                lab_order_id=order.id,
                test_id=test.id, fee=test.standard_fee,
            )
            if status in ("resulted", "delivered"):
                value, unit, ref, abnormal = _lab_demo_result(test)
                item.result_value = value
                item.result_unit = unit
                item.reference_range = ref
                item.is_abnormal = abnormal
                item.resulted_at = datetime.utcnow()
                item.resulted_by_id = user.id
            s.add(item)
            lab_total += test.standard_fee
        if source != "walkin" and status != "ordered":
            s.add(HcSampleCollection(
                tenant_id=tid, lab_order_id=order.id,
                collected_by_id=user.id, collected_at=datetime.utcnow(),
                collection_point="lab", specimen_type="blood", status="received",
            ))
        # Post lab GL for billed orders (delivered/resulted)
        if status in ("delivered", "resulted") and lab_total > 0:
            lab_txn = post_lab_order(
                s, user, amount=lab_total, date=order_date,
                patient_name=pat.name, order_number=lo_num,
                customer_id=pat.customer_id,
            )
            order.transaction_id = lab_txn.id
            s.add(order)

    # ── Procedure Orders (25) ─────────────────────────────────────────────────
    for _ in range(25):
        order_date = _past_days(random.randint(1, max(1, span - 1)), today=today)
        pat  = random.choice(patients)
        proc = random.choice(procedures)
        doc  = random.choice(doctors)
        status = random.choice(["performed", "performed", "ordered"])
        s.add(HcProcedureOrder(
            tenant_id=tid, patient_id=pat.id, doctor_id=doc.id,
            procedure_id=proc.id, order_date=order_date,
            status=status, fee=proc.standard_fee,
            performed_date=order_date if status == "performed" else None,
        ))

    s.flush()

    # ── Sync SequenceCounters so API calls after seeding don't collide ─────────
    # 50 patients → next MR is 51; 20 admissions → next ADM is 21
    for seq_name, next_val in [("hc_mr", 51), ("hc_adm", 21)]:
        row = s.exec(
            select(SequenceCounter).where(
                SequenceCounter.tenant_id == tid,
                SequenceCounter.name == seq_name,
            )
        ).first()
        if row:
            row.next_value = max(row.next_value, next_val)
        else:
            s.add(SequenceCounter(tenant_id=tid, name=seq_name, next_value=next_val))
    s.flush()


def _seed_dialysis(s: Session, user: User) -> None:
    """Dialysis Treatment Unit: 17 machines, 3×4h shifts (08:00–20:00), capacity 51/day.
    Idempotent — skips when a dialysis unit already exists for the tenant."""
    tid = user.tenant_id
    if s.exec(select(HcDialysisUnit).where(HcDialysisUnit.tenant_id == tid)).first():
        return

    today = date.today()
    unit = HcDialysisUnit(
        tenant_id=tid,
        name="Dialysis Treatment Unit",
        open_time="08:00",
        close_time="20:00",
        shift_hours=4,
        created_at=datetime.utcnow(),
    )
    s.add(unit)
    s.flush()

    SHIFT_DATA = [
        ("A", "Morning", "08:00", "12:00", 1),
        ("B", "Afternoon", "12:00", "16:00", 2),
        ("C", "Evening", "16:00", "20:00", 3),
    ]
    shifts: list[HcDialysisShift] = []
    for code, name, start, end, order in SHIFT_DATA:
        sh = HcDialysisShift(
            tenant_id=tid, unit_id=unit.id, code=code, name=name,
            start_time=start, end_time=end, sort_order=order,
        )
        s.add(sh)
        s.flush()
        shifts.append(sh)

    machines: list[HcDialysisMachine] = []
    for i in range(1, 18):
        status = "maintenance" if i in (16, 17) else "available"
        m = HcDialysisMachine(
            tenant_id=tid, unit_id=unit.id,
            code=f"DM-{i:02d}",
            name=f"Dialysis Machine {i:02d}",
            status=status,
            created_at=datetime.utcnow(),
        )
        s.add(m)
        s.flush()
        machines.append(m)

    # Nephrologist
    neph = s.exec(
        select(HcDoctor).where(
            HcDoctor.tenant_id == tid,
            HcDoctor.specialization == "Nephrology",
        )
    ).first()
    if not neph:
        neph = HcDoctor(
            tenant_id=tid,
            name="Dr. Imran Qureshi",
            specialization="Nephrology",
            qualification="MBBS, FCPS (Nephrology)",
            phone="0300-1111006",
            opd_fee=Decimal("2000"),
        )
        s.add(neph)
        s.flush()

    # HD procedure catalogue
    hd = s.exec(
        select(HcProcedureCatalog).where(
            HcProcedureCatalog.tenant_id == tid,
            HcProcedureCatalog.code == "HD-SESSION",
        )
    ).first()
    if not hd:
        hd = HcProcedureCatalog(
            tenant_id=tid,
            code="HD-SESSION",
            name="Hemodialysis Session (4h)",
            category="therapy",
            standard_fee=Decimal("4500"),
            created_at=datetime.utcnow(),
        )
        s.add(hd)
        s.flush()

    patients = list(s.exec(select(HcPatient).where(HcPatient.tenant_id == tid)).all())
    if len(patients) < 12:
        # Create extra chronic HD patients if hospital seed ran thin
        for i in range(12 - len(patients)):
            mr = next_number(s, tid, "hc_mr", "MR", fmt="{prefix}-{YYYY}{seq:04d}")
            cust = Customer(
                tenant_id=tid,
                name=f"HD Patient {i + 1}",
                phone=f"0301-55{i:04d}",
            )
            s.add(cust)
            s.flush()
            pat = HcPatient(
                tenant_id=tid,
                customer_id=cust.id,
                mr_number=mr,
                name=f"HD Patient {i + 1}",
                gender=random.choice(["male", "female"]),
                phone=f"0301-55{i:04d}",
                created_at=datetime.utcnow(),
                created_by_id=user.id,
            )
            s.add(pat)
            s.flush()
            patients.append(pat)

    hd_patients = patients[:12]
    usable = [m for m in machines if m.status != "maintenance"]

    # Past completed sessions (~2–3 weeks, MWF pattern feel)
    seq_next = 1
    for days_ago in range(21, 0, -1):
        d = today - timedelta(days=days_ago)
        if d.weekday() not in (0, 2, 4):  # Mon/Wed/Fri heavy days
            continue
        day_s = d.isoformat()
        # ~30–40 of 51 slots historically
        n = random.randint(28, 40)
        slots = [(m, sh) for m in usable for sh in shifts]
        random.shuffle(slots)
        for m, sh in slots[:n]:
            pat = random.choice(hd_patients)
            sn = f"DS-{d.year}{seq_next:04d}"
            seq_next += 1
            row = HcDialysisSession(
                tenant_id=tid,
                session_number=sn,
                patient_id=pat.id,
                doctor_id=neph.id,
                machine_id=m.id,
                shift_id=sh.id,
                session_date=day_s,
                status="completed",
                fee=hd.standard_fee,
                procedure_id=hd.id,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                created_by_id=user.id,
            )
            s.add(row)
            s.flush()
            try:
                txn = post_procedure(
                    s, user,
                    amount=hd.standard_fee,
                    date=day_s,
                    patient_name=pat.name,
                    procedure_name=hd.name,
                    customer_id=pat.customer_id,
                )
                row.transaction_id = txn.id
                s.add(row)
            except Exception:
                pass  # CoA missing in edge cases — keep memo session

    # Today's board — fill ~40 of usable capacity (15×3=45)
    today_s = today.isoformat()
    slots = [(m, sh) for m in usable for sh in shifts]
    random.shuffle(slots)
    n_today = min(40, len(slots))
    statuses_cycle = (
        ["completed"] * 12
        + ["in_progress"] * 5
        + ["scheduled"] * 23
    )
    for idx, (m, sh) in enumerate(slots[:n_today]):
        pat = hd_patients[idx % len(hd_patients)]
        st = statuses_cycle[idx % len(statuses_cycle)]
        sn = f"DS-{today.year}{seq_next:04d}"
        seq_next += 1
        row = HcDialysisSession(
            tenant_id=tid,
            session_number=sn,
            patient_id=pat.id,
            doctor_id=neph.id,
            machine_id=m.id,
            shift_id=sh.id,
            session_date=today_s,
            status=st,
            fee=hd.standard_fee,
            procedure_id=hd.id,
            started_at=datetime.utcnow() if st in ("in_progress", "completed") else None,
            completed_at=datetime.utcnow() if st == "completed" else None,
            created_at=datetime.utcnow(),
            created_by_id=user.id,
        )
        s.add(row)
        s.flush()
        if st == "in_progress":
            m.status = "in_use"
            s.add(m)
        if st == "completed":
            try:
                txn = post_procedure(
                    s, user,
                    amount=hd.standard_fee,
                    date=today_s,
                    patient_name=pat.name,
                    procedure_name=hd.name,
                    customer_id=pat.customer_id,
                )
                row.transaction_id = txn.id
                s.add(row)
            except Exception:
                pass

    # Sync sequence counter for DS numbers
    row = s.exec(
        select(SequenceCounter).where(
            SequenceCounter.tenant_id == tid,
            SequenceCounter.name == "hc_dialysis",
        )
    ).first()
    if row:
        row.next_value = max(row.next_value, seq_next)
    else:
        s.add(SequenceCounter(tenant_id=tid, name="hc_dialysis", next_value=seq_next))
    s.flush()


def _seed_lab_serial_history(s: Session, user: User) -> None:
    """Ensure a few patients have multi-visit numeric trends for the lab report
    historgram (CLSI cumulative charts). Idempotent — skips when any patient
    already has ≥4 resulted Haemoglobin points."""
    tid = user.tenant_id
    hb = s.exec(
        select(HcLabTest).where(HcLabTest.tenant_id == tid, HcLabTest.code == "HB")
    ).first()
    if not hb:
        return
    # Count patients with ≥4 HB results
    hb_items = s.exec(
        select(HcLabOrderItem, HcLabOrder)
        .join(HcLabOrder, HcLabOrderItem.lab_order_id == HcLabOrder.id)
        .where(
            HcLabOrder.tenant_id == tid,
            HcLabOrderItem.test_id == hb.id,
            HcLabOrderItem.resulted_at.is_not(None),  # type: ignore[attr-defined]
        )
    ).all()
    by_patient: dict[int, int] = {}
    for item, order in hb_items:
        by_patient[order.patient_id] = by_patient.get(order.patient_id, 0) + 1
    if any(c >= 4 for c in by_patient.values()):
        return

    patients = s.exec(select(HcPatient).where(HcPatient.tenant_id == tid)).all()
    doctors = s.exec(select(HcDoctor).where(HcDoctor.tenant_id == tid)).all()
    if len(patients) < 3:
        return

    serial_codes = ["CBC", "HB", "BS-F", "TSH", "ESR"]
    tests = {
        t.code: t
        for t in s.exec(
            select(HcLabTest).where(
                HcLabTest.tenant_id == tid,
                HcLabTest.code.in_(serial_codes),  # type: ignore[attr-defined]
            )
        ).all()
    }
    if len(tests) < 3:
        return

    today = date.today()
    for pi, pat in enumerate(patients[:3]):
        doc = doctors[pi % len(doctors)] if doctors else None
        for visit in range(5):
            order_date = (today - timedelta(days=14 * (5 - visit))).isoformat()
            lo_num = next_number(s, tid, "hc_lab_order", "LO")
            order = HcLabOrder(
                tenant_id=tid, order_number=lo_num, patient_id=pat.id,
                doctor_id=doc.id if doc else None,
                order_date=order_date, source="opd", status="delivered",
            )
            s.add(order); s.flush()
            for code in serial_codes:
                test = tests.get(code)
                if not test:
                    continue
                value, unit, ref, abnormal = _lab_demo_result(test)
                # Mild upward drift for visual trend demos
                num = _try_float(value)
                if num is not None and code in ("HB", "BS-F", "CBC"):
                    num = round(num + visit * 0.3, 1)
                    value = f"{num}"
                    abnormal = False
                item = HcLabOrderItem(
                    lab_order_id=order.id, test_id=test.id, fee=test.standard_fee,
                    result_value=value, result_unit=unit or test.unit or "",
                    reference_range=ref or test.normal_range or "",
                    is_abnormal=abnormal,
                    resulted_at=datetime.utcnow(),
                    resulted_by_id=user.id,
                )
                s.add(item)
            s.add(HcSampleCollection(
                tenant_id=tid, lab_order_id=order.id,
                collected_by_id=user.id, collected_at=datetime.utcnow(),
                collection_point="lab", specimen_type="blood", status="received",
            ))
    s.flush()


def _try_float(value: str) -> Optional[float]:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _seed_healthcare_store(s: Session, user: User) -> None:
    """HC Store / pharmacy issues — backfillable so hospital demos that were
    seeded before this block still get a populated HC Store screen."""
    tid = user.tenant_id
    if s.exec(select(HcStoreIssue).where(HcStoreIssue.tenant_id == tid)).first():
        return

    patients = s.exec(select(HcPatient).where(HcPatient.tenant_id == tid)).all()
    admissions = s.exec(
        select(HcAdmission).where(
            HcAdmission.tenant_id == tid, HcAdmission.status == "admitted",
        )
    ).all()
    products = s.exec(
        select(Product).where(
            Product.tenant_id == tid, Product.product_type == "stock",
        )
    ).all()
    if not products:
        # Ensure pharmacy SKUs exist even on older hospital tenants.
        for code, name, unit, sale, _cost in HOSPITAL_STOCK:
            existing = s.exec(
                select(Product).where(Product.tenant_id == tid, Product.code == code)
            ).first()
            if existing:
                products.append(existing)
                continue
            p = Product(
                tenant_id=tid, code=code, name=name, unit=unit,
                product_type="stock", default_rate=money(D(sale)),
            )
            s.add(p); s.flush()
            products.append(p)
    if not products:
        return

    loc = s.exec(
        select(StockLocation).where(StockLocation.tenant_id == tid, StockLocation.type == "own")
    ).first()
    if not loc:
        loc = StockLocation(
            tenant_id=tid, code="PHARM", name="Pharmacy Store", type="own",
        )
        s.add(loc); s.flush()

    today = date.today()
    purposes = ["pharmacy", "pharmacy", "ward", "lab", "procedure"]
    issue_count = 25
    for i in range(issue_count):
        issue_date = _past_days(2 + i * 2, today=today)
        purpose = purposes[i % len(purposes)]
        pat = patients[i % len(patients)] if patients else None
        adm = admissions[i % len(admissions)] if admissions and purpose in ("pharmacy", "ward") else None
        charge = purpose == "pharmacy" and pat is not None
        issue_number = next_number(s, tid, "hc_store", "HSI", fmt="{prefix}-{YYYY}{seq:04d}")
        issue = HcStoreIssue(
            tenant_id=tid, issue_number=issue_number, issue_date=issue_date,
            from_location_id=loc.id, patient_id=pat.id if pat else None,
            admission_id=adm.id if adm else None, purpose=purpose,
            created_by_id=user.id,
        )
        s.add(issue); s.flush()

        total_charged = ZERO
        for j in range(random.randint(1, 3)):
            prod = products[(i + j) % len(products)]
            qty = D(random.randint(1, 4))
            unit_cost = money(D(prod.default_rate) * D("0.4"))
            charge_amt = money(D(prod.default_rate) * qty) if charge else ZERO
            s.add(HcStoreIssueItem(
                issue_id=issue.id, product_id=prod.id, qty=qty,
                unit_cost=unit_cost, charge_to_patient=charge,
                charge_amount=charge_amt,
            ))
            if charge:
                total_charged += charge_amt
                if adm:
                    s.add(HcAdmissionCharge(
                        tenant_id=tid, admission_id=adm.id,
                        charge_date=issue_date, charge_type="pharmacy",
                        description=f"Store: {prod.name}", amount=charge_amt,
                        created_by_id=user.id,
                    ))
        if total_charged > ZERO:
            txn = post_store_issue(
                s, user, amount=total_charged, date=issue_date,
                issue_number=issue_number, purpose=purpose,
                charge_to_patient=True, customer_id=None,
            )
            issue.transaction_id = txn.id
            s.add(issue)
        s.flush()


def _seed_weaving(s: Session, user: User, customers: list[Customer], vendors: list[Vendor]) -> None:
    """Weaving unit-control demo (#140). Idempotent — skips if contracts exist."""
    tid = user.tenant_id
    if s.exec(select(WvContract).where(WvContract.tenant_id == tid)).first():
        return

    today = date.today()
    from services import weaving_calc as calc

    fq = WvFabricQuality(tenant_id=tid, code="FQ-PC", name="Plain Cotton 60x60", description="Grey fabric")
    yt = WvYarnType(tenant_id=tid, code="YT-30s", name="Cotton 30s", description="Warp/weft yarn")
    loom_a = WvLoom(tenant_id=tid, code="L-01", name="Loom 1", loom_type="airjet")
    loom_b = WvLoom(tenant_id=tid, code="L-02", name="Loom 2", loom_type="rapier")
    shift_a = WvShift(tenant_id=tid, code="A", name="Morning")
    shift_b = WvShift(tenant_id=tid, code="B", name="Evening")
    op1 = WvOperator(tenant_id=tid, code="OP-01", name="Imran Ali")
    op2 = WvOperator(tenant_id=tid, code="OP-02", name="Saeed Khan")
    for row in (fq, yt, loom_a, loom_b, shift_a, shift_b, op1, op2):
        s.add(row)
    s.flush()

    cust = customers[0] if customers else None
    if not cust:
        return
    vendor = vendors[0] if vendors else None

    contracts_spec = [
        ("in_process", Decimal("10000"), Decimal("450"), Decimal("85"), Decimal("12")),
        ("completed", Decimal("5000"), Decimal("420"), Decimal("90"), Decimal("10")),
        ("delayed", Decimal("8000"), Decimal("480"), Decimal("80"), Decimal("15")),
    ]
    contracts: list[WvContract] = []
    span = _seed_span_days(today)
    for i, (status, meters, yarn_rate, weave_rate, shrink) in enumerate(contracts_spec):
        # Spread contract starts across the 2-year window; open ones still end in the future.
        start = _past_days(int(span * (0.85 - i * 0.2)), today=today)
        end = (today + timedelta(days=30 + i * 15)).isoformat()
        c = WvContract(
            tenant_id=tid,
            number=next_number(s, tid, "wv_contract", "WC", fmt="{prefix}-{YYYY}-{seq:04d}"),
            customer_id=cust.id,
            fabric_quality_id=fq.id,
            yarn_type_id=yt.id,
            start_date=start,
            end_date=end,
            contract_meters=meters,
            pick_per_inch=Decimal("72"),
            assumed_yarn_rate_per_kg=yarn_rate,
            fabric_return_price_per_meter=Decimal("55"),
            weaving_rate=weave_rate,
            expected_shrinkage_pct=shrink,
            payment_terms="Net 30",
            status=status,
            created_by_id=user.id,
        )
        s.add(c)
        s.flush()
        contracts.append(c)

    # Activity on first (in_process) contract — enough for all four reports.
    # Scale the original ~60-day process offsets across the 2-year window so
    # yarn → sizing → production → dispatch stay chronological.
    c0 = contracts[0]

    def _wv_days(old_offset: int) -> int:
        return max(1, int(span * old_offset / 60)) if span else max(1, old_offset)

    for i, (gross, tare) in enumerate([(Decimal("520"), Decimal("20")), (Decimal("310"), Decimal("10"))]):
        net = calc.net_kg(gross, tare)
        rate = c0.assumed_yarn_rate_per_kg
        s.add(WvYarnInward(
            tenant_id=tid,
            number=next_number(s, tid, "wv_yarn_inward", "YI", fmt="{prefix}-{YYYY}-{seq:04d}"),
            contract_id=c0.id, yarn_type_id=yt.id,
            date=_past_days(_wv_days(40 - i * 5), today=today),
            gross_kg=gross, tare_kg=tare, net_kg=net,
            rate_per_kg=rate, yarn_value=money(net * rate),
            created_by_id=user.id,
        ))
    s.flush()

    s.add(WvSizing(
        tenant_id=tid,
        number=next_number(s, tid, "wv_sizing", "SZ", fmt="{prefix}-{YYYY}-{seq:04d}"),
        contract_id=c0.id, vendor_id=vendor.id if vendor else None,
        date=_past_days(_wv_days(30), today=today),
        input_kg=Decimal("500"), output_kg=Decimal("485"),
        gain_shrink_pct=calc.sizing_gain_shrink_pct(Decimal("500"), Decimal("485")),
        sizing_cost=Decimal("12500"), created_by_id=user.id,
    ))
    s.flush()

    for i, (warp, weft, grey, loom, shift, op) in enumerate([
        (Decimal("120"), Decimal("80"), Decimal("2200"), loom_a, shift_a, op1),
        (Decimal("100"), Decimal("70"), Decimal("1900"), loom_b, shift_b, op2),
        (Decimal("90"), Decimal("60"), Decimal("1600"), loom_a, shift_a, op1),
    ]):
        total = warp + weft
        s.add(WvProduction(
            tenant_id=tid,
            number=next_number(s, tid, "wv_production", "WP", fmt="{prefix}-{YYYY}-{seq:04d}"),
            contract_id=c0.id, loom_id=loom.id, shift_id=shift.id, operator_id=op.id,
            date=_past_days(_wv_days(25 - i * 5), today=today),
            warp_yarn_kg=warp, weft_yarn_kg=weft, total_yarn_kg=total,
            grey_meters=grey,
            efficiency_pct=calc.production_efficiency_pct(grey, c0.contract_meters),
            weaving_charges=calc.weaving_charges(grey, c0.weaving_rate),
            created_by_id=user.id,
        ))
    s.flush()

    for i, meters in enumerate([Decimal("2000"), Decimal("1500")]):
        dval = calc.dispatch_value(meters, c0.fabric_return_price_per_meter)
        billed = calc.weaving_charges(meters, c0.weaving_rate)
        s.add(WvDispatch(
            tenant_id=tid,
            number=next_number(s, tid, "wv_dispatch", "WD", fmt="{prefix}-{YYYY}-{seq:04d}"),
            contract_id=c0.id,
            date=_past_days(_wv_days(12 - i * 4), today=today),
            meters=meters, dispatch_value=dval,
            weaving_charges_billed=billed,
            net_receivable=calc.net_receivable(dval, billed),
            created_by_id=user.id,
        ))

    # Light activity on completed contract (just after its start within the window)
    c1 = contracts[1]
    net = calc.net_kg(Decimal("260"), Decimal("10"))
    s.add(WvYarnInward(
        tenant_id=tid,
        number=next_number(s, tid, "wv_yarn_inward", "YI", fmt="{prefix}-{YYYY}-{seq:04d}"),
        contract_id=c1.id, yarn_type_id=yt.id,
        date=_past_days(max(1, int(span * 0.55)), today=today),
        gross_kg=Decimal("260"), tare_kg=Decimal("10"), net_kg=net,
        rate_per_kg=c1.assumed_yarn_rate_per_kg,
        yarn_value=net * c1.assumed_yarn_rate_per_kg,
        created_by_id=user.id,
    ))
    s.flush()


def seed_one_tenant(email: str, company_name: str, business_model: str) -> dict:
    """Create or update one demo tenant. Returns a small report dict."""
    random.seed(hash(email) & 0xFFFFFFFF)
    with Session(engine) as s:
        existing_user = s.exec(select(User).where(User.email == email)).first()
        if existing_user:
            tenant_id = existing_user.tenant_id
            tenant = s.get(Tenant, tenant_id)
            if tenant.business_model != business_model:
                tenant.business_model = business_model
            # Converge enabled_modules: a demo tenant must have at least its
            # model's default modules, else the features it demos stay hidden.
            # Union (not replace) so modules installed on top are preserved;
            # unknown legacy strings ("invoicing", …) are dropped.
            try:
                current = _json.loads(tenant.enabled_modules or "[]")
            except Exception:
                current = []
            defaults = set(MODULES_BY_MODEL.get(business_model, ["base"]))
            # PRA demo is a trader model but must expose the PRA nav/logs.
            if email == "demo.pra@easy-books.app":
                defaults.add("pra")
            merged = sorted(
                {m for m in current if m in MODULE_REGISTRY} | defaults
            )
            tenant.enabled_modules = _json.dumps(merged)
            s.add(tenant); s.commit()
        else:
            modules = list(MODULES_BY_MODEL.get(business_model, ["base"]))
            if email == "demo.pra@easy-books.app" and "pra" not in modules:
                modules.append("pra")
            tenant = Tenant(name=company_name, business_model=business_model,
                            base_currency="USD",
                            enabled_modules=_json.dumps(modules))
            s.add(tenant); s.commit(); s.refresh(tenant)
            tenant_id = tenant.id
            seed_data(tenant_id, session=s)

        # Top up any CoA accounts this tenant is missing (newer backbone
        # accounts only reach new tenants otherwise) — must precede the
        # advance/asset seeders that depend on 1260/2310/1090/4901.
        _ensure_coa(s, tenant_id, business_model)
        _set_party_types(s, tenant_id)
        # Seed starter product categories for tenants that pre-date the feature.
        _ensure_categories(s, tenant_id, business_model)
        s.commit()

        # Always (re)assert the demo credentials — convergent so a drifted
        # password or must_change flag never locks the demo account out.
        _get_or_make_user(s, email, "Demo User", tenant_id)
        s.commit()

        # Multiple actors so the Audit Log shows realistic attribution.
        # Accountant/clerk get non-owner roles so portal-mode features activate correctly.
        base, domain = email.split("@", 1)
        accountant = _get_or_make_user(s, f"{base}+accountant@{domain}", "Demo Accountant", tenant_id, role="accountant")
        clerk = _get_or_make_user(s, f"{base}+clerk@{domain}", "Demo Clerk", tenant_id, role="viewer")
        s.commit()
        owner = s.exec(select(User).where(User.email == email)).first()

        user = owner

        _seed_notification_settings(s, tenant_id)
        s.commit()

        customers = _seed_customers(s, tenant_id)
        vendors   = _seed_vendors(s, tenant_id)
        services, stock, custom_supp = _seed_products(s, tenant_id, business_model)
        all_products = services + stock + custom_supp
        s.commit()

        _seed_tax_codes(s, tenant_id)
        _seed_exchange_rates(s, tenant_id)
        _seed_bank_accounts(s, tenant_id)
        s.commit()

        payment_terms = _assign_payment_terms(s, tenant_id, customers, vendors)
        s.commit()

        bills    = _seed_bills(s, accountant, vendors, all_products, business_model,
                               payment_terms)
        s.commit()
        invoices = _seed_invoices(s, user, customers, all_products, business_model,
                                  payment_terms)
        s.commit()
        _seed_payments_received(s, user, invoices)
        _seed_bill_payments(s, accountant, bills)
        s.commit()
        _seed_manual_jvs(s, user)
        s.commit()
        _seed_recurring_templates(s, tenant_id)
        s.commit()

        # ── Improvement-roadmap modules (Sprint 7–12) ──
        _seed_analytic_accounts(s, tenant_id)
        _seed_budgets(s, tenant_id)
        s.commit()
        _seed_fixed_assets(s, user)
        s.commit()
        _seed_credit_notes(s, clerk, invoices)
        s.commit()
        _seed_purchase_orders(s, user, vendors, all_products)
        s.commit()
        if business_model == "services":
            _seed_deferred_revenue(s, user, invoices)
            s.commit()

        # ── Returns & Advances (Sprint 13) ──
        _seed_sales_returns(s, clerk, invoices)
        s.commit()
        _seed_purchase_returns(s, user, bills)
        s.commit()
        _seed_customer_advances(s, user, customers, invoices)
        _seed_vendor_advances(s, user, vendors, bills)
        s.commit()

        # ── Sales incentives + close/reconcile (gap-fill batch) ──
        _seed_promo_rules(s, tenant_id)
        s.commit()
        _seed_commissions(s, owner, [accountant, clerk])
        s.commit()
        _seed_accounting_periods(s, tenant_id)
        s.commit()
        _seed_reconciliations(s, tenant_id)
        _seed_bank_imports(s, tenant_id)
        s.commit()

        if business_model == "manufacturing":
            _seed_manufacturing(s, user, customers, stock, custom_supp)
            s.commit()
            _seed_purchase_store_chain(s, owner, accountant, clerk, vendors, all_products, invoices)
            s.commit()
            # Own guard — backfills Issue Register when the PD chain already existed.
            _seed_store_issues(s, owner, clerk, all_products)
            s.commit()
            _seed_weaving(s, user, customers, vendors)
            s.commit()

        if business_model == "telecom_franchise":
            _seed_telecom_franchise(s, user)
            s.commit()

        if business_model == "hospital":
            _seed_healthcare(s, user)
            s.commit()
            _seed_healthcare_store(s, user)
            s.commit()
            _seed_lab_serial_history(s, user)
            s.commit()
            _seed_dialysis(s, user)
            s.commit()

        # ── PRA e-Invoice demo (Pakistani retail trader) ───────────────────────
        if email == "demo.pra@easy-books.app":
            _seed_pra_settings(s, tenant_id)
            s.commit()
            # Replace customers/products with PRA-specific data (NTN/CNIC/PCT)
            pra_customers = _seed_pra_customers(s, tenant_id)
            s.commit()
            pra_products = _seed_pra_products(s, tenant_id)
            s.commit()
            # Stamp FINs on all already-seeded posted invoices
            all_invoices = s.exec(
                select(Invoice).where(Invoice.tenant_id == tenant_id)
            ).all()
            _stamp_pra_invoices(s, list(all_invoices))
            s.commit()
            _seed_pra_submission_logs(s, tenant_id)
            s.commit()

        # ── Starter saved report (Report Builder) ──────────────────────────────
        _seed_report_definitions(s, tenant_id, user)
        s.commit()

        # ── HRM: Employees, Payroll, Attendance ───────────────────────────────
        employees_hrm = _seed_employees(s, tenant_id, business_model)
        components_hrm = _seed_salary_components(s, tenant_id)
        s.commit()
        _seed_salary_structures(s, employees_hrm, components_hrm)
        s.commit()
        _seed_payroll_runs(s, tenant_id, user, employees_hrm, components_hrm)
        s.commit()
        _seed_attendance(s, tenant_id, employees_hrm)
        s.commit()

        return {
            "tenant":       company_name,
            "email":        email,
            "business_model": business_model,
            "tenant_id":    tenant_id,
            "customers":    len(s.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all()),
            "vendors":      len(s.exec(select(Vendor).where(Vendor.tenant_id == tenant_id)).all()),
            "products":     len(s.exec(select(Product).where(Product.tenant_id == tenant_id)).all()),
            "invoices":     len(s.exec(select(Invoice).where(Invoice.tenant_id == tenant_id)).all()),
            "bills":        len(s.exec(select(Bill).where(Bill.tenant_id == tenant_id)).all()),
            "transactions": len(s.exec(select(Transaction).where(Transaction.tenant_id == tenant_id)).all()),
            "bank_accounts":len(s.exec(select(BankAccount).where(BankAccount.tenant_id == tenant_id)).all()),
            "boms":         len(s.exec(select(BomHeader).where(BomHeader.tenant_id == tenant_id)).all()),
            "rate_plans":   len(s.exec(select(RatePlan).where(RatePlan.tenant_id == tenant_id)).all()),
            "grns":         len(s.exec(select(GoodsReceiptNote).where(GoodsReceiptNote.tenant_id == tenant_id)).all()),
            "production_orders": len(s.exec(select(ProductionOrder).where(ProductionOrder.tenant_id == tenant_id)).all()),
            "credit_notes": len(s.exec(select(CreditNote).where(CreditNote.tenant_id == tenant_id)).all()),
            "fixed_assets": len(s.exec(select(FixedAsset).where(FixedAsset.tenant_id == tenant_id)).all()),
            "budgets":      len(s.exec(select(Budget).where(Budget.tenant_id == tenant_id)).all()),
            "purchase_orders": len(s.exec(select(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id)).all()),
            "analytic_accounts": len(s.exec(select(AnalyticAccount).where(AnalyticAccount.tenant_id == tenant_id)).all()),
            "deferred_schedules": len(s.exec(select(DeferredRevenueSchedule).where(DeferredRevenueSchedule.tenant_id == tenant_id)).all()),
            "debit_notes": len(s.exec(select(DebitNote).where(DebitNote.tenant_id == tenant_id)).all()),
            "customer_advances": len(s.exec(select(CustomerAdvance).where(CustomerAdvance.tenant_id == tenant_id)).all()),
            "vendor_advances": len(s.exec(select(VendorAdvance).where(VendorAdvance.tenant_id == tenant_id)).all()),
            "employees":          len(s.exec(select(Employee).where(Employee.tenant_id == tenant_id)).all()),
            "payroll_runs":       len(s.exec(select(PayrollRun).where(PayrollRun.tenant_id == tenant_id)).all()),
            "attendance_records": len(s.exec(select(AttendanceRecord).where(AttendanceRecord.tenant_id == tenant_id)).all()),
            "promo_rules":        len(s.exec(select(PromoRule).where(PromoRule.tenant_id == tenant_id)).all()),
            "commission_entries": len(s.exec(select(CommissionLedger).where(CommissionLedger.tenant_id == tenant_id)).all()),
            "accounting_periods": len(s.exec(select(AccountingPeriod).where(AccountingPeriod.tenant_id == tenant_id)).all()),
            "reconciliations":    len(s.exec(select(Reconciliation).where(Reconciliation.tenant_id == tenant_id)).all()),
            "bank_imports":       len(s.exec(select(BankStatementImport).where(BankStatementImport.tenant_id == tenant_id)).all()),
            "pra_logs":           len(s.exec(select(PRASubmissionLog).where(PRASubmissionLog.tenant_id == tenant_id)).all()),
            "hc_patients":        len(s.exec(select(HcPatient).where(HcPatient.tenant_id == tenant_id)).all()),
            "hc_doctors":         len(s.exec(select(HcDoctor).where(HcDoctor.tenant_id == tenant_id)).all()),
            "hc_lab_orders":      len(s.exec(select(HcLabOrder).where(HcLabOrder.tenant_id == tenant_id)).all()),
            "hc_store_issues":    len(s.exec(select(HcStoreIssue).where(HcStoreIssue.tenant_id == tenant_id)).all()),
            "store_issues":       len(s.exec(select(StoreIssue).where(StoreIssue.tenant_id == tenant_id)).all()),
            "mm_accounts":        len(s.exec(select(MobileMoneyAccount).where(MobileMoneyAccount.tenant_id == tenant_id)).all()),
            "device_imeis":       len(s.exec(select(DeviceImei).where(DeviceImei.tenant_id == tenant_id)).all()),
            "postpaid":          len(s.exec(select(PostpaidConnection).where(PostpaidConnection.tenant_id == tenant_id)).all()),
            "airtime_stock":     len(s.exec(select(AirtimeStock).where(AirtimeStock.tenant_id == tenant_id)).all()),
        }


def seed_all_demos() -> list[dict]:
    reports = []
    for email, company, model in DEMO_TENANTS:
        try:
            reports.append(seed_one_tenant(email, company, model))
        except Exception as e:
            reports.append({"email": email, "error": str(e)})
    return reports


if __name__ == "__main__":
    import json
    results = seed_all_demos()
    print(json.dumps(results, indent=2, default=str))
