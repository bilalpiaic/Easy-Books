"""#260 — mandatory analytic dimensions + dimensional P&L."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _postable(client: TestClient, headers: dict, acct_type: str) -> list:
    r = client.get("/api/accounts?limit=500", headers=headers)
    assert r.status_code == 200, r.text
    return [
        a for a in r.json()["items"]
        if not a.get("is_group") and not a.get("is_memo") and a.get("type") == acct_type
    ]


def _cash_and_revenue(client: TestClient, headers: dict):
    cash = _postable(client, headers, "Asset")
    rev = _postable(client, headers, "Revenue")
    if not cash or not rev:
        import pytest
        pytest.skip("Need Asset + Revenue accounts")
    return cash[0], rev[0]


def test_required_dimension_blocks_post(client: TestClient, admin_headers: dict):
    # Create a required dimension + value
    dim = client.post(
        "/api/analytic-dimensions",
        json={"code": "CC", "name": "Cost Center", "required": True, "sort_order": 0},
        headers=admin_headers,
    )
    assert dim.status_code == 201, dim.text
    dim_id = dim.json()["id"]

    aa = client.post(
        "/api/analytic-accounts",
        json={"code": "CC-01", "name": "Ops", "type": "cost_center", "dimension_id": dim_id},
        headers=admin_headers,
    )
    assert aa.status_code == 201, aa.text
    aa_id = aa.json()["id"]

    cash, rev = _cash_and_revenue(client, admin_headers)

    # Post without analytic → 400
    r = client.post(
        "/api/transactions",
        json={
            "date": "2026-06-15",
            "description": "untagged",
            "voucher_type": "JV",
            "entries": [
                {"account_id": cash["id"], "debit": 100, "credit": 0},
                {"account_id": rev["id"], "debit": 0, "credit": 100},
            ],
        },
        headers=admin_headers,
    )
    assert r.status_code == 400, r.text
    assert "required" in r.text.lower() or "Cost Center" in r.text or "CC" in r.text

    # Post with analytic → 201
    r2 = client.post(
        "/api/transactions",
        json={
            "date": "2026-06-15",
            "description": "tagged",
            "voucher_type": "JV",
            "analytic_account_id": aa_id,
            "entries": [
                {"account_id": cash["id"], "debit": 250, "credit": 0},
                {"account_id": rev["id"], "debit": 0, "credit": 250},
            ],
        },
        headers=admin_headers,
    )
    assert r2.status_code in (200, 201), r2.text
    txn = r2.json()
    txn_id = txn["id"] if isinstance(txn, dict) and "id" in txn else None
    if txn_id is None:
        # some routers return the transaction object directly
        detail = client.get(f"/api/transactions/{txn.get('id', txn)}", headers=admin_headers)
        assert detail.status_code == 200
        entries = detail.json()["entries"]
    else:
        detail = client.get(f"/api/transactions/{txn_id}", headers=admin_headers)
        assert detail.status_code == 200, detail.text
        entries = detail.json()["entries"]
    assert any(e.get("analytic_account_id") == aa_id for e in entries)

    # Dimensional P&L returns amounts for this analytic
    pl = client.get(
        f"/api/reports/dimensional-pl?analytic_id={aa_id}&start=2026-01-01&end=2026-12-31",
        headers=admin_headers,
    )
    assert pl.status_code == 200, pl.text
    body = pl.json()
    assert body["mode"] == "analytic"
    assert body["totals"]["revenue"] is not None
    # Revenue credit 250 → amount 250
    assert float(body["totals"]["revenue"]) >= 250.0 - 0.02
    assert body["lines"], "expected P&L lines for tagged revenue"


def test_dimensional_pl_breakdown_by_dimension(client: TestClient, admin_headers: dict):
    dim = client.post(
        "/api/analytic-dimensions",
        json={"code": "PROJ", "name": "Project", "required": False, "sort_order": 0},
        headers=admin_headers,
    )
    # May collide if prior test left CC at sort 0 — use next free or accept 400 and list
    if dim.status_code == 400:
        dims = client.get("/api/analytic-dimensions", headers=admin_headers).json()["items"]
        assert dims
        dim_id = dims[0]["id"]
    else:
        assert dim.status_code == 201, dim.text
        dim_id = dim.json()["id"]

    aa = client.post(
        "/api/analytic-accounts",
        json={"code": "P-100", "name": "Alpha", "type": "project", "dimension_id": dim_id},
        headers=admin_headers,
    )
    if aa.status_code == 409:
        items = client.get(
            f"/api/analytic-accounts?dimension_id={dim_id}", headers=admin_headers
        ).json()["items"]
        aa_id = items[0]["id"]
    else:
        assert aa.status_code == 201, aa.text
        aa_id = aa.json()["id"]

    cash, rev = _cash_and_revenue(client, admin_headers)
    # Mark dimension optional so we can control tagging; if required from prior test, include analytic
    r = client.post(
        "/api/transactions",
        json={
            "date": "2026-07-01",
            "description": "proj tagged",
            "voucher_type": "JV",
            "analytic_ids": [aa_id],
            "entries": [
                {"account_id": cash["id"], "debit": 80, "credit": 0},
                {"account_id": rev["id"], "debit": 0, "credit": 80},
            ],
        },
        headers=admin_headers,
    )
    assert r.status_code in (200, 201), r.text

    pl = client.get(
        f"/api/reports/dimensional-pl?dimension_id={dim_id}&start=2026-01-01&end=2026-12-31",
        headers=admin_headers,
    )
    assert pl.status_code == 200, pl.text
    body = pl.json()
    assert body["mode"] == "breakdown"
    assert any(s["analytic"]["id"] == aa_id for s in body.get("segments", []))


def test_max_three_dimensions(client: TestClient, admin_headers: dict):
    # Clear path: create up to 3; 4th must 400
    existing = client.get("/api/analytic-dimensions", headers=admin_headers).json()["items"]
    codes = {d["code"] for d in existing}
    used_orders = {d["sort_order"] for d in existing}
    created = 0
    for code, order in [("D0", 0), ("D1", 1), ("D2", 2)]:
        if order in used_orders or code in codes:
            continue
        r = client.post(
            "/api/analytic-dimensions",
            json={"code": code, "name": code, "sort_order": order},
            headers=admin_headers,
        )
        if r.status_code == 201:
            created += 1
    # After filling, one more must fail
    r = client.post(
        "/api/analytic-dimensions",
        json={"code": "D3", "name": "Too Many", "sort_order": 0},
        headers=admin_headers,
    )
    assert r.status_code == 400, r.text
