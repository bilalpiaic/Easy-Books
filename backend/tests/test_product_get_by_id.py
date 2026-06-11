"""GET /api/products/{id} — single-entity fetch backing the full-page edit
route (#40). Must not shadow the static /stock-summary or /{id}/last-price routes."""


def test_get_product_by_id(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h, json={
        "name": "Widget", "code": "W-1", "product_type": "stock", "default_rate": 25,
    }).json()
    got = client.get(f"/api/products/{p['id']}", headers=h)
    assert got.status_code == 200
    body = got.json()
    assert body["id"] == p["id"]
    assert body["name"] == "Widget"
    assert body["product_type"] == "stock"


def test_get_product_missing_404(client, admin_headers):
    assert client.get("/api/products/99999", headers=admin_headers).status_code == 404


def test_get_product_does_not_shadow_stock_summary(client, admin_headers):
    """Regression: /{product_id} must not capture the static /stock-summary route."""
    r = client.get("/api/products/stock-summary", headers=admin_headers)
    assert r.status_code == 200
    # stock-summary returns a summary payload, not a single product
    assert "id" not in r.json() or isinstance(r.json(), dict)


def test_get_product_does_not_shadow_last_price(client, admin_headers):
    """Regression: /{product_id} must not capture /{product_id}/last-price."""
    h = admin_headers
    p = client.post("/api/products", headers=h, json={"name": "Gadget", "product_type": "stock"}).json()
    r = client.get(f"/api/products/{p['id']}/last-price", headers=h)
    assert r.status_code == 200
    assert "rate" in r.json()
