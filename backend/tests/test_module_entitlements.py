"""Module plan allowlists + ops entitle (#370)."""
from __future__ import annotations

import json

import pytest

from db import MODULE_REGISTRY
from models import Tenant
from services.entitlements import (
    INDUSTRY_PACKS,
    PLAN_DENIED,
    PLAN_MODULES,
    can_install,
    is_allowed,
    is_entitled,
    plan_allows,
    set_entitled,
)
from services.saas import PLAN_LIMITS


@pytest.fixture
def enforce_plans(monkeypatch):
    monkeypatch.setenv("ENFORCE_MODULE_PLANS", "true")


def _signup(client, email, *, company="Co"):
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Owner", "company_name": company, "business_model": "simple",
    })
    assert r.status_code == 200, r.text
    tenant_id = r.json()["tenant_id"]
    tok = client.post("/api/auth/login", data={
        "username": email, "password": "password123",
    })
    assert tok.status_code == 200, tok.text
    client.cookies.clear()
    return tenant_id, {"Authorization": f"Bearer {tok.json()['access_token']}"}


def test_plan_tables_cover_registry():
    assert set(PLAN_MODULES) == set(PLAN_LIMITS)
    for mid in INDUSTRY_PACKS:
        assert mid in MODULE_REGISTRY
    for mid in PLAN_MODULES["pro"]:
        assert mid in MODULE_REGISTRY
    t = Tenant(name="x", plan="enterprise")
    for mid in MODULE_REGISTRY:
        assert plan_allows(t, mid)


def test_plan_allows_free_and_pro():
    free = Tenant(name="f", plan="free")
    assert plan_allows(free, "base")
    assert not plan_allows(free, "inventory")
    assert not plan_allows(free, "spinning")
    pro = Tenant(name="p", plan="pro")
    assert plan_allows(pro, "inventory")
    assert plan_allows(pro, "hrm")
    assert plan_allows(pro, "ai_assistant")
    assert plan_allows(pro, "weighbridge")
    assert not plan_allows(pro, "spinning")
    assert not plan_allows(pro, "healthcare")
    starter = Tenant(name="s", plan="starter")
    assert plan_allows(starter, "weighbridge")
    assert not plan_allows(starter, "spinning")


def test_entitle_flag_overrides_plan(enforce_plans):
    t = Tenant(name="f", plan="free", module_meta="{}")
    assert not can_install(t, "spinning")
    set_entitled(t, ["spinning"])
    assert is_entitled(t, "spinning")
    assert can_install(t, "spinning")
    assert is_allowed(t, "spinning")


def test_uninstall_does_not_clear_entitled_meta():
    t = Tenant(name="f", plan="free", module_meta="{}")
    set_entitled(t, ["spinning"])
    meta = json.loads(t.module_meta)
    meta["spinning"]["installed_at"] = "2026-01-01T00:00:00+00:00"
    t.module_meta = json.dumps(meta)
    # Mimic uninstall keep-entitled: drop install keys, keep entitled.
    blob = dict(json.loads(t.module_meta)["spinning"])
    keep = {"entitled": True}
    if blob.get("entitled_at"):
        keep["entitled_at"] = blob["entitled_at"]
    t.module_meta = json.dumps({"spinning": keep, "base": json.loads(t.module_meta).get("base", {"entitled": True})})
    assert is_entitled(t, "spinning")


def test_free_tenant_spinning_403(client, enforce_plans):
    _tid, auth = _signup(client, "free-spin@test.com")
    listed = client.get("/api/modules", headers=auth)
    assert listed.status_code == 200, listed.text
    spinning = next(m for m in listed.json() if m["id"] == "spinning")
    assert spinning["entitled"] is False
    assert spinning["installable"] is False
    r = client.post("/api/modules/spinning/install", headers=auth)
    assert r.status_code == 403, r.text
    assert PLAN_DENIED in r.json()["detail"]


def test_owner_cannot_hit_ops(client, enforce_plans):
    _tid, auth = _signup(client, "not-ops@test.com")
    r = client.get("/api/ops/tenants", headers=auth)
    assert r.status_code == 403
    r2 = client.put("/api/ops/tenants/1/entitled", headers=auth, json={"modules": ["spinning"]})
    assert r2.status_code == 403


def test_ops_entitle_then_install_and_cross_tenant(client, monkeypatch, enforce_plans):
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@easy-books.test")
    a_id, a_auth = _signup(client, "cust-a@test.com", company="Customer A")
    b_id, b_auth = _signup(client, "cust-b@test.com", company="Customer B")
    _ops_tid, ops_auth = _signup(client, "ops@easy-books.test", company="Easy-Books Ops")

    blocked = client.post("/api/modules/spinning/install", headers=a_auth)
    assert blocked.status_code == 403

    listed = client.get("/api/ops/tenants", headers=ops_auth)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["items"]}
    assert a_id in ids and b_id in ids

    put = client.put(
        f"/api/ops/tenants/{a_id}/entitled",
        headers=ops_auth,
        json={"modules": ["spinning"], "install": True},
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert "spinning" in body["entitled_modules"]
    enabled = set(body["enabled_modules"])
    assert "spinning" in enabled
    assert "inventory" in enabled
    assert "purchase_store" in enabled

    # Already installed after ops install-after
    again = client.post("/api/modules/spinning/install", headers=a_auth)
    assert again.status_code == 200, again.text

    # Tenant B still blocked
    other = client.post("/api/modules/spinning/install", headers=b_auth)
    assert other.status_code == 403, other.text

    # Audit lands on customer A, not the ops tenant
    audit = client.get("/api/audit-log?entity_type=ops.entitle&limit=50", headers=a_auth)
    assert audit.status_code == 200, audit.text
    items = audit.json().get("items") or audit.json().get("entries") or audit.json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("logs") or []
    assert any(
        (row.get("entity_type") == "ops.entitle" or "ops.entitle" in str(row))
        for row in (items if isinstance(items, list) else [])
    ), audit.text

    # Uninstall keeps entitled; reinstall works
    un = client.post("/api/modules/spinning/uninstall", headers=a_auth)
    assert un.status_code == 200, un.text
    listed_a = client.get("/api/modules", headers=a_auth).json()
    spinning = next(m for m in listed_a if m["id"] == "spinning")
    assert spinning["installed"] is False
    assert spinning["entitled"] is True
    assert spinning["installable"] is True
    re = client.post("/api/modules/spinning/install", headers=a_auth)
    assert re.status_code == 200, re.text
    assert "spinning" in re.json()["enabled_modules"]

    # base stays uninstall-blocked
    base = client.post("/api/modules/base/uninstall", headers=a_auth)
    assert base.status_code == 400


def test_pro_plan_installs_hrm_not_industry(client, enforce_plans):
    _tid, auth = _signup(client, "pro-plan@test.com")
    checkout = client.post("/api/billing/checkout", headers=auth, json={"plan": "pro"})
    assert checkout.status_code == 200, checkout.text
    hrm = client.post("/api/modules/hrm/install", headers=auth)
    assert hrm.status_code == 200, hrm.text
    wb = client.post("/api/modules/weighbridge/install", headers=auth)
    assert wb.status_code == 200, wb.text
    spinning = client.post("/api/modules/spinning/install", headers=auth)
    assert spinning.status_code == 403


def test_empty_ops_emails_fail_closed(client, monkeypatch, enforce_plans):
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "")
    _tid, auth = _signup(client, "ops-empty@easy-books.test")
    r = client.get("/api/ops/tenants", headers=auth)
    assert r.status_code == 403


def test_ops_grants_weighbridge_private_listing(client, monkeypatch):
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-wb@easy-books.test")
    mill_id, mill_auth = _signup(client, "ops-mill@test.com", company="Ops Mill")
    _ops_tid, ops_auth = _signup(client, "ops-wb@easy-books.test", company="Ops")

    before = client.get("/api/marketplace/catalog", headers=mill_auth).json()["entries"]
    assert any(e["id"] == "partner.easybooks.weighbridge" for e in before)

    put = client.put(
        f"/api/ops/tenants/{mill_id}/marketplace-private",
        headers=ops_auth,
        json={"extension_ids": ["partner.easybooks.weighbridge"]},
    )
    assert put.status_code == 200, put.text
    assert "partner.easybooks.weighbridge" in put.json()["marketplace_private"]

    after = client.get("/api/marketplace/catalog", headers=mill_auth).json()["entries"]
    row = next(e for e in after if e["id"] == "partner.easybooks.weighbridge")
    assert row["audience"] == "public"
    assert row["for_you"] is False
