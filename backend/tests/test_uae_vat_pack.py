"""UAE VAT localization pack — CoA/tax seed + sandbox stub via API."""
from __future__ import annotations


def _install_uae(client, headers):
    r = client.post("/api/modules/uae_vat/install?seed_sample=true", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_install_seeds_tax_codes_and_coa(client, admin_headers):
    body = _install_uae(client, admin_headers)
    assert "uae_vat" in body["installed"]

    taxes = client.get("/api/tax-codes", headers=admin_headers).json()["items"]
    codes = {t["code"] for t in taxes}
    assert "VAT5_OUT" in codes
    assert "VAT5_IN" in codes

    accounts = client.get("/api/accounts", headers=admin_headers).json()
    if isinstance(accounts, dict):
        accounts = accounts.get("items", accounts.get("accounts", []))
    acc_codes = {a["code"] for a in accounts}
    assert "2210" in acc_codes
    assert "1260" in acc_codes


def test_sandbox_test_and_submit(client, admin_headers):
    _install_uae(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={
            "uae_vat_enabled": "true",
            "uae_sandbox_mode": "true",
            "uae_trn": "100000000000003",
            "uae_legal_name": "Acme UAE LLC",
        },
    )

    ping = client.post("/api/uae/test", headers=admin_headers)
    assert ping.status_code == 200, ping.text
    assert ping.json()["ok"] is True
    assert ping.json()["sandbox"] is True

    inv = client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_name": "Dubai Customer",
            "issue_date": "2026-08-01",
            "due_date": "2026-08-15",
            "gst_rate": 5,
            "lines": [
                {"description": "Consulting", "qty": 1, "rate": 1000, "amount": 1000},
            ],
        },
    )
    assert inv.status_code in (200, 201), inv.text
    inv_id = inv.json()["id"]

    sub = client.post(f"/api/uae/invoices/{inv_id}/submit", headers=admin_headers)
    assert sub.status_code == 200, sub.text
    data = sub.json()
    assert data["success"] is True
    assert data["uuid"].startswith("UAE-SBX-")

    logs = client.get("/api/uae/logs", headers=admin_headers)
    assert logs.status_code == 200
    assert any(row["invoice_id"] == inv_id and row["success"] for row in logs.json())
