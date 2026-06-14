"""Customer account statement endpoint: opening balance, invoices, payments, closing balance."""
from decimal import Decimal


def _post_invoice(client, headers, customer_id, date, amount):
    return client.post("/api/invoices", headers=headers, json={
        "customer_id": customer_id,
        "issue_date": date,
        "gst_rate": 0,
        "lines": [{"description": "Service", "qty": 1, "rate": float(amount)}],
    }).json()


def _post_payment(client, headers, invoice_id, amount, date):
    r = client.post("/api/payments-received", headers=headers, json={
        "invoice_id": invoice_id,
        "payment_date": date,
        "amount": float(amount),
        "method": "bank",
        "reference": f"PAY-{invoice_id}",
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_statement_basic(client, admin_headers):
    """Opening + closing balance calculation with one pre-period invoice and one in-period."""
    h = admin_headers
    cust = client.post("/api/customers", headers=h, json={"name": "Bilal Corp", "opening_balance": 500}).json()
    cid = cust["id"]

    # Pre-period invoice (fully unpaid)
    inv_pre = _post_invoice(client, h, cid, "2026-01-15", 1000)

    # In-period invoice
    inv_period = _post_invoice(client, h, cid, "2026-03-05", 600)

    # Payment in period against pre-period invoice
    _post_payment(client, h, inv_pre["id"], 400, "2026-03-10")

    r = client.get(
        f"/api/customers/{cid}/statement?from_date=2026-03-01&to_date=2026-03-31",
        headers=h,
    )
    assert r.status_code == 200
    data = r.json()

    # Opening = 500 (opening_balance) + 1000 (pre-period invoice) - 0 (no pre-period payments) = 1500
    assert Decimal(data["opening_balance"]) == Decimal("1500")

    # One in-period invoice
    assert len(data["invoices"]) == 1
    assert data["invoices"][0]["number"] == inv_period["number"]
    assert Decimal(data["invoices"][0]["total"]) == Decimal("600")
    # No allocations against it yet
    assert Decimal(data["invoices"][0]["outstanding"]) == Decimal("600")

    # One payment of 400 in period
    assert len(data["payments"]) == 1
    assert Decimal(data["payments"][0]["amount"]) == Decimal("400")

    # Closing = 1500 + 600 - 400 = 1700
    assert Decimal(data["closing_balance"]) == Decimal("1700")


def test_statement_fully_paid_invoice(client, admin_headers):
    """A fully paid in-period invoice shows outstanding = 0."""
    h = admin_headers
    cust = client.post("/api/customers", headers=h, json={"name": "PaidCo"}).json()
    cid = cust["id"]

    inv = _post_invoice(client, h, cid, "2026-04-10", 300)
    _post_payment(client, h, inv["id"], 300, "2026-04-15")

    r = client.get(
        f"/api/customers/{cid}/statement?from_date=2026-04-01&to_date=2026-04-30",
        headers=h,
    )
    assert r.status_code == 200
    data = r.json()

    assert Decimal(data["invoices"][0]["outstanding"]) == Decimal("0")
    assert Decimal(data["closing_balance"]) == Decimal("0")


def test_statement_empty_period(client, admin_headers):
    """Period with no transactions returns opening = closing."""
    h = admin_headers
    cust = client.post("/api/customers", headers=h, json={"name": "QuietCo", "opening_balance": 250}).json()
    cid = cust["id"]

    r = client.get(
        f"/api/customers/{cid}/statement?from_date=2030-01-01&to_date=2030-01-31",
        headers=h,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["invoices"] == []
    assert data["payments"] == []
    assert Decimal(data["opening_balance"]) == Decimal("250")
    assert Decimal(data["closing_balance"]) == Decimal("250")


def test_statement_404_unknown_customer(client, admin_headers):
    r = client.get("/api/customers/999999/statement?from_date=2026-01-01&to_date=2026-01-31", headers=admin_headers)
    assert r.status_code == 404
