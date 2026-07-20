"""Numeric / amount search via GET /api/search."""
from decimal import Decimal

from fastapi.testclient import TestClient


def test_search_by_amount_finds_invoice_and_payment(client: TestClient, admin_headers):
    auth = admin_headers

    r = client.post(
        "/api/customers",
        headers=auth,
        json={"name": "Amount Seeker", "email": "amt@test"},
    )
    assert r.status_code == 201, r.text
    customer_id = r.json()["id"]

    # Invoice total = 100000 (no GST)
    r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": customer_id,
            "issue_date": "2026-07-01",
            "due_date": "2026-07-31",
            "description": "Large job",
            "gst_rate": 0,
            "lines": [{"description": "Bulk", "qty": 1, "rate": 100000}],
        },
    )
    assert r.status_code == 201, r.text
    invoice = r.json()
    assert Decimal(str(invoice["total"])) == Decimal("100000")

    r = client.post(
        "/api/payments-received",
        headers=auth,
        json={
            "invoice_id": invoice["id"],
            "customer_name": "Amount Seeker",
            "payment_date": "2026-07-02",
            "amount": 100000,
            "method": "bank",
            "reference": "WIRE-100K",
        },
    )
    assert r.status_code == 201, r.text
    payment = r.json()

    # Bare number
    r = client.get("/api/search?q=100000&limit=10", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    inv_ids = {row["id"] for row in data.get("invoices", [])}
    pay_ids = {row["id"] for row in data.get("payments_received", [])}
    assert invoice["id"] in inv_ids
    assert payment["id"] in pay_ids
    assert any(abs(float(row["amount"]) - 100000) < 0.02 for row in data["invoices"])

    # Comma-formatted amount
    r = client.get("/api/search?q=100,000&limit=10", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert invoice["id"] in {row["id"] for row in data.get("invoices", [])}

    # Amount-only types filter still works
    r = client.get(
        "/api/search?q=100000&types=invoices,payments_received&limit=10",
        headers=auth,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert invoice["id"] in {row["id"] for row in data.get("invoices", [])}
    assert "bills" not in data or data.get("bills") == []


def test_search_by_amount_finds_journal_line(client: TestClient, admin_headers):
    auth = admin_headers

    # Resolve cash + expense leaf accounts from CoA
    accounts = client.get("/api/accounts?limit=500", headers=auth).json()["items"]
    cash = next(a for a in accounts if a["type"] == "Asset" and not a.get("is_group")
                and "cash" in a["name"].lower())
    expense = next(a for a in accounts if a["type"] == "Expense" and not a.get("is_group"))

    r = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "date": "2026-07-03",
            "description": "Amount search JV",
            "voucher_type": "JV",
            "entries": [
                {"account_id": expense["id"], "debit": 55555.55, "credit": 0},
                {"account_id": cash["id"], "debit": 0, "credit": 55555.55},
            ],
        },
    )
    assert r.status_code in (200, 201), r.text
    txn = r.json()

    r = client.get("/api/search?q=55555.55&types=transactions&limit=10", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    ids = {row["id"] for row in data.get("transactions", [])}
    assert txn["id"] in ids
    match = next(row for row in data["transactions"] if row["id"] == txn["id"])
    assert match.get("amount") is not None
    assert abs(float(match["amount"]) - 55555.55) < 0.02
