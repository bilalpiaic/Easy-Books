"""Manual New-Entry can set the transaction's voucher_type (#52 §4).

Note: as of #80 §1, only JV and CO are permitted via the manual journal entry
form. Dedicated document endpoints (invoices, bills, payments, etc.) continue
to assign their own voucher types internally.
"""


def _accts(client, h):
    a = client.post("/api/accounts", headers=h, json={"code": "9610", "name": "Cash X", "type": "Asset"}).json()
    b = client.post("/api/accounts", headers=h, json={"code": "9620", "name": "Capital X", "type": "Equity"}).json()
    return a["id"], b["id"]


def test_manual_entry_honors_co_voucher_type(client, admin_headers):
    """CO (correction/opening) is one of the two permitted manual voucher types."""
    h = admin_headers
    dr, cr = _accts(client, h)
    r = client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01", "description": "opening entry",
        "voucher_type": "CO",
        "entries": [
            {"account_id": dr, "debit": 100, "credit": 0},
            {"account_id": cr, "debit": 0, "credit": 100},
        ],
    })
    assert r.status_code in (200, 201), r.text
    tid = r.json()["id"]
    got = client.get("/api/reports/journal?limit=50", headers=h).json()
    row = next(x for x in got["items"] if x["transaction_id"] == tid)
    assert row["voucher_type"] == "CO", f"expected CO, got {row['voucher_type']}"


def test_manual_entry_rejects_dedicated_voucher_types(client, admin_headers):
    """Dedicated voucher types (CR, CP, SL, etc.) must be rejected with 400."""
    h = admin_headers
    dr, cr = _accts(client, h)
    for vt in ("CR", "CP", "SL", "SR", "PR", "PV", "CN", "DN", "BP", "BR"):
        r = client.post("/api/transactions", headers=h, json={
            "date": "2026-04-01", "description": "should fail",
            "voucher_type": vt,
            "entries": [
                {"account_id": dr, "debit": 10, "credit": 0},
                {"account_id": cr, "debit": 0, "credit": 10},
            ],
        })
        assert r.status_code == 400, f"expected 400 for {vt}, got {r.status_code}: {r.text}"


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
