import json
import os
from typing import Optional
from sqlmodel import Session, SQLModel, create_engine, select
from models import Account, PaymentTerm, ProductCategory, SequenceCounter, Settings, StockLocation

DATABASE_URL = os.environ.get("DATABASE_URL")

# Neon (and most managed Postgres) require TLS. Prefer the Neon *pooled*
# connection string (`…-pooler.…neon.tech`) on Vercel — each invocation
# opens at most one connection (pool_size=1) so the pooler can multiplex.
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
        sep = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
else:
    _environment = (
        os.environ.get("ENVIRONMENT")
        or os.environ.get("APP_ENV")
        or os.environ.get("ENV")
        or "development"
    ).lower()
    _on_vercel = os.environ.get("VERCEL", "").lower() in ("1", "true")
    if _environment in ("production", "prod") or _on_vercel:
        raise RuntimeError(
            "DATABASE_URL environment variable must be set in production. "
            "Point it at Neon Postgres (pooled connection string). "
            "SQLite fallback is not supported for serverless deployments."
        )
    from sqlalchemy import event
    from local_config import configure_sqlite_connection, sqlite_connect_args, sqlite_path
    sqlite_url = f"sqlite:///{sqlite_path()}"
    engine = create_engine(sqlite_url, connect_args=sqlite_connect_args())
    event.listen(engine, "connect", lambda conn, _: configure_sqlite_connection(conn))

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

    admin_email = os.environ.get("SEED_ADMIN_EMAIL")
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD")
    company_name = os.environ.get("SEED_COMPANY_NAME", "My Company")

    with Session(engine) as session:
        from models import Tenant, User
        from auth import get_password_hash

        default_tenant = session.exec(select(Tenant)).first()
        if not default_tenant:
            default_tenant = Tenant(name=company_name)
            session.add(default_tenant)
            session.commit()
            session.refresh(default_tenant)

            seed_data(default_tenant.id, session=session)

            if admin_email and admin_password:
                admin_user = User(
                    email=admin_email,
                    hashed_password=get_password_hash(admin_password),
                    full_name="System Admin",
                    tenant_id=default_tenant.id,
                )
                session.add(admin_user)
                session.commit()
                session.refresh(admin_user)
                from services.memberships import ensure_membership
                ensure_membership(
                    session, user_id=admin_user.id, tenant_id=default_tenant.id, role="owner"
                )
                session.commit()
        elif admin_email and admin_password:
            existing = session.exec(select(User).where(User.email == admin_email)).first()
            if not existing:
                admin_user = User(
                    email=admin_email,
                    hashed_password=get_password_hash(admin_password),
                    full_name="System Admin",
                    tenant_id=default_tenant.id,
                )
                session.add(admin_user)
                session.commit()
                session.refresh(admin_user)
                from services.memberships import ensure_membership
                ensure_membership(
                    session, user_id=admin_user.id, tenant_id=default_tenant.id, role="owner"
                )
                session.commit()

        # SEED_DEMO=true seeds the demo *login* tenants here (empty — CoA only).
        # The standalone installers run scripts.autoseed_demo first to fully
        # populate them (so this block then no-ops); the desktop build sets
        # SEED_DEMO=false (load on demand via Settings → Sample / Demo Data).
        if os.environ.get("SEED_DEMO", "true").lower() == "true":
            demo_configs = [
                ("demo.simple@easy-books.app", "simple", "Demo - Simple", "Demo User"),
                ("demo.services@easy-books.app", "services", "Demo - Services", "Demo User"),
                ("demo.trader@easy-books.app", "trader", "Demo - Trader", "Demo User"),
                ("demo.manufacturing@easy-books.app", "manufacturing", "Demo - Manufacturing", "Demo User"),
                ("demo.telecom@easy-books.app", "telecom_franchise", "Demo - Telecom Franchise", "Demo User"),
                ("demo.pra@easy-books.app", "trader", "Lahore Retail Traders (PRA Demo)", "Demo User"),
                ("demo.hospital@easy-books.app", "hospital", "City General Hospital (Demo)", "Demo User"),
                ("demo.spinning@easy-books.app", "yarn_spinning", "Demo - Yarn Spinning Mill", "Demo User"),
                ("demo.processing@easy-books.app", "textile_processing", "Demo - Textile Processing Unit", "Demo User"),
            ]
            demo_password_hash = get_password_hash("demo1234")
            created = 0

            for email, model, company, full_name in demo_configs:
                demo_user = session.exec(select(User).where(User.email == email)).first()
                if not demo_user:
                    demo_tenant = Tenant(
                        name=company,
                        business_model=model,
                        enabled_modules=json.dumps(MODULES_BY_MODEL.get(model, ["base"])),
                    )
                    from services.saas import apply_plan_defaults
                    apply_plan_defaults(demo_tenant, "enterprise")
                    session.add(demo_tenant)
                    session.commit()
                    session.refresh(demo_tenant)

                    seed_data(demo_tenant.id, session=session)

                    demo_user = User(
                        email=email,
                        hashed_password=demo_password_hash,
                        full_name=full_name,
                        tenant_id=demo_tenant.id,
                        role="owner",
                    )
                    session.add(demo_user)
                    session.commit()
                    session.refresh(demo_user)
                    from services.memberships import ensure_membership
                    ensure_membership(
                        session, user_id=demo_user.id, tenant_id=demo_tenant.id, role="owner"
                    )
                    session.commit()
                    created += 1

            total = len(
                session.exec(
                    select(User).where(User.email.in_([c[0] for c in demo_configs]))
                ).all()
            )
            print(
                f"[seed] SEED_DEMO=true: {created} demo account(s) created this boot, "
                f"{total} present (login demo.simple@easy-books.app / demo1234, or demo.hospital@easy-books.app for Healthcare demo)",
                flush=True,
            )
        else:
            print(
                "[seed] SEED_DEMO=false: starting empty "
                "(no demo accounts; the first signup becomes the owner)",
                flush=True,
            )

        # Existing mill demo tenants pre-date the Weighbridge grant; converge
        # every boot so Marketplace shows the card after a code-only deploy.
        _ensure_mill_weighbridge_grants(session)
        # yarn_spinning tenants created before the spinning module (or after a
        # plan-entitlements deploy that left enabled_modules stale) get the
        # first-party spinning workspace back without a re-seed.
        _ensure_yarn_spinning_module(session)
        # Existing mill demos pre-date the first-party Weighbridge workspace;
        # install the module when the tenant is already allowed to have it.
        _ensure_mill_weighbridge_module(session)

        # Convergent backfill: tag any product left without a category against
        # its tenant's sub-categories. Handles products created before the
        # category feature (or by an older seeder). One-time-effective and a
        # cheap no-op once every product is tagged.
        _backfill_untagged_products(session)

def _ensure_yarn_spinning_module(session: Session) -> None:
    """Restore spinning on ``yarn_spinning`` tenants that may already install it.

    Nav / Ctrl+K / ``/spinning/*`` gate on ``enabled_modules``. A code-only
    deploy must not leave an already-allowed mill tenant as Base-only.

    Does **not** mint ``module_meta.spinning.entitled`` (ops-only via
    ``PUT /api/ops/tenants/{id}/entitled``). ``business_model`` is tenant-
    writable, so treating it as a commercial grant would let a free/pro
    admin PATCH to ``yarn_spinning`` and pick up the industry pack on reboot.
    """
    from models import Tenant
    from routers.modules import _get_enabled, install_module_for_tenant
    from services.entitlements import can_install

    mills = session.exec(
        select(Tenant).where(Tenant.business_model == "yarn_spinning")
    ).all()
    restored = 0
    for tenant in mills:
        try:
            if "spinning" in _get_enabled(tenant):
                continue
            if not can_install(tenant, "spinning"):
                continue
            install_module_for_tenant(session, tenant, None, "spinning")
            restored += 1
        except Exception as exc:
            print(
                f"[seed] spinning backfill failed for tenant {tenant.id}: {exc}",
                flush=True,
            )
    if restored:
        print(
            f"[seed] restored Yarn Spinning module on {restored} yarn_spinning tenant(s)",
            flush=True,
        )


def _ensure_mill_weighbridge_module(session: Session) -> None:
    """Install first-party Weighbridge on mill tenants that may already have it.

    Nav / Ctrl+K / ``/weighbridge/*`` gate on ``enabled_modules``. A code-only
    deploy must not leave an entitled mill tenant without the workspace.

    Does **not** mint ``module_meta.weighbridge.entitled`` (ops-only).
    ``business_model`` is tenant-writable, so treating it as a commercial grant
    would let a free/pro admin PATCH to manufacturing and pick up the pack.
    """
    from models import Tenant
    from routers.modules import _get_enabled, install_module_for_tenant
    from services.entitlements import can_install
    from services.marketplace.catalog import MILL_WEIGHBRIDGE_MODELS

    mills = session.exec(
        select(Tenant).where(Tenant.business_model.in_(list(MILL_WEIGHBRIDGE_MODELS)))
    ).all()
    restored = 0
    for tenant in mills:
        try:
            if "weighbridge" in _get_enabled(tenant):
                continue
            if not can_install(tenant, "weighbridge"):
                continue
            install_module_for_tenant(session, tenant, None, "weighbridge")
            restored += 1
        except Exception as exc:
            print(
                f"[seed] weighbridge backfill failed for tenant {tenant.id}: {exc}",
                flush=True,
            )
    if restored:
        print(
            f"[seed] restored Weighbridge module on {restored} mill tenant(s)",
            flush=True,
        )


def _ensure_mill_weighbridge_grants(session: Session) -> None:
    """Idempotent mill grant. Listing is public; grants remain for ops/history."""
    from models import Tenant
    from services.marketplace.catalog import (
        MILL_WEIGHBRIDGE_MODELS,
        WEIGHBRIDGE_ID,
        grant_private_listing,
        private_listing_ids,
    )

    mills = session.exec(
        select(Tenant).where(Tenant.business_model.in_(list(MILL_WEIGHBRIDGE_MODELS)))
    ).all()
    dirty = False
    for tenant in mills:
        if WEIGHBRIDGE_ID in private_listing_ids(tenant):
            continue
        grant_private_listing(tenant, WEIGHBRIDGE_ID)
        session.add(tenant)
        dirty = True
    if dirty:
        session.commit()


def _backfill_untagged_products(session: Session):
    """Assign every product with no category_id to a sub-category of its tenant
    (oldest-first, round-robin). Idempotent: skips tenants with no categories,
    and no-ops entirely once all products are tagged."""
    from models import Product, ProductCategory

    untagged = session.exec(
        select(Product).where(Product.category_id.is_(None))
    ).all()
    if not untagged:
        return

    by_tenant: dict[int, list] = {}
    for p in untagged:
        by_tenant.setdefault(p.tenant_id, []).append(p)

    tagged = 0
    for tid, prods in by_tenant.items():
        subs = session.exec(
            select(ProductCategory).where(
                ProductCategory.tenant_id == tid,
                ProductCategory.parent_id.is_not(None),
            ).order_by(ProductCategory.id)
        ).all()
        cats = subs or session.exec(
            select(ProductCategory).where(
                ProductCategory.tenant_id == tid
            ).order_by(ProductCategory.id)
        ).all()
        if not cats:
            continue  # tenant has no categories to assign to
        for i, p in enumerate(prods):
            p.category_id = cats[i % len(cats)].id
            session.add(p)
            tagged += 1
    if tagged:
        session.commit()
        print(f"[seed] backfilled category on {tagged} untagged product(s)", flush=True)

def get_session():
    with Session(engine) as session:
        yield session

def get_tenant_session(tenant_id: int):
    with Session(engine) as session:
        yield session

# Per-business-model Chart of Accounts templates.
# Groups: (code, name, type) — inserted as is_group=True, parent resolved via _GROUP_PARENT.
# Leaves: (code, name, type, is_memo, parent_code) — inserted as is_group=False.
# The four _EXTRA lists layer on top of _COA_COMMON (same de-dup by code).

_COA_GROUPS: list[tuple[str, str, str]] = [
    ("1", "Assets", "Asset"),
    ("11", "Current Assets", "Asset"),
    ("12", "Non-Current Assets", "Asset"),
    ("2", "Liabilities", "Liability"),
    ("21", "Current Liabilities", "Liability"),
    ("3", "Equity", "Equity"),
    ("4", "Revenue", "Revenue"),
    ("41", "Operating Revenue", "Revenue"),
    ("49", "Other Income", "Revenue"),
    ("5", "Expenses", "Expense"),
    ("51", "Cost of Sales", "Expense"),
    ("52", "Operating Expenses", "Expense"),
    ("59", "Other Expenses", "Expense"),
]
_GROUP_PARENT: dict[str, "str | None"] = {
    "1": None, "11": "1", "12": "1",
    "2": None, "21": "2",
    "3": None,
    "4": None, "41": "4", "49": "4",
    "5": None, "51": "5", "52": "5", "59": "5",
}
_COA_COMMON: list[tuple[str, str, str, bool, str]] = [
    ("1000", "Cash in Hand",            "Asset",     False, "11"),
    ("1010", "Bank",                    "Asset",     False, "11"),
    ("1090", "Accumulated Depreciation","Asset",     False, "12"),
    ("1500", "PPE — Furniture & Equipment", "Asset", False, "12"),
    ("1510", "Right-of-use Asset",      "Asset",     False, "12"),
    ("1511", "Accum. Dep. — RoU",       "Asset",     False, "12"),
    ("1100", "Accounts Receivable",     "Asset",     False, "11"),
    ("1140", "Contract Asset (Unbilled)", "Asset",    False, "11"),
    ("1180", "Due from Affiliates",     "Asset",     False, "11"),
    ("1260", "Advances to Vendors",     "Asset",     False, "11"),
    ("2000", "Accounts Payable",        "Liability", False, "21"),
    ("2180", "Due to Affiliates",       "Liability", False, "21"),
    ("2200", "GST Payable (Output)",    "Liability", False, "21"),
    ("2250", "Salaries Payable",        "Liability", False, "21"),
    ("2265", "Withholding Tax Payable", "Liability", False, "21"),
    ("2310", "Customer Advances",       "Liability", False, "21"),
    ("2510", "Lease Liability",         "Liability", False, "21"),
    ("3000", "Owner Capital",           "Equity",    False, "3"),
    ("3010", "Drawings",                "Equity",    False, "3"),
    ("3100", "Retained Earnings",       "Equity",    False, "3"),
    ("4000", "Sales Revenue",           "Revenue",   False, "41"),
    ("4900", "Other Income",            "Revenue",   False, "49"),
    ("4901", "Unrealised FX Gain/Loss", "Revenue",   False, "49"),
    ("4903", "Realised FX Gain/Loss",   "Revenue",   False, "49"),
    ("4904", "Gain on Asset Disposal",  "Revenue",   False, "49"),
    ("5000", "General Expenses",        "Expense",   False, "52"),
    ("5050", "Depreciation Expense",    "Expense",   False, "52"),
    ("5061", "Impairment Loss",         "Expense",   False, "52"),
    ("5062", "Loss on Asset Disposal",  "Expense",   False, "52"),
    ("5100", "Salary Expense",          "Expense",   False, "52"),
    ("5125", "Lease Interest Expense",  "Expense",   False, "52"),
    ("5155", "Withholding Tax Expense", "Expense",   False, "52"),
    ("5900", "Other Expenses",          "Expense",   False, "59"),
]

# Service-style add-ons: time-based revenue + deferred revenue
_COA_SERVICES_EXTRA: list[tuple[str, str, str, bool, str]] = [
    ("4010", "Consulting Revenue",        "Revenue",   False, "41"),
    ("4020", "Recurring Service Revenue", "Revenue",   False, "41"),
    ("2300", "Deferred Revenue",          "Liability", False, "21"),
    ("5110", "Subcontractor Costs",       "Expense",   False, "51"),
]

# Trader extras: finished-goods inventory + COGS + input GST
_COA_TRADER_EXTRA: list[tuple[str, str, str, bool, str]] = [
    ("1200", "Finished Goods Inventory", "Asset",   False, "11"),
    ("1250", "GST Receivable (Input)",   "Asset",   False, "11"),
    ("5010", "Cost of Goods Sold",       "Expense", False, "51"),
    ("5020", "Freight In",               "Expense", False, "51"),
    ("5030", "Storage & Handling",       "Expense", False, "51"),
    ("5040", "Inventory Adjustments",    "Expense", False, "51"),
]

# Manufacturing extras: raw materials, WIP, custodial pair, labour, overhead
_COA_MANUFACTURING_EXTRA: list[tuple[str, str, str, bool, str]] = [
    ("1200", "Raw Material Inventory",   "Asset",     False, "11"),
    ("1201", "Work-in-Progress",         "Asset",     False, "11"),
    ("1202", "Finished Goods Inventory", "Asset",     False, "11"),
    ("1210", "Customer Goods on Hand",   "Asset",     True,  "11"),
    ("1250", "GST Receivable (Input)",   "Asset",     False, "11"),
    ("2150", "Customer Goods Liability", "Liability", True,  "21"),
    ("4010", "Service Revenue (Value-Add)", "Revenue", False, "41"),
    ("5010", "Cost of Goods Sold",       "Expense",   False, "51"),
    ("5100", "Direct Labour",            "Expense",   False, "51"),
    ("5110", "Subcontractor Costs",      "Expense",   False, "51"),
    ("5200", "Manufacturing Overhead",   "Expense",   False, "51"),
    ("5210", "Indirect Materials",       "Expense",   False, "51"),
]

# Telecom-Franchise CoA — combines the corrected operational model (Tracker
# deposits, load float, MSR→RSO→Retail chain, FCA target commission) with the
# extension blueprint (mobile money agency, postpaid billing, IMEI/device
# sales, commission accrual workflow, franchise fee amortisation, RSO
# channel). Codes follow BLUEPRINT.md numbering; descriptions match the
# §3 (Telecom Extension) and §4 (Corrected) reference tables.
_COA_TELECOM_FRANCHISE_EXTRA: list[tuple[str, str, str, bool, str]] = [
    # ── Assets ──────────────────────────────────────────────────────────
    ("1110", "Commission Receivable",         "Asset",     False, "11"),
    ("1120", "RSO Receivables",               "Asset",     False, "11"),
    ("1130", "Postpaid Customer Receivable",  "Asset",     False, "11"),
    ("1200", "SIM Card Inventory",            "Asset",     False, "11"),
    ("1201", "Scratch Card / PIN Inventory",  "Asset",     False, "11"),
    ("1202", "Device Inventory",              "Asset",     False, "11"),
    ("1203", "Bundle Code Inventory",         "Asset",     False, "11"),
    ("1204", "IMSI Inventory",                "Asset",     False, "11"),
    ("1210", "Tracker Deposit Balance",       "Asset",     False, "11"),
    ("1211", "Load Float Asset (MSR SIM)",    "Asset",     False, "11"),
    ("1212", "RSO Load Receivable",           "Asset",     False, "11"),
    ("1213", "Retail Load Receivable",        "Asset",     False, "11"),
    ("1214", "Mobile Money Float Asset",      "Asset",     False, "11"),
    ("1250", "GST Receivable (Input)",        "Asset",     False, "11"),
    ("1300", "Franchise Intangible Asset",    "Asset",     False, "12"),
    ("1301", "Accumulated Amortisation",      "Asset",     False, "12"),
    # ── Liabilities ─────────────────────────────────────────────────────
    ("2010", "Operator Payable",              "Liability", False, "21"),
    ("2100", "Mobile Money Float Liability",  "Liability", False, "21"),
    ("2110", "Postpaid Collections Payable",  "Liability", False, "21"),
    ("2120", "Franchise Royalty Payable",     "Liability", False, "21"),
    ("2300", "Advance from Operator",         "Liability", False, "21"),
    # ── Revenue ─────────────────────────────────────────────────────────
    ("4000", "Airtime / Recharge Revenue",        "Revenue", False, "41"),
    ("4010", "SIM Activation Revenue",            "Revenue", False, "41"),
    ("4020", "Load Uplift Commission (3%)",       "Revenue", False, "41"),
    ("4021", "Commission Income — Recharges",     "Revenue", False, "41"),
    ("4022", "Commission Income — Digital (MM)",  "Revenue", False, "41"),
    ("4023", "Commission Income — Bundles",       "Revenue", False, "41"),
    ("4030", "SIM Sale Revenue",                  "Revenue", False, "41"),
    ("4031", "Device Sales Revenue",              "Revenue", False, "41"),
    ("4040", "Postpaid Billing Revenue",          "Revenue", False, "41"),
    ("4050", "RSO Channel Revenue",               "Revenue", False, "41"),
    ("4060", "FCA Target Commission",             "Revenue", False, "41"),
    ("4061", "Franchise Incentive Income",        "Revenue", False, "49"),
    # ── Expenses ────────────────────────────────────────────────────────
    ("5010", "COGS — Devices",                    "Expense", False, "51"),
    ("5011", "COGS — SIMs",                       "Expense", False, "51"),
    ("5012", "COGS — Scratch Cards",              "Expense", False, "51"),
    ("5020", "RSO Incentives & Commissions",      "Expense", False, "52"),
    ("5021", "Retail Incentives",                 "Expense", False, "52"),
    ("5030", "Franchise Fee Amortisation",        "Expense", False, "52"),
    ("5040", "Franchise Royalty Expense",         "Expense", False, "52"),
    ("5060", "Mobile Money Transaction Costs",    "Expense", False, "52"),
    ("5070", "Tracker / Float Variance",          "Expense", False, "52"),
    ("5080", "Bad Debt — RSO Channel",            "Expense", False, "52"),
    ("5090", "Target Shortfall Penalties",        "Expense", False, "52"),
]


# Textile Processing CoA — process revenue, wastage sales, contractor labor, shrinkage.
# 5220/5215 avoid colliding with manufacturing 5200 (OH) / 5210 (indirect materials).
# Custodial 1210/2150 pair mirrors manufacturing GRN for customer-owned grey.
_COA_TEXTILE_PROCESSING_EXTRA: list[tuple[str, str, str, bool, str]] = [
    ("1210", "Customer Goods on Hand",     "Asset",     True,  "11"),
    ("2150", "Customer Goods Liability",   "Liability", True,  "21"),
    ("4150", "Processing Revenue",         "Revenue", False, "41"),
    ("4160", "Wastage Sales Revenue",      "Revenue", False, "41"),
    ("5220", "Contractor Labor Expense",   "Expense", False, "52"),
    ("5215", "Process Shrinkage Expense",  "Expense", False, "52"),
]

# Yarn Spinning CoA — stage WIP sub-accounts + waste + FG yarn + sales revenue
_COA_YARN_SPINNING_EXTRA: list[tuple[str, str, str, bool, str]] = [
    ("1200", "Raw Cotton / Fiber Inventory", "Asset",     False, "11"),
    ("1201", "WIP — Opening & Carding",      "Asset",     False, "11"),
    ("1202", "WIP — Drawing & Roving",       "Asset",     False, "11"),
    ("1203", "WIP — Ring Spinning",          "Asset",     False, "11"),
    ("1204", "Finished Yarn Inventory",      "Asset",     False, "11"),
    ("1250", "GST Receivable (Input)",       "Asset",     False, "11"),
    ("4170", "Yarn Sales Revenue",           "Revenue",   False, "41"),
    ("5010", "Cost of Goods Sold",           "Expense",   False, "51"),
    ("5100", "Direct Labour",                "Expense",   False, "51"),
    ("5200", "Manufacturing Overhead",       "Expense",   False, "51"),
    ("5901", "Hard Waste / Flat Strips",     "Expense",   False, "59"),
    ("5902", "Soft Waste / Noil",            "Expense",   False, "59"),
    ("5903", "Pneumafil / Dust Waste",       "Expense",   False, "59"),
    ("5904", "Moisture / Conditioning Loss", "Expense",   False, "59"),
]

# Healthcare CoA — patient AR, deposit liability, multi-stream revenue, supply expenses
_COA_HEALTHCARE_EXTRA: list[tuple[str, str, str, bool, str]] = [
    # Assets
    ("1102", "Lab Receivable",              "Asset",     False, "11"),
    ("1200", "Medical Supplies Inventory",  "Asset",     False, "11"),
    ("1250", "GST Receivable (Input)",      "Asset",     False, "11"),
    # Liabilities
    ("2310", "Patient Advance / Deposit",   "Liability", False, "21"),
    # Revenue — OPD
    ("4100", "OPD Consultation Revenue",    "Revenue",   False, "41"),
    ("4101", "OPD Follow-up Revenue",       "Revenue",   False, "41"),
    # Revenue — Lab
    ("4110", "Laboratory Revenue",          "Revenue",   False, "41"),
    ("4111", "Sample Collection Revenue",   "Revenue",   False, "41"),
    # Revenue — IPD / Procedures
    ("4120", "Surgical / Procedure Revenue","Revenue",   False, "41"),
    ("4121", "Ward / Bed Charges Revenue",  "Revenue",   False, "41"),
    ("4122", "Nursing & Allied Services",   "Revenue",   False, "41"),
    ("4130", "Pharmacy Revenue",            "Revenue",   False, "41"),
    # Expenses
    ("5010", "Cost of Medicines Sold",      "Expense",   False, "51"),
    ("5120", "Medical Supplies & Consumables","Expense", False, "52"),
    ("5130", "Lab Reagents & Chemicals",    "Expense",   False, "52"),
]


def _coa_for(business_model: str):
    """CoA template: shared group set + universal leaves + model leaves.
    Returns (code, name, type, is_memo, parent_code, is_group); groups first
    so parents precede children in the two-pass insert."""
    groups = [
        (code, name, gtype, False, _GROUP_PARENT[code], True)
        for (code, name, gtype) in _COA_GROUPS
    ]
    by_code = {a[0]: a for a in _COA_COMMON}
    extra_map = {
        "services":          _COA_SERVICES_EXTRA,
        "trader":            _COA_TRADER_EXTRA,
        "manufacturing":     _COA_MANUFACTURING_EXTRA,
        "telecom_franchise": _COA_TELECOM_FRANCHISE_EXTRA,
        "hospital":          _COA_HEALTHCARE_EXTRA,
        "yarn_spinning":     _COA_YARN_SPINNING_EXTRA,
        "textile_processing": _COA_TEXTILE_PROCESSING_EXTRA,
    }
    for row in extra_map.get(business_model, []):
        by_code[row[0]] = row
    leaves = [(c, n, t, m, p, False) for (c, n, t, m, p) in by_code.values()]
    return sorted(groups, key=lambda r: (len(r[0]), r[0])) + sorted(leaves, key=lambda r: r[0])


# ── Module Registry ──────────────────────────────────────────────────────────
# Single source of truth for every installable module.
# Fields:
#   label       Human-readable name shown in the Apps page
#   description One-line description shown on the module card
#   category    Groups modules on the Apps page (Core / Accounting / Operations / HR / Industry)
#   icon        lucide-react icon name (used by frontend)
#   deps        Module IDs that must be installed first
#   always      If True, the module cannot be uninstalled (locked)
#   default     If True, installed on every new tenant regardless of business_model
#   tier        "free" | "pro" | "enterprise" — reserved for future billing
#   nav_sections Sidebar sections this module adds (informational; frontend drives the actual filter)
MODULE_REGISTRY: dict[str, dict] = {
    "base": {
        "label":       "Base Accounting",
        "description": "Core GL, Chart of Accounts, journal entries, AR/AP, banking, and all financial reports. Required by every other module.",
        "category":    "Core",
        "icon":        "BookOpen",
        "deps":        [],
        "always":      True,
        "default":     True,
        "tier":        "free",
        "nav_sections": ["Overview", "Ledger", "Receivable", "Payable", "Banking", "Reports"],
    },
    "inventory": {
        "label":       "Inventory",
        "description": "Products, product categories, stock locations, product ledger, and inventory performance analytics.",
        "category":    "Operations",
        "icon":        "Package",
        "deps":        ["base"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Inventory"],
    },
    "production": {
        "label":       "Manufacturing",
        "description": "Bills of Material, Production Orders, Goods Receipt Notes, Rate Plans, and job-costing reports.",
        "category":    "Operations",
        "icon":        "Factory",
        "deps":        ["inventory"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Manufacturing"],
    },
    "hrm": {
        "label":       "HRM & Payroll",
        "description": "Employee master, salary components, payroll runs with GL posting, attendance register, and printable payslips.",
        "category":    "HR",
        "icon":        "Users",
        "deps":        ["base"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Payroll"],
    },
    "telecom": {
        "label":       "Telecom Franchise",
        "description": "Franchise wallet (Tracker), MSR/RSO distributor chain, SIM & airtime, FCA targets, mobile money, and postpaid billing.",
        "category":    "Industry",
        "icon":        "Radio",
        "deps":        ["inventory"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Telecom"],
    },
    "pra": {
        "label":       "PRA e-Invoice",
        "description": "Punjab Revenue Authority real-time invoice submission (Pakistan), Fiscal Invoice Numbers, portal mode, NTN/CNIC fields, and PCT product codes.",
        "category":    "Industry",
        "icon":        "FileCheck",
        "deps":        ["base"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["PRA"],
    },
    "uae_vat": {
        "label":       "UAE VAT e-Invoice",
        "description": "United Arab Emirates VAT localization — 5% tax codes, VAT Payable/Receivable CoA leaves, TRN settings, and a sandbox FTA e-invoice adapter stub.",
        "category":    "Industry",
        "icon":        "Landmark",
        "deps":        ["base"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["UAE"],
    },
    "sa_zatca": {
        "label":       "Saudi ZATCA e-Invoice",
        "description": "KSA Phase 2 e-invoicing (sandbox clear/report)",
        "category":    "Localization",
        "icon":        "Landmark",
        "deps":        ["base"],
        "always":      False,
        "default":     False,
        "tier":        "addon",
        "nav_sections": ["ZATCA"],
    },
    "in_gst": {
        "label":       "India GST",
        "description": "India GST country pack — CGST/SGST/IGST tax codes, place-of-supply branching, GSTIN/HSN fields, and GSTR-1 / GSTR-3B summary exports.",
        "category":    "Localization",
        "icon":        "MapPin",
        "deps":        ["base"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Reports"],
    },
    "eu_peppol": {
        "label":       "Peppol / EU VAT e-Invoice",
        "description": "EU Peppol BIS Billing 3.0 UBL export and Access Point submission — participant ID, VAT tax mapping, sandbox AP adapter, and submission logs.",
        "category":    "Localization",
        "icon":        "Globe",
        "deps":        ["base"],
        "always":      False,
        "default":     False,
        "tier":        "addon",
        "nav_sections": ["Peppol"],
    },
    "healthcare": {
        "label":       "Healthcare",
        "description": "OPD/IPD management, lab orders & results, pharmacy store, procedure billing, ward management, and patient records for hospitals and clinics.",
        "category":    "Industry",
        "icon":        "Stethoscope",
        "deps":        ["base", "hrm", "inventory"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Healthcare"],
    },
    "ai_assistant": {
        "label":       "AI Financial Assistant",
        "description": "Ask questions about your finances in plain language. Powered by Claude AI — query P&L, overdue invoices, cash flow, and more.",
        "category":    "Intelligence",
        "icon":        "Sparkles",
        "deps":        ["base"],
        "always":      False,
        "default":     False,
        "tier":        "pro",
        "nav_sections": [],
    },
    "purchase_store": {
        "label":       "Purchases & Store",
        "description": "Procure-to-pay controls: purchase demands, vendor quotation comparison, approval-gated purchase orders, gate-inward receipt control with 3-way match, and gate-outward dispatch tracking for sales, returns, and scrap. Store issues arrive in an upcoming phase.",
        "category":    "Operations",
        "icon":        "ShoppingCart",
        "deps":        ["inventory"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Purchases"],
    },
    "pos": {
        "label":       "Point of Sale",
        "description": "Counter sales: register UI, shift cash-up, and atomic invoice + stock + cash/bank receipt posting.",
        "category":    "Operations",
        "icon":        "Store",
        "deps":        ["inventory"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["POS"],
    },
    "ecommerce": {
        "label":       "eCommerce Connectors",
        "description": "Connect Shopify / WooCommerce stores: map products by SKU, import orders as draft invoices, optional stock sync.",
        "category":    "Operations",
        "icon":        "ShoppingBag",
        "deps":        ["inventory"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["eCommerce"],
    },
    "weaving": {
        "label":       "Weaving",
        "description": "Weaving unit control: contracts, yarn inward, sizing, production, dispatch, and operational dashboards (Kg/Lbs/Bags). Memo/ops in v1 — no GL posting.",
        "category":    "Industry",
        "icon":        "Scissors",
        "deps":        ["base", "inventory"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Weaving"],
    },
    "spinning": {
        "label":       "Yarn Spinning",
        "description": "Spinning mill production: cotton receipt, multi-stage lot tracking, cone output, waste, and full GL costing.",
        "category":    "Industry",
        "icon":        "CircleDot",
        "deps":        ["base", "inventory", "purchase_store"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Spinning"],
    },
    "weighbridge": {
        "label":       "Weighbridge",
        "description": "Weighbridge tickets: vehicle in/out, first and second weigh, net Kg/Lbs/Bags, printable slip. For mills, traders, and any site that weighs inbound/outbound loads. Memo/ops in v1 — no GL posting.",
        "category":    "Operations",
        "icon":        "Scale",
        "deps":        ["base"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Weighbridge"],
    },
    "textile_processing": {
        "label":       "Textile Processing",
        "description": "Ballor/jobber printing unit: customer-owned grey lots, mending, PPC stages, process billing, contractor labor, and grey settlement.",
        "category":    "Industry",
        "icon":        "Layers",
        "deps":        ["base", "inventory", "purchase_store"],
        "always":      False,
        "default":     False,
        "tier":        "free",
        "nav_sections": ["Processing"],
    },
}

# Maps legacy business_model → sensible default module set.
# Used ONLY at tenant creation / model-switch to pre-select modules.
# After that the user manages modules independently via /api/modules.
MODULES_BY_MODEL: dict[str, list[str]] = {
    "simple":            ["base"],
    "services":          ["base"],
    "trader":            ["base", "inventory", "pos"],
    "manufacturing":     ["base", "inventory", "production", "purchase_store", "weaving", "weighbridge"],
    "telecom_franchise": ["base", "inventory", "telecom"],
    "pra_einvoice":      ["base", "pra"],
    "hospital":          ["base", "hrm", "inventory", "healthcare"],
    "yarn_spinning":     ["base", "inventory", "purchase_store", "spinning", "weighbridge"],
    "textile_processing": ["base", "inventory", "purchase_store", "textile_processing"],
}


def seed_data(tenant_id: int, session: Optional[Session] = None):
    def run_seeding(s: Session):
        # Look up the tenant to pick the right CoA template
        from models import Tenant
        tenant = s.get(Tenant, tenant_id)
        model = (tenant.business_model if tenant else None) or "simple"

        account_count = s.exec(
            select(Account).where(Account.tenant_id == tenant_id)
        ).first()

        if not account_count:
            template = _coa_for(model)
            created: dict[str, Account] = {}
            for code, name, atype, is_memo, parent_code, is_group in template:
                acc = Account(code=code, name=name, type=atype, is_memo=is_memo,
                              is_group=is_group, tenant_id=tenant_id)
                s.add(acc)
                created[code] = acc
            s.flush()
            for code, name, atype, is_memo, parent_code, is_group in template:
                if parent_code:
                    created[code].parent_id = created[parent_code].id
            # Set party_type: AR account 1100 → "customer", AP account 2000 → "vendor"
            for code, acc in created.items():
                if code == "1100" and acc.type == "Asset":
                    acc.party_type = "customer"
                elif code == "2000" and acc.type == "Liability":
                    acc.party_type = "vendor"
            s.commit()

        settings_count = s.exec(
            select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == "company_name")
        ).first()
        if not settings_count:
            tenant_row = s.get(Tenant, tenant_id)
            company = (
                os.environ.get("SEED_COMPANY_NAME")
                or (tenant_row.name if tenant_row and tenant_row.name else None)
                or "My Company"
            )
            s.add(Settings(key="company_name", value=company, tenant_id=tenant_id))
            s.commit()

        # Seed default GL account codes so get_default_account always finds them
        for key, code in (
            ("default_ar_account",      "1100"),
            ("default_ap_account",      "2000"),
            ("default_revenue_account", "4000"),
            ("default_cogs_account",    "5010"),
            ("default_mfg_labour_account", "5100"),
            ("default_mfg_overhead_account", "5200"),
            ("default_scrap_expense_account", "5901"),
        ):
            exists = s.exec(
                select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
            ).first()
            if not exists:
                s.add(Settings(tenant_id=tenant_id, key=key, value=code))

        # Seed initial onboarding checklist (all steps false)
        import json as _json
        ob_row = s.exec(
            select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == "onboarding_steps")
        ).first()
        if not ob_row:
            steps = {"company_profile": False, "first_customer": False,
                     "payment_terms": False, "first_invoice": False, "first_bill": False}
            s.add(Settings(tenant_id=tenant_id, key="onboarding_steps", value=_json.dumps(steps)))

        # Seed document-number counters so the at-runtime path never has to
        # INSERT — concurrent POSTs can then serialise on SELECT FOR UPDATE
        # without racing on the unique constraint.
        base_counters = ["invoice", "bill", "grn", "po", "credit_note", "purchase_order",
                         "debit_note", "customer_advance", "vendor_advance"]
        telecom_counters = ["tracker_txn", "load_transfer", "sim_sale", "rso_collection", "fca"]
        counter_names = base_counters + (telecom_counters if model == "telecom_franchise" else [])
        for name in counter_names:
            existing = s.exec(
                select(SequenceCounter).where(
                    SequenceCounter.tenant_id == tenant_id,
                    SequenceCounter.name == name,
                )
            ).first()
            if not existing:
                s.add(SequenceCounter(tenant_id=tenant_id, name=name, next_value=1))

        # Telecom tenants get a dedicated SIM stock location.
        if model == "telecom_franchise":
            for code, loc_name, ltype in (
                ("SIM_STOCK", "SIM Card Store", "own"),
            ):
                exists = s.exec(
                    select(StockLocation).where(
                        StockLocation.tenant_id == tenant_id,
                        StockLocation.code == code,
                    )
                ).first()
                if not exists:
                    s.add(StockLocation(
                        tenant_id=tenant_id, code=code, name=loc_name, type=ltype,
                    ))

        # Seed default StockLocations. Every tenant gets a "Main Store" so
        # legacy invoice/bill flows can attach receipts to it without forcing
        # the user to set up locations first.
        main_store = s.exec(
            select(StockLocation).where(
                StockLocation.tenant_id == tenant_id,
                StockLocation.code == "MAIN",
            )
        ).first()
        if not main_store:
            s.add(StockLocation(
                tenant_id=tenant_id, code="MAIN", name="Main Store", type="own",
            ))
        # Manufacturing tenants additionally get a customer godown and a WIP
        # bucket out of the box so they can record GRNs and production orders
        # immediately after signup.
        if model == "manufacturing":
            for code, name, ltype in (
                ("GODOWN", "Customer Goods Godown", "customer_custodial"),
                ("WIP",    "Work-in-Progress Floor", "wip"),
            ):
                exists = s.exec(
                    select(StockLocation).where(
                        StockLocation.tenant_id == tenant_id,
                        StockLocation.code == code,
                    )
                ).first()
                if not exists:
                    s.add(StockLocation(
                        tenant_id=tenant_id, code=code, name=name, type=ltype,
                    ))
        if model == "yarn_spinning":
            for code, name, ltype in (
                ("RAW",      "Raw Cotton Store", "own"),
                ("WIP-CARD", "WIP Carding",      "wip"),
                ("WIP-DRAW", "WIP Drawing",      "wip"),
                ("WIP-SPIN", "WIP Spinning",       "wip"),
                ("FG-YARN",  "Finished Yarn",      "own"),
            ):
                exists = s.exec(
                    select(StockLocation).where(
                        StockLocation.tenant_id == tenant_id,
                        StockLocation.code == code,
                    )
                ).first()
                if not exists:
                    s.add(StockLocation(
                        tenant_id=tenant_id, code=code, name=name, type=ltype,
                    ))
        if model == "textile_processing":
            for code, name, ltype in (
                ("GODOWN", "Customer Grey Godown", "customer_custodial"),
                ("REJ",    "Rejection Bay",        "customer_custodial"),
                ("WIP",    "Processing Floor",     "wip"),
            ):
                exists = s.exec(
                    select(StockLocation).where(
                        StockLocation.tenant_id == tenant_id,
                        StockLocation.code == code,
                    )
                ).first()
                if not exists:
                    s.add(StockLocation(
                        tenant_id=tenant_id, code=code, name=name, type=ltype,
                    ))
        # Seed default payment terms for every tenant
        for code, name, days in (
            ("DOR",   "Due on Receipt",  0),
            ("NET15", "Net 15 Days",    15),
            ("NET30", "Net 30 Days",    30),
            ("NET60", "Net 60 Days",    60),
        ):
            exists = s.exec(
                select(PaymentTerm).where(
                    PaymentTerm.tenant_id == tenant_id,
                    PaymentTerm.code == code,
                )
            ).first()
            if not exists:
                s.add(PaymentTerm(tenant_id=tenant_id, code=code, name=name, days=days))

        # Starter product categories (parent → sub). Generic defaults; users
        # edit them in-app. Seeded once per tenant (skipped if any exist).
        STARTER_CATEGORIES = {
            "simple":            {"General": ["Products", "Services"]},
            "services":          {"Services": ["Consulting", "Recurring"]},
            "trader":            {"Goods": ["General", "Imported"]},
            "manufacturing":     {"Raw Materials": ["Metals", "Consumables"],
                                  "Finished Goods": ["Standard"]},
            "telecom_franchise": {"SIM": ["Prepaid", "Postpaid"],
                                  "Devices": ["Handsets", "Accessories"]},
            "hospital":          {"Pharmacy": ["Medicines", "Consumables"],
                                  "Services": ["OPD", "Lab", "IPD"]},
            "yarn_spinning":     {"Raw Fiber": ["Cotton Bales", "Synthetic"],
                                  "Finished Yarn": ["Carded", "Combed", "Blended"]},
            "textile_processing": {"Process Chemicals": ["Dyes", "Auxiliaries"],
                                   "Maintenance": ["Spares", "Consumables"]},
        }
        if not s.exec(select(ProductCategory).where(ProductCategory.tenant_id == tenant_id)).first():
            for parent_name, subs in STARTER_CATEGORIES.get(model, {}).items():
                parent = ProductCategory(tenant_id=tenant_id, name=parent_name)
                s.add(parent); s.flush()
                for sub in subs:
                    s.add(ProductCategory(tenant_id=tenant_id, name=sub, parent_id=parent.id))

        s.commit()

    if session:
        run_seeding(session)
    else:
        with Session(engine) as session:
            run_seeding(session)
