"""Product COA valuation tree + product-ledger location field."""
from decimal import Decimal

from fastapi.testclient import TestClient
from main import app
from sqlmodel import Session, select


def _auth(client: TestClient) -> dict:
    client.post("/api/auth/signup", json={
        "email": "coa@p.test", "password": "password123",
        "full_name": "U", "company_name": "COA Co"})
    r = client.post("/api/auth/login", data={"username": "coa@p.test", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _stock_product(client, auth, name, sku, category_id=None, qty=10, cost=5):
    p = client.post("/api/products", headers=auth, json={
        "name": name, "product_type": "stock", "price": 20, "sku": sku,
        **({"category_id": category_id} if category_id else {})}).json()
    vend = client.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    client.post("/api/bills", headers=auth, json={
        "vendor_id": vend["id"], "bill_date": "2026-05-01", "due_date": "2026-05-31",
        "gst_rate": 0, "status": "posted",
        "lines": [{"description": name, "qty": qty, "rate": cost, "product_id": p["id"]}]})
    return p


def test_product_coa_tree_groups_and_subtotals(client: TestClient):
    auth = _auth(client)
    # Main "Goods" -> Sub "Imported"
    main = client.post("/api/product-categories", headers=auth, json={"name": "Goods"}).json()
    sub = client.post("/api/product-categories", headers=auth,
                      json={"name": "Imported", "parent_id": main["id"]}).json()
    _stock_product(client, auth, "Widget", "W1", category_id=sub["id"], qty=10, cost=5)
    _stock_product(client, auth, "Gadget", "G1", category_id=sub["id"], qty=4, cost=20)

    r = client.get("/api/reports/product-coa", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    goods = next(g for g in data["groups"] if g["name"] == "Goods")
    imported = next(s for s in goods["subs"] if s["name"] == "Imported")
    # 10*5 + 4*20 = 50 + 80 = 130
    assert Decimal(str(imported["value"])) == Decimal("130")
    assert Decimal(str(goods["value"])) == Decimal("130")
    assert Decimal(str(data["grand"]["value"])) == Decimal("130")
    assert {i["name"] for i in imported["items"]} == {"Widget", "Gadget"}


def test_product_coa_uncategorized_bucket(client: TestClient):
    auth = _auth(client)
    _stock_product(client, auth, "Loose", "L1", category_id=None, qty=3, cost=7)
    data = client.get("/api/reports/product-coa", headers=auth).json()
    unc = next(g for g in data["groups"] if g["name"] == "Uncategorized")
    assert Decimal(str(unc["value"])) == Decimal("21")  # 3*7
    assert unc["subs"][0]["name"] == "—"


def test_product_ledger_items_carry_location(client: TestClient):
    auth = _auth(client)
    p = _stock_product(client, auth, "Widget", "W1", qty=10, cost=5)
    data = client.get(f"/api/reports/product-ledger?product_id={p['id']}", headers=auth).json()
    assert data["items"], "expected at least one movement"
    assert "location" in data["items"][0]
