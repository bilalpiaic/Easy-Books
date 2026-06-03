"""Convergent backfill tags products left without a category."""
from fastapi.testclient import TestClient
from main import app
from sqlmodel import Session, select


def _auth(client: TestClient) -> dict:
    client.post("/api/auth/signup", json={
        "email": "bf@p.test", "password": "password123",
        "full_name": "U", "company_name": "BF Co"})
    r = client.post("/api/auth/login", data={"username": "bf@p.test", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_backfill_tags_untagged_products(client: TestClient):
    import db as dbmod
    from models import Product, ProductCategory

    auth = _auth(client)
    main = client.post("/api/product-categories", headers=auth, json={"name": "Goods"}).json()
    sub = client.post("/api/product-categories", headers=auth,
                      json={"name": "Imported", "parent_id": main["id"]}).json()
    # A product created with NO category (simulates pre-feature / older-seed data)
    p = client.post("/api/products", headers=auth, json={
        "name": "Loose Widget", "product_type": "stock", "price": 5, "sku": "LW1"}).json()

    eng = app.state.engine
    with Session(eng) as s:
        assert s.get(Product, p["id"]).category_id is None  # precondition
        dbmod._backfill_untagged_products(s)
    with Session(eng) as s:
        sub_ids = {c.id for c in s.exec(
            select(ProductCategory).where(ProductCategory.parent_id.is_not(None))).all()}
        assert s.get(Product, p["id"]).category_id in sub_ids  # now tagged to a sub


def test_backfill_is_noop_when_all_tagged(client: TestClient):
    """Second run leaves the already-tagged product untouched (idempotent)."""
    import db as dbmod
    from models import Product

    auth = _auth(client)
    main = client.post("/api/product-categories", headers=auth, json={"name": "Goods"}).json()
    client.post("/api/product-categories", headers=auth,
                json={"name": "Imported", "parent_id": main["id"]})
    p = client.post("/api/products", headers=auth, json={
        "name": "W", "product_type": "stock", "price": 5, "sku": "W1"}).json()

    eng = app.state.engine
    with Session(eng) as s:
        dbmod._backfill_untagged_products(s)
    with Session(eng) as s:
        first = s.get(Product, p["id"]).category_id
        dbmod._backfill_untagged_products(s)  # second run
    with Session(eng) as s:
        assert s.get(Product, p["id"]).category_id == first  # unchanged
