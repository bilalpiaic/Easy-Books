"""Seed five demo tenants (one per business model) with rich mock data spanning
a full calendar year.

Idempotent — if a demo tenant already exists, the script reuses it and
skips entities that are already present. Safe to re-run.

Data coverage (v2 — post-sprint upgrade):
  • All dates within the past 12 months (365-day rolling window)
  • 100 invoices + 100 bills per tenant, evenly spread month-by-month
  • Every model-specific COA account exercised (4010/4020/5100/5200/5030 etc.)
  • 2–3 bank accounts seeded per tenant
  • Payment terms randomly assigned to customers, vendors, invoices, bills
  • notes / internal_memo fields populated with realistic text
  • 60+ manual JVs covering all expense / revenue / balance-sheet accounts

Usage:
    PYTHONPATH=. uv run python -m scripts.seed_demo

Credentials:
    demo.simple@easy-books.app         / demo1234
    demo.services@easy-books.app       / demo1234
    demo.trader@easy-books.app         / demo1234
    demo.manufacturing@easy-books.app  / demo1234
    demo.telecom@easy-books.app        / demo1234
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from auth import get_password_hash
from db import engine, seed_data
from models import (
    Account, AuditLog, BankAccount, BomHeader, BomLine, Bill, BillLine,
    BillPayment, Customer, CustomerRatePlan, ExchangeRate, GRNLine,
    GoodsReceiptNote, InventoryLayer, Invoice, InvoiceLine, PaymentAllocation,
    PaymentReceived, PaymentTerm, Product, ProductionOrder, RatePlan,
    RecurringTemplate, SequenceCounter, StockLocation, TaxCode, Tenant, User,
    Vendor,
)
from models_telecom import (
    FcaEvent, FranchiseAgreement, KpiTarget, Operator, RetailOutlet,
    RsoAgent, SimActivation, TrackerAccount,
)
from routers.common import next_number
from services.franchise_posting import (
    post_commission_accrual, post_franchise_fee_amortisation,
    post_franchise_fee_capitalisation,
)
from services.inventory import consume_stock, record_movement, record_purchase
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
    ("demo.simple@easy-books.app",        "Demo Simple Co.",        "simple"),
    ("demo.services@easy-books.app",      "Demo Services Ltd.",     "services"),
    ("demo.trader@easy-books.app",        "Demo Trading Co.",       "trader"),
    ("demo.manufacturing@easy-books.app", "Demo Manufacturing Co.", "manufacturing"),
    ("demo.telecom@easy-books.app",       "Demo Telecom Franchise", "telecom_franchise"),
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


def _spread_dates(count: int, days_ago: int = 365, min_days_ago: int = 3) -> list[str]:
    """Return `count` ascending ISO date strings spread across the past
    `days_ago` days with ±3 day jitter so dates are not mechanically even."""
    today = date.today()
    dates: list[str] = []
    for i in range(count):
        # Even spacing across the window
        frac = i / max(count - 1, 1)
        base_days = int(days_ago - frac * (days_ago - min_days_ago))
        jitter = random.randint(-3, 3)
        days_back = max(min_days_ago, base_days + jitter)
        dates.append((today - timedelta(days=days_back)).isoformat())
    return sorted(dates)


def _due_date(issue: str, term_days: int) -> str:
    """Return due date string `term_days` after `issue`."""
    return (date.fromisoformat(issue) + timedelta(days=term_days)).isoformat()


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


def _get_or_make_user(s: Session, email: str, full_name: str, tenant_id: int) -> User:
    u = s.exec(select(User).where(User.email == email)).first()
    if u:
        return u
    u = User(
        email=email,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        full_name=full_name,
        tenant_id=tenant_id,
        role="owner",
    )
    s.add(u); s.flush()
    return u


def _account(s: Session, tenant_id: int, code: str) -> Optional[Account]:
    return s.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
    ).first()


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


def _seed_recurring_templates(s: Session, tenant_id: int) -> None:
    if s.exec(
        select(RecurringTemplate).where(RecurringTemplate.tenant_id == tenant_id)
    ).first():
        return
    today = date.today()
    templates = [
        ("Office Rent",        "monthly",   "5000", "1010", "Monthly office rent"),
        ("Internet & Phone",   "monthly",   "5000", "1010", "Connectivity"),
        ("Cleaning Services",  "monthly",   "5000", "1010", "Office cleaning"),
        ("Software Licenses",  "monthly",   "5000", "1010", "SaaS subscriptions"),
        ("Bookkeeping Fee",    "quarterly", "5000", "1010", "External bookkeeping"),
        ("Insurance Premium",  "yearly",    "5000", "1010", "Annual policy"),
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
    """Seed 2–3 bank accounts per tenant, linked to the Bank (1010) COA account."""
    existing = s.exec(
        select(BankAccount).where(BankAccount.tenant_id == tenant_id)
    ).all()
    if existing:
        return
    bank_coa = _account(s, tenant_id, "1010")
    cash_coa  = _account(s, tenant_id, "1000")

    configs = [
        ("Main Current Account", "Habib Bank Ltd.",  "1234-5678-9012", bank_coa),
        ("USD Operating Account", "Standard Chartered", "9876-5432-1098", bank_coa),
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


# ── Bills (purchase) ──────────────────────────────────────────────────────────


def _seed_bills(
    s: Session, user: User, vendors: list[Vendor], products: list[Product],
    business_model: str, payment_terms: list[PaymentTerm], count: int = 100,
) -> list[Bill]:
    tid = user.tenant_id
    existing = s.exec(select(Bill).where(Bill.tenant_id == tid)).all()
    if len(existing) >= count:
        return list(existing)

    dates = _spread_dates(count, days_ago=365, min_days_ago=5)
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

    dates = _spread_dates(count, days_ago=365, min_days_ago=5)
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
            entries = [EntryInput(account_id=ar.id, debit=total)]
            if gst_amount > 0 and gst_out:
                entries.append(EntryInput(account_id=rev_acc.id, credit=money(subtotal)))
                entries.append(EntryInput(account_id=gst_out.id, credit=gst_amount))
            else:
                entries.append(EntryInput(account_id=rev_acc.id, credit=total))
            txn = post_transaction(
                s, user, date=issue_date,
                description=f"Invoice {number} — {customer.name}",
                entries=entries,
                audit_entity_type="invoice",
                audit_detail={"number": number, "total": str(total)},
            )
            invoice.transaction_id = txn.id
            s.add(invoice)

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
    cash = _account(s, tid, "1010") or _account(s, tid, "1000")
    ar   = _account(s, tid, "1100")
    if not cash or not ar:
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

        pay = PaymentReceived(
            tenant_id=tid, invoice_id=inv.id, customer_name=inv.customer_name,
            payment_date=pay_date, amount=amount,
            method=random.choice(["bank", "cash", "cheque"]),
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
    cash = _account(s, tid, "1010") or _account(s, tid, "1000")
    ap   = _account(s, tid, "2000")
    if not cash or not ap:
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

        pay = BillPayment(
            tenant_id=tid, bill_id=bill.id, vendor_name=bill.vendor_name,
            payment_date=pay_date, amount=amount,
            method=random.choice(["bank", "cheque"]),
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
        )
        pay.transaction_id = txn.id
        s.add(pay)


# ── Manual JVs ────────────────────────────────────────────────────────────────


def _seed_manual_jvs(s: Session, user: User, count: int = 60) -> None:
    tid = user.tenant_id

    # Resolve accounts — fall back gracefully if a code doesn't exist for this model
    def acc(code: str) -> Optional[Account]:
        return _account(s, tid, code)

    cash       = acc("1010") or acc("1000")
    bank       = acc("1010") or acc("1000")
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

    jv_dates = _spread_dates(to_create, days_ago=365, min_days_ago=3)

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
    grn_dates = _spread_dates(grns_to_create, days_ago=360, min_days_ago=10)
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
            created_at=datetime.utcnow() - timedelta(days=random.randint(10, 300)),
        )
        s.add(po); s.flush()


# ── Telecom-franchise-specific ─────────────────────────────────────────────────


def _seed_telecom_franchise(s: Session, user: User) -> None:
    """Seed a full daily-operations slice: operator, tracker, load chain, RSO
    collections, SIM batch + activations, FCA events + target, and a franchise
    agreement with amortisation. Idempotent — skips if an operator exists."""
    tid = user.tenant_id
    if s.exec(select(Operator).where(Operator.tenant_id == tid)).first():
        return

    def acc_id(code: str) -> Optional[int]:
        a = _account(s, tid, code)
        return a.id if a else None

    today = date.today()
    setup_day = (today - timedelta(days=340)).isoformat()

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
            date=(today - timedelta(days=280)).isoformat(),
        )
    s.flush()
    post_rso_to_retail_transfer(
        s, user, rso=rsos[0], retail_outlet_id=outlets[0].id,
        amount=D("20000"), date=(today - timedelta(days=270)).isoformat(),
    )
    s.flush()

    if batch is not None:
        for i, r in enumerate(rsos):
            post_rso_sim_issue(
                s, user, rso=r, batch=batch, qty=20,
                retail_price=D("80"),
                date=(today - timedelta(days=250 - i)).isoformat(),
            )
            batch.qty_activated += 20
        s.add(batch)
    s.flush()

    for i, r in enumerate(rsos):
        post_rso_daily_collection(
            s, user, rso=r, load_portion=D("30000"), stock_portion=D("1500"),
            total_deposited=D("31500"),
            date=(today - timedelta(days=200 - i)).isoformat(),
        )
    s.flush()

    activations: list[SimActivation] = []
    for i in range(50):
        act = SimActivation(
            tenant_id=tid, operator_id=op.id,
            sim_number=f"0300{1000000 + i:07d}",
            batch_id=batch.id if batch else None,
            activation_date=(today - timedelta(days=300 - i * 6)).isoformat(),
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


# ── Driver ────────────────────────────────────────────────────────────────────


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
                s.add(tenant); s.commit()
        else:
            tenant = Tenant(name=company_name, business_model=business_model,
                            base_currency="USD")
            s.add(tenant); s.commit(); s.refresh(tenant)
            tenant_id = tenant.id
            seed_data(tenant_id, session=s)
            _get_or_make_user(s, email, "Demo User", tenant_id)

        s.commit()

        user = s.exec(select(User).where(User.email == email)).first()

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

        bills    = _seed_bills(s, user, vendors, all_products, business_model,
                               payment_terms)
        s.commit()
        invoices = _seed_invoices(s, user, customers, all_products, business_model,
                                  payment_terms)
        s.commit()
        _seed_payments_received(s, user, invoices)
        _seed_bill_payments(s, user, bills)
        s.commit()
        _seed_manual_jvs(s, user)
        s.commit()
        _seed_recurring_templates(s, tenant_id)
        s.commit()

        if business_model == "manufacturing":
            _seed_manufacturing(s, user, customers, stock, custom_supp)
            s.commit()

        if business_model == "telecom_franchise":
            _seed_telecom_franchise(s, user)
            s.commit()

        from models import Transaction
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
