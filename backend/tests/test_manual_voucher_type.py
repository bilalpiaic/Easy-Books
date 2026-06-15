"""Manual New-Entry can set the transaction's voucher_type (#52 §4).

JV, CO, CP, CR, BP, BR are all accepted as manual GL postings.
Document-backed types (SL, PR, CN, DN, SR, PV) are rejected — they must
only originate from their dedicated routers.
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


def test_manual_entry_rejects_document_backed_voucher_types(client, admin_headers):
    """Document-backed types must be rejected — they must originate from dedicated routers."""
    h = admin_headers
    dr, cr = _accts(client, h)
    for vt in ("SL", "SR", "PR", "PV", "CN", "DN"):
        r = client.post("/api/transactions", headers=h, json={
            "date": "2026-04-01", "description": "should fail",
            "voucher_type": vt,
            "entries": [
                {"account_id": dr, "debit": 10, "credit": 0},
                {"account_id": cr, "debit": 0, "credit": 10},
            ],
        })
        assert r.status_code == 400, f"expected 400 for {vt}, got {r.status_code}: {r.text}"


def test_manual_entry_accepts_cash_bank_voucher_types(client, admin_headers):
    """CP/CR/BP/BR are pure GL postings and must be accepted like JV."""
    h = admin_headers
    dr, cr = _accts(client, h)
    for vt in ("CP", "CR", "BP", "BR"):
        r = client.post("/api/transactions", headers=h, json={
            "date": "2026-04-01", "description": f"{vt} posting",
            "voucher_type": vt,
            "entries": [
                {"account_id": dr, "debit": 10, "credit": 0},
                {"account_id": cr, "debit": 0, "credit": 10},
            ],
        })
        assert r.status_code == 200, f"expected 200 for {vt}, got {r.status_code}: {r.text}"


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
