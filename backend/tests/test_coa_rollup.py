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
