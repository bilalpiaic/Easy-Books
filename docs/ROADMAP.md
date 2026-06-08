# Easy-Books — Development Roadmap

_Last reviewed: 2026-06-08 (against `feature/issue53-phase2-coa-rollup`; #53 Phase 2 shipped)_

## Status summary

| State | Issues |
|-------|--------|
| ✅ **Done & closed** | #43 (Financial Reporting/Inventory/Sales-Purchase, 7 sections), #44 (Voucher Series, Phase 1+2), #45 (Consolidated/Sub-Ledger GL), #50 (Selling/Cost Price), #51 (Posted-doc editing) |
| 🟡 **Partially done (open)** | #53 (Multi-Level COA — **Phase 1 shipped v2.4.0; Phase 2 shipped** — hierarchical roll-up + drill-down for TB/BS/P&L; Cash Flow / dashboard summaries remain as future scope), #52 (COA/Dashboard/UX bundle — §1/§2/§5 redirected to #53/#41/#40; net-new §3/§4/§6 remaining) |
| 🔴 **Not started (open)** | #40, #41, #42, #47, #48 |

Shipped this cycle: v2.2.0 → v2.3.0 → v2.3.1 → v2.3.2 → **v2.4.0**.

---

## Remaining work — concrete plans

### 1. #47 + #48 — Posted-edit hardening (mini-batch) · effort **S** · priority **Med**
Two small follow-ups from the posted-edit feature; do together (one branch/PR).

- **#48 — `block_negative_stock` on edit.** `create_invoice` reads the setting and passes `block_negative=` to `consume_stock` (`invoices.py:234-241,287`); `update_invoice`'s re-consume omits it. **Fix:** mirror that read + pass in `update_invoice`. Test: tenant with the setting on, edit a posted invoice to a qty exceeding stock → 400. **Effort XS.**
- **#47 — Deferred-revenue rebuild on edit.** When a posted `is_deferred` invoice is edited, reverse/rebuild its deferral schedule. **Approach:** in `update_invoice`, if `is_deferred`, void the existing `DeferredRevenueSchedule` + un-recognised entries (see `routers/deferred_revenue.py`) and rebuild from the edited lines; **block if any period already recognised** (policy: like block-if-paid). Tests: edit pre-recognition rebuilds; edit post-recognition blocked. **Effort S-M.**
- **Deps:** posted-edit (done). **No design needed** beyond the recognised-period policy.

### 2. #53 Phase 2 — COA reporting roll-up & drill-down · ✅ **SHIPPED**
Hierarchical roll-up + drill-down for Trial Balance, Balance Sheet, and P&L.
- **Shipped:** `GET /api/reports/trial-balance` → `{tree, totals}` (nested tree, parent = Σ children + own, leaf nodes carry `debit`/`credit`); `GET /api/reports/balance-sheet` (single period) → `{assets, liabilities, equity, totals}`; `GET /api/reports/income-statement` (single period) → `{revenue, expenses, totals}`. Comparison-mode responses remain flat `{current, comparison}` (unchanged). `services/account_tree.py` implements the shared roll-up logic. All existing test assertions migrated to new shapes; full suite green (313 tests).
- **Remaining future scope:** Cash Flow hierarchical roll-up; dashboard financial summaries; frontend expand/collapse tree rendering; drill-down statements → ledger → voucher for BS/P&L lines.

### 3. #41 (= #52 §2) — Recent Transactions enhancement · effort **S-M** · priority **Med**
- **Scope:** dashboard Recent Transactions shows full columns (Date · Voucher No · **Voucher Type** · Account · Party · Narration · Amount); user-selectable columns (checkbox, persisted); voucher-type filter; sort by date; quick search; click-to-open.
- **Approach:** reuse **`GET /api/reports/journal`** (already returns `voucher_type` + supports `?voucher_type=` filter from #44). Frontend: enhance the Recent-Transactions widget on `dashboard/page.tsx` — column-config dropdown (persist in settings or localStorage), filter/sort/search, row→`/journal/{transaction_id}`.
- **Deps:** voucher series (#44, done). Mostly frontend.

### 4. #52 §4 — Voucher-type LOV on New Entry · effort **S** · priority **Med**
- **Scope:** the manual New-Entry/JV form (`entry/page.tsx`) gets a **voucher-type selector** that drives the number series / posting classification (entry layout/posting logic per type is future).
- **Approach:** `post_transaction` already accepts `voucher_type` (#44). Add a voucher-type `<select>` (from `lib/voucherTypes.ts`) to the manual entry form; thread it to the create-transaction endpoint → typed number. **Effort S** (leverages #44).
- **Deps:** voucher series (#44, done).

### 5. #40 (= #52 §5) — Full-page data-entry forms · effort **M-L** · priority **Med**
- **Scope:** New Invoice/Bill (+ JV/Receipt/Payment + Product/Customer/Supplier masters) use **full-page** layout instead of modals.
- **Approach:** the invoice/bill create/edit currently lives as a **modal inside the list page** (`invoices/page.tsx`). Convert to dedicated routes (`/invoices/new`, `/invoices/[id]/edit`) reusing the existing form + `LineItemsTable`. Sizeable but mechanical; the density system already helps. **Needs a short design** (route structure, where the shared form lives).
- **Deps:** interacts with #52 §6 (nav controls). **Effort M-L.**

### 6. #52 §6 — Standard navigation controls · effort **M** · priority **Med**
- **Scope:** consistent Previous / Home (Dashboard) / Home (Section) / breadcrumbs on every screen; designed to later support Next/Prev record, Favorites, Recently-Visited.
- **Approach:** a shared top-of-page nav component + a route→section map; mounted in the dashboard layout. **Needs a small design** (section taxonomy, breadcrumb source). **Effort M.**

### 7. #42 — Telecom dashboard Stock & Issuance table · effort **M** · priority **Med (telecom tenants)**
- **Scope:** table — Name · Stock Issuance · Load Issued · HLR Issued · Other Stock Issued · FCA Hits · Closing (SIM Issued − FCA) · Closing (HLR Issued + Load − Bank Deposits).
- **Approach:** new aggregation in `telecom_reports.py` (alongside the existing `/dashboard`, `/rso-ledger`, `/float-statement`) over the `tc_*` telecom tables; telecom dashboard table on `telecom/page.tsx`. **Needs telecom-domain design** (which tc_* tables/events feed each column; the FCA + bank-deposit definitions). **Effort M.**

### 8. #52 §3 — User-customizable dashboard · effort **L** · priority **Low-Med**
- **Scope:** drag-&-drop widgets, hide/show, save per-user layout (Cash Position, Bank Balances, AR/AP Aging, Sales/Purchase/Inventory/Profit summaries, Recent Transactions, Top Customers/Products, Alerts).
- **Approach:** a widget registry + a layout persisted per user; a grid/drag library. **Largest UX piece — its own spec.** Do last.

---

## Recommended sequence
1. **#47 + #48** posted-edit hardening (S, closes 2 issues, low risk).
2. ~~**#53 Phase 2**~~ ✅ COA reporting roll-up/drill-down — **shipped**.
3. **#41** Recent Transactions (S-M; reuses voucher journal endpoint).
4. **#52 §4** Voucher LOV on New Entry (S; leverages #44).
5. **#40** Full-page forms (M-L UX refactor).
6. **#52 §6** Standard nav controls (M).
7. **#42** Telecom Stock & Issuance table (M; domain).
8. **#52 §3** Customizable dashboard (L; last).

**Cross-cutting note:** each non-trivial item (esp. #40, #42, #52 §3/§6) gets its own brainstorm → spec → plan → subagent execution, consistent with how v2.2.0–v2.4.0 shipped. The two hardening items (#47/#48) and #52 §4 are small enough to spec lightly.
