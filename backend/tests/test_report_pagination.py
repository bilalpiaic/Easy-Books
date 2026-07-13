"""#137 carry-in: SQL-side pagination + search on the Purchases/Store
registers. All five list-style reports (gate-register, three-way-match,
gate-outward-register, dispatch-reconciliation, issue-register) move from
bare arrays with Python-side substring filtering to `{total, items}` with
skip/limit and ilike search pushed into the query.
"""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> dict:
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co",
        "business_model": "manufacturing",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _approved_po(client, auth, vendor="Steel Traders", qty=10):
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-05", "vendor_name": vendor,
        "lines": [{"description": f"{vendor} item", "qty": qty, "rate": 5}],
    })
    po = r.json()
    client.patch(f"/api/purchase-orders/{po['id']}/approve", headers=auth)
    return client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()


def _gi(client, auth, po, vehicle, qty=1):
    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05", "vehicle_no": vehicle,
        "lines": [{"po_line_id": po["lines"][0]["id"], "qty_received": qty}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _posted_invoice(client, auth, date="2026-07-06"):
    p = client.post("/api/products", headers=auth,
                    json={"name": f"W-{date}", "product_type": "stock"}).json()
    r = client.post("/api/invoices", headers=auth, json={
        "issue_date": date, "due_date": "2026-08-06",
        "customer_name": "Walk-in Customer",
        "lines": [{"description": "Widget", "qty": 1, "rate": 20, "product_id": p["id"]}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_gate_register_paginates_and_searches_sql_side(client: TestClient):
    auth = _signup(client, "pag1@t.com")
    po = _approved_po(client, auth, qty=10)
    for i, vehicle in enumerate(["LEB-1111", "LEB-2222", "KHI-3333"]):
        _gi(client, auth, po, vehicle)

    r = client.get("/api/purchase-reports/gate-register?limit=2", headers=auth).json()
    assert r["total"] == 3
    assert len(r["items"]) == 2

    r2 = client.get("/api/purchase-reports/gate-register?limit=2&skip=2", headers=auth).json()
    assert r2["total"] == 3
    assert len(r2["items"]) == 1
    assert {i["id"] for i in r["items"]}.isdisjoint({i["id"] for i in r2["items"]})

    # search is case-insensitive and SQL-side (total reflects the filter)
    r = client.get("/api/purchase-reports/gate-register?q=leb", headers=auth).json()
    assert r["total"] == 2
    r = client.get("/api/purchase-reports/gate-register?q=NOPE", headers=auth).json()
    assert r["total"] == 0 and r["items"] == []


def test_three_way_match_paginates_by_po_and_searches(client: TestClient):
    auth = _signup(client, "pag2@t.com")
    po_a = _approved_po(client, auth, vendor="Alpha Mills", qty=5)
    po_b = _approved_po(client, auth, vendor="Beta Steel", qty=5)
    _approved_po(client, auth, vendor="NoActivity Co", qty=5)  # no GI/bill → excluded
    _gi(client, auth, po_a, "V-1", qty=5)
    _gi(client, auth, po_b, "V-2", qty=3)

    r = client.get("/api/purchase-reports/three-way-match", headers=auth).json()
    assert r["total"] == 2  # POs with match activity
    assert {i["po_number"] for i in r["items"]} == {po_a["number"], po_b["number"]}

    r = client.get("/api/purchase-reports/three-way-match?limit=1", headers=auth).json()
    assert r["total"] == 2
    assert len({i["po_number"] for i in r["items"]}) == 1

    r = client.get("/api/purchase-reports/three-way-match?q=beta", headers=auth).json()
    assert r["total"] == 1
    assert r["items"][0]["vendor_name"] == "Beta Steel"


def test_gate_outward_register_paginates_and_searches(client: TestClient):
    auth = _signup(client, "pag3@t.com")
    inv = _posted_invoice(client, auth)
    for vehicle in ["LEB-7777", "LEB-8888", "KHI-9999"]:
        r = client.post("/api/gate-outwards", headers=auth, json={
            "source_doc_type": "invoice", "source_doc_id": inv["id"],
            "gate_date": "2026-07-06", "vehicle_no": vehicle,
            "lines": [{"product_id": inv["lines"][0]["product_id"], "qty": 1}],
        })
        assert r.status_code == 201, r.text

    r = client.get("/api/store-reports/gate-outward-register?limit=2", headers=auth).json()
    assert r["total"] == 3 and len(r["items"]) == 2
    r = client.get("/api/store-reports/gate-outward-register?q=leb", headers=auth).json()
    assert r["total"] == 2


def test_dispatch_reconciliation_paginates_union_and_searches(client: TestClient):
    auth = _signup(client, "pag4@t.com")
    inv1 = _posted_invoice(client, auth, date="2026-07-01")
    inv2 = _posted_invoice(client, auth, date="2026-07-02")
    inv3 = _posted_invoice(client, auth, date="2026-07-03")
    client.post("/api/gate-outwards", headers=auth, json={
        "source_doc_type": "invoice", "source_doc_id": inv3["id"],
        "gate_date": "2026-07-06",
        "lines": [{"product_id": inv3["lines"][0]["product_id"], "qty": 1}],
    })

    r = client.get("/api/store-reports/dispatch-reconciliation", headers=auth).json()
    assert r["total"] == 3
    by_number = {i["doc_number"]: i for i in r["items"]}
    assert by_number[inv3["number"]]["has_gate_exit"] is True
    assert by_number[inv1["number"]]["has_gate_exit"] is False

    # newest-first ordering + pagination across the union
    r = client.get("/api/store-reports/dispatch-reconciliation?limit=2", headers=auth).json()
    assert r["total"] == 3 and len(r["items"]) == 2
    assert r["items"][0]["doc_date"] >= r["items"][1]["doc_date"]

    # search by doc number
    r = client.get(
        f"/api/store-reports/dispatch-reconciliation?q={inv2['number']}", headers=auth
    ).json()
    assert r["total"] == 1 and r["items"][0]["doc_number"] == inv2["number"]


def test_issue_register_paginates_and_searches(client: TestClient):
    auth = _signup(client, "pag5@t.com")
    p = client.post("/api/products", headers=auth,
                    json={"name": "Grease", "product_type": "stock", "opening_qty": 50}).json()
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    exp = next(a for a in accounts if a["type"] == "Expense" and not a.get("is_group"))
    loc_id = client.get("/api/stock-locations", headers=auth).json()["items"][0]["id"]
    for note in ["maintenance bay 1", "maintenance bay 2", "office"]:
        r = client.post("/api/store-issues", headers=auth, json={
            "issue_date": "2026-07-07", "from_location_id": loc_id,
            "debit_account_id": exp["id"], "notes": note,
            "lines": [{"product_id": p["id"], "qty": 1}],
        })
        assert r.status_code == 201, r.text

    r = client.get("/api/store-reports/issue-register?limit=2", headers=auth).json()
    assert r["total"] == 3 and len(r["items"]) == 2
    r = client.get("/api/store-reports/issue-register?q=maintenance", headers=auth).json()
    assert r["total"] == 2
