"""Bank accounts: 1:1 dedicated CoA leaves + multi-bank demo seed."""
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import Account, BankAccount, JournalEntry
from scripts.seed_demo import seed_one_tenant


def test_create_bank_auto_creates_dedicated_coa_leaf(client: TestClient, admin_headers):
    r = client.post(
        "/api/bank-accounts",
        headers=admin_headers,
        json={"name": "HBL Operating", "bank_name": "HBL", "account_number": "111"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["coa_account_id"] is not None

    coa = client.get("/api/accounts", headers=admin_headers).json()["items"]
    leaf = next(a for a in coa if a["id"] == body["coa_account_id"])
    assert leaf["type"] == "Asset"
    assert leaf.get("is_group") is False
    assert "HBL" in leaf["name"] or leaf["name"] == "HBL Operating"


def test_two_banks_cannot_share_same_coa_leaf(client: TestClient, admin_headers):
    coa = client.get("/api/accounts", headers=admin_headers).json()["items"]
    bank1010 = next(a for a in coa if a["code"] == "1010")

    r1 = client.post(
        "/api/bank-accounts",
        headers=admin_headers,
        json={"name": "Bank A", "coa_account_id": bank1010["id"]},
    )
    assert r1.status_code == 201, r1.text

    r2 = client.post(
        "/api/bank-accounts",
        headers=admin_headers,
        json={"name": "Bank B", "coa_account_id": bank1010["id"]},
    )
    assert r2.status_code == 400, r2.text
    assert "already linked" in r2.json()["detail"].lower()


def test_reject_non_asset_coa_link(client: TestClient, admin_headers):
    coa = client.get("/api/accounts", headers=admin_headers).json()["items"]
    expense = next(a for a in coa if a["code"] == "5000")
    r = client.post(
        "/api/bank-accounts",
        headers=admin_headers,
        json={"name": "Bad Link", "coa_account_id": expense["id"]},
    )
    assert r.status_code == 400
    assert "asset" in r.json()["detail"].lower()


def test_seeded_banks_have_distinct_coa_and_balances(client: TestClient):
    """Demo seed: each bank owns a leaf; HBL/SCB balances are not identical."""
    summary = seed_one_tenant(
        "demo.bankseed@easy-books.app", "Bank Seed Co", "services"
    )
    tid = summary["tenant_id"]

    with Session(client.app.state.engine) as s:
        banks = s.exec(
            select(BankAccount).where(BankAccount.tenant_id == tid)
        ).all()
        assert len(banks) >= 3

        coa_ids = [b.coa_account_id for b in banks if b.coa_account_id]
        assert len(coa_ids) == len(set(coa_ids)), "bank accounts must not share a CoA leaf"

        codes = {
            s.get(Account, b.coa_account_id).code
            for b in banks
            if b.coa_account_id and s.get(Account, b.coa_account_id)
        }
        assert "1011" in codes
        assert "1012" in codes
        assert "1000" in codes

        balances: dict[str, Decimal] = {}
        for b in banks:
            if not b.coa_account_id:
                continue
            acc = s.get(Account, b.coa_account_id)
            if not acc:
                continue
            entries = s.exec(
                select(JournalEntry).where(
                    JournalEntry.tenant_id == tid,
                    JournalEntry.account_id == acc.id,
                )
            ).all()
            bal = sum((Decimal(str(e.debit)) - Decimal(str(e.credit)) for e in entries), Decimal("0"))
            balances[acc.code] = bal

        assert balances.get("1011", 0) != 0 or balances.get("1012", 0) != 0
        # Dedicated bank leaves should diverge once multi-bank activity is seeded
        if "1011" in balances and "1012" in balances:
            assert balances["1011"] != balances["1012"], (
                f"expected distinct HBL/SCB balances, got {balances}"
            )
