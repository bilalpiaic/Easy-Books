"""Tests for Textile Processing (ballor) module."""
from decimal import Decimal

from services.textile_processing import (
    format_quality_code, ready_mtr, rej_note_balance, rej_note_status,
    settlement_credit, stage_balance_ok, than_safi_mtr,
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


def test_quality_code_structure():
    assert format_quality_code("ctn", 60, 60, 40, 52, 45) == 'CTN 60X60 40X52 45"'
    assert format_quality_code("PC", "60", "60", "40", "52", '45"') == 'PC 60X60 40X52 45"'
    assert format_quality_code("CTN", None, 60, 40, 52, 45) is None
    assert than_safi_mtr(100, 5) == Decimal("95.0000")
    assert than_safi_mtr(100, 10, 5, 2) == Decimal("83.0000")
    try:
        than_safi_mtr(100, 50, 40, 20)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_grey_inward_form_fields(client):
    """GREY IN voucher: G.Kami / CP / L.Kami / rejection return / summary bands."""
    auth = _signup(client, "tp-grey-in@test.com")
    _install(client, auth, "inventory", "purchase_store", "textile_processing")

    cust = client.post("/api/customers", headers=auth, json={"name": "S.N FABRICS"}).json()
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Mending Gang"}).json()
    q = client.post("/api/textile-processing/qualities", headers=auth, json={
        "fiber": "CTN", "warp_count": "66", "weft_count": "66",
        "epi": "35", "ppi": "35", "width_inch": "45",
    }).json()
    procs = client.get("/api/textile-processing/processes", headers=auth).json()
    prep = next(p for p in procs if p["code"] == "prep")
    ctr = client.post("/api/textile-processing/contractors", headers=auth, json={
        "code": "CAMIR", "name": "SHEIKH AMIR", "vendor_id": vendor["id"],
        "default_process_id": prep["id"],
    }).json()
    so = client.post("/api/textile-processing/sales-orders", headers=auth, json={
        "customer_id": cust["id"], "quality_id": q["id"], "date": "2026-08-05",
        "expected_mtr": 200, "grey_rate": 111,
    }).json()

    lot = client.post("/api/textile-processing/lots", headers=auth, json={
        "sales_order_id": so["id"],
        "date": "2026-08-05",
        "mending_date": "2026-08-06",
        "contractor_id": ctr["id"],
        "category": "CHOTA ARZ",
        "process_name": "PRINT",
        "rate": 111,
        "lot_no": "1328",
        "lot_remarks": "STAPLE 66x66",
        "l_kami_mtr": 0,
        "manual_rejection_mtr": 40,
        "rej_driver_name": "Ali",
        "rej_mobile": "03016047225",
        "rej_vehicle": "LES-900",
        "notes": "INCHARGE OK",
        "thans": [
            {"than_no": "1", "meters": 100, "g_kami_mtr": 0, "rejection_mtr": 0, "cp_mtr": 0},
            {"than_no": "2", "meters": 50, "g_kami_mtr": 0, "rejection_mtr": 0, "cp_mtr": 5},
            {"than_no": "3", "meters": 50, "g_kami_mtr": 2, "rejection_mtr": 48, "cp_mtr": 0},
        ],
    }).json()

    assert lot["lot_no"] == "1328"
    assert lot["category"] == "CHOTA ARZ"
    assert lot["process_name"] == "PRINT"
    assert lot["contractor_id"] == ctr["id"]
    assert lot["party_name"] == "S.N FABRICS"
    assert lot["contractor_name"] == "SHEIKH AMIR"
    assert lot["quality_code"] == q["code"]
    assert lot["rej_driver_name"] == "Ali"
    assert lot["manual_rejection_mtr"] == 40.0

    thans = {t["than_no"]: t for t in lot["thans"]}
    assert thans["1"]["safi_mtr"] == 100.0
    assert thans["2"]["safi_mtr"] == 45.0   # 50 - 5 CP
    assert thans["3"]["safi_mtr"] == 0.0    # 50 - 2 G.Kami - 48 reject

    sm = lot["summary"]
    assert sm["g_total"]["detail_mtrs"] == 200.0
    assert sm["total_cp"]["detail_mtrs"] == 5.0
    assert sm["total_cp"]["than"] == 1
    assert sm["total_rejection"]["detail_mtrs"] == 48.0
    assert sm["total_rejection"]["manual_mtrs"] == 40.0
    assert sm["total_rejection"]["variance"] == -8.0
    assert sm["total_safi"]["detail_mtrs"] == 145.0
    assert lot["ready_mtr"] == 145.0

    detail = client.get(f"/api/textile-processing/lots/{lot['id']}", headers=auth).json()
    assert detail["summary"]["total_g_kami"]["detail_mtrs"] == 2.0
    assert detail["l_kami_mtr"] == 0.0


def test_strengthen_multi_quality_so_and_printouts(client):
    auth = _signup(client, "tp-strengthen@test.com")
    _install(client, auth, "inventory", "purchase_store", "textile_processing")

    cust = client.post("/api/customers", headers=auth, json={"name": "Multi Grey Co"}).json()
    q1 = client.post("/api/textile-processing/qualities", headers=auth, json={
        "fiber": "CTN", "warp_count": "60", "weft_count": "60",
        "epi": "40", "ppi": "52", "width_inch": "45",
    }).json()
    assert q1["code"] == 'CTN 60X60 40X52 45"'
    q2 = client.post("/api/textile-processing/qualities", headers=auth, json={
        "fiber": "PC", "warp_count": "40", "weft_count": "40",
        "epi": "90", "ppi": "88", "width_inch": "58", "name": "PC Lawn",
    }).json()

    procs = client.get("/api/textile-processing/processes", headers=auth).json()
    assert any(p["code"] == "dyeing" for p in procs)
    dyeing = next(p for p in procs if p["code"] == "dyeing")
    printing = next(p for p in procs if p["code"] == "printing")

    # Process ADD / UPDATE / DELETE
    created = client.post("/api/textile-processing/processes", headers=auth, json={
        "seq": 175, "code": "extra-fold", "name": "Extra Fold", "is_billing": False,
    }).json()
    upd = client.put(f"/api/textile-processing/processes/{created['id']}", headers=auth, json={
        "seq": 176, "code": "extra-fold", "name": "Extra Folding", "is_billing": False,
        "default_sale_rate": 0, "is_active": True,
    }).json()
    assert upd["name"] == "Extra Folding"
    deleted = client.delete(f"/api/textile-processing/processes/{created['id']}", headers=auth).json()
    assert deleted["ok"] is True

    vendor = client.post("/api/vendors", headers=auth, json={"name": "Dye Gang"}).json()
    ctr = client.post("/api/textile-processing/contractors", headers=auth, json={
        "code": "DYE1", "name": "Dyers", "vendor_id": vendor["id"],
        "default_process_id": dyeing["id"],
    }).json()
    assert ctr["default_process_id"] == dyeing["id"]
    ctr2 = client.put(f"/api/textile-processing/contractors/{ctr['id']}", headers=auth, json={
        "code": "DYE1", "name": "Dyers Ltd", "vendor_id": vendor["id"],
        "default_process_id": printing["id"], "is_active": True,
    }).json()
    assert ctr2["name"] == "Dyers Ltd"
    assert ctr2["default_process_id"] == printing["id"]

    so = client.post("/api/textile-processing/sales-orders", headers=auth, json={
        "customer_id": cust["id"], "date": "2026-08-01",
        "quality_lines": [
            {"quality_id": q1["id"], "expected_mtr": 500, "grey_rate": 120},
            {"quality_id": q2["id"], "expected_mtr": 300, "grey_rate": 140},
        ],
        "packing_lines": [
            {"item_type": "KMZ", "quality_id": q1["id"], "process_id": printing["id"],
             "qty": 10, "meters": 400, "rate": 5},
            {"item_type": "2PC", "quality_id": q2["id"], "process_id": dyeing["id"],
             "qty": 20, "meters": 250, "rate": 6},
            {"item_type": "SHL", "quality_id": q1["id"], "process_id": printing["id"],
             "qty": 5, "meters": 50, "rate": 4},
        ],
    }).json()
    assert len(so["quality_lines"]) == 2
    assert len(so["packing_lines"]) == 3
    assert so["quality_id"] == q1["id"]
    assert so["expected_mtr"] == 800.0

    lot = client.post("/api/textile-processing/lots", headers=auth, json={
        "sales_order_id": so["id"], "quality_id": q2["id"], "date": "2026-08-02",
        "thans": [
            {"than_no": "1", "meters": 100, "rejection_mtr": 2},
            {"than_no": "2", "meters": 80, "rejection_mtr": 0},
        ],
    }).json()
    assert lot["quality_id"] == q2["id"]
    assert lot["received_mtr"] == 180.0
    assert lot["rejection_mtr"] == 2.0
    assert lot["thans"][0]["safi_mtr"] == 98.0
    assert "kachi_parchi" in lot

    kp = client.get(
        f"/api/textile-processing/kachi-parchis/{lot['kachi_parchi']['id']}", headers=auth,
    ).json()
    assert kp["customer_name"] == "Multi Grey Co"
    assert kp["quality_code"] == q2["code"]
    assert len(kp["thans"]) == 2

    mend = client.post("/api/textile-processing/mendings", headers=auth, json={
        "lot_id": lot["id"], "date": "2026-08-03",
        "l_kami_mtr": 0, "rejection_mtr": 5, "safai_mtr": 5,
    }).json()
    posted = client.patch(
        f"/api/textile-processing/mendings/{mend['id']}/post", headers=auth,
    ).json()
    pakki = client.get(
        f"/api/textile-processing/pakki-parchis/{posted['pakki_parchi']['id']}", headers=auth,
    ).json()
    assert pakki["customer_name"] == "Multi Grey Co"
    assert "mending" in pakki

    ogp = client.post("/api/textile-processing/rejection-ogps", headers=auth, json={
        "rejection_issue_note_id": posted["rejection_note"]["id"],
        "date": "2026-08-04", "qty_mtr": 5, "vehicle": "LES-1",
    }).json()
    ogp_d = client.get(f"/api/textile-processing/rejection-ogps/{ogp['id']}", headers=auth).json()
    assert ogp_d["customer_name"] == "Multi Grey Co"
    assert ogp_d["qty_mtr"] == 5.0
