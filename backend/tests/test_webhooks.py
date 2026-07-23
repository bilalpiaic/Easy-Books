"""Webhook / event bus tests (#114): endpoint CRUD, outbox fan-out from a
real document route, HMAC signing, the retry ladder, and the test ping."""
import hashlib
import hmac
import json

from sqlmodel import Session, select

from models import WebhookDelivery, WebhookEndpoint
from services import events as events_mod
from services.events import (
    MAX_ATTEMPTS, RETRY_DELAYS, drain_once, emit, sign,
)


def _session(client) -> Session:
    return Session(client.app.state.engine)


def _create_endpoint(client, headers, events, url="https://hooks.example/eb"):
    r = client.post("/api/webhooks", headers=headers,
                    json={"url": url, "events": events})
    assert r.status_code == 201, r.text
    return r.json()


# ── CRUD ─────────────────────────────────────────────────────────────────────

def test_create_returns_secret_once_then_masks(client, admin_headers):
    created = _create_endpoint(client, admin_headers, ["invoice.created"])
    assert len(created["secret"]) == 48          # token_hex(24)
    assert created["secret_masked"].endswith(created["secret"][-4:])

    listed = client.get("/api/webhooks", headers=admin_headers).json()
    assert len(listed) == 1
    assert "secret" not in listed[0]
    assert listed[0]["secret_masked"].startswith("••••")


def test_create_rejects_bad_url_and_unknown_event(client, admin_headers):
    r = client.post("/api/webhooks", headers=admin_headers,
                    json={"url": "ftp://x", "events": ["invoice.created"]})
    assert r.status_code == 400
    r = client.post("/api/webhooks", headers=admin_headers,
                    json={"url": "https://x.test", "events": ["no.such.event"]})
    assert r.status_code == 400
    assert "no.such.event" in r.json()["detail"]


def test_update_and_delete(client, admin_headers):
    ep = _create_endpoint(client, admin_headers, ["invoice.created"])
    r = client.put(f"/api/webhooks/{ep['id']}", headers=admin_headers,
                   json={"is_active": False, "events": ["bill.created"]})
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    assert r.json()["events"] == ["bill.created"]

    assert client.delete(f"/api/webhooks/{ep['id']}", headers=admin_headers).status_code == 204
    assert client.get("/api/webhooks", headers=admin_headers).json() == []


def test_event_types_endpoint(client, admin_headers):
    types = client.get("/api/webhooks/event-types", headers=admin_headers).json()
    assert "invoice.created" in types and "stock.low" in types


# ── Fan-out from a real document route ───────────────────────────────────────

def test_customer_create_queues_delivery(client, admin_headers):
    ep = _create_endpoint(client, admin_headers, ["customer.created"])
    # A second endpoint NOT subscribed to this event must receive nothing.
    other = _create_endpoint(client, admin_headers, ["bill.created"],
                             url="https://hooks.example/other")

    r = client.post("/api/customers", headers=admin_headers,
                    json={"name": "Hook Test Co"})
    assert r.status_code == 201

    with _session(client) as s:
        rows = s.exec(select(WebhookDelivery)).all()
        assert len(rows) == 1
        d = rows[0]
        assert d.endpoint_id == ep["id"] != other["id"]
        assert d.status == "pending" and d.event_type == "customer.created"
        payload = json.loads(d.payload_json)
        assert payload["event"] == "customer.created"
        assert payload["data"]["name"] == "Hook Test Co"


def test_inactive_endpoint_gets_nothing(client, admin_headers):
    ep = _create_endpoint(client, admin_headers, ["customer.created"])
    client.put(f"/api/webhooks/{ep['id']}", headers=admin_headers,
               json={"is_active": False})
    client.post("/api/customers", headers=admin_headers, json={"name": "Quiet Co"})
    with _session(client) as s:
        assert s.exec(select(WebhookDelivery)).all() == []


# ── Signature ────────────────────────────────────────────────────────────────

def test_signature_is_verifiable_hmac_sha256():
    body = '{"event":"ping"}'
    secret = "s3cret"
    expected = hmac.new(b"s3cret", body.encode(), hashlib.sha256).hexdigest()
    assert sign(secret, body) == f"sha256={expected}"


# ── Delivery + retry ladder ──────────────────────────────────────────────────

def _seed_delivery(client, admin_headers):
    ep = _create_endpoint(client, admin_headers, ["customer.created"])
    client.post("/api/customers", headers=admin_headers, json={"name": "Drain Co"})
    return ep


def test_drain_success_marks_delivered_and_signs(client, admin_headers):
    ep = _seed_delivery(client, admin_headers)
    seen = {}

    def fake_post(url, body, headers):
        seen.update(url=url, body=body, headers=headers)
        return 200, ""

    with _session(client) as s:
        assert drain_once(s, post=fake_post) == 1
        d = s.exec(select(WebhookDelivery)).one()
        assert d.status == "delivered" and d.response_code == 200
        assert d.attempts == 1 and d.delivered_at is not None
        endpoint = s.get(WebhookEndpoint, ep["id"])
        assert seen["url"] == ep["url"]
        assert seen["headers"]["X-EasyBooks-Signature"] == sign(endpoint.secret, seen["body"])
        assert seen["headers"]["X-EasyBooks-Event"] == "customer.created"
        # nothing left due
        assert drain_once(s, post=fake_post) == 0


def test_drain_failure_walks_retry_ladder_then_fails(client, admin_headers):
    _seed_delivery(client, admin_headers)

    def failing_post(url, body, headers):
        return 500, ""

    with _session(client) as s:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            # Force the row due regardless of the backoff written last round.
            d = s.exec(select(WebhookDelivery)).one()
            d.next_retry = events_mod._utcnow()
            s.add(d); s.commit()

            assert drain_once(s, post=failing_post) == 1
            d = s.exec(select(WebhookDelivery)).one()
            assert d.attempts == attempt
            if attempt < MAX_ATTEMPTS:
                assert d.status == "pending"
                delta = (d.next_retry - events_mod._utcnow()).total_seconds()
                assert abs(delta - RETRY_DELAYS[attempt - 1]) < 5
            else:
                assert d.status == "failed" and d.next_retry is None

        # A failed row never re-delivers.
        assert drain_once(s, post=failing_post) == 0


def test_connection_error_is_recorded(client, admin_headers):
    _seed_delivery(client, admin_headers)
    with _session(client) as s:
        drain_once(s, post=lambda u, b, h: (0, "ConnectError: refused"))
        d = s.exec(select(WebhookDelivery)).one()
        assert d.status == "pending" and d.response_code is None
        assert "ConnectError" in d.last_error


# ── Test ping + logs ─────────────────────────────────────────────────────────

def test_ping_endpoint_reports_live_response(client, admin_headers, monkeypatch):
    ep = _create_endpoint(client, admin_headers, ["invoice.created"])
    monkeypatch.setattr(events_mod, "_default_post", lambda u, b, h: (204, ""))
    r = client.post(f"/api/webhooks/{ep['id']}/test", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "response_code": 204, "error": None}


def test_logs_endpoint_lists_deliveries(client, admin_headers):
    ep = _seed_delivery(client, admin_headers)
    with _session(client) as s:
        drain_once(s, post=lambda u, b, h: (200, ""))
    logs = client.get(f"/api/webhooks/{ep['id']}/logs", headers=admin_headers).json()
    assert len(logs) == 1
    assert logs[0]["event_type"] == "customer.created"
    assert logs[0]["status"] == "delivered"


# ── Tenant isolation ─────────────────────────────────────────────────────────

def test_endpoints_are_tenant_scoped(client, admin_headers):
    ep = _create_endpoint(client, admin_headers, ["invoice.created"])
    client.post("/api/auth/signup", json={
        "email": "other@corp.test", "password": "pw12345678",
        "full_name": "Other", "company_name": "OtherCorp",
    })
    tok2 = client.post("/api/auth/login", data={
        "username": "other@corp.test", "password": "pw12345678",
    }).json()["access_token"]
    client.cookies.clear()
    h2 = {"Authorization": f"Bearer {tok2}"}
    assert client.get("/api/webhooks", headers=h2).json() == []
    assert client.get(f"/api/webhooks/{ep['id']}/logs", headers=h2).status_code == 404
