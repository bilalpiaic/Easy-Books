"""Malaysia MyInvois e-Invoice country pack (#306) — install, sandbox submit, log."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def _install_my_invois(client, headers):
    r = client.post("/api/modules/my_invois/install?seed_sample=true", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_module_in_registry(client, admin_headers):
    mods = client.get("/api/modules", headers=admin_headers)
    assert mods.status_code == 200
    ids = {m["id"] for m in mods.json()}
    assert "my_invois" in ids
    my = next(m for m in mods.json() if m["id"] == "my_invois")
    assert my["category"] == "Localization"
    assert my["icon"] == "FileCheck"


def test_install_enables_sandbox_settings(client, admin_headers):
    body = _install_my_invois(client, admin_headers)
    assert "my_invois" in body["installed"]

    settings = client.get("/api/settings", headers=admin_headers).json()
    assert settings.get("my_invois_enabled") == "true"
    assert settings.get("my_invois_sandbox_mode") == "true"
    assert settings.get("my_invois_tin")
    assert "my_invois_client_secret" not in settings


def test_forbidden_without_module(client, admin_headers):
    r = client.get("/api/my-invois/logs", headers=admin_headers)
    assert r.status_code == 403


def test_sandbox_submit_accepted_and_logged(client, admin_headers):
    _install_my_invois(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={
            "my_invois_enabled": "true",
            "my_invois_sandbox_mode": "true",
            "my_invois_tin": "C12345678901",
            "company_name": "KL Demo Sdn Bhd",
        },
    )

    inv = client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_name": "Walk-in Customer",
            "issue_date": "2026-08-01",
            "due_date": "2026-08-15",
            "gst_rate": 8,
            "lines": [
                {"description": "Consulting", "qty": 1, "rate": 1000, "amount": 1000},
            ],
        },
    )
    assert inv.status_code in (200, 201), inv.text
    inv_id = inv.json()["id"]

    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_resp.text = '{"submissionUid":"MY-SBX-TEST-001","acceptedDocuments":[{"uuid":"MY-SBX-TEST-001"}]}'
    mock_resp.json.return_value = {
        "submissionUid": "MY-SBX-TEST-001",
        "acceptedDocuments": [{"uuid": "MY-SBX-TEST-001"}],
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("services.my_invois.httpx.Client", return_value=mock_client):
        sub = client.post(f"/api/my-invois/invoices/{inv_id}/submit", headers=admin_headers)
    assert sub.status_code == 200, sub.text
    data = sub.json()
    assert data["success"] is True
    assert data["my_invois_status"] == "accepted"
    assert data["my_invois_uuid"] == "MY-SBX-TEST-001"
    assert data["log_id"]

    detail = client.get(f"/api/invoices/{inv_id}", headers=admin_headers).json()
    assert detail["my_invois_status"] == "accepted"
    assert detail["my_invois_uuid"] == "MY-SBX-TEST-001"

    logs = client.get("/api/my-invois/logs", headers=admin_headers)
    assert logs.status_code == 200
    rows = logs.json()
    assert any(row["invoice_id"] == inv_id and row["status"] == "accepted" for row in rows)

    status = client.get(f"/api/my-invois/invoices/{inv_id}/status", headers=admin_headers)
    assert status.status_code == 200
    assert status.json()["my_invois_status"] == "accepted"


def test_build_document_helper():
    from decimal import Decimal

    from models import Invoice, InvoiceLine
    from services.my_invois import build_my_invois_document

    inv = Invoice(
        tenant_id=1,
        number="INV-2026-0001",
        issue_date="2026-08-01",
        due_date="2026-08-15",
        customer_name="Buyer",
        subtotal=Decimal("1000"),
        gst_rate=Decimal("8"),
        gst_amount=Decimal("80"),
        total=Decimal("1080"),
        status="draft",
        currency="MYR",
    )
    lines = [
        InvoiceLine(
            invoice_id=1,
            description="Service",
            qty=Decimal("1"),
            rate=Decimal("1000"),
            amount=Decimal("1000"),
        )
    ]
    doc = build_my_invois_document(
        invoice=inv,
        lines=lines,
        customer=None,
        config={"tin": "C12345678901", "seller_name": "Seller Co"},
        doc_uuid="11111111-2222-3333-4444-555555555555",
    )
    assert doc["supplier"]["tin"] == "C12345678901"
    assert doc["codeNumber"] == "INV-2026-0001"
    assert doc["taxTotal"] == 80.0
    assert len(doc["lines"]) == 1
