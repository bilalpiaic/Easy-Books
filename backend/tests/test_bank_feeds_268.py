"""#268 Bank feeds harden: rules priority, OFX/CSV mapping, confidence accept, de-dupe."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str = "bf268@co.test", company: str = "FeedCo"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": company,
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _bank(client, auth) -> int:
    r = client.post(
        "/api/bank-accounts",
        headers=auth,
        json={"name": "Checking", "account_number": "99"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _expense_account(client, auth) -> int:
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    # Prefer a leaf expense account
    for a in accounts:
        if a.get("type") == "Expense" and not a.get("is_group"):
            return a["id"]
    for a in accounts:
        if not a.get("is_group"):
            return a["id"]
    raise AssertionError("no accounts")


SAMPLE_OFX = """OFXHEADER:100
DATA:OFXSGML
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260504
<TRNAMT>-200.00
<FITID>OFX-RENT-1
<NAME>Office rent
<MEMO>Office rent May
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260502
<TRNAMT>500.00
<FITID>OFX-PAY-1
<NAME>Customer payment Alice
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


def test_rule_priority_applies_on_import(client: TestClient):
    auth = _auth(client, "rules@co.test", "RulesCo")
    acct_id = _bank(client, auth)
    gl_a = _expense_account(client, auth)
    # Second account — pick another leaf if possible
    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    gl_b = next(
        (a["id"] for a in accounts if not a.get("is_group") and a["id"] != gl_a),
        gl_a,
    )

    # Lower priority number wins
    r = client.post(
        "/api/banking/rules",
        headers=auth,
        json={"pattern": "stripe", "account_id": gl_a, "priority": 10, "is_active": True},
    )
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/banking/rules",
        headers=auth,
        json={"pattern": "stripe", "account_id": gl_b, "priority": 50, "is_active": True},
    )
    assert r.status_code == 201, r.text

    csv = "date,description,debit,credit,balance\n2026-05-03,Stripe payout,0,1000,2500\n"
    files = {"file": ("s.csv", io.BytesIO(csv.encode()), "text/csv")}
    imp = client.post(
        "/api/bank-imports",
        headers=auth,
        data={"bank_account_id": str(acct_id)},
        files=files,
    )
    assert imp.status_code == 201, imp.text
    lines = client.get(f"/api/bank-imports/{imp.json()['id']}/lines", headers=auth).json()
    assert len(lines) == 1
    assert lines[0]["categorized_account_id"] == gl_a


def test_ofx_import_and_duplicate_fitid(client: TestClient):
    auth = _auth(client, "ofx@co.test", "OfxCo")
    acct_id = _bank(client, auth)

    files = {"file": ("stmt.ofx", io.BytesIO(SAMPLE_OFX.encode()), "application/x-ofx")}
    r = client.post(
        "/api/bank-imports",
        headers=auth,
        data={"bank_account_id": str(acct_id)},
        files=files,
    )
    assert r.status_code == 201, r.text
    imp = r.json()
    assert imp["line_count"] == 2
    lines = client.get(f"/api/bank-imports/{imp['id']}/lines", headers=auth).json()
    assert {l["external_id"] for l in lines} == {"OFX-RENT-1", "OFX-PAY-1"}
    rent = next(l for l in lines if l["external_id"] == "OFX-RENT-1")
    assert float(rent["debit"]) == 200.0

    # Same file hash → 409
    files2 = {"file": ("stmt.ofx", io.BytesIO(SAMPLE_OFX.encode()), "application/x-ofx")}
    r2 = client.post(
        "/api/bank-imports",
        headers=auth,
        data={"bank_account_id": str(acct_id)},
        files=files2,
    )
    assert r2.status_code == 409


def test_csv_column_mapping(client: TestClient):
    auth = _auth(client, "map@co.test", "MapCo")
    acct_id = _bank(client, auth)
    csv = "TxnDate,Narration,SignedAmt\n2026-05-01,Coffee,-12.50\n"
    files = {"file": ("alt.csv", io.BytesIO(csv.encode()), "text/csv")}
    r = client.post(
        "/api/bank-imports",
        headers=auth,
        data={
            "bank_account_id": str(acct_id),
            "date_col": "TxnDate",
            "description_col": "Narration",
            "amount_col": "SignedAmt",
        },
        files=files,
    )
    assert r.status_code == 201, r.text
    lines = client.get(f"/api/bank-imports/{r.json()['id']}/lines", headers=auth).json()
    assert len(lines) == 1
    assert float(lines[0]["debit"]) == 12.5
    assert lines[0]["description"] == "Coffee"


def test_confidence_accept_reject_audited(client: TestClient):
    auth = _auth(client, "conf@co.test", "ConfCo")
    acct_id = _bank(client, auth)

    accounts = client.get("/api/accounts", headers=auth).json()["items"]
    cash = next(a for a in accounts if a["code"] == "1000")
    sales = next(a for a in accounts if a["code"] == "4000")
    tid = cash["tenant_id"]
    r = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "tenant_id": tid,
            "date": "2026-05-02",
            "description": "Customer payment Alice",
            "entries": [
                {"tenant_id": tid, "account_id": cash["id"], "debit": 500, "credit": 0},
                {"tenant_id": tid, "account_id": sales["id"], "debit": 0, "credit": 500},
            ],
        },
    )
    assert r.status_code == 200, r.text
    txn_id = r.json()["id"]

    csv = "date,description,debit,credit,balance\n2026-05-02,Customer payment Alice,0,500,1500\n"
    files = {"file": ("one.csv", io.BytesIO(csv.encode()), "text/csv")}
    imp = client.post(
        "/api/bank-imports",
        headers=auth,
        data={"bank_account_id": str(acct_id)},
        files=files,
    ).json()

    r = client.post(f"/api/bank-imports/{imp['id']}/auto-match", headers=auth)
    assert r.status_code == 200, r.text
    # Exact amount + date + desc overlap → auto-accept ≥90
    assert r.json()["newly_matched"] == 1

    lines = client.get(f"/api/bank-imports/{imp['id']}/lines", headers=auth).json()
    assert lines[0]["is_matched"] is True
    assert lines[0]["match_status"] == "accepted"
    assert lines[0]["match_confidence"] >= 90
    assert lines[0]["matched_transaction_id"] == txn_id

    # Reject clears
    r = client.post(f"/api/statement-lines/{lines[0]['id']}/reject", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["is_matched"] is False
    assert r.json()["match_status"] == "rejected"


def test_rule_amount_filter_and_crud(client: TestClient):
    auth = _auth(client, "amt@co.test", "AmtCo")
    gl = _expense_account(client, auth)
    r = client.post(
        "/api/banking/rules",
        headers=auth,
        json={
            "pattern": "rent",
            "account_id": gl,
            "priority": 5,
            "match_amount": 200,
            "create_expense_draft": True,
        },
    )
    assert r.status_code == 201, r.text
    rule_id = r.json()["id"]

    r = client.put(
        f"/api/banking/rules/{rule_id}",
        headers=auth,
        json={"priority": 1},
    )
    assert r.status_code == 200
    assert r.json()["priority"] == 1

    rules = client.get("/api/banking/rules", headers=auth).json()
    assert any(x["id"] == rule_id for x in rules)

    r = client.delete(f"/api/banking/rules/{rule_id}", headers=auth)
    assert r.status_code == 204
