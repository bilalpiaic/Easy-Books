"""#118 remainder — require owner TOTP + production demo-login gate."""
from __future__ import annotations

import pyotp


def _signup_login(client, email="owner-2fa@co.test", password="pw12345678"):
    r = client.post("/api/auth/signup", json={
        "email": email,
        "password": password,
        "full_name": "Owner",
        "company_name": "2FA Co",
    })
    assert r.status_code == 200, r.text
    login = client.post("/api/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200, login.text
    client.cookies.clear()
    body = login.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def test_oauth_providers_includes_demo_login(client):
    r = client.get("/api/auth/oauth/providers")
    assert r.status_code == 200
    body = r.json()
    assert body["demo_login"] is True
    assert "google" in body and "microsoft" in body


def test_demo_login_blocked_when_disallowed(client, monkeypatch):
    monkeypatch.setenv("ALLOW_DEMO_LOGIN", "false")
    # Seed a demo-shaped user via signup (email pattern is what the gate keys on).
    r = client.post("/api/auth/signup", json={
        "email": "demo.gate@easy-books.app",
        "password": "pw12345678",
        "full_name": "Demo",
        "company_name": "Demo Co",
    })
    assert r.status_code == 200, r.text
    login = client.post(
        "/api/auth/login",
        data={"username": "demo.gate@easy-books.app", "password": "pw12345678"},
    )
    assert login.status_code == 403
    assert "Demo logins" in login.json()["detail"]


def test_owner_totp_setup_required_and_write_gate(client, monkeypatch):
    monkeypatch.setenv("REQUIRE_OWNER_TOTP", "true")
    headers, body = _signup_login(client, email="need-2fa@co.test")
    assert body["totp_setup_required"] is True
    assert body["totp_enabled"] is False

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["totp_setup_required"] is True
    assert me.json()["totp_can_disable"] is False

    blocked = client.post("/api/customers", headers=headers, json={"name": "Blocked"})
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "totp_setup_required"

    setup = client.post("/api/auth/totp/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()
    enabled = client.post("/api/auth/totp/enable", headers=headers, json={"code": code})
    assert enabled.status_code == 200

    me2 = client.get("/api/auth/me", headers=headers)
    assert me2.json()["totp_enabled"] is True
    assert me2.json()["totp_setup_required"] is False

    ok = client.post("/api/customers", headers=headers, json={"name": "Allowed"})
    assert ok.status_code in (200, 201), ok.text

    disable = client.post(
        "/api/auth/totp/disable",
        headers=headers,
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert disable.status_code == 400
    assert "2FA" in disable.json()["detail"]


def test_demo_owner_exempt_from_totp_requirement(client, monkeypatch):
    monkeypatch.setenv("REQUIRE_OWNER_TOTP", "true")
    headers, body = _signup_login(client, email="demo.spinning@easy-books.app")
    assert body["totp_setup_required"] is False
    r = client.post("/api/customers", headers=headers, json={"name": "Demo Cust"})
    assert r.status_code in (200, 201), r.text


def test_partial_totp_token_cannot_call_me(client, admin_headers):
    r = client.post("/api/auth/totp/setup", headers=admin_headers)
    secret = r.json()["secret"]
    client.post("/api/auth/totp/enable", headers=admin_headers, json={"code": pyotp.TOTP(secret).now()})
    login = client.post(
        "/api/auth/login",
        data={"username": "owner@acme.test", "password": "pw12345678"},
    )
    assert login.status_code == 200
    assert login.json().get("requires_totp") is True
    partial = login.json()["partial_token"]
    client.cookies.clear()
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {partial}"})
    assert me.status_code == 401
    # Disable so the shared admin user doesn't poison later tests in this file
    # (this test uses admin_headers which already enabled TOTP).
    client.post(
        "/api/auth/totp/disable",
        headers=admin_headers,
        json={"code": pyotp.TOTP(secret).now()},
    )
