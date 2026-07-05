"""#137 Phase 2 — Gate Inward chain: GI → billing gate → reports."""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str, model: str = "manufacturing") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": model,
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_gate_models_and_permission_registered(client: TestClient):
    from models import GateInward, GateInwardLine  # importable = tables exist
    from services.permissions import PERMISSION_RESOURCES
    assert "purchase.gate" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["purchase.gate"]["category"] == "Purchasing"


def test_gi_coverage_pure_math(client: TestClient):
    """Coverage helper sums non-cancelled GI lines per PO line."""
    from decimal import Decimal
    from sqlmodel import Session
    from models import (GateInward, GateInwardLine, PurchaseOrder,
                        PurchaseOrderLine, Tenant, User)
    from services.gate import gi_coverage, po_fully_covered
    import db as _db
    with Session(_db.engine) as s:
        t = Tenant(name="CovCo"); s.add(t); s.commit(); s.refresh(t)
        u = User(email="cov@t.test", hashed_password="x", full_name="U",
                 tenant_id=t.id, role="owner")
        s.add(u); s.commit(); s.refresh(u)
        po = PurchaseOrder(tenant_id=t.id, number="PO-X", order_date="2026-07-05",
                           status="approved")
        s.add(po); s.commit(); s.refresh(po)
        l1 = PurchaseOrderLine(po_id=po.id, description="A", qty=Decimal("10"), rate=Decimal("2"), amount=Decimal("20"))
        l2 = PurchaseOrderLine(po_id=po.id, description="B", qty=Decimal("5"), rate=Decimal("3"), amount=Decimal("15"))
        s.add(l1); s.add(l2); s.commit(); s.refresh(l1); s.refresh(l2)

        gi1 = GateInward(tenant_id=t.id, number="GI-1", po_id=po.id,
                         gate_date="2026-07-05", created_by_id=u.id)
        s.add(gi1); s.commit(); s.refresh(gi1)
        s.add(GateInwardLine(gate_inward_id=gi1.id, po_line_id=l1.id, qty_received=Decimal("4")))
        gi2 = GateInward(tenant_id=t.id, number="GI-2", po_id=po.id,
                         gate_date="2026-07-05", created_by_id=u.id, status="cancelled")
        s.add(gi2); s.commit(); s.refresh(gi2)
        s.add(GateInwardLine(gate_inward_id=gi2.id, po_line_id=l1.id, qty_received=Decimal("99")))
        s.commit()

        cov = gi_coverage(s, t.id, po.id)
        assert cov == {l1.id: Decimal("4")}          # cancelled GI excluded
        assert po_fully_covered(s, t.id, po.id) is False

        gi3 = GateInward(tenant_id=t.id, number="GI-3", po_id=po.id,
                         gate_date="2026-07-05", created_by_id=u.id)
        s.add(gi3); s.commit(); s.refresh(gi3)
        s.add(GateInwardLine(gate_inward_id=gi3.id, po_line_id=l1.id, qty_received=Decimal("6")))
        s.add(GateInwardLine(gate_inward_id=gi3.id, po_line_id=l2.id, qty_received=Decimal("5")))
        s.commit()
        assert po_fully_covered(s, t.id, po.id) is True


def _approved_po(client, auth, lines=None):
    """Bare PO (chain setting off) + approve it. Returns the PO dict with lines."""
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-05", "vendor_name": "Steel Traders",
        "lines": lines or [
            {"description": "Steel rods 12mm", "qty": 100, "rate": 5},
            {"description": "Binding wire", "qty": 20, "rate": 2},
        ],
    })
    assert r.status_code == 201, r.text
    po = r.json()
    client.patch(f"/api/purchase-orders/{po['id']}/approve", headers=auth)
    return client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()


def _po_line_ids(po):
    return [l["id"] for l in po["lines"]]


def test_gi_lifecycle_partial_then_full(client: TestClient):
    auth = _signup(client, "gi1@t.com")
    po = _approved_po(client, auth)
    l1, l2 = _po_line_ids(po)

    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05", "time_in": "09:30",
        "vehicle_no": "LEB-1234", "challan_no": "CH-778",
        "lines": [{"po_line_id": l1, "qty_received": 100}],
    })
    assert r.status_code == 201, r.text
    gi = r.json()
    assert gi["number"].startswith("GI-")
    assert gi["status"] == "open"

    # partial coverage → PO still 'approved'
    po_now = client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()
    assert po_now["status"] == "approved"

    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l2, "qty_received": 20}],
    })
    assert r.status_code == 201, r.text

    # full coverage → PO flips to 'received'
    po_now = client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()
    assert po_now["status"] == "received"


def test_gi_over_receipt_rejected(client: TestClient):
    auth = _signup(client, "gi2@t.com")
    po = _approved_po(client, auth)
    l1, _ = _po_line_ids(po)
    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 101}],
    })
    assert r.status_code == 400
    assert "exceed" in r.json()["detail"].lower()


def test_gi_rejects_draft_and_foreign_po(client: TestClient):
    auth = _signup(client, "gi3@t.com")
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    r = client.post("/api/purchase-orders", headers=auth, json={
        "order_date": "2026-07-05", "vendor_name": "V",
        "lines": [{"description": "W", "qty": 1, "rate": 1}],
    })
    draft_po = r.json()
    # POST /api/purchase-orders doesn't echo `lines`; fetch via GET like _approved_po does.
    draft_po_full = client.get(f"/api/purchase-orders/{draft_po['id']}", headers=auth).json()
    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": draft_po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": draft_po_full["lines"][0]["id"], "qty_received": 1}],
    })
    assert r.status_code == 400  # draft PO not receivable

    # foreign tenant's PO → 404
    auth_b = _signup(client, "gi3b@t.com")
    po_a = _approved_po(client, auth)
    r = client.post("/api/gate-inwards", headers=auth_b, json={
        "po_id": po_a["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": _po_line_ids(po_a)[0], "qty_received": 1}],
    })
    assert r.status_code == 404


def test_gi_cancel_requires_reason_and_restores_headroom(client: TestClient):
    auth = _signup(client, "gi4@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    l1 = _po_line_ids(po)[0]
    gi = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 10}],
    }).json()
    assert client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()["status"] == "received"

    r = client.patch(f"/api/gate-inwards/{gi['id']}/cancel", headers=auth, json={})
    assert r.status_code == 422 or r.status_code == 400  # reason required

    r = client.patch(f"/api/gate-inwards/{gi['id']}/cancel", headers=auth,
                     json={"reason": "wrong vehicle logged"})
    assert r.status_code == 200
    # coverage dropped → PO back to 'approved'; headroom restored
    assert client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()["status"] == "approved"
    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 10}],
    })
    assert r.status_code == 201, r.text


def test_gi_create_requires_write_role(client: TestClient):
    auth = _signup(client, "gi5@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 1, "rate": 1}])
    client.post("/api/users", headers=auth, json={
        "email": "gateviewer@t.com", "password": "password123",
        "full_name": "Viewer", "role": "viewer",
    })
    r = client.post("/api/auth/login",
                    data={"username": "gateviewer@t.com", "password": "password123"})
    viewer = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/api/gate-inwards", headers=viewer, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": _po_line_ids(po)[0], "qty_received": 1}],
    })
    assert r.status_code == 403


def test_gi_duplicate_line_entries_cannot_bypass_cap(client: TestClient):
    auth = _signup(client, "gi6@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 100, "rate": 1}])
    l1 = _po_line_ids(po)[0]
    r = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [
            {"po_line_id": l1, "qty_received": 60},
            {"po_line_id": l1, "qty_received": 60},
        ],
    })
    assert r.status_code == 400
    assert "exceed" in r.json()["detail"].lower()


def test_billing_blocked_without_full_gi_coverage(client: TestClient):
    auth = _signup(client, "gate1@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    l1 = _po_line_ids(po)[0]

    # no GI at all → blocked (manufacturing tenant, setting defaults on)
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 400
    assert "gate inward" in r.json()["detail"].lower()

    # partial GI → still blocked
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 4}],
    })
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 400

    # full GI → allowed; GIs flip to billed
    gi2 = client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 6}],
    }).json()
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 201, r.text
    gi_now = client.get(f"/api/gate-inwards/{gi2['id']}", headers=auth).json()
    assert gi_now["status"] == "billed"

    # billed PO → GI cancel refused
    r = client.patch(f"/api/gate-inwards/{gi2['id']}/cancel", headers=auth,
                     json={"reason": "attempted tamper"})
    assert r.status_code == 400


def test_billing_allowed_when_gate_setting_off(client: TestClient):
    auth = _signup(client, "gate2@t.com")
    client.patch("/api/settings", headers=auth, json={"require_gate_inward": "false"})
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 201, r.text


def test_billing_unaffected_without_module(client: TestClient):
    auth = _signup(client, "gate3@t.com", model="simple")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 201, r.text


def test_gate_register_and_search(client: TestClient):
    auth = _signup(client, "rep1@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 1}])
    l1 = _po_line_ids(po)[0]
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05", "vehicle_no": "LEB-9999",
        "challan_no": "CH-123", "lines": [{"po_line_id": l1, "qty_received": 10}],
    })
    rows = client.get("/api/purchase-reports/gate-register", headers=auth).json()
    assert len(rows) == 1
    assert rows[0]["vehicle_no"] == "LEB-9999"
    assert float(rows[0]["total_qty"]) == 10.0

    rows = client.get("/api/purchase-reports/gate-register?q=CH-123", headers=auth).json()
    assert len(rows) == 1
    rows = client.get("/api/purchase-reports/gate-register?q=NOPE", headers=auth).json()
    assert rows == []


def test_three_way_match_variances(client: TestClient):
    auth = _signup(client, "rep2@t.com")
    po = _approved_po(client, auth, lines=[{"description": "A", "qty": 10, "rate": 2}])
    l1 = _po_line_ids(po)[0]
    # receive only 8 of 10, then bill with the setting off (variance scenario)
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": "2026-07-05",
        "lines": [{"po_line_id": l1, "qty_received": 8}],
    })
    client.patch("/api/settings", headers=auth, json={"require_gate_inward": "false"})
    r = client.post(f"/api/purchase-orders/{po['id']}/convert-to-bill", headers=auth,
                    json={"bill_date": "2026-07-06", "due_date": "2026-08-06"})
    assert r.status_code == 201, r.text

    rows = client.get("/api/purchase-reports/three-way-match", headers=auth).json()
    assert len(rows) == 1
    row = rows[0]
    assert float(row["po_qty"]) == 10.0
    assert float(row["gi_qty"]) == 8.0
    assert float(row["bill_qty"]) == 10.0
    assert float(row["qty_variance"]) == -2.0     # gi_qty − po_qty
    assert row["flag"] is True
