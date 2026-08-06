"""Leave + LOP payroll integration (#303)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str, company="Leave Co"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": company,
            "business_model": "services",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_hrm(client, auth):
    r = client.post("/api/modules/hrm/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def test_leave_approve_and_lop_on_payslip(client: TestClient):
    auth = _signup(client, "leave303@co.test")
    _install_hrm(client, auth)

    # Seed leave types
    seeded = client.post("/api/leave/types/seed-defaults", headers=auth)
    assert seeded.status_code == 200, seeded.text
    types = client.get("/api/leave/types", headers=auth).json()
    by_code = {t["code"]: t for t in types}
    assert "UL" in by_code
    ul_id = by_code["UL"]["id"]

    emp = client.post(
        "/api/employees",
        headers=auth,
        json={"employee_code": "E1", "name": "Ali", "is_active": True},
    )
    assert emp.status_code in (200, 201), emp.text
    emp_id = emp.json()["id"]

    # Salary structure: BASIC 30_000
    comps = client.get("/api/payroll/components", headers=auth).json()
    if not comps:
        basic = client.post(
            "/api/payroll/components",
            headers=auth,
            json={
                "name": "Basic",
                "code": "BASIC",
                "component_type": "earnings",
                "is_fixed": True,
            },
        ).json()
    else:
        basic = next((c for c in comps if c["code"] == "BASIC"), comps[0])
        if basic["code"] != "BASIC":
            basic = client.post(
                "/api/payroll/components",
                headers=auth,
                json={
                    "name": "Basic",
                    "code": "BASIC",
                    "component_type": "earnings",
                    "is_fixed": True,
                },
            ).json()

    # Put structure via employee salary API if exists
    struct = client.put(
        f"/api/employees/{emp_id}/structure",
        headers=auth,
        json=[{"component_id": basic["id"], "amount": 30000}],
    )
    assert struct.status_code in (200, 201), struct.text

    # Create unpaid leave 2 days in August — pending
    req = client.post(
        "/api/leave/requests",
        headers=auth,
        json={
            "employee_id": emp_id,
            "leave_type_id": ul_id,
            "from_date": "2026-08-10",
            "to_date": "2026-08-11",
            "reason": "Personal",
        },
    )
    assert req.status_code == 201, req.text
    req_id = req.json()["id"]
    assert req.json()["days"] == 2.0

    # Self-approve blocked
    blocked = client.post(f"/api/leave/requests/{req_id}/approve", headers=auth)
    assert blocked.status_code == 400

    invite = client.post(
        "/api/users",
        headers=auth,
        json={
            "email": "approver303@co.test",
            "password": "password123",
            "full_name": "Approver",
            "role": "admin",
        },
    )
    assert invite.status_code in (200, 201), f"invite failed: {invite.text}"

    r2 = client.post(
        "/api/auth/login",
        data={"username": "approver303@co.test", "password": "password123"},
    )
    assert r2.status_code == 200, r2.text
    auth2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    approved = client.post(f"/api/leave/requests/{req_id}/approve", headers=auth2)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    # Payroll run covering August
    run = client.post(
        "/api/payroll/runs",
        headers=auth,
        json={
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "pay_date": "2026-09-01",
        },
    )
    assert run.status_code in (200, 201), run.text
    run_id = run.json()["id"]

    slip = client.get(f"/api/payroll/runs/{run_id}/payslip/{emp_id}", headers=auth)
    assert slip.status_code == 200, slip.text
    body = slip.json()
    assert body["unpaid_leave_days"] == 2.0
    assert any(d["code"] == "LOP" for d in body["deductions"])
    lop = next(d for d in body["deductions"] if d["code"] == "LOP")
    # 30000 / 31 * 2 ≈ 1935.48
    assert float(lop["amount"]) > 1900
    assert float(body["net_pay"]) < 30000
    assert len(body["leave"]) >= 1
