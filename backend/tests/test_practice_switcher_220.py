"""Practice multi-client switcher (#220)."""
from __future__ import annotations

import jwt
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from auth import ALGORITHM, SECRET_KEY
from models import TenantMembership, User


def _signup(client: TestClient, email: str, company: str) -> dict:
    r = client.post("/api/auth/signup", json={
        "email": email,
        "password": "pw12345678",
        "full_name": email.split("@")[0].title(),
        "company_name": company,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _login(client: TestClient, email: str) -> str:
    client.cookies.clear()
    r = client.post("/api/auth/login", data={"username": email, "password": "pw12345678"})
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return r.json()["access_token"]


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_signup_creates_membership(client: TestClient):
    _signup(client, "owner@acme.test", "Acme")
    tok = _login(client, "owner@acme.test")
    r = client.get("/api/auth/tenants", headers=_hdr(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["is_active"] is True
    assert body["items"][0]["role"] == "owner"


def test_invite_existing_user_attaches_membership(client: TestClient, admin_headers):
    # Second company
    _signup(client, "owner@beta.test", "Beta Co")
    beta_tok = _login(client, "owner@beta.test")

    # Attach Acme's owner into Beta via invite
    r = client.post(
        "/api/users/invites",
        headers=_hdr(beta_tok),
        json={"email": "owner@acme.test", "role": "accountant"},
    )
    assert r.status_code in (200, 201), r.text
    assert r.json()["attached"] is True

    # Acme owner now has two memberships
    acme_tok = _login(client, "owner@acme.test")
    r = client.get("/api/auth/tenants", headers=_hdr(acme_tok))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    roles = {i["role"] for i in items}
    assert roles == {"owner", "accountant"}
    tenant_ids = {i["tenant_id"] for i in items}
    assert len(tenant_ids) == 2


def test_switch_tenant_remints_jwt_and_updates_user(client: TestClient):
    _signup(client, "owner@acme.test", "Acme")
    _signup(client, "owner@beta.test", "Beta Co")
    beta_tok = _login(client, "owner@beta.test")
    beta_tid = jwt.decode(beta_tok, SECRET_KEY, algorithms=[ALGORITHM])["tenant_id"]

    client.post(
        "/api/users/invites",
        headers=_hdr(beta_tok),
        json={"email": "owner@acme.test", "role": "viewer"},
    )

    old_tok = _login(client, "owner@acme.test")
    old_payload = jwt.decode(old_tok, SECRET_KEY, algorithms=[ALGORITHM])
    assert old_payload["tenant_id"] != beta_tid

    r = client.post(
        "/api/auth/switch-tenant",
        headers=_hdr(old_tok),
        json={"tenant_id": beta_tid},
    )
    assert r.status_code == 200, r.text
    new_tok = r.json()["access_token"]
    new_payload = jwt.decode(new_tok, SECRET_KEY, algorithms=[ALGORITHM])
    assert new_payload["tenant_id"] == beta_tid
    assert new_payload["role"] == "viewer"
    assert new_payload.get("jti") != old_payload.get("jti")

    # Old token rejected (revoked + tenant mismatch)
    r = client.get("/api/auth/me", headers=_hdr(old_tok))
    assert r.status_code == 401

    me = client.get("/api/auth/me", headers=_hdr(new_tok))
    assert me.status_code == 200
    assert me.json()["tenant"]["id"] == beta_tid
    assert me.json()["role"] == "viewer"
    assert me.json()["memberships_count"] == 2


def test_switch_non_member_forbidden(client: TestClient, admin_headers):
    _signup(client, "other@solo.test", "Solo")
    other_tok = _login(client, "other@solo.test")
    other_tid = jwt.decode(other_tok, SECRET_KEY, algorithms=[ALGORITHM])["tenant_id"]

    # admin_headers is Acme owner — try switching into Solo without membership
    r = client.post(
        "/api/auth/switch-tenant",
        headers=admin_headers,
        json={"tenant_id": other_tid},
    )
    assert r.status_code == 403


def test_cross_tenant_isolation_after_switch(client: TestClient):
    _signup(client, "owner@acme.test", "Acme")
    _signup(client, "owner@beta.test", "Beta Co")
    beta_tok = _login(client, "owner@beta.test")
    beta_tid = jwt.decode(beta_tok, SECRET_KEY, algorithms=[ALGORITHM])["tenant_id"]

    # Create a customer in Beta
    r = client.post(
        "/api/customers",
        headers=_hdr(beta_tok),
        json={"name": "Beta Only Customer", "email": "c@beta.test"},
    )
    assert r.status_code in (200, 201), r.text

    # Attach Acme owner as viewer on Beta
    client.post(
        "/api/users/invites",
        headers=_hdr(beta_tok),
        json={"email": "owner@acme.test", "role": "viewer"},
    )

    acme_tok = _login(client, "owner@acme.test")
    # Still on Acme — should not see Beta customer
    r = client.get("/api/customers", headers=_hdr(acme_tok))
    assert r.status_code == 200
    names = [c.get("name") for c in (r.json() if isinstance(r.json(), list) else r.json().get("items", []))]
    assert "Beta Only Customer" not in names

    # Switch to Beta — should see it
    sw = client.post(
        "/api/auth/switch-tenant",
        headers=_hdr(acme_tok),
        json={"tenant_id": beta_tid},
    )
    assert sw.status_code == 200
    beta_view = sw.json()["access_token"]
    r = client.get("/api/customers", headers=_hdr(beta_view))
    assert r.status_code == 200
    names = [c.get("name") for c in (r.json() if isinstance(r.json(), list) else r.json().get("items", []))]
    assert "Beta Only Customer" in names


def test_membership_backfill_on_login(client: TestClient):
    """Legacy users without a membership row get one on login."""
    _signup(client, "legacy@acme.test", "Legacy Co")
    engine = client.app.state.engine
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "legacy@acme.test")).first()
        assert user is not None
        for m in session.exec(
            select(TenantMembership).where(TenantMembership.user_id == user.id)
        ).all():
            session.delete(m)
        session.commit()
        assert session.exec(
            select(TenantMembership).where(TenantMembership.user_id == user.id)
        ).first() is None

    tok = _login(client, "legacy@acme.test")
    r = client.get("/api/auth/tenants", headers=_hdr(tok))
    assert r.status_code == 200
    assert r.json()["total"] == 1
