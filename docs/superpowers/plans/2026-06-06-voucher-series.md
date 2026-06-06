# Voucher Series & Transaction Types (#44, Phase 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). Backend tests: `cd backend && PYTHONPATH=. uv run pytest <file> -v` (PYTHONPATH=. REQUIRED). **Accounting/migration correctness matters — if a backfill mapping or sequence-seeding step is genuinely ambiguous after reading the code, STOP and report BLOCKED.**

**Goal:** Typed voucher series (SL/CP/BP/…), auto-assigned per source, backfilled onto existing data (old number preserved), surfaced in Journal/Day-Book/General-Ledger with a voucher-type filter.

**Branch:** `feature/issue44-voucher-series` (based on v2.2.0). **Spec:** `docs/superpowers/specs/2026-06-06-voucher-series-design.md`.

---

### Task 1 — Catalog + numbering + schema + `post_transaction` param

**Files:** `backend/services/vouchers.py` (new), `backend/models.py`, `backend/services/posting.py`, `backend/alembic/versions/<rev>_voucher_series.py` (new), `backend/tests/test_voucher_numbering.py`

- [ ] **Step 1 (test):**
```python
# backend/tests/test_voucher_numbering.py
from sqlmodel import Session, select
import db as _db_module
from models import Transaction

def _post(client, h, vtype=None):
    # Post a balanced manual JV via the transactions API; capture its number.
    body = {"date": "2026-04-01", "description": "t",
            "entries": [{"account_code": "1000", "debit": 10, "credit": 0},
                        {"account_code": "4000", "debit": 0, "credit": 10}]}
    # (confirm the manual-transaction payload by reading routers/transactions.py)
    return client.post("/api/transactions", headers=h, json=body)

def test_manual_post_defaults_to_jv_typed_number(client, admin_headers):
    r = _post(client, admin_headers)
    assert r.status_code in (200, 201), r.text
    num = r.json()["jv_number"]
    assert num.startswith("JV-")          # default type
    assert len(num.split("-")[1]) == 6     # zero-padded width 6
```
> Confirm the manual-transaction endpoint + payload shape and response key by reading `routers/transactions.py` first; adjust the test to match.

- [ ] **Step 2:** run → fail (numbers are `JV-{id:05d}`, width 5).
- [ ] **Step 3 (catalog + helper):** create `backend/services/vouchers.py`:
```python
VOUCHER_TYPES = {
    "JV": "Journal Voucher", "CP": "Cash Payment", "CR": "Cash Receipt",
    "BP": "Bank Payment", "BR": "Bank Receipt", "SL": "Sales Invoice",
    "SR": "Sales Return", "PR": "Purchase Invoice", "PV": "Purchase Return",
    "CO": "Contra", "DN": "Debit Note", "CN": "Credit Note",
}

def voucher_number(session, tenant_id: int, vtype: str) -> str:
    from routers.common import next_number
    if vtype not in VOUCHER_TYPES:
        vtype = "JV"
    return next_number(session, tenant_id, name=f"voucher:{vtype}",
                       prefix=vtype, width=6, fmt="{prefix}-{seq:06d}")

def classify_cash_account(session, tenant_id: int, account_id: int | None) -> str:
    """'bank' if the account is referenced by a BankAccount.coa_account_id for the
    tenant; else 'cash'."""
    if account_id is None:
        return "cash"
    from models import BankAccount
    linked = session.exec(
        select(BankAccount.id).where(BankAccount.tenant_id == tenant_id,
                                     BankAccount.coa_account_id == account_id)
    ).first()  # import select from sqlmodel
    return "bank" if linked else "cash"
```
- [ ] **Step 4 (model):** add to `Transaction` in `models.py`:
```python
    voucher_type: str = Field(default="JV", index=True)
    legacy_jv_number: Optional[str] = None
```
- [ ] **Step 5 (posting):** in `post_transaction` (`posting.py:112`), add param `voucher_type: str = "JV"`, store `txn.voucher_type = voucher_type`, and replace the `jv_number = f"JV-{txn.id:05d}"` line with `txn.jv_number = voucher_number(session, tenant_id, voucher_type)`. (The temp `__TMP__` flush pattern can stay; assign the real number where `JV-{id}` was set. Ensure numbering happens within the same session/transaction.)
- [ ] **Step 6 (migration):** `cd backend && uv run alembic revision -m "voucher series columns"`; hand-write `op.add_column` for `voucher_type` (String, server_default 'JV', not null) and `legacy_jv_number` (String, nullable), each wrapped in the project's existence guard (see migrations 0016/0017 pattern; SQLite-safe — no FK/constraint). Leave backfill to Task 3 (separate migration or a later step in this one — keep this migration columns-only for a clean separation). `uv run alembic upgrade head`.
- [ ] **Step 7:** run tests → pass. `PYTHONPATH=. uv run pytest tests/test_voucher_numbering.py -v`.
- [ ] **Step 8:** full suite sanity (numbering format changed — some tests may assert `JV-` prefixes; the width changed 5→6, and per-type sequences mean numbers differ): `PYTHONPATH=. uv run pytest -q`. Fix any test that asserted the OLD `JV-{id:05d}` exact format to accept the new typed format (those are legitimately updated, not weakened — note each in the commit).
- [ ] **Step 9:** commit `feat(posting): typed voucher numbering + voucher_type/legacy columns`.

---

### Task 2 — Explicit assignment at posting call sites

**Files:** `backend/routers/{invoices,bills,credit_notes,debit_notes,payments,transactions}.py` (+ any contra/transfer site); `backend/tests/test_voucher_assignment.py`

- [ ] **Step 1 (test):** `test_voucher_assignment.py` — post an invoice → its `Transaction.voucher_type == "SL"` and number starts `SL-`; the invoice COGS txn (`Invoice.cogs_transaction_id`) → `"JV"`; a bill → `"PR"`; a credit note → `"CN"`; a debit note → `"DN"`; a payment received into a cash account → `"CR"`; into a bank account (a `BankAccount.coa_account_id`) → `"BR"`; a bill payment cash → `"CP"`, bank → `"BP"`; a reversal of an invoice txn inherits `"SL"`. (Use the existing create/post patterns from the edit-posted tests; fetch the Transaction via `Session`.)
- [ ] **Step 2:** run → fail (everything posts JV).
- [ ] **Step 3:** thread `voucher_type` into each `post_transaction` call:
  - `invoices.py`: sale txn → `"SL"`; COGS txn → `"JV"`; edit-reversal → inherit `old_txn.voucher_type`.
  - `bills.py`: `"PR"`; edit-reversal → inherit.
  - `credit_notes.py` → `"CN"`; `debit_notes.py` → `"DN"`.
  - `payments.py`: receipt → `classify_cash_account(...) == "bank" ? "BR" : "CR"`; payment-made → `"BP"/"CP"`.
  - `transactions.py` reverse endpoint → inherit the reversed txn's `voucher_type`; manual create stays `"JV"` (default).
  - Contra/cash↔bank transfer (read the code — likely in `bank_accounts.py`/`transactions.py`; if a dedicated transfer flow exists) → `"CO"`. If none exists, note it and leave (the JV default covers manual transfers).
  - All other callers (advances/assets/GRN/deferred/production/recurring/imports/reports) keep the `"JV"` default — no change.
- [ ] **Step 4:** run → pass; `PYTHONPATH=. uv run pytest -k "voucher or invoice or bill or payment" -q` green.
- [ ] **Step 5:** commit `feat(vouchers): explicit voucher-type assignment at posting sites`.

---

### Task 3 — Backfill migration (renumber existing, preserve legacy)

**Files:** `backend/alembic/versions/<rev>_voucher_backfill.py` (new), `backend/services/voucher_backfill.py` (the logic, importable + testable), `backend/tests/test_voucher_backfill.py`

- [ ] **Step 1 (test):** seed a tenant with mixed sources (invoice+COGS, bill, payment-received cash, bill-payment bank, credit note) via the API, capture their `transaction_id`s and original `jv_number`s, then call `backfill_vouchers(session, tenant_id)` and assert:
  - each txn's `voucher_type` matches its source (invoice→SL, COGS→JV, bill→PR, payment→CR, bill-payment→BP, credit note→CN);
  - `legacy_jv_number` == the original number; `jv_number` now `TYPE-000001…` in chronological order per type;
  - all `jv_number` unique per tenant;
  - the `SequenceCounter` for each type is seeded so a subsequent `voucher_number(session, tid, "SL")` continues AFTER the highest backfilled SL;
  - **idempotent:** a second `backfill_vouchers` call changes nothing.
- [ ] **Step 2:** run → fail.
- [ ] **Step 3 (logic):** implement `backfill_vouchers(session, tenant_id)` in `services/voucher_backfill.py`:
  1. Build `{txn_id: vtype}` from source back-refs: `Invoice.transaction_id→SL`, `Invoice.cogs_transaction_id→JV`, `Bill.transaction_id→PR`, `PaymentReceived.transaction_id→CR/BR` (via `classify_cash_account` on its `cash_account_id`), `BillPayment→CP/BP`, credit-note→CN, debit-note→DN, contra→CO. Reversal txns (`reversed_by_id` set, or txns whose id is some txn's `reversed_by_id`) inherit the parent's vtype. Unmapped → `JV`.
  2. Skip txns already backfilled (`legacy_jv_number IS NOT NULL`) → idempotency.
  3. Order the to-process txns by `(date, id)`. **Two-pass** to avoid unique-constraint trips: pass A set every processed txn's `jv_number` to a unique temp `f"__MIG__{id}"` and `legacy_jv_number = old number` and `voucher_type = vtype`; flush. Pass B walk in `(date,id)` order grouping by vtype, assign `voucher_number(...)`-style sequential `TYPE-000001` (use a local counter per type, NOT `next_number`, so ordering is deterministic), flush.
  4. After assigning, **seed `SequenceCounter`**: for each type set/raise `next_value` to `max_assigned_seq + 1` (create the row if missing) so post-migration `voucher_number` continues the series.
  All tenant-scoped.
- [ ] **Step 4 (migration):** new Alembic revision (after Task 1's columns migration) whose `upgrade()` iterates tenants and calls `backfill_vouchers`. Alembic's run-once nature + the `legacy_jv_number` guard make it safe.
- [ ] **Step 5:** run → pass. `PYTHONPATH=. uv run pytest tests/test_voucher_backfill.py -v`.
- [ ] **Step 6:** `uv run alembic upgrade head` on a demo-seeded DB runs clean; spot-check a few renumbered txns keep `legacy_jv_number`.
- [ ] **Step 7:** commit `feat(vouchers): backfill + renumber existing transactions (legacy number preserved)`.

---

### Task 4 — Surfacing: type display + filter

**Files:** `backend/routers/transactions.py` (listing returns `voucher_type`/`legacy_jv_number` + `voucher_type` filter param), `backend/tests/test_voucher_listing.py`; `frontend/src/app/(dashboard)/journal/page.tsx`, `frontend/src/app/(dashboard)/ledger/page.tsx` (+ Day Book if separate)

- [ ] **Step 1 (test):** the transactions/journal listing endpoint returns `voucher_type` (+ `legacy_jv_number`) per row, and accepts `?voucher_type=SL` to filter. Seed two types, assert the filter narrows. (Read `routers/transactions.py` for the listing endpoint + its current response/params.)
- [ ] **Step 2:** run → fail.
- [ ] **Step 3 (backend):** add `voucher_type` (+ `legacy_jv_number`) to the listing serialisation and a `voucher_type: Optional[str] = None` filter (tenant-scoped). Add an optional `voucher_number` substring search if cheap.
- [ ] **Step 4:** run → pass.
- [ ] **Step 5 (frontend):** Journal page: show a voucher-type badge next to the number; add a voucher-type filter `<select>` (options from a small TS catalog mirroring `VOUCHER_TYPES`) wired to the listing query; show legacy number in a tooltip/subtle text. General Ledger: the entry number now IS the typed number — show the type badge too (the ledger endpoint already returns `jv_number`; add `voucher_type` to its entry payload in `reports.py get_ledger` and render the badge). Use `ui-th`/`ui-td` + existing badge styling.
- [ ] **Step 6:** `cd frontend && npm run lint && npm run build` clean (no NEW lint errors; pre-existing unrelated ones fine).
- [ ] **Step 7:** commit `feat(vouchers): show voucher type + filter in journal and general ledger`.

---

### Task 5 — Verification

- [ ] **Step 1:** full backend suite green: `cd backend && PYTHONPATH=. uv run pytest -q`. Confirm any tests updated for the new numbering format are legitimately updated (not weakened) — they assert the typed format, not the old `JV-{id}`.
- [ ] **Step 2:** `alembic upgrade head` from a clean DB AND from a demo-seeded DB both run clean; idempotent on re-run.
- [ ] **Step 3:** `cd frontend && npm run lint && npm run build` clean.
- [ ] **Step 4:** Manual: post an invoice (SL-…), a cash receipt (CR-…), a bank payment (BP-…); journal shows types + filter works; an old (pre-migration) voucher shows its new typed number with the legacy number visible.
- [ ] **Step 5:** commit any final tweaks; PR body: "#44 Phase 1 — typed voucher series + backfill + Journal/GL surfacing. Phase 2 (ledgers/cash-book/bank-book/TB drill-down) deferred."

---

## Self-Review Notes
- One chokepoint (`post_transaction`) makes assignment clean; most of the ~18 callers keep the `JV` default untouched.
- The backfill is the risk: two-pass renumber avoids unique-constraint trips; `legacy_jv_number` preserved; idempotent; `SequenceCounter` seeded so new posts continue. Tested explicitly.
- Execution-time verifications flagged inline: manual-transaction payload shape (Task 1), whether a distinct contra/sales-return flow exists (Task 2), the journal listing endpoint shape (Task 4). Confirm by reading the cited code.
- Tests that asserted the old `JV-{id:05d}` format must be updated to the typed format (Task 1 Step 8) — these are correct updates; call them out in commits.
- Out of scope: Phase-2 surfacing (no schema change needed for it).
