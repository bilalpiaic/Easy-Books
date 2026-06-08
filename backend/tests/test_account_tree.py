"""Unit tests for the hierarchical roll-up engine (#53 Phase 2)."""
from decimal import Decimal
from types import SimpleNamespace

from services.account_tree import build_account_tree


def _acc(id, code, name, type="Asset", parent_id=None, is_group=False):
    return SimpleNamespace(id=id, code=code, name=name, type=type,
                           parent_id=parent_id, is_group=is_group)


def test_parent_rolls_up_children():
    accounts = [
        _acc(1, "1000", "Current Assets", is_group=True),
        _acc(2, "1010", "Cash", parent_id=1),
        _acc(3, "1020", "Bank", parent_id=1),
    ]
    values = {2: {"balance": Decimal("30")}, 3: {"balance": Decimal("70")}}
    tree = build_account_tree(accounts, values, ["balance"])
    assert len(tree) == 1
    root = tree[0]
    assert root["code"] == "1000" and root["level"] == 0
    assert root["balance"] == Decimal("100")          # 30 + 70
    assert [c["code"] for c in root["children"]] == ["1010", "1020"]
    assert root["children"][0]["level"] == 1


def test_group_with_own_direct_balance():
    accounts = [
        _acc(1, "1000", "Parent", is_group=True),
        _acc(2, "1010", "Child", parent_id=1),
    ]
    values = {1: {"balance": Decimal("5")}, 2: {"balance": Decimal("20")}}
    tree = build_account_tree(accounts, values, ["balance"])
    assert tree[0]["balance"] == Decimal("25")        # own 5 + child 20


def test_prunes_zero_subtree_but_keeps_nonzero_sibling():
    accounts = [
        _acc(1, "1000", "Parent", is_group=True),
        _acc(2, "1010", "HasBalance", parent_id=1),
        _acc(3, "1020", "Empty", parent_id=1),
    ]
    values = {2: {"balance": Decimal("10")}}
    tree = build_account_tree(accounts, values, ["balance"])
    assert len(tree) == 1
    assert [c["code"] for c in tree[0]["children"]] == ["1010"]


def test_fully_zero_tree_pruned_to_empty():
    accounts = [_acc(1, "1000", "P", is_group=True), _acc(2, "1010", "C", parent_id=1)]
    assert build_account_tree(accounts, {}, ["balance"]) == []


def test_multiple_fields_and_grand_total_preserved():
    accounts = [
        _acc(1, "4000", "Revenue", "Revenue", is_group=True),
        _acc(2, "4010", "Sales", "Revenue", parent_id=1),
        _acc(3, "4020", "Service", "Revenue", parent_id=1),
    ]
    values = {2: {"debit": Decimal("1"), "credit": Decimal("100")},
              3: {"debit": Decimal("2"), "credit": Decimal("50")}}
    tree = build_account_tree(accounts, values, ["debit", "credit"])
    assert tree[0]["debit"] == Decimal("3")
    assert tree[0]["credit"] == Decimal("150")
    assert sum(r["credit"] for r in tree) == Decimal("150")


def test_orphan_parent_id_treated_as_root():
    accounts = [_acc(2, "1010", "Lonely", parent_id=999)]
    values = {2: {"balance": Decimal("5")}}
    tree = build_account_tree(accounts, values, ["balance"])
    assert len(tree) == 1 and tree[0]["code"] == "1010" and tree[0]["level"] == 0


def test_roots_and_children_ordered_by_code():
    accounts = [
        _acc(1, "2000", "B-Root", is_group=True),
        _acc(2, "1000", "A-Root", is_group=True),
        _acc(3, "1020", "A-Child2", parent_id=2),
        _acc(4, "1010", "A-Child1", parent_id=2),
    ]
    # 2000 carries a direct balance so it survives pruning (it has no children);
    # this test is about ordering, not pruning.
    values = {1: {"balance": Decimal("1")}, 3: {"balance": Decimal("1")}, 4: {"balance": Decimal("1")}}
    tree = build_account_tree(accounts, values, ["balance"])
    assert [r["code"] for r in tree] == ["1000", "2000"]
    assert [c["code"] for c in tree[0]["children"]] == ["1010", "1020"]
