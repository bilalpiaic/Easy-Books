"""Stock transfers / WMS slice (#302)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str = "wms302@co.test"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "WMS",
            "company_name": "WMS Co",
            "business_model": "trader",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_inventory(client, auth):
    r = client.post("/api/modules/inventory/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def _two_locations(client, auth):
    # MAIN may already exist from inventory install
    locs = client.get("/api/stock-locations?type=own", headers=auth).json()["items"]
    by_code = {l["code"]: l for l in locs}
    if "MAIN" not in by_code:
        m = client.post(
            "/api/stock-locations",
            headers=auth,
            json={"code": "MAIN", "name": "Main Store", "type": "own"},
        )
        assert m.status_code == 201, m.text
        by_code["MAIN"] = m.json()
    if "WH2" not in by_code:
        w = client.post(
            "/api/stock-locations",
            headers=auth,
            json={"code": "WH2", "name": "Warehouse 2", "type": "own"},
        )
        assert w.status_code == 201, w.text
        by_code["WH2"] = w.json()
    return by_code["MAIN"]["id"], by_code["WH2"]["id"]


def test_transfer_ship_receive_preserves_product_qty(client: TestClient):
    auth = _auth(client)
    _install_inventory(client, auth)
    main_id, wh2_id = _two_locations(client, auth)

    prod = client.post(
        "/api/products",
        headers=auth,
        json={
            "name": "Bolt",
            "product_type": "stock",
            "default_rate": 5,
            "opening_qty": 20,
            "opening_cost": 2,
        },
    )
    assert prod.status_code in (200, 201), prod.text
    pid = prod.json()["id"]
    # Opening lands on default own location (MAIN)
    before = client.get(f"/api/products/{pid}", headers=auth).json()
    assert float(before["stock_qty"]) == 20.0

    st = client.post(
        "/api/stock-transfers",
        headers=auth,
        json={
            "transfer_date": "2026-08-01",
            "from_location_id": main_id,
            "to_location_id": wh2_id,
            "lines": [{"product_id": pid, "qty": 5}],
        },
    )
    assert st.status_code == 201, st.text
    tid = st.json()["id"]
    assert st.json()["status"] == "draft"
    assert st.json()["number"].startswith("ST-")

    ship = client.post(f"/api/stock-transfers/{tid}/ship", headers=auth)
    assert ship.status_code == 200, ship.text
    assert ship.json()["status"] == "in_transit"

    mid = client.get(f"/api/products/{pid}", headers=auth).json()
    assert float(mid["stock_qty"]) == 20.0  # unchanged while in transit

    on_hand_main = client.get(
        f"/api/stock-transfers/meta/on-hand?product_id={pid}&location_id={main_id}",
        headers=auth,
    ).json()
    assert float(on_hand_main["qty"]) == 15.0

    recv = client.post(f"/api/stock-transfers/{tid}/receive", headers=auth)
    assert recv.status_code == 200, recv.text
    assert recv.json()["status"] == "received"

    after = client.get(f"/api/products/{pid}", headers=auth).json()
    assert float(after["stock_qty"]) == 20.0

    wh2 = client.get(f"/api/stock-locations/{wh2_id}/stock", headers=auth).json()
    qty_wh2 = sum(float(i["qty"]) for i in wh2["items"] if i["product_id"] == pid)
    assert qty_wh2 == 5.0

    report = client.get("/api/reports/stock-by-warehouse", headers=auth)
    assert report.status_code == 200, report.text
    codes = {w["code"] for w in report.json()["warehouses"]}
    assert "WH2" in codes

    reg = client.get("/api/stock-transfers/register", headers=auth)
    assert reg.status_code == 200
    assert reg.json()["total"] >= 1


def test_transfer_insufficient_stock(client: TestClient):
    auth = _auth(client, "wms302b@co.test")
    _install_inventory(client, auth)
    main_id, wh2_id = _two_locations(client, auth)
    prod = client.post(
        "/api/products",
        headers=auth,
        json={
            "name": "Nut",
            "product_type": "stock",
            "opening_qty": 2,
            "opening_cost": 1,
        },
    ).json()
    st = client.post(
        "/api/stock-transfers",
        headers=auth,
        json={
            "transfer_date": "2026-08-01",
            "from_location_id": main_id,
            "to_location_id": wh2_id,
            "lines": [{"product_id": prod["id"], "qty": 10}],
        },
    ).json()
    ship = client.post(f"/api/stock-transfers/{st['id']}/ship", headers=auth)
    assert ship.status_code == 400
