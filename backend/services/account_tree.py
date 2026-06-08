"""Hierarchical roll-up for account-balance statements (#53 Phase 2).

Turns a flat {account_id: {field: Decimal}} of *direct* (leaf) balances plus the
tenant's accounts into a nested tree where each parent's field value is its own
direct value + the sum of its children. Pure logic — no DB, no HTTP. Shared by
the Trial Balance / Balance Sheet / P&L endpoints so the roll-up is written once.
"""
from typing import Optional

from services.money import D, ZERO


def build_account_tree(accounts, values_by_account_id, field_names, *, prune_zero=True):
    """Build a nested account tree with rolled-up subtotals.

    accounts: iterable of objects with .id, .code, .name, .type, .parent_id, .is_group
    values_by_account_id: {account_id: {field: Decimal}} of DIRECT balances
    field_names: list of numeric fields to roll up (e.g. ["debit","credit"] or ["balance"])
    prune_zero: drop nodes whose every field rolls to zero AND have no surviving children

    Returns a list of root node dicts:
      {id, code, name, type, is_group, level, <field...>, children: [node...]}
    Parent[field] == own[field] + sum(child[field]).
    """
    by_id = {a.id: a for a in accounts}
    children_map: dict[Optional[int], list] = {}
    for a in accounts:
        pid = a.parent_id if (a.parent_id in by_id) else None
        children_map.setdefault(pid, []).append(a)

    def _build(acct, level):
        own = values_by_account_id.get(acct.id, {})
        rolled = {f: D(own.get(f, 0)) for f in field_names}
        child_nodes = []
        for child in sorted(children_map.get(acct.id, []), key=lambda x: x.code):
            cn = _build(child, level + 1)
            if cn is not None:
                child_nodes.append(cn)
                for f in field_names:
                    rolled[f] += D(cn[f])
        has_value = any(rolled[f] != ZERO for f in field_names)
        if prune_zero and not has_value and not child_nodes:
            return None
        node = {
            "id": acct.id,
            "code": acct.code,
            "name": acct.name,
            "type": acct.type,
            "is_group": bool(getattr(acct, "is_group", False)),
            "level": level,
            "children": child_nodes,
        }
        for f in field_names:
            node[f] = rolled[f]
        return node

    out = []
    for root in sorted(children_map.get(None, []), key=lambda x: x.code):
        n = _build(root, 0)
        if n is not None:
            out.append(n)
    return out
