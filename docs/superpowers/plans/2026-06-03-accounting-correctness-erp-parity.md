# Accounting Correctness & ERP Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add IAS 21 FX revaluation (re-run-safe, AR+AP), IAS 2 stock adjustments, IAS 16 asset-disposal GL posting, and an accounting-rules + ERP-parity reference doc to Easy-Books.

**Architecture:** Pure-logic services (`fx_revaluation.py`, new `inventory.py` functions) own the accounting math; thin FastAPI routers wrap them; `services/posting.py:post_transaction` remains the only GL writer. New tables get Alembic migrations guarded with `bind.dialect.has_table(...)` so they coexist with dev `create_all()`. Frontend adds one Inventory page + a disposal modal.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest (backend); Next.js 16 / React 19 / TS (frontend). Decimal money via `services` `D()`/`money()` helpers.

---

## Conventions (read once)

- **Money:** import `from services.posting import EntryInput, post_transaction`; build Decimal values with the repo's `D(...)` and `money(...)` helpers (see `services/inventory.py` imports). `post_transaction(session, user, *, date, description, entries, audit_entity_type=..., audit_detail=...)` validates `Σdebit==Σcredit`, writes the `Transaction` + `JournalEntry` rows + an `AuditLog`, and returns the `Transaction`. **The caller commits.**
- **Accounts:** `from routers.common import get_or_create_account` → `get_or_create_account(session, tenant_id, code, name, type)`.
- **FX rate lookup:** `from services.fx import rate_to_base` → `rate_to_base(session, tenant_id, currency, date)` returns Decimal (doc→base), raises `LookupError` if no rate on/before that date.
- **Tests:** use the `client` fixture + a local `_auth(client)` helper (see `tests/test_multi_currency.py`). Signup tenant base currency is **USD**. To touch the DB directly inside a test, use `app.state.engine` with a `Session`.
- **Run a single test:** `cd backend && uv run pytest tests/<file>::<test> -v`. Full suite: `uv run pytest`.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Migrations:** `cd backend && uv run alembic revision -m "..."` (hand-write the upgrade for new tables — autogenerate is unreliable with SQLite here), then `uv run alembic upgrade head`. New-table upgrades MUST guard with `if not bind.dialect.has_table(bind, "tablename"):`. New columns on existing tables: `with op.batch_alter_table("tablename") as b: b.add_column(...)` (SQLite-safe), no FK lines on ALTER.

---

## File Structure

**Phase 1 — FX revaluation**
- Create: `backend/services/fx_revaluation.py` — pure revaluation engine (AR+AP, auto-reverse, same-date void).
- Modify: `backend/models.py` — add `FxRevaluationRun` table.
- Create: `backend/alembic/versions/0020_fx_revaluation_run.py` — guarded table.
- Modify: `backend/routers/reports.py:883-969` — `/fx-revaluation` becomes a thin wrapper.
- Test: `backend/tests/test_fx_revaluation.py`.

**Phase 2 — Stock adjustments**
- Modify: `backend/models.py` — add `StockAdjustment` table.
- Create: `backend/alembic/versions/0021_stock_adjustment.py` — guarded table.
- Modify: `backend/services/inventory.py` — `_deplete_layers` helper + `adjust_loss`, `adjust_gain`, `write_down`.
- Create: `backend/routers/stock_adjustments.py` — POST/GET endpoints.
- Modify: `backend/main.py` — register router.
- Create: `frontend/src/app/(dashboard)/inventory/adjustments/page.tsx`.
- Modify: `frontend/src/components/Sidebar.tsx` — add nav entry.
- Test: `backend/tests/test_stock_adjustments.py`.

**Phase 3 — Asset disposal**
- Modify: `backend/models.py` — add 3 columns to `FixedAsset`.
- Create: `backend/alembic/versions/0022_asset_disposal.py` — guarded columns.
- Modify: `backend/routers/assets.py:143-156` — `dispose_asset` posts GL.
- Modify: `frontend/src/app/(dashboard)/assets/page.tsx` (or the disposal modal component) — add proceeds/account/date fields.
- Test: `backend/tests/test_asset_disposal.py`.

**Phase 4 — Documentation**
- Create: `docs/ACCOUNTING_RULES.md`.
- Modify: `BLUEPRINT.md` (§11 cross-link), `CLAUDE.md` (router table), `README.md`.

**Phase 5 — Demo seed + green suite**
- Modify: `backend/scripts/seed_demo.py`.
- Run: full `uv run pytest`.

---

## Phase 1 — FX Revaluation Engine

### Task 1.1: `FxRevaluationRun` model + migration

**Files:**
- Modify: `backend/models.py`
- Create: `backend/alembic/versions/0020_fx_revaluation_run.py`

- [ ] **Step 1: Add the model** (place near `ExchangeRate`, ~line 1056)

```python
class FxRevaluationRun(SQLModel, table=True):
    """Tracks each FX revaluation so a re-run for the same date can void the
    prior revaluation + reversal pair before re-posting. IAS 21.23."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    revaluation_date: str
    txn_id: int = Field(foreign_key="transaction.id")
    reversal_txn_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 2: Create the migration**

```python
"""fx revaluation run

Revision ID: 0020_fx_revaluation_run
Revises: 0019_<previous>
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_fx_revaluation_run"
down_revision = "0019_<previous>"   # set to current head: `uv run alembic heads`
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "fxrevaluationrun"):
        op.create_table(
            "fxrevaluationrun",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), index=True, nullable=False),
            sa.Column("revaluation_date", sa.String, nullable=False),
            sa.Column("txn_id", sa.Integer, sa.ForeignKey("transaction.id"), nullable=False),
            sa.Column("reversal_txn_id", sa.Integer, sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    op.drop_table("fxrevaluationrun")
```

- [ ] **Step 3: Set the real `down_revision`**

Run: `cd backend && uv run alembic heads` → copy the printed head id into `down_revision` (replace `0019_<previous>`).

- [ ] **Step 4: Apply + verify**

Run: `cd backend && uv run alembic upgrade head`
Expected: no error; `uv run alembic current` shows `0020_fx_revaluation_run`.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/alembic/versions/0020_fx_revaluation_run.py
git commit -m "feat(fx): FxRevaluationRun table for re-run-safe revaluation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.2: FX engine — AR gain/loss (failing test first)

**Files:**
- Create: `backend/services/fx_revaluation.py`
- Test: `backend/tests/test_fx_revaluation.py`

- [ ] **Step 1: Write the failing test**

```python
"""FX revaluation engine — IAS 21.23 unrealized gain/loss on open AR/AP."""
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from main import app
from sqlmodel import Session, select


def _auth(client: TestClient) -> dict:
    client.post("/api/auth/signup", json={
        "email": "fx@rev.test", "password": "password123",
        "full_name": "U", "company_name": "FX Co"})
    r = client.post("/api/auth/login", data={"username": "fx@rev.test", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _rate(client, auth, d, frm, rate, to="USD"):
    client.post("/api/exchange-rates", headers=auth,
                json={"date": d, "from_currency": frm, "to_currency": to, "rate": rate})


def _tb_row(client, auth, code):
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    return next((r for r in rows if r["code"] == code), None)


def _sum(rows, key):
    return sum((Decimal(str(r.get(key) or 0)) for r in rows), start=Decimal("0"))


def test_ar_fx_gain_posts_dr_ar_cr_4901(client: TestClient):
    auth = _auth(client)
    # Booked at 1.10, closes at 1.20 -> AR worth more in base -> GAIN
    _rate(client, auth, "2026-05-01", "EUR", "1.10")
    cust = client.post("/api/customers", headers=auth, json={"name": "A"}).json()
    client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-05-02", "due_date": "2026-06-30",
        "gst_rate": 0, "currency": "EUR",
        "lines": [{"description": "S", "qty": 1, "rate": 1000}]})
    _rate(client, auth, "2026-05-31", "EUR", "1.20")

    r = client.post("/api/reports/fx-revaluation?revaluation_date=2026-05-31", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["entries_count"] >= 2
    # Outstanding 1000 EUR: (1.20-1.10)*1000 = 100 base gain
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    fx = next(r for r in rows if r["code"] == "4901")
    # 4901 is Revenue -> credited on a gain
    assert Decimal(str(fx["total_credit"])) == Decimal("100")
    assert _sum(rows, "total_debit") == _sum(rows, "total_credit")
```

- [ ] **Step 2: Run it — expect failure**

Run: `cd backend && uv run pytest tests/test_fx_revaluation.py::test_ar_fx_gain_posts_dr_ar_cr_4901 -v`
Expected: FAIL (current endpoint posts only the reval entry; this should still pass for the gain math — but we are about to replace the endpoint with the service, so run to confirm the baseline, then proceed).

- [ ] **Step 3: Write the engine**

```python
"""IAS 21.23 — period-end revaluation of open foreign-currency monetary items.

Each run posts the full unrealized gain/loss at `revaluation_date` and an
auto-reversing entry on the first day of the next calendar month, so each
period stands alone and settlement realizes the true figure. A re-run for the
same date voids the prior pair first (idempotent + period-aware)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from models import (Account, Bill, FxRevaluationRun, Invoice, JournalEntry,
                    PaymentAllocation, Tenant, Transaction, User)
from routers.common import get_or_create_account
from services.fx import rate_to_base
from services.posting import EntryInput, post_transaction

D = Decimal
ZERO = D("0")


def _money(x: Decimal) -> Decimal:
    return x.quantize(D("0.01"))


@dataclass
class RevaluationResult:
    revaluation_txn_id: Optional[int]
    reversal_txn_id: Optional[int]
    entries_count: int
    net_gain_loss: Decimal
    message: str


def _first_of_next_month(d: str) -> str:
    y, m, _ = (int(p) for p in d.split("-"))
    return f"{y + 1}-01-01" if m == 12 else f"{y}-{m + 1:02d}-01"


def _invoice_outstanding(session: Session, inv: Invoice) -> Decimal:
    allocated = session.exec(
        select(PaymentAllocation.amount).where(PaymentAllocation.invoice_id == inv.id)
    ).all()
    return D(str(inv.total)) - sum((D(str(a)) for a in allocated), start=ZERO)


def _bill_outstanding(session: Session, bill: Bill) -> Decimal:
    allocated = session.exec(
        select(PaymentAllocation.amount).where(PaymentAllocation.bill_id == bill.id)
    ).all()
    return D(str(bill.total)) - sum((D(str(a)) for a in allocated), start=ZERO)


def _void_prior_run(session: Session, run: FxRevaluationRun) -> None:
    for tid in (run.txn_id, run.reversal_txn_id):
        if not tid:
            continue
        for je in session.exec(select(JournalEntry).where(JournalEntry.transaction_id == tid)).all():
            session.delete(je)
        txn = session.get(Transaction, tid)
        if txn:
            session.delete(txn)
    session.delete(run)
    session.flush()


def revalue_open_positions(
    session: Session, *, tenant_id: int, user: User, revaluation_date: str,
) -> RevaluationResult:
    tenant = session.get(Tenant, tenant_id)
    base = tenant.base_currency if tenant else "USD"

    # Idempotent: void any prior run for this exact date.
    prior = session.exec(
        select(FxRevaluationRun).where(
            FxRevaluationRun.tenant_id == tenant_id,
            FxRevaluationRun.revaluation_date == revaluation_date,
        )
    ).all()
    for run in prior:
        _void_prior_run(session, run)

    fx_acc = get_or_create_account(session, tenant_id, "4901", "Unrealised FX Gain/Loss", "Revenue")

    entries: list[EntryInput] = []
    net = ZERO

    # AR (invoices): gain -> Dr AR / Cr 4901 ; loss -> Dr 4901 / Cr AR
    invoices = session.exec(select(Invoice).where(
        Invoice.tenant_id == tenant_id,
        Invoice.status.in_(["draft", "posted", "partial", "sent"]),
        Invoice.transaction_id.is_not(None),
        Invoice.currency != base,
    )).all()
    for inv in invoices:
        out = _invoice_outstanding(session, inv)
        if out <= ZERO:
            continue
        try:
            closing = rate_to_base(session, tenant_id, inv.currency, revaluation_date)
        except LookupError:
            continue
        diff = _money(out * closing) - _money(out * D(str(inv.exchange_rate)))
        if abs(diff) < D("0.01"):
            continue
        ar = session.get(Account, inv.ar_account_id) if inv.ar_account_id else \
            session.exec(select(Account).where(Account.tenant_id == tenant_id, Account.code == "1100")).first()
        if not ar:
            continue
        if diff > ZERO:
            entries += [EntryInput(account_id=ar.id, debit=diff), EntryInput(account_id=fx_acc.id, credit=diff)]
        else:
            entries += [EntryInput(account_id=fx_acc.id, debit=-diff), EntryInput(account_id=ar.id, credit=-diff)]
        net += diff

    # AP (bills): owe-more (diff>0) -> Dr 4901 / Cr AP (loss) ; owe-less -> Dr AP / Cr 4901 (gain)
    bills = session.exec(select(Bill).where(
        Bill.tenant_id == tenant_id,
        Bill.status.in_(["posted", "partial"]),
        Bill.transaction_id.is_not(None),
        Bill.currency != base,
    )).all()
    for bill in bills:
        out = _bill_outstanding(session, bill)
        if out <= ZERO:
            continue
        try:
            closing = rate_to_base(session, tenant_id, bill.currency, revaluation_date)
        except LookupError:
            continue
        diff = _money(out * closing) - _money(out * D(str(bill.exchange_rate)))
        if abs(diff) < D("0.01"):
            continue
        ap = session.get(Account, bill.ap_account_id) if bill.ap_account_id else \
            session.exec(select(Account).where(Account.tenant_id == tenant_id, Account.code == "2000")).first()
        if not ap:
            continue
        if diff > ZERO:  # liability grew -> loss
            entries += [EntryInput(account_id=fx_acc.id, debit=diff), EntryInput(account_id=ap.id, credit=diff)]
            net -= diff
        else:           # liability shrank -> gain
            entries += [EntryInput(account_id=ap.id, debit=-diff), EntryInput(account_id=fx_acc.id, credit=-diff)]
            net += -diff

    if not entries:
        return RevaluationResult(None, None, 0, ZERO, "No open foreign-currency positions to revalue")

    reval = post_transaction(
        session, user, date=revaluation_date,
        description=f"FX Revaluation as at {revaluation_date}",
        entries=entries, audit_entity_type="fx_revaluation",
        audit_detail={"revaluation_date": revaluation_date})
    session.flush()

    # Auto-reversal on first day of next month: swap debit/credit.
    rev_entries = [EntryInput(account_id=e.account_id, debit=e.credit, credit=e.debit)
                   for e in (x.normalised() for x in entries)]
    reversal = post_transaction(
        session, user, date=_first_of_next_month(revaluation_date),
        description=f"FX Revaluation reversal of {revaluation_date}",
        entries=rev_entries, audit_entity_type="fx_revaluation_reversal",
        audit_detail={"revaluation_date": revaluation_date})
    session.flush()

    session.add(FxRevaluationRun(
        tenant_id=tenant_id, revaluation_date=revaluation_date,
        txn_id=reval.id, reversal_txn_id=reversal.id))

    return RevaluationResult(reval.id, reversal.id, len(entries), net,
                             f"Revalued {len(entries)//2} position(s)")
```

> NOTE for implementer: confirm `EntryInput.normalised()` exposes `.debit`/`.credit` (it does — see `services/posting.py`). If `Invoice.ar_account_id`/`Bill.ap_account_id` differ, fix the attribute names (verified present in `models.py` at design time).

- [ ] **Step 4: Wire the endpoint to the service** (replace `routers/reports.py:883-969` body)

```python
@router.post("/fx-revaluation")
def run_fx_revaluation(session: SessionDep, user: CurrentUserDep, revaluation_date: str):
    """Revalue open foreign-currency AR & AP to closing rate. IAS 21.23."""
    from services.fx_revaluation import revalue_open_positions
    result = revalue_open_positions(session, tenant_id=user.tenant_id, user=user,
                                    revaluation_date=revaluation_date)
    session.commit()
    return {
        "message": result.message,
        "entries_count": result.entries_count,
        "revaluation_txn_id": result.revaluation_txn_id,
        "reversal_txn_id": result.reversal_txn_id,
        "net_gain_loss": str(result.net_gain_loss),
    }
```

- [ ] **Step 5: Run the gain test — expect PASS**

Run: `cd backend && uv run pytest tests/test_fx_revaluation.py::test_ar_fx_gain_posts_dr_ar_cr_4901 -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/fx_revaluation.py backend/routers/reports.py backend/tests/test_fx_revaluation.py
git commit -m "feat(fx): re-run-safe AR/AP revaluation engine with auto-reversal

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.3: FX engine — loss, AP, auto-reverse, and no-double-count tests

**Files:**
- Test: `backend/tests/test_fx_revaluation.py`

- [ ] **Step 1: Add the tests**

```python
def test_ar_fx_loss_posts_dr_4901_cr_ar(client: TestClient):
    auth = _auth(client)
    _rate(client, auth, "2026-05-01", "EUR", "1.20")
    cust = client.post("/api/customers", headers=auth, json={"name": "A"}).json()
    client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-05-02", "due_date": "2026-06-30",
        "gst_rate": 0, "currency": "EUR", "lines": [{"description": "S", "qty": 1, "rate": 1000}]})
    _rate(client, auth, "2026-05-31", "EUR", "1.10")  # AR worth less -> loss
    client.post("/api/reports/fx-revaluation?revaluation_date=2026-05-31", headers=auth)
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    fx = next(r for r in rows if r["code"] == "4901")
    assert Decimal(str(fx["total_debit"])) == Decimal("100")  # loss debits 4901
    assert _sum(rows, "total_debit") == _sum(rows, "total_credit")


def test_rerun_same_date_does_not_double_count(client: TestClient):
    auth = _auth(client)
    _rate(client, auth, "2026-05-01", "EUR", "1.10")
    cust = client.post("/api/customers", headers=auth, json={"name": "A"}).json()
    client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-05-02", "due_date": "2026-06-30",
        "gst_rate": 0, "currency": "EUR", "lines": [{"description": "S", "qty": 1, "rate": 1000}]})
    _rate(client, auth, "2026-05-31", "EUR", "1.20")
    client.post("/api/reports/fx-revaluation?revaluation_date=2026-05-31", headers=auth)
    client.post("/api/reports/fx-revaluation?revaluation_date=2026-05-31", headers=auth)  # re-run
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    fx = next(r for r in rows if r["code"] == "4901")
    # Still exactly 100 credit (single run), not 200 — prior pair was voided.
    assert Decimal(str(fx["total_credit"])) == Decimal("100")
    assert _sum(rows, "total_debit") == _sum(rows, "total_credit")


def test_reversal_dated_first_of_next_month(client: TestClient):
    auth = _auth(client)
    _rate(client, auth, "2026-05-01", "EUR", "1.10")
    cust = client.post("/api/customers", headers=auth, json={"name": "A"}).json()
    client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-05-02", "due_date": "2026-06-30",
        "gst_rate": 0, "currency": "EUR", "lines": [{"description": "S", "qty": 1, "rate": 1000}]})
    _rate(client, auth, "2026-05-31", "EUR", "1.20")
    body = client.post("/api/reports/fx-revaluation?revaluation_date=2026-05-31", headers=auth).json()
    assert body["reversal_txn_id"] is not None
    with Session(app.state.engine) as s:
        from models import Transaction
        rev = s.get(Transaction, body["reversal_txn_id"])
        assert rev.date == "2026-06-01"
```

- [ ] **Step 2: Run all FX tests — expect PASS**

Run: `cd backend && uv run pytest tests/test_fx_revaluation.py -v`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_fx_revaluation.py
git commit -m "test(fx): loss, re-run safety, next-month reversal coverage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 2 — Stock Adjustments (IAS 2)

### Task 2.1: `StockAdjustment` model + migration

**Files:**
- Modify: `backend/models.py`
- Create: `backend/alembic/versions/0021_stock_adjustment.py`

- [ ] **Step 1: Add the model** (near `StockMovement`, ~line 525)

```python
class StockAdjustment(SQLModel, table=True):
    """IAS 2 inventory adjustment: quantity loss/gain or NRV write-down."""
    __table_args__ = (
        CheckConstraint("reason IN ('loss','gain','write_down')", name="ck_stock_adj_reason"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    product_id: int = Field(foreign_key="product.id")
    reason: str
    qty: Money = money_col()                  # >0 for loss/gain; 0 for write_down
    unit_cost: Money = money_col()            # gain: layer cost; write_down: NRV unit cost
    cost_amount: Money = money_col()          # GL value posted (computed)
    note: Optional[str] = None
    adjustment_date: str
    movement_id: Optional[int] = Field(default=None, foreign_key="stockmovement.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 2: Migration** (same guarded pattern as Task 1.1; `down_revision = "0020_fx_revaluation_run"`)

```python
"""stock adjustment

Revision ID: 0021_stock_adjustment
Revises: 0020_fx_revaluation_run
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_stock_adjustment"
down_revision = "0020_fx_revaluation_run"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "stockadjustment"):
        op.create_table(
            "stockadjustment",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), index=True, nullable=False),
            sa.Column("product_id", sa.Integer, sa.ForeignKey("product.id"), nullable=False),
            sa.Column("reason", sa.String, nullable=False),
            sa.Column("qty", sa.Numeric, nullable=False),
            sa.Column("unit_cost", sa.Numeric, nullable=False),
            sa.Column("cost_amount", sa.Numeric, nullable=False),
            sa.Column("note", sa.String, nullable=True),
            sa.Column("adjustment_date", sa.String, nullable=False),
            sa.Column("movement_id", sa.Integer, sa.ForeignKey("stockmovement.id"), nullable=True),
            sa.Column("transaction_id", sa.Integer, sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    op.drop_table("stockadjustment")
```

- [ ] **Step 3: Apply + verify**

Run: `cd backend && uv run alembic upgrade head` → `uv run alembic current` shows `0021_stock_adjustment`.

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/alembic/versions/0021_stock_adjustment.py
git commit -m "feat(inventory): StockAdjustment table

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2.2: inventory.py — `adjust_loss` / `adjust_gain` / `write_down`

**Files:**
- Modify: `backend/services/inventory.py`
- Test: `backend/tests/test_stock_adjustments.py`

- [ ] **Step 1: Write failing unit tests** (call the service directly with a Session)

```python
"""IAS 2 stock adjustment service: loss/gain/write-down layer accounting."""
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from main import app
from sqlmodel import Session, select


def _auth(client):
    client.post("/api/auth/signup", json={"email": "adj@t.test", "password": "password123",
                                          "full_name": "U", "company_name": "Adj Co"})
    r = client.post("/api/auth/login", data={"username": "adj@t.test", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _stock_product(client, auth, qty=10, cost=5):
    """Create a stock product and receive `qty` @ `cost` via a posted bill so layers exist."""
    p = client.post("/api/products", headers=auth, json={
        "name": "Widget", "product_type": "stock", "price": 20, "sku": "W1"}).json()
    vend = client.post("/api/vendors", headers=auth, json={"name": "V"}).json()
    client.post("/api/bills", headers=auth, json={
        "vendor_id": vend["id"], "bill_date": "2026-05-01", "due_date": "2026-05-31",
        "gst_rate": 0, "status": "posted",
        "lines": [{"description": "Widget", "qty": qty, "rate": cost, "product_id": p["id"]}]})
    return p


def test_adjust_loss_depletes_and_returns_cost(client: TestClient):
    auth = _auth(client)
    p = _stock_product(client, auth, qty=10, cost=5)
    from services.inventory import adjust_loss
    from models import Product, User
    with Session(app.state.engine) as s:
        user = s.exec(select(User)).first()
        cost = adjust_loss(s, tenant_id=user.tenant_id, product_id=p["id"], qty=Decimal("3"),
                           block_negative=True)
        s.commit()
        assert cost == Decimal("15.00")           # 3 @ 5
        prod = s.get(Product, p["id"])
        assert Decimal(str(prod.stock_qty)) == Decimal("7")


def test_adjust_loss_block_negative_raises(client: TestClient):
    auth = _auth(client)
    p = _stock_product(client, auth, qty=2, cost=5)
    from services.inventory import adjust_loss, InventoryError
    from models import User
    with Session(app.state.engine) as s:
        user = s.exec(select(User)).first()
        with pytest.raises(InventoryError):
            adjust_loss(s, tenant_id=user.tenant_id, product_id=p["id"], qty=Decimal("5"),
                        block_negative=True)


def test_adjust_gain_adds_layer(client: TestClient):
    auth = _auth(client)
    p = _stock_product(client, auth, qty=10, cost=5)
    from services.inventory import adjust_gain
    from models import Product, User
    with Session(app.state.engine) as s:
        user = s.exec(select(User)).first()
        val = adjust_gain(s, tenant_id=user.tenant_id, product_id=p["id"], qty=Decimal("4"),
                          unit_cost=Decimal("6"))
        s.commit()
        assert val == Decimal("24.00")
        prod = s.get(Product, p["id"])
        assert Decimal(str(prod.stock_qty)) == Decimal("14")


def test_write_down_lowers_layer_cost(client: TestClient):
    auth = _auth(client)
    p = _stock_product(client, auth, qty=10, cost=5)
    from services.inventory import write_down
    from models import Product, User
    with Session(app.state.engine) as s:
        user = s.exec(select(User)).first()
        amt = write_down(s, tenant_id=user.tenant_id, product_id=p["id"], nrv_unit_cost=Decimal("3"))
        s.commit()
        assert amt == Decimal("20.00")            # 10 units * (5-3)
        prod = s.get(Product, p["id"])
        assert Decimal(str(prod.stock_qty)) == Decimal("10")   # qty unchanged
```

- [ ] **Step 2: Run — expect FAIL** (`ImportError: cannot import name 'adjust_loss'`)

Run: `cd backend && uv run pytest tests/test_stock_adjustments.py -v`
Expected: FAIL on import.

- [ ] **Step 3: Refactor depletion + add functions** in `services/inventory.py`

First extract the layer-depletion loop already inside `consume_stock` into a reusable helper (DRY), then add the three functions:

```python
def _deplete_layers(session: Session, *, tenant_id: int, product_id: int,
                    qty: Decimal, cost_method: str) -> tuple[Decimal, Optional[int], Optional[str]]:
    """Drain `qty` from remaining layers oldest-first. Returns
    (total_cost, first_location_id, first_lot_no). WAvg charges at product
    avg_cost; FIFO charges at each layer's own unit_cost."""
    prod = session.get(Product, product_id)
    avg_cost = D(prod.avg_cost)
    layers = session.exec(
        select(InventoryLayer).where(
            InventoryLayer.tenant_id == tenant_id,
            InventoryLayer.product_id == product_id,
            InventoryLayer.qty_remaining > 0,
        ).order_by(InventoryLayer.id.asc())
    ).all()
    cost = ZERO
    remaining = qty
    loc_id: Optional[int] = None
    lot_no: Optional[str] = None
    for layer in layers:
        if remaining <= 0:
            break
        take = min(D(layer.qty_remaining), remaining)
        cost += money(take * (D(layer.unit_cost) if cost_method == "fifo" else avg_cost))
        layer.qty_remaining = D(layer.qty_remaining) - take
        remaining -= take
        session.add(layer)
        if loc_id is None:
            loc_id, lot_no = layer.location_id, layer.lot_no
    return cost, loc_id, lot_no


def _cost_method(session: Session, tenant_id: int) -> str:
    from models import Tenant as _T
    t = session.get(_T, tenant_id)
    return getattr(t, "cost_method", "wavg") if t else "wavg"


def adjust_loss(session: Session, *, tenant_id: int, product_id: int,
                qty: Decimal, block_negative: bool = False) -> Decimal:
    """Shrinkage/write-off: deplete layers, decrement stock_qty, return cost."""
    qty = D(qty)
    if qty <= 0:
        return ZERO
    prod = session.exec(select(Product).where(
        Product.id == product_id, Product.tenant_id == tenant_id).with_for_update()).first()
    if not prod or prod.product_type != "stock":
        return ZERO
    if block_negative and D(prod.stock_qty) < qty:
        raise InventoryError(
            f"Insufficient stock for {prod.name}: on hand {money(prod.stock_qty)}, loss {money(qty)}")
    cost, loc_id, lot_no = _deplete_layers(
        session, tenant_id=tenant_id, product_id=product_id, qty=qty, cost_method=_cost_method(session, tenant_id))
    prod.stock_qty = D(prod.stock_qty) - qty
    session.add(prod)
    record_movement(session, tenant_id=tenant_id, product_id=product_id, direction="ADJUSTMENT",
                    qty=qty, from_location_id=loc_id or _default_own_location(session, tenant_id),
                    lot_no=lot_no, unit_cost=(cost / qty if qty else ZERO),
                    source_doc_type="stock_adjustment", posted_to_gl=True)
    return money(cost)


def adjust_gain(session: Session, *, tenant_id: int, product_id: int,
                qty: Decimal, unit_cost: Decimal) -> Decimal:
    """Found stock / count surplus: add a layer, bump stock_qty + avg_cost."""
    qty, unit_cost = D(qty), D(unit_cost)
    if qty <= 0:
        return ZERO
    prod = session.exec(select(Product).where(
        Product.id == product_id, Product.tenant_id == tenant_id).with_for_update()).first()
    if not prod or prod.product_type != "stock":
        return ZERO
    old_qty, old_val = D(prod.stock_qty), D(prod.stock_qty) * D(prod.avg_cost)
    new_qty = old_qty + qty
    prod.stock_qty = new_qty
    prod.avg_cost = money((old_val + qty * unit_cost) / new_qty) if new_qty else ZERO
    session.add(prod)
    session.add(InventoryLayer(tenant_id=tenant_id, product_id=product_id, qty_received=qty,
                               qty_remaining=qty, unit_cost=money(unit_cost),
                               source_doc="stock_adjustment"))
    record_movement(session, tenant_id=tenant_id, product_id=product_id, direction="ADJUSTMENT",
                    qty=qty, to_location_id=_default_own_location(session, tenant_id),
                    unit_cost=unit_cost, source_doc_type="stock_adjustment", posted_to_gl=True)
    return money(qty * unit_cost)


def write_down(session: Session, *, tenant_id: int, product_id: int,
               nrv_unit_cost: Decimal) -> Decimal:
    """IAS 2.34 NRV write-down: lower each remaining layer's unit_cost to NRV.
    Qty unchanged; returns total write-down amount."""
    nrv = D(nrv_unit_cost)
    prod = session.exec(select(Product).where(
        Product.id == product_id, Product.tenant_id == tenant_id).with_for_update()).first()
    if not prod or prod.product_type != "stock":
        return ZERO
    layers = session.exec(select(InventoryLayer).where(
        InventoryLayer.tenant_id == tenant_id, InventoryLayer.product_id == product_id,
        InventoryLayer.qty_remaining > 0)).all()
    total = ZERO
    for layer in layers:
        if D(layer.unit_cost) > nrv:
            total += money(D(layer.qty_remaining) * (D(layer.unit_cost) - nrv))
            layer.unit_cost = money(nrv)
            session.add(layer)
    if D(prod.avg_cost) > nrv:
        prod.avg_cost = money(nrv)
        session.add(prod)
    return money(total)
```

> Then replace the inline depletion loop in `consume_stock` with a call to `_deplete_layers` to keep one code path (optional but recommended; if risk-averse, leave `consume_stock` untouched and only add the new helpers — the tests don't require the refactor).

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_stock_adjustments.py -v`
Expected: the four service tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/inventory.py backend/tests/test_stock_adjustments.py
git commit -m "feat(inventory): adjust_loss/adjust_gain/write_down layer functions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2.3: `stock_adjustments` router + GL posting

**Files:**
- Create: `backend/routers/stock_adjustments.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_stock_adjustments.py`

- [ ] **Step 1: Add endpoint test**

```python
def test_post_loss_adjustment_posts_gl_and_balances(client: TestClient):
    auth = _auth(client)
    p = _stock_product(client, auth, qty=10, cost=5)
    r = client.post("/api/stock-adjustments", headers=auth, json={
        "product_id": p["id"], "reason": "loss", "qty": 3,
        "adjustment_date": "2026-05-10", "note": "breakage"})
    assert r.status_code == 201, r.text
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    adj = next(r for r in rows if r["code"] == "5040")
    assert Decimal(str(adj["total_debit"])) == Decimal("15")     # Dr 5040
    assert sum((Decimal(str(x.get("total_debit") or 0)) for x in rows), start=Decimal("0")) == \
           sum((Decimal(str(x.get("total_credit") or 0)) for x in rows), start=Decimal("0"))
    items = client.get("/api/stock-adjustments", headers=auth).json()["items"]
    assert len(items) == 1 and items[0]["reason"] == "loss"


def test_post_gain_adjustment_credits_5040(client: TestClient):
    auth = _auth(client)
    p = _stock_product(client, auth, qty=10, cost=5)
    r = client.post("/api/stock-adjustments", headers=auth, json={
        "product_id": p["id"], "reason": "gain", "qty": 2, "unit_cost": 6,
        "adjustment_date": "2026-05-10"})
    assert r.status_code == 201, r.text
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    adj = next(r for r in rows if r["code"] == "5040")
    assert Decimal(str(adj["total_credit"])) == Decimal("12")    # Cr 5040 (2*6)
```

- [ ] **Step 2: Run — expect FAIL** (404 / no route)

Run: `cd backend && uv run pytest tests/test_stock_adjustments.py::test_post_loss_adjustment_posts_gl_and_balances -v`
Expected: FAIL.

- [ ] **Step 3: Write the router**

```python
"""IAS 2 stock adjustments: loss / gain / NRV write-down with GL posting."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from db import SessionDep
from auth import CurrentUserDep
from models import Account, Product, Settings, StockAdjustment
from routers.common import get_or_create_account
from services.inventory import (InventoryError, adjust_gain, adjust_loss, write_down)
from services.posting import EntryInput, post_transaction

router = APIRouter(prefix="/api/stock-adjustments", tags=["stock-adjustments"])
D = Decimal


class AdjustmentIn(BaseModel):
    product_id: int
    reason: str                       # loss | gain | write_down
    qty: Decimal = Decimal("0")
    unit_cost: Optional[Decimal] = None      # gain: layer cost; write_down: NRV unit cost
    adjustment_date: str
    note: Optional[str] = None


def _inv_account(session, tenant_id: int, prod: Product) -> Account:
    if prod.stock_account_id:
        acc = session.get(Account, prod.stock_account_id)
        if acc:
            return acc
    return get_or_create_account(session, tenant_id, "1200", "Inventory", "Asset")


@router.post("", status_code=201)
def create_adjustment(session: SessionDep, user: CurrentUserDep, body: AdjustmentIn):
    if body.reason not in ("loss", "gain", "write_down"):
        raise HTTPException(400, "reason must be loss, gain, or write_down")
    prod = session.exec(select(Product).where(
        Product.id == body.product_id, Product.tenant_id == user.tenant_id)).first()
    if not prod or prod.product_type != "stock":
        raise HTTPException(400, "product not found or not a stock product")

    inv_acc = _inv_account(session, user.tenant_id, prod)
    adj_acc = get_or_create_account(session, user.tenant_id, "5040", "Inventory Adjustments", "Expense")

    try:
        if body.reason == "loss":
            block = bool(getattr(session.exec(select(Settings).where(
                Settings.tenant_id == user.tenant_id)).first(), "block_negative_stock", False))
            cost = adjust_loss(session, tenant_id=user.tenant_id, product_id=prod.id,
                               qty=D(body.qty), block_negative=block)
            entries = [EntryInput(account_id=adj_acc.id, debit=cost),
                       EntryInput(account_id=inv_acc.id, credit=cost)]
            unit = body.qty and (cost / D(body.qty))
        elif body.reason == "gain":
            if body.unit_cost is None:
                raise HTTPException(400, "unit_cost required for gain")
            cost = adjust_gain(session, tenant_id=user.tenant_id, product_id=prod.id,
                               qty=D(body.qty), unit_cost=D(body.unit_cost))
            entries = [EntryInput(account_id=inv_acc.id, debit=cost),
                       EntryInput(account_id=adj_acc.id, credit=cost)]
            unit = D(body.unit_cost)
        else:  # write_down
            if body.unit_cost is None:
                raise HTTPException(400, "unit_cost (NRV) required for write_down")
            cost = write_down(session, tenant_id=user.tenant_id, product_id=prod.id,
                              nrv_unit_cost=D(body.unit_cost))
            entries = [EntryInput(account_id=adj_acc.id, debit=cost),
                       EntryInput(account_id=inv_acc.id, credit=cost)]
            unit = D(body.unit_cost)
    except InventoryError as e:
        raise HTTPException(400, str(e))

    if cost <= 0:
        raise HTTPException(400, "adjustment has no cost impact")

    txn = post_transaction(session, user, date=body.adjustment_date,
                           description=f"Stock {body.reason} — {prod.name}",
                           entries=entries, audit_entity_type="stock_adjustment",
                           audit_detail={"product_id": prod.id, "reason": body.reason})
    rec = StockAdjustment(tenant_id=user.tenant_id, product_id=prod.id, reason=body.reason,
                          qty=D(body.qty), unit_cost=D(unit or 0), cost_amount=cost,
                          note=body.note, adjustment_date=body.adjustment_date,
                          transaction_id=txn.id)
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return {"id": rec.id, "reason": rec.reason, "cost_amount": str(rec.cost_amount),
            "jv_number": txn.jv_number}


@router.get("")
def list_adjustments(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(select(StockAdjustment).where(
        StockAdjustment.tenant_id == user.tenant_id).order_by(StockAdjustment.id.desc())).all()
    return {"items": [{"id": r.id, "product_id": r.product_id, "reason": r.reason,
                       "qty": str(r.qty), "unit_cost": str(r.unit_cost),
                       "cost_amount": str(r.cost_amount), "note": r.note,
                       "adjustment_date": r.adjustment_date} for r in rows]}
```

> NOTE: confirm the settings model name (`Settings`) and the `block_negative_stock` attribute against `routers/settings.py` / `models.py`; adapt if the field lives elsewhere.

- [ ] **Step 4: Register the router** in `backend/main.py`

Add `stock_adjustments` to the `from routers import (...)` block and append `stock_adjustments.router` to the list iterated by `app.include_router(r)`.

- [ ] **Step 5: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_stock_adjustments.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/stock_adjustments.py backend/main.py backend/tests/test_stock_adjustments.py
git commit -m "feat(inventory): stock-adjustments router with IAS 2 GL postings

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2.4: Frontend — Stock Adjustments page + sidebar

**Files:**
- Create: `frontend/src/app/(dashboard)/inventory/adjustments/page.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Read the Next.js guide + an existing page**

Read `frontend/AGENTS.md`, then read an existing list+form page (e.g. `frontend/src/app/(dashboard)/products/categories/page.tsx`) to copy the `apiFetch`, table, and form patterns exactly (client component, `useState`, `useEffect`, brand colors).

- [ ] **Step 2: Create the page**

Build a client page that:
- `GET /api/stock-adjustments` on mount → table (date, product, reason, qty, unit cost, cost amount, note).
- A "New adjustment" form: product `<select>` (from `GET /api/products` filtered `product_type==="stock"`), reason `<select>` (loss/gain/write_down), qty input (hidden/0 for write_down), unit-cost input (shown for gain + write_down, labelled "NRV unit cost" for write_down), date, note.
- `POST /api/stock-adjustments` via `apiFetch`; on success refetch list + reset form; show server error text on 400.
- Use lucide-react icons, Tailwind, brand colors (`#b8943f`, `#f6f3ee`, `#1a1814`).

- [ ] **Step 3: Add the sidebar entry** in `Sidebar.tsx`

In the existing `"Inventory"` section of the `NAV` array, add `{ label: "Stock Adjustments", href: "/inventory/adjustments", icon: <Lucide icon> }` following the exact shape of sibling entries.

- [ ] **Step 4: Build check**

Run: `cd frontend && npm run lint && npm run build`
Expected: lint clean; build succeeds (route `/inventory/adjustments` listed).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/"(dashboard)"/inventory/adjustments/page.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat(ui): Stock Adjustments page under Inventory

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 3 — Asset Disposal GL (IAS 16.71)

### Task 3.1: `FixedAsset` disposal columns + migration

**Files:**
- Modify: `backend/models.py:797-821`
- Create: `backend/alembic/versions/0022_asset_disposal.py`

- [ ] **Step 1: Add columns to `FixedAsset`** (after `last_depreciation_date`)

```python
    disposal_date: Optional[str] = None
    disposal_proceeds: Money = money_col()
    disposal_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")
```

- [ ] **Step 2: Migration** (`down_revision = "0021_stock_adjustment"`; columns via batch ALTER, no FK on ALTER)

```python
"""asset disposal columns

Revision ID: 0022_asset_disposal
Revises: 0021_stock_adjustment
"""
from alembic import op
import sqlalchemy as sa

revision = "0022_asset_disposal"
down_revision = "0021_stock_adjustment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("fixedasset")}
    with op.batch_alter_table("fixedasset") as b:
        if "disposal_date" not in cols:
            b.add_column(sa.Column("disposal_date", sa.String, nullable=True))
        if "disposal_proceeds" not in cols:
            b.add_column(sa.Column("disposal_proceeds", sa.Numeric, nullable=True))
        if "disposal_transaction_id" not in cols:
            b.add_column(sa.Column("disposal_transaction_id", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("fixedasset") as b:
        b.drop_column("disposal_transaction_id")
        b.drop_column("disposal_proceeds")
        b.drop_column("disposal_date")
```

- [ ] **Step 3: Apply + verify**

Run: `cd backend && uv run alembic upgrade head` → `uv run alembic current` shows `0022_asset_disposal`.

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/alembic/versions/0022_asset_disposal.py
git commit -m "feat(assets): FixedAsset disposal columns

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3.2: `dispose_asset` posts GL

**Files:**
- Modify: `backend/routers/assets.py:143-156`
- Test: `backend/tests/test_asset_disposal.py`

- [ ] **Step 1: Write failing tests**

```python
"""IAS 16.71 asset disposal: NBV derecognition + gain/loss."""
from decimal import Decimal
from fastapi.testclient import TestClient


def _auth(client):
    client.post("/api/auth/signup", json={"email": "d@a.test", "password": "password123",
                                          "full_name": "U", "company_name": "Asset Co"})
    r = client.post("/api/auth/login", data={"username": "d@a.test", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _asset(client, auth, cost=1000, life=10):
    return client.post("/api/assets", headers=auth, json={
        "name": "Van", "acquisition_date": "2026-01-01", "acquisition_cost": cost,
        "salvage_value": 0, "useful_life_months": life, "method": "straight_line"}).json()


def _sum(rows, key):
    return sum((Decimal(str(r.get(key) or 0)) for r in rows), start=Decimal("0"))


def test_disposal_gain_posts_4900_and_balances(client: TestClient):
    auth = _auth(client)
    a = _asset(client, auth, cost=1000)
    # Sell for 1200 with zero accumulated depreciation -> gain 200, NBV 1000.
    r = client.patch(f"/api/assets/{a['id']}/dispose", headers=auth, json={
        "proceeds": 1200, "disposal_date": "2026-06-01"})
    assert r.status_code == 200, r.text
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    gain = next(r for r in rows if r["code"] == "4900")
    assert Decimal(str(gain["total_credit"])) == Decimal("200")
    assert _sum(rows, "total_debit") == _sum(rows, "total_credit")


def test_disposal_scrap_is_full_loss(client: TestClient):
    auth = _auth(client)
    a = _asset(client, auth, cost=1000)
    r = client.patch(f"/api/assets/{a['id']}/dispose", headers=auth, json={
        "disposal_date": "2026-06-01"})       # proceeds default 0 -> loss = NBV 1000
    assert r.status_code == 200, r.text
    rows = client.get("/api/reports/trial-balance", headers=auth).json()
    loss = next(r for r in rows if r["code"] == "5900")
    assert Decimal(str(loss["total_debit"])) == Decimal("1000")
    assert _sum(rows, "total_debit") == _sum(rows, "total_credit")
```

> If `POST /api/assets` requires explicit account ids, read `routers/assets.py` create handler and add the fields the test needs (the create path auto-resolves asset/accum-depr/expense accounts in most setups; adapt the `_asset` helper to match).

- [ ] **Step 2: Run — expect FAIL** (disposal posts nothing; 4900/5900 rows absent)

Run: `cd backend && uv run pytest tests/test_asset_disposal.py -v`
Expected: FAIL.

- [ ] **Step 3: Rewrite `dispose_asset`**

```python
class DisposeIn(BaseModel):
    proceeds: Decimal = Decimal("0")
    proceeds_account_id: Optional[int] = None
    disposal_date: str


@router.patch("/{asset_id}/dispose")
def dispose_asset(session: SessionDep, user: WriteUserDep, asset_id: int, body: DisposeIn):
    asset = session.exec(select(FixedAsset).where(
        FixedAsset.id == asset_id, FixedAsset.tenant_id == user.tenant_id)).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    if asset.is_disposed:
        raise HTTPException(400, "Asset already disposed")

    proceeds = D(body.proceeds)
    cost = D(asset.acquisition_cost)
    accum = D(asset.accumulated_depreciation)
    nbv = cost - accum
    gain_loss = proceeds - nbv            # + gain, - loss

    entries = []
    if proceeds > 0:
        if not body.proceeds_account_id:
            raise HTTPException(400, "proceeds_account_id required when proceeds > 0")
        cash = session.get(Account, body.proceeds_account_id)
        if not cash or cash.tenant_id != user.tenant_id:
            raise HTTPException(400, "proceeds account not found")
        entries.append(EntryInput(account_id=cash.id, debit=proceeds))
    if accum > 0:
        entries.append(EntryInput(account_id=asset.accum_depr_account_id, debit=accum))
    entries.append(EntryInput(account_id=asset.asset_account_id, credit=cost))
    if gain_loss > 0:
        gain_acc = get_or_create_account(session, user.tenant_id, "4900", "Other Income", "Revenue")
        entries.append(EntryInput(account_id=gain_acc.id, credit=gain_loss))
    elif gain_loss < 0:
        loss_acc = get_or_create_account(session, user.tenant_id, "5900", "Other Expenses", "Expense")
        entries.append(EntryInput(account_id=loss_acc.id, debit=-gain_loss))

    txn = post_transaction(session, user, date=body.disposal_date,
                           description=f"Disposal of {asset.name}",
                           entries=entries, audit_entity_type="asset_disposal",
                           audit_detail={"asset_id": asset.id, "proceeds": str(proceeds),
                                         "gain_loss": str(gain_loss)})
    asset.is_disposed = True
    asset.book_value = D("0")
    asset.disposal_date = body.disposal_date
    asset.disposal_proceeds = proceeds
    asset.disposal_transaction_id = txn.id
    session.add(asset)
    log_audit(session, user, "UPDATE", "fixed_asset", asset_id, {"action": "disposed"})
    session.commit()
    return {"success": True, "jv_number": txn.jv_number, "gain_loss": str(gain_loss)}
```

Add imports at the top of `assets.py` if missing: `from pydantic import BaseModel`, `from typing import Optional`, `from decimal import Decimal as _D` (or reuse the file's `D`), `from models import Account`, `from routers.common import get_or_create_account`, `from services.posting import EntryInput, post_transaction`.

- [ ] **Step 4: Run — expect PASS**

Run: `cd backend && uv run pytest tests/test_asset_disposal.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/assets.py backend/tests/test_asset_disposal.py
git commit -m "feat(assets): IAS 16 disposal GL posting with gain/loss

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3.3: Frontend — disposal modal fields

**Files:**
- Modify: the assets page / disposal modal under `frontend/src/app/(dashboard)/assets/`

- [ ] **Step 1: Locate the dispose UI**

Run: `cd frontend && grep -rn "dispose" src/app/"(dashboard)"/assets/`
Read the file that calls the dispose endpoint.

- [ ] **Step 2: Add fields**

Replace the bare "Dispose" action with a small modal/form capturing **proceeds** (number, default 0), **receiving account** (`<select>` from `GET /api/accounts` filtered to cash/bank, shown only when proceeds > 0), and **disposal date** (date input, default today). Send them in the PATCH body: `{ proceeds, proceeds_account_id, disposal_date }`. Show the returned `gain_loss` in a success toast/line.

- [ ] **Step 3: Build check**

Run: `cd frontend && npm run lint && npm run build`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/"(dashboard)"/assets
git commit -m "feat(ui): asset disposal modal with proceeds + account + date

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 4 — Documentation

### Task 4.1: `docs/ACCOUNTING_RULES.md`

**Files:**
- Create: `docs/ACCOUNTING_RULES.md`

- [ ] **Step 1: Write the doc** with these sections (use real account codes from `db.py`):

1. **Ledger-Entry Matrices** — one Dr/Cr table each:
   - *Sales Return (Credit Note)*: value reversal `Dr 4000 Revenue + Dr 2200 GST Payable / Cr 1100 AR`; restock sub-JV `Dr 1200 Inventory / Cr 5010 COGS` at original layer cost. (Documents existing `credit_notes.py`.)
   - *Asset Disposal (IAS 16.71)*: `Dr Cash/Bank (proceeds) + Dr 1090 Accum Depr / Cr asset-cost`; balancing `Cr 4900 gain` or `Dr 5900 loss`; worked gain example + scrap (loss) example.
   - *FX Revaluation (IAS 21.23)*: AR gain `Dr 1100 / Cr 4901`; AR loss `Dr 4901 / Cr 1100`; AP loss `Dr 4901 / Cr 2000`; AP gain `Dr 2000 / Cr 4901`; note the next-month auto-reversal and same-date void.
   - *Stock Adjustments (IAS 2)*: loss/write-down `Dr 5040 / Cr 1200`; gain `Dr 1200 / Cr 5040`.
2. **ERP Parity Mapping** — the model-by-model table from the spec (Easy-Books ↔ Odoo 17 ↔ QBO), plus a short paragraph on how Easy-Books' single-`Transaction`/N-`JournalEntry` model maps onto Odoo's `account.move`/`account.move.line` and QBO's `JournalEntry.Line`, and how `PaymentAllocation` parallels Odoo reconciliation / QBO `LinkedTxn`.

- [ ] **Step 2: Commit**

```bash
git add docs/ACCOUNTING_RULES.md
git commit -m "docs: accounting ledger matrices + Odoo/QBO parity mapping

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4.2: Cross-link existing docs

**Files:**
- Modify: `BLUEPRINT.md`, `CLAUDE.md`, `README.md`

- [ ] **Step 1: BLUEPRINT.md** — in §11 add a line pointing to `docs/ACCOUNTING_RULES.md`; in §8 add the `POST /api/stock-adjustments`, `GET /api/stock-adjustments`, and the extended `PATCH /api/assets/{id}/dispose` + `POST /api/reports/fx-revaluation` (AR+AP) endpoints.

- [ ] **Step 2: CLAUDE.md** — add `routers/stock_adjustments.py` to the router table; add a line under the reports/services notes that FX revaluation now lives in `services/fx_revaluation.py` (AR+AP, auto-reversing) and asset disposal posts full IAS 16 GL.

- [ ] **Step 3: README.md** — add a one-line mention of stock adjustments + FX revaluation under features.

- [ ] **Step 4: Commit**

```bash
git add BLUEPRINT.md CLAUDE.md README.md
git commit -m "docs: reference stock adjustments, FX engine, disposal GL

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 5 — Demo Seed + Green Suite

### Task 5.1: Seed adjustments, a disposal, and open FX positions

**Files:**
- Modify: `backend/scripts/seed_demo.py`

- [ ] **Step 1: Add seed steps** in `seed_one_tenant` (guard to inventory-bearing models for stock adj; all models can take the FX positions):
   - For trader/manufacturing: create one EUR (or non-base) **open** invoice and one open bill, and seed an `ExchangeRate` for a later date so `/fx-revaluation` has something to act on.
   - For inventory-bearing models: call the stock-adjustment endpoint logic OR insert via the service: one `loss` and one `write_down` on an existing stock product.
   - For any model with a fixed asset: dispose one asset (proceeds < NBV → loss) so the disposal GL path is exercised in demo data.

Follow the existing helper style in `seed_demo.py` (the `_seed_*` functions). Keep it idempotent.

- [ ] **Step 2: Run the seeder against a scratch DB**

Run: `cd backend && rm -f /tmp/seedcheck.db && DATABASE_URL=sqlite:////tmp/seedcheck.db PYTHONPATH=. uv run python -m scripts.seed_demo`
Expected: completes without error.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed_demo.py
git commit -m "chore(seed): demo stock adjustments, asset disposal, open FX positions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5.2: Full suite green

- [ ] **Step 1: Run the whole backend suite**

Run: `cd backend && uv run pytest`
Expected: all green (the pre-existing 165 + the new FX/stock/disposal tests). Fix any regressions before proceeding.

- [ ] **Step 2: Frontend build**

Run: `cd frontend && npm run lint && npm run build`
Expected: clean.

- [ ] **Step 3: Final commit (if any fixups)**

```bash
git add -A
git commit -m "test: green suite after accounting-correctness feature

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** Component A → Phase 1 (Tasks 1.1–1.3); Component B → Phase 2 (2.1–2.4); Component C → Phase 3 (3.1–3.3); Component D → Phase 4 (4.1–4.2); Component E → Phase 5 (5.1–5.2). All five components covered. Sales-return matrix is documentation-only (Task 4.1) — matches spec finding that `credit_notes.py` already implements it.
- **Placeholder scan:** no TBD/TODO; every code step shows real code; the few "confirm field name" notes point at concrete files for the implementer to verify, not blanks.
- **Type consistency:** `revalue_open_positions`, `RevaluationResult`, `FxRevaluationRun`, `adjust_loss/adjust_gain/write_down`, `_deplete_layers`, `StockAdjustment`, `DisposeIn` used consistently across tasks and tests. Account codes (4901/4900/5900/5040/1200/5010/1100/2000/1090) match `db.py`.
- **Known verification points (flagged inline for implementer):** `EntryInput.normalised()` field exposure; `Invoice.ar_account_id`/`Bill.ap_account_id` (verified at design time); settings model name + `block_negative_stock` location; `POST /api/assets` required fields. None block the plan; each has a stated fallback.
