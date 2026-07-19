"""Tests for weaving module (#140)."""
from decimal import Decimal

from services.weaving_calc import (
    KG_TO_LB, weight_triple, rate_per_lb, sizing_gain_shrink_pct,
    production_efficiency_pct, net_kg, dispatch_value, weaving_charges, net_receivable,
)


def test_weight_triple_and_rate():
    t = weight_triple(100)
    assert t["kg"] == 100.0
    assert t["lbs"] > 220.0
    assert t["bags"] > 2.0
    assert abs(rate_per_lb(220.46226218) - 100.0) < 0.01


def test_sizing_and_efficiency():
    assert sizing_gain_shrink_pct(100, 95) == -5.0
    assert sizing_gain_shrink_pct(100, 105) == 5.0
    assert production_efficiency_pct(500, 1000) == 50.0
    assert production_efficiency_pct(100, 0) == 0.0
    assert float(net_kg(110, 10)) == 100.0


def test_dispatch_math():
    dval = dispatch_value(100, 50)
    billed = weaving_charges(100, 10)
    assert float(dval) == 5000.0
    assert float(billed) == 1000.0
    assert float(net_receivable(dval, billed)) == 4000.0


def _signup(client, email, company="Weave Co"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Weaver", "company_name": company, "business_model": "trader",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install(client, auth, *modules):
    for m in modules:
        r = client.post(f"/api/modules/{m}/install", headers=auth)
        assert r.status_code in (200, 201), f"{m}: {r.text}"


def test_weaving_module_gate(client):
    auth = _signup(client, "weave-gate@test.com")
    r = client.get("/api/weaving/contracts", headers=auth)
    assert r.status_code == 403


def test_weaving_happy_path(client):
    auth = _signup(client, "weave-ok@test.com")
    _install(client, auth, "inventory", "weaving")

    # Customer
    cust = client.post("/api/customers", headers=auth, json={"name": "Textile Buyer"}).json()

    # Masters
    fq = client.post("/api/weaving/fabric-qualities", headers=auth,
                     json={"code": "FQ1", "name": "40s Poplin"}).json()
    assert fq["code"] == "FQ1"
    yt = client.post("/api/weaving/yarn-types", headers=auth,
                     json={"code": "YT1", "name": "Cotton 40s"}).json()
    loom = client.post("/api/weaving/looms", headers=auth,
                       json={"code": "L1", "name": "Loom-1"}).json()
    shift = client.post("/api/weaving/shifts", headers=auth,
                        json={"code": "A", "name": "Morning"}).json()
    op = client.post("/api/weaving/operators", headers=auth,
                     json={"code": "OP1", "name": "Ali"}).json()

    # Contract
    c = client.post("/api/weaving/contracts", headers=auth, json={
        "customer_id": cust["id"],
        "fabric_quality_id": fq["id"],
        "yarn_type_id": yt["id"],
        "start_date": "2026-07-01",
        "contract_meters": 10000,
        "pick_per_inch": 60,
        "assumed_yarn_rate_per_kg": 220.46226218,
        "fabric_return_price_per_meter": 50,
        "weaving_rate": 10,
        "expected_shrinkage_pct": 3,
        "status": "draft",
    }).json()
    assert c["number"].startswith("WC-")
    assert abs(c["assumed_yarn_rate_per_lb"] - 100.0) < 0.01
    assert c["expected_weaving_revenue"] == 100000.0

    # Yarn inward
    yi = client.post("/api/weaving/yarn-inwards", headers=auth, json={
        "contract_id": c["id"],
        "date": "2026-07-02",
        "gross_kg": 1100,
        "tare_kg": 100,
    }).json()
    assert yi["net_kg"] == 1000.0
    assert abs(yi["net_lbs"] - 2204.62) < 0.01
    assert abs(yi["rate_per_lb"] - 100.0) < 0.01

    # Sizing
    sz = client.post("/api/weaving/sizings", headers=auth, json={
        "contract_id": c["id"],
        "date": "2026-07-03",
        "input_kg": 500,
        "output_kg": 490,
        "sizing_cost": 2000,
    }).json()
    assert sz["gain_shrink_pct"] == -2.0
    assert "output_lbs" in sz and "output_bags" in sz

    # Production
    pr = client.post("/api/weaving/productions", headers=auth, json={
        "contract_id": c["id"],
        "loom_id": loom["id"],
        "shift_id": shift["id"],
        "operator_id": op["id"],
        "date": "2026-07-04",
        "warp_yarn_kg": 200,
        "weft_yarn_kg": 150,
        "grey_meters": 2000,
    }).json()
    assert pr["total_yarn_kg"] == 350.0
    assert pr["efficiency_pct"] == 20.0
    assert pr["weaving_charges"] == 20000.0
    assert "total_yarn_lbs" in pr

    # Dispatch
    dp = client.post("/api/weaving/dispatches", headers=auth, json={
        "contract_id": c["id"],
        "date": "2026-07-05",
        "meters": 1500,
    }).json()
    assert dp["dispatch_value"] == 75000.0
    assert dp["weaving_charges_billed"] == 15000.0
    assert dp["net_receivable"] == 60000.0

    # Reports
    dash = client.get("/api/weaving/reports/dashboard", headers=auth).json()
    assert dash["kpis"]["yarn_received"]["kg"] == 1000.0
    assert "lbs" in dash["kpis"]["yarn_received"]
    assert "bags" in dash["kpis"]["yarn_received"]
    assert len(dash["monthly_trend"]) >= 1

    daily = client.get("/api/weaving/reports/daily", headers=auth).json()
    assert daily["kpis"]["yarn_received"]["lbs"] > 0
    assert len(daily["activity"]) >= 4

    ctrl = client.get(f"/api/weaving/reports/contract-control?contract_id={c['id']}", headers=auth).json()
    assert ctrl["yarn_received"]["bags"] > 0
    assert ctrl["contract"]["id"] == c["id"]

    kpi = client.get("/api/weaving/reports/customer-kpi", headers=auth).json()
    assert kpi["portfolio"]["total_contracts"] == 1
    assert kpi["portfolio"]["yarn_received"]["kg"] == 1000.0
    assert len(kpi["contracts"]) == 1
