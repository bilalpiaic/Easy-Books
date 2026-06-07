# Multi-Level COA Phase 1 (#53) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). Backend tests: `cd backend && PYTHONPATH=. uv run pytest <file> -v` (PYTHONPATH=. REQUIRED). **Posting touches every GL path — be careful; if a posting/migration detail is ambiguous after reading the code, STOP and report BLOCKED.**

**Goal:** Multi-level CoA on `parent_id` with posting allowed only on active, non-group, leaf accounts; CoA tree management + validation + next-code suggestion. Reporting roll-up is Phase 2.

**Branch:** `feature/issue53-multilevel-coa-phase1` (off main). **Spec:** `docs/superpowers/specs/2026-06-07-multilevel-coa-phase1-design.md`.

---

### Task 1 — Model + migration + posting restriction

**Files:** `backend/models.py`, `backend/services/accounts.py` (new), `backend/services/posting.py`, `backend/alembic/versions/<rev>_account_group_active.py` (new), `backend/tests/test_account_posting_control.py`

- [ ] **Step 1 (test):**
```python
# backend/tests/test_account_posting_control.py
from sqlmodel import Session
import db as _db_module
from models import Account

def _acct(client, h, code, name, type="Asset", parent_id=None, is_group=False):
    return client.post("/api/accounts", headers=h, json={
        "code": code, "name": name, "type": type,
        "parent_id": parent_id, "is_group": is_group,
    }).json()

def _post_jv(client, h, dr_code, cr_code, amt=10):
    # confirm the manual transactions payload by reading routers/transactions.py
    return client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01", "description": "t",
        "entries": [{"account_code": dr_code, "debit": amt, "credit": 0},
                    {"account_code": cr_code, "debit": 0, "credit": amt}],
    })

def test_cannot_post_to_group_account(client, admin_headers):
    h = admin_headers
    g = _acct(client, h, "9100", "Header", is_group=True)
    leaf = _acct(client, h, "9101", "Leaf")
    r = _post_jv(client, h, "9100", "9101")
    assert r.status_code == 400 and "group" in r.text.lower()

def test_cannot_post_to_parent_with_children(client, admin_headers):
    h = admin_headers
    p = _acct(client, h, "9200", "Parent")
    c = _acct(client, h, "9201", "Child", parent_id=p["id"])
    r = _post_jv(client, h, "9200", "9201")   # 9200 now has a child → not postable
    assert r.status_code == 400

def test_post_to_normal_leaf_ok(client, admin_headers):
    h = admin_headers
    a = _acct(client, h, "9300", "A"); b = _acct(client, h, "9301", "B")
    r = _post_jv(client, h, "9300", "9301")
    assert r.status_code in (200, 201)
```
> Confirm the manual-transaction endpoint + payload (account_code vs account_id) and that `/api/accounts` accepts `is_group`/`parent_id` — read `routers/transactions.py` + `routers/accounts.py` and adjust.

- [ ] **Step 2:** run → fail. `PYTHONPATH=. uv run pytest tests/test_account_posting_control.py -v`
- [ ] **Step 3 (model):** add to `Account` in `models.py`:
```python
    is_group: bool = Field(default=False, index=True)
    is_active: bool = Field(default=True)
```
- [ ] **Step 4 (helpers):** `backend/services/accounts.py`:
```python
from sqlmodel import Session, select, func
from models import Account, JournalEntry

def account_has_children(session, tenant_id, account_id) -> bool:
    return session.exec(
        select(func.count()).select_from(Account).where(
            Account.tenant_id == tenant_id, Account.parent_id == account_id)
    ).one() > 0

def account_has_postings(session, tenant_id, account_id) -> bool:
    return session.exec(
        select(func.count()).select_from(JournalEntry).where(
            JournalEntry.tenant_id == tenant_id, JournalEntry.account_id == account_id)
    ).one() > 0

def assert_account_postable(session, tenant_id, account) -> None:
    from fastapi import HTTPException
    if account.is_group:
        raise HTTPException(400, f"Cannot post to '{account.code} {account.name}' — it is a group/header account.")
    if not account.is_active:
        raise HTTPException(400, f"Cannot post to '{account.code} {account.name}' — it is inactive.")
    if account_has_children(session, tenant_id, account.id):
        raise HTTPException(400, f"Cannot post to '{account.code} {account.name}' — it has sub-accounts; post to a detail account.")
```
(Confirm `JournalEntry.tenant_id` exists; if entries are tenant-scoped via their transaction, count via a join to Transaction instead.)
- [ ] **Step 5 (posting):** in `services/posting.py`, in the per-entry account validation (`_check_accounts_belong_to_tenant` ~line 101), after confirming the account belongs to the tenant, call `assert_account_postable(session, tenant_id, account)`. Import the helper. This makes EVERY posting path enforce it.
- [ ] **Step 6 (migration):** Alembic revision adding `is_group` (Boolean, server_default false, not null) + `is_active` (Boolean, server_default true, not null), existence-guarded, SQLite-safe. `uv run alembic upgrade head`.
- [ ] **Step 7:** run tests → pass. Then full suite `PYTHONPATH=. uv run pytest -q` — **existing posting tests may now fail if any seeded/test account being posted to has children or is a group.** Investigate each: a legitimately-flat seeded account should stay postable (no children, not group) → those tests pass. If a test posts to an account that the seed makes a parent, that's a real signal — fix the test/seed, don't weaken the check. Report any such case.
- [ ] **Step 8:** commit `feat(accounts): is_group/is_active + posting restricted to active leaf accounts`.

---

### Task 2 — Accounts router: hierarchy validation, next-code, activate, tree payload

**Files:** `backend/routers/accounts.py`, `backend/services/accounts.py`, `backend/tests/test_account_hierarchy.py`

- [ ] **Step 1 (test):** in `test_account_hierarchy.py`:
  - list/tree payload includes `parent_id`, `is_group`, `is_active`, `has_children`, `postable`, `depth`.
  - create two accounts with the same name under the SAME parent → 2nd returns 400 (dup name within parent); same name under DIFFERENT parents → OK.
  - set an account's `parent_id` to itself or a descendant → 400 (cycle).
  - create a child under an account that already has journal entries → 400 ("has postings").
  - `GET /api/accounts/next-code?parent_id={p}` → returns a non-empty code not already used under the tenant.
  - `PATCH /api/accounts/{id}/active?is_active=false` then it's excluded from postable.
- [ ] **Step 2:** run → fail.
- [ ] **Step 3:** implement in `routers/accounts.py`:
  - **create/update:** accept `is_group`, `is_active`; validate dup-name-within-parent (tenant + parent_id + name), no-cycle (walk parent chain), and reject creating/moving a child under an account that `account_has_postings`. Default `type` from parent when omitted.
  - **list/tree:** add the computed fields (`has_children`, `postable`, `depth`). Keep the existing flat list working (don't break callers); add the fields to each item.
  - **`GET /api/accounts/next-code`:** suggest the next free code under the parent (parent.code + next sequential numeric suffix, or `parent.code-01`; for no parent, next top-level). Pure function in `services/accounts.py`, tested.
  - **`PATCH /api/accounts/{id}/active`:** toggle `is_active` (tenant-scoped).
- [ ] **Step 4:** run → pass; regression `PYTHONPATH=. uv run pytest -k "account" -q`.
- [ ] **Step 5:** commit `feat(accounts): hierarchy validation, next-code, activate/deactivate, tree fields`.

---

### Task 3 — Frontend: CoA tree management + postable pickers

**Files:** `frontend/src/app/(dashboard)/coa/page.tsx`; the manual New-Entry/JV account picker (read `frontend/src/app/(dashboard)/entry/page.tsx` or wherever JV lines pick accounts)

- [ ] **Step 1:** Read the current `coa/page.tsx` and the accounts list usage; heed `frontend/AGENTS.md`.
- [ ] **Step 2 (tree view):** render accounts as an expandable parent→child tree (indent by `depth`); mark each row **Header** (`is_group` or `has_children`) vs **Posting** (`postable`); inactive rows muted with an Activate toggle. Use `ui-*` density classes.
- [ ] **Step 3 (create/edit modal):** parent picker (any account), name, type (default from parent), code with a **"Suggest"** button calling `/api/accounts/next-code?parent_id=`, `is_group` toggle, `is_active` toggle. Surface backend 400 validation messages inline.
- [ ] **Step 4 (activate/deactivate):** wire the toggle to `PATCH /api/accounts/{id}/active`.
- [ ] **Step 5 (postable pickers):** in the manual New-Entry/JV line account selector, filter the options to `postable` accounts only (group/inactive/parent accounts not selectable). (Invoice/bill AR/AP/Revenue selectors: optional in Phase 1 — note if done.)
- [ ] **Step 6:** `cd frontend && npm run lint && npm run build` clean (no NEW lint errors; pre-existing unrelated ones fine).
- [ ] **Step 7:** Manual: build a Group→child hierarchy; posting to a group/parent is blocked in the JV picker (not selectable) and by the API; activate/deactivate works; next-code suggests.
- [ ] **Step 8:** commit `feat(coa): multi-level tree management + postable-only account pickers`.

---

### Task 4 — Verification

- [ ] **Step 1:** full backend suite green: `cd backend && PYTHONPATH=. uv run pytest -q` (note + fix any posting tests that legitimately broke due to the new restriction — only where a test posted to a now-non-postable account; don't weaken the rule).
- [ ] **Step 2:** `alembic upgrade head` clean from a fresh DB; existing seeded accounts all `postable=true`.
- [ ] **Step 3:** `cd frontend && npm run lint && npm run build` clean.
- [ ] **Step 4:** Manual sweep: CoA tree create/edit/activate; posting control enforced (API + JV picker); reports unaffected (still flat).
- [ ] **Step 5:** commit final tweaks; PR body: "#53 Phase 1 — multi-level CoA model + posting control + tree management. Phase 2 (report roll-up/drill-down) to follow. Supersedes #52 §1."

---

## Self-Review Notes
- Single chokepoint: `assert_account_postable` in `post_transaction` covers every GL path — invoices/bills/payments/manual all enforced via one helper (DRY).
- Migration is purely additive (two boolean columns, safe defaults) — existing accounts stay postable; no renumbering (codes preserved so default_ar_account/cash heuristics keep working).
- Highest risk: an existing test that posts to an account the seed makes a parent/group → that's a real signal, fix the data not the check (Task 1 Step 7).
- Execution-time verifications flagged inline: manual-transaction payload (Task 1), `JournalEntry` tenant-scoping for the postings count (Task 1 Step 4), the JV account-picker location (Task 3).
- Out of scope: report roll-up/drill-down (Phase 2).
