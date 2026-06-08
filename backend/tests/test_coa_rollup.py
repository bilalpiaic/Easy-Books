"""Integration tests for hierarchical TB / BS / P&L (#53 Phase 2)."""


def _acct(client, h, code, name, type="Asset", parent_id=None, is_group=False):
    r = client.post("/api/accounts", headers=h, json={
        "code": code, "name": name, "type": type,
        "parent_id": parent_id, "is_group": is_group,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _post(client, h, dr_id, cr_id, amt, date="2026-04-01"):
    r = client.post("/api/transactions", headers=h, json={
        "date": date, "description": "rollup test",
        "entries": [
            {"account_id": dr_id, "debit": amt, "credit": 0},
            {"account_id": cr_id, "debit": 0, "credit": amt},
        ],
    })
    assert r.status_code in (200, 201), r.text


def _find(nodes, code):
    for n in nodes:
        if n["code"] == code:
            return n
        hit = _find(n["children"], code)
        if hit:
            return hit
    return None


def test_trial_balance_returns_rolled_up_tree(client, admin_headers):
    h = admin_headers
    # NB: new tenants get a seeded CoA (signup → seed_data), so use high 9xxx
    # codes that won't collide with seeded accounts (matches existing tests).
    # group 9500 with two postable leaves; an Equity leaf to balance the JVs
    grp = _acct(client, h, "9500", "Current Assets", "Asset", is_group=True)
    cash = _acct(client, h, "9510", "Cash", "Asset", parent_id=grp["id"])
    bank = _acct(client, h, "9520", "Bank", "Asset", parent_id=grp["id"])
    cap = _acct(client, h, "9100", "Capital", "Equity")
    _post(client, h, cash["id"], cap["id"], 30)
    _post(client, h, bank["id"], cap["id"], 70)

    r = client.get("/api/reports/trial-balance?start=2026-01-01&end=2026-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "tree" in body and "totals" in body
    node = _find(body["tree"], "9500")
    assert node is not None and node["is_group"] is True
    assert float(node["debit"]) == 100.0            # 30 + 70 rolled up
    assert {c["code"] for c in node["children"]} == {"9510", "9520"}
    # grand totals still balance
    assert float(body["totals"]["debit"]) == float(body["totals"]["credit"])


def test_balance_sheet_single_period_is_tree_and_balances(client, admin_headers):
    h = admin_headers
    ag = _acct(client, h, "9500", "Current Assets", "Asset", is_group=True)
    cash = _acct(client, h, "9510", "Cash", "Asset", parent_id=ag["id"])
    cap = _acct(client, h, "9100", "Capital", "Equity")
    _post(client, h, cash["id"], cap["id"], 100)

    r = client.get("/api/reports/balance-sheet?date=2026-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(["assets", "liabilities", "equity", "totals"]).issubset(body)
    ag_node = _find(body["assets"], "9500")
    assert ag_node is not None and float(ag_node["balance"]) == 100.0
    assert float(_find(body["assets"], "9510")["balance"]) == 100.0
    # Assets == Liabilities + Equity
    assert float(body["totals"]["assets"]) == float(body["totals"]["liabilities"]) + float(body["totals"]["equity"])


def test_balance_sheet_comparison_mode_stays_flat(client, admin_headers):
    h = admin_headers
    cash = _acct(client, h, "9510", "Cash", "Asset")
    cap = _acct(client, h, "9100", "Capital", "Equity")
    _post(client, h, cash["id"], cap["id"], 100)
    r = client.get("/api/reports/balance-sheet?date=2026-12-31&compare_end=2025-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "current" in body and "comparison" in body      # unchanged flat shape
    assert isinstance(body["current"], list)


def test_income_statement_single_period_is_tree(client, admin_headers):
    h = admin_headers
    # Name must not collide with the seeded top-level "Revenue" group (code "4").
    rg = _acct(client, h, "9400", "Revenue Group (test)", "Revenue", is_group=True)
    sales = _acct(client, h, "9410", "Sales", "Revenue", parent_id=rg["id"])
    cash = _acct(client, h, "9510", "Cash", "Asset")
    exp = _acct(client, h, "9900", "Rent", "Expense")
    _post(client, h, cash["id"], sales["id"], 200)   # revenue 200
    _post(client, h, exp["id"], cash["id"], 50)      # expense 50

    r = client.get("/api/reports/income-statement?start=2026-01-01&end=2026-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(["revenue", "expenses", "totals"]).issubset(body)
    assert float(_find(body["revenue"], "9400")["amount"]) == 200.0   # rolled up
    assert float(body["totals"]["revenue"]) == 200.0
    assert float(body["totals"]["expenses"]) == 50.0
    assert float(body["totals"]["net_profit"]) == 150.0


def test_income_statement_comparison_mode_stays_flat(client, admin_headers):
    h = admin_headers
    sales = _acct(client, h, "9410", "Sales", "Revenue")
    cash = _acct(client, h, "9510", "Cash", "Asset")
    _post(client, h, cash["id"], sales["id"], 200)
    r = client.get("/api/reports/income-statement?start=2026-01-01&end=2026-12-31"
                   "&compare_start=2025-01-01&compare_end=2025-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "current" in body and "comparison" in body
    assert isinstance(body["current"], list)
