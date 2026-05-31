"""WS-3: product category CRUD — 2-level cap and delete guards."""


def test_two_level_cap_and_delete_guard(client, admin_headers):
    h = admin_headers
    parent = client.post("/api/product-categories", json={"name": "SIM"}, headers=h).json()
    sub = client.post("/api/product-categories", json={"name": "Prepaid", "parent_id": parent["id"]}, headers=h).json()

    # A third level is rejected.
    r = client.post("/api/product-categories", json={"name": "Lyca", "parent_id": sub["id"]}, headers=h)
    assert r.status_code == 400
    assert "two levels" in r.json()["detail"].lower()

    # Deleting a parent that still has children is blocked.
    assert client.delete(f"/api/product-categories/{parent['id']}", headers=h).status_code == 400

    # Deleting the leaf works, then the parent works.
    assert client.delete(f"/api/product-categories/{sub['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/product-categories/{parent['id']}", headers=h).status_code == 200


def test_categories_are_tenant_isolated(client, admin_headers):
    """A second tenant must not see or mutate the first tenant's categories."""
    h1 = admin_headers
    cat = client.post("/api/product-categories", json={"name": "OnlyTenant1"}, headers=h1).json()

    # Make a second tenant + owner.
    client.post("/api/auth/signup", json={
        "email": "owner2@beta.test", "password": "pw12345678",
        "full_name": "Owner2", "company_name": "Beta",
    })
    tok2 = client.post("/api/auth/login", data={
        "username": "owner2@beta.test", "password": "pw12345678",
    }).json()["access_token"]
    h2 = {"Authorization": f"Bearer {tok2}"}

    # Tenant 2 sees an empty list and cannot delete tenant 1's category.
    assert client.get("/api/product-categories", headers=h2).json() == []
    assert client.delete(f"/api/product-categories/{cat['id']}", headers=h2).status_code == 404


def test_product_can_be_assigned_a_category(client, admin_headers):
    h = admin_headers
    cat = client.post("/api/product-categories", json={"name": "Goods"}, headers=h).json()
    p = client.post("/api/products", json={"name": "Widget", "product_type": "stock",
                                           "category_id": cat["id"]}, headers=h).json()
    assert p.get("category_id") == cat["id"]
    listed = client.get(f"/api/products?category_id={cat['id']}", headers=h).json()
    items = listed if isinstance(listed, list) else listed.get("items", listed)
    assert any(x["id"] == p["id"] for x in items)
