"""
Posting-control tests: group/parent/inactive accounts must be rejected at post time.

Payload note: POST /api/transactions uses JournalEntryBase which has `account_id`
(integer FK), not `account_code`.  The helper _post_jv looks up the account id
from the create response.
"""
import db as _db_module
from models import Account


def _acct(client, h, code, name, account_type="Asset", parent_id=None, is_group=False):
    r = client.post("/api/accounts", headers=h, json={
        "code": code, "name": name, "type": account_type,
        "parent_id": parent_id, "is_group": is_group,
    })
    assert r.status_code == 200, f"_acct {code}: {r.text}"
    return r.json()


def _post_jv(client, h, dr_id, cr_id, amt=10):
    """Post a balanced manual JV using account *ids*."""
    return client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01",
        "description": "test posting control",
        "entries": [
            {"account_id": dr_id, "debit": amt, "credit": 0},
            {"account_id": cr_id, "debit": 0, "credit": amt},
        ],
    })


def test_cannot_post_to_group_account(client, admin_headers):
    h = admin_headers
    g = _acct(client, h, "9100", "Header", is_group=True)
    leaf = _acct(client, h, "9101", "Leaf")
    r = _post_jv(client, h, g["id"], leaf["id"])
    assert r.status_code == 400, r.text
    assert "group" in r.text.lower(), f"Expected 'group' in error: {r.text}"


def test_cannot_post_to_parent_with_children(client, admin_headers):
    h = admin_headers
    p = _acct(client, h, "9200", "Parent")
    c = _acct(client, h, "9201", "Child", parent_id=p["id"])
    # 9200 now has a child → not postable
    r = _post_jv(client, h, p["id"], c["id"])
    assert r.status_code == 400, r.text


def test_post_to_normal_leaf_ok(client, admin_headers):
    h = admin_headers
    a = _acct(client, h, "9300", "A")
    b = _acct(client, h, "9301", "B")
    r = _post_jv(client, h, a["id"], b["id"])
    assert r.status_code in (200, 201), r.text
