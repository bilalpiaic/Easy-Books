"""Expense claims + statutory pack (#303 remainder)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": "HR Co",
            "business_model": "services",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_hrm(client, auth):
    r = client.post("/api/modules/hrm/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def test_expense_claim_approve_creates_bill(client: TestClient):
    auth = _signup(client, "exp303@co.test")
    _install_hrm(client, auth)

    emp = client.post(
        "/api/employees",
        headers=auth,
        json={"employee_code": "E9", "name": "Sara", "is_active": True},
    )
    assert emp.status_code in (200, 201), emp.text
    emp_id = emp.json()["id"]

    claim = client.post(
        "/api/expense-claims",
        headers=auth,
        json={
            "employee_id": emp_id,
            "claim_date": "2026-08-01",
            "description": "Client travel",
            "lines": [{"description": "Taxi", "amount": 150}],
        },
    )
    assert claim.status_code == 201, claim.text
    assert claim.json()["status"] == "submitted"
    cid = claim.json()["id"]

    approved = client.post(f"/api/expense-claims/{cid}/approve", headers=auth)
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "approved"
    assert body["bill_id"] is not None

    bill = client.get(f"/api/bills/{body['bill_id']}", headers=auth)
    assert bill.status_code == 200, bill.text
    assert float(bill.json()["total"]) == 150.0


def test_statutory_pk_pack(client: TestClient):
    auth = _signup(client, "stat303@co.test")
    _install_hrm(client, auth)

    seeded = client.post("/api/payroll/components/seed-statutory-pk", headers=auth)
    assert seeded.status_code == 200, seeded.text
    comps = client.get("/api/payroll/components", headers=auth).json()
    by_code = {c["code"]: c for c in comps}
    assert "EOBI" in by_code
    assert by_code["EOBI"]["component_type"] == "statutory"
    assert "SESSTI" in by_code
    assert by_code["SESSTI"]["component_type"] == "statutory"

    # Idempotent
    again = client.post("/api/payroll/components/seed-statutory-pk", headers=auth)
    assert again.status_code == 200
    assert again.json()["created"] == []
