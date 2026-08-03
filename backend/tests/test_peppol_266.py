"""Peppol / EU VAT e-Invoice country pack (#266) — UBL XML, tax mapping, mock submit."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch


def _install_peppol(client, headers):
    r = client.post("/api/modules/eu_peppol/install?seed_sample=true", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_module_in_registry(client, admin_headers):
    mods = client.get("/api/modules", headers=admin_headers)
    assert mods.status_code == 200
    ids = {m["id"] for m in mods.json()}
    assert "eu_peppol" in ids
    eu = next(m for m in mods.json() if m["id"] == "eu_peppol")
    assert eu["category"] == "Localization"
    assert eu["icon"] == "Globe"


def test_install_enables_sandbox_settings(client, admin_headers):
    body = _install_peppol(client, admin_headers)
    assert "eu_peppol" in body["installed"]

    settings = client.get("/api/settings", headers=admin_headers).json()
    assert settings.get("peppol_enabled") == "true"
    assert settings.get("peppol_sandbox_mode") == "true"
    assert settings.get("peppol_participant_id")
    assert settings.get("peppol_ap_url")
    # Secret must never leave GET
    assert "peppol_api_key" not in settings


def test_forbidden_without_module(client, admin_headers):
    r = client.get("/api/peppol/logs", headers=admin_headers)
    assert r.status_code == 403


def test_map_vat_category_tax_mapping():
    from services.peppol import map_vat_category

    assert map_vat_category(Decimal("21")) == ("S", "Standard rated")
    assert map_vat_category(21) == ("S", "Standard rated")
    assert map_vat_category(Decimal("0")) == ("Z", "Zero rated goods")
    assert map_vat_category(Decimal("0"), reverse_charge=True) == ("AE", "VAT Reverse Charge")
    assert map_vat_category(Decimal("19"), reverse_charge=True)[0] == "AE"


def test_build_ubl_bis_billing_xml_structure_and_tax():
    from models import Invoice, InvoiceLine
    from services.peppol import (
        BIS_BILLING_CUSTOMIZATION_ID,
        build_ubl_bis_billing_xml,
    )

    inv = Invoice(
        tenant_id=1,
        number="INV-2026-EU-0001",
        issue_date="2026-08-01",
        due_date="2026-08-31",
        customer_name="Amsterdam Buyer BV",
        subtotal=Decimal("1000"),
        gst_rate=Decimal("21"),
        gst_amount=Decimal("210"),
        total=Decimal("1210"),
        currency="EUR",
        status="draft",
    )
    lines = [
        InvoiceLine(
            invoice_id=1,
            description="Consulting services",
            qty=Decimal("1"),
            rate=Decimal("1000"),
            amount=Decimal("1000"),
            tax_rate=Decimal("21"),
            tax_amount=Decimal("210"),
        )
    ]
    xml = build_ubl_bis_billing_xml(
        inv,
        lines,
        {
            "participant_id": "0088:1234567890123",
            "seller_name": "Demo NL Trading BV",
            "seller_vat": "NL123456789B01",
            "seller_country": "NL",
            "currency": "EUR",
            "address_line1": "Herengracht 1",
            "city": "Amsterdam",
        },
        document_id="doc-uuid-test-001",
    )

    assert "<Invoice" in xml
    assert 'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"' in xml
    assert 'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"' in xml
    assert "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" in xml
    assert BIS_BILLING_CUSTOMIZATION_ID in xml
    assert "<cac:AccountingSupplierParty>" in xml
    assert "<cac:AccountingCustomerParty>" in xml
    assert "<cac:TaxTotal>" in xml
    assert "<cac:InvoiceLine>" in xml
    assert "<cbc:ID>S</cbc:ID>" in xml or ">S</cbc:ID>" in xml
    assert "21.00" in xml
    assert "INV-2026-EU-0001" in xml
    assert "NL123456789B01" in xml
    assert "doc-uuid-test-001" in xml


def test_build_ubl_reverse_charge_maps_ae():
    from models import Customer, Invoice, InvoiceLine
    from services.peppol import build_ubl_bis_billing_xml

    inv = Invoice(
        tenant_id=1,
        number="INV-RC-1",
        issue_date="2026-08-01",
        due_date="2026-08-15",
        customer_name="DE Buyer",
        subtotal=Decimal("500"),
        gst_rate=Decimal("0"),
        gst_amount=Decimal("0"),
        total=Decimal("500"),
        currency="EUR",
        status="draft",
    )
    lines = [
        InvoiceLine(
            invoice_id=1,
            description="Cross-border service",
            qty=Decimal("1"),
            rate=Decimal("500"),
            amount=Decimal("500"),
        )
    ]
    customer = Customer(tenant_id=1, name="DE Buyer", ntn="DE123456789")
    xml = build_ubl_bis_billing_xml(
        inv,
        lines,
        {
            "participant_id": "9930:NL999999999B01",
            "seller_name": "NL Seller",
            "seller_vat": "NL999999999B01",
            "seller_country": "NL",
            "currency": "EUR",
        },
        customer=customer,
    )
    assert ">AE</cbc:ID>" in xml or "<cbc:ID>AE</cbc:ID>" in xml
    assert "Reverse charge" in xml


def test_sandbox_submit_accepted_and_logged(client, admin_headers):
    _install_peppol(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={
            "peppol_enabled": "true",
            "peppol_sandbox_mode": "true",
            "peppol_participant_id": "0088:1234567890123",
            "peppol_ap_url": "https://api.peppol-sandbox.example/v1/send",
            "company_name": "Demo NL Trading BV",
            "tax_id": "NL123456789B01",
            "currency": "EUR",
            "country": "NL",
        },
    )

    inv = client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_name": "EU Customer",
            "issue_date": "2026-08-01",
            "due_date": "2026-08-15",
            "gst_rate": 21,
            "currency": "EUR",
            "lines": [
                {"description": "Consulting", "qty": 1, "rate": 1000, "amount": 1000},
            ],
        },
    )
    assert inv.status_code in (200, 201), inv.text
    inv_id = inv.json()["id"]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"status":"ACCEPTED","documentId":"PEPPOL-SBX-DOC-001"}'
    mock_resp.json.return_value = {
        "status": "ACCEPTED",
        "documentId": "PEPPOL-SBX-DOC-001",
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("services.peppol.httpx.Client", return_value=mock_client):
        sub = client.post(f"/api/peppol/invoices/{inv_id}/submit", headers=admin_headers)
    assert sub.status_code == 200, sub.text
    data = sub.json()
    assert data["success"] is True
    assert data["peppol_status"] == "accepted"
    assert data["peppol_document_id"] == "PEPPOL-SBX-DOC-001"
    assert data["log_id"]

    detail = client.get(f"/api/invoices/{inv_id}", headers=admin_headers).json()
    assert detail["peppol_status"] == "accepted"
    assert detail["peppol_document_id"] == "PEPPOL-SBX-DOC-001"

    logs = client.get("/api/peppol/logs", headers=admin_headers)
    assert logs.status_code == 200
    rows = logs.json()
    assert any(row["invoice_id"] == inv_id and row["status"] == "accepted" for row in rows)

    status = client.get(f"/api/peppol/invoices/{inv_id}/status", headers=admin_headers)
    assert status.status_code == 200
    assert status.json()["peppol_status"] == "accepted"

    # Export UBL XML download
    export = client.get(f"/api/peppol/invoices/{inv_id}/export", headers=admin_headers)
    assert export.status_code == 200, export.text
    assert "application/xml" in export.headers.get("content-type", "")
    body = export.text
    assert "<Invoice" in body
    assert "xmlns:cac=" in body
    assert "xmlns:cbc=" in body
    assert "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0" in body


def test_sandbox_test_endpoint_mocked(client, admin_headers):
    _install_peppol(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={
            "peppol_enabled": "true",
            "peppol_participant_id": "0088:1234567890123",
            "peppol_ap_url": "https://api.peppol-sandbox.example/v1/send",
            "peppol_sandbox_mode": "true",
        },
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "unauthorized"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("routers.peppol.httpx.Client", return_value=mock_client):
        ping = client.post("/api/peppol/test", headers=admin_headers)
    assert ping.status_code == 200, ping.text
    assert ping.json()["ok"] is True
    assert ping.json()["sandbox"] is True
