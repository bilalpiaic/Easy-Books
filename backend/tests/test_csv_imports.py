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
