"""#214 Wave B–D harden: approvals submit, Plaid upsert, vendor portal, AI draft invoice."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import StatementLine, User
from services.ai_tools import TOOL_REGISTRY, execute_tool
from services.plaid_sync import upsert_plaid_transactions


def _auth(client: TestClient, email: str = "harden214@co.test", company: str = "HardenCo"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Tester",
            "company_name": company,
        },
    )
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user_session(client: TestClient, email: str) -> tuple[Session, User]:
    session = Session(client.app.state.engine)
    user = session.exec(select(User).where(User.email == email)).first()
    assert user is not None
    return session, user


def test_submit_invoice_for_approval_creates_request(client: TestClient):
    auth = _auth(client, "appr-inv@co.test")
    r = client.post(
        "/api/approvals/workflows",
        headers=auth,
        json={
            "document_type": "invoice",
            "name": "Invoice approve",
            "is_active": True,
            "steps": [{"step_order": 0, "approver_role": "owner"}],
        },
    )
    assert r.status_code == 201, r.text

    r = client.post("/api/customers", headers=auth, json={"name": "Acme"})
    assert r.status_code in (200, 201), r.text
    cust_id = r.json()["id"]

    r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust_id,
            "issue_date": "2026-07-01",
            "due_date": "2026-07-31",
            "gst_rate": 0,
            "lines": [{"description": "Svc", "qty": 1, "rate": 100}],
        },
    )
    assert r.status_code == 201, r.text
    inv_id = r.json()["id"]

    r = client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["submitted"] is True
    assert body["approval_status"] == "pending"

    r = client.get("/api/approvals/workflows?document_type=invoice", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Re-submit while pending → 400
    r = client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=auth)
    assert r.status_code == 400


def test_submit_without_workflow_is_noop(client: TestClient):
    auth = _auth(client, "appr-none@co.test")
    r = client.post("/api/customers", headers=auth, json={"name": "NoWf"})
    cust_id = r.json()["id"]
    r = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust_id,
            "issue_date": "2026-07-01",
            "due_date": "2026-07-31",
            "gst_rate": 0,
            "lines": [{"description": "Svc", "qty": 1, "rate": 50}],
        },
    )
    inv_id = r.json()["id"]
    r = client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["submitted"] is False


def test_submit_bill_for_approval(client: TestClient):
    auth = _auth(client, "appr-bill@co.test")
    client.post(
        "/api/approvals/workflows",
        headers=auth,
        json={
            "document_type": "bill",
            "name": "Bill approve",
            "is_active": True,
            "steps": [{"step_order": 0, "approver_role": "owner"}],
        },
    )
    r = client.post("/api/vendors", headers=auth, json={"name": "VendorCo"})
    vend_id = r.json()["id"]
    r = client.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_id": vend_id,
            "bill_date": "2026-07-01",
            "due_date": "2026-07-31",
            "gst_rate": 0,
            "lines": [{"description": "Parts", "qty": 1, "rate": 80}],
        },
    )
    assert r.status_code == 201, r.text
    bill_id = r.json()["id"]
    r = client.post(f"/api/bills/{bill_id}/submit-for-approval", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["submitted"] is True
    assert r.json()["approval_status"] == "pending"


def test_plaid_upsert_dedupes_by_external_id(client: TestClient):
    auth = _auth(client, "plaid@co.test")
    session, user = _user_session(client, "plaid@co.test")
    txns = [
        {
            "transaction_id": "txn_abc",
            "date": "2026-07-10",
            "name": "Coffee Shop",
            "amount": 12.5,
        },
        {
            "transaction_id": "txn_in",
            "date": "2026-07-11",
            "name": "Customer deposit",
            "amount": -100.0,
        },
    ]
    first = upsert_plaid_transactions(
        session, tenant_id=user.tenant_id, bank_account_id=1, transactions=txns
    )
    session.commit()
    assert first["imported"] == 2
    assert first["skipped"] == 0

    second = upsert_plaid_transactions(
        session, tenant_id=user.tenant_id, bank_account_id=1, transactions=txns
    )
    session.commit()
    assert second["imported"] == 0
    assert second["skipped"] == 2

    rows = session.exec(
        select(StatementLine).where(StatementLine.tenant_id == user.tenant_id)
    ).all()
    assert len(rows) == 2
    by_ext = {r.external_id: r for r in rows}
    assert float(by_ext["txn_abc"].debit) == 12.5
    assert float(by_ext["txn_abc"].credit) == 0
    assert float(by_ext["txn_in"].credit) == 100.0
    assert float(by_ext["txn_in"].debit) == 0
    session.close()
    _ = auth  # keep signup side-effects (tenant CoA) intentional


def test_vendor_portal_bills_and_statement(client: TestClient):
    auth = _auth(client, "portal-v@co.test")
    r = client.post("/api/vendors", headers=auth, json={"name": "Portal Vendor"})
    vend_id = r.json()["id"]
    r = client.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_id": vend_id,
            "bill_date": "2026-07-01",
            "due_date": "2026-07-31",
            "gst_rate": 0,
            "lines": [{"description": "Widgets", "qty": 2, "rate": 25}],
        },
    )
    assert r.status_code == 201, r.text
    # Mark received so it appears in portal (not draft)
    bill_id = r.json()["id"]
    client.patch(f"/api/bills/{bill_id}/status?status=received", headers=auth)

    r = client.post(
        f"/api/portal/mint?entity_type=vendor&entity_id={vend_id}",
        headers=auth,
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]

    r = client.get(f"/api/portal/{token}")
    assert r.status_code == 200
    assert r.json()["entity_type"] == "vendor"
    assert r.json()["entity_name"] == "Portal Vendor"

    r = client.get(f"/api/portal/{token}/bills")
    assert r.status_code == 200
    bills = r.json()
    assert len(bills) >= 1
    assert bills[0]["number"]

    r = client.get(f"/api/portal/{token}/statement")
    assert r.status_code == 200
    stmt = r.json()
    assert stmt["outstanding"] > 0
    assert len(stmt["open_bills"]) >= 1

    # Customer invoice endpoint rejects vendor tokens
    r = client.get(f"/api/portal/{token}/invoices")
    assert r.status_code == 400


def test_create_draft_invoice_tool_registered_and_works(client: TestClient):
    assert "create_draft_invoice" in TOOL_REGISTRY
    from services.ai_agents import AGENTS
    assert "create_draft_invoice" in AGENTS["sales"].tools
    assert "create_draft_invoice" in AGENTS["data_entry"].tools

    auth = _auth(client, "ai-inv@co.test")
    r = client.post("/api/customers", headers=auth, json={"name": "AI Cust"})
    cust_id = r.json()["id"]
    session, user = _user_session(client, "ai-inv@co.test")
    text, is_error = execute_tool(
        "create_draft_invoice",
        {
            "customer_id": cust_id,
            "issue_date": "2026-07-15",
            "gst_rate": 0,
            "lines": [{"description": "Consulting", "qty": 1, "rate": 250}],
        },
        session,
        user,
    )
    data = json.loads(text)
    assert is_error is False, data
    assert data.get("ok") is True
    assert data.get("invoice_id")
    assert data.get("number")
    session.close()
