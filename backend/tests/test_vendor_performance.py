"""#137 Phase 4 — vendor performance: delivery lead time + rate trend +
short-receipt-rate proxy (documented stand-in for true rejection rate,
which this schema can't track — see spec decision #4)."""
from datetime import date, timedelta

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


def _second_admin(client, auth, email="approver@t.com"):
    """Invite a second admin in the same tenant and return their auth header."""
    client.post(
        "/api/users",
        headers=auth,
        json={"email": email, "password": "password123", "full_name": "Approver", "role": "admin"},
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _full_chain_po(client, auth, vendor_id, product_id, qty=10, rate=5,
                    order_date="2026-06-01", gi_date="2026-06-08"):
    """Builds one PurchaseOrder with a linked GateInward, bypassing the
    Demand/Comparative chain (purchase_store's require_purchase_chain
    defaults on, but auto-toggles off once a demand-less PO is the only
    path being tested — matches the existing test_purchase_flow.py
    convention of disabling the chain setting for isolated PO tests).

    NOTE: POST /api/purchase-orders returns the bare PurchaseOrder row with
    no "lines" key (routers/purchase_orders.py:150 `return po` — only
    GET /{po_id} attaches lines, routers/purchase_orders.py:68-80). Must
    re-fetch via GET to get each line's id for the Gate Inward call."""
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    po = client.post("/api/purchase-orders", headers=auth, json={
        "vendor_id": vendor_id, "order_date": order_date,
        "lines": [{"product_id": product_id, "description": "Item", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/purchase-orders/{po['id']}/approve", headers=auth)
    po = client.get(f"/api/purchase-orders/{po['id']}", headers=auth).json()
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po["id"], "gate_date": gi_date,
        "lines": [{"po_line_id": po["lines"][0]["id"], "qty_received": qty}],
    })
    return po


def test_vendor_performance_lead_time(client: TestClient):
    auth = _signup(client, "vp1@t.com")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Lead Time Vendor"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "VP Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    _full_chain_po(client, auth, vendor["id"], product["id"],
                    order_date="2026-06-01", gi_date="2026-06-08")   # 7 days
    _full_chain_po(client, auth, vendor["id"], product["id"],
                    order_date="2026-06-10", gi_date="2026-06-15")   # 5 days

    rows = client.get("/api/purchase-reports/vendor-performance", headers=auth).json()
    row = next(r for r in rows if r["vendor_id"] == vendor["id"])
    assert row["po_count"] == 2
    assert row["avg_lead_time_days"] == 6.0  # (7+5)/2


def test_vendor_performance_rate_trend(client: TestClient):
    auth = _signup(client, "vp2@t.com")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Rate Vendor"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "Rate Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    demand = client.post("/api/purchase-demands", headers=auth, json={
        "demand_date": "2026-05-01", "required_by": "2026-06-01", "purpose": "restock",
        "lines": [{"product_id": product["id"], "description": "Item", "qty": 10}],
    }).json()
    # A second admin must approve (creator cannot self-approve)
    auth2 = _second_admin(client, auth, email=f"appr-vp2-{demand['id']}@t.com")
    client.patch(f"/api/purchase-demands/{demand['id']}/approve", headers=auth2)
    client.post("/api/quotations", headers=auth, json={
        "demand_id": demand["id"], "vendor_id": vendor["id"], "quote_date": "2026-05-05",
        "lines": [{"demand_line_id": demand["lines"][0]["id"], "rate": 8, "qty": 10}],
    })

    rows = client.get("/api/purchase-reports/vendor-performance", headers=auth).json()
    row = next(r for r in rows if r["vendor_id"] == vendor["id"])
    assert len(row["rate_trend"]) == 1
    assert row["rate_trend"][0]["product_id"] == product["id"]
    assert row["rate_trend"][0]["product_name"] == "Rate Widget"
    assert row["rate_trend"][0]["rate"] == 8


def test_vendor_performance_short_receipt_matches_three_way_match(client: TestClient):
    """Cross-checks against the existing 3-way-match calc rather than
    re-deriving variance independently, per spec's stated guard against
    the two silently diverging."""
    auth = _signup(client, "vp3@t.com")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Short Vendor"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "Short Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    _full_chain_po(client, auth, vendor["id"], product["id"], qty=10, gi_date="2026-06-08")
    # Deliberately short-receive: only 7 of 10 actually received this time
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    po2 = client.post("/api/purchase-orders", headers=auth, json={
        "vendor_id": vendor["id"], "order_date": "2026-06-10",
        "lines": [{"product_id": product["id"], "description": "Item", "qty": 10, "rate": 5}],
    }).json()
    client.patch(f"/api/purchase-orders/{po2['id']}/approve", headers=auth)
    po2 = client.get(f"/api/purchase-orders/{po2['id']}", headers=auth).json()  # re-fetch for lines
    client.post("/api/gate-inwards", headers=auth, json={
        "po_id": po2["id"], "gate_date": "2026-06-17",
        "lines": [{"po_line_id": po2["lines"][0]["id"], "qty_received": 7}],
    })

    twm_rows = client.get("/api/purchase-reports/three-way-match", headers=auth).json()
    twm_variance = sum(r["qty_variance"] for r in twm_rows if r["vendor_name"] == "Short Vendor")

    vp_rows = client.get("/api/purchase-reports/vendor-performance", headers=auth).json()
    row = next(r for r in vp_rows if r["vendor_id"] == vendor["id"])
    ordered_total = 20  # 10 + 10 across the two POs
    expected_pct = round(abs(twm_variance) / ordered_total * 100, 2)
    assert row["short_receipt_rate_pct"] == expected_pct


def test_vendor_performance_pending_po_not_counted_short(client: TestClient):
    """An approved PO with no gate activity yet is an undelivered order,
    not a 100% short receipt (#145 review follow-up)."""
    auth = _signup(client, "vp4@t.com")
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Pending Vendor"}).json()
    product = client.post("/api/products", headers=auth, json={
        "name": "Pending Widget", "product_type": "stock", "unit": "pcs",
    }).json()
    _full_chain_po(client, auth, vendor["id"], product["id"], qty=10)  # fully received
    client.patch("/api/settings", headers=auth, json={"require_purchase_chain": "false"})
    po2 = client.post("/api/purchase-orders", headers=auth, json={
        "vendor_id": vendor["id"], "order_date": "2026-06-20",
        "lines": [{"product_id": product["id"], "description": "Item", "qty": 10, "rate": 5}],
    }).json()
    client.patch(f"/api/purchase-orders/{po2['id']}/approve", headers=auth)  # no GI ever

    rows = client.get("/api/purchase-reports/vendor-performance", headers=auth).json()
    row = next(r for r in rows if r["vendor_id"] == vendor["id"])
    assert row["po_count"] == 2
    assert row["short_receipt_rate_pct"] == 0.0   # was 50.0 before the fix
