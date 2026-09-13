"""Unit tests for FBR DI (PRAL v1.12) payload builder and response parser."""
from decimal import Decimal
from types import SimpleNamespace

from services.pra import (
    INVOICE_TYPE_DEBIT,
    INVOICE_TYPE_SALE,
    SALE_STANDARD,
    SALE_THIRD,
    build_di_payload,
    format_rate_desc,
    local_validate_payload,
    parse_di_response,
    scenarios_for,
)


def _invoice(**kwargs):
    inv = SimpleNamespace(
        number="SL-2026-001",
        issue_date="2026-06-22",
        subtotal=Decimal("1000"),
        gst_amount=Decimal("180"),
        total=Decimal("1180"),
        gst_rate=Decimal("18"),
        payment_mode=1,
        buyer_ntn="2046004",
        buyer_cnic=None,
        customer_name="FERTILIZER MANUFAC IRS NEW",
        buyer_registration_type="Registered",
        buyer_province="Sindh",
        di_invoice_type=INVOICE_TYPE_SALE,
        di_invoice_ref_no="",
        di_scenario_id="SN001",
    )
    for k, v in kwargs.items():
        setattr(inv, k, v)
    return inv


def _customer(**kwargs):
    c = SimpleNamespace(
        name="FERTILIZER MANUFAC IRS NEW",
        ntn="2046004",
        cnic=None,
        phone=None,
        address="Karachi",
        registration_type="Registered",
        province="Sindh",
    )
    for k, v in kwargs.items():
        setattr(c, k, v)
    return c


def _line(**kwargs):
    ln = SimpleNamespace(
        product_id=1,
        description="test",
        qty=400,
        unit="pcs",
        amount=Decimal("1000"),
        discount_pct=Decimal("0"),
        tax_code_id=None,
        tax_rate=Decimal("18"),
        tax_amount=Decimal("180"),
        sale_type=SALE_STANDARD,
        hs_code="0101.2100",
        di_uom="Numbers, pieces, units",
        di_rate=None,
        further_tax=0,
        extra_tax=0,
        fed_payable=0,
        st_withheld=0,
        fixed_notified_value=0,
        sro_schedule_no="",
        sro_item_serial="",
    )
    for k, v in kwargs.items():
        setattr(ln, k, v)
    return ln


def _product(**kwargs):
    p = SimpleNamespace(
        hs_code="0101.2100",
        unit="pcs",
        sale_type=SALE_STANDARD,
        di_uom="Numbers, pieces, units",
        fixed_notified_value=None,
        sro_schedule_no=None,
        sro_item_serial=None,
        di_rate=None,
    )
    for k, v in kwargs.items():
        setattr(p, k, v)
    return p


def _config(**kwargs):
    cfg = {
        "sandbox": True,
        "token": "tok",
        "seller_ntn": "8885801",
        "seller_business_name": "Company 8",
        "seller_province": "Sindh",
        "seller_address": "Karachi",
        "business_activity": "Retailer",
        "sector": "Wholesale / Retails",
        "default_scenario": "SN026",
    }
    cfg.update(kwargs)
    return cfg


def test_sn001_registered_standard_rate():
    payload = build_di_payload(
        _invoice(di_scenario_id="SN001"),
        [_line()],
        _customer(),
        {1: _product()},
        {},
        _config(),
    )
    assert payload["invoiceType"] == INVOICE_TYPE_SALE
    assert payload["scenarioId"] == "SN001"
    assert payload["buyerRegistrationType"] == "Registered"
    assert payload["sellerNTNCNIC"] == "8885801"
    assert payload["buyerNTNCNIC"] == "2046004"
    item = payload["items"][0]
    assert item["hsCode"] == "0101.2100"
    assert item["rate"] == "18%"
    assert item["uoM"] == "Numbers, pieces, units"
    assert item["quantity"] == 400
    assert item["valueSalesExcludingST"] == 1000.0
    assert item["salesTaxApplicable"] == 180.0
    assert item["saleType"] == SALE_STANDARD
    assert item["fixedNotifiedValueOrRetailPrice"] == 0.0


def test_sn002_unregistered():
    payload = build_di_payload(
        _invoice(di_scenario_id="SN002", buyer_ntn="1234567", buyer_registration_type="Unregistered"),
        [_line()],
        _customer(ntn="1234567", registration_type="Unregistered"),
        {1: _product()},
        {},
        _config(),
    )
    assert payload["scenarioId"] == "SN002"
    assert payload["buyerRegistrationType"] == "Unregistered"
    assert payload["buyerNTNCNIC"] == "1234567"


def test_sn008_mrp_third_schedule():
    payload = build_di_payload(
        _invoice(di_scenario_id="SN008"),
        [_line(
            sale_type=SALE_THIRD,
            qty=1,
            amount=Decimal("0"),
            tax_amount=Decimal("18"),
            fixed_notified_value=100,
        )],
        _customer(),
        {1: _product(sale_type=SALE_THIRD, fixed_notified_value=100)},
        {},
        _config(),
    )
    item = payload["items"][0]
    assert item["saleType"] == SALE_THIRD
    assert item["valueSalesExcludingST"] == 0.0
    assert item["fixedNotifiedValueOrRetailPrice"] == 100.0
    assert item["salesTaxApplicable"] == 18.0


def test_sn026_and_sn027():
    p26 = build_di_payload(
        _invoice(di_scenario_id="SN026"),
        [_line(qty=123)],
        _customer(),
        {1: _product()},
        {},
        _config(),
    )
    assert p26["scenarioId"] == "SN026"
    p27 = build_di_payload(
        _invoice(di_scenario_id="SN027"),
        [_line(sale_type=SALE_THIRD, qty=1, amount=0, tax_amount=18, fixed_notified_value=100)],
        _customer(),
        {1: _product()},
        {},
        _config(),
    )
    assert p27["scenarioId"] == "SN027"
    assert p27["items"][0]["fixedNotifiedValueOrRetailPrice"] == 100.0


def test_scenario_id_omitted_in_production():
    payload = build_di_payload(
        _invoice(di_scenario_id="SN001"),
        [_line()],
        _customer(),
        {1: _product()},
        {},
        _config(sandbox=False),
    )
    assert "scenarioId" not in payload


def test_debit_note_header():
    payload = build_di_payload(
        _invoice(
            di_invoice_type=INVOICE_TYPE_DEBIT,
            di_invoice_ref_no="7000007DI1747119701593",
            di_scenario_id="SN001",
        ),
        [_line()],
        _customer(),
        {1: _product()},
        {},
        _config(),
    )
    assert payload["invoiceType"] == INVOICE_TYPE_DEBIT
    assert payload["invoiceRefNo"] == "7000007DI1747119701593"


def test_local_validate_sandbox_requires_scenario_and_hs():
    payload = build_di_payload(
        _invoice(di_scenario_id=""),
        [_line(hs_code="")],
        _customer(),
        {1: _product(hs_code="")},
        {},
        _config(),
        include_scenario=False,
        scenario_id="",
    )
    errs = local_validate_payload(payload, sandbox=True)
    assert any("scenarioId" in e for e in errs)
    assert any("HSCode" in e or "0019" in e for e in errs)


def test_local_validate_debit_note_requires_ref():
    payload = build_di_payload(
        _invoice(di_invoice_type=INVOICE_TYPE_DEBIT, di_invoice_ref_no=""),
        [_line()],
        _customer(),
        {1: _product()},
        {},
        _config(),
    )
    errs = local_validate_payload(payload, sandbox=True)
    assert any("0026" in e for e in errs)


def test_parse_valid_post_response():
    parsed = parse_di_response({
        "invoiceNumber": "7000007DI1747119701593",
        "dated": "2025-05-13 12:01:41",
        "validationResponse": {
            "statusCode": "00",
            "status": "Valid",
            "error": "",
            "invoiceStatuses": [{
                "itemSNo": "1",
                "statusCode": "00",
                "status": "Valid",
                "invoiceNo": "7000007DI1747119701593-1",
                "errorCode": "",
                "error": "",
            }],
        },
    })
    assert parsed["ok"] is True
    assert parsed["invoice_number"] == "7000007DI1747119701593"


def test_parse_invalid_header():
    parsed = parse_di_response({
        "dated": "2025-05-13 13:09:05",
        "validationResponse": {
            "statusCode": "01",
            "status": "Invalid",
            "errorCode": "0052",
            "error": "Provide proper HS Code with invoice no. null",
            "invoiceStatuses": None,
        },
    })
    assert parsed["ok"] is False
    assert "0052" in parsed["error"]


def test_parse_invalid_item():
    parsed = parse_di_response({
        "dated": "2025-05-13 13:10:00",
        "validationResponse": {
            "statusCode": "00",
            "status": "invalid",
            "error": "",
            "invoiceStatuses": [{
                "itemSNo": "1",
                "statusCode": "01",
                "status": "Invalid",
                "invoiceNo": None,
                "errorCode": "0046",
                "error": "Provide rate.",
            }],
        },
    })
    assert parsed["ok"] is False
    assert "0046" in parsed["error"]


def test_format_rate_exempt_and_percent():
    assert format_rate_desc(18, SALE_STANDARD) == "18%"
    assert format_rate_desc(0, "Exempt goods") == "Exempt"
    assert format_rate_desc("18%") == "18%"


def test_retailer_scenarios_include_26_27_28():
    ids = {row["id"] for row in scenarios_for("Retailer", "Wholesale / Retails")}
    assert {"SN026", "SN027", "SN028", "SN008"} <= ids


def test_manufacturer_steel_excludes_retailer_only():
    ids = {row["id"] for row in scenarios_for("Manufacturer", "Steel")}
    assert "SN003" in ids
    assert "SN026" not in ids


def test_seller_ntn_strips_hyphens():
    payload = build_di_payload(
        _invoice(),
        [_line()],
        _customer(),
        {1: _product()},
        {},
        _config(seller_ntn="8885801"),
    )
    assert payload["sellerNTNCNIC"] == "8885801"
    from services.pra import _digits
    assert _digits("888-5801-1") == "88858011"


def test_payment_mode_not_in_payload():
    payload = build_di_payload(
        _invoice(payment_mode=1),
        [_line()],
        _customer(),
        {1: _product()},
        {},
        _config(),
    )
    blob = str(payload).lower()
    assert "paymentmode" not in blob
    assert "posid" not in blob
    assert "usin" not in blob


def test_fetch_reference_fallback_without_token():
    from services.pra import fetch_reference, _REF_CACHE
    _REF_CACHE.clear()
    data = fetch_reference("provinces", "")
    assert any(row.get("stateProvinceDesc") == "Punjab" for row in data)
    uom = fetch_reference("uom", "")
    assert any("Numbers" in (row.get("description") or "") for row in uom)


def test_submit_validate_then_post(client, admin_headers, monkeypatch):
    calls: list[str] = []

    def fake_post(url, payload, token, timeout=20.0):
        calls.append(url)
        assert payload["invoiceType"] == INVOICE_TYPE_SALE
        assert payload["scenarioId"] == "SN001"
        assert payload["items"][0]["hsCode"] == "0101.2100"
        return 200, {
            "invoiceNumber": "7000007DI1747119701593",
            "dated": "2025-05-13 12:01:41",
            "validationResponse": {
                "statusCode": "00",
                "status": "Valid",
                "error": "",
                "invoiceStatuses": [{"itemSNo": "1", "statusCode": "00", "status": "Valid"}],
            },
        }, "{}"

    monkeypatch.setattr("services.pra._post_json", fake_post)
    h = admin_headers
    client.patch("/api/settings", headers=h, json={
        "pra_enabled": "true",
        "pra_ntn": "8885801",
        "pra_api_token": "tok",
        "pra_sandbox_mode": "true",
        "pra_seller_province": "Sindh",
        "company_name": "Company 8",
        "pra_business_activity": "Manufacturer",
        "pra_sector": "All Other Sectors",
    })
    c = client.post("/api/customers", headers=h, json={
        "name": "Buyer Co",
        "ntn": "2046004",
        "registration_type": "Registered",
        "province": "Sindh",
    }).json()
    p = client.post("/api/products", headers=h, json={
        "name": "Widget",
        "hs_code": "0101.2100",
        "sale_type": SALE_STANDARD,
        "product_type": "service",
    }).json()
    created = client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"],
        "issue_date": "2026-06-22",
        "gst_rate": 18,
        "buyer_registration_type": "Registered",
        "buyer_province": "Sindh",
        "di_invoice_type": INVOICE_TYPE_SALE,
        "di_scenario_id": "SN001",
        "lines": [{
            "product_id": p["id"],
            "description": "test",
            "qty": 400,
            "rate": 2.5,
            "hs_code": "0101.2100",
            "sale_type": SALE_STANDARD,
        }],
    })
    assert created.status_code == 200, created.text
    inv_id = created.json()["id"]
    r = client.post(f"/api/pra/invoices/{inv_id}/submit", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["pra_status"] == "submitted"
    assert body["pra_fiscal_number"] == "7000007DI1747119701593"
    assert len(calls) == 2
    assert "validateinvoicedata" in calls[0]
    assert "postinvoicedata" in calls[1]


def test_submit_debit_note_requires_ref_then_posts(client, admin_headers, monkeypatch):
    calls: list[dict] = []

    def fake_post(url, payload, token, timeout=20.0):
        calls.append(payload)
        return 200, {
            "invoiceNumber": "7000007DI1747119701594",
            "validationResponse": {
                "statusCode": "00",
                "status": "Valid",
                "invoiceStatuses": [{"itemSNo": "1", "statusCode": "00", "status": "Valid"}],
            },
        }, "{}"

    monkeypatch.setattr("services.pra._post_json", fake_post)
    h = admin_headers
    client.patch("/api/settings", headers=h, json={
        "pra_enabled": "true",
        "pra_ntn": "8885801",
        "pra_api_token": "tok",
        "pra_sandbox_mode": "true",
        "pra_seller_province": "Sindh",
        "company_name": "Company 8",
    })
    c = client.post("/api/customers", headers=h, json={
        "name": "Buyer Co", "ntn": "2046004", "registration_type": "Registered", "province": "Sindh",
    }).json()
    missing = client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"],
        "issue_date": "2026-06-22",
        "gst_rate": 18,
        "di_invoice_type": INVOICE_TYPE_DEBIT,
        "di_invoice_ref_no": "",
        "di_scenario_id": "SN001",
        "buyer_registration_type": "Registered",
        "buyer_province": "Sindh",
        "lines": [{"description": "return", "qty": 1, "rate": 100, "hs_code": "0101.2100"}],
    })
    assert missing.status_code == 200, missing.text
    bad = client.post(f"/api/pra/invoices/{missing.json()['id']}/submit", headers=h)
    assert bad.status_code == 200
    assert bad.json()["success"] is False
    assert calls == []

    ok = client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"],
        "issue_date": "2026-06-22",
        "gst_rate": 18,
        "di_invoice_type": INVOICE_TYPE_DEBIT,
        "di_invoice_ref_no": "7000007DI1747119701593",
        "di_scenario_id": "SN001",
        "buyer_registration_type": "Registered",
        "buyer_province": "Sindh",
        "lines": [{"description": "return", "qty": 1, "rate": 100, "hs_code": "0101.2100"}],
    })
    assert ok.status_code == 200, ok.text
    posted = client.post(f"/api/pra/invoices/{ok.json()['id']}/submit", headers=h)
    assert posted.json()["success"] is True
    assert calls[0]["invoiceType"] == INVOICE_TYPE_DEBIT
    assert calls[0]["invoiceRefNo"] == "7000007DI1747119701593"


def test_ref_provinces_fallback(client, admin_headers):
    r = client.get("/api/pra/ref/provinces", headers=admin_headers)
    assert r.status_code == 200
    names = [row.get("stateProvinceDesc") for row in r.json()]
    assert "Punjab" in names
    assert "Sindh" in names


def test_scenarios_retailer_default_sn026(client, admin_headers):
    client.patch("/api/settings", headers=admin_headers, json={
        "pra_enabled": "true",
        "pra_ntn": "8885801",
        "pra_business_activity": "Retailer",
        "pra_sector": "Wholesale / Retails",
    })
    r = client.get("/api/pra/scenarios", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["default"] == "SN026"
    ids = {row["id"] for row in body["items"]}
    assert {"SN026", "SN027", "SN028"} <= ids
