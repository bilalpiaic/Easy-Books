"""eCommerce connectors (#305) — mock connect → map SKU → import draft invoices."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Ecom Tester",
            "company_name": "Ecom Co",
            "business_model": "trader",
        },
    )
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install(client: TestClient, auth, *mods: str):
    for m in mods:
        r = client.post(f"/api/modules/{m}/install", headers=auth)
        assert r.status_code in (200, 201), (m, r.text)


def test_ecommerce_module_gate(client: TestClient):
    auth = _signup(client, "ecom-gate@test.com")
    # trader defaults include inventory+pos but not ecommerce
    r = client.get("/api/ecommerce/connections", headers=auth)
    assert r.status_code == 403


def test_mock_connect_map_import_orders(client: TestClient):
    auth = _signup(client, "ecom-flow@test.com")
    _install(client, auth, "inventory", "ecommerce")

    p1 = client.post("/api/products", headers=auth, json={
        "name": "Canvas Tote", "code": "WEB-SKU-A", "unit": "pcs",
        "product_type": "stock", "default_rate": 18, "opening_qty": 50,
    }).json()
    p2 = client.post("/api/products", headers=auth, json={
        "name": "Notebook Pack", "code": "WEB-SKU-B", "unit": "pcs",
        "product_type": "stock", "default_rate": 12.5, "opening_qty": 80,
    }).json()
    assert p1.get("id") and p2.get("id")

    providers = client.get("/api/ecommerce/providers", headers=auth).json()
    assert {p["id"] for p in providers} >= {"mock", "shopify", "woocommerce", "daraz"}

    conn = client.post("/api/ecommerce/connections", headers=auth, json={
        "provider": "mock",
        "shop_name": "Demo Shop",
        "stock_sync_direction": "store_to_eb",
    }).json()
    assert conn["provider"] == "mock"
    assert conn["access_token_masked"]
    cid = conn["id"]

    mapped = client.post(f"/api/ecommerce/connections/{cid}/products/auto-map", headers=auth).json()
    assert mapped["linked"] == 2

    remote = client.get(f"/api/ecommerce/connections/{cid}/products", headers=auth).json()
    assert len(remote) == 2
    assert all(r["mapped_product_id"] for r in remote)

    sync = client.post(f"/api/ecommerce/connections/{cid}/sync", headers=auth).json()
    assert sync["created_count"] == 2
    assert sync["skipped"] == 0

    sync2 = client.post(f"/api/ecommerce/connections/{cid}/sync", headers=auth).json()
    assert sync2["created_count"] == 0
    assert sync2["skipped"] == 2

    imports = client.get(f"/api/ecommerce/connections/{cid}/imports", headers=auth).json()
    assert len(imports) == 2
    inv_id = imports[0]["invoice_id"]
    inv = client.get(f"/api/invoices/{inv_id}", headers=auth).json()
    assert inv["status"] == "draft"

    patched = client.patch(f"/api/ecommerce/connections/{cid}", headers=auth, json={
        "stock_sync_direction": "eb_to_store",
    }).json()
    assert patched["stock_sync_direction"] == "eb_to_store"


def test_shopify_provider_requires_token(client: TestClient):
    auth = _signup(client, "ecom-shopify@test.com")
    _install(client, auth, "inventory", "ecommerce")
    conn = client.post("/api/ecommerce/connections", headers=auth, json={
        "provider": "shopify",
        "shop_domain": "example.myshopify.com",
        "access_token": "",
    }).json()
    r = client.post(f"/api/ecommerce/connections/{conn['id']}/sync", headers=auth)
    assert r.status_code == 400
    assert "access_token" in r.json()["detail"].lower() or "required" in r.json()["detail"].lower()


def test_daraz_sandbox_sync_and_eb_to_store_push(client: TestClient):
    auth = _signup(client, "ecom-daraz@test.com")
    _install(client, auth, "inventory", "ecommerce")
    client.post("/api/products", headers=auth, json={
        "name": "Daraz Tote", "code": "DZ-SKU-A", "product_type": "stock",
        "default_rate": 1499, "opening_qty": 10, "opening_cost": 100,
    })
    conn = client.post("/api/ecommerce/connections", headers=auth, json={
        "provider": "daraz",
        "shop_name": "Daraz PK",
        "stock_sync_direction": "eb_to_store",
    }).json()
    assert conn["provider"] == "daraz"
    cid = conn["id"]
    mapped = client.post(f"/api/ecommerce/connections/{cid}/products/auto-map", headers=auth).json()
    assert mapped["linked"] >= 1
    sync = client.post(f"/api/ecommerce/connections/{cid}/sync", headers=auth)
    assert sync.status_code == 200, sync.text
    body = sync.json()
    assert body["created_count"] >= 1

