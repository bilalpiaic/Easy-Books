"""Seed four demo tenants (one per business model) with rich mock data.

Idempotent — if a demo tenant already exists, the script reuses it and
skips entities that are already present. Safe to re-run.

Usage:
    PYTHONPATH=. .venv/bin/python -m scripts.seed_demo

Or programmatically:
    from scripts.seed_demo import seed_all_demos
    seed_all_demos()

Credentials (login at the configured frontend URL):
    demo.simple@easy-books.app         / demo1234
    demo.services@easy-books.app       / demo1234
    demo.trader@easy-books.app         / demo1234
    demo.manufacturing@easy-books.app  / demo1234
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
    Account, AuditLog, BomHeader, BomLine, Bill, BillLine, BillPayment, Customer,
    CustomerRatePlan, ExchangeRate, GRNLine, GoodsReceiptNote, InventoryLayer,
    Invoice, InvoiceLine, PaymentAllocation, PaymentReceived, Product,
    ProductionOrder, RatePlan, RecurringTemplate, SequenceCounter, StockLocation,
    TaxCode, Tenant, User, Vendor,
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


# ── Configuration ────────────────────────────────────────────────────────────

DEMO_PASSWORD = "demo1234"
DEMO_TENANTS = [
    ("demo.simple@easy-books.app",        "Demo Simple Co.",        "simple"),
    ("demo.services@easy-books.app",      "Demo Services Ltd.",     "services"),
    ("demo.trader@easy-books.app",        "Demo Trading Co.",       "trader"),
    ("demo.manufacturing@easy-books.app", "Demo Manufacturing Co.", "manufacturing"),
    ("demo.telecom@easy-books.app",       "Demo Telecom Franchise", "telecom_franchise"),
]

# Each list has 12+ entries — meets the "at least 10 of each" requirement.

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
# Manufacturing-specific
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
# Telecom-specific: physical inventory (SIMs, devices) + connectivity bundles
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


# ── Tiny helpers ──────────────────────────────────────────────────────────────


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
        c = Customer(tenant_id=tenant_id, name=name, email=name.lower().replace(" ", ".") + "@example.com")
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
        v = Vendor(tenant_id=tenant_id, name=name, email=name.lower().replace(" ", ".") + "@example.com")
        s.add(v); s.flush()
        out.append(v)
    return out


def _seed_products(
    s: Session, tenant_id: int, business_model: str
) -> tuple[list[Product], list[Product], list[Product]]:
    """Returns (service_products, stock_products, customer_supplied_products)."""
    services: list[Product] = []
    stock: list[Product] = []
    customer_supplied: list[Product] = []

    def upsert(code: str, name: str, unit: str, default_rate: Decimal, product_type: str) -> Product:
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
        # Telecom franchise replaces generic services with connectivity bundles
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
            # Some business models don't ship with input-GST (1250) etc. Skip.
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
        ("Office Rent",        "monthly",   "5000", "1000",  "Monthly office rent"),
        ("Internet & Phone",   "monthly",   "5000", "1000",  "Connectivity"),
        ("Cleaning Services",  "monthly",   "5000", "1000",  "Office cleaning"),
        ("Software Licenses",  "monthly",   "5000", "1000",  "SaaS subscriptions"),
        ("Bookkeeping Fee",    "quarterly", "5000", "1000",  "External bookkeeping"),
        ("Insurance Premium",  "yearly",    "5000", "1000",  "Annual policy"),
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


# ── Bills (purchase) ──────────────────────────────────────────────────────────


def _seed_bills(
    s: Session, user: User, vendors: list[Vendor], products: list[Product],
    business_model: str, count: int = 50,
) -> list[Bill]:
    tid = user.tenant_id
    existing = s.exec(select(Bill).where(Bill.tenant_id == tid)).all()
    if len(existing) >= count:
        return existing

    base_day = date.today() - timedelta(days=120)
    bills: list[Bill] = []
    ap = _account(s, tid, "2000")
    gst_input = _account(s, tid, "1250") or _account(s, tid, "2200")  # fallback

    purchasable = [p for p in products if p.product_type == "stock"] or products

    for i in range(count - len(existing)):
        bill_date = (base_day + timedelta(days=i * 7)).isoformat()
        vendor = vendors[i % len(vendors)]

        # Pick 1-3 lines
        n_lines = random.randint(1, 3)
        chosen = random.sample(purchasable, min(n_lines, len(purchasable)))
        subtotal = ZERO
        line_items: list[dict] = []
        for p in chosen:
            qty = D(random.randint(5, 20))
            rate = D(p.default_rate) / D(2) if p.default_rate > 0 else D(random.randint(2, 30))
            rate = money(rate if rate > 0 else D(5))
            amount = money(qty * rate)
            subtotal += amount
            line_items.append({"product": p, "qty": qty, "rate": rate, "amount": amount})

        gst_rate = D(17)
        gst_amount = money(subtotal * gst_rate / D(100))
        total = money(subtotal + gst_amount)

        number = next_number(s, tid, "bill", "BILL", width=4)

        bill = Bill(
            tenant_id=tid, number=number, vendor_id=vendor.id,
            vendor_name=vendor.name,
            bill_date=bill_date, due_date=(base_day + timedelta(days=i*7 + 30)).isoformat(),
            description=f"Purchase from {vendor.name}",
            subtotal=money(subtotal), gst_rate=gst_rate, gst_amount=gst_amount,
            total=total, currency="USD", exchange_rate=D(1),
            status="posted",
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

        # JE: Dr Expense / Inventory + Dr GST / Cr AP
        exp_acc = _account(s, tid, "5000") or _account(s, tid, "5010")
        entries = []
        if exp_acc:
            entries.append(EntryInput(account_id=exp_acc.id, debit=money(subtotal)))
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
    business_model: str, count: int = 50,
) -> list[Invoice]:
    tid = user.tenant_id
    existing = s.exec(select(Invoice).where(Invoice.tenant_id == tid)).all()
    if len(existing) >= count:
        return existing

    base_day = date.today() - timedelta(days=90)
    invoices: list[Invoice] = []
    ar = _account(s, tid, "1100")
    rev = _account(s, tid, "4000")
    gst_out = _account(s, tid, "2200")
    cogs = _account(s, tid, "5010")
    inv_acc = _account(s, tid, "1200") or _account(s, tid, "1202")

    sellable = [p for p in products if p.product_type in ("stock", "service")] or products

    for i in range(count - len(existing)):
        issue_date = (base_day + timedelta(days=i * 5)).isoformat()
        customer = customers[i % len(customers)]

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
                    pass  # not enough stock — skip silently for demo

        gst_rate = D(17)
        gst_amount = money(subtotal * gst_rate / D(100))
        total = money(subtotal + gst_amount)

        number = next_number(s, tid, "invoice", "INV", width=4)

        # Distribute statuses
        bucket = i % 4
        status = ("draft", "posted", "partial", "paid")[bucket]

        invoice = Invoice(
            tenant_id=tid, number=number, customer_id=customer.id,
            customer_name=customer.name,
            issue_date=issue_date, due_date=(base_day + timedelta(days=i*5 + 30)).isoformat(),
            description=f"Sale to {customer.name}",
            subtotal=money(subtotal), gst_rate=gst_rate, gst_amount=gst_amount,
            total=total, currency="USD", exchange_rate=D(1),
            status=status,
            ar_account_id=ar.id if ar else None,
            revenue_account_id=rev.id if rev else None,
        )
        s.add(invoice); s.flush()

        for li in line_items:
            s.add(InvoiceLine(
                invoice_id=invoice.id, product_id=li["product"].id,
                description=li["product"].name,
                qty=li["qty"], unit=li["product"].unit,
                rate=li["rate"], amount=li["amount"],
            ))

        # JE: Dr AR / Cr Revenue + Cr GST (only for non-draft)
        if status != "draft" and ar and rev:
            entries = [EntryInput(account_id=ar.id, debit=total)]
            if gst_amount > 0 and gst_out:
                entries.append(EntryInput(account_id=rev.id, credit=money(subtotal)))
                entries.append(EntryInput(account_id=gst_out.id, credit=gst_amount))
            else:
                entries.append(EntryInput(account_id=rev.id, credit=total))
            txn = post_transaction(
                s, user, date=issue_date,
                description=f"Invoice {number} — {customer.name}",
                entries=entries,
                audit_entity_type="invoice",
                audit_detail={"number": number, "total": str(total)},
            )
            invoice.transaction_id = txn.id
            s.add(invoice)

            # COGS sub-JV
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
    s: Session, user: User, invoices: list[Invoice], count: int = 50,
) -> None:
    tid = user.tenant_id
    posted_invoices = [i for i in invoices if i.status in ("posted", "partial", "paid")]
    if not posted_invoices:
        return
    existing = s.exec(select(PaymentReceived).where(PaymentReceived.tenant_id == tid)).all()
    if len(existing) >= count:
        return
    cash = _account(s, tid, "1010") or _account(s, tid, "1000")
    ar = _account(s, tid, "1100")
    if not cash or not ar:
        return

    base_day = date.today() - timedelta(days=60)
    for i, inv in enumerate(posted_invoices[:count - len(existing)]):
        ratio = D("0.5") if inv.status == "partial" else D("1.0") if inv.status == "paid" else D("1.0")
        amount = money(D(inv.total) * ratio)
        if amount <= 0:
            continue
        pay_date = (base_day + timedelta(days=i * 3)).isoformat()
        pay = PaymentReceived(
            tenant_id=tid, invoice_id=inv.id, customer_name=inv.customer_name,
            payment_date=pay_date, amount=amount, method="bank",
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
                EntryInput(account_id=ar.id, credit=amount),
            ],
            audit_entity_type="payment",
            audit_detail={"invoice": inv.number, "amount": str(amount)},
        )
        pay.transaction_id = txn.id
        s.add(pay)


def _seed_bill_payments(
    s: Session, user: User, bills: list[Bill], count: int = 50,
) -> None:
    tid = user.tenant_id
    existing = s.exec(select(BillPayment).where(BillPayment.tenant_id == tid)).all()
    if len(existing) >= count:
        return
    cash = _account(s, tid, "1010") or _account(s, tid, "1000")
    ap = _account(s, tid, "2000")
    if not cash or not ap:
        return

    base_day = date.today() - timedelta(days=45)
    for i, bill in enumerate(bills[:count - len(existing)]):
        amount = money(D(bill.total) * (D("0.7") if i % 3 == 0 else D("1.0")))
        if amount <= 0:
            continue
        pay_date = (base_day + timedelta(days=i * 3)).isoformat()
        pay = BillPayment(
            tenant_id=tid, bill_id=bill.id, vendor_name=bill.vendor_name,
            payment_date=pay_date, amount=amount, method="bank",
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
                EntryInput(account_id=ap.id, debit=amount),
                EntryInput(account_id=cash.id, credit=amount),
            ],
            audit_entity_type="bill_payment",
            audit_detail={"bill": bill.number, "amount": str(amount)},
        )
        pay.transaction_id = txn.id
        s.add(pay)


# ── Manual JVs ────────────────────────────────────────────────────────────────


def _seed_manual_jvs(s: Session, user: User, count: int = 50) -> None:
    tid = user.tenant_id
    base_day = date.today() - timedelta(days=365)

    cash      = _account(s, tid, "1010") or _account(s, tid, "1000")
    bank      = _account(s, tid, "1010") or _account(s, tid, "1000")
    rent      = _account(s, tid, "5000")
    capital   = _account(s, tid, "3000")
    drawings  = _account(s, tid, "3010")
    other_inc = _account(s, tid, "4900")
    depr_exp  = _account(s, tid, "5050")
    salary    = _account(s, tid, "5100") or _account(s, tid, "5000")
    util      = _account(s, tid, "5200") or _account(s, tid, "5000")
    adv       = _account(s, tid, "5300") or _account(s, tid, "5000")

    # Pattern pool — cycled to reach `count` entries
    patterns = [
        ("Owner capital injection",         capital,   bank,      D(50000)),
        ("Office rent payment",             rent,      cash,      D(1500)),
        ("Owner drawings",                  drawings,  cash,      D(800)),
        ("Other income — refund",           other_inc, bank,      D(450)),
        ("Depreciation charge",             depr_exp,  bank,      D(300)),
        ("Owner top-up capital",            capital,   bank,      D(10000)),
        ("Salary expense",                  salary,    cash,      D(3500)),
        ("Utility bill payment",            util,      cash,      D(280)),
        ("Advertising spend",               adv,       bank,      D(650)),
        ("Bank interest income",            bank,      other_inc, D(95)),
        ("Office supplies expense",         rent,      cash,      D(120)),
        ("Owner drawings — Q2",             drawings,  cash,      D(600)),
        ("Telephone & internet",            util,      cash,      D(180)),
        ("Staff overtime payment",          salary,    cash,      D(900)),
        ("Maintenance & repairs",           rent,      cash,      D(430)),
        ("Professional fees",               adv,       bank,      D(2000)),
        ("Travel & accommodation",          adv,       cash,      D(750)),
        ("Stationery & printing",           rent,      cash,      D(85)),
        ("Bank charges",                    rent,      bank,      D(35)),
        ("Miscellaneous income",            bank,      other_inc, D(200)),
        ("Security deposit paid",           capital,   bank,      D(5000)),
        ("Asset injection — owner",         capital,   bank,      D(25000)),
        ("Annual insurance premium",        adv,       bank,      D(1200)),
        ("Cleaning services",               rent,      cash,      D(240)),
        ("Software subscription",           adv,       bank,      D(300)),
        ("Courier & postage",               rent,      cash,      D(60)),
        ("Vehicle running expense",         util,      cash,      D(520)),
        ("Depreciation — equipment",        depr_exp,  bank,      D(400)),
        ("Festive bonuses",                 salary,    cash,      D(1500)),
        ("Marketing campaign",              adv,       bank,      D(3200)),
        ("Owner drawings — Q3",             drawings,  cash,      D(700)),
        ("Training & development",          adv,       bank,      D(800)),
        ("Fuel expense",                    util,      cash,      D(310)),
        ("Water charges",                   util,      cash,      D(90)),
        ("Electricity bill",                util,      cash,      D(460)),
        ("Legal & compliance fees",         adv,       bank,      D(1800)),
        ("Inventory write-off",             rent,      bank,      D(550)),
        ("Gain on asset disposal",          bank,      other_inc, D(1100)),
        ("Interest on loan",                rent,      bank,      D(620)),
        ("Owner drawings — Q4",             drawings,  cash,      D(850)),
        ("Yearend audit fee",               adv,       bank,      D(2500)),
        ("Office renovation",               rent,      bank,      D(4500)),
        ("Petty cash replenishment",        rent,      cash,      D(200)),
        ("Staff welfare",                   salary,    cash,      D(350)),
        ("Parking & toll fees",             util,      cash,      D(75)),
        ("Printing & design",               adv,       bank,      D(480)),
        ("Subscription renewal",            adv,       bank,      D(420)),
        ("Owner capital — final tranche",   capital,   bank,      D(15000)),
        ("Yearend depreciation adjustment", depr_exp,  bank,      D(500)),
    ]

    valid = [(desc, a, b, amt) for desc, a, b, amt in patterns if a and b and a.id != b.id]

    existing_jv_count = len(s.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tid,
            AuditLog.entity_type == "manual_jv",
        )
    ).all())
    to_create = max(0, count - existing_jv_count)

    for i in range(to_create):
        desc, dr_acc, cr_acc, base_amt = valid[i % len(valid)]
        cycle = i // len(valid)
        amt = money(base_amt + D(cycle * 50))
        d = (base_day + timedelta(days=i * 7)).isoformat()
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

    # Pick raw materials + finished goods
    raw = [p for p in stock_products if p.code and p.code.startswith("RM-")]
    fg  = [p for p in stock_products if p.code and p.code.startswith("FG-")]
    if not raw or not fg or not customer_supplied_products:
        return

    # 1. BoMs — one per finished good (3) + variations = 50+
    existing_boms = s.exec(select(BomHeader).where(BomHeader.tenant_id == tid)).all()
    if len(existing_boms) < 50:
        for i in range(50 - len(existing_boms)):
            output = fg[i % len(fg)]
            # Each BoM consumes 1-2 raw + 1 customer-supplied
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

    # 2. Rate plans — 50
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

    # 3. Assign first plan to each customer
    for c in customers:
        existing_assign = s.exec(
            select(CustomerRatePlan).where(
                CustomerRatePlan.tenant_id == tid, CustomerRatePlan.customer_id == c.id,
            )
        ).first()
        if existing_assign or not plan_objs:
            continue
        s.add(CustomerRatePlan(
            tenant_id=tid, customer_id=c.id, rate_plan_id=plan_objs[0].id, is_active=True,
        ))

    # 4. GRNs — 50, each receiving customer-supplied material
    godown = s.exec(
        select(StockLocation).where(
            StockLocation.tenant_id == tid, StockLocation.type == "customer_custodial",
        )
    ).first()
    if not godown:
        return
    existing_grns = s.exec(select(GoodsReceiptNote).where(GoodsReceiptNote.tenant_id == tid)).all()
    grn_objs: list[GoodsReceiptNote] = list(existing_grns)
    grns_to_create = max(0, 50 - len(existing_grns))
    base_day = date.today() - timedelta(days=80)
    for i in range(grns_to_create):
        customer = customers[i % len(customers)]
        cs = customer_supplied_products[i % len(customer_supplied_products)]
        qty = D(random.randint(20, 50))
        declared = D(random.randint(100, 500))
        number = next_number(s, tid, "grn", "GRN", width=4)
        grn = GoodsReceiptNote(
            tenant_id=tid, number=number, customer_id=customer.id,
            received_date=(base_day + timedelta(days=i * 6)).isoformat(),
            location_id=godown.id, declared_value=money(declared),
        )
        s.add(grn); s.flush()
        s.add(GRNLine(
            grn_id=grn.id, product_id=cs.id, qty=qty,
            lot_no=f"LOT-{i+1:03d}", declared_value=money(declared),
        ))
        # Custodial layer
        s.add(InventoryLayer(
            tenant_id=tid, product_id=cs.id, location_id=godown.id,
            owner_customer_id=customer.id, lot_no=f"LOT-{i+1:03d}",
            qty_received=qty, qty_remaining=qty, unit_cost=ZERO,
            source_doc=number,
        ))
        # Movement
        record_movement(
            s, tenant_id=tid, product_id=cs.id, direction="CUSTODIAL_RECEIPT",
            qty=qty, to_location_id=godown.id, lot_no=f"LOT-{i+1:03d}",
            owner_customer_id=customer.id,
            source_doc_type="grn", source_doc_id=grn.id, posted_to_gl=False,
        )
        # Memo JE
        memo_a = _account(s, tid, "1210")
        memo_l = _account(s, tid, "2150")
        if memo_a and memo_l and declared > 0:
            for acc in (memo_a, memo_l):
                if not acc.is_memo:
                    acc.is_memo = True; s.add(acc)
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

    # 5. Production orders — 50, distributed across states
    existing_pos = s.exec(select(ProductionOrder).where(ProductionOrder.tenant_id == tid)).all()
    pos_to_create = max(0, 50 - len(existing_pos))
    state_pattern = [
        "draft", "draft", "draft", "started", "started", "started",
        "completed", "completed", "delivered", "delivered",
        "billed", "billed", "billed", "cancelled", "draft",
    ]
    for i in range(pos_to_create):
        # Pick an active BoM
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
            output_qty=qty, state="draft",
            created_at=datetime.utcnow() - timedelta(days=30 - i),
        )
        s.add(po); s.flush()
        # Don't drive state transitions automatically — keep simple "draft" for now
        # so we don't deplete custodial stock or post extra JEs in seed.

    # The state pattern is left as is — most POs remain draft for demo simplicity.
    # Users can drive them through the lifecycle from the UI.


# ── Telecom-franchise-specific ──────────────────────────────────────────────


def _seed_telecom_franchise(s: Session, user: User) -> None:
    """Seed a full daily-operations slice: operator, tracker, load chain, RSO
    collections, SIM batch + activations, FCA events + target, and a franchise
    agreement with amortisation. Idempotent — skips if an operator exists."""
    tid = user.tenant_id
    if s.exec(select(Operator).where(Operator.tenant_id == tid)).first():
        return   # already seeded

    def acc_id(code: str) -> Optional[int]:
        a = _account(s, tid, code)
        return a.id if a else None

    today = date.today()
    setup_day = (today - timedelta(days=100)).isoformat()

    # 1. Operator — wired to the franchise CoA
    op = Operator(
        tenant_id=tid, name="Jazz", operator_code="JAZZ",
        contact_person="Franchise Desk", contact_phone="0300-1112223",
        commission_settlement_cycle="monthly",
        deposit_account_id=acc_id("1210"), load_account_id=acc_id("1211"),
        payable_account_id=acc_id("2010"), commission_account_id=acc_id("4020"),
    )
    s.add(op); s.flush()

    # 2. Tracker (MSR) account + initial deposit + load order (3% uplift)
    ta = TrackerAccount(tenant_id=tid, operator_id=op.id, account_number="3001234567")
    s.add(ta); s.flush()
    post_tracker_deposit(s, user, tracker_account=ta, amount=D("500000"),
                         date=setup_day, reference="Opening deposit")
    post_load_order(s, user, tracker_account=ta, cash_debit=D("300000"),
                    uplift_pct=D("3.00"), date=setup_day, reference="Initial load")
    s.flush()

    # 3. SIM stock procurement via tracker (creates a SIM batch)
    batch, _ = post_stock_debit(
        s, user, tracker_account=ta, inventory_account_code="1200",
        qty=200, unit_cost=D("50"), date=setup_day, batch_number="SIMB-0001",
    )
    s.flush()

    # 4. RSO agents + retail outlets
    rsos: list[RsoAgent] = []
    for name, terr in [("Imran Khan", "North Zone"), ("Sana Malik", "Central Zone"), ("Bilal Ahmed", "South Zone")]:
        r = RsoAgent(tenant_id=tid, name=name, territory=terr,
                     receivable_account_id=acc_id("1120"))
        s.add(r); s.flush()
        rsos.append(r)
    outlets: list[RetailOutlet] = []
    for i, r in enumerate(rsos):
        o = RetailOutlet(tenant_id=tid, rso_id=r.id, shop_name=f"{r.territory} Mobile Point",
                         owner_name=f"Owner {i+1}")
        s.add(o); s.flush()
        outlets.append(o)

    # 5. Distribute load: MSR → each RSO, then RSO → retail
    for r in rsos:
        post_msr_to_rso_transfer(s, user, tracker_account=ta, rso=r,
                                 amount=D("50000"), date=(today - timedelta(days=40)).isoformat())
    s.flush()
    post_rso_to_retail_transfer(s, user, rso=rsos[0], retail_outlet_id=outlets[0].id,
                                amount=D("20000"), date=(today - timedelta(days=38)).isoformat())
    s.flush()

    # 7. SIM issue to each RSO from the batch (20 SIMs @ 80 face = 1600 stock each)
    if batch is not None:
        for i, r in enumerate(rsos):
            post_rso_sim_issue(s, user, rso=r, batch=batch, qty=20,
                               retail_price=D("80"), date=(today - timedelta(days=26 - i)).isoformat())
            batch.qty_activated += 20
        s.add(batch)
    s.flush()

    # 6. RSO daily collections — load + stock kept consistent with what was issued
    #    (each RSO was issued 1600 of SIM stock; collect 1500 of it so the stock
    #    receivable stays a small positive balance rather than going negative).
    for i, r in enumerate(rsos):
        post_rso_daily_collection(
            s, user, rso=r, load_portion=D("30000"), stock_portion=D("1500"),
            total_deposited=D("31500"), date=(today - timedelta(days=20 - i)).isoformat(),
        )
    s.flush()

    # 8. SIM activations (some with commission accrued)
    activations: list[SimActivation] = []
    for i in range(50):
        act = SimActivation(
            tenant_id=tid, operator_id=op.id,
            sim_number=f"0300{1000000 + i:07d}",
            batch_id=batch.id if batch else None,
            activation_date=(today - timedelta(days=50 - i)).isoformat(),
            customer_name=f"Customer {i+1}", activation_type="prepaid" if i % 3 != 0 else "postpaid",
            status="active", commission_rate=D("150"), commission_status="pending",
        )
        s.add(act); s.flush()
        activations.append(act)
    for act in activations[:25]:
        post_commission_accrual(s, user, activation=act, amount=D("150"),
                                date=act.activation_date, revenue_account_code="4020")
    s.flush()

    # 9. FCA events this month + a monthly target
    month = today.strftime("%Y-%m")
    target = KpiTarget(tenant_id=tid, operator_id=op.id, target_month=f"{month}-01",
                       metric="fca", target_value=D("60"))
    s.add(target); s.flush()
    for i in range(50):
        day = min((i % 28) + 1, today.day if today.day > 0 else 1)
        s.add(FcaEvent(
            tenant_id=tid, msisdn=f"0301{2000000 + i:07d}",
            event_date=f"{month}-{day:02d}", source_channel="rso_retail",
            kpi_target_id=target.id,
        ))
    s.flush()
    # Target commission earned (credited back to tracker deposit)
    post_fca_target_commission(s, user, tracker_account=ta, amount=D("12000"),
                               date=(today - timedelta(days=2)).isoformat(), credit_to="tracker")
    s.flush()

    # 10. Franchise agreement + capitalise fee + one month amortisation
    ag = FranchiseAgreement(
        tenant_id=tid, operator_id=op.id, agreement_number="FA-2024-JAZZ",
        start_date=setup_day, franchise_fee_paid=D("600000"),
        royalty_rate_pct=D("5"), min_monthly_target=D("250000"),
        penalty_rate_pct=D("2"), amortisation_months=60,
        intangible_account_id=acc_id("1300"), amortisation_account_id=acc_id("5030"),
    )
    s.add(ag); s.flush()
    post_franchise_fee_capitalisation(s, user, agreement=ag, fee=D("600000"),
                                      date=setup_day)
    post_franchise_fee_amortisation(s, user, agreement=ag,
                                    date=(today - timedelta(days=5)).isoformat())
    s.flush()


# ── Driver ────────────────────────────────────────────────────────────────────


def seed_one_tenant(email: str, company_name: str, business_model: str) -> dict:
    """Create or update one demo tenant. Returns a small report dict."""
    random.seed(hash(email) & 0xFFFFFFFF)  # deterministic per tenant
    with Session(engine) as s:
        # Get or create tenant
        existing_user = s.exec(select(User).where(User.email == email)).first()
        if existing_user:
            tenant_id = existing_user.tenant_id
            tenant = s.get(Tenant, tenant_id)
            # Ensure business_model is set correctly
            if tenant.business_model != business_model:
                tenant.business_model = business_model
                s.add(tenant); s.commit()
        else:
            tenant = Tenant(name=company_name, business_model=business_model, base_currency="USD")
            s.add(tenant); s.commit(); s.refresh(tenant)
            tenant_id = tenant.id
            # Reuse the existing seed_data helper — it lays down the
            # business-model-specific CoA, stock locations, and counters.
            seed_data(tenant_id, session=s)
            _get_or_make_user(s, email, "Demo User", tenant_id)

        s.commit()

        # Seed everything else
        user = s.exec(select(User).where(User.email == email)).first()

        customers = _seed_customers(s, tenant_id)
        vendors = _seed_vendors(s, tenant_id)
        services, stock, custom_supp = _seed_products(s, tenant_id, business_model)
        all_products = services + stock + custom_supp
        s.commit()

        _seed_tax_codes(s, tenant_id)
        _seed_exchange_rates(s, tenant_id)
        s.commit()

        # Need accounts after commit
        bills = _seed_bills(s, user, vendors, all_products, business_model)
        s.commit()
        invoices = _seed_invoices(s, user, customers, all_products, business_model)
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

        # Report counts
        from models import Transaction
        return {
            "tenant": company_name,
            "email": email,
            "business_model": business_model,
            "tenant_id": tenant_id,
            "customers": len(s.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all()),
            "vendors":   len(s.exec(select(Vendor).where(Vendor.tenant_id == tenant_id)).all()),
            "products":  len(s.exec(select(Product).where(Product.tenant_id == tenant_id)).all()),
            "invoices":  len(s.exec(select(Invoice).where(Invoice.tenant_id == tenant_id)).all()),
            "bills":     len(s.exec(select(Bill).where(Bill.tenant_id == tenant_id)).all()),
            "transactions": len(s.exec(select(Transaction).where(Transaction.tenant_id == tenant_id)).all()),
            "boms":      len(s.exec(select(BomHeader).where(BomHeader.tenant_id == tenant_id)).all()),
            "rate_plans":len(s.exec(select(RatePlan).where(RatePlan.tenant_id == tenant_id)).all()),
            "grns":      len(s.exec(select(GoodsReceiptNote).where(GoodsReceiptNote.tenant_id == tenant_id)).all()),
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
