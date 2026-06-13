"""CSV bulk import — field-sync tests (accounts, products, transactions, compat)."""
import io
import csv as _csv_mod


def _csv(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    _csv_mod.writer(buf).writerows(rows)
    return buf.getvalue().encode()


def _upload(client, entity: str, rows: list[list[str]], headers: dict):
    data = _csv(rows)
    return client.post(
        f"/api/import/{entity}",
        headers=headers,
        files={"file": (f"{entity}.csv", data, "text/csv")},
    )


# ── Accounts ──────────────────────────────────────────────────────────────────

def test_import_accounts_parent_code(client, admin_headers):
    """parent_code in the CSV must wire parent_id after import.

    Uses codes in the 9xx/91xx range which are not part of the default seeded CoA.
    """
    h = admin_headers
    r = _upload(client, "accounts", [
        ["code", "name", "type", "parent_code", "is_group", "is_memo"],
        ["910",  "Test Assets Group", "Asset", "",    "true",  "false"],
        ["9110", "Test Cash",         "Asset", "910", "false", "false"],
        ["9120", "Test Bank",         "Asset", "910", "false", "false"],
    ], h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 3, body
    # no hard errors (parent_code resolved from same batch)
    assert body["errors"] == [], body["errors"]

    accounts = client.get("/api/accounts", headers=h).json()["items"]
    by_code = {a["code"]: a for a in accounts}

    parent = by_code["910"]
    assert parent["is_group"] is True

    assert by_code["9110"]["parent_id"] == parent["id"]
    assert by_code["9120"]["parent_id"] == parent["id"]


def test_import_accounts_is_group_and_is_memo(client, admin_headers):
    """is_group and is_memo are written to the Account row.

    Uses codes in the 9xx range which are not part of the default seeded CoA.
    """
    h = admin_headers
    r = _upload(client, "accounts", [
        ["code", "name",              "type",    "parent_code", "is_group", "is_memo"],
        ["920",  "Test Memo Acct",    "Asset",   "",            "false",    "true"],
        ["921",  "Test Group Only",   "Expense", "",            "true",     "false"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2

    accounts = client.get("/api/accounts", headers=h).json()["items"]
    by_code = {a["code"]: a for a in accounts}

    assert by_code["920"]["is_memo"] is True
    assert by_code["920"]["is_group"] is False
    assert by_code["921"]["is_group"] is True
    assert by_code["921"]["is_memo"] is False


# ── Products ──────────────────────────────────────────────────────────────────

def test_import_products_category_name(client, admin_headers):
    """category_name resolves to category_id on import."""
    h = admin_headers
    cat = client.post("/api/product-categories", json={"name": "Electronics"}, headers=h).json()

    r = _upload(client, "products", [
        ["code",    "name",     "unit", "product_type", "default_rate", "reorder_level", "category_name", "is_deferred", "recognition_months"],
        ["EL-001", "Gadget A", "pcs",  "stock",        "1500",         "10",            "Electronics",   "false",       ""],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    assert r.json()["errors"] == []

    products = client.get("/api/products", headers=h).json()
    items = products if isinstance(products, list) else products.get("items", products)
    gadget = next(p for p in items if p["code"] == "EL-001")
    assert gadget["category_id"] == cat["id"]


def test_import_products_unknown_category(client, admin_headers):
    """An unknown category_name causes a row-level error; no product is created."""
    h = admin_headers
    r = _upload(client, "products", [
        ["code",    "name",      "unit", "product_type", "default_rate", "reorder_level", "category_name", "is_deferred", "recognition_months"],
        ["XX-001", "Unknown Cat", "pcs", "stock",        "100",          "0",             "DoesNotExist",  "false",       ""],
    ], h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 0
    assert len(body["errors"]) == 1
    assert "DoesNotExist" in body["errors"][0]["message"]


def test_import_products_is_deferred(client, admin_headers):
    """is_deferred=true and recognition_months=6 are written to the Product row."""
    h = admin_headers
    r = _upload(client, "products", [
        ["code",    "name",               "unit", "product_type", "default_rate", "reorder_level", "category_name", "is_deferred", "recognition_months"],
        ["SV-001", "Annual Maintenance", "hrs",  "service",      "50000",        "0",             "",              "true",        "6"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    assert r.json()["errors"] == []

    products = client.get("/api/products", headers=h).json()
    items = products if isinstance(products, list) else products.get("items", products)
    svc = next(p for p in items if p["code"] == "SV-001")
    assert svc["is_deferred"] is True
    assert svc["recognition_months"] == 6


# ── Transactions ──────────────────────────────────────────────────────────────

def test_import_transactions_voucher_type(client, admin_headers):
    """A CSV with voucher_type=SL posts the transaction with that voucher series."""
    h = admin_headers
    # Create two leaf accounts for a balanced JV
    ar = client.post("/api/accounts", headers=h, json={"code": "9810", "name": "AR Test", "type": "Asset"}).json()
    rev = client.post("/api/accounts", headers=h, json={"code": "9820", "name": "Rev Test", "type": "Revenue"}).json()

    r = _upload(client, "transactions", [
        ["date",       "description", "account_code", "debit", "credit", "voucher_type"],
        ["2025-03-01", "Test sale",   "9810",         "5000",  "0",      "SL"],
        ["2025-03-01", "Test sale",   "9820",         "0",     "5000",   "SL"],
    ], h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 1, body
    assert body["errors"] == []

    journal = client.get("/api/reports/journal?limit=50", headers=h).json()
    rows = journal if isinstance(journal, list) else journal.get("items", journal)
    assert any(row["voucher_type"] == "SL" for row in rows), rows


def test_import_transactions_default_voucher_type(client, admin_headers):
    """Transactions without voucher_type column default to JV."""
    h = admin_headers
    acct1 = client.post("/api/accounts", headers=h, json={"code": "9830", "name": "Cash Def", "type": "Asset"}).json()
    acct2 = client.post("/api/accounts", headers=h, json={"code": "9840", "name": "Eq Def", "type": "Equity"}).json()

    r = _upload(client, "transactions", [
        ["date",       "description",   "account_code", "debit", "credit"],
        ["2025-04-01", "Default VT",    "9830",         "2000",  "0"],
        ["2025-04-01", "Default VT",    "9840",         "0",     "2000"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    assert r.json()["errors"] == []

    journal = client.get("/api/reports/journal?limit=50", headers=h).json()
    rows = journal if isinstance(journal, list) else journal.get("items", journal)
    matching = [row for row in rows if row.get("description") == "Default VT"]
    assert all(row["voucher_type"] == "JV" for row in matching), matching


def test_import_transactions_invalid_voucher_type(client, admin_headers):
    """An invalid voucher_type causes a group-level error; transaction not created."""
    h = admin_headers
    acct1 = client.post("/api/accounts", headers=h, json={"code": "9850", "name": "Cash Inv", "type": "Asset"}).json()
    acct2 = client.post("/api/accounts", headers=h, json={"code": "9860", "name": "Rev Inv", "type": "Revenue"}).json()

    r = _upload(client, "transactions", [
        ["date",       "description",    "account_code", "debit", "credit", "voucher_type"],
        ["2025-05-01", "Bad VT entry",   "9850",         "1000",  "0",      "XX"],
        ["2025-05-01", "Bad VT entry",   "9860",         "0",     "1000",   "XX"],
    ], h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 0
    assert len(body["errors"]) == 1
    assert "XX" in body["errors"][0]["message"]


# ── Backward compatibility ────────────────────────────────────────────────────

def test_import_backward_compat_all_entities(client, admin_headers):
    """Old-style CSVs (no new columns) import cleanly for all five entities."""
    h = admin_headers

    # Accounts — original 3-column format
    r = _upload(client, "accounts", [
        ["code", "name",              "type"],
        ["8810", "Compat Cash",       "Asset"],
        ["8820", "Compat Equity",     "Equity"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2, r.json()
    assert r.json()["errors"] == []

    # Customers — original 5-column format
    r = _upload(client, "customers", [
        ["name",          "email",              "phone",          "address",  "opening_balance"],
        ["Compat Cust",   "compat@example.com", "0300-0000000",   "Karachi",  "0"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1

    # Vendors — original 5-column format
    r = _upload(client, "vendors", [
        ["name",          "email",               "phone",         "address",    "opening_balance"],
        ["Compat Vend",   "vcompat@example.com", "0311-0000000",  "Lahore",     "0"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1

    # Products — original 6-column format
    r = _upload(client, "products", [
        ["code",    "name",         "unit", "product_type", "default_rate", "reorder_level"],
        ["CP-001", "Compat Widget", "pcs",  "stock",        "100",          "5"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1

    # Transactions — original 5-column format
    acct1 = client.post("/api/accounts", headers=h, json={"code": "9910", "name": "Compat Cash Acct", "type": "Asset"}).json()
    acct2 = client.post("/api/accounts", headers=h, json={"code": "9920", "name": "Compat Eq Acct", "type": "Equity"}).json()
    r = _upload(client, "transactions", [
        ["date",       "description",  "account_code", "debit", "credit"],
        ["2025-06-01", "Compat entry", "9910",         "1000",  "0"],
        ["2025-06-01", "Compat entry", "9920",         "0",     "1000"],
    ], h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    assert r.json()["errors"] == []
