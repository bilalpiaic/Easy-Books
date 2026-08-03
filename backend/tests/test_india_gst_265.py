"""India GST country pack (#265) — place-of-supply branching + GSTR summary."""
from __future__ import annotations

from decimal import Decimal


def _install_in_gst(client, headers):
    r = client.post("/api/modules/in_gst/install?seed_sample=true", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_install_seeds_cgst_sgst_igst(client, admin_headers):
    body = _install_in_gst(client, admin_headers)
    assert "in_gst" in body["installed"]

    taxes = client.get("/api/tax-codes", headers=admin_headers).json()["items"]
    codes = {t["code"] for t in taxes}
    assert "CGST_9" in codes
    assert "SGST_9" in codes
    assert "IGST_18" in codes


def test_place_of_supply_intrastate_cgst_sgst(client, admin_headers):
    _install_in_gst(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={"in_gst_enabled": "true", "in_state_code": "27", "in_gstin": "27AAAAA0000A1Z5"},
    )

    sug = client.post(
        "/api/india-gst/suggest-tax",
        headers=admin_headers,
        json={"seller_state": "27", "buyer_state": "27", "taxable": 1000},
    )
    assert sug.status_code == 200, sug.text
    data = sug.json()
    assert data["interstate"] is False
    codes = [leg["code"] for leg in data["legs"]]
    assert codes == ["CGST_9", "SGST_9"]
    assert abs(data["total_tax"] - 180.0) < 0.01
    assert abs(data["legs"][0]["amount"] - 90.0) < 0.01
    assert abs(data["legs"][1]["amount"] - 90.0) < 0.01


def test_place_of_supply_interstate_igst(client, admin_headers):
    _install_in_gst(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={"in_gst_enabled": "true", "in_state_code": "27"},
    )

    sug = client.post(
        "/api/india-gst/suggest-tax",
        headers=admin_headers,
        json={"seller_state": "27", "buyer_state": "29", "taxable": 1000},
    )
    assert sug.status_code == 200, sug.text
    data = sug.json()
    assert data["interstate"] is True
    assert len(data["legs"]) == 1
    assert data["legs"][0]["code"] == "IGST_18"
    assert abs(data["total_tax"] - 180.0) < 0.01


def test_invoice_auto_apply_interstate_and_gstr_summary(client, admin_headers):
    _install_in_gst(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={"in_gst_enabled": "true", "in_state_code": "27", "in_gstin": "27AAAAA0000A1Z5"},
    )

    cust = client.post(
        "/api/customers",
        headers=admin_headers,
        json={
            "name": "Bangalore Buyer",
            "gstin": "29BBBBB0000B1Z5",
            "state_code": "29",
        },
    )
    assert cust.status_code in (200, 201), cust.text
    cust_id = cust.json()["id"]

    inv = client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_id": cust_id,
            "issue_date": "2026-08-01",
            "due_date": "2026-08-15",
            "gst_rate": 0,
            "lines": [
                {"description": "Consulting", "qty": 1, "rate": 1000, "amount": 1000},
            ],
        },
    )
    assert inv.status_code in (200, 201), inv.text
    body = inv.json()
    assert abs(float(body["gst_amount"]) - 180.0) < 0.02
    assert abs(float(body["total"]) - 1180.0) < 0.02

    detail = client.get(f"/api/invoices/{body['id']}", headers=admin_headers).json()
    assert detail["lines"][0]["tax_code_id"] is not None

    gstr = client.get(
        "/api/india-gst/gstr1?start=2026-08-01&end=2026-08-31",
        headers=admin_headers,
    )
    assert gstr.status_code == 200, gstr.text
    summary = gstr.json()
    assert summary["totals"]["invoice_count"] >= 1
    row = next(r for r in summary["b2b"] if r["invoice_id"] == body["id"])
    assert abs(row["igst"] - 180.0) < 0.02
    assert abs(row["cgst"]) < 0.02
    assert abs(row["sgst"]) < 0.02
    assert row["gstin"] == "29BBBBB0000B1Z5"


def test_invoice_auto_apply_intrastate_mirrors_sgst(client, admin_headers):
    _install_in_gst(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={"in_gst_enabled": "true", "in_state_code": "27"},
    )

    cust = client.post(
        "/api/customers",
        headers=admin_headers,
        json={"name": "Mumbai Buyer", "gstin": "27CCCCC0000C1Z5", "state_code": "27"},
    )
    assert cust.status_code in (200, 201), cust.text
    cust_id = cust.json()["id"]

    inv = client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_id": cust_id,
            "issue_date": "2026-08-02",
            "due_date": "2026-08-16",
            "gst_rate": 0,
            "lines": [
                {"description": "Services", "qty": 1, "rate": 2000, "amount": 2000},
            ],
        },
    )
    assert inv.status_code in (200, 201), inv.text
    body = inv.json()
    assert abs(float(body["gst_amount"]) - 360.0) < 0.02

    gstr = client.get(
        "/api/india-gst/gstr1?start=2026-08-01&end=2026-08-31",
        headers=admin_headers,
    )
    assert gstr.status_code == 200, gstr.text
    row = next(r for r in gstr.json()["b2b"] if r["invoice_id"] == body["id"])
    assert abs(row["cgst"] - 180.0) < 0.02
    assert abs(row["sgst"] - 180.0) < 0.02
    assert abs(row["igst"]) < 0.02


def test_unit_place_of_supply_helper():
    from services.india_gst import place_of_supply_interstate

    assert place_of_supply_interstate("27", "29") is True
    assert place_of_supply_interstate("27", "27") is False
    assert place_of_supply_interstate("", "29") is False
    assert place_of_supply_interstate("27", None) is False


def test_gstr3b_aggregates(client, admin_headers):
    _install_in_gst(client, admin_headers)
    client.patch(
        "/api/settings",
        headers=admin_headers,
        json={"in_gst_enabled": "true", "in_state_code": "27"},
    )
    cust = client.post(
        "/api/customers",
        headers=admin_headers,
        json={"name": "Local Co", "state_code": "27", "gstin": "27DDDDD0000D1Z5"},
    ).json()
    client.post(
        "/api/invoices",
        headers=admin_headers,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-08-03",
            "due_date": "2026-08-17",
            "gst_rate": 0,
            "lines": [{"description": "Item", "qty": 1, "rate": 500, "amount": 500}],
        },
    )
    r = client.get(
        "/api/india-gst/gstr3b?start=2026-08-01&end=2026-08-31",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    out = r.json()["outward_supplies"]
    assert out["taxable"] >= 500
    assert abs((out["cgst"] + out["sgst"] + out["igst"]) - out["total_tax"]) < 0.02
    assert Decimal(str(out["total_tax"])) >= 0
