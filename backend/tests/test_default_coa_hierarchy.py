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


import pytest


@pytest.mark.parametrize("model", ["simple", "services", "trader", "manufacturing", "telecom_franchise"])
def test_every_model_coa_is_valid_hierarchy(client, model):
    tid = _signup(client, email=f"owner_{model}@acme.test", model=model)
    accts = _accounts(tid)
    by_id = {a.id: a for a in accts}
    roots = [a for a in accts if a.parent_id is None]
    assert {r.code for r in roots} == {"1", "2", "3", "4", "5"}
    for a in accts:
        if not a.is_group:
            assert a.parent_id is not None, f"{model}: leaf {a.code} orphaned"
        if a.parent_id is not None:
            p = by_id[a.parent_id]
            assert p.is_group, f"{model}: {a.code} parent {p.code} not a group"
            assert p.type == a.type, f"{model}: {a.code} type != parent type"


def test_posting_to_group_account_rejected(client):
    tid = _signup(client, email="poster@acme.test", model="simple")
    tok = client.post("/api/auth/login", data={
        "username": "poster@acme.test", "password": "pw12345678",
    }).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    client.cookies.clear()
    accts = client.get("/api/accounts", headers=h).json()["items"]
    g1 = next(a for a in accts if a["code"] == "1")
    leaf = next(a for a in accts if a["code"] == "1000")
    r = client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01", "description": "to group",
        "entries": [{"account_id": g1["id"], "debit": 10, "credit": 0},
                    {"account_id": leaf["id"], "debit": 0, "credit": 10}],
    })
    assert r.status_code == 400, r.text
