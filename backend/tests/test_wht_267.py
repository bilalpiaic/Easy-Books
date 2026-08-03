"""Withholding tax on bill payments + CIT worksheet (#267)."""
from __future__ import annotations

from decimal import Decimal

from services.money import D


def _make_wht_code(client, auth, *, code="WHT10", rate=10):
    accounts = client.get("/api/accounts?limit=500", headers=auth).json()["items"]
    gl = next((a["id"] for a in accounts if a["code"] == "2265"), None)
    if gl is None:
        gl = next(a["id"] for a in accounts if a["type"] == "Liability" and not a.get("is_group"))
    r = client.post(
        "/api/tax-codes",
        headers=auth,
        json={
            "code": code,
            "name": f"Withholding {rate}%",
            "rate": rate,
            "type": "input",
            "gl_account_id": gl,
            "is_withholding": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_bill_payment_wht_je_balances(client, admin_headers):
    auth = admin_headers
    wht_code = _make_wht_code(client, auth, rate=10)
    vendor = client.post(
        "/api/vendors",
        headers=auth,
        json={
            "name": "WHT Vendor Co",
            "wht_tax_code_id": wht_code["id"],
            "wht_rate": 10,
        },
    ).json()
    assert vendor["wht_rate"] == 10 or Decimal(str(vendor["wht_rate"])) == Decimal("10")

    bill = client.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "bill_date": "2026-03-01",
            "due_date": "2026-03-31",
            "gst_rate": 0,
            "lines": [{"description": "Services", "qty": 1, "rate": 1000}],
        },
    )
    assert bill.status_code == 201, bill.text
    bill = bill.json()

    pay = client.post(
        "/api/bill-payments",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "bill_id": bill["id"],
            "payment_date": "2026-03-15",
            "amount": 1000,
            "method": "bank_transfer",
            "allocations": [{"bill_id": bill["id"], "amount": 1000}],
        },
    )
    assert pay.status_code == 201, pay.text
    pay = pay.json()
    assert Decimal(str(pay["wht_amount"])) == Decimal("100")
    assert Decimal(str(pay["amount"])) == Decimal("1000")

    txn = client.get(f"/api/transactions/{pay['transaction_id']}", headers=auth)
    assert txn.status_code == 200, txn.text
    entries = txn.json()["entries"]
    total_dr = sum(Decimal(str(e["debit"])) for e in entries)
    total_cr = sum(Decimal(str(e["credit"])) for e in entries)
    assert total_dr == total_cr
    assert total_dr == Decimal("1000")

    accounts = {a["id"]: a for a in client.get("/api/accounts?limit=500", headers=auth).json()["items"]}
    by_code: dict[str, Decimal] = {}
    for e in entries:
        code = accounts[e["account_id"]]["code"]
        by_code[code] = by_code.get(code, Decimal("0")) + Decimal(str(e["debit"])) - Decimal(str(e["credit"]))

    # Dr AP 1000 → net +1000 on 2000; Cr Bank 900 → -900; Cr WHT 100 → -100
    assert by_code.get("2000", Decimal("0")) == Decimal("1000")
    assert by_code.get("2265", Decimal("0")) == Decimal("-100")
    cash_net = sum(by_code[c] for c in ("1000", "1010") if c in by_code)
    assert cash_net == Decimal("-900")


def test_wht_report_totals(client, admin_headers):
    auth = admin_headers
    wht_code = _make_wht_code(client, auth, code="WHT15", rate=15)
    vendor = client.post(
        "/api/vendors",
        headers=auth,
        json={"name": "Report Vendor", "wht_rate": 15, "wht_tax_code_id": wht_code["id"]},
    ).json()
    bill = client.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "bill_date": "2026-04-01",
            "due_date": "2026-04-30",
            "gst_rate": 0,
            "lines": [{"description": "Fees", "qty": 1, "rate": 2000}],
        },
    ).json()
    client.post(
        "/api/bill-payments",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "bill_id": bill["id"],
            "payment_date": "2026-04-10",
            "amount": 2000,
            "method": "cash",
            "allocations": [{"bill_id": bill["id"], "amount": 2000}],
        },
    )

    r = client.get("/api/reports/wht?start=2026-01-01&end=2026-12-31", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert Decimal(str(data["totals"]["wht"])) >= Decimal("300")
    row = next(i for i in data["items"] if i["vendor"] == "Report Vendor")
    assert Decimal(str(row["base"])) == Decimal("2000")
    assert Decimal(str(row["wht"])) == Decimal("300")
    assert row["payments"] == 1


def test_cit_worksheet_with_adjustments(client, admin_headers):
    auth = admin_headers
    # Seed a bit of P&L activity via a simple invoice (revenue)
    cust = client.post("/api/customers", headers=auth, json={"name": "CIT Cust"}).json()
    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-02-01",
            "due_date": "2026-02-28",
            "gst_rate": 0,
            "lines": [{"description": "Sale", "qty": 1, "rate": 5000}],
        },
    )
    assert inv.status_code == 201, inv.text

    adj = client.post(
        "/api/reports/cit-adjustments",
        headers=auth,
        json={
            "fiscal_year": "2026",
            "kind": "addback",
            "description": "Non-deductible fine",
            "amount": 200,
        },
    )
    assert adj.status_code == 201, adj.text

    ws = client.get(
        "/api/reports/cit-worksheet?start=2026-01-01&end=2026-12-31&fiscal_year=2026&tax_rate=29",
        headers=auth,
    )
    assert ws.status_code == 200, ws.text
    data = ws.json()
    assert Decimal(str(data["total_addbacks"])) == Decimal("200")
    assert Decimal(str(data["taxable_income"])) == Decimal(str(data["accounting_profit"])) + Decimal("200")
    assert D(data["estimated_tax"]) == D(
        max(Decimal("0"), Decimal(str(data["taxable_income"]))) * Decimal("29") / Decimal("100")
    )


def test_explicit_wht_amount_override(client, admin_headers):
    auth = admin_headers
    vendor = client.post(
        "/api/vendors",
        headers=auth,
        json={"name": "Override Vendor", "wht_rate": 10},
    ).json()
    bill = client.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "bill_date": "2026-05-01",
            "due_date": "2026-05-31",
            "gst_rate": 0,
            "lines": [{"description": "Work", "qty": 1, "rate": 500}],
        },
    ).json()
    pay = client.post(
        "/api/bill-payments",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "bill_id": bill["id"],
            "payment_date": "2026-05-10",
            "amount": 500,
            "wht_amount": 25,
            "method": "cash",
            "allocations": [{"bill_id": bill["id"], "amount": 500}],
        },
    ).json()
    assert Decimal(str(pay["wht_amount"])) == Decimal("25")
    txn = client.get(f"/api/transactions/{pay['transaction_id']}", headers=auth).json()
    total_dr = sum(Decimal(str(e["debit"])) for e in txn["entries"])
    total_cr = sum(Decimal(str(e["credit"])) for e in txn["entries"])
    assert total_dr == total_cr
