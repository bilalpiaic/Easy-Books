"""Tests for Textile Processing (ballor) module."""
from decimal import Decimal

from services.textile_processing import (
    ready_mtr, rej_note_balance, rej_note_status, settlement_credit, stage_balance_ok,
)


def _signup(client, email, company="Process Co"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Processor", "company_name": company, "business_model": "trader",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install(client, auth, *modules):
    for m in modules:
        r = client.post(f"/api/modules/{m}/install", headers=auth)
        assert r.status_code in (200, 201), f"{m}: {r.text}"


def test_mending_maths():
    assert ready_mtr(1000, 10, 15, 75) == Decimal("900.0000")
    assert stage_balance_ok(100, 97, 2, 1)
    assert not stage_balance_ok(100, 90, 2, 1)
    cq, cv = settlement_credit(1000, 850, 20, 10, 120)
    assert cq == Decimal("120.0000")
    assert cv == Decimal("14400.0000")
    assert rej_note_balance(15, 10) == Decimal("5.0000")
    assert rej_note_status(15, 0) == "issued"
    assert rej_note_status(15, 10) == "partially_lifted"
    assert rej_note_status(15, 15) == "lifted"


def test_module_gate(client):
    auth = _signup(client, "tp-gate@test.com")
    r = client.get("/api/textile-processing/lots", headers=auth)
    assert r.status_code == 403


def test_phase1_flow(client):
    auth = _signup(client, "tp-p1@test.com")
    _install(client, auth, "inventory", "purchase_store", "textile_processing")

    cust = client.post("/api/customers", headers=auth, json={"name": "Grey Owner"}).json()
    q = client.post("/api/textile-processing/qualities", headers=auth, json={
        "code": "PC60", "name": "Poplin", "blend": "100% Cotton", "width": "60\"",
    }).json()
    assert q["code"] == "PC60"

    procs = client.get("/api/textile-processing/processes", headers=auth).json()
    assert len(procs) >= 10

    so = client.post("/api/textile-processing/sales-orders", headers=auth, json={
        "customer_id": cust["id"], "quality_id": q["id"], "date": "2026-07-01",
        "expected_mtr": 1000, "grey_rate": 120,
        "process_rates": [
            {"process_id": p["id"], "rate": 2.5, "enabled": True}
            for p in procs if p["is_billing"]
        ][:3],
    }).json()
    assert so["number"].startswith("SO-")

    lot = client.post("/api/textile-processing/lots", headers=auth, json={
        "sales_order_id": so["id"], "date": "2026-07-02",
        "thans": [{"than_no": str(i), "meters": 100} for i in range(1, 11)],
    }).json()
    assert lot["received_mtr"] == 1000.0
    assert lot["kachi_parchi"]["meters"] == 1000.0

    # PO blocked without Pakki
    bad_po = client.post("/api/textile-processing/production-orders", headers=auth, json={
        "lot_id": lot["id"], "date": "2026-07-03",
    })
    assert bad_po.status_code == 400

    mend = client.post("/api/textile-processing/mendings", headers=auth, json={
        "lot_id": lot["id"], "date": "2026-07-03",
        "l_kami_mtr": 10, "rejection_mtr": 15, "safai_mtr": 75,
    }).json()
    assert mend["ready_mtr"] == 900.0
    assert mend["status"] == "draft"

    posted = client.patch(f"/api/textile-processing/mendings/{mend['id']}/post", headers=auth).json()
    assert posted["status"] == "posted"
    assert posted["pakki_parchi"]["meters"] == 900.0
    assert posted["rejection_note"]["issued_mtr"] == 15.0

    # OGP caps
    note_id = posted["rejection_note"]["id"]
    over = client.post("/api/textile-processing/rejection-ogps", headers=auth, json={
        "rejection_issue_note_id": note_id, "date": "2026-07-04", "qty_mtr": 20,
    })
    assert over.status_code == 400

    ogp = client.post("/api/textile-processing/rejection-ogps", headers=auth, json={
        "rejection_issue_note_id": note_id, "date": "2026-07-04",
        "qty_mtr": 10, "vehicle": "ABC-1",
    }).json()
    assert ogp["qty_mtr"] == 10.0

    note = client.get(f"/api/textile-processing/rejection-notes/{note_id}", headers=auth).json()
    assert note["status"] == "partially_lifted"
    assert note["balance_mtr"] == 5.0

    # Cancel blocked with OGP
    cancel = client.patch(f"/api/textile-processing/rejection-notes/{note_id}/cancel", headers=auth)
    assert cancel.status_code == 400

    # Production Order after Pakki
    po = client.post("/api/textile-processing/production-orders", headers=auth, json={
        "lot_id": lot["id"], "date": "2026-07-05",
    }).json()
    assert po["issued_mtr"] == 900.0

    # Stage with wastage
    prep = next(p for p in procs if p["code"] == "prep")
    stage = client.post("/api/textile-processing/stages", headers=auth, json={
        "production_order_id": po["id"], "process_id": prep["id"], "date": "2026-07-06",
        "input_mtr": 900, "output_mtr": 890, "visible_wastage_mtr": 7, "invisible_wastage_mtr": 3,
        "labor_qty": 890, "labor_rate": 0.5,
    }).json()
    assert stage["loss_mtr"] == 10.0

    # Bad balance rejected
    salai = next(p for p in procs if p["code"] == "salai")
    bad = client.post("/api/textile-processing/stages", headers=auth, json={
        "production_order_id": po["id"], "process_id": salai["id"], "date": "2026-07-07",
        "input_mtr": 890, "output_mtr": 800, "visible_wastage_mtr": 1, "invisible_wastage_mtr": 1,
    })
    assert bad.status_code == 400

    reg = client.get("/api/textile-processing/reports/customer-rejection-register", headers=auth).json()
    assert reg["total"] >= 1

    ledger = client.get("/api/textile-processing/reports/customer-stock-ledger", headers=auth).json()
    assert ledger["total"] >= 1

    dash = client.get("/api/textile-processing/dashboard", headers=auth).json()
    assert "kpis" in dash


def test_dispatch_settlement(client):
    auth = _signup(client, "tp-bill@test.com")
    _install(client, auth, "inventory", "purchase_store", "textile_processing")

    cust = client.post("/api/customers", headers=auth, json={"name": "Buyer"}).json()
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Labor Gang"}).json()
    q = client.post("/api/textile-processing/qualities", headers=auth, json={
        "code": "Q1", "name": "Lawn",
    }).json()
    procs = client.get("/api/textile-processing/processes", headers=auth).json()
    prep = next(p for p in procs if p["code"] == "prep")

    ctr = client.post("/api/textile-processing/contractors", headers=auth, json={
        "code": "C1", "name": "Gang", "vendor_id": vendor["id"], "default_process_id": prep["id"],
    }).json()

    so = client.post("/api/textile-processing/sales-orders", headers=auth, json={
        "customer_id": cust["id"], "quality_id": q["id"], "date": "2026-07-01",
        "expected_mtr": 100, "grey_rate": 100,
        "process_rates": [{"process_id": prep["id"], "rate": 5, "enabled": True}],
    }).json()
    lot = client.post("/api/textile-processing/lots", headers=auth, json={
        "sales_order_id": so["id"], "date": "2026-07-02",
        "thans": [{"than_no": "1", "meters": 100}],
    }).json()
    mend = client.post("/api/textile-processing/mendings", headers=auth, json={
        "lot_id": lot["id"], "date": "2026-07-03",
        "l_kami_mtr": 0, "rejection_mtr": 0, "safai_mtr": 0,
    }).json()
    client.patch(f"/api/textile-processing/mendings/{mend['id']}/post", headers=auth)
    po = client.post("/api/textile-processing/production-orders", headers=auth, json={
        "lot_id": lot["id"], "date": "2026-07-04",
    }).json()
    stage = client.post("/api/textile-processing/stages", headers=auth, json={
        "production_order_id": po["id"], "process_id": prep["id"], "date": "2026-07-05",
        "input_mtr": 100, "output_mtr": 95, "visible_wastage_mtr": 3, "invisible_wastage_mtr": 2,
        "contractor_id": ctr["id"], "labor_qty": 95, "labor_rate": 1,
    }).json()

    labor = client.post("/api/textile-processing/labor-bills", headers=auth, json={
        "contractor_id": ctr["id"], "date": "2026-07-06",
        "stage_entry_ids": [stage["id"]],
    }).json()
    assert labor["bill_id"]
    assert labor["labor_amount"] == 95.0

    disp = client.post("/api/textile-processing/dispatches", headers=auth, json={
        "production_order_id": po["id"], "date": "2026-07-07", "meters": 90,
    }).json()
    assert disp["invoice_id"]
    assert disp["meters"] == 90.0

    # Over-dispatch blocked
    over = client.post("/api/textile-processing/dispatches", headers=auth, json={
        "production_order_id": po["id"], "date": "2026-07-08", "meters": 50,
    })
    assert over.status_code == 400

    sett = client.post("/api/textile-processing/settlements", headers=auth, json={
        "lot_id": lot["id"], "date": "2026-07-09",
        "recognize_visible_wastage": True, "visible_wastage_rate": 50,
    }).json()
    # credit = 100 - 90 - (3+2) = 5; value = 5 * 100 = 500
    assert sett["credit_qty_mtr"] == 5.0
    assert sett["credit_value"] == 500.0
    assert sett["credit_note_id"]
    assert sett["wastage_invoice_id"]

    ppc = client.get("/api/textile-processing/reports/ppc-stage?group_by=stage", headers=auth).json()
    assert ppc["total"] >= 1
