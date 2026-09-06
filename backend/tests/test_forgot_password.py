"""Self-service forgot-password (#390)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlmodel import Session, select

import db
from models import PasswordResetToken, User


GENERIC = "If that account exists, we sent a reset link."


def _signup(client, email="reset.me@co.test", password="oldpass12"):
    r = client.post("/api/auth/signup", json={
        "email": email,
        "password": password,
        "full_name": "Reset Me",
        "company_name": "Reset Co",
    })
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return email, password


def _token_from_html(html: str) -> str:
    m = re.search(r"reset-password\?token=([^\"'&\s]+)", html)
    assert m, html
    return m.group(1)


def test_forgot_unknown_email_is_generic(client, monkeypatch):
    sent = []
    monkeypatch.setattr("routers.auth.send_email", lambda *a, **k: sent.append((a, k)))
    r = client.post("/api/auth/forgot-password", json={"email": "nobody@missing.test"})
    assert r.status_code == 200
    assert r.json()["message"] == GENERIC
    assert "token" not in r.json()
    assert sent == []


def test_forgot_happy_path_reset_then_login(client, monkeypatch):
    email, old = _signup(client)
    sent = {}

    def capture(to, subject, html_body):
        sent["to"] = to
        sent["subject"] = subject
        sent["html"] = html_body

    monkeypatch.setattr("routers.auth.send_email", capture)
    r = client.post("/api/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    assert r.json()["message"] == GENERIC
    assert "token" not in r.json()
    assert sent["to"] == email
    token = _token_from_html(sent["html"])
    assert "localhost:3000/reset-password?token=" in sent["html"]

    inspect = client.get(f"/api/auth/reset-password/{token}")
    assert inspect.status_code == 200
    assert inspect.json() == {"valid": True}

    reset = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "newpass99"},
    )
    assert reset.status_code == 200
    assert reset.json()["success"] is True

    assert client.post(
        "/api/auth/login", data={"username": email, "password": old},
    ).status_code == 401
    login = client.post(
        "/api/auth/login", data={"username": email, "password": "newpass99"},
    )
    assert login.status_code == 200, login.text


def test_reset_token_cannot_be_reused(client, monkeypatch):
    email, _ = _signup(client, email="reuse@co.test")
    sent = {}
    monkeypatch.setattr(
        "routers.auth.send_email",
        lambda to, subject, html_body: sent.update(html=html_body),
    )
    client.post("/api/auth/forgot-password", json={"email": email})
    token = _token_from_html(sent["html"])
    first = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "newpass99"},
    )
    assert first.status_code == 200
    second = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "another99"},
    )
    assert second.status_code == 400
    inspect = client.get(f"/api/auth/reset-password/{token}")
    assert inspect.status_code == 400


def test_expired_token_rejected(client, monkeypatch):
    email, _ = _signup(client, email="expire@co.test")
    sent = {}
    monkeypatch.setattr(
        "routers.auth.send_email",
        lambda to, subject, html_body: sent.update(html=html_body),
    )
    client.post("/api/auth/forgot-password", json={"email": email})
    token = _token_from_html(sent["html"])
    with Session(db.engine) as s:
        row = s.exec(select(PasswordResetToken)).first()
        assert row is not None
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        s.add(row)
        s.commit()
    assert client.get(f"/api/auth/reset-password/{token}").status_code == 400
    r = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "newpass99"},
    )
    assert r.status_code == 400


def test_inactive_and_demo_and_oauth_skip_mail(client, monkeypatch):
    sent = []
    monkeypatch.setattr("routers.auth.send_email", lambda *a, **k: sent.append(1))

    _signup(client, email="gone@co.test")
    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "gone@co.test")).first()
        u.is_active = False
        s.add(u)
        s.commit()
    r = client.post("/api/auth/forgot-password", json={"email": "gone@co.test"})
    assert r.status_code == 200
    assert r.json()["message"] == GENERIC
    assert sent == []

    _signup(client, email="demo.reset@easy-books.app")
    r = client.post("/api/auth/forgot-password", json={"email": "demo.reset@easy-books.app"})
    assert r.status_code == 200
    assert sent == []

    _signup(client, email="sso@co.test")
    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "sso@co.test")).first()
        u.oauth_provider = "google"
        s.add(u)
        s.commit()
    r = client.post("/api/auth/forgot-password", json={"email": "sso@co.test"})
    assert r.status_code == 200
    assert sent == []


def test_reset_does_not_disable_totp(client, monkeypatch):
    email, _ = _signup(client, email="totp-reset@co.test")
    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == email)).first()
        u.totp_enabled = True
        s.add(u)
        s.commit()
    sent = {}
    monkeypatch.setattr(
        "routers.auth.send_email",
        lambda to, subject, html_body: sent.update(html=html_body),
    )
    client.post("/api/auth/forgot-password", json={"email": email})
    token = _token_from_html(sent["html"])
    assert client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "newpass99"},
    ).status_code == 200
    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == email)).first()
        assert u.totp_enabled is True
        assert u.must_change_password is False


def test_reset_rejects_short_password(client, monkeypatch):
    email, _ = _signup(client, email="short@co.test")
    sent = {}
    monkeypatch.setattr(
        "routers.auth.send_email",
        lambda to, subject, html_body: sent.update(html=html_body),
    )
    client.post("/api/auth/forgot-password", json={"email": email})
    token = _token_from_html(sent["html"])
    r = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "short"},
    )
    assert r.status_code == 422


def test_forgot_rate_limit_per_email(client, monkeypatch):
    monkeypatch.setattr("routers.auth.send_email", lambda *a, **k: None)
    email = "flood@missing.test"
    last = None
    for _ in range(6):
        last = client.post("/api/auth/forgot-password", json={"email": email})
    assert last.status_code == 429
