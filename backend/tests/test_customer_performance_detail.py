"""customer-performance returns a per-customer breakdown when customer_id given."""


def _seed(client, h):
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-01-15",
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 4, "rate": 100}],
    })
    client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-02-10",
        "lines": [{"product_id": p["id"], "description": "Bolt", "qty": 6, "rate": 100}],
    })
    return c, p


def test_breakdown_has_monthly_volume_and_gp(client, admin_headers):
    h = admin_headers
    c, p = _seed(client, h)
    data = client.get(
        f"/api/reports/customer-performance?customer_id={c['id']}"
        f"&start=2026-01-01&end=2026-12-31", headers=h,
    ).json()
    d = data["detail"]
    assert d is not None
    # two months of activity
    months = {m["month"]: m for m in d["monthly"]}
    assert months["2026-01"]["revenue"] == 400
    assert months["2026-02"]["revenue"] == 600
    # GP = revenue - COGS(qty * avg_cost); avg_cost may be 0 if no purchase posted
    assert d["totals"]["revenue"] == 1000
    assert "cogs" in d["totals"] and "gp" in d["totals"]
    # product/category trade summary present
    prod_row = next(r for r in d["products"] if r["product_id"] == p["id"])
    assert prod_row["qty"] == 10
    assert prod_row["revenue"] == 1000


def test_ranking_still_returned_without_customer_id(client, admin_headers):
    h = admin_headers
    _seed(client, h)
    data = client.get("/api/reports/customer-performance", headers=h).json()
    assert "items" in data and len(data["items"]) >= 1
    assert data.get("detail") is None
