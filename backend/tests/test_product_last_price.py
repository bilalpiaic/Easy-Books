"""Last-price lookup: per-customer first, global fallback."""


def _make_invoice(client, h, customer_id, product_id, rate, date):
    return client.post("/api/invoices", headers=h, json={
        "customer_id": customer_id, "issue_date": date,
        "lines": [{"product_id": product_id, "description": "x",
                   "qty": 1, "rate": rate}],
    })


def test_last_price_prefers_this_customer(client, admin_headers):
    h = admin_headers
    a = client.post("/api/customers", headers=h, json={"name": "A"}).json()
    b = client.post("/api/customers", headers=h, json={"name": "B"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Widget", "product_type": "stock"}).json()
    _make_invoice(client, h, a["id"], p["id"], 100, "2026-01-01")
    _make_invoice(client, h, b["id"], p["id"], 250, "2026-02-01")  # later, other cust
    r = client.get(
        f"/api/products/{p['id']}/last-price?customer_id={a['id']}&kind=sale",
        headers=h,
    ).json()
    assert r["rate"] == 100
    assert r["scope"] == "customer"


def test_last_price_global_fallback(client, admin_headers):
    h = admin_headers
    a = client.post("/api/customers", headers=h, json={"name": "A"}).json()
    b = client.post("/api/customers", headers=h, json={"name": "B"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Gadget", "product_type": "stock"}).json()
    _make_invoice(client, h, b["id"], p["id"], 77, "2026-03-01")
    r = client.get(
        f"/api/products/{p['id']}/last-price?customer_id={a['id']}&kind=sale",
        headers=h,
    ).json()
    assert r["rate"] == 77
    assert r["scope"] == "global"


def test_last_price_none_when_never_sold(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h,
                    json={"name": "New", "product_type": "stock"}).json()
    r = client.get(f"/api/products/{p['id']}/last-price?kind=sale", headers=h).json()
    assert r["rate"] is None
    assert r["scope"] is None
