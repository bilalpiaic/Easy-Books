# Demo-Seed Upgrades — Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the demo seeder (`scripts/seed_demo.py`) so a freshly seeded tenant exercises the v2.5.0 feature set: deferred-revenue origination, voucher types across documents, multi-period (2 fiscal years) data, and multiple users with varied audit attribution.

**Architecture:** Surgically extend the existing 2188-line `seed_demo.py` (do not rewrite). Each upgrade is driven by a **per-segment smoke test** that seeds a tenant into the in-memory test DB (the conftest `client` fixture monkeypatches `seed_demo.engine`) and asserts the invariant — failing on the current seed, passing after the change. Reuse shipped services (`services.deferred`) rather than re-implementing.

**Tech Stack:** FastAPI, SQLModel, pytest. `post_transaction(s, user, *, date, description, entries, audit_entity_type, audit_detail, voucher_type="JV")` is the GL writer; `services.deferred.{resolve_deferred_account, create_schedules}` originate deferral; `services.account_tree` exists.

**Spec:** `docs/superpowers/specs/2026-06-08-seed-regen-hierarchical-coa-design.md` §3–§6, §8 (Phase A §1–§2 already shipped — `main` has the hierarchical CoA).

**Base:** `main` @ `5cbebae` (hierarchical CoA merged). Branch: `feature/seed-regen-phaseB-demo`.

**Run tests from `backend/` with `PYTHONPATH=.`.** Seed smoke tests call `seed_demo.seed_one_tenant(email, company, model)`; the conftest `client` fixture must be a test arg so the in-memory engine is patched in.

---

## Test harness (shared by all tasks)

Create `backend/tests/test_seed_demo_phaseB.py` with this header + helper (Task 1 creates it; later tasks append):

```python
"""Phase B: the demo seeder exercises current features (deferred / vouchers /
multi-period / multi-user). Each test seeds a tenant into the in-memory test DB
(the `client` fixture patches seed_demo.engine) and asserts an invariant."""
from datetime import date

from sqlmodel import Session, select

import db as _db_module
from models import Account, AuditLog, DeferredRevenueSchedule, JournalEntry, Transaction, User
from scripts.seed_demo import seed_one_tenant


def _seed(client, model, email=None):
    """Seed one demo tenant of `model` into the test DB; return its tenant_id.
    `client` patches seed_demo.engine to the in-memory test engine."""
    email = email or f"demo.{model}@seedtest.app"
    rep = seed_one_tenant(email, f"{model.title()} Co", model)
    return rep["tenant_id"]


def _txns(tid):
    with Session(_db_module.engine) as s:
        return s.exec(select(Transaction).where(Transaction.tenant_id == tid)).all()
```

NOTE: `seed_one_tenant` opens its own `Session(engine)`; because the conftest patches `scripts.seed_demo.engine` to the test engine, that works inside a `client`-fixture test. Verify in Task 1 Step 2 that seeding runs at all under the fixture before adding feature assertions.

---

### Task 1: Multi-period (2 fiscal years) date spread

**Files:**
- Modify: `backend/scripts/seed_demo.py` (`_spread_dates`, ~line 224)
- Test: `backend/tests/test_seed_demo_phaseB.py` (new)

The current `_spread_dates(count, days_ago=365)` keeps everything inside the last 12 months. Widen the default window so data spans the prior fiscal year and the current year-to-date.

- [ ] **Step 1: Write the failing test** (create the file with the header above, then append)

```python
def test_seeded_data_spans_two_fiscal_years(client):
    tid = _seed(client, "services")
    years = {t.date[:4] for t in _txns(tid)}        # ISO date 'YYYY-...'
    assert len(years) >= 2, f"expected ≥2 distinct years, got {sorted(years)}"
```

- [ ] **Step 2: Run — verify the seed runs and the test FAILS**

Run: `PYTHONPATH=. uv run pytest tests/test_seed_demo_phaseB.py::test_seeded_data_spans_two_fiscal_years -v`
Expected: FAIL with `expected ≥2 distinct years` (current 365-day window from a mid-year run date often lands in a single year). If instead it ERRORS (seed didn't run under the fixture), STOP and report — the harness assumption is wrong.

- [ ] **Step 3: Widen the date window**

In `backend/scripts/seed_demo.py`, change `_spread_dates`'s default `days_ago` from `365` to `640` (≈ 21 months → guarantees the window straddles a year boundary regardless of run date), keeping the jitter logic:

```python
def _spread_dates(count: int, days_ago: int = 640, min_days_ago: int = 3) -> list[str]:
    """Return `count` ascending ISO date strings spread across the past
    `days_ago` days (~21 months → spans prior + current fiscal year) with ±3
    day jitter so dates are not mechanically even."""
    today = date.today()
    dates: list[str] = []
    for i in range(count):
        frac = i / max(count - 1, 1)
        base_days = int(days_ago - frac * (days_ago - min_days_ago))
        jitter = random.randint(-3, 3)
        days_back = max(min_days_ago, base_days + jitter)
        dates.append((today - timedelta(days=days_back)).isoformat())
    return sorted(dates)
```

Callers that pass an explicit `days_ago=365` (invoices/bills, ~lines 608/717) — update those two call sites to `days_ago=640` as well so invoices/bills span both years (leave the smaller windows for GRNs/POs/returns/advances as-is; those are recent-activity by nature).

- [ ] **Step 4: Run — verify PASS**

Run: `PYTHONPATH=. uv run pytest tests/test_seed_demo_phaseB.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_demo.py backend/tests/test_seed_demo_phaseB.py
git commit -m "feat(seed): spread demo data across two fiscal years (#53 seeding Phase B)"
```

---

### Task 2: Voucher types on primary documents

**Files:**
- Modify: `backend/scripts/seed_demo.py` (the primary-document `post_transaction` calls)
- Test: `backend/tests/test_seed_demo_phaseB.py` (append)

Every seed `post_transaction` currently omits `voucher_type`, so all transactions default to `"JV"`. Thread the correct type at the **primary document** post sites (leave internal/cost-relief postings as JV).

Mapping (find each by its `description=` string and add `voucher_type=`):
- `_seed_invoices` invoice JV (`description=f"Invoice {number} — ..."`, ~line 810) → `voucher_type="SL"`
- `_seed_bills` bill JV (`description` referencing the bill, ~line 691) → `voucher_type="PU"`
- `_seed_payments_received` (~line 881) → `voucher_type="CR"`
- `_seed_bill_payments` (~line 933) → `voucher_type="CP"`
- `_seed_credit_notes` (~line 1550) → `voucher_type="CN"`
- `_seed_purchase_returns` debit-note posting (~line 1881) → `voucher_type="DN"`
- `_seed_manual_jvs` (~line 1110) → leave/ set `voucher_type="JV"` (explicit)

(COGS relief, advances, manufacturing, telecom, PO postings stay default `"JV"` — they are internal/cost entries, not party documents.)

- [ ] **Step 1: Write the failing test**

```python
def test_seeded_transactions_carry_document_voucher_types(client):
    tid = _seed(client, "trader")
    with Session(_db_module.engine) as s:
        vtypes = {t.voucher_type for t in s.exec(
            select(Transaction).where(Transaction.tenant_id == tid)).all()}
    # The primary documents must be present and typed (not all JV)
    assert {"SL", "PU", "CR", "CP"}.issubset(vtypes), f"got {sorted(vtypes)}"
```

- [ ] **Step 2: Run — verify FAIL**

Run: `PYTHONPATH=. uv run pytest tests/test_seed_demo_phaseB.py::test_seeded_transactions_carry_document_voucher_types -v`
Expected: FAIL — only `{"JV"}` present.

- [ ] **Step 3: Add `voucher_type=` at each primary post site**

For each site above, add the `voucher_type="XX"` keyword argument to the `post_transaction(...)` call (alongside the existing `audit_entity_type=`/`audit_detail=`). Example for the invoice site (~line 810):

```python
            txn = post_transaction(
                s, user, date=issue_date,
                description=f"Invoice {number} — {customer.name}",
                entries=entries,
                audit_entity_type="invoice",
                audit_detail={"number": number, "total": str(total)},
                voucher_type="SL",
            )
```

Apply the analogous one-line addition at the bill (`"PU"`), payment-received (`"CR"`), bill-payment (`"CP"`), credit-note (`"CN"`), and purchase-return/debit-note (`"DN"`) sites. Do not change entries or amounts.

- [ ] **Step 4: Run — verify PASS** (and the multi-period test still passes)

Run: `PYTHONPATH=. uv run pytest tests/test_seed_demo_phaseB.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_demo.py backend/tests/test_seed_demo_phaseB.py
git commit -m "feat(seed): tag primary documents with voucher types (SL/PU/CR/CP/CN/DN) (#53 seeding Phase B)"
```

---

### Task 3: Deferred-revenue origination (real #47 path)

**Files:**
- Modify: `backend/scripts/seed_demo.py` (`_seed_products` to flag a deferred product; `_seed_invoices` to split to 2300 + originate schedules; replace `_seed_deferred_revenue` usage)
- Test: `backend/tests/test_seed_demo_phaseB.py` (append)

Replace the inert direct-schedule seed with the shipped origination: a deferred product's invoice line credits Deferred Revenue (2300) and originates a real `DeferredRevenueSchedule` via `services.deferred.create_schedules`; then recognise a couple of periods.

- [ ] **Step 1: Write the failing test**

```python
def test_seeded_deferred_revenue_is_originated_and_partially_recognised(client):
    tid = _seed(client, "services")
    with Session(_db_module.engine) as s:
        scheds = s.exec(select(DeferredRevenueSchedule).where(
            DeferredRevenueSchedule.tenant_id == tid)).all()
        acc2300 = s.exec(select(Account).where(
            Account.tenant_id == tid, Account.code == "2300")).first()
        credits_2300 = 0.0
        if acc2300:
            from services.money import D
            rows = s.exec(select(JournalEntry).where(
                JournalEntry.account_id == acc2300.id)).all()
            credits_2300 = float(sum(D(r.credit) for r in rows))
    assert scheds, "no deferred schedules originated"
    assert any(float(x.recognised_amount) > 0 for x in scheds), "no partial recognition"
    assert credits_2300 > 0, "no Deferred Revenue (2300) credit posted by origination"
```

- [ ] **Step 2: Run — verify FAIL**

Run: `PYTHONPATH=. uv run pytest tests/test_seed_demo_phaseB.py::test_seeded_deferred_revenue_is_originated_and_partially_recognised -v`
Expected: FAIL — current `_seed_deferred_revenue` builds schedules directly with no 2300 posting and `recognised_amount=ZERO` (no recognition).

- [ ] **Step 3: Flag a deferred product** in `_seed_products` (services model)

In `backend/scripts/seed_demo.py` `_seed_products` (~line 425), for the `services` model mark one seeded service product `is_deferred=True` with `recognition_months=12`. Locate where service products are created (`Product(... product_type="service" ...)`) and set the two fields on one of them, e.g.:

```python
        # One subscription-style service product demonstrates deferred revenue.
        if business_model in ("services", "simple") and svc_products:
            svc_products[0].is_deferred = True
            svc_products[0].recognition_months = 12
```

(Use the actual local variable name the function builds the service-product list into — read the function; it returns `(services, stock, custom_supp)`.)

- [ ] **Step 4: Originate schedules in `_seed_invoices`**

In `_seed_invoices`, where a line's product drives the revenue posting, when `product.is_deferred` is True: credit the Deferred Revenue account (via `from services.deferred import resolve_deferred_account`) instead of `rev_acc` for that line's net, and after the invoice txn is posted, call `from services.deferred import create_schedules` to originate the schedule. Mirror the production `create_invoice` split (Phase A spec / #47). Minimal approach that satisfies the test and keeps the JV balanced: build a per-invoice `deferred_net`; if > 0, post the deferred portion to 2300 and the rest to revenue, then:

```python
            from services.deferred import resolve_deferred_account, create_schedules, DeferralPlan, LineDeferral
            # after txn posted and invoice.id is set:
            if deferred_net > 0:
                plan = DeferralPlan(
                    deferred_lines=[LineDeferral(net_base=money(deferred_net),
                                                 recognition_months=12,
                                                 revenue_account_id=rev_acc.id)],
                    deferred_net_base=money(deferred_net),
                )
                create_schedules(s, user, invoice, plan)
```

(The exact integration follows `create_invoice`'s pattern from `routers/invoices.py`; keep the invoice JV balanced — total debit to AR == revenue credit + deferred credit + GST.)

- [ ] **Step 5: Recognise a couple of periods**

After invoices are seeded (in `seed_one_tenant`, replacing the `if business_model == "services": _seed_deferred_revenue(...)` block ~line 2122), call the recognition logic for 1–2 elapsed month-ends so some schedules show `recognised_amount > 0`. Reuse the recognition engine: import and call the same logic `routers/deferred_revenue.run_recognition` uses, or post the Dr 2300 / Cr revenue entry directly for one period per schedule and bump `recognised_amount`. Keep it simple and balanced.

Remove the now-obsolete inert `_seed_deferred_revenue` direct-insert (or repurpose it as the recognition driver). Update `seed_one_tenant` accordingly.

- [ ] **Step 6: Run — verify PASS** (full Phase B file)

Run: `PYTHONPATH=. uv run pytest tests/test_seed_demo_phaseB.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/seed_demo.py backend/tests/test_seed_demo_phaseB.py
git commit -m "feat(seed): originate deferred revenue via #47 path + partial recognition (#53 seeding Phase B)"
```

---

### Task 4: Multiple users + audit attribution

**Files:**
- Modify: `backend/scripts/seed_demo.py` (`seed_one_tenant` — create 2–3 users, rotate the actor passed to seeders)
- Test: `backend/tests/test_seed_demo_phaseB.py` (append)

`_get_or_make_user` makes one demo user. Create an owner + accountant + clerk and attribute different seeding phases to different users so the Audit Log shows multiple actors.

- [ ] **Step 1: Write the failing test**

```python
def test_seeded_tenant_has_multiple_users_with_varied_audit(client):
    tid = _seed(client, "services")
    with Session(_db_module.engine) as s:
        users = s.exec(select(User).where(User.tenant_id == tid)).all()
        actor_ids = {a.user_id for a in s.exec(
            select(AuditLog).where(AuditLog.tenant_id == tid)).all()}
    assert len(users) >= 2, f"expected ≥2 users, got {len(users)}"
    assert len(actor_ids) >= 2, f"audit attributed to {len(actor_ids)} user(s)"
```

(Confirm `AuditLog` has a `tenant_id` column; if it does not, filter audit rows by `user_id in {u.id for u in users}` instead.)

- [ ] **Step 2: Run — verify FAIL**

Run: `PYTHONPATH=. uv run pytest tests/test_seed_demo_phaseB.py::test_seeded_tenant_has_multiple_users_with_varied_audit -v`
Expected: FAIL — one user, audit attributed to a single actor.

- [ ] **Step 3: Create extra users + rotate actors in `seed_one_tenant`**

After the existing `_get_or_make_user(s, email, "Demo User", tenant_id)` (~line 2079), create two more users (distinct emails derived from the tenant email, same demo password via `_get_or_make_user`):

```python
        # Multiple actors so the Audit Log shows realistic attribution.
        base, domain = email.split("@", 1)
        accountant = _get_or_make_user(s, f"{base}+accountant@{domain}", "Demo Accountant", tenant_id)
        clerk = _get_or_make_user(s, f"{base}+clerk@{domain}", "Demo Clerk", tenant_id)
        s.commit()
        owner = s.exec(select(User).where(User.email == email)).first()
```

Then attribute seeding phases to different actors: pass `owner` to invoices/JVs, `accountant` to bills/payments, `clerk` to credit notes/returns. Concretely, change the relevant `_seed_*(s, user, ...)` calls in `seed_one_tenant` to pass `accountant`/`clerk` instead of `user` — e.g. `_seed_bills(s, accountant, ...)`, `_seed_bill_payments(s, accountant, ...)`, `_seed_credit_notes(s, clerk, ...)`, `_seed_sales_returns(s, clerk, ...)`. Leave invoices/manual-JVs on `owner` (= `user`).

- [ ] **Step 4: Run — verify PASS**

Run: `PYTHONPATH=. uv run pytest tests/test_seed_demo_phaseB.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_demo.py backend/tests/test_seed_demo_phaseB.py
git commit -m "feat(seed): multiple users + varied audit attribution per tenant (#53 seeding Phase B)"
```

---

### Task 5: Per-segment regeneration smoke test + full suite

**Files:**
- Test: `backend/tests/test_seed_demo_phaseB.py` (append)

Prove all 5 segments seed cleanly and the books balance (the §7/§8 reconciliation gate).

- [ ] **Step 1: Write the test**

```python
import pytest


@pytest.mark.parametrize("model", ["simple", "services", "trader", "manufacturing", "telecom_franchise"])
def test_every_segment_seeds_and_trial_balance_balances(client, model):
    tid = _seed(client, model)
    from services.money import D
    with Session(_db_module.engine) as s:
        rows = s.exec(select(JournalEntry).join(Transaction).where(
            Transaction.tenant_id == tid)).all()
        dr = sum(D(r.debit) for r in rows)
        cr = sum(D(r.credit) for r in rows)
    assert dr == cr, f"{model}: trial balance off by {dr - cr}"
    assert len(_txns(tid)) > 0, f"{model}: no transactions seeded"
```

- [ ] **Step 2: Run**

Run: `PYTHONPATH=. uv run pytest tests/test_seed_demo_phaseB.py -v`
Expected: PASS (all 5 segments balance). If a segment errors during seeding (e.g. a deferred/voucher/user change broke a model-specific path), fix the seed code for that path — do not weaken the test.

- [ ] **Step 3: Full backend suite**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: all pass (existing + new Phase B tests). Fix any seed regression surfaced.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_seed_demo_phaseB.py
git commit -m "test(seed): per-segment regeneration balances + full suite green (#53 seeding Phase B)"
```

---

## Self-Review notes

- **Spec coverage:** §3 deferred origination → Task 3; §4 voucher types → Task 2; §5 multi-period → Task 1; §6 multi-user → Task 4; §7 regeneration / §8 testing → Task 5 (+ each task's smoke test).
- **Sequencing:** Task 1 (date window) is foundational and lowest-risk; Task 3 (deferred) is the most involved (touches `_seed_products` + `_seed_invoices` + recognition); Task 5 is the all-segment safety net that catches any model-specific breakage from Tasks 1–4.
- **Reuse:** Task 3 imports `services.deferred` (`resolve_deferred_account`, `create_schedules`, `DeferralPlan`, `LineDeferral`) rather than re-implementing — same engine production uses.
- **Open items the implementer must resolve by reading code (flagged, not placeholders):** the exact local variable for service products in `_seed_products` (Task 3 Step 3); whether `AuditLog` has `tenant_id` (Task 4 Step 1 gives the fallback); the precise `deferred_net` computation in `_seed_invoices` (Task 3 Step 4 — mirror `create_invoice`). These are genuine "match the existing code" instructions, and each step states the invariant its test enforces.
