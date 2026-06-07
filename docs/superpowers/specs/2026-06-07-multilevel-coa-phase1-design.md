# Design: Multi-Level Chart of Accounts — Phase 1 (#53)

**Date:** 2026-06-07
**Status:** Approved
**GitHub issue:** #53 (also supersedes #52 §1)

## Overview

Turn the Chart of Accounts into a real **multi-level hierarchy** with **posting
control**: arbitrary-depth parent/child accounts where only **leaf "Detail"
accounts** can be posted to, and **group/header accounts** act as
reporting/control nodes. Phase 1 delivers the account model, posting restriction,
CoA tree management, next-code suggestion, and validation. Reporting roll-up &
drill-down (TB/BS/P&L/GL parent subtotals) is **Phase 2**.

**Branch:** `feature/issue53-multilevel-coa-phase1`, off `main`.

### Locked decisions
| Decision | Choice |
|----------|--------|
| Hierarchy | **Flexible N-level on existing `parent_id`**; keep existing codes (no renumbering); structured codes offered as optional auto-suggestion, not enforced |
| Posting control | Explicit **`is_group`** flag (non-postable) **+** "non-leaf (has children) can't post" **+** active-only |
| Phasing | **Phase 1 = foundation** (this spec); Phase 2 = report roll-up/drill-down |
| Existing accounts | Become **active postable leaves**; hierarchy built over them at the user's pace |
| Code generation | Suggest a sensible **editable** next code under a parent (e.g. `1100`→`1101` or `1100-01`); not a rigid format |

## Key facts (verified)
- `Account` (models.py:112) has `code`, `name`, `type`, `parent_id` (nullable FK to
  account.id, arbitrary depth), `is_memo`. **No** `is_active`, no posting
  restriction, no "group" concept.
- `post_transaction` (services/posting.py) does **not** restrict which accounts are
  postable; `_check_accounts_belong_to_tenant` (posting.py:101) is the natural place
  to add a postable check.
- Reports group flat by `Account.id` — **no parent roll-up** today (that's Phase 2).
- Lots of logic is **code-keyed**: `default_ar_account="1100"`,
  `default_ap_account="2000"`, cash/bank "10xx" heuristic, COGS "5010", etc. →
  codes must NOT change (hence flexible-on-parent_id, keep-codes).
- `routers/accounts.py` create/update already accept `parent_id`; unique
  constraint on (tenant_id, code) exists.

## Architecture

### Account model (additive)
```python
# Account (models.py)
is_group:  bool = Field(default=False)   # header/control account — never postable
is_active: bool = Field(default=True)    # activate / deactivate
```
`parent_id` (existing) supplies depth; "level" (Group/Main/Sub/Detail) is **derived
depth**, shown via indentation — not a fixed 4-level enforcement. Alembic migration
adds both columns (SQLite-safe, guarded, server_default). Existing rows →
`is_group=false, is_active=true` (active postable leaves).

### Posting control (core rule)
New helper `assert_account_postable(session, tenant_id, account)` — raises
`HTTPException(400, ...)` unless the account is **all of**: `is_group == False`,
`is_active == True`, and **leaf** (no child accounts for the tenant). Called from
`post_transaction`'s per-entry account validation (extend
`_check_accounts_belong_to_tenant` or add a sibling check) so EVERY posting path
(invoices, bills, payments, manual JV, etc.) is covered by the single GL writer.
Clear message, e.g. "Cannot post to '1100 Accounts Receivable' — it is a
group/header account" or "— it has sub-accounts; post to a detail account".

### CoA management — `routers/accounts.py` + `/coa` page
- **Tree/list payload:** extend the accounts list (or add `GET /api/accounts/tree`)
  to return per account: `parent_id`, `is_group`, `is_active`, `has_children`
  (bool), `postable` (= `!is_group && is_active && !has_children`), and `depth`.
- **Create / Edit:** parent picker (any account), name, type, code, `is_group`
  toggle, `is_active`. On create, the `type` defaults from the parent's type.
- **Next-code:** `GET /api/accounts/next-code?parent_id=` → suggests the next free
  code under the parent (parent code + next sequential child, e.g. `1100`→`1101`,
  or `1100-01` if a structured child scheme is detected); editable. Falls back to a
  sensible top-level suggestion when no parent.
- **Activate/Deactivate:** `PATCH /api/accounts/{id}/active?is_active=`.
- **Account pickers elsewhere:** the manual New-Entry / JV line account selector
  (and invoice/bill AR/AP/Revenue selectors) filter to **postable** accounts
  (`postable=true`). At minimum the manual journal-entry picker in Phase 1.

### Validation (router-level, tenant-scoped)
- Duplicate **code** per tenant → existing unique constraint (surface a clean 400).
- Duplicate **name within the same parent** → new check on create/update.
- **No cycles** — an account cannot be set to its own descendant/itself as parent.
- **Cannot add a child to an account that already has JournalEntry rows** (it must
  remain a posting leaf — prevents orphaning existing postings). Enforced when
  setting a `parent_id` to such an account, or when creating a child under it.
- A `is_group=true` account cannot have postings (and vice-versa: can't flag a
  posted account as group). Surfaced as 400.
- Delete already blocked when referenced; keep that behaviour.

## Components / boundaries
- `models.py`: `Account.is_group`, `Account.is_active` + Alembic migration.
- `services/accounts.py` (new, small) or posting.py: `assert_account_postable`,
  `account_has_children`, and the next-code suggestion logic — pure, testable.
- `routers/accounts.py`: hierarchy-aware create/update + validation, `next-code`,
  activate/deactivate, tree/list payload.
- `services/posting.py`: call `assert_account_postable` in the account-validation step.
- `frontend/.../coa/page.tsx`: tree management UI; postable-only account pickers
  (start with the manual entry/JV line picker).

## Testing
- **Posting:** to a group account → 400; to a non-leaf (has children) → 400; to an
  inactive account → 400; to a normal active leaf → OK. Manual JV + an invoice post
  both honour it.
- **CoA management:** create under a parent (parent becomes non-postable); type
  defaults from parent; dup-name-within-parent rejected; cycle rejected; can't add a
  child to an account that has journal entries; activate/deactivate; `next-code`
  returns a free code under the parent.
- **Migration:** adds both columns; all existing seeded accounts remain
  `postable=true`; a fresh `create_all` DB has the columns.
- **Reports unaffected** in Phase 1 (still flat) — confirm existing report tests stay
  green.

## Out of scope (Phase 2)
Parent-subtotal roll-up and expand/drill-down in Trial Balance, Balance Sheet,
P&L, Cash Flow, General Ledger, and dashboard summaries; statements→ledger→voucher
drill navigation. Phase 1 leaves reporting flat; the hierarchy data it establishes
is what Phase 2 rolls up.
