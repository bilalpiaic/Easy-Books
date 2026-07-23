"""Wave B–D smoke tests: SaaS quotas, TOTP, portal, approvals, forecasts."""
from __future__ import annotations

import pyotp


def test_billing_usage_and_offline_upgrade(client, admin_headers):
    r = client.get("/api/billing/usage", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "plan" in body and "documents_this_month" in body

    r = client.post("/api/billing/checkout", headers=admin_headers, json={"plan": "starter"})
    assert r.status_code == 200
    assert r.json()["plan"] == "starter"


def test_totp_setup_enable_and_login_gate(client, admin_headers):
    r = client.post("/api/auth/totp/setup", headers=admin_headers)
    assert r.status_code == 200
    secret = r.json()["secret"]
    code = pyotp.TOTP(secret).now()
    r = client.post("/api/auth/totp/enable", headers=admin_headers, json={"code": code})
    assert r.status_code == 200
    assert r.json()["totp_enabled"] is True

    # Disable so other tests aren't blocked
    code = pyotp.TOTP(secret).now()
    client.post("/api/auth/totp/disable", headers=admin_headers, json={"code": code})


def test_oauth_providers_endpoint(client):
    r = client.get("/api/auth/oauth/providers")
    assert r.status_code == 200
    body = r.json()
    assert "google" in body and "microsoft" in body


def test_portal_mint_and_home(client, admin_headers):
    cust = client.post(
        "/api/customers",
        headers=admin_headers,
        json={"name": "Portal Co", "email": "portal@example.com"},
    )
    assert cust.status_code in (200, 201)
    cid = cust.json()["id"]
    r = client.post(
        f"/api/portal/mint?entity_type=customer&entity_id={cid}",
        headers=admin_headers,
    )
    assert r.status_code == 200
    token = r.json()["token"]
    home = client.get(f"/api/portal/{token}")
    assert home.status_code == 200
    assert "company_name" in home.json()


def test_approval_workflow_create_and_list(client, admin_headers):
    r = client.post(
        "/api/approvals/workflows",
        headers=admin_headers,
        json={
            "document_type": "bill",
            "name": "Bills over 50k",
            "steps": [{"step_order": 0, "approver_role": "owner", "min_amount": 50000}],
        },
    )
    assert r.status_code == 201
    assert client.get("/api/approvals/workflows", headers=admin_headers).status_code == 200


def test_plaid_list_without_config(client, admin_headers):
    r = client.get("/api/banking/plaid/connections", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []
    r = client.post("/api/banking/plaid/link-token", headers=admin_headers)
    assert r.status_code == 503


def test_forecast_revenue_shape(client, admin_headers):
    r = client.get("/api/agent/forecast/revenue", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "actuals" in body and "forecast" in body


def test_agent_suggestions_list(client, admin_headers):
    r = client.get("/api/agent/suggestions", headers=admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_health_still_ok(client):
    assert client.get("/api/health").status_code == 200
