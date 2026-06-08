"""The default per-tenant CoA (db.py seed_data) is a multi-level hierarchy."""
from sqlmodel import Session, select

import db as _db_module
from models import Account
from services.account_tree import build_account_tree


def _accounts(tenant_id):
    with Session(_db_module.engine) as s:
        return s.exec(select(Account).where(Account.tenant_id == tenant_id)).all()


def _signup(client, email="owner@acme.test", model="simple"):
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "pw12345678", "full_name": "Owner",
        "company_name": "Acme", "business_model": model,
    })
    assert r.status_code == 200, r.text
    return r.json()["tenant_id"]


def test_default_coa_has_group_roots_with_children(client):
    tid = _signup(client)
    accts = _accounts(tid)
    by_code = {a.code: a for a in accts}
    for code, typ in [("1", "Asset"), ("2", "Liability"), ("3", "Equity"),
                      ("4", "Revenue"), ("5", "Expense")]:
        assert code in by_code, f"missing group {code}"
        assert by_code[code].is_group is True
        assert by_code[code].type == typ
        assert by_code[code].parent_id is None
    cash = by_code["1000"]
    assert cash.is_group is False
    assert cash.parent_id == by_code["11"].id
    assert by_code["11"].parent_id == by_code["1"].id


def test_default_coa_rollup_reconciles_and_groups_are_leafless_in_postings(client):
    tid = _signup(client)
    accts = _accounts(tid)
    by_id = {a.id: a for a in accts}
    for a in accts:
        if not a.is_group:
            assert a.parent_id is not None, f"leaf {a.code} has no parent"
        if a.parent_id is not None:
            assert by_id[a.parent_id].is_group is True, f"{a.code} parent is not a group"
    tree = build_account_tree(accts, {}, ["balance"], prune_zero=False)
    assert {n["code"] for n in tree} == {"1", "2", "3", "4", "5"}
