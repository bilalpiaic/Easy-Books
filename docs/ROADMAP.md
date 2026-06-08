# Easy-Books — Development Roadmap

_Last reviewed: 2026-06-08 (against `main` @ v2.5.0; #47/#48 + #53 Phase 2 merged)_

## Status summary

| State | Issues |
|-------|--------|
| ✅ **Done & closed** | #43 (Financial Reporting/Inventory/Sales-Purchase, 7 sections), #44 (Voucher Series, Phase 1+2), #45 (Consolidated/Sub-Ledger GL), #48 (posted-edit `block_negative_stock` hardening — v2.5.0), #47 (deferred-revenue origination — v2.5.0), #50 (Selling/Cost Price), #51 (Posted-doc editing), #53 (Multi-Level COA — **Phase 1 v2.4.0 + Phase 2 v2.5.0**) |
| 🟡 **Partially done (open)** | #52 (COA/Dashboard/UX bundle — §1/§2/§5 redirected to #53/#41/#40; net-new §3/§4/§6 remaining) |
| 🔴 **Not started (open)** | #40, #41, #42 |

Shipped this cycle: v2.2.0 → v2.3.0 → v2.3.1 → v2.3.2 → v2.4.0 → **v2.5.0** (#47 deferred-revenue origination, #48 posted-edit negative-stock hardening, #53 Phase 2 hierarchical reporting).

**Post-v2.5.0 infrastructure (on `main`):** seeding-layer modernization — the **default Chart of Accounts is now hierarchical for every tenant** (group skeleton + parented leaves in `db.py`), and the demo seed exercises deferred-revenue origination, voucher types, two fiscal years, and multiple users per tenant. **In progress:** documentation regeneration (all `.md` + the in-app guide/workflow pages reconciled to v2.5.0; branch `feature/docs-regen`).

---

## Remaining work — concrete plans

### 1. #47 + #48 — Posted-edit hardening + deferred revenue · ✅ **SHIPPED (v2.5.0)**
- **#48 — `block_negative_stock` on edit.** `update_invoice`'s re-consume now mirrors `create_invoice`: reads the setting, passes `block_negative=`, wraps the loop in `try/except InventoryError → rollback + 400`.
- **#47 — Deferred-revenue origination** (re-scoped from "rebuild on edit" — the origination path never existed). `services/deferred.py` (`plan_deferral`/`resolve_deferred_account`/`create_schedules`/`has_any_recognition`/`reverse_schedules`); `create_invoice` splits net revenue → Deferred Revenue (2300) for `product.is_deferred` lines + builds one schedule per deferred line; `update_invoice` blocks edits once recognised, else reverses+rebuilds; product form exposes the flags; existing recognition engine reused. GST posts immediately; deferred GL credit clamped to subtotal (multi-currency-safe).

### 2. #53 Phase 2 — COA reporting roll-up & drill-down · ✅ **SHIPPED (v2.5.0)**
Hierarchical Trial Balance, Balance Sheet, and P&L.
- **Shipped:** `services/account_tree.py` shared roll-up engine; `/trial-balance` → `{tree, totals}`, `/balance-sheet` (single period) → `{assets, liabilities, equity, totals}` (RE-CUR synthetic equity node preserved), `/income-statement` (single period) → `{revenue, expenses, totals}` + `net_profit`; comparison mode stays flat. Reusable `<AccountTree>` frontend component with expand/collapse + **leaf drill-to-ledger** on all three pages. All flat-shape test assertions migrated; full suite green (333 tests on merged main).
- **Remaining future scope:** Cash Flow hierarchical roll-up; dashboard financial summaries.

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
