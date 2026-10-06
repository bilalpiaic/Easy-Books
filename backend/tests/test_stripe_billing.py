"""#420 — one Stripe webhook; no silent upgrades or unsigned events in production."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str = "stripe-a@co.test") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": "Stripe Co",
            "business_model": "simple",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_offline_checkout_still_works_off_production(client: TestClient, admin_headers):
    r = client.post("/api/billing/checkout", headers=admin_headers, json={"plan": "starter"})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "offline"
    assert r.json()["plan"] == "starter"


def test_checkout_503_in_production_without_stripe(client: TestClient, admin_headers, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_OWNER_TOTP", "false")
    r = client.post("/api/billing/checkout", headers=admin_headers, json={"plan": "starter"})
    assert r.status_code == 503


def test_unsigned_webhook_refused_in_production(client: TestClient, monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    r = client.post(
        "/api/stripe/webhook",
        json={"type": "customer.subscription.updated", "data": {"object": {}}},
    )
    assert r.status_code == 503


def test_unsigned_webhook_applies_plan_off_production(client: TestClient, admin_headers, monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    me = client.get("/api/auth/me", headers=admin_headers).json()
    tenant_id = me["tenant"]["id"]
    r = client.post(
        "/api/stripe/webhook",
        json={
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "customer": "cus_x",
                    "metadata": {"tenant_id": str(tenant_id), "plan": "pro"},
                }
            },
        },
    )
    assert r.status_code == 200, r.text
    usage = client.get("/api/billing/usage", headers=admin_headers).json()
    assert usage["plan"] == "pro"


def test_simulate_pay_refused_in_production(client: TestClient, monkeypatch):
    auth = _auth(client, "sim-prod@co.test")
    cust_r = client.post("/api/customers", headers=auth, json={"name": "Buyer Co"})
    assert cust_r.status_code in (200, 201), cust_r.text
    cust = cust_r.json()
    inv_r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-08-01",
            "due_date": "2026-08-31",
            "gst_rate": 0,
            "lines": [{"description": "Consulting", "qty": 1, "rate": 250}],
        },
    )
    assert inv_r.status_code == 201, inv_r.text
    inv = inv_r.json()
    minted = client.post(
        f"/api/portal/mint?entity_type=customer&entity_id={cust['id']}",
        headers=auth,
    )
    assert minted.status_code == 200, minted.text
    token = minted.json()["token"]
    monkeypatch.setenv("ENVIRONMENT", "production")
    r = client.post(
        f"/api/portal/{token}/invoices/{inv['id']}/simulate-pay",
        json={"checkout_session_id": "cs_sim", "amount": 250},
    )
    assert r.status_code == 403
