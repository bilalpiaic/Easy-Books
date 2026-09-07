"""UK MTD VAT country pack (#306) — install, VAT boxes, sandbox submit, log."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def _install_uk_mtd(client, headers):
    r = client.post("/api/modules/uk_mtd/install?seed_sample=true", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_module_in_registry(client, admin_headers):
    mods = client.get("/api/modules", headers=admin_headers)
    assert mods.status_code == 200
    ids = {m["id"] for m in mods.json()}
    assert "uk_mtd" in ids
    uk = next(m for m in mods.json() if m["id"] == "uk_mtd")
    assert uk["category"] == "Localization"
    assert uk["icon"] == "Landmark"


def test_install_enables_sandbox_settings(client, admin_headers):
    body = _install_uk_mtd(client, admin_headers)
    assert "uk_mtd" in body["installed"]

    settings = client.get("/api/settings", headers=admin_headers).json()
    assert settings.get("uk_mtd_enabled") == "true"
    assert settings.get("uk_mtd_sandbox_mode") == "true"
    assert settings.get("uk_mtd_vrn")
    assert "uk_mtd_client_secret" not in settings


def test_forbidden_without_module(client, admin_headers):
    r = client.get("/api/uk-mtd/logs", headers=admin_headers)
    assert r.status_code == 403
    r = client.get("/api/uk-mtd/vat-return", headers=admin_headers)
    assert r.status_code == 403


def test_vat_boxes_and_sandbox_submit(client, admin_headers):
    _install_uk_mtd(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={
            "uk_mtd_enabled": "true",
            "uk_mtd_sandbox_mode": "true",
            "uk_mtd_vrn": "123456789",
            "company_name": "London Demo Ltd",
        },
    )

    inv = client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_name": "Walk-in Customer",
            "issue_date": "2026-08-01",
            "due_date": "2026-08-15",
            "gst_rate": 20,
            "lines": [
                {"description": "Consulting", "qty": 1, "rate": 1000, "amount": 1000},
            ],
        },
    )
    assert inv.status_code in (200, 201), inv.text
    inv_id = inv.json()["id"]
    posted = client.patch(
        f"/api/invoices/{inv_id}/status",
        headers=admin_headers,
        params={"status": "sent"},
    )
    assert posted.status_code == 200, posted.text

    boxes = client.get(
        "/api/uk-mtd/vat-return?period_key=2026-Q3",
        headers=admin_headers,
    )
    assert boxes.status_code == 200, boxes.text
    data = boxes.json()
    assert data["period_key"] == "2026-Q3"
    assert data["boxes"]["vatDueSales"] == 200.0
    assert data["boxes"]["totalValueSalesExVAT"] == 1000
    assert data["payload"]["periodKey"] == "2026-Q3"
    assert data["payload"]["finalised"] is True

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.text = '{"processingDate":"2026-08-01","formBundleNumber":"999999999999"}'
    mock_resp.json.return_value = {
        "processingDate": "2026-08-01",
        "formBundleNumber": "999999999999",
        "correlationId": "MTD-SBX-TEST-001",
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("services.uk_mtd.httpx.Client", return_value=mock_client):
        sub = client.post(
            "/api/uk-mtd/vat-return/submit?period_key=2026-Q3",
            headers=admin_headers,
        )
    assert sub.status_code == 200, sub.text
    result = sub.json()
    assert result["success"] is True
    assert result["uk_mtd_status"] == "accepted"
    assert result["log_id"]
    assert result["boxes"]["vatDueSales"] == 200.0

    detail = client.get(f"/api/invoices/{inv_id}", headers=admin_headers).json()
    assert detail["uk_mtd_status"] == "accepted"
    assert detail["uk_mtd_period"] == "2026-Q3"

    logs = client.get("/api/uk-mtd/logs", headers=admin_headers)
    assert logs.status_code == 200
    rows = logs.json()
    assert any(row["period_key"] == "2026-Q3" and row["status"] == "accepted" for row in rows)


def test_invoice_sandbox_submit_and_status(client, admin_headers):
    _install_uk_mtd(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={"uk_mtd_enabled": "true", "uk_mtd_vrn": "123456789"},
    )
    inv = client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_name": "Buyer Ltd",
            "issue_date": "2026-05-10",
            "due_date": "2026-05-24",
            "gst_rate": 20,
            "lines": [{"description": "Widget", "qty": 1, "rate": 50, "amount": 50}],
        },
    )
    inv_id = inv.json()["id"]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"correlationId":"MTD-INV-1"}'
    mock_resp.json.return_value = {"correlationId": "MTD-INV-1"}
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("services.uk_mtd.httpx.Client", return_value=mock_client):
        sub = client.post(f"/api/uk-mtd/invoices/{inv_id}/submit", headers=admin_headers)
    assert sub.status_code == 200, sub.text
    data = sub.json()
    assert data["success"] is True
    assert data["uk_mtd_status"] == "accepted"
    assert data["uk_mtd_correlation_id"] == "MTD-INV-1"

    status = client.get(f"/api/uk-mtd/invoices/{inv_id}/status", headers=admin_headers)
    assert status.status_code == 200
    assert status.json()["uk_mtd_status"] == "accepted"


def test_period_helper():
    from services.uk_mtd import hmrc_return_payload, period_for_date, resolve_period

    key, start, end = period_for_date("2026-08-15")
    assert key == "2026-Q3"
    assert start == "2026-07-01"
    assert end == "2026-09-30"
    key2, s2, e2 = resolve_period("2026-Q1")
    assert key2 == "2026-Q1" and s2 == "2026-01-01" and e2 == "2026-03-31"
    payload = hmrc_return_payload("2026-Q3", {
        "vatDueSales": 20.0, "vatDueAcquisitions": 0.0, "totalVatDue": 20.0,
        "vatReclaimedCurrPeriod": 5.0, "netVatDue": 15.0,
        "totalValueSalesExVAT": 100, "totalValuePurchasesExVAT": 25,
        "totalValueGoodsSuppliedExVAT": 0, "totalAcquisitionsExVAT": 0,
    })
    assert payload["finalised"] is True
    assert payload["vatDueSales"] == 20.0
