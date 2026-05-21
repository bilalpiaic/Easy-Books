"""V2.5 tests: manufacturing reports (dashboard, WIP aging, summary, custody)."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from db import get_session
from main import app


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    app.state.engine = engine
    app.dependency_overrides[get_session] = _override
    client = TestClient(app)
    yield client, engine
    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _signup(c, model, email):
    c.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": model,
        },
    )
    r = c.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_product(c, auth, code):
    return c.post(
        "/api/products", headers=auth,
        json={"code": code, "name": code, "unit": "ea",
              "product_type": "stock", "default_rate": 0},
    ).json()


def _scenario(c, auth):
    """Common setup: 1 customer, 1 GRN, BoM with own + customer components,
    rate plan assigned. Returns (cust, out, button, fabric, bom, plan)."""
    cust = c.post("/api/customers", headers=auth, json={"name": "Brand"}).json()
    out = _make_product(c, auth, "WIDGET")
    button = _make_product(c, auth, "BUTTON")
    fabric = _make_product(c, auth, "FABRIC")
    vendor = c.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    c.post(
        "/api/bills", headers=auth,
        json={"vendor_id": vendor["id"], "bill_date": "2026-05-01",
              "due_date": "2026-05-31", "gst_rate": 0,
              "lines": [{"product_id": button["id"], "description": "buy",
                         "qty": 200, "rate": 1}]},
    )
    bom = c.post(
        "/api/bom", headers=auth,
        json={"output_product_id": out["id"], "output_qty": 1,
              "lines": [
                  {"component_product_id": button["id"], "qty_per_output": 2, "source": "own_stock"},
                  {"component_product_id": fabric["id"], "qty_per_output": 1, "source": "customer_supplied"},
              ]},
    ).json()
    plan = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "STD", "name": "Std", "per_unit_rate": "10",
              "includes_materials_at_cost": True,
              "overhead_pct": "0", "margin_pct": "0"},
    ).json()
    c.post(
        "/api/rate-plans/assign", headers=auth,
        json={"customer_id": cust["id"], "rate_plan_id": plan["id"]},
    )
    c.post(
        "/api/grn", headers=auth,
        json={"customer_id": cust["id"], "received_date": "2026-05-10",
              "lines": [{"product_id": fabric["id"], "qty": 30, "lot_no": "L1",
                         "declared_value": "300"}]},
    )
    return cust, out, button, fabric, bom, plan


def test_dashboard_empty(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "d1@m.test")
    r = c.get("/api/manufacturing/dashboard", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline"]["draft"] == 0
    assert Decimal(body["totals"]["wip_cost"]) == Decimal("0")


def test_dashboard_counts_by_state(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "d2@m.test")
    cust, out, button, fabric, bom, plan = _scenario(c, auth)

    # Make 3 POs in various states
    p1 = c.post("/api/production-orders", headers=auth,
                json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 5}).json()
    p2 = c.post("/api/production-orders", headers=auth,
                json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 5}).json()
    c.post(f"/api/production-orders/{p2['id']}/start", headers=auth)
    p3 = c.post("/api/production-orders", headers=auth,
                json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 5}).json()
    c.post(f"/api/production-orders/{p3['id']}/cancel", headers=auth)

    r = c.get("/api/manufacturing/dashboard", headers=auth).json()
    assert r["pipeline"]["draft"] == 1
    assert r["pipeline"]["started"] == 1
    assert r["pipeline"]["cancelled"] == 1
    assert Decimal(r["totals"]["wip_cost"]) == Decimal("10")  # 5 widgets × 2 buttons × $1
    # p2 consumed 5 fabric (1 per output × 5 widgets), so 30 - 5 = 25 remain
    assert Decimal(r["totals"]["custodial_qty"]) == Decimal("25")


def test_wip_aging_buckets_started_pos(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "w1@m.test")
    cust, out, button, fabric, bom, plan = _scenario(c, auth)
    po = c.post("/api/production-orders", headers=auth,
                json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 5}).json()
    c.post(f"/api/production-orders/{po['id']}/start", headers=auth)

    r = c.get("/api/manufacturing/wip-aging", headers=auth).json()
    assert "summary" in r
    assert "buckets" in r
    # Just-started PO lands in 0-7d
    assert r["summary"]["0-7d"]["count"] == 1
    assert Decimal(r["summary"]["0-7d"]["total_wip_cost"]) == Decimal("10")


def test_production_summary_groups_by_state(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "s1@m.test")
    cust, out, button, fabric, bom, plan = _scenario(c, auth)
    p1 = c.post("/api/production-orders", headers=auth,
                json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 5}).json()
    p2 = c.post("/api/production-orders", headers=auth,
                json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 3}).json()
    c.post(f"/api/production-orders/{p2['id']}/start", headers=auth)

    r = c.get("/api/manufacturing/production-summary", headers=auth).json()
    assert r["draft"]["count"] == 1
    assert Decimal(r["draft"]["output_qty"]) == Decimal("5")
    assert r["started"]["count"] == 1
    assert Decimal(r["started"]["cost"]) == Decimal("6")  # 3 × 2 buttons × $1


def test_customer_custody_report(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "c1@m.test")
    cust, out, button, fabric, bom, plan = _scenario(c, auth)

    r = c.get("/api/manufacturing/customer-custody", headers=auth).json()
    assert len(r) == 1
    row = r[0]
    assert row["customer_id"] == cust["id"]
    assert row["product_id"] == fabric["id"]
    assert Decimal(row["qty_on_hand"]) == Decimal("30")
    assert Decimal(row["declared_value_open"]) == Decimal("300")


def test_reports_tenant_isolation(client):
    c, _ = client
    auth_a = _signup(c, "manufacturing", "ia@m.test")
    auth_b = _signup(c, "manufacturing", "ib@m.test")
    _scenario(c, auth_a)
    # Tenant B sees empty reports
    r = c.get("/api/manufacturing/dashboard", headers=auth_b).json()
    assert r["pipeline"]["draft"] == 0
    assert Decimal(r["totals"]["custodial_qty"]) == Decimal("0")
    r = c.get("/api/manufacturing/customer-custody", headers=auth_b).json()
    assert r == []
