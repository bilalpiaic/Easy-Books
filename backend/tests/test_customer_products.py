"""Customer's-products module: every product sold to a customer + last price."""


def test_customer_products_aggregates(client, admin_headers):
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h,
                    json={"name": "Bolt", "product_type": "stock"}).json()
    for rate, date, qty in [(10, "2026-01-01", 5), (12, "2026-02-01", 3)]:
        client.post("/api/invoices", headers=h, json={
            "customer_id": c["id"], "issue_date": date,
            "lines": [{"product_id": p["id"], "description": "Bolt",
                       "qty": qty, "rate": rate}],
        })
    data = client.get(f"/api/customers/{c['id']}/products", headers=h).json()
    row = next(r for r in data["items"] if r["product_id"] == p["id"])
    assert row["last_rate"] == 12          # most recent
    assert row["last_date"] == "2026-02-01"
    assert row["total_qty"] == 8           # 5 + 3
    assert row["invoice_count"] == 2
