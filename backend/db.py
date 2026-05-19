import os
from typing import Optional
from sqlmodel import Session, SQLModel, create_engine, select
from models import Account, Settings

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

def seed_data(tenant_id: int, session: Optional[Session] = None):
    def run_seeding(s: Session):
        account_count = s.exec(
            select(Account).where(Account.tenant_id == tenant_id)
        ).first()

        if not account_count:
            initial_accounts = [
                Account(code="1000", name="Cash in Hand", type="Asset", tenant_id=tenant_id),
                Account(code="1100", name="Accounts Receivable", type="Asset", tenant_id=tenant_id),
                Account(code="1200", name="Raw Material Inventory", type="Asset", tenant_id=tenant_id),
                Account(code="1300", name="Work-in-Progress", type="Asset", tenant_id=tenant_id),
                Account(code="2000", name="Accounts Payable", type="Liability", tenant_id=tenant_id),
                Account(code="2100", name="Advances Received", type="Liability", tenant_id=tenant_id),
                Account(code="3000", name="Owner Capital", type="Equity", tenant_id=tenant_id),
                Account(code="3100", name="Retained Earnings", type="Equity", tenant_id=tenant_id),
                Account(code="4000", name="CMT Services Income", type="Revenue", tenant_id=tenant_id),
                Account(code="4100", name="T-Shirt Sales", type="Revenue", tenant_id=tenant_id),
                Account(code="4200", name="Scrap Sales", type="Revenue", tenant_id=tenant_id),
                Account(code="4300", name="WC Orders Income", type="Revenue", tenant_id=tenant_id),
                Account(code="4900", name="Other Income", type="Revenue", tenant_id=tenant_id),
                Account(code="5000", name="Raw Material Expense", type="Expense", tenant_id=tenant_id),
                Account(code="5100", name="Labour & Wages", type="Expense", tenant_id=tenant_id),
                Account(code="5200", name="CMT Processing Expense", type="Expense", tenant_id=tenant_id),
                Account(code="5300", name="Rent & Utilities", type="Expense", tenant_id=tenant_id),
                Account(code="5400", name="Transport & Delivery", type="Expense", tenant_id=tenant_id),
                Account(code="5500", name="Machine Repair & Maintenance", type="Expense", tenant_id=tenant_id),
                Account(code="1201", name="Finished Goods Inventory", type="Asset", tenant_id=tenant_id),
                Account(code="5010", name="Cost of Goods Sold", type="Expense", tenant_id=tenant_id),
                Account(code="5900", name="Other Expenses", type="Expense", tenant_id=tenant_id),
            ]
            s.add_all(initial_accounts)
            s.commit()

        settings_count = s.exec(
            select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == "company_name")
        ).first()
        if not settings_count:
            company = os.environ.get("SEED_COMPANY_NAME", "My Company")
            s.add(Settings(key="company_name", value=company, tenant_id=tenant_id))
            s.commit()

    if session:
        run_seeding(session)
    else:
        with Session(engine) as session:
            run_seeding(session)
