"""Test that get_ledger correctly computes opening balance from entries
before the start date, so closing = opening + period movements."""


def _post_jv(client, headers, date, debit_code, credit_code, amount):
    """Post a balanced 2-line journal via the transactions API."""
    accts = client.get("/api/accounts?limit=500", headers=headers).json()["items"]
    by_code = {a["code"]: a["id"] for a in accts}
    r = client.post("/api/transactions", headers=headers, json={
        "date": date, "description": "test",
        "entries": [
            {"account_id": by_code[debit_code], "debit": amount, "credit": 0},
            {"account_id": by_code[credit_code], "debit": 0, "credit": amount},
        ],
    })
    assert r.status_code in (200, 201), r.text


def test_ledger_opening_plus_movements_equals_closing(client, admin_headers):
    h = admin_headers
    _post_jv(client, h, "2026-01-10", "1000", "3000", 100)   # before window
    _post_jv(client, h, "2026-03-15", "1000", "3000", 40)    # in window
    data = client.get(
        "/api/reports/ledger?start=2026-03-01&end=2026-03-31&account_code=1000",
        headers=h).json()
    acct = data["items"][0]
    assert float(acct["opening_balance"]) == 100.0
    assert float(acct["closing_balance"]) == 140.0
    assert float(acct["closing_balance"]) == float(acct["opening_balance"]) + 40.0
