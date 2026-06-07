# Voucher Surfacing Phase 2 (#44 Phase 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). Backend tests: `cd backend && PYTHONPATH=. uv run pytest <file> -v` (PYTHONPATH=. REQUIRED).

**Goal:** Surface voucher types across the remaining ledgers — badge+filter on customer/vendor sub-ledgers, and new Cash Book / Bank Book pages built on the existing voucher-aware GL-ledger engine.

**Branch:** `feature/issue44-phase2-voucher-surfacing` (off main / v2.3.0). **Spec:** `docs/superpowers/specs/2026-06-06-voucher-surfacing-phase2-design.md`.

---

### Task 1 — Backend: voucher_type on customer/vendor ledger rows

**Files:** `backend/routers/subledger.py`, `backend/tests/test_subledger_voucher.py`

- [ ] **Step 1 (test):**
```python
# backend/tests/test_subledger_voucher.py
from sqlmodel import Session
import db as _db_module

def test_customer_ledger_rows_have_voucher_type(client, admin_headers):
    h = admin_headers
    c = client.post("/api/customers", headers=h, json={"name": "Acme"}).json()
    p = client.post("/api/products", headers=h, json={"name": "W", "product_type": "service"}).json()
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": c["id"], "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "x", "qty": 1, "rate": 100}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    data = client.get(f"/api/customers/{c['id']}/ledger?start=2026-01-01&end=2026-12-31", headers=h).json()
    inv_rows = [r for r in data["entries"] if r.get("doc_type") == "invoice"]
    assert inv_rows and inv_rows[0]["voucher_type"] == "SL"

def test_vendor_ledger_rows_have_voucher_type(client, admin_headers):
    h = admin_headers
    v = client.post("/api/vendors", headers=h, json={"name": "Sup"}).json()
    p = client.post("/api/products", headers=h, json={"name": "N", "product_type": "service"}).json()
    bill = client.post("/api/bills", headers=h, json={
        "vendor_id": v["id"], "bill_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "y", "qty": 1, "rate": 50}],
    }).json()
    client.patch(f"/api/bills/{bill['id']}/status?status=received", headers=h)
    data = client.get(f"/api/vendors/{v['id']}/ledger?start=2026-01-01&end=2026-12-31", headers=h).json()
    bill_rows = [r for r in data["entries"] if r.get("doc_type") == "bill"]
    assert bill_rows and bill_rows[0]["voucher_type"] == "PR"
```
(Confirm the ledger response key for rows — `entries` vs `rows` — by reading `subledger.py`; adjust the test.)
- [ ] **Step 2:** run → fail (`voucher_type` absent). `PYTHONPATH=. uv run pytest tests/test_subledger_voucher.py -v`
- [ ] **Step 3:** In `subledger.py`, for both `customer_ledger` and `vendor_ledger`: collect the `transaction_id`s of the rows' source documents (invoice/payment/bill/bill-payment each expose `transaction_id`), batch-load `{transaction_id: voucher_type}` from `Transaction` in ONE tenant-scoped query, and attach `row["voucher_type"]` to each emitted row (None when the doc has no transaction). Factor a shared helper `def _voucher_types_for(session, tenant_id, txn_ids) -> dict` used by both. Do NOT change existing row fields/order.
- [ ] **Step 4:** run → pass; regression `PYTHONPATH=. uv run pytest -k "subledger or ledger or customer or vendor" -q`.
- [ ] **Step 5:** commit `feat(subledger): expose voucher_type on customer/vendor ledger rows`.

---

### Task 2 — Frontend: customer/vendor ledger badge + filter

**Files:** `frontend/src/app/(dashboard)/customers/[id]/ledger/page.tsx`, `frontend/src/app/(dashboard)/vendors/[id]/ledger/page.tsx`

- [ ] **Step 1:** Read both pages + `frontend/src/lib/voucherTypes.ts` (catalog + `voucherTypeBadgeClass`). Heed `frontend/AGENTS.md`.
- [ ] **Step 2:** Extend each page's row TS interface with `voucher_type?: string | null`. Render a voucher-type badge next to the existing doc link/number per row (same badge markup as the Journal page: `voucherTypeBadgeClass(vt)` + `VOUCHER_TYPES[vt]` title), `ui-td` cell.
- [ ] **Step 3:** Add a voucher-type `<select>` filter above the table (options from `VOUCHER_TYPES`); filter the loaded rows **client-side** by `voucher_type`. "All" shows everything. Keep the running-balance column correct: filtering is a view concern — either (a) filter only the displayed rows leaving balances as-is with a note, or (b) simplest: when a filter is active, show the matching rows without recomputing running balance (document this). Prefer (a): keep the full ledger's running balance values on each row; the filter just hides non-matching rows.
- [ ] **Step 4:** `cd frontend && npm run lint && npm run build` clean (no NEW lint errors in the two pages; pre-existing unrelated errors fine).
- [ ] **Step 5:** commit `feat(ledger-ui): voucher badge + filter on customer/vendor ledgers`.

---

### Task 3 — Cash Book page

**Files:** `frontend/src/app/(dashboard)/cash-book/page.tsx` (new), `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1:** Read the existing `/ledger` page to reuse its entry-rendering shape (date / jv_number / voucher badge / description / debit / credit / running balance) and the `/api/reports/ledger` response (`{ code, name, opening_balance, entries:[{date, jv_number, voucher_type, transaction_id, description, debit, credit, balance}], closing_balance }`). Read `/api/accounts` + `/api/bank-accounts` response shapes.
- [ ] **Step 2:** Build `cash-book/page.tsx`: on load, fetch `/api/accounts?limit=500` and `/api/bank-accounts`; compute **cash accounts** = Asset accounts with `code` starting `"10"` whose `id` is NOT among the bank-accounts' `coa_account_id`. If one → use it; if several → an account `<select>`. Date range (default current FY/month like other reports). Fetch `/api/reports/ledger?account_code={code}&start=&end=` (or `account_id`) and render the entries table with voucher badges + running balance, a voucher-type client-side filter, and an Opening/Closing balance header. Use `ui-th`/`ui-td`; reuse the ledger page's visual style; include `PrintHeader` + Print.
- [ ] **Step 3:** Add a **Cash Book** entry to `Sidebar.tsx` under the `Banking` section (lucide icon, e.g. `Wallet` or `BookOpen`).
- [ ] **Step 4:** `cd frontend && npm run lint && npm run build` clean.
- [ ] **Step 5:** Manual: Cash Book shows the cash account's ledger with voucher badges + running balance; voucher filter narrows; print is clean.
- [ ] **Step 6:** commit `feat(banking): Cash Book — voucher-aware cash-account ledger view`.

---

### Task 4 — Bank Book page

**Files:** `frontend/src/app/(dashboard)/bank-book/page.tsx` (new), `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1:** Build `bank-book/page.tsx`: fetch `/api/bank-accounts`; a bank `<select>` defaulting to the **first**; on selection, fetch `/api/reports/ledger?account_id={bank.coa_account_id}&start=&end=` and render the same entries table (voucher badges + running balance + voucher-type client-side filter + date range + Opening/Closing header) as Cash Book — factor a shared `LedgerEntriesTable` component used by both Cash Book and Bank Book to avoid duplicating the render (DRY). Handle the empty case (bank account with no `coa_account_id` / no banks → friendly message).
- [ ] **Step 2:** Add a **Bank Book** entry to `Sidebar.tsx` under `Banking`.
- [ ] **Step 3:** `cd frontend && npm run lint && npm run build` clean.
- [ ] **Step 4:** Manual: Bank Book defaults to first bank, selector switches accounts, entries show voucher badges + running balance; filter works.
- [ ] **Step 5:** commit `feat(banking): Bank Book — voucher-aware bank-account ledger view with selector`.

---

### Task 5 — Verify TB drill-down + final checks

- [ ] **Step 1:** Verify `/trial-balance` → `/ledger?account=CODE` shows voucher badges (Phase 1). If a gap exists, note it; otherwise no change.
- [ ] **Step 2:** Full backend suite: `cd backend && PYTHONPATH=. uv run pytest -q`. Frontend `npm run lint && npm run build` clean.
- [ ] **Step 3:** Manual sweep: customer ledger, vendor ledger, Cash Book, Bank Book all show voucher badges + filters; TB drill shows badges.
- [ ] **Step 4:** commit any final tweaks; PR body: "#44 Phase 2 — voucher surfacing on customer/vendor ledgers + new Cash Book/Bank Book views. Completes #44."

---

## Self-Review Notes
- DRY: a shared `_voucher_types_for` batch resolver in `subledger.py` (Task 1); a shared `LedgerEntriesTable` component for Cash Book + Bank Book (Task 4).
- No new backend endpoint for cash/bank book — reuse `/api/reports/ledger` (already voucher-aware + running balance).
- Client-side voucher filtering on the focused per-entity views (bounded row sets) avoids endpoint churn; running-balance values stay as computed by the ledger (filter hides rows, doesn't recompute) — documented in Task 2 Step 3.
- Execution-time verifications: subledger row key (`entries` vs `rows`), `/ledger` + `/api/accounts` + `/api/bank-accounts` response shapes — confirm by reading before coding.
