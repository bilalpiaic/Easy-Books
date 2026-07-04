"""V2.1 tests: business_model selection at signup, per-model CoA, switching."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import Account, Tenant


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    app.state.engine = engine
    app.dependency_overrides[get_session] = _override
    client = TestClient(app)
    yield client, engine
    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _signup(client: TestClient, business_model: str, email: str) -> dict:
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": business_model,
        },
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_signup_defaults_to_simple_when_model_omitted(client):
    c, engine = client
    c.post("/api/auth/signup", json={
        "email": "d@d.test", "password": "password123",
        "full_name": "U", "company_name": "Co",
    })
    with Session(engine) as s:
        t = s.exec(select(Tenant)).first()
        assert t.business_model == "simple"


def test_simple_model_seeds_minimal_coa(client):
    c, engine = client
    _signup(c, "simple", "s@s.test")
    with Session(engine) as s:
        accts = s.exec(select(Account)).all()
        codes = {a.code for a in accts}
        # Backbone present
        assert "1000" in codes and "1100" in codes and "4000" in codes
        # Trader/manufacturing extras absent
        assert "1200" not in codes  # no inventory in simple
        assert "1210" not in codes  # no custodial in simple
        assert "5010" not in codes  # no COGS in simple


def test_trader_model_seeds_inventory_accounts(client):
    c, engine = client
    _signup(c, "trader", "tr@tr.test")
    with Session(engine) as s:
        codes = {a.code for a in s.exec(select(Account)).all()}
        assert "1200" in codes  # Finished Goods Inventory
        assert "1250" in codes  # GST Input
        assert "5010" in codes  # COGS
        assert "5020" in codes  # Freight In
        # No manufacturing-specific extras
        assert "1201" not in codes  # no WIP in trader
        assert "1210" not in codes  # no custodial


def test_manufacturing_model_seeds_custodial_memo_accounts(client):
    c, engine = client
    _signup(c, "manufacturing", "m@m.test")
    with Session(engine) as s:
        accts = {a.code: a for a in s.exec(select(Account)).all()}
        # Manufacturing CoA backbone
        assert "1200" in accts  # Raw Material
        assert "1201" in accts  # WIP
        assert "1202" in accts  # FG
        assert "5100" in accts  # Direct Labour
        assert "5200" in accts  # Manufacturing Overhead
        # Custodial pair must be present AND flagged is_memo
        assert accts["1210"].is_memo is True
        assert accts["2150"].is_memo is True
        # Other accounts must NOT be is_memo
        assert accts["1100"].is_memo is False
        assert accts["4010"].is_memo is False


def test_services_model_seeds_service_revenue_accounts(client):
    c, engine = client
    _signup(c, "services", "sv@sv.test")
    with Session(engine) as s:
        codes = {a.code for a in s.exec(select(Account)).all()}
        assert "4010" in codes  # Consulting Revenue
        assert "4020" in codes  # Recurring Service Revenue
        assert "2300" in codes  # Deferred Revenue
        # No inventory
        assert "1200" not in codes
        assert "5010" not in codes


def test_invalid_business_model_rejected(client):
    c, _ = client
    r = c.post("/api/auth/signup", json={
        "email": "x@x.test", "password": "password123",
        "full_name": "U", "company_name": "Co",
        "business_model": "unicorn",
    })
    assert r.status_code == 400
    assert "business_model" in r.json()["detail"]


def test_me_endpoint_returns_business_model_and_modules(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "me@me.test")
    r = c.get("/api/auth/me", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["tenant"]["business_model"] == "manufacturing"
    modules = body["tenant"]["enabled_modules"]
    assert "base" in modules
    assert "inventory" in modules
    assert "production" in modules
    assert "purchase_store" in modules


def test_switching_business_model_adds_new_coa_accounts(client):
    c, engine = client
    auth = _signup(c, "simple", "sw@sw.test")
    # Initially no WIP, no custodial
    with Session(engine) as s:
        codes = {a.code for a in s.exec(select(Account)).all()}
        assert "1201" not in codes
        assert "1210" not in codes

    r = c.patch(
        "/api/settings/business-model", headers=auth,
        json={"business_model": "manufacturing"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["business_model"] == "manufacturing"
    assert "1201" in body["accounts_added"]
    assert "1210" in body["accounts_added"]
    # WIP + custodial now present
    with Session(engine) as s:
        codes = {a.code for a in s.exec(select(Account)).all()}
        assert "1201" in codes
        assert "1210" in codes


def test_switching_business_model_requires_admin_role(client):
    c, engine = client
    auth = _signup(c, "simple", "demote@d.test")
    # Demote owner to accountant
    with Session(engine) as s:
        from models import User as UserModel
        u = s.query(UserModel).filter(UserModel.email == "demote@d.test").first()
        u.role = "accountant"
        s.add(u)
        s.commit()
    # Re-login to get a fresh JWT with accountant role
    r = c.post(
        "/api/auth/login",
        data={"username": "demote@d.test", "password": "password123"},
    )
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = c.patch(
        "/api/settings/business-model", headers=auth,
        json={"business_model": "trader"},
    )
    assert r.status_code == 403  # WriteUserDep allows accountant; AdminUserDep doesn't


def test_modules_can_be_customised_independently(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "mod@mod.test")
    # Disable BoM module
    r = c.patch(
        "/api/settings/modules", headers=auth,
        json={"enabled_modules": ["invoicing", "billing", "inventory"]},
    )
    assert r.status_code == 200
    assert "bom" not in r.json()["enabled_modules"]
    # Business model unchanged
    me = c.get("/api/auth/me", headers=auth).json()
    assert me["tenant"]["business_model"] == "manufacturing"
    assert me["tenant"]["enabled_modules"] == ["invoicing", "billing", "inventory"]
