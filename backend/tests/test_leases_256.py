"""#256 IFRS 16 leases — PV math, interest split, balanced period JEs."""
from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from services.leases import present_value_of_lease, build_schedule
from services.money import D, money


def _auth(client: TestClient, email: str = "lease@test.local"):
    client.post("/api/auth/signup", json={
        "email": email,
        "password": "password123",
        "full_name": "Lease Owner",
        "company_name": "LeaseCo",
        "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_pv_math_known_annuity():
    # 12 months × 1,000 at 12% annual → monthly r=1%
    # PV = 1000 * (1 - 1.01^-12) / 0.01 ≈ 11,255.08
    pv = present_value_of_lease(Decimal("1000"), 12, Decimal("12"), "arrears")
    assert abs(float(pv) - 11255.08) < 0.02


def test_schedule_interest_split_and_clears():
    pv = present_value_of_lease(Decimal("1000"), 12, Decimal("12"), "arrears")
    rows = build_schedule(
        commencement="2026-01-01",
        payment=Decimal("1000"),
        term_months=12,
        annual_pct=Decimal("12"),
        timing="arrears",
        rou_cost=pv,
        opening_liability=pv,
    )
    assert len(rows) == 12
    assert rows[-1].closing_liability == 0
    # First interest ≈ PV * 1%
    assert abs(float(rows[0].interest) - float(money(pv * D("0.01")))) < 0.02
    # Payment = interest + principal each period (within 1 cent)
    for r in rows:
        assert abs(float(r.payment) - float(r.interest + r.principal)) < 0.02
    # RoU depr sums to cost
    assert abs(sum(float(r.depreciation) for r in rows) - float(pv)) < 0.02


def test_activate_and_post_period_balanced(client: TestClient):
    auth = _auth(client, "lease-post@test.local")

    # Seed bank so we can pay
    by = {a["code"]: a["id"] for a in client.get("/api/accounts?limit=500", headers=auth).json()["items"]}
    # Ensure cash exists for funding bank if needed — post capital
    client.post("/api/transactions", headers=auth, json={
        "date": "2026-01-01",
        "description": "capital",
        "entries": [
            {"account_id": by["1010"], "debit": 50000, "credit": 0},
            {"account_id": by["3000"], "debit": 0, "credit": 50000},
        ],
    })

    preview = client.post("/api/leases/preview", headers=auth, json={
        "commencement_date": "2026-01-01",
        "term_months": 6,
        "payment_amount": 1000,
        "annual_discount_rate": 12,
        "payment_timing": "arrears",
    })
    assert preview.status_code == 200, preview.text
    assert preview.json()["present_value"] > 0

    created = client.post("/api/leases", headers=auth, json={
        "name": "Office rent",
        "lessor": "Landlord Ltd",
        "commencement_date": "2026-01-01",
        "term_months": 6,
        "payment_amount": 1000,
        "annual_discount_rate": 12,
        "payment_timing": "arrears",
        "payment_account_id": by["1010"],
        "activate": True,
    })
    assert created.status_code == 201, created.text
    lease = created.json()
    assert lease["status"] == "active"
    assert lease["initial_transaction_id"]
    assert abs(lease["rou_cost"] - lease["present_value"]) < 0.01

    detail = client.get(f"/api/leases/{lease['id']}", headers=auth).json()
    assert len(detail["schedule"]) == 6
    assert detail["schedule"][0]["status"] == "pending"

    posted = client.post(
        f"/api/leases/{lease['id']}/periods/1/post", headers=auth,
    )
    assert posted.status_code == 200, posted.text
    line = posted.json()
    assert line["status"] == "posted"
    assert line["interest_transaction_id"]
    assert line["payment_transaction_id"]
    assert line["depr_transaction_id"]

    # Verify each JE balances via transaction fetch
    for tid in (line["interest_transaction_id"], line["payment_transaction_id"], line["depr_transaction_id"]):
        txn = client.get(f"/api/transactions/{tid}", headers=auth).json()
        entries = txn.get("journal_entries") or txn.get("entries") or []
        if not entries and "id" in txn:
            # shape may nest differently
            entries = txn.get("lines") or []
        dr = sum(float(e.get("debit") or 0) for e in entries)
        cr = sum(float(e.get("credit") or 0) for e in entries)
        assert abs(dr - cr) < 0.01, (tid, txn)

    maturity = client.get("/api/leases/maturity?as_of=2026-01-01", headers=auth)
    assert maturity.status_code == 200, maturity.text
    assert maturity.json()["buckets"]["total"] > 0


def test_leases_disabled_setting(client: TestClient):
    auth = _auth(client, "lease-off@test.local")
    client.patch("/api/settings", headers=auth, json={"leases_enabled": "false"})
    r = client.get("/api/leases", headers=auth)
    assert r.status_code == 400
    assert "disabled" in r.json()["detail"].lower()
