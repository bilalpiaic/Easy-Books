"""Capacitor device tokens + overdue/approval push hook (#307)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str, company: str = "PushCo"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": company,
            "business_model": "simple",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_register_list_deactivate_device(client: TestClient):
    auth = _signup(client, "push-dev@test.local")
    r = client.post(
        "/api/devices",
        headers=auth,
        json={"token": "fcm-token-aaaa-bbbb", "platform": "android", "device_name": "Pixel"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["platform"] == "android"
    assert body["token_hint"] == "aaa-bbbb" or body["token_hint"].endswith("bbbb")
    assert "fcm-token-aaaa-bbbb" not in str(body)
    device_id = body["id"]

    listed = client.get("/api/devices", headers=auth)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == device_id

    again = client.post(
        "/api/devices",
        headers=auth,
        json={"token": "fcm-token-aaaa-bbbb", "platform": "android"},
    )
    assert again.status_code == 200
    assert again.json()["id"] == device_id

    gone = client.delete(f"/api/devices/{device_id}", headers=auth)
    assert gone.status_code == 200
    empty = client.get("/api/devices", headers=auth)
    assert empty.json()["items"] == []


def test_register_rejects_unknown_platform(client: TestClient):
    auth = _signup(client, "push-plat@test.local")
    r = client.post(
        "/api/devices",
        headers=auth,
        json={"token": "token-long-enough", "platform": "windows"},
    )
    assert r.status_code == 400


def test_emit_alert_fans_out_to_registered_device(client: TestClient, monkeypatch):
    auth = _signup(client, "push-fan@test.local", "FanCo")
    client.post(
        "/api/devices",
        headers=auth,
        json={"token": "ios-device-token-xyz", "platform": "ios"},
    )

    seen: list[dict] = []

    def fake_deliver(**kwargs):
        seen.append(kwargs)
        return "skipped_no_provider"

    monkeypatch.setattr("services.push.deliver_one", fake_deliver)

    from db import engine
    from sqlmodel import Session, select
    from models import User
    from services.alerts import emit_alert

    with Session(engine) as s:
        user = s.exec(select(User).where(User.email == "push-fan@test.local")).one()
        created = emit_alert(
            s,
            tenant_id=user.tenant_id,
            user_id=user.id,
            kind="overdue_invoice",
            title="Invoice overdue",
            body="INV-1 is overdue",
            href="/invoices/9",
            dedupe_key="overdue:9",
            entity_type="invoice",
            entity_id=9,
        )
        assert created is True
        s.commit()

    assert len(seen) == 1
    assert seen[0]["token"] == "ios-device-token-xyz"
    assert seen[0]["platform"] == "ios"
    assert seen[0]["data"]["href"] == "/invoices/9"
    assert seen[0]["data"]["kind"] == "overdue_invoice"


def test_low_stock_does_not_push(client: TestClient, monkeypatch):
    auth = _signup(client, "push-low@test.local")
    client.post(
        "/api/devices",
        headers=auth,
        json={"token": "android-token-no-push", "platform": "android"},
    )
    seen: list = []
    monkeypatch.setattr("services.push.deliver_one", lambda **kw: seen.append(kw) or "sent")

    from db import engine
    from sqlmodel import Session, select
    from models import User
    from services.alerts import emit_alert

    with Session(engine) as s:
        user = s.exec(select(User).where(User.email == "push-low@test.local")).one()
        emit_alert(
            s,
            tenant_id=user.tenant_id,
            user_id=user.id,
            kind="low_stock",
            title="Low stock",
            dedupe_key="low:1",
            href="/products/1",
        )
        s.commit()
    assert seen == []


def test_capacitor_origins_allowed_for_cors():
    from services.frontend_origin import parse_frontend_origins
    origins = parse_frontend_origins("https://books.example.com")
    assert origins[0] == "https://books.example.com"
    assert "capacitor://localhost" in origins
    assert "https://localhost" in origins
