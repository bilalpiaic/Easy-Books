"""Customers / vendors list return live closing balances (not setup opening)."""
from decimal import Decimal

from fastapi.testclient import TestClient


def test_customer_list_closing_balance(client: TestClient, admin_headers):
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={
        "name": "Closing Cust", "opening_balance": 100,
    }).json()
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"],
        "issue_date": "2026-06-01",
        "gst_rate": 0,
        "lines": [{"description": "Svc", "qty": 1, "rate": 250}],
    })
    assert inv.status_code in (200, 201), inv.text

    r = client.get("/api/customers?search=Closing Cust", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "closing_balance_total" in data
    row = next(i for i in data["items"] if i["id"] == c["id"])
    assert Decimal(str(row["opening_balance"])) == Decimal("100")
    assert Decimal(str(row["closing_balance"])) == Decimal("350")
    assert Decimal(str(data["closing_balance_total"])) >= Decimal("350")


def test_vendor_list_closing_balance(client: TestClient, admin_headers):
    h = admin_headers
    v = client.post("/api/vendors", headers=h, json={
        "name": "Closing Vend", "opening_balance": 50,
    }).json()
    bill = client.post("/api/bills", headers=h, json={
        "vendor_id": v["id"],
        "bill_date": "2026-06-01",
        "gst_rate": 0,
        "lines": [{"description": "Parts", "qty": 1, "rate": 200}],
    })
    assert bill.status_code in (200, 201), bill.text

    r = client.get("/api/vendors?search=Closing Vend", headers=h)
    assert r.status_code == 200
    data = r.json()
    row = next(i for i in data["items"] if i["id"] == v["id"])
    assert Decimal(str(row["opening_balance"])) == Decimal("50")
    assert Decimal(str(row["closing_balance"])) == Decimal("250")
    assert Decimal(str(data["closing_balance_total"])) >= Decimal("250")
