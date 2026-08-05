"""#299 Accountant practice depth — dashboard, onboarding, tenant-scoped permissions."""
from datetime import date as DateType, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, StaticPool, create_engine, select

from db import get_session
from main import app
from models import UserPermission


def _mk_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _override(engine):
    def _inner():
        with Session(engine) as s:
            yield s
    return _inner


def _signup(client, email, company):
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Tester",
            "company_name": company,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["tenant_id"]


def _login(client, email):
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def test_practice_dashboard_isolates_per_client():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)

    acme_tid = _signup(client, "acct@firm.test", "Acme")
    beta_tid = _signup(client, "owner@beta.test", "Beta Co")

    # Attach accountant to Beta
    beta_tok = _login(client, "owner@beta.test")
    r = client.post(
        "/api/users/invites",
        headers=_hdr(beta_tok),
        json={"email": "acct@firm.test", "role": "accountant"},
    )
    assert r.status_code in (200, 201), r.text

    # Seed an open invoice on Acme
    acme_tok = _login(client, "acct@firm.test")
    cust = client.post("/api/customers", headers=_hdr(acme_tok), json={"name": "Alice"}).json()
    due = (DateType.today() - timedelta(days=10)).isoformat()
    client.post("/api/invoices", headers=_hdr(acme_tok), json={
        "customer_id": cust["id"],
        "issue_date": (DateType.today() - timedelta(days=20)).isoformat(),
        "due_date": due,
        "gst_rate": 0,
        "lines": [{"description": "Svc", "qty": 1, "rate": 500}],
    })

    dash = client.get("/api/practice/dashboard", headers=_hdr(acme_tok)).json()
    assert dash["total"] >= 2
    by_id = {i["tenant_id"]: i for i in dash["items"]}
    assert acme_tid in by_id and beta_tid in by_id
    assert float(by_id[acme_tid]["ar_outstanding"]) == 500.0
    assert float(by_id[acme_tid]["ar_overdue"]) == 500.0
    # Beta has no invoices
    assert float(by_id[beta_tid]["ar_outstanding"]) == 0.0

    app.dependency_overrides.clear()


def test_practice_create_client_attaches_caller():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)

    _signup(client, "firm@practice.test", "Firm Home")
    tok = _login(client, "firm@practice.test")

    r = client.post(
        "/api/practice/clients",
        headers=_hdr(tok),
        json={"company_name": "New Client Ltd"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["role"] == "admin"
    new_tid = body["tenant_id"]

    tenants = client.get("/api/auth/tenants", headers=_hdr(tok)).json()
    ids = {t["tenant_id"] for t in tenants["items"]}
    assert new_tid in ids

    # Switch into new client works
    sw = client.post(
        "/api/auth/switch-tenant",
        headers=_hdr(tok),
        json={"tenant_id": new_tid},
    )
    assert sw.status_code == 200, sw.text
    new_tok = sw.json()["access_token"]
    # CoA seeded
    accts = client.get("/api/accounts", headers=_hdr(new_tok)).json()
    assert accts["total"] > 0

    app.dependency_overrides.clear()


def test_permission_overrides_are_tenant_scoped():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)

    _signup(client, "multi@firm.test", "Home Co")
    tok = _login(client, "multi@firm.test")

    # Create two client companies
    c1 = client.post("/api/practice/clients", headers=_hdr(tok), json={"company_name": "Client One"}).json()
    c2 = client.post("/api/practice/clients", headers=_hdr(tok), json={"company_name": "Client Two"}).json()
    me = client.get("/api/auth/me", headers=_hdr(tok)).json()
    uid = me["id"]

    # Restrict invoices on Client One only
    r = client.put(
        f"/api/practice/clients/{c1['tenant_id']}/permissions/{uid}",
        headers=_hdr(tok),
        json=[{"resource_key": "invoices", "access_level": "none"}],
    )
    assert r.status_code == 200, r.text

    # Client Two still has role default (edit for admin)
    p2 = client.get(
        f"/api/practice/clients/{c2['tenant_id']}/permissions/{uid}",
        headers=_hdr(tok),
    ).json()
    assert p2["permissions"]["invoices"] == "edit"

    p1 = client.get(
        f"/api/practice/clients/{c1['tenant_id']}/permissions/{uid}",
        headers=_hdr(tok),
    ).json()
    assert p1["permissions"]["invoices"] == "none"

    # DB has two distinct rows (tenant-scoped unique)
    with Session(engine) as s:
        rows = s.exec(
            select(UserPermission).where(
                UserPermission.user_id == uid,
                UserPermission.resource_key == "invoices",
            )
        ).all()
        # Only Client One has an override row
        assert len(rows) == 1
        assert rows[0].tenant_id == c1["tenant_id"]

    app.dependency_overrides.clear()


def test_practice_members_requires_admin_membership():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)

    _signup(client, "viewer-home@t.test", "Home")
    _signup(client, "owner-b@t.test", "Other")
    other_tok = _login(client, "owner-b@t.test")
    # Attach as viewer
    client.post(
        "/api/users/invites",
        headers=_hdr(other_tok),
        json={"email": "viewer-home@t.test", "role": "viewer"},
    )
    home_tok = _login(client, "viewer-home@t.test")
    tenants = client.get("/api/auth/tenants", headers=_hdr(home_tok)).json()["items"]
    other = next(t for t in tenants if t["role"] == "viewer")

    r = client.get(
        f"/api/practice/clients/{other['tenant_id']}/members",
        headers=_hdr(home_tok),
    )
    assert r.status_code == 403

    app.dependency_overrides.clear()
