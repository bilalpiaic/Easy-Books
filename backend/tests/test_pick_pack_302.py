"""Pick/pack + location reservation (#302 remainder)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str = "pick302@co.test"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Pick",
            "company_name": "Pick Co",
            "business_model": "trader",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_inventory(client, auth):
    r = client.post("/api/modules/inventory/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def test_reservation_blocks_oversell_when_enabled(client: TestClient):
    auth = _auth(client)
    _install_inventory(client, auth)

    client.patch(
        "/api/settings",
        headers=auth,
        json={"stock_reservation_enabled": "true"},
    )

    prod = client.post(
        "/api/products",
        headers=auth,
        json={
            "name": "Widget",
            "product_type": "stock",
            "default_rate": 10,
            "opening_qty": 10,
            "opening_cost": 2,
        },
    )
    assert prod.status_code in (200, 201), prod.text
    pid = prod.json()["id"]

    res = client.post(
        "/api/pick-lists/reservations",
        headers=auth,
        json={"product_id": pid, "qty": 8, "source_doc_type": "manual"},
    )
    assert res.status_code == 201, res.text

    avail = client.get(
        f"/api/pick-lists/meta/available?product_id={pid}",
        headers=auth,
    )
    assert avail.status_code == 200
    assert float(avail.json()["available"]) == 2.0
    assert float(avail.json()["reserved"]) == 8.0

    # Second reservation for 5 should fail (only 2 ATP)
    bad = client.post(
        "/api/pick-lists/reservations",
        headers=auth,
        json={"product_id": pid, "qty": 5},
    )
    assert bad.status_code == 400


def test_pick_pack_from_invoice(client: TestClient):
    auth = _auth(client, "pickpack302@co.test")
    _install_inventory(client, auth)
    client.patch("/api/settings", headers=auth, json={"stock_reservation_enabled": "true"})

    prod = client.post(
        "/api/products",
        headers=auth,
        json={
            "name": "Bolt",
            "code": "BOLT-1",
            "product_type": "stock",
            "default_rate": 5,
            "opening_qty": 20,
            "opening_cost": 1,
        },
    )
    assert prod.status_code in (200, 201), prod.text
    pid = prod.json()["id"]

    cust = client.post(
        "/api/customers",
        headers=auth,
        json={"name": "Buyer Co"},
    )
    assert cust.status_code in (200, 201), cust.text
    cid = cust.json()["id"]

    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cid,
            "issue_date": "2026-08-01",
            "due_date": "2026-08-15",
            "lines": [
                {"product_id": pid, "description": "Bolt", "qty": 3, "rate": 5},
            ],
        },
    )
    assert inv.status_code in (200, 201), inv.text
    iid = inv.json()["id"]

    pl = client.post(
        "/api/pick-lists",
        headers=auth,
        json={"invoice_id": iid, "reserve": True},
    )
    assert pl.status_code == 201, pl.text
    body = pl.json()
    assert body["status"] == "draft"
    assert len(body["lines"]) == 1
    assert body["lines"][0]["reservation_id"] is not None
    plid = body["id"]
    line_id = body["lines"][0]["id"]

    start = client.post(f"/api/pick-lists/{plid}/start", headers=auth)
    assert start.status_code == 200
    assert start.json()["status"] == "picking"

    picked = client.post(
        f"/api/pick-lists/{plid}/pick",
        headers=auth,
        json={"lines": [{"line_id": line_id, "qty_picked": 3}]},
    )
    assert picked.status_code == 200, picked.text
    assert picked.json()["status"] == "picked"

    packed = client.post(f"/api/pick-lists/{plid}/pack", headers=auth)
    assert packed.status_code == 200
    assert packed.json()["status"] == "packed"
