# Issue #43 Finisher — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) tracking.

**Goal:** Close the small remaining gaps of GitHub issue #43 left open after v2.2.0 (PR #46): customer-perf extras (§2), last-price counterparty info (§6), product-performance export + category grouping (§3), and a posted-edit audit trail (§4).

**Branch:** `feature/issue43-finisher`, stacked on `feature/sales-ux-density-and-posted-edit` (it extends features that only exist there).

**Locked decisions:** audit trail = **header + totals diff**; export = **server XLSX/CSV + Print→PDF via existing print path**.

**Tech:** FastAPI + SQLModel; Next.js 16 / React 19 / TS; pytest. Reuse density classes (`ui-th`/`ui-td`/`ui-field`) and the report_builder export pattern (`routers/report_builder.py:161`, openpyxl + StreamingResponse, formula-injection-safe).

---

### Task 1 — §2 Customer performance: # transactions + avg invoice value

**Files:** `backend/routers/reports.py` (`customer_performance` detail `totals`); `backend/tests/test_customer_performance_detail.py`; `frontend/src/app/(dashboard)/customer-performance/page.tsx`

- [ ] **Step 1 (test):** extend `test_breakdown_has_monthly_volume_and_gp` (or add a test) to assert `detail["totals"]["transaction_count"]` == distinct invoices in period and `detail["totals"]["avg_invoice_value"]` == revenue / transaction_count. Seed 2 invoices (400 + 600) → count 2, avg 500.
- [ ] **Step 2:** run → fail (keys absent). `cd backend && PYTHONPATH=. uv run pytest tests/test_customer_performance_detail.py -v`
- [ ] **Step 3:** in the detail block, count distinct `inv.id` for the customer in the window (`transaction_count = len(cust_invoices)`), and `avg_invoice_value = money(tot_rev / transaction_count)` guarded for zero. Add both to `detail["totals"]`.
- [ ] **Step 4:** run → pass.
- [ ] **Step 5 (frontend):** add two KPI cards ("# Invoices", "Avg Invoice Value") next to the existing Revenue/COGS/GP/GP% cards, using the same card markup.
- [ ] **Step 6:** `cd frontend && npm run lint && npm run build` clean.
- [ ] **Step 7:** commit `feat(reports): add transaction count + avg invoice value to customer performance`.

---

### Task 2 — §6 Last-price hint: last date + counterparty name

**Files:** `backend/routers/products.py` (`product_last_price`); `backend/tests/test_product_last_price.py`; `frontend/src/components/LineItemsTable.tsx`

- [ ] **Step 1 (test):** assert the `/last-price` response also returns `party_name` (the customer name for `kind=sale` / vendor name for `kind=purchase`) for the row that set the price, plus the existing `date`. For the per-customer case it's that customer's name; for global fallback it's whoever the most-recent line belonged to.
- [ ] **Step 2:** run → fail.
- [ ] **Step 3:** extend the `latest()` query to also select the doc's party id; resolve the name (join or follow-up lookup to `Customer`/`Vendor`, tenant-scoped). Return `party_name` in the dict (None when no row).
- [ ] **Step 4:** run → pass; also run the existing 4 last-price tests (incl. tenant isolation) — keep green.
- [ ] **Step 5 (frontend):** in `LineItemsTable`, extend the hint text/tooltip to show `Last: <rate> — <party_name> · <date>` with the one-click "Use". Keep it compact; don't auto-overwrite a typed rate.
- [ ] **Step 6:** lint + build clean.
- [ ] **Step 7:** commit `feat(lines): show last date + customer/supplier in last-price hint`.

---

### Task 3 — §3 Product performance: export + category grouping

**Files:** `backend/routers/reports.py` (export endpoint); `backend/tests/test_product_performance.py`; `frontend/src/app/(dashboard)/inventory/performance/page.tsx`

- [ ] **Step 1 (test):** add `test_product_performance_export_xlsx` and `_csv`: `GET /api/reports/product-performance/export?format=xlsx&start=&end=` returns 200 with `Content-Disposition` attachment and a non-empty body; CSV body contains the product name and the column headers (Opening Qty/Value, Purchased, Sold, GP, Closing Qty/Value). Reuse the seeding from existing product-performance tests.
- [ ] **Step 2:** run → fail (endpoint missing).
- [ ] **Step 3:** add `product_performance_export` reusing the same row computation as `product_performance` (factor the per-product computation into a shared helper to avoid duplication — DRY), then stream CSV/XLSX with the **formula-injection-safe** escaping used in `report_builder.export` (study `routers/report_builder.py:161-187` and reuse its sanitizer; if it's a local helper, lift it into a shared util rather than copy-paste).
- [ ] **Step 4:** run → pass.
- [ ] **Step 5 (category grouping, backend):** add an optional `group_by=category` mode (or a sibling field) so the report can return rows grouped by product category with subtotals — reuse the category-label resolution already in `product-coa`/`customer_performance` (factor a shared `cat_label` helper). Add a small test asserting grouped subtotals reconcile to the flat totals.
- [ ] **Step 6 (frontend):** add **Export CSV / Export XLSX** buttons on the Period-Movement tab of `inventory/performance/page.tsx` (download via the export endpoint), a **Print** button (existing `window.print()` + PrintHeader for PDF), and a **Group by category** toggle that renders subtotal rows. Use `ui-th`/`ui-td`.
- [ ] **Step 7:** lint + build clean; backend `PYTHONPATH=. uv run pytest tests/test_product_performance.py -v` green.
- [ ] **Step 8:** commit(s): `feat(reports): product-performance CSV/XLSX export` and `feat(inventory): category grouping + export/print on product performance`.

---

### Task 4 — §4 Posted-edit audit trail (header + totals diff + Change History)

**Files:** `backend/routers/invoices.py` (`update_invoice`), `backend/routers/bills.py` (`update_bill`); `backend/tests/test_edit_audit_trail.py`; `frontend/src/app/(dashboard)/invoices/[id]/page.tsx`, `bills/[id]/page.tsx`

- [ ] **Step 1 (test):** post an invoice, edit it (change customer + total), then `GET /api/audit?entity_type=invoice&entity_id=<id>` (confirm the audit endpoint's query params by reading `routers/audit.py`) and assert the UPDATE row's `detail` JSON contains a `changes` object with `before`/`after` for the changed header fields and totals (e.g. `total: {before: 200, after: 360}`), plus the acting `user_id` and `timestamp` are present.
- [ ] **Step 2:** run → fail.
- [ ] **Step 3 (backend):** in `update_invoice`, BEFORE mutating `inv`, snapshot the prior header+totals (customer_name, issue_date, due_date, subtotal, gst_amount, total, line_count, currency). After applying changes, compute a `changes` dict of only the fields that differ (`{field: {before, after}}`) and pass it in the `log_audit(..., detail={... "changes": changes})`. Mirror in `update_bill`. Keep it header+totals level (no per-line diff) per the locked decision.
- [ ] **Step 4:** run → pass.
- [ ] **Step 5 (frontend):** on `invoices/[id]/page.tsx` and `bills/[id]/page.tsx`, add a **"Change History"** panel that fetches `/api/audit` for this entity and lists each edit as *"Edited by {user} on {timestamp}"* with the changed fields shown as `field: before → after`. Read-only; collapse if no edits. Use density classes.
- [ ] **Step 6:** lint + build clean.
- [ ] **Step 7:** commit `feat(audit): capture header/totals diff on posted edit + Change History panel`.

---

### Task 5 — Verification + issue cross-link

- [ ] **Step 1:** full backend suite green: `cd backend && PYTHONPATH=. uv run pytest -q`.
- [ ] **Step 2:** `cd frontend && npm run lint && npm run build` clean (no NEW lint errors).
- [ ] **Step 3:** Manual: customer-perf shows # invoices + avg value; last-price hint shows party + date; product-performance exports XLSX/CSV, groups by category, prints; editing a posted invoice/bill records a readable change history.
- [ ] **Step 4:** commit any final tweaks; PR body should say "Closes the §2/§3/§4/§6 remainders of #43" (leaving §1 comparative statements open).

---

## Self-Review Notes
- DRY callouts: factor the per-product computation (Task 3), the formula-injection sanitizer (Task 3), and `cat_label` (Tasks 1/3) into shared helpers rather than duplicating.
- §1 (comparative financial statements) is intentionally OUT of this finisher — it's the larger remaining piece and gets its own effort.
- Execution-time verifications: audit endpoint query-param shape (Task 4), report_builder sanitizer location (Task 3), exact KPI-card markup (Task 1) — confirm by reading the cited code.
