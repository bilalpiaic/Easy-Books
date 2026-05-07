import os
from typing import Optional
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
    
    # For development, ensure at least one tenant and user exist
    with Session(engine) as session:
        from models import Tenant, User
        from auth import get_password_hash
        
        default_tenant = session.exec(select(Tenant)).first()
        if not default_tenant:
            default_tenant = Tenant(name="Malik Enterprises")
            session.add(default_tenant)
            session.commit()
            session.refresh(default_tenant)
            
            # Seed data for this default tenant
            seed_data(default_tenant.id, session=session)
            
            # Create a default admin user
            admin_user = User(
                email="admin@malik.com",
                hashed_password=get_password_hash("admin123"),
                full_name="System Admin",
                tenant_id=default_tenant.id
            )
            session.add(admin_user)
            session.commit()

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

def seed_data(tenant_id: int, session: Optional[Session] = None):
    def run_seeding(s: Session):
        # Seed accounts for the specific tenant if empty
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
                Account(code="5900", name="Other Expenses", type="Expense", tenant_id=tenant_id),
            ]
            s.add_all(initial_accounts)
            s.commit()

        # Seed settings for the specific tenant if empty
        settings_count = s.exec(
            select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == "org_name")
        ).first()
        if not settings_count:
            s.add(Settings(key="org_name", value="New Company", tenant_id=tenant_id))
            s.commit()

    if session:
        run_seeding(session)
    else:
        with Session(engine) as session:
            run_seeding(session)
