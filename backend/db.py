import os
from sqlmodel import Session, SQLModel, create_engine, select
from models import Account, Settings

# Use absolute path for the database file to ensure consistency
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sqlite_file_name = os.path.join(BASE_DIR, "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    seed_data()

def get_session():
    with Session(engine) as session:
        yield session

def get_tenant_session(tenant_id: int):
    """
    Dependency that provides a session for a specific tenant.
    Currently a wrapper around get_session, but can be extended
    with automatic filtering in the future.
    """
    with Session(engine) as session:
        yield session

def seed_data():
    with Session(engine) as session:
        from models import Tenant
        # Create a default tenant if none exists
        default_tenant = session.exec(select(Tenant)).first()
        if not default_tenant:
            default_tenant = Tenant(name="Default Tenant")
            session.add(default_tenant)
            session.commit()
            session.refresh(default_tenant)
        
        tenant_id = default_tenant.id

        # Seed accounts if empty
        account_count = session.exec(select(Account)).first()
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
                Account(code="5900", name="Other Expenses", type="Expense", tenant_id=tenant_id),
            ]
            session.add_all(initial_accounts)
            session.commit()

        # Seed settings if empty
        settings_count = session.exec(select(Settings)).first()
        if not settings_count:
            session.add(Settings(key="org_name", value="Malik Enterprises", tenant_id=tenant_id))
            session.commit()
