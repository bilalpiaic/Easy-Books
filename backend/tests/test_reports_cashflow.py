"""B3 — cash-flow reconciliation tie-out.

The statement must always satisfy:
    net_cash_change + unclassified == ending_balance - beginning_balance
where unclassified = (ending - beginning) - net_cash_change surfaces any cash
movement the operating/investing/financing classifier didn't bucket.

Default CoA (`_COA_COMMON`) accounts used:
  1000 Cash in Hand (a cash account)
  4000 Sales Revenue (classifiable → operating, via net income)
  1260 Advances to Vendors (Asset, name has "advance" → excluded from investing,
        not AR/revenue/financing → UNBUCKETED, creates an unclassified gap)
"""

PERIOD = "start=2026-01-01&end=2026-12-31"


def _post_jv(client, headers, date, debit_code, credit_code, amount):
    accts = client.get("/api/accounts?limit=500", headers=headers).json()["items"]
    by_code = {a["code"]: a["id"] for a in accts}
    r = client.post("/api/transactions", headers=headers, json={
        "date": date, "description": "cf-tieout test",
        "entries": [
            {"account_id": by_code[debit_code], "debit": amount, "credit": 0},
            {"account_id": by_code[credit_code], "debit": 0, "credit": amount},
        ],
    })
    assert r.status_code in (200, 201), r.text


def test_cashflow_clean_data_zero_unclassified(client, admin_headers):
    # Cash sale: Dr Cash / Cr Sales Revenue → fully classified (operating).
    _post_jv(client, admin_headers, "2026-03-15", "1000", "4000", 100)
    body = client.get(f"/api/reports/cash-flow?{PERIOD}", headers=admin_headers).json()
    assert "unclassified" in body
    assert abs(float(body["unclassified"])) < 0.005


def test_cashflow_unclassified_gap(client, admin_headers):
    # Dr Cash / Cr Advances to Vendors → cash moves against an unbucketed account.
    _post_jv(client, admin_headers, "2026-03-15", "1000", "1260", 100)
    body = client.get(f"/api/reports/cash-flow?{PERIOD}", headers=admin_headers).json()
    unclassified = float(body["unclassified"])
    assert abs(unclassified) > 0.005  # a real gap was surfaced
    # invariant still holds
    nc = float(body["net_cash_change"])
    beg = float(body["beginning_balance"])
    end = float(body["ending_balance"])
    assert abs((nc + unclassified) - (end - beg)) < 0.005


def test_cashflow_tieout_invariant_with_compare(client, admin_headers):
    # Mixed activity across two periods; invariant must hold on BOTH sides.
    _post_jv(client, admin_headers, "2026-02-10", "1000", "4000", 250)   # classified
    _post_jv(client, admin_headers, "2026-05-10", "1000", "1260", 70)    # unclassified
    body = client.get(
        "/api/reports/cash-flow?start=2026-04-01&end=2026-06-30"
        "&compare_start=2026-01-01&compare_end=2026-03-31",
        headers=admin_headers,
    ).json()
    assert "current" in body and "comparison" in body
    for side in (body["current"], body["comparison"]):
        nc = float(side["net_cash_change"])
        unc = float(side["unclassified"])
        beg = float(side["beginning_balance"])
        end = float(side["ending_balance"])
        assert abs((nc + unc) - (end - beg)) < 0.005
