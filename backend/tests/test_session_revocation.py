"""Part 3/4 of #113 — jti-based session revocation.

The behavioral change under test: before this, /logout only deleted
cookies — a copy of the token (another tab, a captured Authorization
header) stayed valid until natural 24h expiry. Now logout denylists the
token's jti and every request checks it."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from auth import create_access_token


def _signup(client, email):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co", "business_model": "simple",
    })


def _login(client, email):
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    client.cookies.clear()
    return r.json()["access_token"]


def test_logout_revokes_the_presented_bearer_token(client: TestClient):
    _signup(client, "rev1@t.com")
    token = _login(client, "rev1@t.com")
    auth = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/auth/me", headers=auth).status_code == 200
    assert client.post("/api/auth/logout", headers=auth).status_code == 200
    # The SAME token, still in hand — dead immediately, not at natural expiry.
    assert client.get("/api/auth/me", headers=auth).status_code == 401


def test_logout_via_cookie_revokes_too(client: TestClient):
    _signup(client, "rev2@t.com")
    r = client.post("/api/auth/login", data={"username": "rev2@t.com", "password": "password123"})
    token = r.json()["access_token"]
    csrf = r.json()["csrf_token"]

    # Cookie-authenticated logout (the SPA path) — needs the CSRF header?
    # /logout is CSRF-exempt (services/csrf.py _EXEMPT_PATHS), so no.
    assert client.post("/api/auth/logout").status_code == 200
    client.cookies.clear()
    # The bearer copy of that same cookie token is dead as well.
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert csrf  # silence unused warning; csrf flow itself is covered elsewhere


def test_other_sessions_are_unaffected(client: TestClient):
    _signup(client, "rev3@t.com")
    token_a = _login(client, "rev3@t.com")
    token_b = _login(client, "rev3@t.com")  # second login → distinct jti

    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token_a}"}).status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"}).status_code == 401
    # The other session's token keeps working — revocation is per-token.
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_b}"}).status_code == 200


def test_double_logout_of_the_same_token_is_harmless(client: TestClient):
    _signup(client, "rev4@t.com")
    token = _login(client, "rev4@t.com")
    auth = {"Authorization": f"Bearer {token}"}

    assert client.post("/api/auth/logout", headers=auth).status_code == 200
    # Second logout hits the unique-jti constraint — must not 500.
    assert client.post("/api/auth/logout", headers=auth).status_code == 200


def test_pre_jti_tokens_still_authenticate(client: TestClient):
    """Tokens minted before this feature carry no jti claim — they must keep
    working (no forced re-login on deploy), just without revocability."""
    _signup(client, "rev5@t.com")
    legacy = create_access_token(
        data={"sub": "rev5@t.com", "tenant_id": 1, "full_name": "U", "role": "owner"},
        expires_delta=timedelta(minutes=30),
    )
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 200


def test_prune_removes_only_expired_rows(client: TestClient):
    _signup(client, "rev6@t.com")
    token = _login(client, "rev6@t.com")
    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    from models import RevokedToken
    engine = client.app.state.engine
    with Session(engine) as s:
        live = s.exec(select(RevokedToken)).all()
        assert len(live) == 1
        live_jti, live_tenant = live[0].jti, live[0].tenant_id
        # Plant an already-expired row alongside the live one.
        s.add(RevokedToken(jti="expired-jti", tenant_id=live_tenant,
                           expires_at=datetime.utcnow() - timedelta(hours=1)))
        s.commit()

    import db as _db
    from main import _run_revoked_token_prune_once
    original_engine = _db.engine
    _db.engine = engine
    try:
        _run_revoked_token_prune_once()
    finally:
        _db.engine = original_engine

    with Session(engine) as s:
        remaining = s.exec(select(RevokedToken)).all()
        assert [r.jti for r in remaining] == [live_jti]
