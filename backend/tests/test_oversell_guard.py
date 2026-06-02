"""Tests for the block_negative_stock over-sell guard (C2)."""
from sqlmodel import Session, select

import db as _db_module
from models import Product


def _make_stock_product(client, h, on_hand):
    """Create a stock-type product and set its on-hand qty directly in the DB."""
    p = client.post("/api/products", headers=h, json={
        "name": "Widget", "product_type": "stock", "default_rate": 10
    }).json()
    with Session(_db_module.engine) as s:
        prod = s.exec(select(Product).where(Product.id == p["id"])).first()
        prod.stock_qty = on_hand
        s.add(prod)
        s.commit()
    return p


def test_oversell_blocked_when_setting_on(client, admin_headers):
    h = admin_headers
    # Enable the guard
    client.patch("/api/settings", headers=h, json={"block_negative_stock": "true"})
    p = _make_stock_product(client, h, on_hand=5)
    # Attempt to sell 9 when only 5 on hand
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme",
        "issue_date": "2026-03-01",
        "due_date": "2026-03-31",
        "lines": [
            {
                "product_id": p["id"],
                "description": "Widget",
                "qty": 9,
                "rate": 10,
            }
        ],
    })
    assert r.status_code == 400, r.text
    assert "stock" in r.json()["detail"].lower()
    # Stock must be unchanged — no partial write; read directly from DB
    with Session(_db_module.engine) as s:
        prod = s.exec(select(Product).where(Product.id == p["id"])).first()
        assert float(prod.stock_qty) == 5.0, f"Expected 5.0, got {prod.stock_qty}"


def test_oversell_allowed_when_setting_off(client, admin_headers):
    h = admin_headers
    # Disable the guard (default behaviour)
    client.patch("/api/settings", headers=h, json={"block_negative_stock": "false"})
    p = _make_stock_product(client, h, on_hand=5)
    # Selling 9 when only 5 on hand should succeed (warn-only mode)
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme",
        "issue_date": "2026-03-01",
        "due_date": "2026-03-31",
        "lines": [
            {
                "product_id": p["id"],
                "description": "Widget",
                "qty": 9,
                "rate": 10,
            }
        ],
    })
    assert r.status_code in (200, 201), r.text
