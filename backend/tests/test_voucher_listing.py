"""Tests for voucher-type surfacing in the journal listing and General Ledger
endpoints (Task 4 of voucher-series feature).

Coverage:
- Journal listing (/api/reports/journal) returns voucher_type and
  legacy_jv_number on each row.
- ?voucher_type=SL filter narrows results to SL rows only.
- General Ledger (/api/reports/ledger) entries include voucher_type.
"""


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_accounts(client, h):
    """Return Cash (1000) and Revenue (4000) account ids."""
    r = client.get("/api/accounts", headers=h)
    assert r.status_code == 200, r.text
    accounts = r.json()["items"]
    cash = next(a for a in accounts if a["code"] == "1000")
    revenue = next(a for a in accounts if a["code"] == "4000")
    return cash, revenue


def _post_manual_jv(client, h):
    """Post a balanced manual JV (will be type JV)."""
    cash, revenue = _get_accounts(client, h)
    r = client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01", "description": "Manual JV",
        "entries": [
            {"account_id": cash["id"], "debit": 10, "credit": 0},
            {"account_id": revenue["id"], "debit": 0, "credit": 10},
        ],
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_and_post_invoice(client, h):
    """Create a customer, service product, and post an invoice (will be type SL)."""
    cust = client.post("/api/customers", headers=h, json={"name": "Test Customer"}).json()
    prod = client.post("/api/products", headers=h, json={
        "name": "Widget", "product_type": "service", "sale_price": 100,
    }).json()
    r = client.post("/api/invoices", headers=h, json={
        "customer_id": cust["id"],
        "issue_date": "2026-04-02",
        "gst_rate": 0,
        "lines": [{"product_id": prod["id"], "description": "service", "qty": 1, "rate": 100}],
    })
    assert r.status_code == 201, r.text
    return r.json()


# ── Journal listing tests ──────────────────────────────────────────────────────


def test_journal_listing_returns_voucher_type(client, admin_headers):
    """Every row in /api/reports/journal must carry voucher_type."""
    _post_manual_jv(client, admin_headers)

    r = client.get("/api/reports/journal", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] > 0
    for item in data["items"]:
        assert "voucher_type" in item, f"voucher_type missing from row: {item}"


def test_journal_listing_returns_legacy_jv_number(client, admin_headers):
    """Every row must carry legacy_jv_number (may be None for new txns)."""
    _post_manual_jv(client, admin_headers)

    r = client.get("/api/reports/journal", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] > 0
    for item in data["items"]:
        assert "legacy_jv_number" in item, f"legacy_jv_number missing from row: {item}"


def test_journal_listing_voucher_type_filter_sl(client, admin_headers):
    """?voucher_type=SL must narrow results to only SL rows."""
    # Post a manual JV (type=JV) and an invoice (type=SL)
    _post_manual_jv(client, admin_headers)
    _create_and_post_invoice(client, admin_headers)

    # Without filter — should have both JV and SL rows
    all_r = client.get("/api/reports/journal", headers=admin_headers)
    all_data = all_r.json()
    all_types = {item["voucher_type"] for item in all_data["items"]}
    assert "JV" in all_types, "Expected JV rows in unfiltered listing"
    assert "SL" in all_types, "Expected SL rows in unfiltered listing"

    # With ?voucher_type=SL — only SL rows
    sl_r = client.get("/api/reports/journal?voucher_type=SL", headers=admin_headers)
    assert sl_r.status_code == 200, sl_r.text
    sl_data = sl_r.json()
    assert sl_data["total"] > 0, "Expected some SL rows"
    for item in sl_data["items"]:
        assert item["voucher_type"] == "SL", (
            f"Expected voucher_type=SL, got {item['voucher_type']}"
        )


def test_journal_listing_voucher_type_filter_excludes_others(client, admin_headers):
    """Filtering by JV should exclude SL rows."""
    _post_manual_jv(client, admin_headers)
    _create_and_post_invoice(client, admin_headers)

    jv_r = client.get("/api/reports/journal?voucher_type=JV", headers=admin_headers)
    assert jv_r.status_code == 200, jv_r.text
    jv_data = jv_r.json()
    assert jv_data["total"] > 0, "Expected some JV rows"
    for item in jv_data["items"]:
        assert item["voucher_type"] == "JV", (
            f"Expected voucher_type=JV, got {item['voucher_type']}"
        )


# ── General Ledger tests ───────────────────────────────────────────────────────


def test_ledger_entries_include_voucher_type(client, admin_headers):
    """Each entry in /api/reports/ledger must carry voucher_type."""
    # Post an invoice so we have at least one entry
    _create_and_post_invoice(client, admin_headers)

    # Get accounts — find AR (1100) or Revenue (4000) which are touched by an invoice
    accts_r = client.get("/api/accounts?limit=500", headers=admin_headers)
    accts = accts_r.json()["items"]

    # Prefer AR (code 1100) then Revenue (code 4000) — both are touched by invoice posting
    target = (
        next((a for a in accts if a["code"] == "1100"), None)
        or next((a for a in accts if a["code"] == "4000"), None)
    )
    assert target is not None, "Expected AR (1100) or Revenue (4000) account from seeded CoA"

    r = client.get(
        f"/api/reports/ledger?account_id={target['id']}&start=2026-01-01&end=2026-12-31",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] > 0, f"Expected ledger data for account {target['code']}"

    entries = data["items"][0]["entries"]
    assert len(entries) > 0, f"Expected entries for account {target['code']}"
    for entry in entries:
        assert "voucher_type" in entry, (
            f"voucher_type missing from ledger entry: {entry}"
        )
