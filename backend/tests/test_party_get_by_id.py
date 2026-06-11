"""GET /api/customers/{id} and /api/vendors/{id} — single-entity fetch backing
the full-page edit routes (#40). Tenant-scoped; 404 on miss / cross-tenant."""


def test_get_customer_by_id(client, admin_headers):
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={
        "name": "Acme", "email": "a@acme.test", "phone": "123", "opening_balance": 50,
    }).json()
    got = client.get(f"/api/customers/{c['id']}", headers=h)
    assert got.status_code == 200
    body = got.json()
    assert body["id"] == c["id"]
    assert body["name"] == "Acme"
    assert body["email"] == "a@acme.test"


def test_get_customer_missing_404(client, admin_headers):
    assert client.get("/api/customers/99999", headers=admin_headers).status_code == 404


def test_get_vendor_by_id(client, admin_headers):
    h = admin_headers
    v = client.post("/api/vendors", headers=h, json={"name": "Supplier Co", "phone": "555"}).json()
    got = client.get(f"/api/vendors/{v['id']}", headers=h)
    assert got.status_code == 200
    body = got.json()
    assert body["id"] == v["id"]
    assert body["name"] == "Supplier Co"


def test_get_vendor_missing_404(client, admin_headers):
    assert client.get("/api/vendors/99999", headers=admin_headers).status_code == 404


def test_get_customer_does_not_shadow_products_subroute(client, admin_headers):
    """Regression: /{id} must not capture /{id}/products."""
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={"name": "RouteCo"}).json()
    r = client.get(f"/api/customers/{c['id']}/products", headers=h)
    assert r.status_code == 200
    assert "items" in r.json()
