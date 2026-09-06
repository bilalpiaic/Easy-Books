"""Tests for the first-party Weighbridge mill workspace (#391)."""
from pathlib import Path

from services.weaving_calc import net_kg, weight_triple


def _signup(client, email, *, model="trader", company="Mill Co"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Clerk", "company_name": company, "business_model": model,
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install(client, auth, *modules):
    for m in modules:
        r = client.post(f"/api/modules/{m}/install", headers=auth)
        assert r.status_code in (200, 201), f"{m}: {r.text}"


def test_weighbridge_router_does_not_touch_posting():
    src = Path(__file__).resolve().parents[1] / "routers" / "weighbridge.py"
    text = src.read_text()
    assert "services.posting" not in text
    assert "import posting" not in text
    assert "post_transaction" not in text


def test_net_kg_abs_for_slip():
    assert float(net_kg(110, 10)) == 100.0
    t = weight_triple(100)
    assert t["kg"] == 100.0
    assert abs(t["lbs"] - 220.46226218) < 0.001
    assert abs(t["bags"] - 2.2046226218) < 0.001


def test_weighbridge_module_gate(client):
    auth = _signup(client, "wb-gate@test.com")
    r = client.get("/api/weighbridge/tickets", headers=auth)
    assert r.status_code == 403
    assert "not installed" in r.json()["detail"]


def test_weighbridge_hidden_from_hospital(client):
    from db import MODULES_BY_MODEL
    assert "weighbridge" not in MODULES_BY_MODEL["hospital"]
    auth = _signup(client, "wb-hosp@test.com", model="simple", company="City Clinic")
    listed = client.get("/api/modules", headers=auth)
    assert listed.status_code == 200, listed.text
    wb = next(m for m in listed.json() if m["id"] == "weighbridge")
    assert wb["installed"] is False
    r = client.get("/api/weighbridge/summary", headers=auth)
    assert r.status_code == 403


def test_weighbridge_preinstalled_on_manufacturing(client):
    auth = _signup(client, "wb-mfg@test.com", model="manufacturing", company="Mfg Mill")
    listed = client.get("/api/modules", headers=auth)
    wb = next(m for m in listed.json() if m["id"] == "weighbridge")
    assert wb["installed"] is True
    r = client.get("/api/weighbridge/tickets", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0


def test_weighbridge_on_yarn_spinning_model_defaults():
    from db import MODULES_BY_MODEL
    assert "weighbridge" in MODULES_BY_MODEL["yarn_spinning"]
    assert "weighbridge" in MODULES_BY_MODEL["manufacturing"]


def test_weighbridge_happy_path_and_state_machine(client):
    auth = _signup(client, "wb-ok@test.com")
    _install(client, auth, "weighbridge")

    create = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "inbound",
        "vehicle_no": "LES-1",
        "driver_name": "Ali",
        "party_type": "other",
        "party_name": "Walk-in",
        "commodity": "Cotton",
        "lot_ref": "L-9",
    })
    assert create.status_code == 201, create.text
    ticket = create.json()
    assert ticket["number"].startswith("WB-")
    assert ticket["status"] == "draft"
    tid = ticket["id"]

    first = client.post(f"/api/weighbridge/tickets/{tid}/weigh", headers=auth, json={
        "kind": "gross", "kg": 1020,
    })
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "weighed_in"
    assert first.json()["gross_kg"] == 1020.0
    assert first.json()["first_weigh_kind"] == "gross"

    same_side = client.post(f"/api/weighbridge/tickets/{tid}/weigh", headers=auth, json={
        "kind": "gross", "kg": 1030,
    })
    assert same_side.status_code == 400

    second = client.post(f"/api/weighbridge/tickets/{tid}/weigh", headers=auth, json={
        "kind": "tare", "kg": 20,
    })
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["status"] == "completed"
    assert body["net_kg"] == 1000.0
    assert abs(body["net"]["lbs"] - 2204.6226218) < 0.01
    assert abs(body["net"]["bags"] - 22.046226218) < 0.01

    cancel_done = client.post(f"/api/weighbridge/tickets/{tid}/cancel", headers=auth, json={
        "reason": "too late",
    })
    assert cancel_done.status_code == 400

    listing = client.get("/api/weighbridge/tickets?q=LES-1", headers=auth)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["number"] == ticket["number"]

    hub = client.get("/api/weighbridge/summary", headers=auth)
    assert hub.status_code == 200
    assert hub.json()["today_count"] >= 1
    assert hub.json()["on_site"] == 0
    assert hub.json()["net_kg_today"] == 1000.0

    register = client.get("/api/weighbridge/reports/register", headers=auth)
    assert register.status_code == 200
    assert register.json()["total"] >= 1


def test_weighbridge_create_with_first_weigh_and_cancel(client):
    auth = _signup(client, "wb-first@test.com")
    _install(client, auth, "weighbridge")
    r = client.post("/api/weighbridge/tickets", headers=auth, json={
        "vehicle_no": "LHR-2",
        "first_weigh_kind": "tare",
        "first_kg": 18.5,
    })
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "weighed_in"
    assert r.json()["tare_kg"] == 18.5
    tid = r.json()["id"]
    cancelled = client.post(f"/api/weighbridge/tickets/{tid}/cancel", headers=auth, json={
        "reason": "wrong vehicle",
    })
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancel_reason"] == "wrong vehicle"
    weigh = client.post(f"/api/weighbridge/tickets/{tid}/weigh", headers=auth, json={
        "kind": "gross", "kg": 900,
    })
    assert weigh.status_code == 400


def test_weighbridge_tenant_isolation(client):
    a = _signup(client, "wb-a@test.com")
    b = _signup(client, "wb-b@test.com")
    _install(client, a, "weighbridge")
    _install(client, b, "weighbridge")
    created = client.post("/api/weighbridge/tickets", headers=a, json={"vehicle_no": "AAA-1"})
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    other = client.get(f"/api/weighbridge/tickets/{tid}", headers=b)
    assert other.status_code == 404
    listing = client.get("/api/weighbridge/tickets", headers=b)
    assert listing.json()["total"] == 0


def test_weighbridge_copy_gate_pass(client):
    auth = _signup(client, "wb-gp@test.com")
    _install(client, auth, "weighbridge")
    cust = client.post("/api/customers", headers=auth, json={"name": "Buyer"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-09-01", "due_date": "2026-09-30",
        "gst_rate": 0,
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 201, inv.text
    invoice_id = inv.json()["id"]

    ticket = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "inbound",
        "vehicle_no": "GP-TRUCK",
        "lot_ref": "LOT-X",
        "gross_kg": 500,
        "tare_kg": 20,
        "invoice_id": invoice_id,
    })
    assert ticket.status_code == 201, ticket.text
    assert ticket.json()["status"] == "completed"
    tid = ticket.json()["id"]
    number = ticket.json()["number"]

    copied = client.post(f"/api/weighbridge/tickets/{tid}/copy-gate-pass", headers=auth, json={})
    assert copied.status_code == 200, copied.text
    assert copied.json()["gate_pass_no"] == number
    assert copied.json()["custom_fields"]["x.gate_pass_no"] == number
    assert copied.json()["custom_fields"]["x.lot_ref"] == "LOT-X"

    fetched = client.get(f"/api/invoices/{invoice_id}", headers=auth)
    assert fetched.status_code == 200, fetched.text
    cf = fetched.json().get("custom_fields") or {}
    assert cf.get("x.gate_pass_no") == number


def test_weighbridge_copy_gate_pass_rejects_outbound(client):
    auth = _signup(client, "wb-out@test.com")
    _install(client, auth, "weighbridge")
    ticket = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "outbound",
        "vehicle_no": "OUT-1",
        "gross_kg": 200,
        "tare_kg": 20,
    })
    assert ticket.json()["status"] == "completed"
    r = client.post(
        f"/api/weighbridge/tickets/{ticket.json()['id']}/copy-gate-pass",
        headers=auth, json={"invoice_id": 1},
    )
    assert r.status_code == 400


def test_plan_blocks_weighbridge_on_pro():
    from models import Tenant
    from services.entitlements import plan_allows

    pro = Tenant(name="p", plan="pro")
    assert not plan_allows(pro, "weighbridge")
    ent = Tenant(name="e", plan="enterprise")
    assert plan_allows(ent, "weighbridge")
