from db import create_db_and_tables
from sqlmodel import Session, select
from models import Tenant, Account, Settings
from db import engine

def verify_db():
    create_db_and_tables()
    with Session(engine) as session:
        tenants = session.exec(select(Tenant)).all()
        print(f"Tenants: {len(tenants)}")
        for t in tenants:
            print(f"  - {t.name} (ID: {t.id})")
        
        accounts = session.exec(select(Account)).all()
        print(f"Accounts: {len(accounts)}")
        
        settings = session.exec(select(Settings)).all()
        print(f"Settings: {len(settings)}")
        for s in settings:
            print(f"  - {s.key}: {s.value} (Tenant ID: {s.tenant_id})")

if __name__ == "__main__":
    verify_db()
