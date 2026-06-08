"""Manual New-Entry can set the transaction's voucher_type (#52 §4)."""


def _accts(client, h):
    a = client.post("/api/accounts", headers=h, json={"code": "9610", "name": "Cash X", "type": "Asset"}).json()
    b = client.post("/api/accounts", headers=h, json={"code": "9620", "name": "Capital X", "type": "Equity"}).json()
    return a["id"], b["id"]


def test_manual_entry_honors_voucher_type(client, admin_headers):
    h = admin_headers
    dr, cr = _accts(client, h)
    r = client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01", "description": "cash receipt",
        "voucher_type": "CR",
        "entries": [
            {"account_id": dr, "debit": 100, "credit": 0},
            {"account_id": cr, "debit": 0, "credit": 100},
        ],
    })
    assert r.status_code in (200, 201), r.text
    tid = r.json()["id"]
    got = client.get("/api/reports/journal?limit=50", headers=h).json()
    row = next(x for x in got["items"] if x["transaction_id"] == tid)
    assert row["voucher_type"] == "CR", f"expected CR, got {row['voucher_type']}"


def test_manual_entry_defaults_to_jv_when_omitted(client, admin_headers):
    h = admin_headers
    dr, cr = _accts(client, h)
    r = client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01", "description": "adjustment",
        "entries": [
            {"account_id": dr, "debit": 50, "credit": 0},
            {"account_id": cr, "debit": 0, "credit": 50},
        ],
    })
    assert r.status_code in (200, 201), r.text
    tid = r.json()["id"]
    got = client.get("/api/reports/journal?limit=50", headers=h).json()
    row = next(x for x in got["items"] if x["transaction_id"] == tid)
    assert row["voucher_type"] == "JV"
