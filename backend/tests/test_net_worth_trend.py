"""Tests for GET /api/reports/dashboard/net-worth (#130)."""


def _post_jv(client, headers, date, entries):
    accts = client.get("/api/accounts?limit=500", headers=headers).json()["items"]
    by_code = {a["code"]: a["id"] for a in accts}
    r = client.post("/api/transactions", headers=headers, json={
        "date": date, "description": "net-worth test",
        "entries": [
            {"account_id": by_code[code], "debit": debit, "credit": credit}
            for code, debit, credit in entries
        ],
    })
    assert r.status_code in (200, 201), r.text


def _series(client, headers, months=36):
    r = client.get(f"/api/reports/dashboard/net-worth?months={months}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["series"]


def test_empty_tenant_returns_empty_series(client, admin_headers):
    assert _series(client, admin_headers) == []


def test_single_jv_balances(client, admin_headers):
    # Dr Cash 1000 / Cr Accounts Payable 400 / Cr Owner Capital 600
    _post_jv(client, admin_headers, "2026-05-15", [
        ("1000", 1000, 0), ("2000", 0, 400), ("3000", 0, 600),
    ])
    series = _series(client, admin_headers)
    last = series[-1]
    assert float(last["assets"]) == 1000.0
    assert float(last["liabilities"]) == 400.0
    assert float(last["net_worth"]) == 600.0


def test_cumulative_carry_forward_through_gap_months(client, admin_headers):
    _post_jv(client, admin_headers, "2026-01-15", [("1000", 500, 0), ("3000", 0, 500)])
    _post_jv(client, admin_headers, "2026-03-10", [("1000", 200, 0), ("2000", 0, 200)])
    by_month = {p["month"]: p for p in _series(client, admin_headers)}
    # gap month carries January's balances forward
    assert float(by_month["2026-02"]["assets"]) == 500.0
    assert float(by_month["2026-02"]["liabilities"]) == 0.0
    # March adds on top of the cumulative balance
    assert float(by_month["2026-03"]["assets"]) == 700.0
    assert float(by_month["2026-03"]["liabilities"]) == 200.0
    assert float(by_month["2026-03"]["net_worth"]) == 500.0
    # series extends to the current month with the same closing balances
    assert float(_series(client, admin_headers)[-1]["net_worth"]) == 500.0


def test_months_param_limits_window(client, admin_headers):
    _post_jv(client, admin_headers, "2025-01-15", [("1000", 100, 0), ("3000", 0, 100)])
    assert len(_series(client, admin_headers, months=3)) == 3


def test_tenant_isolation(client, admin_headers):
    _post_jv(client, admin_headers, "2026-04-15", [("1000", 900, 0), ("3000", 0, 900)])
    r = client.post("/api/auth/signup", json={
        "email": "other@tenant.test", "password": "pw12345678",
        "full_name": "Other", "company_name": "OtherCo",
    })
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login", data={
        "username": "other@tenant.test", "password": "pw12345678",
    }).json()["access_token"]
    client.cookies.clear()
    other = {"Authorization": f"Bearer {tok}"}
    assert _series(client, other) == []
