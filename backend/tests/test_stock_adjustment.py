"""POST /api/products/{id}/adjust-stock — physical count variance with GL posting."""
from decimal import Decimal


def _make_stock_product(client, headers, name="Widget", opening_qty=10, unit_cost=5):
    p = client.post("/api/products", headers=headers, json={
        "name": name, "code": f"W-{name[:2]}", "product_type": "stock",
        "default_rate": 20, "opening_qty": opening_qty, "opening_cost": unit_cost,
    }).json()
    assert p.get("id"), f"Product creation failed: {p}"
    return p


def test_adjust_stock_negative_variance(client, admin_headers):
    """Physical count finds less stock → Dr Inventory Adjustments / Cr Inventory."""
    p = _make_stock_product(client, admin_headers, name="WidgetNeg", opening_qty=10, unit_cost=5)
    r = client.post(
        f"/api/products/{p['id']}/adjust-stock",
        headers=admin_headers,
        json={"counted_qty": 7, "date": "2026-06-14", "notes": "Shrinkage found"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["variance"]) == Decimal("-3")
    assert body["jv_number"] is not None
    # Stock qty should now be 7
    got = client.get(f"/api/products/{p['id']}", headers=admin_headers).json()
    assert Decimal(got["stock_qty"]) == Decimal("7")


def test_adjust_stock_positive_variance(client, admin_headers):
    """Physical count finds more stock → Dr Inventory / Cr Inventory Adjustments."""
    p = _make_stock_product(client, admin_headers, name="WidgetPos", opening_qty=10, unit_cost=5)
    r = client.post(
        f"/api/products/{p['id']}/adjust-stock",
        headers=admin_headers,
        json={"counted_qty": 12, "date": "2026-06-14"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["variance"]) == Decimal("2")
    got = client.get(f"/api/products/{p['id']}", headers=admin_headers).json()
    assert Decimal(got["stock_qty"]) == Decimal("12")


def test_adjust_stock_no_variance(client, admin_headers):
    """Counted qty matches system qty — no JV posted."""
    p = _make_stock_product(client, admin_headers, name="WidgetZero", opening_qty=10, unit_cost=5)
    r = client.post(
        f"/api/products/{p['id']}/adjust-stock",
        headers=admin_headers,
        json={"counted_qty": 10, "date": "2026-06-14"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["variance"]) == Decimal("0")
    assert body["jv_number"] is None


def test_adjust_stock_service_product_rejected(client, admin_headers):
    """Service products cannot be stock-adjusted."""
    p = client.post("/api/products", headers=admin_headers, json={
        "name": "Consulting", "product_type": "service", "default_rate": 100,
    }).json()
    r = client.post(
        f"/api/products/{p['id']}/adjust-stock",
        headers=admin_headers,
        json={"counted_qty": 5, "date": "2026-06-14"},
    )
    assert r.status_code == 400


def test_adjust_stock_not_found(client, admin_headers):
    r = client.post(
        "/api/products/99999/adjust-stock",
        headers=admin_headers,
        json={"counted_qty": 5, "date": "2026-06-14"},
    )
    assert r.status_code == 404
