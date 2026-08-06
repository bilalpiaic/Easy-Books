"""Approval Workflows document-type LOV — full product catalog across tenants."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from models import ApprovalWorkflow, Tenant
from services.approval_document_types import (
    DOCUMENT_TYPE_KEYS,
    all_catalog_types,
    is_valid_document_type,
    list_document_types,
)


def test_catalog_includes_original_four_and_module_docs():
    keys = {r["key"] for r in all_catalog_types()}
    for required in ("invoice", "bill", "purchase_order", "journal"):
        assert required in keys
    # Types from other tenant business models / modules must be present
    for required in (
        "purchase_demand",
        "payroll_run",
        "spinning_bale_receipt",
        "healthcare_admission",
        "textile_sales_order",
        "weaving_contract",
        "credit_note",
        "gate_outward",
    ):
        assert required in keys, f"missing {required}"


def test_document_types_endpoint_returns_full_lov(client: TestClient, admin_headers):
    r = client.get("/api/approvals/document-types", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list) and len(body) >= len(DOCUMENT_TYPE_KEYS)
    keys = {row["key"] for row in body}
    assert "invoice" in keys and "bill" in keys
    assert "purchase_demand" in keys
    assert "spinning_dispatch" in keys
    # Each row has label for the LOV
    assert all(row.get("label") and row.get("key") for row in body)


def test_create_workflow_accepts_expanded_document_types(client: TestClient, admin_headers):
    r = client.post(
        "/api/approvals/workflows",
        headers=admin_headers,
        json={
            "document_type": "purchase_demand",
            "name": "Demand approval",
            "is_active": True,
            "steps": [{"step_order": 0, "approver_role": "owner"}],
        },
    )
    assert r.status_code == 201, r.text

    r = client.post(
        "/api/approvals/workflows",
        headers=admin_headers,
        json={
            "document_type": "not_a_real_doc_type_xyz",
            "name": "Bad",
            "is_active": True,
            "steps": [{"step_order": 0, "approver_role": "owner"}],
        },
    )
    assert r.status_code == 400


def test_lov_includes_workflow_keys_from_other_tenants(client: TestClient, admin_headers):
    """Distinct document_type values from ANY tenant appear in the LOV."""
    engine = client.app.state.engine
    with Session(engine) as s:
        other = Tenant(name="Other LOV Tenant", business_model="simple")
        s.add(other)
        s.commit()
        s.refresh(other)
        s.add(ApprovalWorkflow(
            tenant_id=other.id,
            document_type="legacy_custom_doc",
            name="Legacy",
            is_active=True,
        ))
        s.commit()

    r = client.get("/api/approvals/document-types", headers=admin_headers)
    assert r.status_code == 200
    keys = {row["key"] for row in r.json()}
    assert "legacy_custom_doc" in keys

    with Session(engine) as s:
        assert is_valid_document_type(s, "legacy_custom_doc")
        rows = list_document_types(s)
        assert any(r["key"] == "legacy_custom_doc" for r in rows)
