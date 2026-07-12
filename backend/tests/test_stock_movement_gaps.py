"""Follow-ups from the #137/#145 final reviews: every stock_qty mutation
must emit a StockMovement so the perpetual Stock Tie-out reconciles."""
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


def _tie_out_row(client, auth, product_id):
    rows = client.get(
        f"/api/store-reports/stock-tie-out?product_id={product_id}", headers=auth
    ).json()
    return rows[0]


def _received_bill(client, auth, product_id, qty, rate=4):
    bill = client.post("/api/bills", headers=auth, json={
        "vendor_name": "Sup", "bill_date": "2026-02-01", "gst_rate": 0,
        "lines": [{"product_id": product_id, "description": "Nut", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/bills/{bill['id']}/status?status=received", headers=auth)
    return client.get(f"/api/bills/{bill['id']}", headers=auth).json()


def test_bill_edit_reversal_ties_out(client: TestClient):
    auth = _signup(client, "rev1@t.com")
    p = client.post("/api/products", headers=auth,
                    json={"name": "Nut", "product_type": "stock", "unit": "pcs"}).json()
    bill = _received_bill(client, auth, p["id"], qty=50)
    client.put(f"/api/bills/{bill['id']}", headers=auth, json={
        "vendor_name": "Sup", "bill_date": "2026-02-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Nut", "qty": 30, "rate": 4}],
    })
    row = _tie_out_row(client, auth, p["id"])
    assert float(row["actual_closing"]) == 30
    assert float(row["variance"]) == 0     # was -50 before the fix
    # the reversal must not masquerade as a bill receipt in the display column
    assert float(row["received_qty"]) == 80  # 50 original + 30 re-post


def test_bill_void_reversal_ties_out(client: TestClient):
    auth = _signup(client, "rev2@t.com")
    p = client.post("/api/products", headers=auth,
                    json={"name": "Bolt", "product_type": "stock", "unit": "pcs"}).json()
    bill = _received_bill(client, auth, p["id"], qty=20, rate=5)
    r = client.post(f"/api/transactions/{bill['transaction_id']}/reverse", headers=auth)
    assert r.status_code == 200
    row = _tie_out_row(client, auth, p["id"])
    assert float(row["actual_closing"]) == 0
    assert float(row["variance"]) == 0     # was -20 before the fix
