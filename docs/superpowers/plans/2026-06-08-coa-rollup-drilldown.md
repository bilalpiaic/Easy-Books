# Multi-Level COA Reporting Roll-up & Drill-down (#53 Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Trial Balance, Balance Sheet, and P&L hierarchical — parent-subtotal roll-up over the multi-level CoA, expand/collapse, and leaf drill-to-ledger — via one shared roll-up engine, without changing any statement's bottom line.

**Architecture:** A pure-logic `services/account_tree.py` turns `{account_id: {field: Decimal}}` direct balances + the tenant's accounts into a nested, pruned tree (parent = own + Σ children). The TB/BS/P&L endpoints compute their leaf balances as today, then return `build_account_tree(...)` output (single-period only; BS/P&L comparison mode stays flat). A reusable `<AccountTree>` React component renders all three pages.

**Tech Stack:** FastAPI, SQLModel, pytest (backend); Next.js 16 / React 19 / TypeScript / Tailwind v4 (frontend). Money via `services/money.py` (`D`, `ZERO`).

**Spec:** `docs/superpowers/specs/2026-06-08-coa-rollup-drilldown-design.md`

**Run backend tests from `backend/` with `PYTHONPATH=.`** (conftest imports `db` as a top-level module).

---

## File Structure

| File | Responsibility | Tasks |
|------|----------------|-------|
| `backend/services/account_tree.py` (new) | `build_account_tree` roll-up engine | 1 |
| `backend/tests/test_account_tree.py` (new) | Engine unit tests | 1 |
| `backend/routers/reports.py` | TB / BS / P&L return nested trees (single-period) | 2,3,4 |
| `backend/tests/test_coa_rollup.py` (new) | Endpoint integration tests | 2,3,4 |
| `frontend/src/components/AccountTree.tsx` (new) | Recursive expandable tree rows | 5 |
| `frontend/src/app/(dashboard)/trial-balance/page.tsx` | Render TB tree | 5 |
| `frontend/src/app/(dashboard)/balance/page.tsx` | Render BS tree (single-period); keep flat compare | 6 |
| `frontend/src/app/(dashboard)/pl/page.tsx` | Render P&L tree (single-period); keep flat compare | 7 |

---

### Task 1: `services/account_tree.py` — the roll-up engine

**Files:**
- Create: `backend/services/account_tree.py`
- Test: `backend/tests/test_account_tree.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_account_tree.py`:

```python
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
    # legacy: a group that itself carries a posting
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
    values = {2: {"balance": Decimal("10")}}          # 1020 has nothing
    tree = build_account_tree(accounts, values, ["balance"])
    assert len(tree) == 1
    assert [c["code"] for c in tree[0]["children"]] == ["1010"]   # 1020 pruned


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
    # grand total over roots == sum of input leaf values
    assert sum(r["credit"] for r in tree) == Decimal("150")


def test_orphan_parent_id_treated_as_root():
    # parent_id points to a non-existent account → node is a root
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
    values = {3: {"balance": Decimal("1")}, 4: {"balance": Decimal("1")}}
    tree = build_account_tree(accounts, values, ["balance"])
    assert [r["code"] for r in tree] == ["1000", "2000"]
    assert [c["code"] for c in tree[0]["children"]] == ["1010", "1020"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_account_tree.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.account_tree'`

- [ ] **Step 3: Implement the engine**

Create `backend/services/account_tree.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_account_tree.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/account_tree.py backend/tests/test_account_tree.py
git commit -m "feat(reports): hierarchical account roll-up engine (#53 Phase 2)"
```

---

### Task 2: Trial Balance endpoint → nested tree

**Files:**
- Modify: `backend/routers/reports.py` (`get_trial_balance`, ~lines 78-117)
- Test: `backend/tests/test_coa_rollup.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_coa_rollup.py`:

```python
"""Integration tests for hierarchical TB / BS / P&L (#53 Phase 2)."""


def _acct(client, h, code, name, type="Asset", parent_id=None, is_group=False):
    r = client.post("/api/accounts", headers=h, json={
        "code": code, "name": name, "type": type,
        "parent_id": parent_id, "is_group": is_group,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _post(client, h, dr_id, cr_id, amt, date="2026-04-01"):
    r = client.post("/api/transactions", headers=h, json={
        "date": date, "description": "rollup test",
        "entries": [
            {"account_id": dr_id, "debit": amt, "credit": 0},
            {"account_id": cr_id, "debit": 0, "credit": amt},
        ],
    })
    assert r.status_code in (200, 201), r.text


def _find(nodes, code):
    for n in nodes:
        if n["code"] == code:
            return n
        hit = _find(n["children"], code)
        if hit:
            return hit
    return None


def test_trial_balance_returns_rolled_up_tree(client, admin_headers):
    h = admin_headers
    # NB: new tenants get a seeded CoA (signup → seed_data), so use high 9xxx
    # codes that won't collide with seeded accounts (matches existing tests).
    # group 9500 with two postable leaves; an Equity leaf to balance the JVs
    grp = _acct(client, h, "9500", "Current Assets", "Asset", is_group=True)
    cash = _acct(client, h, "9510", "Cash", "Asset", parent_id=grp["id"])
    bank = _acct(client, h, "9520", "Bank", "Asset", parent_id=grp["id"])
    cap = _acct(client, h, "9100", "Capital", "Equity")
    _post(client, h, cash["id"], cap["id"], 30)
    _post(client, h, bank["id"], cap["id"], 70)

    r = client.get("/api/reports/trial-balance?start=2026-01-01&end=2026-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "tree" in body and "totals" in body
    node = _find(body["tree"], "9500")
    assert node is not None and node["is_group"] is True
    assert float(node["debit"]) == 100.0            # 30 + 70 rolled up
    assert {c["code"] for c in node["children"]} == {"9510", "9520"}
    # grand totals still balance
    assert float(body["totals"]["debit"]) == float(body["totals"]["credit"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_coa_rollup.py::test_trial_balance_returns_rolled_up_tree -v`
Expected: FAIL — response is still a flat list (`"tree" not in body`; body is a list).

- [ ] **Step 3: Add the import + rewrite `get_trial_balance`**

In `backend/routers/reports.py`, add near the other `services` imports at the top:

```python
from services.account_tree import build_account_tree
```

Replace the body of `get_trial_balance` (the `q = (...)` build, the `rows = ...`, and the `return [...]`) with:

```python
@router.get("/trial-balance")
def get_trial_balance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    date: Optional[str] = None,
):
    q = (
        select(
            Account.id,
            func.sum(JournalEntry.debit).label("total_debit"),
            func.sum(JournalEntry.credit).label("total_credit"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(Transaction.tenant_id == user.tenant_id)
    )
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date <= end)
    elif date:
        q = q.where(Transaction.date <= date)
    rows = session.exec(q.group_by(Account.id)).all()

    values = {
        r.id: {"debit": D(r.total_debit or 0), "credit": D(r.total_credit or 0)}
        for r in rows
    }
    accounts = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id)
    ).all()
    tree = build_account_tree(accounts, values, ["debit", "credit"])
    total_debit = sum((v["debit"] for v in values.values()), ZERO)
    total_credit = sum((v["credit"] for v in values.values()), ZERO)
    return {"tree": tree, "totals": {"debit": total_debit, "credit": total_credit}}
```

(`D` and `ZERO` are already imported in `reports.py`; confirm and add from `services.money` if not.)

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_coa_rollup.py::test_trial_balance_returns_rolled_up_tree -v`
Expected: PASS

- [ ] **Step 5: Run reports regression**

Run: `PYTHONPATH=. uv run pytest tests/ -k "report or trial or ledger or balance or subledger" -q`
Expected: PASS. (If a test asserted the old flat TB list shape, update it to read `body["tree"]`/`body["totals"]` — note any such change.)

- [ ] **Step 6: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_coa_rollup.py
git commit -m "feat(reports): trial balance returns hierarchical tree (#53 Phase 2)"
```

---

### Task 3: Balance Sheet endpoint → nested tree (single-period)

**Files:**
- Modify: `backend/routers/reports.py` (`get_balance_sheet`, ~lines 762-819)
- Test: `backend/tests/test_coa_rollup.py`

The endpoint keeps comparison mode flat. Only the single-period branch becomes a tree. The synthetic `RE-CUR` net-income node is appended to the equity section as a top-level node (no children, not drillable).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_coa_rollup.py`:

```python
def test_balance_sheet_single_period_is_tree_and_balances(client, admin_headers):
    h = admin_headers
    ag = _acct(client, h, "9500", "Current Assets", "Asset", is_group=True)
    cash = _acct(client, h, "9510", "Cash", "Asset", parent_id=ag["id"])
    cap = _acct(client, h, "9100", "Capital", "Equity")
    _post(client, h, cash["id"], cap["id"], 100)

    r = client.get("/api/reports/balance-sheet?date=2026-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(["assets", "liabilities", "equity", "totals"]).issubset(body)
    ag_node = _find(body["assets"], "9500")
    assert ag_node is not None and float(ag_node["balance"]) == 100.0
    assert float(_find(body["assets"], "9510")["balance"]) == 100.0
    # Assets == Liabilities + Equity
    assert float(body["totals"]["assets"]) == float(body["totals"]["liabilities"]) + float(body["totals"]["equity"])


def test_balance_sheet_comparison_mode_stays_flat(client, admin_headers):
    h = admin_headers
    cash = _acct(client, h, "9510", "Cash", "Asset")
    cap = _acct(client, h, "9100", "Capital", "Equity")
    _post(client, h, cash["id"], cap["id"], 100)
    r = client.get("/api/reports/balance-sheet?date=2026-12-31&compare_end=2025-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "current" in body and "comparison" in body      # unchanged flat shape
    assert isinstance(body["current"], list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_coa_rollup.py -k balance_sheet -v`
Expected: the single-period test FAILS (response is a flat list, no `assets` key); the comparison test PASSES already.

- [ ] **Step 3: Rewrite `get_balance_sheet` single-period branch**

Replace `get_balance_sheet` with (keeps the inner `_query` for comparison flat; adds a tree builder for single period):

```python
@router.get("/balance-sheet")
def get_balance_sheet(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    date: Optional[str] = None,
    compare_end: Optional[str] = None,
):
    def _leaf_rows(s, e, as_of):
        q = (
            select(
                Account.id, Account.code, Account.name, Account.type,
                func.sum(JournalEntry.debit).label("total_debit"),
                func.sum(JournalEntry.credit).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.account_id == Account.id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(Transaction.tenant_id == user.tenant_id)
        )
        if s:
            q = q.where(Transaction.date >= s)
        if e:
            q = q.where(Transaction.date <= e)
        elif as_of:
            q = q.where(Transaction.date <= as_of)
        return session.exec(q.group_by(Account.id)).all()

    def _flat(s, e, as_of):
        # Existing flat shape (used for comparison mode) — unchanged behaviour.
        items, net_income = [], ZERO
        for r in _leaf_rows(s, e, as_of):
            debit, credit = D(r.total_debit or 0), D(r.total_credit or 0)
            if r.type == "Asset":
                balance = debit - credit
            elif r.type in ("Liability", "Equity"):
                balance = credit - debit
            elif r.type == "Revenue":
                net_income += credit - debit
                continue
            elif r.type == "Expense":
                net_income -= debit - credit
                continue
            else:
                balance = debit - credit
            items.append({"code": r.code, "name": r.name, "type": r.type, "balance": balance})
        if net_income != ZERO:
            items.append({"code": "RE-CUR", "name": "Retained Earnings (Current Period)",
                          "type": "Equity", "balance": net_income})
        return items

    # Comparison mode: keep the existing flat {current, comparison} shape.
    if compare_end:
        return {"current": _flat(start, end, date), "comparison": _flat(None, compare_end, None)}

    # Single period: hierarchical tree per section.
    rows = _leaf_rows(start, end, date)
    values, net_income = {}, ZERO
    for r in rows:
        debit, credit = D(r.total_debit or 0), D(r.total_credit or 0)
        if r.type == "Asset":
            values[r.id] = {"balance": debit - credit}
        elif r.type in ("Liability", "Equity"):
            values[r.id] = {"balance": credit - debit}
        elif r.type == "Revenue":
            net_income += credit - debit
        elif r.type == "Expense":
            net_income -= debit - credit

    accounts = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id)
    ).all()
    by_type = {t: [a for a in accounts if a.type == t] for t in ("Asset", "Liability", "Equity")}

    def _section(type_name):
        return build_account_tree(by_type[type_name], values, ["balance"])

    assets = _section("Asset")
    liabilities = _section("Liability")
    equity = _section("Equity")
    if net_income != ZERO:
        equity.append({
            "id": None, "code": "RE-CUR", "name": "Retained Earnings (Current Period)",
            "type": "Equity", "is_group": False, "level": 0,
            "balance": net_income, "children": [],
        })

    def _tot(nodes):
        return sum((D(n["balance"]) for n in nodes), ZERO)

    return {
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "totals": {"assets": _tot(assets), "liabilities": _tot(liabilities), "equity": _tot(equity)},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_coa_rollup.py -k balance_sheet -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Regression**

Run: `PYTHONPATH=. uv run pytest tests/ -k "balance or report or comparative" -q`
Expected: PASS (update any test asserting the old single-period flat BS shape to read sections; note changes).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_coa_rollup.py
git commit -m "feat(reports): balance sheet hierarchical tree for single period (#53 Phase 2)"
```

---

### Task 4: P&L (income statement) endpoint → nested tree (single-period)

**Files:**
- Modify: `backend/routers/reports.py` (`get_income_statement`, ~lines 395-432)
- Test: `backend/tests/test_coa_rollup.py`

Single-period → tree with Revenue / Expense sections + `net_profit`. Comparison mode stays flat. Each node's `amount` is the natural positive figure (Revenue: credit−debit; Expense: debit−credit).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_coa_rollup.py`:

```python
def test_income_statement_single_period_is_tree(client, admin_headers):
    h = admin_headers
    rg = _acct(client, h, "9400", "Revenue", "Revenue", is_group=True)
    sales = _acct(client, h, "9410", "Sales", "Revenue", parent_id=rg["id"])
    cash = _acct(client, h, "9510", "Cash", "Asset")
    exp = _acct(client, h, "9900", "Rent", "Expense")
    _post(client, h, cash["id"], sales["id"], 200)   # revenue 200
    _post(client, h, exp["id"], cash["id"], 50)      # expense 50

    r = client.get("/api/reports/income-statement?start=2026-01-01&end=2026-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(["revenue", "expenses", "totals"]).issubset(body)
    assert float(_find(body["revenue"], "9400")["amount"]) == 200.0   # rolled up
    assert float(body["totals"]["revenue"]) == 200.0
    assert float(body["totals"]["expenses"]) == 50.0
    assert float(body["totals"]["net_profit"]) == 150.0


def test_income_statement_comparison_mode_stays_flat(client, admin_headers):
    h = admin_headers
    sales = _acct(client, h, "9410", "Sales", "Revenue")
    cash = _acct(client, h, "9510", "Cash", "Asset")
    _post(client, h, cash["id"], sales["id"], 200)
    r = client.get("/api/reports/income-statement?start=2026-01-01&end=2026-12-31"
                   "&compare_start=2025-01-01&compare_end=2025-12-31", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "current" in body and "comparison" in body
    assert isinstance(body["current"], list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_coa_rollup.py -k income_statement -v`
Expected: single-period FAILS (flat list, no `revenue` key); comparison PASSES.

- [ ] **Step 3: Rewrite `get_income_statement`**

Replace `get_income_statement` with:

```python
@router.get("/income-statement")
def get_income_statement(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    compare_start: Optional[str] = None, compare_end: Optional[str] = None,
):
    def _leaf_rows(s, e):
        q = (
            select(
                Account.id, Account.code, Account.name, Account.type,
                func.sum(JournalEntry.debit).label("total_debit"),
                func.sum(JournalEntry.credit).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.account_id == Account.id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(Account.type.in_(["Revenue", "Expense"]))
            .where(Transaction.tenant_id == user.tenant_id)
        )
        if s and e:
            q = q.where(Transaction.date >= s, Transaction.date <= e)
        return session.exec(q.group_by(Account.id)).all()

    def _flat(s, e):
        # Existing flat shape (comparison mode) — unchanged.
        out = []
        for r in _leaf_rows(s, e):
            out.append({"name": r.name, "type": r.type, "code": r.code,
                        "total_debit": r.total_debit, "total_credit": r.total_credit})
        return out

    if compare_start and compare_end:
        return {"current": _flat(start, end), "comparison": _flat(compare_start, compare_end)}

    rows = _leaf_rows(start, end)
    values = {}
    for r in rows:
        debit, credit = D(r.total_debit or 0), D(r.total_credit or 0)
        amount = (credit - debit) if r.type == "Revenue" else (debit - credit)
        values[r.id] = {"amount": amount}

    accounts = session.exec(
        select(Account).where(
            Account.tenant_id == user.tenant_id,
            Account.type.in_(["Revenue", "Expense"]),
        )
    ).all()
    rev_accts = [a for a in accounts if a.type == "Revenue"]
    exp_accts = [a for a in accounts if a.type == "Expense"]
    revenue = build_account_tree(rev_accts, values, ["amount"])
    expenses = build_account_tree(exp_accts, values, ["amount"])

    def _tot(nodes):
        return sum((D(n["amount"]) for n in nodes), ZERO)

    total_rev, total_exp = _tot(revenue), _tot(expenses)
    return {
        "revenue": revenue, "expenses": expenses,
        "totals": {"revenue": total_rev, "expenses": total_exp,
                   "net_profit": total_rev - total_exp},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_coa_rollup.py -k income_statement -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Regression + full deferred-independent suite slice**

Run: `PYTHONPATH=. uv run pytest tests/test_coa_rollup.py tests/ -k "report or income or pl or comparative" -q`
Expected: PASS (update any test asserting old single-period flat P&L list; note changes).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_coa_rollup.py
git commit -m "feat(reports): income statement hierarchical tree for single period (#53 Phase 2)"
```

---

### Task 5: `<AccountTree>` component + Trial Balance page

**Files:**
- Create: `frontend/src/components/AccountTree.tsx`
- Modify: `frontend/src/app/(dashboard)/trial-balance/page.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/AccountTree.tsx`:

```tsx
"use client"
import { useState } from "react"
import { ChevronRight, ChevronDown } from "lucide-react"

export interface TreeNode {
  id: number | null
  code: string
  name: string
  type: string
  is_group: boolean
  level: number
  children: TreeNode[]
  [field: string]: unknown   // numeric fields (debit/credit/balance/amount)
}

export function AccountTreeRows({
  nodes, columns, renderLeafLabel,
}: {
  nodes: TreeNode[]
  columns: { key: string; align?: "right" | "left" }[]
  renderLeafLabel?: (node: TreeNode) => React.ReactNode
}) {
  return (
    <>
      {nodes.map(n => (
        <TreeRow key={`${n.code}-${n.id ?? "syn"}`} node={n} columns={columns} renderLeafLabel={renderLeafLabel} />
      ))}
    </>
  )
}

function TreeRow({ node, columns, renderLeafLabel }: {
  node: TreeNode
  columns: { key: string; align?: "right" | "left" }[]
  renderLeafLabel?: (node: TreeNode) => React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  const hasChildren = node.children && node.children.length > 0
  const isGroup = node.is_group || hasChildren
  return (
    <>
      <tr className={isGroup ? "font-semibold bg-[#f6f3ee]/40" : ""}>
        <td className="py-2 pr-3">
          <span style={{ paddingLeft: `${node.level * 20}px` }} className="inline-flex items-center gap-1">
            {hasChildren ? (
              <button onClick={() => setOpen(o => !o)} className="text-[#1a1814]/50 hover:text-[#b8943f]">
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
            ) : <span className="inline-block w-[14px]" />}
            <span className="text-[#1a1814]/50 text-xs tabular-nums">{node.code}</span>
            {!isGroup && renderLeafLabel ? renderLeafLabel(node) : <span>{node.name}</span>}
          </span>
        </td>
        {columns.map(col => (
          <td key={col.key} className={`py-2 px-3 tabular-nums ${col.align === "right" ? "text-right" : ""}`}>
            {fmtNum(node[col.key])}
          </td>
        ))}
      </tr>
      {hasChildren && open && (
        <AccountTreeRows nodes={node.children} columns={columns} renderLeafLabel={renderLeafLabel} />
      )}
    </>
  )
}

function fmtNum(v: unknown): string {
  const n = Number(v ?? 0)
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
```

- [ ] **Step 2: Wire it into the Trial Balance page**

Read `frontend/src/app/(dashboard)/trial-balance/page.tsx`. The fetch currently sets a flat array; change it to consume `{tree, totals}`. Replace the table body rows with `<AccountTreeRows>` and the footer with `totals`. Keep the existing leaf drill link (`/ledger?account=<code>&start=&end=`) by passing a `renderLeafLabel` that wraps the name in that `<Link>`:

```tsx
import { AccountTreeRows, type TreeNode } from "@/components/AccountTree"
// ...
const [tree, setTree] = useState<TreeNode[]>([])
const [totals, setTotals] = useState<{ debit: number; credit: number }>({ debit: 0, credit: 0 })
// in the fetch .then:
//   setTree(res.tree ?? []); setTotals(res.totals ?? { debit: 0, credit: 0 })
// in the table:
<AccountTreeRows
  nodes={tree}
  columns={[{ key: "debit", align: "right" }, { key: "credit", align: "right" }]}
  renderLeafLabel={(n) => (
    <Link href={`/ledger?account=${encodeURIComponent(n.code)}&start=${start}&end=${end}`}
          className="hover:text-[#b8943f] hover:underline">{n.name}</Link>
  )}
/>
```

Update the CSV export to flatten the tree (walk nodes → rows) so the existing download still works. If the page used `data.map(...)` for CSV, add a `flatten(nodes)` helper that recurses into `children`.

- [ ] **Step 3: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors in `AccountTree.tsx` or `trial-balance/page.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AccountTree.tsx "frontend/src/app/(dashboard)/trial-balance/page.tsx"
git commit -m "feat(reports-ui): expandable account tree on Trial Balance (#53 Phase 2)"
```

---

### Task 6: Balance Sheet page → tree (single-period)

**Files:**
- Modify: `frontend/src/app/(dashboard)/balance/page.tsx`

- [ ] **Step 1: Wire the tree for single-period; keep flat compare**

Read `frontend/src/app/(dashboard)/balance/page.tsx`. It already branches on `compareMode`. For the **non-compare** path, the response is now `{assets, liabilities, equity, totals}` (trees); render each section with `<AccountTreeRows nodes={...} columns={[{key:"balance",align:"right"}]} renderLeafLabel={...}>`, using the existing `DocLink type="account" id={node.code}` for the leaf label so drill-down is preserved. For the **compare** path, keep the existing flat `{current, comparison}` rendering unchanged.

Concretely: keep `compareMode` state. When `!compareMode`, fetch and store `assets/liabilities/equity/totals` (tree state) and render the three sections via `<AccountTreeRows>`. When `compareMode`, keep the current flat-list code path exactly as-is. Use section `totals` for the section footers and the Assets == Liab+Equity check.

- [ ] **Step 2: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors in `balance/page.tsx`.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(dashboard)/balance/page.tsx"
git commit -m "feat(reports-ui): expandable tree on Balance Sheet single-period view (#53 Phase 2)"
```

---

### Task 7: P&L page → tree (single-period)

**Files:**
- Modify: `frontend/src/app/(dashboard)/pl/page.tsx`

- [ ] **Step 1: Wire the tree for single-period; keep flat compare**

Read `frontend/src/app/(dashboard)/pl/page.tsx`. Mirror Task 6: when `!compareMode`, consume `{revenue, expenses, totals}` (trees) and render Revenue / Expense sections with `<AccountTreeRows nodes={...} columns={[{key:"amount",align:"right"}]} renderLeafLabel={...}>` (preserve the existing leaf drill if present). Show `totals.revenue`, `totals.expenses`, `totals.net_profit` in the footers. When `compareMode`, keep the existing flat rendering unchanged.

- [ ] **Step 2: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors in `pl/page.tsx`.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(dashboard)/pl/page.tsx"
git commit -m "feat(reports-ui): expandable tree on P&L single-period view (#53 Phase 2)"
```

---

### Task 8: Full verification + roadmap

- [ ] **Step 1: Full backend suite**

Run: `cd backend && PYTHONPATH=. uv run pytest -q`
Expected: all pass (existing + new `test_account_tree.py` + `test_coa_rollup.py`). Investigate any failure caused by the shape change and fix the asserting test.

- [ ] **Step 2: Frontend lint**

Run: `cd frontend && npm run lint`
Expected: no new errors in the touched files.

- [ ] **Step 3: Update the roadmap**

In `docs/ROADMAP.md`, move #53 Phase 2 from "Partially done" to done (the roll-up/drill-down for TB/BS/P&L shipped; note Cash Flow/dashboard remain).

- [ ] **Step 4: Commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs(roadmap): #53 Phase 2 COA reporting roll-up/drill-down shipped"
```

---

## Self-Review notes

- **Spec coverage:** §1 engine → Task 1; §2 endpoints (TB/BS/P&L, comparison-flat, RE-CUR synthetic) → Tasks 2/3/4; §3 `<AccountTree>` + 3 pages → Tasks 5/6/7; §4 tests → Tasks 1-4; §5 edge cases (group-with-own, orphan parent, is_group styling, ordering) → covered by Task 1 unit tests.
- **Reconciliation:** TB grand totals stay equal; BS balances (Assets == Liab+Equity); P&L net_profit == revenue − expenses — all asserted in integration tests, proving the roll-up never changes the bottom line.
- **Field-name consistency:** TB uses `["debit","credit"]`; BS uses `["balance"]`; P&L uses `["amount"]`. The frontend column `key`s match (`debit`/`credit`, `balance`, `amount`).
- **Comparison mode** preserved flat on BS (`compare_end`) and P&L (`compare_start`+`compare_end`); TB has none.
