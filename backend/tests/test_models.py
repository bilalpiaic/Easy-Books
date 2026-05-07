import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models import Tenant, User, Account, Transaction, JournalEntry, Settings

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_create_tenant_and_user(session: Session):
    tenant = Tenant(name="Acme Corp")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    
    assert tenant.id is not None
    assert tenant.name == "Acme Corp"
    
    user = User(
        email="user@example.com",
        hashed_password="hashed",
        tenant_id=tenant.id
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    assert user.id is not None
    assert user.tenant_id == tenant.id

def test_models_have_tenant_id(session: Session):
    tenant = Tenant(name="Acme Corp")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    
    account = Account(name="Cash", code="1001", type="Asset", tenant_id=tenant.id)
    session.add(account)
    
    transaction = Transaction(jv_number="JV001", date="2023-01-01", tenant_id=tenant.id)
    session.add(transaction)
    session.commit()
    
    session.refresh(account)
    session.refresh(transaction)
    
    assert account.tenant_id == tenant.id
    assert transaction.tenant_id == tenant.id
    
    entry = JournalEntry(
        transaction_id=transaction.id,
        account_id=account.id,
        debit=100.0,
        tenant_id=tenant.id
    )
    session.add(entry)
    
    settings = Settings(key="currency", value="USD", tenant_id=tenant.id)
    session.add(settings)
    
    session.commit()
    session.refresh(entry)
    session.refresh(settings)
    
    assert entry.tenant_id == tenant.id
    assert settings.tenant_id == tenant.id
