# Hierarchical Default CoA — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the default per-tenant Chart of Accounts (in `db.py`, used by every signup and by the demo seeder) a multi-level hierarchy — group parents + existing leaves — so the v2.5.0 roll-up reports (TB/BS/P&L) show real subtotals for every tenant, without renumbering any leaf.

**Architecture:** Extend the CoA tuple shape from `(code, name, type, is_memo)` to `(code, name, type, is_memo, parent_code)`, add `is_group=True` group-parent rows with short non-colliding codes (`1`,`11`,`12`,`2`,`21`,`3`,`4`,`41`,`49`,`5`,`51`,`52`,`59`) into `_COA_COMMON` (so all 5 models share them), and give every existing leaf a `parent_code`. `seed_data()` does a two-pass insert (create all, then resolve `parent_id`). Posting stays leaf-only (Phase-1 rule). Then reconcile the test suite.

**Tech Stack:** FastAPI, SQLModel, pytest. Account hierarchy fields (`parent_id`, `is_group`) already exist (Phase 1, v2.4.0). The roll-up engine `services/account_tree.build_account_tree` exists (v2.5.0).

**Spec:** `docs/superpowers/specs/2026-06-08-seed-regen-hierarchical-coa-design.md` (this plan = §1 + §2; demo-seed upgrades §3–§8 are Phase B, a separate plan).

**This is Phase A of the seeding-layer spec.** Phase B (demo-seed upgrades) follows in its own plan once Phase A is green on main.

**Run tests from `backend/` with `PYTHONPATH=.`.**

---

## Group-code scheme (shared by all models, lives in `_COA_COMMON`)

| Code | Name | Type | parent_code |
|------|------|------|-------------|
| `1`  | Assets | Asset | (root) |
| `11` | Current Assets | Asset | `1` |
| `12` | Non-Current Assets | Asset | `1` |
| `2`  | Liabilities | Liability | (root) |
| `21` | Current Liabilities | Liability | `2` |
| `3`  | Equity | Equity | (root) |
| `4`  | Revenue | Revenue | (root) |
| `41` | Operating Revenue | Revenue | `4` |
| `49` | Other Income | Revenue | `4` |
| `5`  | Expenses | Expense | (root) |
| `51` | Cost of Sales | Expense | `5` |
| `52` | Operating Expenses | Expense | `5` |
| `59` | Other Expenses | Expense | `5` |

All group rows are `is_group=True`, `is_memo=False`. Group codes never collide with the 4-digit leaves and never sit as siblings of leaves (groups are interior nodes), so their string-sort position relative to leaves is irrelevant. Empty groups (no children for a given model) are harmless — the report roll-up prunes zero subtrees; they only appear in CoA management as empty headers.

---

### Task 1: Tuple format + two-pass insert + common backbone hierarchy

**Files:**
- Modify: `backend/db.py` (`_COA_COMMON`, `_coa_for`, `seed_data`)
- Modify: `backend/scripts/seed_demo.py` (`_ensure_coa` — unpack new tuple shape)
- Test: `backend/tests/test_default_coa_hierarchy.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_default_coa_hierarchy.py`:

```python
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
    # The 5 type roots exist as groups
    for code, typ in [("1", "Asset"), ("2", "Liability"), ("3", "Equity"),
                      ("4", "Revenue"), ("5", "Expense")]:
        assert code in by_code, f"missing group {code}"
        assert by_code[code].is_group is True
        assert by_code[code].type == typ
        assert by_code[code].parent_id is None
    # A known leaf is parented under a sub-group, not a root
    cash = by_code["1000"]
    assert cash.is_group is False
    assert cash.parent_id == by_code["11"].id          # Current Assets
    assert by_code["11"].parent_id == by_code["1"].id   # → Assets


def test_default_coa_rollup_reconciles_and_groups_are_leafless_in_postings(client):
    tid = _signup(client)
    accts = _accounts(tid)
    # Every non-group account has a parent (no orphan leaves); every group's
    # parent (if any) is also a group.
    by_id = {a.id: a for a in accts}
    for a in accts:
        if not a.is_group:
            assert a.parent_id is not None, f"leaf {a.code} has no parent"
        if a.parent_id is not None:
            assert by_id[a.parent_id].is_group is True, f"{a.code} parent is not a group"
    # build_account_tree produces a forest rooted at the 5 type groups
    tree = build_account_tree(accts, {}, ["balance"], prune_zero=False)
    assert {n["code"] for n in tree} == {"1", "2", "3", "4", "5"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_default_coa_hierarchy.py -v`
Expected: FAIL — group "1" not in CoA / `1000.parent_id is None` (current CoA is flat).

- [ ] **Step 3: Restructure `_COA_COMMON` with groups + parent_code**

In `backend/db.py`, replace `_COA_COMMON` (lines ~184-203) with the 5-tuple shape `(code, name, type, is_memo, parent_code)`, group rows first:

```python
# 5-tuple: (code, name, type, is_memo, parent_code). Group rows carry is_group
# implicitly (parent_code-bearing leaves vs. the group set below). The group
# set is defined in _COA_GROUPS and shared by every model.
_COA_GROUPS: list[tuple[str, str, str]] = [
    # (code, name, type) — all is_group=True, parent resolved from _GROUP_PARENT
    ("1", "Assets", "Asset"),
    ("11", "Current Assets", "Asset"),
    ("12", "Non-Current Assets", "Asset"),
    ("2", "Liabilities", "Liability"),
    ("21", "Current Liabilities", "Liability"),
    ("3", "Equity", "Equity"),
    ("4", "Revenue", "Revenue"),
    ("41", "Operating Revenue", "Revenue"),
    ("49", "Other Income", "Revenue"),
    ("5", "Expenses", "Expense"),
    ("51", "Cost of Sales", "Expense"),
    ("52", "Operating Expenses", "Expense"),
    ("59", "Other Expenses", "Expense"),
]
_GROUP_PARENT: dict[str, str | None] = {
    "1": None, "11": "1", "12": "1",
    "2": None, "21": "2",
    "3": None,
    "4": None, "41": "4", "49": "4",
    "5": None, "51": "5", "52": "5", "59": "5",
}

# Leaf accounts: (code, name, type, is_memo, parent_code)
_COA_COMMON: list[tuple[str, str, str, bool, str]] = [
    ("1000", "Cash in Hand",            "Asset",     False, "11"),
    ("1010", "Bank",                    "Asset",     False, "11"),
    ("1090", "Accumulated Depreciation","Asset",     False, "12"),
    ("1100", "Accounts Receivable",     "Asset",     False, "11"),
    ("1260", "Advances to Vendors",     "Asset",     False, "11"),
    ("2000", "Accounts Payable",        "Liability", False, "21"),
    ("2200", "GST Payable (Output)",    "Liability", False, "21"),
    ("2310", "Customer Advances",       "Liability", False, "21"),
    ("3000", "Owner Capital",           "Equity",    False, "3"),
    ("3010", "Drawings",                "Equity",    False, "3"),
    ("3100", "Retained Earnings",       "Equity",    False, "3"),
    ("4000", "Sales Revenue",           "Revenue",   False, "41"),
    ("4900", "Other Income",            "Revenue",   False, "49"),
    ("4901", "Unrealised FX Gain/Loss", "Revenue",   False, "49"),
    ("5000", "General Expenses",        "Expense",   False, "52"),
    ("5050", "Depreciation Expense",    "Expense",   False, "52"),
    ("5900", "Other Expenses",          "Expense",   False, "59"),
]
```

- [ ] **Step 4: Update the per-model EXTRA lists to 5-tuples (parent_code)**

In `backend/db.py`, add a `parent_code` as the 5th element to every row of `_COA_SERVICES_EXTRA`, `_COA_TRADER_EXTRA`, `_COA_MANUFACTURING_EXTRA`, `_COA_TELECOM_FRANCHISE_EXTRA`, per this mapping:

```python
_COA_SERVICES_EXTRA = [
    ("4010", "Consulting Revenue",        "Revenue",   False, "41"),
    ("4020", "Recurring Service Revenue", "Revenue",   False, "41"),
    ("2300", "Deferred Revenue",          "Liability", False, "21"),
    ("5110", "Subcontractor Costs",       "Expense",   False, "51"),
]
_COA_TRADER_EXTRA = [
    ("1200", "Finished Goods Inventory", "Asset",   False, "11"),
    ("1250", "GST Receivable (Input)",   "Asset",   False, "11"),
    ("5010", "Cost of Goods Sold",       "Expense", False, "51"),
    ("5020", "Freight In",               "Expense", False, "51"),
    ("5030", "Storage & Handling",       "Expense", False, "51"),
    ("5040", "Inventory Adjustments",    "Expense", False, "51"),
]
_COA_MANUFACTURING_EXTRA = [
    ("1200", "Raw Material Inventory",   "Asset",     False, "11"),
    ("1201", "Work-in-Progress",         "Asset",     False, "11"),
    ("1202", "Finished Goods Inventory", "Asset",     False, "11"),
    ("1210", "Customer Goods on Hand",   "Asset",     True,  "11"),
    ("1250", "GST Receivable (Input)",   "Asset",     False, "11"),
    ("2150", "Customer Goods Liability", "Liability", True,  "21"),
    ("4010", "Service Revenue (Value-Add)", "Revenue", False, "41"),
    ("5010", "Cost of Goods Sold",       "Expense",   False, "51"),
    ("5100", "Direct Labour",            "Expense",   False, "51"),
    ("5110", "Subcontractor Costs",      "Expense",   False, "51"),
    ("5200", "Manufacturing Overhead",   "Expense",   False, "51"),
    ("5210", "Indirect Materials",       "Expense",   False, "51"),
]
_COA_TELECOM_FRANCHISE_EXTRA = [
    ("1110", "Commission Receivable",         "Asset",     False, "11"),
    ("1120", "RSO Receivables",               "Asset",     False, "11"),
    ("1130", "Postpaid Customer Receivable",  "Asset",     False, "11"),
    ("1200", "SIM Card Inventory",            "Asset",     False, "11"),
    ("1201", "Scratch Card / PIN Inventory",  "Asset",     False, "11"),
    ("1202", "Device Inventory",              "Asset",     False, "11"),
    ("1203", "Bundle Code Inventory",         "Asset",     False, "11"),
    ("1204", "IMSI Inventory",                "Asset",     False, "11"),
    ("1210", "Tracker Deposit Balance",       "Asset",     False, "11"),
    ("1211", "Load Float Asset (MSR SIM)",    "Asset",     False, "11"),
    ("1212", "RSO Load Receivable",           "Asset",     False, "11"),
    ("1213", "Retail Load Receivable",        "Asset",     False, "11"),
    ("1214", "Mobile Money Float Asset",      "Asset",     False, "11"),
    ("1250", "GST Receivable (Input)",        "Asset",     False, "11"),
    ("1300", "Franchise Intangible Asset",    "Asset",     False, "12"),
    ("1301", "Accumulated Amortisation",      "Asset",     False, "12"),
    ("2010", "Operator Payable",              "Liability", False, "21"),
    ("2100", "Mobile Money Float Liability",  "Liability", False, "21"),
    ("2110", "Postpaid Collections Payable",  "Liability", False, "21"),
    ("2120", "Franchise Royalty Payable",     "Liability", False, "21"),
    ("2300", "Advance from Operator",         "Liability", False, "21"),
    ("4000", "Airtime / Recharge Revenue",        "Revenue", False, "41"),
    ("4010", "SIM Activation Revenue",            "Revenue", False, "41"),
    ("4020", "Load Uplift Commission (3%)",       "Revenue", False, "41"),
    ("4021", "Commission Income — Recharges",     "Revenue", False, "41"),
    ("4022", "Commission Income — Digital (MM)",  "Revenue", False, "41"),
    ("4023", "Commission Income — Bundles",       "Revenue", False, "41"),
    ("4030", "SIM Sale Revenue",                  "Revenue", False, "41"),
    ("4031", "Device Sales Revenue",              "Revenue", False, "41"),
    ("4040", "Postpaid Billing Revenue",          "Revenue", False, "41"),
    ("4050", "RSO Channel Revenue",               "Revenue", False, "41"),
    ("4060", "FCA Target Commission",             "Revenue", False, "41"),
    ("4061", "Franchise Incentive Income",        "Revenue", False, "49"),
    ("5010", "COGS — Devices",                    "Expense", False, "51"),
    ("5011", "COGS — SIMs",                       "Expense", False, "51"),
    ("5012", "COGS — Scratch Cards",              "Expense", False, "51"),
    ("5020", "RSO Incentives & Commissions",      "Expense", False, "52"),
    ("5021", "Retail Incentives",                 "Expense", False, "52"),
    ("5030", "Franchise Fee Amortisation",        "Expense", False, "52"),
    ("5040", "Franchise Royalty Expense",         "Expense", False, "52"),
    ("5060", "Mobile Money Transaction Costs",    "Expense", False, "52"),
    ("5070", "Tracker / Float Variance",          "Expense", False, "52"),
    ("5080", "Bad Debt — RSO Channel",            "Expense", False, "52"),
    ("5090", "Target Shortfall Penalties",        "Expense", False, "52"),
]
```

- [ ] **Step 5: Update `_coa_for` to merge groups + leaves and carry parent_code**

Replace `_coa_for` in `backend/db.py` so it returns rows of `(code, name, type, is_memo, parent_code, is_group)`:

```python
def _coa_for(business_model: str):
    """CoA template: shared group set + universal leaves + model leaves.
    Returns (code, name, type, is_memo, parent_code, is_group) sorted so that
    parents precede children (groups first by code length, then leaves)."""
    groups = [
        (code, name, gtype, False, _GROUP_PARENT[code], True)
        for (code, name, gtype) in _COA_GROUPS
    ]
    by_code = {a[0]: a for a in _COA_COMMON}
    extra_map = {
        "services":          _COA_SERVICES_EXTRA,
        "trader":            _COA_TRADER_EXTRA,
        "manufacturing":     _COA_MANUFACTURING_EXTRA,
        "telecom_franchise": _COA_TELECOM_FRANCHISE_EXTRA,
    }
    for row in extra_map.get(business_model, []):
        by_code[row[0]] = row
    leaves = [(c, n, t, m, p, False) for (c, n, t, m, p) in by_code.values()]
    # Groups first (so parents exist before children in the two-pass insert),
    # then leaves; each list ordered by code.
    return sorted(groups, key=lambda r: (len(r[0]), r[0])) + sorted(leaves, key=lambda r: r[0])
```

- [ ] **Step 6: Two-pass insert in `seed_data`**

In `backend/db.py` `seed_data`, replace the CoA insert block (the `if not account_count:` body that does `s.add_all([Account(...) ...])`) with a two-pass create that resolves `parent_id` by code:

```python
        if not account_count:
            template = _coa_for(model)
            # Pass 1: create every account (no parent yet)
            created: dict[str, Account] = {}
            for code, name, atype, is_memo, parent_code, is_group in template:
                acc = Account(code=code, name=name, type=atype, is_memo=is_memo,
                              is_group=is_group, tenant_id=tenant_id)
                s.add(acc)
                created[code] = acc
            s.flush()  # assign ids
            # Pass 2: link parents by code
            for code, name, atype, is_memo, parent_code, is_group in template:
                if parent_code:
                    created[code].parent_id = created[parent_code].id
            s.commit()
```

- [ ] **Step 7: Update the demo seeder's `_ensure_coa` to the new tuple shape**

In `backend/scripts/seed_demo.py` `_ensure_coa` (~line 360), the loop `for code, name, atype, is_memo in _coa_for(model):` now yields 6-tuples. Replace with a parent-aware top-up:

```python
    existing = {a.code: a for a in s.exec(
        select(Account).where(Account.tenant_id == tenant_id)
    ).all()}
    template = _coa_for(model)
    # Pass 1: create missing accounts
    for code, name, atype, is_memo, parent_code, is_group in template:
        if code not in existing:
            acc = Account(code=code, name=name, type=atype, is_memo=is_memo,
                          is_group=is_group, tenant_id=tenant_id)
            s.add(acc); existing[code] = acc
    s.flush()
    # Pass 2: ensure parent links
    for code, name, atype, is_memo, parent_code, is_group in template:
        if parent_code and existing[code].parent_id is None:
            existing[code].parent_id = existing[parent_code].id
    s.flush()
```

- [ ] **Step 8: Run the new test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_default_coa_hierarchy.py -v`
Expected: PASS (2 tests)

- [ ] **Step 9: Commit**

```bash
git add backend/db.py backend/scripts/seed_demo.py backend/tests/test_default_coa_hierarchy.py
git commit -m "feat(coa): hierarchical default Chart of Accounts (group parents + parented leaves) (#53 seeding)"
```

---

### Task 2: Per-model hierarchy smoke test (all 5 segments)

**Files:**
- Test: `backend/tests/test_default_coa_hierarchy.py` (append)

Verify each business model produces a valid hierarchy and posting to a group is rejected.

- [ ] **Step 1: Append the test**

```python
import pytest


@pytest.mark.parametrize("model", ["simple", "services", "trader", "manufacturing", "telecom_franchise"])
def test_every_model_coa_is_valid_hierarchy(client, model):
    tid = _signup(client, email=f"owner_{model}@acme.test", model=model)
    accts = _accounts(tid)
    by_id = {a.id: a for a in accts}
    by_code = {a.code: a for a in accts}
    # roots are the 5 type groups
    roots = [a for a in accts if a.parent_id is None]
    assert {r.code for r in roots} == {"1", "2", "3", "4", "5"}
    # no leaf is an orphan; every parent is a group; parent type matches
    for a in accts:
        if not a.is_group:
            assert a.parent_id is not None, f"{model}: leaf {a.code} orphaned"
        if a.parent_id is not None:
            p = by_id[a.parent_id]
            assert p.is_group, f"{model}: {a.code} parent {p.code} not a group"
            assert p.type == a.type, f"{model}: {a.code} type != parent type"


def test_posting_to_group_account_rejected(client):
    tid = _signup(client, email="poster@acme.test", model="simple")
    # Need auth headers for this tenant
    tok = client.post("/api/auth/login", data={
        "username": "poster@acme.test", "password": "pw12345678",
    }).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    client.cookies.clear()
    grp = client.get("/api/accounts", headers=h).json()["items"]
    g1 = next(a for a in grp if a["code"] == "1")     # Assets group
    leaf = next(a for a in grp if a["code"] == "1000")
    r = client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01", "description": "to group",
        "entries": [{"account_id": g1["id"], "debit": 10, "credit": 0},
                    {"account_id": leaf["id"], "debit": 0, "credit": 10}],
    })
    assert r.status_code == 400, r.text   # Phase-1 rule: no posting to groups
```

- [ ] **Step 2: Run**

Run: `PYTHONPATH=. uv run pytest tests/test_default_coa_hierarchy.py -v`
Expected: PASS (all, incl. 5 parametrized model cases + group-posting rejection)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_default_coa_hierarchy.py
git commit -m "test(coa): per-model hierarchy validity + group-posting rejection (#53 seeding)"
```

---

### Task 3: Full-suite reconciliation

**Files:**
- Modify: whichever existing tests assert a flat CoA, exact account counts, or post to a code that is now a group.

- [ ] **Step 1: Run the full suite, capture failures**

Run: `PYTHONPATH=. uv run pytest -q 2>&1 | tail -40`
The hierarchy adds 13 group accounts per tenant and gives leaves parents. Likely breakages: tests asserting a flat account count, tests that fetch the CoA and expect no `is_group`/`parent_id`, the demo-seed (`test_seed_demo*` if any) creating accounts, CoA-management tests asserting tree shape.

- [ ] **Step 2: Migrate each failure faithfully (file by file)**

For each failure, read the test and fix per these rules (preserve the invariant; never weaken):
- **Account-count assertions:** add 13 (the group rows) to the expected count, or assert on leaf count via `[a for a in accts if not a["is_group"]]`.
- **"CoA is flat" assumptions:** update to expect the hierarchy (roots `1`–`5`, leaves parented).
- **Posting to a code that is now a group:** none of the standard auto-posting codes became groups (1100/2200/4000/5010/1200 are all still leaves) — but if any test posts to `1`/`2`/`3`/`4`/`5` or a sub-group code, repoint to a leaf.
- **`9xxx` ad-hoc test accounts:** unaffected (they create their own leaves); if a test now needs a parent, it may set `parent_id` or leave it (a `9xxx` root leaf is allowed).
- If a failure is a genuine product-code regression (not a CoA-shape assumption), STOP and report it.

- [ ] **Step 3: Re-run until green**

Run: `PYTHONPATH=. uv run pytest -q 2>&1 | tail -15`
Report the final pass count and list every test file you touched + the invariant each preserved.

- [ ] **Step 4: Commit**

```bash
git add backend/tests
git commit -m "test: reconcile suite to hierarchical default CoA (#53 seeding)"
```

---

## Self-Review notes

- **Spec coverage:** §1 (hierarchical default CoA, both db.py + demo via shared `_coa_for`) → Tasks 1-2; §2 (test reconciliation) → Task 3. Demo-seed §3–§8 are Phase B (separate plan).
- **Leaf codes preserved:** every original 4-digit code is unchanged; only group rows (`1`/`11`/`12`/`2`/`21`/`3`/`4`/`41`/`49`/`5`/`51`/`52`/`59`) are added and `parent_code` attached. Auto-posting defaults (1100/2200/4000/5010/1200/…) remain postable leaves.
- **Type consistency:** group `type` matches its leaves' type (enforced by the Task 2 test `p.type == a.type`); the `parent_code` values reference only codes defined in `_COA_GROUPS`.
- **Two-pass insert** appears in both `seed_data` (db.py) and `_ensure_coa` (seed_demo) with the same 6-tuple unpack `(code, name, atype, is_memo, parent_code, is_group)`.
- **Migration note:** `seed_data` runs on signup (create_all in dev); no Alembic change needed since `is_group`/`parent_id` columns already exist (Phase 1). Existing demo tenants are refreshed via purge+reseed (Phase B / admin card), not migrated in place.
