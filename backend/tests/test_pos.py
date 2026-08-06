"""Point of Sale module (#304)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Cashier",
            "company_name": "POS Shop",
            "business_model": "trader",
        },
    )
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install(client: TestClient, auth, *modules: str):
    for m in modules:
        r = client.post(f"/api/modules/{m}/install", headers=auth)
        assert r.status_code in (200, 201), f"{m}: {r.text}"


def test_pos_module_gate(client: TestClient):
    client.post(
        "/api/auth/signup",
        json={
            "email": "pos-gate@test.com",
            "password": "password123",
            "full_name": "Owner",
            "company_name": "No POS Co",
            "business_model": "simple",
        },
    )
    r = client.post(
        "/api/auth/login",
        data={"username": "pos-gate@test.com", "password": "password123"},
    )
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    blocked = client.get("/api/pos/registers", headers=auth)
    assert blocked.status_code == 403


def test_pos_sale_shift_close(client: TestClient):
    auth = _signup(client, "pos-ok@test.com")
    # trader already has inventory+pos; ensure installed
    _install(client, auth, "inventory", "pos")

    prod = client.post(
        "/api/products",
        headers=auth,
        json={
            "name": "Soda",
            "product_type": "service",
            "default_rate": 10,
            "unit": "pcs",
        },
    )
    assert prod.status_code in (200, 201), prod.text
    product_id = prod.json()["id"]

    reg = client.post(
        "/api/pos/registers",
        headers=auth,
        json={"name": "Counter 1", "code": "C1"},
    )
    assert reg.status_code == 201, reg.text
    register_id = reg.json()["id"]
    assert reg.json()["cash_account_id"] is not None

    # Seed sample also creates a register when installing with seed — list ok
    regs = client.get("/api/pos/registers", headers=auth)
    assert regs.status_code == 200
    assert any(r["id"] == register_id for r in regs.json())

    opened = client.post(
        "/api/pos/shifts/open",
        headers=auth,
        json={"register_id": register_id, "opening_float": 100},
    )
    assert opened.status_code == 201, opened.text
    shift_id = opened.json()["id"]
    assert opened.json()["status"] == "open"
    assert float(opened.json()["opening_float"]) == 100.0

    # Second open on same register blocked
    dup = client.post(
        "/api/pos/shifts/open",
        headers=auth,
        json={"register_id": register_id, "opening_float": 0},
    )
    assert dup.status_code == 400

    sale = client.post(
        "/api/pos/sales",
        headers=auth,
        json={
            "shift_id": shift_id,
            "tender": "cash",
            "cash_tendered": 50,
            "gst_rate": 0,
            "lines": [{"product_id": product_id, "qty": 2}],
        },
    )
    assert sale.status_code == 201, sale.text
    body = sale.json()
    assert body["invoice_id"]
    assert body["payment_received_id"]
    assert float(body["total"]) == 20.0
    assert float(body["change_given"]) == 30.0
    assert body["tender"] == "cash"

    inv = client.get(f"/api/invoices/{body['invoice_id']}", headers=auth)
    assert inv.status_code == 200, inv.text
    assert inv.json()["status"] == "paid"
    assert float(inv.json()["total"]) == 20.0

    detail = client.get(f"/api/pos/shifts/{shift_id}", headers=auth)
    assert detail.status_code == 200
    d = detail.json()
    assert d["sale_count"] == 1
    # opening 100 + (50 tendered - 30 change) = 120
    assert float(d["expected_cash_live"]) == 120.0

    closed = client.post(
        f"/api/pos/shifts/{shift_id}/close",
        headers=auth,
        json={"closing_count": 119, "notes": "short a coin"},
    )
    assert closed.status_code == 200, closed.text
    c = closed.json()
    assert c["status"] == "closed"
    assert float(c["expected_cash"]) == 120.0
    assert float(c["closing_count"]) == 119.0
    assert float(c["variance"]) == -1.0

    # Sale on closed shift rejected
    again = client.post(
        "/api/pos/sales",
        headers=auth,
        json={
            "shift_id": shift_id,
            "tender": "cash",
            "gst_rate": 0,
            "lines": [{"product_id": product_id, "qty": 1}],
        },
    )
    assert again.status_code == 400


def test_pos_stock_sale_relieves_inventory(client: TestClient):
    auth = _signup(client, "pos-stock@test.com")
    _install(client, auth, "inventory", "pos")

    prod = client.post(
        "/api/products",
        headers=auth,
        json={
            "name": "Widget",
            "product_type": "stock",
            "default_rate": 25,
            "unit": "pcs",
            "opening_qty": 10,
            "opening_cost": 10,
        },
    )
    assert prod.status_code in (200, 201), prod.text
    product_id = prod.json()["id"]

    reg = client.post(
        "/api/pos/registers",
        headers=auth,
        json={"name": "Main", "code": "M1"},
    ).json()
    shift = client.post(
        "/api/pos/shifts/open",
        headers=auth,
        json={"register_id": reg["id"], "opening_float": 0},
    ).json()

    sale = client.post(
        "/api/pos/sales",
        headers=auth,
        json={
            "shift_id": shift["id"],
            "tender": "cash",
            "gst_rate": 0,
            "lines": [{"product_id": product_id, "qty": 3, "rate": 25}],
        },
    )
    assert sale.status_code == 201, sale.text
    assert float(sale.json()["total"]) == 75.0

    after = client.get(f"/api/products/{product_id}", headers=auth)
    assert after.status_code == 200, after.text
    assert float(after.json()["stock_qty"]) == 7.0


def test_pos_install_sample_seeds_register(client: TestClient):
    client.post(
        "/api/auth/signup",
        json={
            "email": "pos-sample@test.com",
            "password": "password123",
            "full_name": "Owner",
            "company_name": "Sample POS",
            "business_model": "simple",
        },
    )
    r = client.post(
        "/api/auth/login",
        data={"username": "pos-sample@test.com", "password": "password123"},
    )
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    _install(client, auth, "inventory")
    inst = client.post("/api/modules/pos/install?seed_sample=true", headers=auth)
    assert inst.status_code in (200, 201), inst.text
    regs = client.get("/api/pos/registers", headers=auth)
    assert regs.status_code == 200
    assert len(regs.json()) >= 1
    assert any(r["name"] == "Front Counter" for r in regs.json())
