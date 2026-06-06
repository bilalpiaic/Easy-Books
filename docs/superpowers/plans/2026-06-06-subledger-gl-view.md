# Consolidated ↔ Sub-Ledger GL View (#45) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) tracking. Backend tests run with `cd backend && PYTHONPATH=. uv run pytest <file> -v` (PYTHONPATH=. REQUIRED).

**Goal:** Add a Consolidated ↔ Sub-Ledger toggle to `/ledger`; in Sub-Ledger mode, AR/AP/Bank control accounts expand to per-customer / per-vendor / per-bank-account summaries that reconcile to the control-account GL balance, each linking to its detailed ledger.

**Branch:** `feature/issue45-subledger` (based on v2.2.0). **Spec:** `docs/superpowers/specs/2026-06-06-subledger-gl-view-design.md`.

**Tech:** FastAPI + SQLModel; Next.js 16 / React 19 / TS; pytest; density classes `ui-th`/`ui-td`.

---

### Task 1 — AR sub-ledger summary + shared per-party helper

**Files:** `backend/routers/subledger.py` (factor helper), `backend/routers/reports.py` (new endpoint), `backend/tests/test_subledger_view.py`

- [ ] **Step 1 (test):**
```python
# backend/tests/test_subledger_view.py
def _post_inv(client, h, cid, pid, rate, qty, date):
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": cid, "issue_date": date, "gst_rate": 0,
        "lines": [{"product_id": pid, "description": "x", "qty": qty, "rate": rate}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    return inv

def test_ar_subledger_reconciles(client, admin_headers):
    h = admin_headers
    a = client.post("/api/customers", headers=h, json={"name": "Alpha"}).json()
    b = client.post("/api/customers", headers=h, json={"name": "Beta"}).json()
    p = client.post("/api/products", headers=h, json={"name": "W", "product_type": "service"}).json()
    _post_inv(client, h, a["id"], p["id"], 100, 2, "2026-02-01")   # Alpha AR 200
    _post_inv(client, h, b["id"], p["id"], 50, 3, "2026-02-05")    # Beta AR 150
    data = client.get("/api/reports/ledger/subledger?control=ar&start=2026-01-01&end=2026-02-28", headers=h).json()
    by = {r["name"]: r for r in data["items"]}
    assert by["Alpha"]["closing"] == 200 and by["Alpha"]["debit"] == 200
    assert by["Beta"]["closing"] == 150
    assert data["sub_total"] == 350
    assert data["reconciles"] is True          # Σ sub == control 1100 GL balance
    assert by["Alpha"]["link"] == "/customers/%d/ledger" % a["id"]
```
- [ ] **Step 2:** run → fail (endpoint missing). `PYTHONPATH=. uv run pytest tests/test_subledger_view.py -v`
- [ ] **Step 3 (helper):** In `subledger.py`, factor the per-customer opening + period Dr/Cr computation currently inside `customer_ledger` into a reusable function, e.g.:
```python
def ar_party_movement(session, tenant_id, customer, start, end) -> dict:
    """Return {opening, debit, credit, closing} for one customer's AR over the
    window — opening = AR before `start`, debit = invoices in window, credit =
    payments-received applied in window. Pure; no HTTP."""
```
Refactor `customer_ledger` to use it for its opening/summary so logic isn't duplicated (keep its event list as-is). Confirm `customer_ledger`'s existing tests still pass.
- [ ] **Step 4 (endpoint):** In `reports.py` add `ledger_subledger(control, start, end)`. For `control=="ar"`: resolve the control account from the `default_ar_account` setting (fallback code "1100"); for every customer with any AR activity, call `ar_party_movement`; build items (with `link=f"/customers/{id}/ledger"`); compute `control_balance` = GL closing of the AR account (reuse the signed opening+movement logic from `get_ledger`, or query JournalEntry for that account), `sub_total = Σ closing`, `reconciles = abs(sub_total - control_balance) < 0.01`.
- [ ] **Step 5:** run → pass. Also run `PYTHONPATH=. uv run pytest -k "subledger or customer_ledger" -v` (existing customer-ledger tests green).
- [ ] **Step 6:** commit `feat(reports): AR sub-ledger summary endpoint + shared party-movement helper`.

---

### Task 2 — AP sub-ledger summary

**Files:** `backend/routers/subledger.py`, `backend/routers/reports.py`, `backend/tests/test_subledger_view.py`

- [ ] **Step 1 (test):** `test_ap_subledger_reconciles` — 2 vendors with posted bills; assert per-vendor closing, `sub_total`, `reconciles` against the AP control (`default_ap_account`, "2000"), and `link == /vendors/{id}/ledger`. (Create/post bills via the API the way `tests/test_edit_posted_bill.py` does; set status received.)
- [ ] **Step 2:** run → fail.
- [ ] **Step 3:** factor `ap_party_movement(session, tenant_id, vendor, start, end)` out of `vendor_ledger` (mirror of AR: opening = AP before start, debit = payments-made, credit = bills — sign per AP being a liability; match `vendor_ledger`'s existing sign convention). Add `control=="ap"` branch to `ledger_subledger` using it; control account from `default_ap_account` (fallback "2000").
- [ ] **Step 4:** run → pass; `PYTHONPATH=. uv run pytest -k "subledger or vendor_ledger" -v` green.
- [ ] **Step 5:** commit `feat(reports): AP sub-ledger summary (per-vendor)`.

---

### Task 3 — Bank sub-ledger summary (GL accounts) + reconciliation

**Files:** `backend/routers/reports.py`, `backend/tests/test_subledger_view.py`

- [ ] **Step 1 (test):** `test_bank_subledger` — record two payments-received into two different cash/bank accounts (e.g. 1000 Cash, 1010 Bank), then `GET /ledger/subledger?control=bank&start=&end=`; assert each bank GL account appears with opening/Dr/Cr/closing matching its GL balance, `sub_total == Σ`, `reconciles True`, `link == /ledger?account_id={id}`.
- [ ] **Step 2:** run → fail.
- [ ] **Step 3:** add `control=="bank"` branch. Identify cash/bank GL accounts as the tenant's Asset accounts whose `code` starts with `"10"` (this matches the existing Cash & Bank logic at `reports.py:214` — read it and stay consistent), UNION any `BankAccount.coa_account_id` for the tenant. For each, compute opening/Dr/Cr/closing straight from `JournalEntry` (reuse the signed-balance computation used by `get_ledger`; factor a small `account_gl_movement(session, tenant_id, account, start, end)` helper if it reduces duplication). `control_balance` = Σ of those accounts' closing (the "Cash & Bank" group), so `reconciles` is trivially true here but keep the field for UI uniformity.
- [ ] **Step 4:** run → pass.
- [ ] **Step 5:** commit `feat(reports): Bank/Cash sub-ledger summary (per GL account)`.

---

### Task 4 — Frontend: Consolidated/Sub-Ledger toggle + expandable rows

**Files:** `frontend/src/app/(dashboard)/ledger/page.tsx`

- [ ] **Step 1:** Read the current ledger page and `frontend/AGENTS.md`. Note how account rows render today (consolidated mode = unchanged).
- [ ] **Step 2:** Add a `Consolidated | Sub-Ledger` toggle (mirror the Products List/Tree toggle markup). State `view: 'consolidated' | 'subledger'`.
- [ ] **Step 3:** Map which displayed accounts are control accounts: AR (code 1100 / matches the AR account), AP (2000), and Bank (codes starting `10`). In Sub-Ledger view, give those rows an expand chevron.
- [ ] **Step 4:** On expand, lazy-`apiFetch('/api/reports/ledger/subledger?control=…&start=&end=')`, render sub-entity rows (Name, Opening, Debit, Credit, Closing) with `ui-td`/`ui-th`, indented under the control row. Show a small badge: `reconciles ✓` or `⚠ off by {fmt(diff)}`. Each name links to its `link`. Cache per control so re-expanding doesn't refetch.
- [ ] **Step 5:** `cd frontend && npm run lint && npm run build` clean (no NEW lint errors; pre-existing unrelated ones are fine).
- [ ] **Step 6:** Manual: toggle switches modes; expanding AR/AP/Bank shows reconciling sub-entities; links open the detailed ledgers.
- [ ] **Step 7:** commit `feat(ledger): consolidated/sub-ledger view toggle with expandable control accounts`.

---

### Task 5 — Verification + edge cases

- [ ] **Step 1:** Add `test_subledger_tenant_isolation` (a foreign-tenant customer/account never leaks) and `test_subledger_empty_control` (control account with no sub-entities → `items: []`, `reconciles True`).
- [ ] **Step 2:** Add `test_ar_opening_balance_caveat`: a customer with a non-journalised `opening_balance` → assert the DOCUMENTED behaviour (e.g. `reconciles` reflects the opening delta) rather than a false invariant. Decide & document the policy in code comments.
- [ ] **Step 3:** Full suite green: `cd backend && PYTHONPATH=. uv run pytest -q`. Frontend `npm run lint && npm run build` clean.
- [ ] **Step 4:** commit any final tweaks; PR body: "Implements #45 (Consolidated vs Sub-Ledger GL view) — AR/AP/Bank; Stock deferred."

---

## Self-Review Notes
- DRY: `ar_party_movement`/`ap_party_movement` shared between the single-party ledgers and the summary; `account_gl_movement` shared with `get_ledger` where it reduces duplication.
- Reconciliation is the core correctness guarantee — tested for document-driven activity; the opening-balance caveat is handled explicitly (Task 5 Step 2), not asserted as a false invariant.
- Execution-time verifications: exact sign convention in `vendor_ledger` (Task 2), the `reports.py:214` cash/bank identification (Task 3), and the current ledger-row markup (Task 4) — confirm by reading the cited code.
- Out of scope: `control=stock` (structure leaves room to add it later).
