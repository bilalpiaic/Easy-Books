import pytest
from fastapi.testclient import TestClient
from main import app
from db import engine
from sqlmodel import SQLModel, Session, select
from models import Tenant, User, Account

@pytest.fixture(name="client")
def client_fixture():
    # Setup: Create tables in an in-memory database
    # Note: We need to use the same engine for main app during tests
    # For simplicity here, we'll just use the default engine which is database.db
    # In a real app, we'd override the get_session dependency
    client = TestClient(app)
    yield client

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
