# Seeding-Layer Modernization — Hierarchical CoA + Demo Regen — Design

_Date: 2026-06-08 · Branch: `feature/seed-regen-hierarchical-coa` · Base: `main` @ v2.5.0_

## Problem

Recent releases shipped multi-level Chart of Accounts (Phase 1 v2.4.0 + Phase 2
v2.5.0 hierarchical reporting), deferred-revenue origination (#47), voucher series
(#44), and comparative statements (#43). But the **seeding layer never caught up**:

- Both Chart-of-Accounts sources are **flat** — `db.py` `_coa_for()` (the default CoA
  every tenant gets on signup) and `scripts/seed_demo.py` (the 5 demo tenants). So the
  new roll-up TB/BS/P&L render every account as a flat root for **all** tenants.
- The demo seeder's `_seed_deferred_revenue` builds `DeferredRevenueSchedule` rows
  **directly** — it does not exercise the #47 origination path (no 2300 posting split).
- Voucher types, multi-period spread, and multi-user audit attribution are thin or absent.

This spec modernizes the seeding layer so a freshly seeded environment demonstrably
exercises the current feature set across all 5 business segments.

## Scope (decided)

This is the **seed-regen** sub-project (docs-regen is a separate spec to follow).

- **In:** hierarchical default CoA in `db.py` (every tenant); test reconciliation;
  demo-seed upgrades — deferred origination, voucher types, multi-period (2 FYs),
  multiple users + audit attribution; purge-and-reseed regeneration; seed tests.
- **Out (future / separate):** docs regeneration (next spec); posted-document-editing
  scenarios (a user action, not seedable); Cash Flow / dashboard hierarchy (those
  product features are themselves future scope).

## Decisions (locked during brainstorming)

1. **Two sub-projects, seed-regen first** — docs-regen follows in its own spec.
2. **CoA hierarchy applies to BOTH** the default signup CoA (`db.py`) and the demo seed.
3. **Regeneration = purge + fresh reseed** (demo data is disposable; never touches real data).
4. **Coverage targets:** hierarchical CoA, deferred origination, voucher types,
   multi-period data, multiple users.
5. **CoA expressed as explicit parent/child tuples** with `is_group` group rows
   (two-pass insert), not derived from code prefixes.
6. **Surgically extend** `seed_demo.py`, do not rewrite it.
7. **Multi-user = audit-log attribution + populated user list** (no per-transaction
   owner field exists in the schema — `Transaction`/`JournalEntry` have none; only
   `AuditLog.user_id` records the actor).

## §1 · Hierarchical default CoA (`db.py`)

Restructure `_COA_COMMON` + per-model `_EXTRA` lists from `(code, name, type, is_memo)`
to `(code, name, type, is_memo, parent_code)`, adding standard **group parent** rows
(`is_group=True`, `parent_code=None` for roots). Target shape (illustrative, per the
existing account set — exact leaves preserved):

```
1000 Assets (group)
  1100 Current Assets (group)
    1110 Cash, 1120 Bank, 1200 Accounts Receivable, 1260 …, 1090 …
  1200x Inventory (group, where present)         # trader/manufacturing
  1500 Non-Current Assets (group)
    fixed-asset + accumulated-depreciation leaves
2000 Liabilities (group)
  2100 Current Liabilities (group)
    2200 GST Payable, 2300 Deferred Revenue, 2310 …, AP …
3000 Equity (group)  → capital / retained-earnings leaves
4000 Revenue (group) → sales / service / other-income leaves
5000 Expenses (group)
  5100 COGS (group) → cogs leaves
  5200 Operating Expenses (group) → expense leaves
```

`seed_data()` (in `db.py`) does a **two-pass insert**: create all accounts, then set
`parent_id` by resolving `parent_code`; group rows get `is_group=True`. Every existing
**leaf code is preserved** (so auto-posting defaults like 1100/2200/4000/5010/1200 keep
working). Posting remains restricted to active leaves (Phase-1 rule, already enforced).
Group accounts carry no postings; their balances come from roll-up.

**Single source of truth:** the demo seeder must consume `db.py`'s hierarchical CoA
definitions — if `seed_demo.py` currently duplicates a `_coa_for`, consolidate it to
import `db.py`'s (verify during planning) so there is exactly one CoA definition and demo
tenants get a structure identical to real tenants. No second, drifting CoA list.

## §2 · Test reconciliation

The hierarchy adds group accounts, changes account counts, and makes some codes
non-postable parents. After §1, run the full suite and migrate each failure faithfully:
- Tests asserting a flat CoA / exact account counts → update expectations to the tree.
- Tests posting directly to a code that is now a **group** → post to the correct leaf.
- Never weaken an accounting assertion; if a failure looks like a real regression in
  product code (not a seed/CoA-shape mismatch), STOP and report.
- Tests using ad-hoc `9xxx` codes create their own leaves and are unaffected.

## §3 · Demo seed — deferred-revenue origination

In `scripts/seed_demo.py`:
- Mark 1–2 service/subscription products `is_deferred=True` with a `recognition_months`
  (segments: services, simple, telecom where sensible).
- In `_seed_invoices`, for a deferred-product line, credit **Deferred Revenue (2300)**
  (via `services.deferred.resolve_deferred_account`) instead of the revenue account, and
  call `services.deferred.create_schedules(...)` to originate the real schedule(s).
- After invoices are posted, run recognition for 1–2 elapsed periods (reuse the
  `run-recognition` logic) so some schedules show `recognised_amount > 0`.
- Remove/replace the inert `_seed_deferred_revenue` direct-insert.

## §4 · Demo seed — voucher types

Thread `voucher_type` through the seed's `post_transaction` calls: **SL** sales invoices,
**PU** bills, **CR** payments received, **CP** bill payments, **JV** manual journals,
**CN/DN** credit/debit notes, **Contra** for any bank↔cash transfers. So voucher-series
numbering, the Cash/Bank Book, and voucher-type filters have realistic data.

## §5 · Demo seed — multi-period data

Extend `_spread_dates` (and callers) so seeded transactions populate the **prior fiscal
year and the current-year-to-date** (anchored at run time; today 2026-06-08 → FY2025 +
FY2026-to-date). Comparative statements and period-over-period reports then have real
prior-period figures.

## §6 · Demo seed — multiple users + audit attribution

Create **2–3 users per demo tenant** (owner + accountant + clerk, distinct emails, shared
demo password). Rotate which `user` is passed into seeding/posting calls so `AuditLog`
rows are attributed to different actors and the users screen is populated. No
per-transaction owner is fabricated (schema has none).

## §7 · Regeneration mechanics

"Regenerate" = **purge + fresh reseed** per tenant via the existing admin purge +
`seed_one_tenant` path. The seed stays idempotent for top-up, but the canonical refresh
is purge→reseed. Verify each of the 5 segments (simple, services, trader, manufacturing,
telecom_franchise) seeds cleanly end-to-end.

Post-seed reconciliation per tenant: Trial Balance balances; hierarchical TB/BS/P&L
render with real subtotals; ≥1 deferred schedule with partial recognition; voucher types
present; transactions span two FYs; ≥2 users with audit-log rows.

## §8 · Testing

- **Default-CoA test** (`tests/`): a fresh signup tenant gets a hierarchical CoA — group
  parents exist (`is_group=True`), leaves carry `parent_id`, posting to a group is
  rejected (Phase-1), and the `build_account_tree` roll-up reconciles (parent == Σ leaves).
- **Demo-seed smoke test** (per segment): seed each of the 5 segments into an in-memory
  DB and assert: TB balances; ≥1 `DeferredRevenueSchedule` with `recognised_amount > 0`;
  distinct `voucher_type`s present on transactions; transaction dates span ≥2 fiscal
  years; ≥2 users exist with `AuditLog` rows attributed to more than one.
- Full backend suite green after §2 fixups.

## Success criteria

A purge-and-reseed of any of the 5 demo tenants yields data that visibly exercises the
v2.5.0 feature set: the hierarchical statements show rolled-up subtotals, the deferred-
revenue screen shows originated schedules mid-recognition, the Cash/Bank Book and
voucher filters are populated, comparative statements have a prior year, and the Audit
Log shows multiple actors. Every real tenant created via signup also receives the
hierarchical CoA. The full test suite is green.
