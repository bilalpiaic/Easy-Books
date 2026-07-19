"""Tests for GET /api/reports/dashboard/trends (dashboard trend widgets)."""
from datetime import date


def _by_code(client, headers):
    accts = client.get("/api/accounts?limit=500", headers=headers).json()["items"]
    return {a["code"]: a["id"] for a in accts}


def _post_jv(client, headers, jv_date, entries):
    by_code = _by_code(client, headers)
    r = client.post("/api/transactions", headers=headers, json={
        "date": jv_date, "description": "trends test",
        "entries": [
            {"account_id": by_code[code], "debit": debit, "credit": credit}
            for code, debit, credit in entries
        ],
    })
    assert r.status_code in (200, 201), r.text


def _trends(client, headers, months=12):
    r = client.get(f"/api/reports/dashboard/trends?months={months}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _this_month():
    return date.today().strftime("%Y-%m")


def test_empty_tenant_shapes(client, admin_headers):
    t = _trends(client, admin_headers, months=6)
    assert len(t["months"]) == 6
    assert t["months"][-1] == _this_month()
    for key in ("inflow", "outflow", "net"):
        assert len(t["cashflow"][key]) == 6
        assert all(float(v) == 0 for v in t["cashflow"][key])
    assert len(t["cash_balance"]) == 6
    assert len(t["sales_purchases"]["sales"]) == 6
    assert len(t["collections"]) == 6
    assert t["expense_trend"] == {"accounts": [], "series": []}
    assert t["revenue_breakdown"] == []
    assert t["top_vendors"] == []
    assert t["invoice_status"] == []
    assert all(float(v) == 0 for v in t["ap_aging"].values())


def test_cashflow_and_balance(client, admin_headers):
    today = date.today()
    d = today.strftime("%Y-%m-15")
    # Dr Cash 1000 / Cr Owner Capital 1000, then Dr Rent 300 / Cr Cash 300
    _post_jv(client, admin_headers, d, [("1000", 1000, 0), ("3000", 0, 1000)])
    _post_jv(client, admin_headers, d, [("5100", 300, 0), ("1000", 0, 300)])
    t = _trends(client, admin_headers, months=3)
    assert float(t["cashflow"]["inflow"][-1]) == 1000.0
    assert float(t["cashflow"]["outflow"][-1]) == 300.0
    assert float(t["cashflow"]["net"][-1]) == 700.0
    assert float(t["cash_balance"][-1]) == 700.0


def test_cash_balance_carries_opening_from_before_window(client, admin_headers):
    # Activity 2 years back stays out of the window but seeds the opening balance
    old = date(date.today().year - 2, 6, 15).isoformat()
    _post_jv(client, admin_headers, old, [("1000", 500, 0), ("3000", 0, 500)])
    t = _trends(client, admin_headers, months=3)
    assert all(float(v) == 0 for v in t["cashflow"]["inflow"])
    assert float(t["cash_balance"][0]) == 500.0
    assert float(t["cash_balance"][-1]) == 500.0


def test_expense_trend_and_revenue_breakdown(client, admin_headers):
    d = date.today().strftime("%Y-%m-10")
    _post_jv(client, admin_headers, d, [("5100", 250, 0), ("1000", 0, 250)])
    _post_jv(client, admin_headers, d, [("1000", 900, 0), ("4000", 0, 900)])
    t = _trends(client, admin_headers, months=3)
    assert len(t["expense_trend"]["accounts"]) >= 1
    idx = 0  # top expense account is the only one posted
    assert float(t["expense_trend"]["series"][idx][-1]) == 250.0
    assert len(t["revenue_breakdown"]) == 1
    assert float(t["revenue_breakdown"][0]["amount"]) == 900.0


def test_sales_purchases_status_and_ap_aging(client, admin_headers):
    from decimal import Decimal

    from sqlmodel import Session

    import db as _db_module
    from models import Bill, Customer, Invoice, Vendor

    h = admin_headers
    cust = client.post("/api/customers", headers=h, json={"name": "Trend Cust"}).json()
    vend = client.post("/api/vendors", headers=h, json={"name": "Trend Vendor"}).json()

    today = date.today()
    d = today.strftime("%Y-%m-05")
    with Session(_db_module.engine) as s:
        tid = s.get(Customer, cust["id"]).tenant_id
        s.add(Invoice(
            tenant_id=tid, number="INV-T-001", customer_id=cust["id"],
            issue_date=d, due_date=d,
            subtotal=Decimal(400), gst_amount=Decimal(0),
            total=Decimal(400), status="sent",
        ))
        s.add(Invoice(
            tenant_id=tid, number="INV-T-002", customer_id=cust["id"],
            issue_date=d, due_date=d,
            subtotal=Decimal(100), gst_amount=Decimal(0),
            total=Decimal(100), status="void",   # excluded from sales
        ))
        s.add(Bill(
            tenant_id=tid, number="BILL-T-001", vendor_id=vend["id"],
            bill_date=d, due_date=(today.replace(day=1)).isoformat(),
            subtotal=Decimal(150), gst_amount=Decimal(0),
            total=Decimal(150), status="received",
        ))
        s.commit()
        assert s.get(Vendor, vend["id"]).tenant_id == tid

    t = _trends(client, h, months=3)
    assert float(t["sales_purchases"]["sales"][-1]) == 400.0
    assert float(t["sales_purchases"]["purchases"][-1]) == 150.0
    assert t["top_vendors"][0]["name"] == "Trend Vendor"
    assert float(t["top_vendors"][0]["total"]) == 150.0
    statuses = {row["status"]: row for row in t["invoice_status"]}
    assert statuses["sent"]["count"] == 1
    assert float(statuses["sent"]["amount"]) == 400.0
    # the unpaid bill lands in an AP aging bucket
    assert sum(float(v) for v in t["ap_aging"].values()) == 150.0


def test_ar_ap_trend_balances(client, admin_headers):
    d = date.today().strftime("%Y-%m-08")
    # Dr AR 600 / Cr Revenue 600, then Dr Expense 200 / Cr AP 200
    _post_jv(client, admin_headers, d, [("1100", 600, 0), ("4000", 0, 600)])
    _post_jv(client, admin_headers, d, [("5100", 200, 0), ("2000", 0, 200)])
    t = _trends(client, admin_headers, months=3)
    trend = t["ar_ap_trend"]
    assert len(trend["months"]) == 36
    assert trend["months"][-1] == _this_month()
    assert float(trend["ar"][-1]) == 600.0
    assert float(trend["ap"][-1]) == 200.0
    assert float(trend["ar"][0]) == 0.0


def test_day_book_summary(client, admin_headers):
    d = date.today().isoformat()
    _post_jv(client, admin_headers, d, [("1000", 500, 0), ("3000", 0, 500)])
    r = client.post("/api/customers", headers=admin_headers, json={"name": "DayBook Cust"})
    assert r.status_code in (200, 201)

    r = client.get(f"/api/reports/dashboard/day-book?date={d}", headers=admin_headers)
    assert r.status_code == 200, r.text
    book = r.json()
    assert book["date"] == d
    assert book["voucher_totals"]["count"] >= 1
    total_by_type = {v["type"]: v for v in book["vouchers"]}
    assert float(total_by_type["JV"]["total"]) >= 500.0
    for key in ("invoices", "bills", "payments_received", "payments_made"):
        assert "count" in book["documents"][key]
    # customer creation shows up in the non-financial category view
    categories = {a["category"] for a in book["activity"]}
    assert "customer" in categories


def test_day_book_rejects_bad_date(client, admin_headers):
    r = client.get("/api/reports/dashboard/day-book?date=nonsense", headers=admin_headers)
    assert r.status_code == 400


def test_months_param_clamped(client, admin_headers):
    assert len(_trends(client, admin_headers, months=999)["months"]) == 36
    assert len(_trends(client, admin_headers, months=0)["months"]) == 1


def test_tenant_isolation(client, admin_headers):
    d = date.today().strftime("%Y-%m-12")
    _post_jv(client, admin_headers, d, [("1000", 800, 0), ("3000", 0, 800)])
    r = client.post("/api/auth/signup", json={
        "email": "trends-other@tenant.test", "password": "pw12345678",
        "full_name": "Other", "company_name": "OtherCo",
    })
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login", data={
        "username": "trends-other@tenant.test", "password": "pw12345678",
    }).json()["access_token"]
    client.cookies.clear()
    other = {"Authorization": f"Bearer {tok}"}
    t = _trends(client, other, months=3)
    assert all(float(v) == 0 for v in t["cashflow"]["inflow"])
    assert float(t["cash_balance"][-1]) == 0.0
