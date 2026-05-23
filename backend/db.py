import os
from typing import Optional
from sqlmodel import Session, SQLModel, create_engine, select
from models import Account, SequenceCounter, Settings, StockLocation

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
        sep = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    _environment = os.environ.get("ENVIRONMENT", "development").lower()
    if _environment == "production":
        raise RuntimeError(
            "DATABASE_URL environment variable must be set in production. "
            "SQLite fallback is not supported for serverless deployments."
        )
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sqlite_file_name = os.path.join(BASE_DIR, "database.db")
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

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

def get_session():
    with Session(engine) as session:
        yield session

def get_tenant_session(tenant_id: int):
    with Session(engine) as session:
        yield session

# Per-business-model Chart of Accounts templates. Each entry is
# (code, name, type, is_memo). The four lists are designed to overlap on the
# common backbone (cash, AR, AP, revenue, expense) so reports keep working
# regardless of which model is chosen. Manufacturing adds the custodial pair
# 1210/2150 with is_memo=True.

_COA_COMMON: list[tuple[str, str, str, bool]] = [
    # Universal backbone — present in every model
    ("1000", "Cash in Hand",        "Asset",     False),
    ("1010", "Bank",                "Asset",     False),
    ("1100", "Accounts Receivable", "Asset",     False),
    ("2000", "Accounts Payable",    "Liability", False),
    ("2200", "GST Payable (Output)","Liability", False),
    ("3000", "Owner Capital",       "Equity",    False),
    ("3010", "Drawings",            "Equity",    False),
    ("3100", "Retained Earnings",   "Equity",    False),
    ("4000", "Sales Revenue",       "Revenue",   False),
    ("4900", "Other Income",        "Revenue",   False),
    ("5000", "General Expenses",    "Expense",   False),
    ("5050", "Depreciation Expense","Expense",   False),
    ("5900", "Other Expenses",      "Expense",   False),
]

# Service-style add-ons: time-based revenue + deferred revenue
_COA_SERVICES_EXTRA: list[tuple[str, str, str, bool]] = [
    ("4010", "Consulting Revenue",        "Revenue",   False),
    ("4020", "Recurring Service Revenue", "Revenue",   False),
    ("2300", "Deferred Revenue",          "Liability", False),
    ("5110", "Subcontractor Costs",       "Expense",   False),
]

# Trader extras: finished-goods inventory + COGS + input GST
_COA_TRADER_EXTRA: list[tuple[str, str, str, bool]] = [
    ("1200", "Finished Goods Inventory", "Asset",   False),
    ("1250", "GST Receivable (Input)",   "Asset",   False),
    ("5010", "Cost of Goods Sold",       "Expense", False),
    ("5020", "Freight In",               "Expense", False),
    ("5030", "Storage & Handling",       "Expense", False),
    ("5040", "Inventory Adjustments",    "Expense", False),
]

# Manufacturing extras: raw materials, WIP, custodial pair, labour, overhead
_COA_MANUFACTURING_EXTRA: list[tuple[str, str, str, bool]] = [
    ("1200", "Raw Material Inventory",   "Asset",     False),
    ("1201", "Work-in-Progress",         "Asset",     False),
    ("1202", "Finished Goods Inventory", "Asset",     False),
    ("1210", "Customer Goods on Hand",   "Asset",     True),   # memo
    ("1250", "GST Receivable (Input)",   "Asset",     False),
    ("2150", "Customer Goods Liability", "Liability", True),   # memo (mirrors 1210)
    ("4010", "Service Revenue (Value-Add)", "Revenue", False),
    ("5010", "Cost of Goods Sold",       "Expense",   False),
    ("5100", "Direct Labour",            "Expense",   False),
    ("5110", "Subcontractor Costs",      "Expense",   False),
    ("5200", "Manufacturing Overhead",   "Expense",   False),
    ("5210", "Indirect Materials",       "Expense",   False),
]

# Telecom extras: connectivity revenue split + prepaid deferred revenue +
# interconnect / roaming COGS + SIM/device inventory + network opex.
_COA_TELECOM_EXTRA: list[tuple[str, str, str, bool]] = [
    ("1200", "SIM & Device Inventory",      "Asset",     False),
    ("1250", "GST Receivable (Input)",      "Asset",     False),
    ("2310", "Unearned Airtime Revenue",    "Liability", False),
    ("2320", "Unearned Data Revenue",       "Liability", False),
    ("2330", "Unearned SMS Revenue",        "Liability", False),
    ("4010", "Airtime Revenue",             "Revenue",   False),
    ("4020", "Data Revenue",                "Revenue",   False),
    ("4030", "SMS Revenue",                 "Revenue",   False),
    ("4040", "Roaming Revenue",             "Revenue",   False),
    ("4050", "Interconnect Revenue",        "Revenue",   False),
    ("4060", "Value-Added Services Revenue","Revenue",   False),
    ("5010", "Cost of Goods Sold",          "Expense",   False),
    ("5300", "Interconnect Charges",        "Expense",   False),
    ("5310", "Roaming Costs",               "Expense",   False),
    ("5320", "Bandwidth & Transmission",    "Expense",   False),
    ("5330", "Tower & Site Rentals",        "Expense",   False),
    ("5340", "Spectrum & Licence Fees",     "Expense",   False),
    ("5350", "Network Maintenance",         "Expense",   False),
]


def _coa_for(business_model: str) -> list[tuple[str, str, str, bool]]:
    """Return the CoA template for a business model. Universal backbone always
    present; model-specific extras layered on top. Codes are unique within
    each template (Manufacturing's 1200 overrides Common-Trader's 1200 by
    keying on code in the dict below)."""
    by_code: dict[str, tuple[str, str, str, bool]] = {a[0]: a for a in _COA_COMMON}
    extra_map = {
        "services":      _COA_SERVICES_EXTRA,
        "trader":        _COA_TRADER_EXTRA,
        "manufacturing": _COA_MANUFACTURING_EXTRA,
        "telecom":       _COA_TELECOM_EXTRA,
    }
    for row in extra_map.get(business_model, []):
        by_code[row[0]] = row
    return sorted(by_code.values(), key=lambda r: r[0])


# Module activation per business model. Module names are conventions used by
# the frontend sidebar and (later) endpoint guards — they are NOT enforced at
# the backend yet (V2.4 wires them up).
MODULES_BY_MODEL: dict[str, list[str]] = {
    "simple":        ["invoicing", "billing", "manual_jv"],
    "services":      ["invoicing", "billing", "manual_jv", "service_catalogue"],
    "trader":        ["invoicing", "billing", "manual_jv", "inventory"],
    "manufacturing": ["invoicing", "billing", "manual_jv", "inventory",
                      "stores", "bom", "production", "customer_goods"],
    "telecom":       ["invoicing", "billing", "manual_jv", "inventory",
                      "deferred_revenue", "rate_plans"],
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
            s.add_all([
                Account(
                    code=code, name=name, type=atype,
                    is_memo=is_memo, tenant_id=tenant_id,
                )
                for code, name, atype, is_memo in template
            ])
            s.commit()

        settings_count = s.exec(
            select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == "company_name")
        ).first()
        if not settings_count:
            company = os.environ.get("SEED_COMPANY_NAME", "My Company")
            s.add(Settings(key="company_name", value=company, tenant_id=tenant_id))
            s.commit()

        # Seed document-number counters so the at-runtime path never has to
        # INSERT — concurrent POSTs can then serialise on SELECT FOR UPDATE
        # without racing on the unique constraint.
        for name in ("invoice", "bill", "grn", "po"):
            existing = s.exec(
                select(SequenceCounter).where(
                    SequenceCounter.tenant_id == tenant_id,
                    SequenceCounter.name == name,
                )
            ).first()
            if not existing:
                s.add(SequenceCounter(tenant_id=tenant_id, name=name, next_value=1))

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
        s.commit()

    if session:
        run_seeding(session)
    else:
        with Session(engine) as session:
            run_seeding(session)
