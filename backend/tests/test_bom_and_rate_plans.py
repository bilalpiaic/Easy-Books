"""V2.3 tests: Bills of Material + Rate Plans + Customer ↔ Plan assignment."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import BomHeader, BomLine, CustomerRatePlan, RatePlan


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


def _signup(client: TestClient, model: str, email: str) -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": model,
        },
    )
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "password123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_product(client: TestClient, auth: dict, code: str, name: str = None) -> dict:
    return client.post(
        "/api/products", headers=auth,
        json={
            "code": code, "name": name or code, "unit": "ea",
            "product_type": "stock", "default_rate": 0,
        },
    ).json()


# ── BoM CRUD ────────────────────────────────────────────────────────────────


def test_create_bom_with_mixed_sources(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "bom1@m.test")
    out = _make_product(c, auth, "WIDGET")
    raw = _make_product(c, auth, "RAW-A")
    cust = _make_product(c, auth, "CUST-FABRIC")

    r = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"],
            "output_qty": 1,
            "description": "v1 recipe",
            "lines": [
                {"component_product_id": raw["id"], "qty_per_output": 2, "source": "own_stock"},
                {"component_product_id": cust["id"], "qty_per_output": 1, "source": "customer_supplied"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version"] == 1
    assert body["is_active"] is True
    assert len(body["lines"]) == 2
    sources = {ln["source"] for ln in body["lines"]}
    assert sources == {"own_stock", "customer_supplied"}


def test_bom_requires_at_least_one_line(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "empty@m.test")
    out = _make_product(c, auth, "EMPTY")
    r = c.post(
        "/api/bom", headers=auth,
        json={"output_product_id": out["id"], "output_qty": 1, "lines": []},
    )
    assert r.status_code == 400


def test_bom_rejects_invalid_source(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "bad@m.test")
    out = _make_product(c, auth, "OUT")
    raw = _make_product(c, auth, "RAW")
    r = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"],
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 1, "source": "wild"}],
        },
    )
    assert r.status_code == 400


def test_bom_rejects_nonpositive_qty(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "zero@m.test")
    out = _make_product(c, auth, "OUT")
    raw = _make_product(c, auth, "RAW")
    r = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"],
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 0}],
        },
    )
    assert r.status_code == 400


def test_bom_rejects_cross_tenant_product(client):
    c, _ = client
    auth_a = _signup(c, "manufacturing", "a@m.test")
    auth_b = _signup(c, "manufacturing", "b@m.test")
    out_a = _make_product(c, auth_a, "A-OUT")
    raw_b = _make_product(c, auth_b, "B-RAW")
    # Tenant A tries to reference Tenant B's product as a component
    r = c.post(
        "/api/bom", headers=auth_a,
        json={
            "output_product_id": out_a["id"],
            "lines": [{"component_product_id": raw_b["id"], "qty_per_output": 1}],
        },
    )
    assert r.status_code == 400


def test_bom_versioning_deactivates_prior(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "ver@m.test")
    out = _make_product(c, auth, "VER-OUT")
    raw = _make_product(c, auth, "VER-RAW")

    v1 = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"],
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 1}],
        },
    ).json()
    v2 = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"],
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 2}],
        },
    ).json()
    assert v1["version"] == 1
    assert v2["version"] == 2
    # v1 is now inactive, v2 is active
    with Session(engine) as s:
        h1 = s.get(BomHeader, v1["id"])
        h2 = s.get(BomHeader, v2["id"])
        assert h1.is_active is False
        assert h2.is_active is True


def test_bom_deactivate_endpoint(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "deact@m.test")
    out = _make_product(c, auth, "D-OUT")
    raw = _make_product(c, auth, "D-RAW")
    bom = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"],
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 1}],
        },
    ).json()
    r = c.patch(f"/api/bom/{bom['id']}/deactivate", headers=auth)
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_bom_list_filters_by_output_product(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "list@m.test")
    out1 = _make_product(c, auth, "OUT-1")
    out2 = _make_product(c, auth, "OUT-2")
    raw = _make_product(c, auth, "RAW")
    c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out1["id"],
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 1}],
        },
    )
    c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out2["id"],
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 1}],
        },
    )
    r = c.get(f"/api/bom?output_product_id={out1['id']}", headers=auth)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["output_product_id"] == out1["id"] for i in items)
    assert len(items) == 1


def test_bom_tenant_isolation_on_get(client):
    c, _ = client
    auth_a = _signup(c, "manufacturing", "iso-a@m.test")
    auth_b = _signup(c, "manufacturing", "iso-b@m.test")
    out = _make_product(c, auth_a, "OUT")
    raw = _make_product(c, auth_a, "RAW")
    bom_a = c.post(
        "/api/bom", headers=auth_a,
        json={
            "output_product_id": out["id"],
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 1}],
        },
    ).json()
    # Tenant B cannot read tenant A's BoM
    r = c.get(f"/api/bom/{bom_a['id']}", headers=auth_b)
    assert r.status_code == 404


# ── RatePlan CRUD ────────────────────────────────────────────────────────────


def test_create_rate_plan(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "rp1@m.test")
    r = c.post(
        "/api/rate-plans", headers=auth,
        json={
            "code": "STITCH-STD", "name": "Standard stitching",
            "per_unit_rate": "12.50",
            "includes_materials_at_cost": True,
            "overhead_pct": "5", "margin_pct": "10",
        },
    )
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["version"] == 1
    assert plan["is_active"] is True
    assert Decimal(str(plan["per_unit_rate"])) == Decimal("12.50")


def test_rate_plan_rejects_negative_rate(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "neg@m.test")
    r = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "BAD", "name": "Bad", "per_unit_rate": "-1"},
    )
    assert r.status_code == 400


def test_rate_plan_versioning_deactivates_prior(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "rpv@m.test")
    p1 = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "SAME", "name": "v1", "per_unit_rate": "10"},
    ).json()
    p2 = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "SAME", "name": "v2", "per_unit_rate": "15"},
    ).json()
    assert p1["version"] == 1
    assert p2["version"] == 2
    with Session(engine) as s:
        assert s.get(RatePlan, p1["id"]).is_active is False
        assert s.get(RatePlan, p2["id"]).is_active is True


def test_update_rate_plan(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "upd@m.test")
    plan = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "U", "name": "U", "per_unit_rate": "10"},
    ).json()
    r = c.put(
        f"/api/rate-plans/{plan['id']}", headers=auth,
        json={"name": "Updated", "per_unit_rate": "20"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Updated"
    assert Decimal(str(body["per_unit_rate"])) == Decimal("20")


def test_update_rate_plan_rejects_negative(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "uneg@m.test")
    plan = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "X", "name": "X", "per_unit_rate": "10"},
    ).json()
    r = c.put(
        f"/api/rate-plans/{plan['id']}", headers=auth,
        json={"per_unit_rate": "-5"},
    )
    assert r.status_code == 400


def test_rate_plan_tenant_isolation_on_update(client):
    c, _ = client
    auth_a = _signup(c, "manufacturing", "ti-a@m.test")
    auth_b = _signup(c, "manufacturing", "ti-b@m.test")
    plan_a = c.post(
        "/api/rate-plans", headers=auth_a,
        json={"code": "A", "name": "A", "per_unit_rate": "10"},
    ).json()
    r = c.put(
        f"/api/rate-plans/{plan_a['id']}", headers=auth_b,
        json={"name": "stolen"},
    )
    assert r.status_code == 404


# ── Customer assignment ─────────────────────────────────────────────────────


def _make_customer(c: TestClient, auth: dict, name: str) -> dict:
    return c.post("/api/customers", headers=auth, json={"name": name}).json()


def test_assign_plan_to_customer(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "asg@m.test")
    cust = _make_customer(c, auth, "Brand Co.")
    plan = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "STD", "name": "Std", "per_unit_rate": "10"},
    ).json()
    r = c.post(
        "/api/rate-plans/assign", headers=auth,
        json={"customer_id": cust["id"], "rate_plan_id": plan["id"]},
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_active"] is True


def test_reassign_deactivates_prior(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "rea@m.test")
    cust = _make_customer(c, auth, "Brand Co.")
    p1 = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "P1", "name": "P1", "per_unit_rate": "10"},
    ).json()
    p2 = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "P2", "name": "P2", "per_unit_rate": "20"},
    ).json()
    c.post(
        "/api/rate-plans/assign", headers=auth,
        json={"customer_id": cust["id"], "rate_plan_id": p1["id"]},
    )
    c.post(
        "/api/rate-plans/assign", headers=auth,
        json={"customer_id": cust["id"], "rate_plan_id": p2["id"]},
    )
    with Session(engine) as s:
        rows = s.exec(
            select(CustomerRatePlan).where(
                CustomerRatePlan.customer_id == cust["id"]
            )
        ).all()
        active = [r for r in rows if r.is_active]
        assert len(active) == 1
        assert active[0].rate_plan_id == p2["id"]


def test_reassign_existing_pair_reactivates(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "rev@m.test")
    cust = _make_customer(c, auth, "Co")
    p = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "P", "name": "P", "per_unit_rate": "10"},
    ).json()
    a1 = c.post(
        "/api/rate-plans/assign", headers=auth,
        json={"customer_id": cust["id"], "rate_plan_id": p["id"]},
    ).json()
    p2 = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "Q", "name": "Q", "per_unit_rate": "20"},
    ).json()
    # Switch to p2 — a1 becomes inactive
    c.post(
        "/api/rate-plans/assign", headers=auth,
        json={"customer_id": cust["id"], "rate_plan_id": p2["id"]},
    )
    # Switch back to p — should reactivate existing row, not create new
    a3 = c.post(
        "/api/rate-plans/assign", headers=auth,
        json={"customer_id": cust["id"], "rate_plan_id": p["id"]},
    ).json()
    assert a3["id"] == a1["id"]
    assert a3["is_active"] is True


def test_list_customer_plans(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "lcp@m.test")
    cust = _make_customer(c, auth, "Brand Co.")
    p = c.post(
        "/api/rate-plans", headers=auth,
        json={"code": "L", "name": "L", "per_unit_rate": "10"},
    ).json()
    c.post(
        "/api/rate-plans/assign", headers=auth,
        json={"customer_id": cust["id"], "rate_plan_id": p["id"]},
    )
    r = c.get(f"/api/rate-plans/customer/{cust['id']}", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["is_active"] is True
    assert body[0]["plan"]["code"] == "L"


def test_assign_rejects_cross_tenant_customer(client):
    c, _ = client
    auth_a = _signup(c, "manufacturing", "xa@m.test")
    auth_b = _signup(c, "manufacturing", "xb@m.test")
    cust_b = _make_customer(c, auth_b, "Their customer")
    plan_a = c.post(
        "/api/rate-plans", headers=auth_a,
        json={"code": "X", "name": "X", "per_unit_rate": "10"},
    ).json()
    r = c.post(
        "/api/rate-plans/assign", headers=auth_a,
        json={"customer_id": cust_b["id"], "rate_plan_id": plan_a["id"]},
    )
    assert r.status_code == 404


# ── Multi-output BoMs (#223) ────────────────────────────────────────────────


def test_create_bom_multi_output_fixed_pct(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "multi1@m.test")
    primary = _make_product(c, auth, "MAIN")
    byprod = _make_product(c, auth, "SCRAP-METAL")
    raw = _make_product(c, auth, "RAW-X")

    r = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": primary["id"],
            "output_qty": 10,
            "cost_alloc_method": "fixed_pct",
            "lines": [
                {"component_product_id": raw["id"], "qty_per_output": 1, "source": "own_stock"},
            ],
            "outputs": [
                {"product_id": primary["id"], "qty_per_batch": 10, "role": "primary", "alloc_pct": 80},
                {"product_id": byprod["id"], "qty_per_batch": 2, "role": "by_product", "alloc_pct": 20},
            ],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["cost_alloc_method"] == "fixed_pct"
    assert len(body["outputs"]) == 2
    roles = {o["role"] for o in body["outputs"]}
    assert roles == {"primary", "by_product"}


def test_bom_fixed_pct_must_sum_100(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "multi2@m.test")
    primary = _make_product(c, auth, "MAIN2")
    byprod = _make_product(c, auth, "BY2")
    raw = _make_product(c, auth, "RAW2")
    r = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": primary["id"],
            "output_qty": 1,
            "cost_alloc_method": "fixed_pct",
            "lines": [
                {"component_product_id": raw["id"], "qty_per_output": 1, "source": "own_stock"},
            ],
            "outputs": [
                {"product_id": primary["id"], "qty_per_batch": 1, "role": "primary", "alloc_pct": 50},
                {"product_id": byprod["id"], "qty_per_batch": 1, "role": "by_product", "alloc_pct": 30},
            ],
        },
    )
    assert r.status_code == 400
    assert "100" in r.json()["detail"]


def test_bom_legacy_create_synthesizes_primary_output(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "legacyout@m.test")
    out = _make_product(c, auth, "LEGACY")
    raw = _make_product(c, auth, "RAW-L")
    r = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"],
            "output_qty": 5,
            "lines": [
                {"component_product_id": raw["id"], "qty_per_output": 1, "source": "own_stock"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["outputs"]) == 1
    assert body["outputs"][0]["role"] == "primary"
    assert body["outputs"][0]["product_id"] == out["id"]
