"""Standalone premises install — 15-day demo-login trial."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _stamp(path: Path, when: datetime) -> None:
    text = when.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    path.write_text(text + "\n", encoding="utf-8")


def _standalone(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EB_STANDALONE", "true")
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("EB_SKIP_DEMO_TRIAL", raising=False)
    monkeypatch.delenv("ALLOW_DEMO_LOGIN", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("APP_ENV", "local")


def test_trial_does_not_apply_under_pytest_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("EB_STANDALONE", raising=False)
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_ENV", "development")
    from services.standalone_trial import demo_trial_applies, demo_trial_expired, trial_info

    assert demo_trial_applies() is False
    assert demo_trial_expired() is False
    assert trial_info() is None


def test_fresh_standalone_allows_demo_for_15_days(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    from services import standalone_trial as st
    from services.security_policy import demo_login_allowed

    assert st.demo_trial_applies() is True
    assert st.demo_trial_expired() is False
    assert demo_login_allowed() is True
    info = st.trial_info()
    assert info is not None
    assert info["expired"] is False
    assert info["locked"] is False
    assert info["days"] == 15
    assert info["days_remaining"] == 15
    assert (tmp_path / st.STAMP_NAME).is_file()


def test_expired_stamp_blocks_demo_login(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    from services import standalone_trial as st
    from services.security_policy import demo_login_allowed, demo_login_block_detail

    started = datetime.now(timezone.utc) - timedelta(days=16)
    _stamp(tmp_path / st.STAMP_NAME, started)
    assert st.demo_trial_expired() is True
    assert demo_login_allowed() is False
    assert "15-day trial" in demo_login_block_detail()
    assert "locked" in demo_login_block_detail().lower()
    assert (tmp_path / st.EXPIRED_NAME).is_file()
    info = st.trial_info()
    assert info["expired"] is True
    assert info["locked"] is True
    assert info["days_remaining"] == 0


def test_clock_rollback_after_expiry_stays_blocked(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    from services import standalone_trial as st

    started = datetime.now(timezone.utc) - timedelta(days=20)
    _stamp(tmp_path / st.STAMP_NAME, started)
    assert st.demo_trial_expired() is True
    # Wind the stamp forward as if the clock went back inside the window.
    _stamp(tmp_path / st.STAMP_NAME, datetime.now(timezone.utc))
    assert st.demo_trial_expired() is True


def test_skip_env_bypasses_trial(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    monkeypatch.setenv("EB_SKIP_DEMO_TRIAL", "true")
    from services.standalone_trial import demo_trial_applies, demo_trial_expired
    from services.security_policy import demo_login_allowed

    assert demo_trial_applies() is False
    assert demo_trial_expired() is False
    assert demo_login_allowed() is True


def test_allow_demo_login_false_wins_during_trial(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    monkeypatch.setenv("ALLOW_DEMO_LOGIN", "false")
    from services.security_policy import demo_login_allowed, demo_login_block_detail

    assert demo_login_allowed() is False
    assert demo_login_block_detail() == "Demo logins are disabled on this server."


def test_stamp_not_rewritten(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    from services import standalone_trial as st

    original = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    _stamp(tmp_path / st.STAMP_NAME, original)
    first = st.ensure_started_at()
    second = st.ensure_started_at()
    assert first.replace(microsecond=0) == original.replace(microsecond=0)
    assert second.replace(microsecond=0) == original.replace(microsecond=0)


def test_missing_stamp_backfills_from_sqlite_tenant(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    import sqlite3

    from services import standalone_trial as st

    created = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    db = tmp_path / "database.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE tenant (id INTEGER PRIMARY KEY, created_at TEXT)")
    con.execute("INSERT INTO tenant (created_at) VALUES (?)", (created.isoformat(),))
    con.commit()
    con.close()

    started = st.ensure_started_at()
    assert started.replace(microsecond=0) == created.replace(microsecond=0)
    assert st.demo_trial_expired() is True


def test_future_stamp_does_not_extend_trial(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    from services import standalone_trial as st

    _stamp(tmp_path / st.STAMP_NAME, datetime.now(timezone.utc) + timedelta(days=10))
    started = st.ensure_started_at()
    assert started <= datetime.now(timezone.utc) + timedelta(minutes=1)


def test_app_env_local_applies_outside_pytest(monkeypatch, tmp_path):
    monkeypatch.delenv("EB_STANDALONE", raising=False)
    monkeypatch.delenv("EB_SKIP_DEMO_TRIAL", raising=False)
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    from services.standalone_trial import demo_trial_applies

    assert demo_trial_applies() is True


def test_login_and_session_blocked_after_trial(client, monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    from services import standalone_trial as st

    r = client.post("/api/auth/signup", json={
        "email": "demo.trial@easy-books.app",
        "password": "pw12345678",
        "full_name": "Demo Trial",
        "company_name": "Trial Co",
    })
    assert r.status_code == 200, r.text
    login = client.post(
        "/api/auth/login",
        data={"username": "demo.trial@easy-books.app", "password": "pw12345678"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200

    started = datetime.now(timezone.utc) - timedelta(days=16)
    _stamp(tmp_path / st.STAMP_NAME, started)
    expired_marker = tmp_path / st.EXPIRED_NAME
    if expired_marker.exists():
        expired_marker.unlink()

    providers = client.get("/api/auth/oauth/providers")
    assert providers.status_code == 200
    body = providers.json()
    assert body["demo_login"] is False
    assert body["demo_trial"]["expired"] is True

    blocked = client.post(
        "/api/auth/login",
        data={"username": "demo.trial@easy-books.app", "password": "pw12345678"},
    )
    assert blocked.status_code == 403
    assert "trial" in blocked.json()["detail"].lower()
    assert blocked.json().get("code") == "standalone_trial_expired"

    me2 = client.get("/api/auth/me", headers=headers)
    assert me2.status_code == 403
    assert "locked" in me2.json()["detail"].lower()

    health = client.get("/api/health")
    assert health.status_code == 200


def test_signup_and_all_logins_blocked_after_trial(client, monkeypatch, tmp_path):
    """The install folder is not deleted; the running copy is locked for everyone."""
    _standalone(monkeypatch, tmp_path)
    from services import standalone_trial as st

    r = client.post("/api/auth/signup", json={
        "email": "owner.during-trial@co.test",
        "password": "pw12345678",
        "full_name": "Owner",
        "company_name": "Real Co",
    })
    assert r.status_code == 200, r.text
    login = client.post(
        "/api/auth/login",
        data={"username": "owner.during-trial@co.test", "password": "pw12345678"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    _stamp(tmp_path / st.STAMP_NAME, datetime.now(timezone.utc) - timedelta(days=20))
    expired_marker = tmp_path / st.EXPIRED_NAME
    if expired_marker.exists():
        expired_marker.unlink()

    signup = client.post("/api/auth/signup", json={
        "email": "owner.after-trial@co.test",
        "password": "pw12345678",
        "full_name": "Owner",
        "company_name": "Too Late Co",
    })
    assert signup.status_code == 403
    assert signup.json().get("code") == "standalone_trial_expired"

    relogin = client.post(
        "/api/auth/login",
        data={"username": "owner.during-trial@co.test", "password": "pw12345678"},
    )
    assert relogin.status_code == 403

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 403

    customers = client.get("/api/customers", headers={"Authorization": f"Bearer {token}"})
    assert customers.status_code == 403

    assert (tmp_path / st.STAMP_NAME).is_file()
    assert (tmp_path / st.EXPIRED_NAME).is_file()
    assert client.get("/api/auth/oauth/providers").status_code == 200


def test_custom_trial_days(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    monkeypatch.setenv("EB_DEMO_TRIAL_DAYS", "2")
    from services import standalone_trial as st

    _stamp(tmp_path / st.STAMP_NAME, datetime.now(timezone.utc) - timedelta(days=3))
    assert st.trial_days() == 2
    assert st.demo_trial_expired() is True
    assert "2-day trial" in st.trial_expired_detail()
    assert "locked" in st.trial_expired_detail().lower()


def test_extend_trial_grants_another_15_days(client, monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    from services import standalone_trial as st

    r = client.post("/api/auth/signup", json={
        "email": "owner.extend@co.test",
        "password": "pw12345678",
        "full_name": "Owner",
        "company_name": "Extend Co",
    })
    assert r.status_code == 200, r.text
    _stamp(tmp_path / st.STAMP_NAME, datetime.now(timezone.utc) - timedelta(days=20))
    expired = tmp_path / st.EXPIRED_NAME
    if expired.exists():
        expired.unlink()
    assert client.post(
        "/api/auth/login",
        data={"username": "owner.extend@co.test", "password": "pw12345678"},
    ).status_code == 403

    info = st.extend_trial(days=15)
    assert info["expired"] is False
    assert info["locked"] is False
    assert info["days"] == 15
    assert info["days_remaining"] == 15
    assert not expired.is_file()

    login = client.post(
        "/api/auth/login",
        data={"username": "owner.extend@co.test", "password": "pw12345678"},
    )
    assert login.status_code == 200, login.text

    signup = client.post("/api/auth/signup", json={
        "email": "new.business@co.test",
        "password": "pw12345678",
        "full_name": "New Owner",
        "company_name": "New Business Co",
    })
    assert signup.status_code == 200, signup.text
    new_login = client.post(
        "/api/auth/login",
        data={"username": "new.business@co.test", "password": "pw12345678"},
    )
    assert new_login.status_code == 200, new_login.text


def test_extend_trial_script_rewrites_clock(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    from services import standalone_trial as st
    from scripts.extend_trial import main

    started = datetime.now(timezone.utc) - timedelta(days=20)
    _stamp(tmp_path / st.STAMP_NAME, started)
    assert st.demo_trial_expired() is True
    assert main(["--days", "15"]) == 0
    assert st.demo_trial_expired() is False
    info = st.trial_info()
    assert info is not None
    assert info["days_remaining"] == 15
    assert info["expired"] is False
