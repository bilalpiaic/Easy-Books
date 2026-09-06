"""Tests for spinning module."""
from decimal import Decimal

from services.spinning_calc import net_kg, stage_yield_pct, weight_triple


def _signup(client, email, company="Spin Co"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Spinner", "company_name": company, "business_model": "trader",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install(client, auth, *modules):
    for m in modules:
        r = client.post(f"/api/modules/{m}/install", headers=auth)
        assert r.status_code in (200, 201), f"{m}: {r.text}"


def test_spinning_module_gate(client):
    auth = _signup(client, "spin-gate@test.com")
    r = client.get("/api/spinning/lots", headers=auth)
    assert r.status_code == 403


def test_spinning_happy_path(client):
    auth = _signup(client, "spin-ok@test.com")
    _install(client, auth, "inventory", "purchase_store", "spinning")

    prod = client.post("/api/products", headers=auth, json={
        "code": "COTTON", "name": "Raw Cotton", "unit": "kg", "product_type": "stock",
    }).json()
    yarn = client.post("/api/products", headers=auth, json={
        "code": "YARN20", "name": "20Ne Yarn", "unit": "kg", "product_type": "stock",
    }).json()

    spec = client.post("/api/spinning/yarn-specs", headers=auth, json={
        "code": "YS20", "name": "20Ne Carded", "count_ne": 20, "output_product_id": yarn["id"],
    }).json()

    lot = client.post("/api/spinning/lots", headers=auth, json={
        "yarn_spec_id": spec["id"], "start_date": "2026-07-01", "target_output_kg": 1000,
    }).json()
    assert lot["number"].startswith("SL-")

    client.patch(f"/api/spinning/lots/{lot['id']}/start", headers=auth)

    br = client.post("/api/spinning/bale-receipts", headers=auth, json={
        "product_id": prod["id"], "date": "2026-07-02", "gross_kg": 220, "tare_kg": 20,
        "rate_per_kg": 380, "spin_lot_id": lot["id"],
    }).json()
    assert br["net_kg"] == 200.0

    approved = client.patch(f"/api/spinning/bale-receipts/{br['id']}/approve", headers=auth)
    assert approved.status_code == 200

    stage = client.post("/api/spinning/stages", headers=auth, json={
        "spin_lot_id": lot["id"], "stage": "opening", "date": "2026-07-03",
        "input_kg": 200, "output_kg": 196, "waste_kg": 4,
    }).json()
    assert stage["status"] == "posted"

    dash = client.get("/api/spinning/reports/dashboard", headers=auth).json()
    assert "kpis" in dash

    calc = client.post("/api/spinning/calculators/yield", headers=auth, json={
        "input_kg": 100, "output_kg": 85,
    }).json()
    assert calc["yield_pct"] == 85.0


def test_spinning_calc_helpers():
    t = weight_triple(100)
    assert t["kg"] == 100.0
    assert float(net_kg(110, 10)) == 100.0
    assert stage_yield_pct(100, 85) == 85.0


def test_yarn_spinning_backfill_restores_module(client):
    """Existing yarn_spinning tenants missing spinning get it back on boot backfill."""
    from sqlmodel import Session
    import db as db_mod
    from models import Tenant
    from routers.modules import _get_enabled

    auth = _signup(client, "spin-restore@test.com")
    me = client.get("/api/auth/me", headers=auth)
    assert me.status_code == 200, me.text
    tid = me.json()["tenant"]["id"]

    with Session(db_mod.engine) as s:
        mill = s.get(Tenant, tid)
        mill.business_model = "yarn_spinning"
        mill.enabled_modules = '["base"]'
        s.add(mill)
        s.commit()

    blocked = client.get("/api/spinning/lots", headers=auth)
    assert blocked.status_code == 403

    with Session(db_mod.engine) as s:
        db_mod._ensure_yarn_spinning_module(s)
        mill = s.get(Tenant, tid)
        assert "spinning" in _get_enabled(mill)

    ok = client.get("/api/spinning/lots", headers=auth)
    assert ok.status_code == 200, ok.text
    listed = client.get("/api/modules", headers=auth)
    spinning = next(m for m in listed.json() if m["id"] == "spinning")
    assert spinning["installed"] is True


def test_yarn_spinning_backfill_skips_other_models(client):
    from sqlmodel import Session
    import db as db_mod
    from models import Tenant
    from routers.modules import _get_enabled

    auth = _signup(client, "spin-skip@test.com")
    me = client.get("/api/auth/me", headers=auth)
    tid = me.json()["tenant"]["id"]

    with Session(db_mod.engine) as s:
        t = s.get(Tenant, tid)
        assert t.business_model != "yarn_spinning"
        db_mod._ensure_yarn_spinning_module(s)
        t = s.get(Tenant, tid)
        assert "spinning" not in _get_enabled(t)

    r = client.get("/api/spinning/lots", headers=auth)
    assert r.status_code == 403
