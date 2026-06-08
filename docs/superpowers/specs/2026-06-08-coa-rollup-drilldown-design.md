# Multi-Level COA Reporting — Roll-up & Drill-down (#53 Phase 2) — Design

_Date: 2026-06-08 · Branch: `feature/issue53-phase2-coa-rollup`_

## Problem

Phase 1 (shipped v2.4.0) gave the Chart of Accounts a hierarchy (`Account.parent_id`,
`is_group`, `is_active`) and restricted posting to **leaf** accounts. But the
financial statements still aggregate **flat** by `Account.id` (`routers/reports.py`):
Trial Balance, Balance Sheet, and P&L return one row per posting account with no
parent subtotals and no tree. Because group accounts never receive postings, they
are simply absent from the statements — so a multi-level CoA produces a flat report
that ignores its own structure.

Phase 2 makes the three account-balance statements **hierarchical**: parent-subtotal
roll-up (parent = its own direct balance + Σ descendant leaves), expand/collapse, and
drill-through from a leaf line into the ledger and on to the voucher.

## Scope (decided)

- **In:** Trial Balance, Balance Sheet, P&L — one shared roll-up engine; nested-tree
  payloads (replacing the flat shape); expand/collapse + leaf drill-down on all three
  pages.
- **Out (separate work):** Cash Flow (derived by the indirect method, not a leaf
  roll-up), GL (already per-account detail — it is the drill *target*), and dashboard
  headline summaries.

## Decisions (locked during brainstorming)

1. **Scope:** TB + Balance Sheet + P&L, sharing one roll-up engine.
2. **Payload:** nested tree — each node carries its rolled-up totals + a `children` array.
3. **API:** replace the flat response on the existing endpoints and update the three
   report pages in the same PR (they are the only consumers).
4. **Empty rows:** prune zero subtrees — hide zero-activity leaves and any group whose
   whole subtree rolls to zero (matches today's TB `HAVING debit>0 OR credit>0`).

## §1 · `services/account_tree.py` — shared roll-up engine

A pure-logic module (no HTTP, no DB), mirroring the `services/` pattern and the existing
`product_coa` tree precedent. One function:

```python
def build_account_tree(
    accounts: list[Account],
    values_by_account_id: dict[int, dict[str, Decimal]],
    field_names: list[str],
    *,
    prune_zero: bool = True,
) -> list[Node]:
```

- `accounts` — the tenant's accounts (id, code, name, type, parent_id, is_group).
- `values_by_account_id` — `{account_id: {field: Decimal}}`, the **direct** (leaf)
  balances the endpoint already computes. Accounts absent from this dict have zero
  direct value.
- `field_names` — the numeric fields to roll up (e.g. `["debit", "credit"]` for TB,
  `["balance"]` for BS/P&L). Generic over field count so one function serves all three.

Behaviour:
- Build the parent→child tree from `parent_id`. A node's value per field =
  **its own direct value + Σ children** (so a group that carries direct postings —
  legacy data — is never dropped).
- Each `Node`: `{id, code, name, type, is_group, level, <field…>, children: [Node]}`.
- `prune_zero=True`: drop any node whose **every** field rolls to zero (after summing
  children); a group survives iff it has ≥1 non-zero descendant or non-zero own value.
- Roots = accounts whose `parent_id` is null or points outside the tenant's set;
  ordered by `code`; children ordered by `code` within each level; `level` is 0-based depth.

Invariant (tested): for every node, `node[field] == own[field] + Σ child[field]`, and
the sum over all roots equals the sum of all input leaf values (the roll-up never
changes the bottom line).

## §2 · Endpoint changes (`routers/reports.py`)

Each endpoint keeps its current leaf aggregation (group by `Account.id`), converts the
rows to `values_by_account_id`, loads the tenant's accounts, and returns
`build_account_tree(...)` output. Endpoints stay thin.

- **`GET /trial-balance`** — fields `["debit", "credit"]`. Returns
  `{tree: [Node...], totals: {debit, credit}}`. Grand totals tie out and remain equal.
  Account `type` carried on nodes for optional sectioning.
- **`GET /balance-sheet`** — field `["balance"]` (signed per type, as today). Three
  section sub-trees — Assets / Liabilities / Equity — each built from the accounts of
  that type. Returns `{assets: [...], liabilities: [...], equity: [...], totals:
  {assets, liabilities, equity}}` plus the existing balancing check (Assets == Liab + Equity).
- **`GET /income-statement`** — field `["balance"]`. Revenue / Expense section sub-trees
  + computed **net_profit** (same math, now over rolled-up section totals). Returns
  `{revenue: [...], expenses: [...], totals: {revenue, expenses, net_profit}}`.

Filters (`start`/`end`/`date`) and sign conventions are unchanged — only the response
*shape* changes from flat list to nested tree.

## §3 · Frontend — reusable `<AccountTree>` component

A recursive row renderer used by all three pages
(`trial-balance/page.tsx`, `balance/page.tsx`, `pl/page.tsx`):

- Indents by `level`; a chevron toggles expand/collapse on **group** nodes; group rows
  use subtotal styling (bold). Default state **expanded**; expand/collapse is local
  component state (no persistence — YAGNI).
- **Leaf** rows keep the existing **drill-to-ledger**: click a leaf → the ledger for
  that account → voucher, reusing the exact drill handler/route already wired on the
  Trial Balance page (the implementation plan pins the route); extend the same handler
  to BS/P&L leaf rows. Group rows expand/collapse only (no drill).
- Each page keeps its own header, period controls, grand-total/section footers, and
  print button; only the row body is replaced by `<AccountTree>`.

## §4 · Testing

**Engine unit tests** (`backend/tests/test_account_tree.py`):
- parent total == own + Σ descendants (multi-level).
- pruning removes an all-zero subtree but keeps a group with one non-zero leaf.
- grand total of the tree == sum of the flat input leaf values.
- a group carrying its own direct postings is summed (own + children).
- ordering by `code`; `level` depth correct.

**Endpoint integration tests** (extend the reports test suite):
- Seed a small hierarchy (parent group → 2 leaves), post entries, assert the nested
  shape, parent subtotals, and pruning.
- Balance Sheet still balances (Assets == Liab + Equity) and P&L net profit equals the
  pre-tree flat figure (reconciliation against the old computation).

## §5 · Edge cases & rules

- **Group with direct postings** (legacy; Phase 1 blocks new ones): own balance included
  in its subtotal, never silently dropped.
- **Orphan `parent_id`** (missing / cross-tenant): treated as a root. Tenant-scoped
  queries make cross-tenant references impossible in practice.
- **Account with children but `is_group=False`** (or a childless `is_group=True`):
  display treats *any account with children* as expandable; `is_group` drives styling
  only, not correctness.
- Ordering by `code` within each level. Sign conventions identical to today's endpoints.

## Success criteria

Opening Trial Balance / Balance Sheet / P&L shows the accounts under their parent groups
with rolled-up subtotals, collapsible to any level; clicking a leaf line drills to its
ledger and on to the voucher; the grand totals and BS/P&L bottom lines are identical to
the pre-Phase-2 flat figures (the roll-up only reorganises, never changes, the numbers).
