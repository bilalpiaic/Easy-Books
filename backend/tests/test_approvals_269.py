"""#269 Approvals SoD, amount thresholds, substitutes, decision audit, perms."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import ApprovalDecision


def _auth(client: TestClient, email: str, company: str = "SoDCo"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": company,
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _login(client: TestClient, email: str):
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _add_user(client: TestClient, owner_auth, email: str, role: str = "admin"):
    r = client.post(
        "/api/users",
        headers=owner_auth,
        json={
            "email": email,
            "password": "password123",
            "full_name": email.split("@")[0],
            "role": role,
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _invoice(client: TestClient, auth, rate: float = 100.0) -> int:
    r = client.post("/api/customers", headers=auth, json={"name": f"Cust-{rate}"})
    assert r.status_code in (200, 201), r.text
    cust_id = r.json()["id"]
    r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust_id,
            "issue_date": "2026-08-01",
            "due_date": "2026-08-31",
            "gst_rate": 0,
            "lines": [{"description": "Svc", "qty": 1, "rate": rate}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_sod_blocks_self_approve_when_enabled(client: TestClient):
    owner = _auth(client, "sod-on@co.test", "SoDOn")
    admin_id = _add_user(client, owner, "sod-admin@co.test", "admin")
    assert admin_id

    r = client.post(
        "/api/approvals/workflows",
        headers=owner,
        json={
            "document_type": "invoice",
            "name": "Inv",
            "is_active": True,
            "steps": [{"step_order": 0, "approver_role": "owner"}],
        },
    )
    assert r.status_code == 201, r.text

    inv_id = _invoice(client, owner, 200)
    r = client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=owner)
    assert r.status_code == 200 and r.json()["submitted"] is True

    pending = client.get("/api/approvals", headers=owner).json()
    # Owner is submitter — SoD hides from their inbox
    assert pending == []

    r = client.get("/api/approvals", headers=_login(client, "sod-admin@co.test"))
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    req_id = items[0]["id"]

    # Direct approve as submitter still blocked even if they guess the id
    r = client.post(
        f"/api/approvals/{req_id}/approve",
        headers=owner,
        json={"notes": "self"},
    )
    assert r.status_code == 400
    assert "submitter" in r.json()["detail"].lower() or "cannot" in r.json()["detail"].lower()

    r = client.post(
        f"/api/approvals/{req_id}/approve",
        headers=_login(client, "sod-admin@co.test"),
        json={"notes": "ok"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


def test_sod_allows_self_approve_when_disabled(client: TestClient):
    owner = _auth(client, "sod-off@co.test", "SoDOff")
    client.patch(
        "/api/settings",
        headers=owner,
        json={"approvals_block_self_approval": "false"},
    )
    client.post(
        "/api/approvals/workflows",
        headers=owner,
        json={
            "document_type": "invoice",
            "name": "Inv",
            "is_active": True,
            "steps": [{"step_order": 0, "approver_role": "owner"}],
        },
    )
    inv_id = _invoice(client, owner, 150)
    client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=owner)
    items = client.get("/api/approvals", headers=owner).json()
    assert len(items) == 1
    r = client.post(
        f"/api/approvals/{items[0]['id']}/approve",
        headers=owner,
        json={},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


def test_threshold_routing_and_advance(client: TestClient):
    owner = _auth(client, "thr@co.test", "ThrCo")
    _add_user(client, owner, "thr-admin@co.test", "admin")
    admin = _login(client, "thr-admin@co.test")

    client.post(
        "/api/approvals/workflows",
        headers=owner,
        json={
            "document_type": "invoice",
            "name": "Tiered",
            "is_active": True,
            "steps": [
                {"step_order": 0, "approver_role": "admin", "min_amount": 1000},
                {"step_order": 1, "approver_role": "owner", "min_amount": 5000},
            ],
        },
    )

    # Below all thresholds → no request
    low = _invoice(client, owner, 500)
    r = client.post(f"/api/invoices/{low}/submit-for-approval", headers=owner)
    assert r.status_code == 200
    assert r.json()["submitted"] is False

    # Mid band: only first step applies
    mid = _invoice(client, owner, 2500)
    r = client.post(f"/api/invoices/{mid}/submit-for-approval", headers=owner)
    assert r.json()["submitted"] is True
    items = client.get("/api/approvals", headers=admin).json()
    assert len(items) == 1
    assert items[0]["amount"] == 2500.0 or items[0]["amount"] == 2500
    assert items[0]["current_step"] == 0
    req_id = items[0]["id"]

    r = client.post(f"/api/approvals/{req_id}/approve", headers=admin, json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"  # no second applicable step

    # High band: both steps — approve advances then resolves
    high = _invoice(client, owner, 8000)
    r = client.post(f"/api/invoices/{high}/submit-for-approval", headers=owner)
    assert r.json()["submitted"] is True
    items = client.get("/api/approvals", headers=admin).json()
    assert len(items) == 1
    req_id = items[0]["id"]
    assert items[0]["current_step"] == 0

    r = client.post(f"/api/approvals/{req_id}/approve", headers=admin, json={"notes": "L1"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    assert r.json()["current_step"] == 1

    # Owner is also submitter — SoD blocks; use a second owner? Use admin can't do step 1
    # unless admin matches owner role via admin bypass — yes owner/admin bypass role steps.
    # SoD still blocks owner (submitter). Admin can finish step 1 via admin role bypass.
    r = client.post(f"/api/approvals/{req_id}/approve", headers=admin, json={"notes": "L2"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


def test_substitute_in_range_can_approve(client: TestClient):
    owner = _auth(client, "sub-o@co.test", "SubCo")
    admin_id = _add_user(client, owner, "sub-a@co.test", "admin")
    cover_id = _add_user(client, owner, "sub-cover@co.test", "accountant")
    _add_user(client, owner, "sub-c-submit@co.test", "accountant")
    admin = _login(client, "sub-a@co.test")
    submitter = _login(client, "sub-c-submit@co.test")
    cover = _login(client, "sub-cover@co.test")

    client.post(
        "/api/approvals/workflows",
        headers=owner,
        json={
            "document_type": "invoice",
            "name": "User step",
            "is_active": True,
            "steps": [{"step_order": 0, "approver_user_id": admin_id}],
        },
    )

    inv_id = _invoice(client, submitter, 300)
    r = client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=submitter)
    assert r.json()["submitted"] is True

    today = date.today()
    # Out of range — cover cannot approve
    client.post(
        "/api/approvals/substitutes",
        headers=admin,
        json={
            "substitute_user_id": cover_id,
            "starts_on": (today - timedelta(days=10)).isoformat(),
            "ends_on": (today - timedelta(days=5)).isoformat(),
            "is_active": True,
        },
    )
    assert client.get("/api/approvals", headers=cover).json() == []

    # In range
    client.post(
        "/api/approvals/substitutes",
        headers=admin,
        json={
            "substitute_user_id": cover_id,
            "starts_on": today.isoformat(),
            "ends_on": (today + timedelta(days=3)).isoformat(),
            "is_active": True,
        },
    )
    items = client.get("/api/approvals", headers=cover).json()
    assert len(items) == 1
    r = client.post(
        f"/api/approvals/{items[0]['id']}/approve",
        headers=cover,
        json={"notes": "covering"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


def test_workflows_permission_enforced(client: TestClient):
    owner = _auth(client, "perm-o@co.test", "PermCo")
    _add_user(client, owner, "perm-v@co.test", "accountant")
    viewer = _login(client, "perm-v@co.test")

    client.patch("/api/settings", headers=owner, json={"user_rights_enabled": "true"})
    users = client.get("/api/users", headers=owner).json()["items"]
    acct = next(u for u in users if u["email"] == "perm-v@co.test")
    r = client.put(
        f"/api/permissions/users/{acct['id']}",
        headers=owner,
        json=[
            {"resource_key": "approvals.workflows", "access_level": "view"},
            {"resource_key": "approvals", "access_level": "view"},
        ],
    )
    assert r.status_code == 200, r.text

    r = client.post(
        "/api/approvals/workflows",
        headers=viewer,
        json={
            "document_type": "invoice",
            "name": "Nope",
            "is_active": True,
            "steps": [{"step_order": 0, "approver_role": "owner"}],
        },
    )
    assert r.status_code == 403

    r = client.get("/api/approvals/workflows", headers=viewer)
    assert r.status_code == 200


def test_decision_rows_append_only(client: TestClient):
    owner = _auth(client, "dec@co.test", "DecCo")
    _add_user(client, owner, "dec-a@co.test", "admin")
    admin = _login(client, "dec-a@co.test")

    client.post(
        "/api/approvals/workflows",
        headers=owner,
        json={
            "document_type": "invoice",
            "name": "Inv",
            "is_active": True,
            "steps": [
                {"step_order": 0, "approver_role": "admin", "min_amount": None},
                {"step_order": 1, "approver_role": "owner", "min_amount": None},
            ],
        },
    )
    inv_id = _invoice(client, owner, 100)
    client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=owner)
    req_id = client.get("/api/approvals", headers=admin).json()[0]["id"]

    client.post(f"/api/approvals/{req_id}/approve", headers=admin, json={"notes": "1"})
    # second step — admin can still act via role bypass; owner is submitter so SoD blocks them
    client.post(f"/api/approvals/{req_id}/approve", headers=admin, json={"notes": "2"})

    decisions = client.get(f"/api/approvals/{req_id}/decisions", headers=admin).json()
    assert len(decisions) == 2
    assert [d["action"] for d in decisions] == ["approve", "approve"]
    assert decisions[0]["step_index"] == 0
    assert decisions[1]["step_index"] == 1

    # No delete endpoint — count stays
    session = Session(client.app.state.engine)
    n = len(session.exec(select(ApprovalDecision).where(ApprovalDecision.request_id == req_id)).all())
    session.close()
    assert n == 2
