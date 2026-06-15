"""§3 — create_asset with funding_account_id posts an IAS 16 acquisition GL entry."""
import pytest
from fastapi.testclient import TestClient


def _postable_asset_accounts(client: TestClient, headers: dict) -> list:
    r = client.get("/api/accounts?limit=500", headers=headers)
    assert r.status_code == 200, r.text
    return [
        a for a in r.json()["items"]
        if not a.get("is_group") and not a.get("is_memo") and a.get("type") == "Asset"
    ]


def test_asset_without_funding_account_has_no_acquisition_txn(client, admin_headers):
    accounts = _postable_asset_accounts(client, admin_headers)
    if len(accounts) < 1:
        pytest.skip("Not enough Asset accounts in CoA")
    a = accounts[0]
    payload = {
        "name": "Test Machine No GL",
        "asset_account_id": a["id"],
        "accum_depr_account_id": a["id"],
        "depr_expense_account_id": a["id"],
        "acquisition_date": "2026-01-01",
        "acquisition_cost": "10000.00",
        "useful_life_months": 60,
    }
    r = client.post("/api/assets", json=payload, headers=admin_headers)
    assert r.status_code in (200, 201), r.text
    assert r.json().get("acquisition_transaction_id") is None


def test_asset_with_funding_account_posts_acquisition_jv(client, admin_headers):
    accounts = _postable_asset_accounts(client, admin_headers)
    if len(accounts) < 2:
        pytest.skip("Need at least 2 Asset accounts in CoA")
    asset_acc = accounts[0]
    funding_acc = accounts[1]

    payload = {
        "name": "Test Machine With GL",
        "asset_account_id": asset_acc["id"],
        "accum_depr_account_id": asset_acc["id"],
        "depr_expense_account_id": asset_acc["id"],
        "acquisition_date": "2026-01-01",
        "acquisition_cost": "15000.00",
        "useful_life_months": 60,
        "funding_account_id": funding_acc["id"],
    }
    r = client.post("/api/assets", json=payload, headers=admin_headers)
    assert r.status_code in (200, 201), r.text
    asset = r.json()
    assert asset.get("acquisition_transaction_id") is not None, \
        f"acquisition_transaction_id should be set. asset={asset}"

    txn_id = asset["acquisition_transaction_id"]
    txn_r = client.get(f"/api/transactions/{txn_id}", headers=admin_headers)
    assert txn_r.status_code == 200, txn_r.text
    entries = txn_r.json()["entries"]
    total_debit = sum(e.get("debit", 0) for e in entries)
    total_credit = sum(e.get("credit", 0) for e in entries)
    assert abs(total_debit - 15000.0) < 0.01, f"Expected debit 15000, got {total_debit}"
    assert abs(total_credit - 15000.0) < 0.01, f"Expected credit 15000, got {total_credit}"
