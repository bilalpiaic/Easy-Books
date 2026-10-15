"""Shop-floor PLC ingest — mill auto-recording from a gateway POST."""
from decimal import Decimal


def _signup(client, email, company="Mill Co"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Mill Owner", "company_name": company, "business_model": "trader",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install(client, auth, *modules):
    for m in modules:
        r = client.post(f"/api/modules/{m}/install", headers=auth)
        assert r.status_code in (200, 201), f"{m}: {r.text}"


def test_plc_module_gate(client):
    auth = _signup(client, "plc-gate@test.com")
    r = client.get("/api/plc/devices", headers=auth)
    assert r.status_code == 403


def test_plc_weaving_production_auto_apply_and_idempotent(client):
    auth = _signup(client, "plc-weave@test.com")
    _install(client, auth, "inventory", "weaving")

    cust = client.post("/api/customers", headers=auth, json={"name": "Buyer"}).json()
    loom = client.post("/api/weaving/looms", headers=auth, json={"code": "L-01", "name": "Loom 1"}).json()
    shift = client.post("/api/weaving/shifts", headers=auth, json={"code": "A", "name": "Morning"}).json()
    contract = client.post("/api/weaving/contracts", headers=auth, json={
        "customer_id": cust["id"], "start_date": "2026-10-01",
        "contract_meters": 10000, "weaving_rate": 12, "fabric_return_price_per_meter": 55,
    }).json()

    device = client.post("/api/plc/devices", headers=auth, json={
        "code": "L-01",
        "name": "Airjet 1",
        "protocol": "modbus_tcp",
        "event_type": "weaving.production",
        "binding": {"contract_id": contract["id"], "shift_code": "A"},
    })
    assert device.status_code == 201, device.text
    assert device.json()["code"] == "L-01"

    body = {
        "idempotency_key": "L-01-2026-10-15T08:00Z",
        "machine_code": "L-01",
        "event_type": "weaving.production",
        "occurred_at": "2026-10-15T08:00:00Z",
        "readings": {
            "grey_meters": 2200,
            "warp_yarn_kg": 120,
            "weft_yarn_kg": 80,
        },
    }
    r1 = client.post("/api/plc/ingest", headers=auth, json=body)
    assert r1.status_code == 201, r1.text
    ev = r1.json()
    assert ev["status"] == "applied"
    assert ev["result_doc_type"] == "wv_production"
    assert ev["result_number"].startswith("WP-")
    assert ev["replayed"] is False

    r2 = client.post("/api/plc/ingest", headers=auth, json=body)
    assert r2.status_code == 200, r2.text
    assert r2.json()["replayed"] is True
    assert r2.json()["id"] == ev["id"]

    prods = client.get("/api/weaving/productions", headers=auth).json()
    assert len(prods) == 1
    assert prods[0]["source"] == "plc"
    assert prods[0]["grey_meters"] == 2200.0
    assert prods[0]["loom_id"] == loom["id"]
    assert prods[0]["shift_id"] == shift["id"]
    assert prods[0]["total_yarn_kg"] == 200.0

    listed = client.get("/api/plc/events", headers=auth).json()
    assert listed["total"] == 1
    assert listed["items"][0]["status"] == "applied"


def test_plc_spinning_stage_waits_for_apply_no_silent_gl(client):
    auth = _signup(client, "plc-spin@test.com")
    _install(client, auth, "inventory", "purchase_store", "spinning")

    yarn = client.post("/api/products", headers=auth, json={
        "code": "YARN20", "name": "20Ne Yarn", "unit": "kg", "product_type": "stock",
    }).json()
    spec = client.post("/api/spinning/yarn-specs", headers=auth, json={
        "code": "YS20", "name": "20Ne", "count_ne": 20, "output_product_id": yarn["id"],
    }).json()
    lot = client.post("/api/spinning/lots", headers=auth, json={
        "yarn_spec_id": spec["id"], "start_date": "2026-10-01", "target_output_kg": 1000,
    }).json()
    machine = client.post("/api/spinning/machines", headers=auth, json={
        "code": "RING-01", "name": "Ring 1", "machine_type": "ring",
    }).json()

    client.post("/api/plc/devices", headers=auth, json={
        "code": "RING-01",
        "name": "Ring frame 1",
        "event_type": "spinning.stage",
        "binding": {"spin_lot_id": lot["id"], "stage": "spinning"},
        # default auto_apply for spinning.stage is False
    })

    ingest = client.post("/api/plc/ingest", headers=auth, json={
        "idempotency_key": "RING-01-shift-a",
        "machine_code": "RING-01",
        "event_type": "spinning.stage",
        "readings": {"input_kg": 200, "output_kg": 196, "waste_kg": 4},
    })
    assert ingest.status_code == 201, ingest.text
    ev = ingest.json()
    assert ev["status"] == "received"
    assert ev["result_doc_id"] is None

    stages = client.get("/api/spinning/stages", headers=auth).json()
    assert stages == []

    applied = client.post(f"/api/plc/events/{ev['id']}/apply", headers=auth)
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    assert applied.json()["result_doc_type"] == "sp_stage_entry"

    stages = client.get("/api/spinning/stages", headers=auth).json()
    assert len(stages) == 1
    assert stages[0]["source"] == "plc"
    assert stages[0]["status"] == "posted"
    assert stages[0]["machine_id"] == machine["id"]


def test_plc_cone_output_draft_and_api_key_auth(client):
    auth = _signup(client, "plc-cone@test.com")
    _install(client, auth, "inventory", "purchase_store", "spinning")
    yarn = client.post("/api/products", headers=auth, json={
        "code": "YARN20", "name": "20Ne Yarn", "unit": "kg", "product_type": "stock",
    }).json()
    spec = client.post("/api/spinning/yarn-specs", headers=auth, json={
        "code": "YS20", "name": "20Ne", "output_product_id": yarn["id"],
    }).json()
    lot = client.post("/api/spinning/lots", headers=auth, json={
        "yarn_spec_id": spec["id"], "start_date": "2026-10-01", "target_output_kg": 500,
    }).json()
    client.post("/api/plc/devices", headers=auth, json={
        "code": "AUTO-01",
        "name": "Autoconer",
        "event_type": "spinning.cone_output",
        "binding": {"spin_lot_id": lot["id"]},
    })

    key = client.post("/api/auth/keys", headers=auth, json={"name": "shop-floor gateway"}).json()
    assert key["key"].startswith("eb_live_")
    gw = {"Authorization": f"Bearer {key['key']}"}

    r = client.post("/api/plc/ingest", headers=gw, json={
        "idempotency_key": "AUTO-01-cones-1",
        "machine_code": "AUTO-01",
        "event_type": "spinning.cone_output",
        "readings": {"net_kg": 48.5, "cones_count": 120},
    })
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "applied"
    cones = client.get("/api/spinning/cone-outputs", headers=auth).json()
    assert len(cones) == 1
    assert cones[0]["status"] == "draft"
    assert cones[0]["source"] == "plc"


def test_plc_weighbridge_creates_ticket(client):
    auth = _signup(client, "plc-wb@test.com")
    _install(client, auth, "inventory", "weighbridge")
    client.post("/api/plc/devices", headers=auth, json={
        "code": "WB-01",
        "name": "Inbound scale",
        "event_type": "weighbridge.weigh",
    })
    r = client.post("/api/plc/ingest", headers=auth, json={
        "idempotency_key": "WB-01-truck-1",
        "machine_code": "WB-01",
        "event_type": "weighbridge.weigh",
        "readings": {
            "vehicle_no": "LES-4012",
            "gross_kg": 18200,
            "tare_kg": 7400,
            "commodity": "Raw cotton",
        },
    })
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "applied"
    tickets = client.get("/api/weighbridge/tickets", headers=auth).json()
    items = tickets["items"] if isinstance(tickets, dict) else tickets
    assert len(items) == 1
    assert items[0]["source"] == "plc"
    assert items[0]["status"] == "completed"
    assert Decimal(str(items[0]["net_kg"])) == Decimal("10800.0000")


def test_plc_reject_and_missing_fields(client):
    auth = _signup(client, "plc-rej@test.com")
    _install(client, auth, "inventory", "weaving")
    r = client.post("/api/plc/ingest", headers=auth, json={
        "idempotency_key": "orphan-1",
        "machine_code": "UNKNOWN",
        "event_type": "weaving.production",
        "readings": {"grey_meters": 10},
        "apply": True,
    })
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["status"] == "error"
    assert "contract" in (ev["error_message"] or "").lower()

    rejected = client.post(f"/api/plc/events/{ev['id']}/reject", headers=auth, json={"reason": "bad tag"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_shop_floor_permission_registered():
    from services.permissions import PERMISSION_RESOURCES
    assert "shop_floor.plc" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["shop_floor.plc"]["category"] == "Shop Floor"
