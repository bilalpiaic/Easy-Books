# #42 Telecom Stock & Issuance Table — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-RSO Stock & Issuance report (backend endpoint + telecom-dashboard table) with a franchise-level totals footer carrying the FCA figures.

**Architecture:** A new read-only endpoint `GET /api/telecom/reports/stock-issuance` aggregates per-RSO stock/load/SIM issuance, deposits, and a receivable closing from the `tc_*` tables, plus franchise FCA totals; the telecom dashboard page renders it as a date-filtered table with a TOTAL footer.

**Tech Stack:** FastAPI + SQLModel/SQLAlchemy (backend), pytest; Next.js 16 / React 19 / TypeScript / Tailwind (frontend).

**Spec:** `docs/superpowers/specs/2026-06-11-issue42-telecom-stock-issuance-design.md`

**Run commands from:** backend `cd backend && PYTHONPATH=. uv run pytest ...`; frontend `cd frontend && npm run build && npm run lint`.

---

## File structure

| File | Responsibility | Task |
|------|----------------|------|
| `backend/routers/telecom_reports.py` | **Modify.** Add `RsoStockIssue` import + the `/stock-issuance` handler | 1 |
| `backend/tests/test_telecom_stock_issuance.py` | **Create.** Aggregation, footer, period-filter, tenant-isolation tests | 1 |
| `frontend/src/app/(dashboard)/telecom/page.tsx` | **Modify.** Add the Stock & Issuance `Section` (date filter + table + footer) | 2 |

---

## Task 1: Backend endpoint `/stock-issuance` + tests

**Files:**
- Modify: `backend/routers/telecom_reports.py` (import line ~19-22; add handler near the other RSO endpoints)
- Create: `backend/tests/test_telecom_stock_issuance.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_telecom_stock_issuance.py`:

```python
"""#42 Telecom Stock & Issuance report — per-RSO aggregation + franchise FCA footer."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import User
from models_telecom import (
    FcaEvent, LoadTransfer, RsoAgent, RsoDailyCollection, RsoStockIssue,
)


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    app.state.engine = engine
    app.dependency_overrides[get_session] = _override
    c = TestClient(app)
    yield c, engine
    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _signup(c, email, model="telecom_franchise"):
    c.post("/api/auth/signup", json={
        "email": email, "password": "password123", "full_name": "U",
        "company_name": "Telco", "business_model": model,
    })
    tok = c.post("/api/auth/login", data={
        "username": email, "password": "password123",
    }).json()["access_token"]
    c.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def _tenant_id(engine, email):
    with Session(engine) as s:
        return s.exec(select(User).where(User.email == email)).first().tenant_id


def test_stock_issuance_aggregates_and_footer(client):
    c, engine = client
    auth = _signup(c, "tel@t.test")
    tid = _tenant_id(engine, "tel@t.test")
    with Session(engine) as s:
        r1 = RsoAgent(tenant_id=tid, name="Ahmed", territory="North")
        r2 = RsoAgent(tenant_id=tid, name="Bilal", territory="South")
        s.add(r1); s.add(r2); s.commit(); s.refresh(r1); s.refresh(r2)
        # r1: scratch 12000, sim_batch 5000 (qty 50), bundle 1200
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r1.id, issue_date="2026-03-10", stock_type="scratch_card", stock_ref_id=1, qty_issued=120, face_value=12000))
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r1.id, issue_date="2026-03-10", stock_type="sim_batch", stock_ref_id=2, qty_issued=50, face_value=5000))
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r1.id, issue_date="2026-03-10", stock_type="bundle", stock_ref_id=3, qty_issued=10, face_value=1200))
        # r2: scratch 9500, imsi 3000 (qty 30)
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r2.id, issue_date="2026-03-11", stock_type="scratch_card", stock_ref_id=4, qty_issued=95, face_value=9500))
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r2.id, issue_date="2026-03-11", stock_type="imsi", stock_ref_id=5, qty_issued=30, face_value=3000))
        # load transfers msr->rso
        s.add(LoadTransfer(tenant_id=tid, transfer_date="2026-03-10", from_type="msr", from_ref_id=1, to_type="rso", to_ref_id=r1.id, amount=8000))
        s.add(LoadTransfer(tenant_id=tid, transfer_date="2026-03-11", from_type="msr", from_ref_id=1, to_type="rso", to_ref_id=r2.id, amount=6200))
        # daily collections (bank deposits)
        s.add(RsoDailyCollection(tenant_id=tid, rso_id=r1.id, collection_date="2026-03-12", total_deposited=9800))
        s.add(RsoDailyCollection(tenant_id=tid, rso_id=r2.id, collection_date="2026-03-12", total_deposited=6200))
        # FCA events (franchise-level): 3
        s.add(FcaEvent(tenant_id=tid, event_date="2026-03-12", msisdn="0300", source_channel="rso_retail"))
        s.add(FcaEvent(tenant_id=tid, event_date="2026-03-12", msisdn="0301", source_channel="counter"))
        s.add(FcaEvent(tenant_id=tid, event_date="2026-03-13", msisdn="0302", source_channel="rso_retail"))
        s.commit()

    data = c.get("/api/telecom/reports/stock-issuance", headers=auth).json()
    rows = {r["name"]: r for r in data["items"]}
    a = rows["Ahmed"]
    assert Decimal(a["stock_issuance"]) == Decimal("12000")
    assert Decimal(a["load_issued"]) == Decimal("8000")
    assert Decimal(a["hlr_issued"]) == Decimal("5000")
    assert a["sim_issued_qty"] == 50
    assert Decimal(a["other_stock"]) == Decimal("1200")
    assert Decimal(a["bank_deposits"]) == Decimal("9800")
    assert Decimal(a["closing_hlr_load_dep"]) == Decimal("3200")  # 5000+8000-9800
    assert a["fca_hits"] is None
    assert a["closing_sim_fca"] is None

    t = data["totals"]
    assert t["sim_issued_qty"] == 80          # 50 + 30
    assert t["fca_hits"] == 3
    assert t["closing_sim_fca"] == 77         # 80 - 3
    assert Decimal(t["hlr_issued"]) == Decimal("8000")
    assert Decimal(t["load_issued"]) == Decimal("14200")
    assert Decimal(t["bank_deposits"]) == Decimal("16000")
    assert Decimal(t["closing_hlr_load_dep"]) == Decimal("6200")  # 8000+14200-16000


def test_stock_issuance_period_filter(client):
    c, engine = client
    auth = _signup(c, "per@t.test")
    tid = _tenant_id(engine, "per@t.test")
    with Session(engine) as s:
        r = RsoAgent(tenant_id=tid, name="Cee"); s.add(r); s.commit(); s.refresh(r)
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r.id, issue_date="2026-01-05", stock_type="scratch_card", stock_ref_id=1, qty_issued=10, face_value=1000))
        s.add(RsoStockIssue(tenant_id=tid, rso_id=r.id, issue_date="2026-03-05", stock_type="scratch_card", stock_ref_id=2, qty_issued=20, face_value=2000))
        s.add(FcaEvent(tenant_id=tid, event_date="2026-01-09", msisdn="x", source_channel="counter"))
        s.add(FcaEvent(tenant_id=tid, event_date="2026-03-09", msisdn="y", source_channel="counter"))
        s.commit()
    data = c.get("/api/telecom/reports/stock-issuance?start=2026-03-01&end=2026-03-31", headers=auth).json()
    assert Decimal(data["items"][0]["stock_issuance"]) == Decimal("2000")  # March only
    assert data["totals"]["fca_hits"] == 1                                  # March FCA only
    assert data["period"] == {"start": "2026-03-01", "end": "2026-03-31"}


def test_stock_issuance_tenant_isolation(client):
    c, engine = client
    auth_a = _signup(c, "a@t.test")
    _signup(c, "b@t.test")
    tid_b = _tenant_id(engine, "b@t.test")
    with Session(engine) as s:
        rb = RsoAgent(tenant_id=tid_b, name="OtherTenantRSO"); s.add(rb); s.commit(); s.refresh(rb)
        s.add(RsoStockIssue(tenant_id=tid_b, rso_id=rb.id, issue_date="2026-03-01", stock_type="scratch_card", stock_ref_id=1, qty_issued=5, face_value=500))
        s.add(FcaEvent(tenant_id=tid_b, event_date="2026-03-01", msisdn="z", source_channel="counter"))
        s.commit()
    data = c.get("/api/telecom/reports/stock-issuance", headers=auth_a).json()
    assert data["items"] == []            # tenant A has no RSOs
    assert data["totals"]["fca_hits"] == 0  # tenant B's FCA not counted
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_telecom_stock_issuance.py -q`
Expected: FAIL — the endpoint returns 404 (route not found), so `data["items"]`/`data["totals"]` raise `KeyError`.

- [ ] **Step 3: Add the `RsoStockIssue` import**

In `backend/routers/telecom_reports.py`, the `from models_telecom import (...)` block (around lines 19-22) does not include `RsoStockIssue`. Add it (keep alphabetical-ish grouping):

```python
from models_telecom import (
    CommissionLine, CommissionStatement, FcaEvent, KpiTarget, LoadTransfer,
    MobileMoneyAccount, PostpaidBillCycle, RsoAgent, RsoDailyCollection,
    RsoStockIssue, SimActivation, SimBatch, TrackerAccount, TrackerTransaction,
)
```

- [ ] **Step 4: Implement the handler**

Append to `backend/routers/telecom_reports.py` (after the `/rso-ledger` handler is a natural home):

```python
@router.get("/stock-issuance")
def stock_issuance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    """Per-RSO stock & issuance report (#42). One row per RSO agent; FCA is
    franchise-level (tc_fca_event has no rso_id) so it appears only in totals.
    Covers the MSR->channel->bank segment of the franchise load/stock chain."""
    tid = user.tenant_id

    def _between(col):
        conds = []
        if start:
            conds.append(col >= start)
        if end:
            conds.append(col <= end)
        return conds

    def _sum(model, value_col, *extra):
        return session.exec(
            select(func.coalesce(func.sum(value_col), 0)).where(
                model.tenant_id == tid, *extra,
            )
        ).one()

    rsos = session.exec(select(RsoAgent).where(RsoAgent.tenant_id == tid)).all()

    items = []
    tot_stock = tot_load = tot_hlr = tot_other = tot_dep = ZERO
    tot_sim = 0
    for r in rsos:
        sim_types = RsoStockIssue.stock_type.in_(("sim_batch", "imsi"))
        stock = _sum(RsoStockIssue, RsoStockIssue.face_value,
                     RsoStockIssue.rso_id == r.id,
                     RsoStockIssue.stock_type == "scratch_card",
                     *_between(RsoStockIssue.issue_date))
        load = _sum(LoadTransfer, LoadTransfer.amount,
                    LoadTransfer.to_type == "rso", LoadTransfer.to_ref_id == r.id,
                    *_between(LoadTransfer.transfer_date))
        hlr = _sum(RsoStockIssue, RsoStockIssue.face_value,
                   RsoStockIssue.rso_id == r.id, sim_types,
                   *_between(RsoStockIssue.issue_date))
        sim_qty = _sum(RsoStockIssue, RsoStockIssue.qty_issued,
                       RsoStockIssue.rso_id == r.id, sim_types,
                       *_between(RsoStockIssue.issue_date))
        other = _sum(RsoStockIssue, RsoStockIssue.face_value,
                     RsoStockIssue.rso_id == r.id,
                     RsoStockIssue.stock_type == "bundle",
                     *_between(RsoStockIssue.issue_date))
        dep = _sum(RsoDailyCollection, RsoDailyCollection.total_deposited,
                   RsoDailyCollection.rso_id == r.id,
                   *_between(RsoDailyCollection.collection_date))

        stock_d, load_d, hlr_d, other_d, dep_d = D(stock), D(load), D(hlr), D(other), D(dep)
        sim_i = int(sim_qty)
        items.append({
            "rso_id": r.id, "name": r.name, "territory": r.territory,
            "stock_issuance": str(stock_d), "load_issued": str(load_d),
            "hlr_issued": str(hlr_d), "sim_issued_qty": sim_i,
            "other_stock": str(other_d), "bank_deposits": str(dep_d),
            "closing_hlr_load_dep": str(hlr_d + load_d - dep_d),
            "fca_hits": None, "closing_sim_fca": None,
        })
        tot_stock += stock_d; tot_load += load_d; tot_hlr += hlr_d
        tot_other += other_d; tot_dep += dep_d; tot_sim += sim_i

    fca_count = session.exec(
        select(func.coalesce(func.count(FcaEvent.id), 0)).where(
            FcaEvent.tenant_id == tid, *_between(FcaEvent.event_date),
        )
    ).one()
    fca = int(fca_count)

    totals = {
        "stock_issuance": str(tot_stock), "load_issued": str(tot_load),
        "hlr_issued": str(tot_hlr), "sim_issued_qty": tot_sim,
        "other_stock": str(tot_other), "bank_deposits": str(tot_dep),
        "closing_hlr_load_dep": str(tot_hlr + tot_load - tot_dep),
        "fca_hits": fca, "closing_sim_fca": tot_sim - fca,
    }
    return {"items": items, "totals": totals, "period": {"start": start, "end": end}}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_telecom_stock_issuance.py -q`
Expected: PASS (3 tests). If a money assertion fails on format, confirm the test uses `Decimal(...)` comparison (it does) — not string equality.

- [ ] **Step 6: Run the full backend suite (no regressions)**

Run: `cd backend && PYTHONPATH=. uv run pytest -q`
Expected: all pass (prior count 361 + 3 new = 364).

- [ ] **Step 7: Commit**

```bash
git add backend/routers/telecom_reports.py backend/tests/test_telecom_stock_issuance.py
git commit -m "feat(telecom): per-RSO stock & issuance report endpoint (#42)"
```

---

## Task 2: Frontend Stock & Issuance section

**Files:**
- Modify: `frontend/src/app/(dashboard)/telecom/page.tsx`

- [ ] **Step 1: Add the response interfaces**

After the `RevenueResp` interface (around line 27) add:

```tsx
interface StockRow {
  rso_id: number; name: string; territory: string | null
  stock_issuance: string; load_issued: string; hlr_issued: string
  sim_issued_qty: number; other_stock: string; bank_deposits: string
  closing_hlr_load_dep: string; fca_hits: number | null; closing_sim_fca: number | null
}
interface StockTotals {
  stock_issuance: string; load_issued: string; hlr_issued: string
  sim_issued_qty: number; other_stock: string; bank_deposits: string
  closing_hlr_load_dep: string; fca_hits: number; closing_sim_fca: number
}
interface StockResp { items: StockRow[]; totals: StockTotals; period: { start: string | null; end: string | null } }
```

- [ ] **Step 2: Add state + a date-driven fetch**

Inside `TelecomDashboardPage`, after the existing `const [error, setError] = ...` (line 32) add:

```tsx
  const [stock, setStock] = useState<StockResp | null>(null)
  const [siStart, setSiStart] = useState("")
  const [siEnd, setSiEnd] = useState("")

  useEffect(() => {
    const qs = new URLSearchParams()
    if (siStart) qs.set("start", siStart)
    if (siEnd) qs.set("end", siEnd)
    apiFetch<StockResp>(`/api/telecom/reports/stock-issuance${qs.toString() ? `?${qs}` : ""}`)
      .then(setStock)
      .catch(() => {})
  }, [siStart, siEnd])
```

- [ ] **Step 3: Render the section**

Insert this `<Section>` immediately BEFORE the `<Section title="Jump to">` block (around line 136). It reuses the imported `money()` and `Section` primitives:

```tsx
      <Section title="Stock & Issuance (per RSO)">
        <div className="flex flex-wrap items-end gap-3 mb-3">
          <label className="text-xs text-[#1a1814]/60">
            From
            <input type="date" value={siStart} onChange={e => setSiStart(e.target.value)}
              className="block mt-1 px-2 py-1 border border-[#ede9e2] rounded-lg text-sm" />
          </label>
          <label className="text-xs text-[#1a1814]/60">
            To
            <input type="date" value={siEnd} onChange={e => setSiEnd(e.target.value)}
              className="block mt-1 px-2 py-1 border border-[#ede9e2] rounded-lg text-sm" />
          </label>
          {(siStart || siEnd) && (
            <button onClick={() => { setSiStart(""); setSiEnd("") }}
              className="text-xs text-[#b8943f] hover:underline">Clear</button>
          )}
        </div>
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-x-auto">
          <table className="w-full text-sm min-w-[920px]">
            <thead className="bg-[#f6f3ee] text-[10px] uppercase tracking-widest text-[#1a1814]/60">
              <tr>
                <th className="px-3 py-2 text-left">RSO</th>
                <th className="px-3 py-2 text-right">Stock Iss.</th>
                <th className="px-3 py-2 text-right">Load Iss.</th>
                <th className="px-3 py-2 text-right">HLR Iss.</th>
                <th className="px-3 py-2 text-right">Other Stock</th>
                <th className="px-3 py-2 text-right">SIM Iss.</th>
                <th className="px-3 py-2 text-right">Bank Dep.</th>
                <th className="px-3 py-2 text-right">FCA Hits</th>
                <th className="px-3 py-2 text-right">Closing (SIM−FCA)</th>
                <th className="px-3 py-2 text-right">Closing (HLR+Load−Dep)</th>
              </tr>
            </thead>
            <tbody>
              {(stock?.items ?? []).map(r => (
                <tr key={r.rso_id} className="border-t border-[#ede9e2]">
                  <td className="px-3 py-2">{r.name}{r.territory ? ` · ${r.territory}` : ""}</td>
                  <td className="px-3 py-2 text-right">{money(r.stock_issuance)}</td>
                  <td className="px-3 py-2 text-right">{money(r.load_issued)}</td>
                  <td className="px-3 py-2 text-right">{money(r.hlr_issued)}</td>
                  <td className="px-3 py-2 text-right">{money(r.other_stock)}</td>
                  <td className="px-3 py-2 text-right">{r.sim_issued_qty}</td>
                  <td className="px-3 py-2 text-right">{money(r.bank_deposits)}</td>
                  <td className="px-3 py-2 text-right text-[#1a1814]/35">—</td>
                  <td className="px-3 py-2 text-right text-[#1a1814]/35">—</td>
                  <td className="px-3 py-2 text-right">{money(r.closing_hlr_load_dep)}</td>
                </tr>
              ))}
              {stock && stock.items.length === 0 && (
                <tr><td className="px-4 py-6 text-center text-[#1a1814]/50" colSpan={10}>No RSO activity for this period.</td></tr>
              )}
            </tbody>
            {stock && stock.items.length > 0 && (
              <tfoot>
                <tr className="border-t-2 border-[#b8943f]/30 bg-[#faf6ec] font-bold">
                  <td className="px-3 py-2">TOTAL</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.stock_issuance)}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.load_issued)}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.hlr_issued)}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.other_stock)}</td>
                  <td className="px-3 py-2 text-right">{stock.totals.sim_issued_qty}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.bank_deposits)}</td>
                  <td className="px-3 py-2 text-right">{stock.totals.fca_hits}</td>
                  <td className="px-3 py-2 text-right">{stock.totals.closing_sim_fca}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.closing_hlr_load_dep)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </Section>
```

- [ ] **Step 2 note — verify the `money` helper accepts a string.** It already does (`money(data?.tracker.deposit_balance)` etc. in this file pass `string | undefined`). No import change needed; `Section` and `money` are already imported from `@/components/telecom/primitives`.

- [ ] **Step 4: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green (telecom route compiles). Lint clean on `telecom/page.tsx` — confirm no unused-var or hooks warnings introduced (the new `useEffect` deps `[siStart, siEnd]` are complete).

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(dashboard)/telecom/page.tsx"
git commit -m "feat(telecom): Stock & Issuance table on telecom dashboard (#42)"
```

---

## Self-review (completed at write time)

- **Spec coverage:** Unit 1 (endpoint, per-RSO mapping, totals footer with franchise FCA, period filter, string money) → Task 1 Steps 3-4; tests for aggregation/footer/period/isolation → Task 1 Step 1. Unit 2 (date filter + 10-col table + TOTAL footer, `—` for per-RSO FCA) → Task 2. Workflow context (MSR→channel→bank→FCA) informs the column semantics; no separate task needed.
- **Type consistency:** endpoint returns `{items, totals, period}` with fields `stock_issuance/load_issued/hlr_issued/sim_issued_qty/other_stock/bank_deposits/closing_hlr_load_dep/fca_hits/closing_sim_fca`; the frontend `StockRow`/`StockTotals` interfaces match exactly; `fca_hits`/`closing_sim_fca` are `number | null` per-row and `number` in totals, matching the handler (`None` per row, `int` in totals).
- **No placeholders:** full endpoint, full test, full frontend section all inline. The `_sum`/`_between` helpers are defined in Step 4.
- **Money-format robustness:** tests compare with `Decimal(...)` (not string equality) because `D()` is non-quantized; verified against `services/money.py`.
