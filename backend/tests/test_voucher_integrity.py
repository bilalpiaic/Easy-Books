"""§1 — create_transaction must reject document-backed voucher types (SL/PR/CN/DN/SR/PV).

JV, CO, CP, CR, BP, BR are all valid manual GL postings and must be accepted.
"""


def _accts(client, h):
    a = client.post("/api/accounts", headers=h, json={"code": "9710", "name": "Cash VI", "type": "Asset"}).json()
    b = client.post("/api/accounts", headers=h, json={"code": "9720", "name": "Capital VI", "type": "Equity"}).json()
    return a["id"], b["id"]


def _payload(voucher_type: str, dr: int, cr: int) -> dict:
    return {
        "date": "2026-01-01",
        "description": "test",
        "voucher_type": voucher_type,
        "entries": [
            {"account_id": dr, "debit": 100, "credit": 0},
            {"account_id": cr, "debit": 0, "credit": 100},
        ],
    }


def test_jv_accepted(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("JV", dr, cr))
    assert r.status_code == 200, r.text


def test_co_accepted(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("CO", dr, cr))
    assert r.status_code == 200, r.text


def test_sl_rejected(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("SL", dr, cr))
    assert r.status_code == 400, r.text


def test_sr_rejected(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("SR", dr, cr))
    assert r.status_code == 400, r.text


def test_pr_rejected(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("PR", dr, cr))
    assert r.status_code == 400, r.text


def test_cn_rejected(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("CN", dr, cr))
    assert r.status_code == 400, r.text


def test_dn_rejected(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("DN", dr, cr))
    assert r.status_code == 400, r.text


def test_pv_rejected(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("PV", dr, cr))
    assert r.status_code == 400, r.text


def test_cp_accepted(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("CP", dr, cr))
    assert r.status_code == 200, r.text


def test_cr_accepted(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("CR", dr, cr))
    assert r.status_code == 200, r.text


def test_bp_accepted(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("BP", dr, cr))
    assert r.status_code == 200, r.text


def test_br_accepted(client, admin_headers):
    dr, cr = _accts(client, admin_headers)
    r = client.post("/api/transactions", headers=admin_headers, json=_payload("BR", dr, cr))
    assert r.status_code == 200, r.text
