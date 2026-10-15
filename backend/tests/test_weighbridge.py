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
    assert "from services.posting" not in text
    assert "import posting" not in text
    assert "post_transaction" not in text


def test_net_kg_abs_for_slip():
    assert float(net_kg(110, 10)) == 100.0
    t = weight_triple(100)
    assert t["kg"] == 100.0
    assert t["lbs"] > 220.0
    assert t["bags"] > 2.0


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


def test_weighbridge_on_mill_model_defaults():
    """Weighbridge is a mill Operations module — not spinning-only.

    Pre-installed wherever a yard scale is practical (manufacturing, yarn
    spinning, textile processing). Weaving has no business_model — the
    weaving mill is manufacturing, or Optional Weaving which now depends
    on weighbridge. Hospital / telecom / services / simple stay Optional;
    trader keeps inventory+POS and installs from Add-ons.
    """
    from db import MODULE_REGISTRY, MODULES_BY_MODEL
    from services.marketplace.catalog import (
        MILL_WEIGHBRIDGE_MODELS,
        MILL_WEIGHBRIDGE_MODULES,
    )

    mills = {"manufacturing", "yarn_spinning", "textile_processing"}
    assert MILL_WEIGHBRIDGE_MODELS == mills
    assert MILL_WEIGHBRIDGE_MODULES == {"weaving", "spinning", "textile_processing"}
    for model in mills:
        assert "weighbridge" in MODULES_BY_MODEL[model], model
    for model in ("simple", "services", "trader", "telecom_franchise", "hospital", "pra_einvoice"):
        assert "weighbridge" not in MODULES_BY_MODEL[model], model
    for mid in MILL_WEIGHBRIDGE_MODULES:
        assert "weighbridge" in MODULE_REGISTRY[mid]["deps"], mid


def test_weighbridge_backfill_restores_on_textile_processing(client):
    """Existing processing tenants missing the workspace get it on boot."""
    from sqlmodel import Session
    import db as db_mod
    from models import Tenant
    from routers.modules import _get_enabled

    auth = _signup(client, "wb-tp-restore@test.com")
    me = client.get("/api/auth/me", headers=auth)
    tid = me.json()["tenant"]["id"]

    with Session(db_mod.engine) as s:
        mill = s.get(Tenant, tid)
        mill.business_model = "textile_processing"
        mill.enabled_modules = '["base", "inventory", "purchase_store", "textile_processing"]'
        s.add(mill)
        s.commit()

    blocked = client.get("/api/weighbridge/tickets", headers=auth)
    assert blocked.status_code == 403

    with Session(db_mod.engine) as s:
        db_mod._ensure_mill_weighbridge_module(s)
        mill = s.get(Tenant, tid)
        assert "weighbridge" in _get_enabled(mill)

    ok = client.get("/api/weighbridge/tickets", headers=auth)
    assert ok.status_code == 200, ok.text


def test_install_weaving_pulls_weighbridge(client):
    """Weaving mill (Optional industry pack) must show the scale desk."""
    auth = _signup(client, "wb-weave-dep@test.com")
    r = client.post("/api/modules/weaving/install", headers=auth)
    assert r.status_code == 200, r.text
    enabled = set(r.json()["enabled_modules"])
    assert "weaving" in enabled
    assert "weighbridge" in enabled
    listed = client.get("/api/modules", headers=auth).json()
    wb = next(m for m in listed if m["id"] == "weighbridge")
    assert wb["installed"] is True
    tickets = client.get("/api/weighbridge/tickets", headers=auth)
    assert tickets.status_code == 200, tickets.text


def test_weighbridge_backfill_restores_on_weaving_module(client):
    """Existing weaving tenants (no mill business_model) get the workspace."""
    from sqlmodel import Session
    import db as db_mod
    from models import Tenant
    from routers.modules import _get_enabled

    auth = _signup(client, "wb-weave-restore@test.com")
    me = client.get("/api/auth/me", headers=auth)
    tid = me.json()["tenant"]["id"]

    with Session(db_mod.engine) as s:
        mill = s.get(Tenant, tid)
        mill.business_model = "trader"
        mill.enabled_modules = '["base", "inventory", "weaving"]'
        s.add(mill)
        s.commit()

    blocked = client.get("/api/weighbridge/tickets", headers=auth)
    assert blocked.status_code == 403

    with Session(db_mod.engine) as s:
        db_mod._ensure_mill_weighbridge_module(s)
        mill = s.get(Tenant, tid)
        assert "weighbridge" in _get_enabled(mill)
        assert "weaving" in _get_enabled(mill)

    ok = client.get("/api/weighbridge/tickets", headers=auth)
    assert ok.status_code == 200, ok.text


def test_weighbridge_backfill_skips_hospital(client):
    from sqlmodel import Session
    import db as db_mod
    from models import Tenant
    from routers.modules import _get_enabled

    auth = _signup(client, "wb-hosp-skip@test.com", model="simple", company="City Clinic")
    me = client.get("/api/auth/me", headers=auth)
    tid = me.json()["tenant"]["id"]

    with Session(db_mod.engine) as s:
        hosp = s.get(Tenant, tid)
        hosp.business_model = "hospital"
        hosp.enabled_modules = '["base", "hrm", "inventory", "healthcare"]'
        s.add(hosp)
        s.commit()

    with Session(db_mod.engine) as s:
        db_mod._ensure_mill_weighbridge_module(s)
        hosp = s.get(Tenant, tid)
        assert "weighbridge" not in _get_enabled(hosp)

    r = client.get("/api/weighbridge/summary", headers=auth)
    assert r.status_code == 403


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


def test_plan_allows_weighbridge_on_pro_and_starter():
    from models import Tenant
    from services.entitlements import plan_allows

    starter = Tenant(name="s", plan="starter")
    assert plan_allows(starter, "weighbridge")
    pro = Tenant(name="p", plan="pro")
    assert plan_allows(pro, "weighbridge")
    free = Tenant(name="f", plan="free")
    assert not plan_allows(free, "weighbridge")
    ent = Tenant(name="e", plan="enterprise")
    assert plan_allows(ent, "weighbridge")


def test_weighbridge_docs_does_not_touch_posting():
    src = Path(__file__).resolve().parents[1] / "services" / "weighbridge_docs.py"
    text = src.read_text()
    assert "from services.posting" not in text
    assert "post_transaction" not in text


def test_wb_stock_forms_cover_truck_scale_docs():
    from services.weighbridge_docs import WB_STOCK_FORMS
    inbound = {k for k, v in WB_STOCK_FORMS.items() if v.direction == "inbound"}
    outbound = {k for k, v in WB_STOCK_FORMS.items() if v.direction == "outbound"}
    assert inbound == {
        "gate_inward", "grey_lot", "bill", "sp_bale_receipt", "wv_yarn_inward",
        "grn", "credit_note",
    }
    assert outbound == {
        "gate_outward", "invoice", "rejection_ogp", "tp_dispatch",
        "wv_dispatch", "sp_yarn_dispatch",
        "debit_note", "stock_transfer",
    }


def test_pickable_requires_module_and_filters_direction(client):
    auth = _signup(client, "wb-pick@test.com")
    blocked = client.get("/api/weighbridge/pickable?direction=inbound", headers=auth)
    assert blocked.status_code == 403
    _install(client, auth, "weighbridge")
    inbound = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "inbound", "vehicle_no": "IN-1",
        "gross_kg": 400, "tare_kg": 40,
    })
    outbound = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "outbound", "vehicle_no": "OUT-1",
        "gross_kg": 300, "tare_kg": 30,
    })
    draft = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "inbound", "vehicle_no": "DRAFT-1",
    })
    assert inbound.status_code == 201, inbound.text
    assert outbound.status_code == 201, outbound.text
    assert draft.json()["status"] == "draft"

    inn = client.get("/api/weighbridge/pickable?direction=inbound", headers=auth)
    assert inn.status_code == 200, inn.text
    inn_ids = {r["id"] for r in inn.json()["items"]}
    assert inbound.json()["id"] in inn_ids
    assert outbound.json()["id"] not in inn_ids
    assert draft.json()["id"] not in inn_ids
    assert "gate_inward" in inn.json()["forms"]

    out = client.get("/api/weighbridge/pickable?direction=outbound", headers=auth)
    out_ids = {r["id"] for r in out.json()["items"]}
    assert outbound.json()["id"] in out_ids
    assert inbound.json()["id"] not in out_ids


def test_gate_inward_attaches_inbound_ticket(client):
    auth = _signup(client, "wb-gi@test.com", model="manufacturing")
    ticket = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "inbound", "vehicle_no": "LEA-99",
        "lot_ref": "LOT-GI", "gross_kg": 1100, "tare_kg": 100,
    })
    assert ticket.status_code == 201, ticket.text
    tid = ticket.json()["id"]

    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    po = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-10-01", "vendor_name": "Cotton Co",
        "lines": [{"description": "Bales", "qty": 10, "rate": 5}],
    })
    assert po.status_code == 201, po.text
    client.patch(f"/api/purchase-orders/{po.json()['id']}/approve", headers=auth)
    po = client.get(f"/api/purchase-orders/{po.json()['id']}", headers=auth).json()
    line_id = po["lines"][0]["id"]

    gi = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-10-01",
        "vehicle_no": "LEA-99", "challan_no": ticket.json()["number"],
        "lines": [{"po_line_id": line_id, "qty_received": 10}],
        "wb_ticket_id": tid,
    })
    assert gi.status_code == 201, gi.text
    links = client.get(
        f"/api/weighbridge/links?doc_type=gate_inward&doc_id={gi.json()['id']}",
        headers=auth,
    )
    assert links.status_code == 200, links.text
    assert links.json()["items"][0]["id"] == tid
    fetched = client.get(f"/api/weighbridge/tickets/{tid}", headers=auth).json()
    assert fetched["gate_inward_id"] == gi.json()["id"]
    assert fetched["po_id"] == po["id"]


def test_invoice_attaches_outbound_ticket_and_stamps_gate_pass(client):
    auth = _signup(client, "wb-inv-attach@test.com")
    _install(client, auth, "weighbridge")
    cust = client.post("/api/customers", headers=auth, json={"name": "Buyer"}).json()
    ticket = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "outbound", "vehicle_no": "OUT-INV",
        "lot_ref": "LOT-SALE", "gross_kg": 250, "tare_kg": 25,
    })
    assert ticket.status_code == 201, ticket.text
    tid = ticket.json()["id"]
    number = ticket.json()["number"]

    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-10-01", "due_date": "2026-10-30",
        "gst_rate": 0,
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
        "wb_ticket_id": tid,
    })
    assert inv.status_code == 201, inv.text
    cf = inv.json().get("custom_fields") or {}
    assert cf.get("x.gate_pass_no") == number
    assert cf.get("x.lot_ref") == "LOT-SALE"
    links = client.get(
        f"/api/weighbridge/links?doc_type=invoice&doc_id={inv.json()['id']}",
        headers=auth,
    )
    assert links.json()["items"][0]["id"] == tid

    inbound = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "inbound", "vehicle_no": "WRONG-WAY",
        "gross_kg": 100, "tare_kg": 10,
    })
    bad = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-10-02", "due_date": "2026-10-30",
        "gst_rate": 0,
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
        "wb_ticket_id": inbound.json()["id"],
    })
    assert bad.status_code == 400
    assert "outbound" in bad.json()["detail"]


def test_attach_endpoint_idempotent(client):
    auth = _signup(client, "wb-attach-ep@test.com")
    _install(client, auth, "weighbridge")
    cust = client.post("/api/customers", headers=auth, json={"name": "Buyer"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-10-01", "due_date": "2026-10-30",
        "gst_rate": 0,
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    ticket = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "outbound", "vehicle_no": "EP-1",
        "gross_kg": 80, "tare_kg": 8,
    })
    tid = ticket.json()["id"]
    invoice_id = inv.json()["id"]
    first = client.post(
        f"/api/weighbridge/tickets/{tid}/attach",
        headers=auth, json={"doc_type": "invoice", "doc_id": invoice_id},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/weighbridge/tickets/{tid}/attach",
        headers=auth, json={"doc_type": "invoice", "doc_id": invoice_id},
    )
    assert second.status_code == 200, second.text
    fetched = client.get(f"/api/invoices/{invoice_id}", headers=auth).json()
    assert fetched["custom_fields"]["x.gate_pass_no"] == ticket.json()["number"]


def test_grn_and_credit_note_attach_inbound_ticket(client):
    auth = _signup(client, "wb-grn-cn@test.com", model="manufacturing")
    cust = client.post("/api/customers", headers=auth, json={"name": "Brand Co"}).json()
    prod = client.post("/api/products", headers=auth, json={
        "code": "FAB", "name": "Fabric", "unit": "kg",
        "product_type": "stock", "default_rate": 10,
    }).json()
    ticket = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "inbound", "vehicle_no": "GRN-TRK",
        "lot_ref": "LOT-G", "gross_kg": 500, "tare_kg": 50,
    })
    assert ticket.status_code == 201, ticket.text
    tid = ticket.json()["id"]

    grn = client.post("/api/grn", headers=auth, json={
        "customer_id": cust["id"], "received_date": "2026-10-01",
        "lines": [{"product_id": prod["id"], "qty": 100, "lot_no": "LOT-G"}],
        "wb_ticket_id": tid,
    })
    assert grn.status_code == 201, grn.text
    links = client.get(
        f"/api/weighbridge/links?doc_type=grn&doc_id={grn.json()['id']}",
        headers=auth,
    )
    assert links.json()["items"][0]["id"] == tid

    cn = client.post("/api/credit-notes", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-10-02",
        "lines": [{"description": "Return", "qty": 1, "rate": 5}],
        "wb_ticket_id": tid,
    })
    assert cn.status_code == 201, cn.text
    cn_links = client.get(
        f"/api/weighbridge/links?doc_type=credit_note&doc_id={cn.json()['id']}",
        headers=auth,
    )
    assert cn_links.json()["items"][0]["id"] == tid


def test_debit_note_and_transfer_attach_outbound_ticket(client):
    auth = _signup(client, "wb-dn-st@test.com", model="trader")
    _install(client, auth, "weighbridge", "inventory")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Cotton Co"}).json()
    bill = client.post("/api/bills", headers=auth, json={
        "vendor_id": vendor["id"], "bill_date": "2026-10-01", "due_date": "2026-10-30",
        "gst_rate": 0,
        "lines": [{"description": "Yarn", "qty": 1, "rate": 20}],
    })
    assert bill.status_code == 201, bill.text
    ticket = client.post("/api/weighbridge/tickets", headers=auth, json={
        "direction": "outbound", "vehicle_no": "DN-TRK",
        "gross_kg": 200, "tare_kg": 20,
    })
    assert ticket.status_code == 201, ticket.text
    tid = ticket.json()["id"]

    dn = client.post("/api/debit-notes", headers=auth, json={
        "bill_id": bill.json()["id"], "vendor_id": vendor["id"],
        "issue_date": "2026-10-02",
        "lines": [{"description": "Return", "qty": 1, "rate": 20}],
        "wb_ticket_id": tid,
    })
    assert dn.status_code == 201, dn.text
    dn_links = client.get(
        f"/api/weighbridge/links?doc_type=debit_note&doc_id={dn.json()['id']}",
        headers=auth,
    )
    assert dn_links.json()["items"][0]["id"] == tid

    locs = client.get("/api/stock-locations?type=own", headers=auth).json()["items"]
    by_code = {l["code"]: l for l in locs}
    if "WH2" not in by_code:
        w = client.post("/api/stock-locations", headers=auth, json={
            "code": "WH2", "name": "Warehouse 2", "type": "own",
        })
        assert w.status_code == 201, w.text
        by_code["WH2"] = w.json()
    main_id = by_code["MAIN"]["id"]
    wh2_id = by_code["WH2"]["id"]
    prod = client.post("/api/products", headers=auth, json={
        "name": "Bolt", "product_type": "stock", "default_rate": 5,
        "opening_qty": 10, "opening_cost": 2,
    })
    assert prod.status_code in (200, 201), prod.text
    st = client.post("/api/stock-transfers", headers=auth, json={
        "transfer_date": "2026-10-03",
        "from_location_id": main_id,
        "to_location_id": wh2_id,
        "lines": [{"product_id": prod.json()["id"], "qty": 2}],
        "wb_ticket_id": tid,
    })
    assert st.status_code == 201, st.text
    st_links = client.get(
        f"/api/weighbridge/links?doc_type=stock_transfer&doc_id={st.json()['id']}",
        headers=auth,
    )
    assert st_links.json()["items"][0]["id"] == tid
