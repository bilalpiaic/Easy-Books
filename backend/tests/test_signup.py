import pytest
import os
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel, select
from main import app
from db import get_session
from models import Tenant, User, Account

# File-based database for testing to ensure connection persistence
TEST_DB = "test_database.db"
sqlite_url = f"sqlite:///{TEST_DB}"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def get_session_override():
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture():
    # Setup: Create tables
    SQLModel.metadata.create_all(engine)
    
    # Override dependency
    app.dependency_overrides[get_session] = get_session_override
    
    client = TestClient(app)
    yield client
    
    # Teardown
    app.dependency_overrides.clear()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_signup_flow(client: TestClient):
    signup_data = {
        "email": "test@example.com",
        "password": "password123",
        "full_name": "Test User",
        "company_name": "Test Company"
    }
    
    response = client.post("/api/auth/signup", json=signup_data)
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Verify in DB
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "test@example.com")).first()
        assert user is not None
        assert user.full_name == "Test User"
        
        tenant = session.exec(select(Tenant).where(Tenant.id == user.tenant_id)).first()
        assert tenant.name == "Test Company"
        
        # Verify auto-seeding
        accounts = session.exec(select(Account).where(Account.tenant_id == tenant.id)).all()
        assert len(accounts) > 0
        assert any(a.name == "Cash in Hand" for a in accounts)

def test_login_flow(client: TestClient):
    # Depends on the previous test or we create a user here
    login_data = {
        "username": "test@example.com",
        "password": "password123"
    }
    
    response = client.post("/api/auth/login", data=login_data)
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"
