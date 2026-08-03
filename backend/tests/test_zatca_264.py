"""Saudi ZATCA e-Invoice country pack (#264) — install, sandbox submit, log."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx


def _install_zatca(client, headers):
    r = client.post("/api/modules/sa_zatca/install?seed_sample=true", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_module_in_registry(client, admin_headers):
    mods = client.get("/api/modules", headers=admin_headers)
    assert mods.status_code == 200
    ids = {m["id"] for m in mods.json()}
    assert "sa_zatca" in ids
    sa = next(m for m in mods.json() if m["id"] == "sa_zatca")
    assert sa["category"] == "Localization"
    assert sa["icon"] == "Landmark"


def test_install_enables_sandbox_settings(client, admin_headers):
    body = _install_zatca(client, admin_headers)
    assert "sa_zatca" in body["installed"]

    settings = client.get("/api/settings", headers=admin_headers).json()
    assert settings.get("zatca_enabled") == "true"
    assert settings.get("zatca_sandbox_mode") == "true"
    assert settings.get("zatca_vat_number")
    # Secret must never leave GET
    assert "zatca_csid_token" not in settings


def test_forbidden_without_module(client, admin_headers):
    r = client.get("/api/zatca/logs", headers=admin_headers)
    assert r.status_code == 403


def test_sandbox_submit_cleared_and_logged(client, admin_headers, monkeypatch):
    _install_zatca(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={
            "zatca_enabled": "true",
            "zatca_sandbox_mode": "true",
            "zatca_vat_number": "300000000000003",
            "zatca_cr_number": "1010000000",
            "company_name": "Riyadh Demo Trading",
        },
    )

    inv = client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_name": "Walk-in Customer",
            "issue_date": "2026-08-01",
            "due_date": "2026-08-15",
            "gst_rate": 15,
            "lines": [
                {"description": "Consulting", "qty": 1, "rate": 1000, "amount": 1000},
            ],
        },
    )
    assert inv.status_code in (200, 201), inv.text
    inv_id = inv.json()["id"]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"status":"REPORTED","uuid":"ZATCA-SBX-TEST-001"}'
    mock_resp.json.return_value = {
        "status": "REPORTED",
        "uuid": "ZATCA-SBX-TEST-001",
        "invoiceHash": "abc123hash",
        "qr": "dGVzdC1xcg==",
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("services.zatca.httpx.Client", return_value=mock_client):
        sub = client.post(f"/api/zatca/invoices/{inv_id}/submit", headers=admin_headers)
    assert sub.status_code == 200, sub.text
    data = sub.json()
    assert data["success"] is True
    assert data["zatca_status"] == "reported"  # B2C / no buyer VAT → report
    assert data["zatca_uuid"] == "ZATCA-SBX-TEST-001"
    assert data["zatca_hash"]
    assert data["zatca_qr"]
    assert data["log_id"]

    detail = client.get(f"/api/invoices/{inv_id}", headers=admin_headers).json()
    assert detail["zatca_status"] == "reported"
    assert detail["zatca_uuid"] == "ZATCA-SBX-TEST-001"

    logs = client.get("/api/zatca/logs", headers=admin_headers)
    assert logs.status_code == 200
    rows = logs.json()
    assert any(row["invoice_id"] == inv_id and row["status"] == "reported" for row in rows)

    status = client.get(f"/api/zatca/invoices/{inv_id}/status", headers=admin_headers)
    assert status.status_code == 200
    assert status.json()["zatca_status"] == "reported"


def test_build_qr_tlv_and_xml_helpers():
    from decimal import Decimal

    from services.zatca import build_zatca_invoice_xml, build_zatca_qr_tlv
    from models import Invoice, InvoiceLine

    qr = build_zatca_qr_tlv("Seller Co", "300000000000003", "2026-08-01T12:00:00Z", "1150.00", "150.00")
    assert isinstance(qr, str) and len(qr) > 10

    inv = Invoice(
        tenant_id=1,
        number="INV-2026-0001",
        issue_date="2026-08-01",
        due_date="2026-08-15",
        customer_name="Buyer",
        subtotal=Decimal("1000"),
        gst_rate=Decimal("15"),
        gst_amount=Decimal("150"),
        total=Decimal("1150"),
        status="draft",
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
    xml = build_zatca_invoice_xml(
        invoice=inv,
        lines=lines,
        customer=None,
        config={"vat_number": "300000000000003", "cr_number": "101", "seller_name": "Seller Co"},
        invoice_uuid="11111111-2222-3333-4444-555555555555",
    )
    assert "300000000000003" in xml
    assert "INV-2026-0001" in xml
    assert "11111111-2222-3333-4444-555555555555" in xml


def test_sandbox_test_endpoint_mocked(client, admin_headers):
    _install_zatca(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={"zatca_enabled": "true", "zatca_vat_number": "300000000000003", "zatca_sandbox_mode": "true"},
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "unauthorized"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("routers.zatca.httpx.Client", return_value=mock_client):
        ping = client.post("/api/zatca/test", headers=admin_headers)
    assert ping.status_code == 200, ping.text
    assert ping.json()["ok"] is True
    assert ping.json()["sandbox"] is True
