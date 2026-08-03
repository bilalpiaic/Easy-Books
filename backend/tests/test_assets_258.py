"""#258 — fixed-asset depth: components, impairment, disposal."""
import pytest
from fastapi.testclient import TestClient


def _postable_accounts(client: TestClient, headers: dict, acct_type: str = "Asset") -> list:
    r = client.get("/api/accounts?limit=500", headers=headers)
    assert r.status_code == 200, r.text
    return [
        a for a in r.json()["items"]
        if not a.get("is_group") and not a.get("is_memo") and a.get("type") == acct_type
    ]


def _pick_accounts(client: TestClient, headers: dict):
    assets = _postable_accounts(client, headers, "Asset")
    expenses = _postable_accounts(client, headers, "Expense")
    if len(assets) < 2 or not expenses:
        pytest.skip("Need Asset + Expense accounts in CoA")
    return {
        "asset": assets[0],
        "accum": assets[1] if len(assets) > 1 else assets[0],
        "funding": assets[1] if len(assets) > 1 else assets[0],
        "expense": expenses[0],
    }


def _create_asset(client, headers, accs, *, name, cost, life=60, parent_id=None, funding=True):
    payload = {
        "name": name,
        "asset_account_id": accs["asset"]["id"],
        "accum_depr_account_id": accs["accum"]["id"],
        "depr_expense_account_id": accs["expense"]["id"],
        "acquisition_date": "2026-01-01",
        "acquisition_cost": str(cost),
        "salvage_value": "0",
        "useful_life_months": life,
        "method": "straight_line",
    }
    if funding:
        payload["funding_account_id"] = accs["funding"]["id"]
    if parent_id is not None:
        payload["parent_id"] = parent_id
    r = client.post("/api/assets", json=payload, headers=headers)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_component_depreciation(client, admin_headers):
    accs = _pick_accounts(client, admin_headers)
    parent = _create_asset(
        client, admin_headers, accs, name="Line Parent", cost=0, life=1, funding=False
    )
    c1 = _create_asset(
        client, admin_headers, accs,
        name="Component A", cost=12000, life=12, parent_id=parent["id"],
    )
    c2 = _create_asset(
        client, admin_headers, accs,
        name="Component B", cost=24000, life=24, parent_id=parent["id"],
    )

    # Parent depreciate must 400
    r = client.post(
        f"/api/assets/{parent['id']}/depreciate",
        json={"depreciation_date": "2026-02-01"},
        headers=admin_headers,
    )
    assert r.status_code == 400, r.text

    r1 = client.post(
        f"/api/assets/{c1['id']}/depreciate",
        json={"depreciation_date": "2026-02-01"},
        headers=admin_headers,
    )
    assert r1.status_code == 200, r1.text
    r2 = client.post(
        f"/api/assets/{c2['id']}/depreciate",
        json={"depreciation_date": "2026-02-01"},
        headers=admin_headers,
    )
    assert r2.status_code == 200, r2.text

    # SL: (12000/12) + (24000/24) = 1000 + 1000 = 2000
    charge1 = float(r1.json()["depreciation_amount"])
    charge2 = float(r2.json()["depreciation_amount"])
    assert abs(charge1 - 1000.0) < 0.02, charge1
    assert abs(charge2 - 1000.0) < 0.02, charge2
    assert abs(charge1 + charge2 - 2000.0) < 0.02

    detail = client.get(f"/api/assets/{parent['id']}", headers=admin_headers)
    assert detail.status_code == 200
    comps = detail.json()["components"]
    assert len(comps) == 2


def test_impairment_posts_je(client, admin_headers):
    accs = _pick_accounts(client, admin_headers)
    asset = _create_asset(
        client, admin_headers, accs, name="Impair Me", cost=10000, life=60
    )
    assert asset.get("acquisition_transaction_id") is not None

    r = client.post(
        f"/api/assets/{asset['id']}/impair",
        json={
            "recoverable_amount": "7000.00",
            "impairment_date": "2026-03-15",
            "notes": "test impair",
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert abs(float(body["accum_impairment"]) - 3000.0) < 0.02
    assert abs(float(body["book_value"]) - 7000.0) < 0.02
    assert abs(float(body["nbv"]) - 7000.0) < 0.02

    imp = body["impairment"]
    assert abs(float(imp["amount"]) - 3000.0) < 0.02
    txn_id = imp["transaction_id"]
    txn_r = client.get(f"/api/transactions/{txn_id}", headers=admin_headers)
    assert txn_r.status_code == 200, txn_r.text
    entries = txn_r.json()["entries"]
    total_debit = sum(e.get("debit", 0) for e in entries)
    total_credit = sum(e.get("credit", 0) for e in entries)
    assert abs(total_debit - 3000.0) < 0.01
    assert abs(total_credit - 3000.0) < 0.01


def test_disposal_with_proceeds(client, admin_headers):
    accs = _pick_accounts(client, admin_headers)
    asset = _create_asset(
        client, admin_headers, accs, name="Dispose Me", cost=10000, life=10
    )
    # One month dep → charge 1000, NBV 9000
    r = client.post(
        f"/api/assets/{asset['id']}/depreciate",
        json={"depreciation_date": "2026-02-01"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    # Sell for 9500 → gain 500
    r = client.patch(
        f"/api/assets/{asset['id']}/dispose",
        json={
            "disposal_date": "2026-03-01",
            "proceeds": "9500.00",
            "proceeds_account_id": accs["funding"]["id"],
            "mode": "sale",
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_disposed"] is True
    assert abs(float(body["book_value"])) < 0.01
    assert abs(float(body["disposal_proceeds"]) - 9500.0) < 0.02
    assert body.get("disposal_transaction_id") is not None

    txn_r = client.get(
        f"/api/transactions/{body['disposal_transaction_id']}",
        headers=admin_headers,
    )
    assert txn_r.status_code == 200
    entries = txn_r.json()["entries"]
    total_debit = sum(e.get("debit", 0) for e in entries)
    total_credit = sum(e.get("credit", 0) for e in entries)
    assert abs(total_debit - total_credit) < 0.02
    # Dr accum 1000 + Dr bank 9500 = 10500; Cr asset 10000 + Cr gain 500
    assert abs(total_debit - 10500.0) < 0.05, total_debit
