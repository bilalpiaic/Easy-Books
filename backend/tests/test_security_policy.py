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


def test_login_attempt_default_is_timezone_aware():
    """SQLAlchemy 2.1 rejects naive datetime.utcnow() on LoginAttempt."""
    from models import LoginAttempt

    row = LoginAttempt(ip="127.0.0.1")
    assert row.attempted_at.tzinfo is not None
    assert row.attempted_at.utcoffset().total_seconds() == 0


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


def test_production_defaults_fail_closed(monkeypatch):
    """#419 — production env without explicit flags: TOTP on, demo login off."""
    monkeypatch.delenv("REQUIRE_OWNER_TOTP", raising=False)
    monkeypatch.delenv("ALLOW_DEMO_LOGIN", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    from services import security_policy as sp
    assert sp.is_production() is True
    assert sp.require_owner_totp() is True
    assert sp.demo_login_allowed() is False
    assert sp.seed_demo_default() == "false"


def test_dev_defaults_keep_demo_usable(monkeypatch):
    monkeypatch.delenv("REQUIRE_OWNER_TOTP", raising=False)
    monkeypatch.delenv("ALLOW_DEMO_LOGIN", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    from services import security_policy as sp
    assert sp.is_production() is False
    assert sp.require_owner_totp() is False
    assert sp.demo_login_allowed() is True
    assert sp.seed_demo_default() == "true"


def test_explicit_flags_override_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_OWNER_TOTP", "false")
    monkeypatch.setenv("ALLOW_DEMO_LOGIN", "true")
    from services import security_policy as sp
    assert sp.require_owner_totp() is False
    assert sp.demo_login_allowed() is True


def test_totp_enable_accepts_spaced_code_and_stores_aware_timestamp(client, admin_headers):
    setup = client.post("/api/auth/totp/setup", headers=admin_headers)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()
    enabled = client.post(
        "/api/auth/totp/enable",
        headers=admin_headers,
        json={"code": f"{code[:3]} {code[3:]}"},
    )
    assert enabled.status_code == 200, enabled.text
    import db as dbmod
    from models import User
    from sqlmodel import Session, select

    with Session(dbmod.engine) as session:
        user = session.exec(select(User).where(User.email == "owner@acme.test")).first()
        assert user is not None
        assert user.totp_enabled is True
        assert user.totp_verified_at is not None
    client.post(
        "/api/auth/totp/disable",
        headers=admin_headers,
        json={"code": pyotp.TOTP(secret).now()},
    )


def test_totp_verify_writes_aware_last_login(client, admin_headers):
    setup = client.post("/api/auth/totp/setup", headers=admin_headers)
    secret = setup.json()["secret"]
    client.post("/api/auth/totp/enable", headers=admin_headers, json={"code": pyotp.TOTP(secret).now()})
    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        data={"username": "owner@acme.test", "password": "pw12345678"},
    )
    assert login.json().get("requires_totp") is True
    verify = client.post(
        "/api/auth/totp/verify",
        json={
            "partial_token": login.json()["partial_token"],
            "code": pyotp.TOTP(secret).now(),
        },
    )
    assert verify.status_code == 200, verify.text
    import db as dbmod
    from models import User
    from sqlmodel import Session, select

    with Session(dbmod.engine) as session:
        user = session.exec(select(User).where(User.email == "owner@acme.test")).first()
        assert user is not None
        assert user.last_login_at is not None
    client.post(
        "/api/auth/totp/disable",
        headers=admin_headers,
        json={"code": pyotp.TOTP(secret).now()},
    )


def test_unhandled_500_includes_cors_for_frontend_origin(client):
    from main import app

    async def boom():
        raise RuntimeError("simulated totp commit failure")

    app.add_api_route("/api/__test_boom_cors", boom, methods=["GET"], include_in_schema=False)
    r = client.get(
        "/api/__test_boom_cors",
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.status_code == 500
    assert r.json()["detail"] == "Internal server error"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_missing_column_error_is_503_with_cors(client):
    from main import app
    from sqlalchemy.exc import ProgrammingError

    async def boom():
        raise ProgrammingError(
            "SELECT invoice.buyer_registration_type",
            {},
            Exception("column invoice.buyer_registration_type does not exist"),
        )

    app.add_api_route("/api/__test_schema_cors", boom, methods=["GET"], include_in_schema=False)
    r = client.get(
        "/api/__test_schema_cors",
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.status_code == 503
    assert "schema is behind" in r.json()["detail"]
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_vercel_bundle_includes_alembic_scripts():
    from pathlib import Path
    import json

    cfg = json.loads((Path(__file__).resolve().parents[1] / "vercel.json").read_text())
    exclude = cfg["functions"]["api/index.py"]["excludeFiles"]
    assert "alembic" not in exclude


def test_schema_upgrade_requires_auth(client):
    r = client.post("/api/system/schema-upgrade")
    assert r.status_code == 401


def test_schema_migrate_file_head_is_current():
    from services.schema_migrate import file_head

    head = file_head()
    assert head is not None
    assert head.startswith("00")


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
