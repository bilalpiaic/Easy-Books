# #52 §3 — User-customizable Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each user reorder and show/hide the existing dashboard blocks, with the layout persisted per-user server-side.

**Architecture:** A new per-user `UserDashboardLayout` KV table stores an opaque JSON layout blob (`GET/PUT /api/dashboard/layout`). The frontend owns a `WIDGET_REGISTRY` (the existing blocks lifted into render functions), a pure `resolveLayout(registry, saved)` merge, a `useDashboardLayout` hook, and a `<DashboardCanvas>` that renders ordered visible widgets and hosts a `@dnd-kit` Customize mode (save-on-Done).

**Tech Stack:** FastAPI + SQLModel + Alembic (backend); Next.js 16 / React 19 / TypeScript + `@dnd-kit` (frontend).

**Spec:** `docs/superpowers/specs/2026-06-12-issue52-3-customizable-dashboard-design.md`

---

## File Structure

**New:**
- `backend/models.py` → add `UserDashboardLayout` table
- `backend/routers/dashboard_layout.py` → `GET`/`PUT /api/dashboard/layout`
- `backend/main.py` → import + mount the router
- `backend/alembic/versions/dashlayout01_user_dashboard_layout.py` → guarded table
- `backend/tests/test_dashboard_layout.py` → round-trip + per-user/tenant isolation
- `frontend/src/lib/dashboardWidgets.tsx` → data interfaces + `WidgetContext` + `WidgetDef` + `WIDGET_REGISTRY` + small presentational helpers
- `frontend/src/hooks/useDashboardLayout.ts` → `resolveLayout` (pure) + hook
- `frontend/src/components/dashboard/DashboardCanvas.tsx` → canvas + Customize mode

**Modified:**
- `frontend/src/app/(dashboard)/dashboard/page.tsx` → slim to fetch + build `ctx` + `<DashboardCanvas>`
- `frontend/package.json` → add `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`

---

## Task 1: Backend per-user layout store

**Files:**
- Modify: `backend/models.py` (append a table near the other tables)
- Create: `backend/routers/dashboard_layout.py`
- Modify: `backend/main.py` (import + `_ROUTERS` list)
- Create: `backend/alembic/versions/dashlayout01_user_dashboard_layout.py`
- Test: `backend/tests/test_dashboard_layout.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_dashboard_layout.py`:

```python
"""#52 §3 — per-user dashboard layout store: round-trip + per-user/tenant isolation."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from auth import get_password_hash
from db import get_session
from main import app
from models import User


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


def _signup(c, email):
    """Signup creates a NEW tenant; first user is its owner. Returns Bearer headers."""
    c.post("/api/auth/signup", json={
        "email": email, "password": "password123", "full_name": "U", "company_name": "Co",
    })
    tok = c.post("/api/auth/login", data={
        "username": email, "password": "password123",
    }).json()["access_token"]
    c.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def _tenant_id(engine, email):
    with Session(engine) as s:
        return s.exec(select(User).where(User.email == email)).first().tenant_id


def _add_user_to_tenant(engine, email, tenant_id, role="accountant"):
    with Session(engine) as s:
        s.add(User(
            email=email, hashed_password=get_password_hash("password123"),
            full_name="Second", role=role, tenant_id=tenant_id, is_active=True,
        ))
        s.commit()


def _login(c, email):
    tok = c.post("/api/auth/login", data={
        "username": email, "password": "password123",
    }).json()["access_token"]
    c.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def test_layout_defaults_to_null_when_unset(client):
    c, engine = client
    auth = _signup(c, "a@t.test")
    r = c.get("/api/dashboard/layout", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"layout": None}


def test_layout_round_trips(client):
    c, engine = client
    auth = _signup(c, "a@t.test")
    payload = {"layout": {"version": 1, "widgets": [
        {"id": "primary_kpis", "visible": True},
        {"id": "ar_aging", "visible": False},
    ]}}
    put = c.put("/api/dashboard/layout", headers=auth, json=payload)
    assert put.status_code == 200, put.text
    got = c.get("/api/dashboard/layout", headers=auth).json()
    assert got["layout"] == payload["layout"]


def test_layout_per_user_isolation_same_tenant(client):
    """Two users in the SAME tenant must have independent layouts — guards
    against keying the store by tenant_id only (like the Settings table)."""
    c, engine = client
    auth_a = _signup(c, "owner@t.test")
    tid = _tenant_id(engine, "owner@t.test")
    _add_user_to_tenant(engine, "clerk@t.test", tid)
    auth_b = _login(c, "clerk@t.test")

    c.put("/api/dashboard/layout", headers=auth_a, json={"layout": {"version": 1, "widgets": [{"id": "primary_kpis", "visible": False}]}})

    # B in the same tenant is unaffected — still default.
    assert c.get("/api/dashboard/layout", headers=auth_b).json() == {"layout": None}
    # A keeps its own.
    assert c.get("/api/dashboard/layout", headers=auth_a).json()["layout"]["widgets"][0]["visible"] is False


def test_layout_tenant_isolation(client):
    c, engine = client
    auth_a = _signup(c, "a@t.test")
    auth_b = _signup(c, "b@t.test")
    c.put("/api/dashboard/layout", headers=auth_a, json={"layout": {"version": 1, "widgets": [{"id": "ar_aging", "visible": False}]}})
    assert c.get("/api/dashboard/layout", headers=auth_b).json() == {"layout": None}


def test_layout_rejects_non_object(client):
    c, engine = client
    auth = _signup(c, "a@t.test")
    r = c.put("/api/dashboard/layout", headers=auth, json={"layout": [1, 2, 3]})
    assert r.status_code == 422
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_dashboard_layout.py -q`
Expected: FAIL — 404 on `/api/dashboard/layout` (router not mounted yet).

- [ ] **Step 3: Add the model**

In `backend/models.py`, immediately after the `Settings` class (ends at the line `tenant: Tenant = Relationship(back_populates="settings")`, before `class Account`), add:

```python
class UserDashboardLayout(SQLModel, table=True):
    """Per-user dashboard layout (#52 §3). Opaque JSON blob — the widget
    registry and merge logic live in the frontend; the backend only stores
    and returns the string keyed by (tenant_id, user_id)."""
    tenant_id: int = Field(foreign_key="tenant.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    layout_json: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

(`datetime` and `Field` are already imported at the top of `models.py`.)

- [ ] **Step 4: Create the router**

Create `backend/routers/dashboard_layout.py`:

```python
"""Per-user dashboard layout store (#52 §3). The backend treats the layout as
an opaque JSON object — the widget registry + merge live in the frontend."""
import json
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from models import UserDashboardLayout

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class LayoutBody(BaseModel):
    layout: dict


@router.get("/layout")
def get_layout(session: SessionDep, user: CurrentUserDep):
    row = session.exec(
        select(UserDashboardLayout).where(
            UserDashboardLayout.tenant_id == user.tenant_id,
            UserDashboardLayout.user_id == user.id,
        )
    ).first()
    if row is None:
        return {"layout": None}
    try:
        return {"layout": json.loads(row.layout_json)}
    except (ValueError, TypeError):
        return {"layout": None}


@router.put("/layout")
def put_layout(session: SessionDep, user: CurrentUserDep, body: LayoutBody):
    # CurrentUserDep (not WriteUserDep): saving one's OWN dashboard layout is a
    # personal UI preference, so even viewer-role users may persist it.
    row = session.exec(
        select(UserDashboardLayout).where(
            UserDashboardLayout.tenant_id == user.tenant_id,
            UserDashboardLayout.user_id == user.id,
        )
    ).first()
    payload = json.dumps(body.layout)
    if row is None:
        row = UserDashboardLayout(
            tenant_id=user.tenant_id, user_id=user.id, layout_json=payload,
        )
        session.add(row)
    else:
        row.layout_json = payload
        row.updated_at = datetime.utcnow()
        session.add(row)
    session.commit()
    return {"ok": True}
```

- [ ] **Step 5: Mount the router in `main.py`**

In `backend/main.py`, add `dashboard_layout` to the `from routers import (...)` block (keep alphabetical-ish; place after `credit_notes,`):

```python
from routers import (
    accounts, admin, advances, aging, analytic_accounts, assets, attachments,
    audit, auth, backup, bank_accounts, bank_imports, bills, bom, budgets,
    credit_notes, dashboard_layout, debit_notes, deferred_revenue, exchange_rates, grn,
    imports, invoices, manufacturing_reports, payment_terms, payments, periods,
    product_categories, production_orders, products, purchase_orders, rate_plans,
    reconciliations, recurring, report_builder, reports, settings, stock_locations,
    subledger, tax_codes, telecom, telecom_reports, transactions, users, vendors,
)
```

Then add `dashboard_layout.router,` to the `_ROUTERS` list (place after `reports.router,`):

```python
    transactions.router, reports.router, dashboard_layout.router, imports.router,
```

- [ ] **Step 6: Create the Alembic migration**

Create `backend/alembic/versions/dashlayout01_user_dashboard_layout.py`:

```python
"""user dashboard layout

Revision ID: dashlayout01
Revises: e545b922a716
"""
from alembic import op
import sqlalchemy as sa

revision = "dashlayout01"
down_revision = "e545b922a716"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "userdashboardlayout"):
        op.create_table(
            "userdashboardlayout",
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), primary_key=True),
            sa.Column("layout_json", sa.String, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    op.drop_table("userdashboardlayout")
```

- [ ] **Step 7: Run the new tests to verify they pass**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_dashboard_layout.py -q`
Expected: PASS (5 passed).

- [ ] **Step 8: Run the full backend suite**

Run: `cd backend && PYTHONPATH=. uv run pytest -q`
Expected: all pass (369 total — 364 existing + 5 new).

- [ ] **Step 9: Verify the migration applies cleanly**

Run: `cd backend && PYTHONPATH=. uv run alembic upgrade head`
Expected: no error; `dashlayout01` becomes head (run `uv run alembic heads` to confirm).

- [ ] **Step 10: Commit**

```bash
git add backend/models.py backend/routers/dashboard_layout.py backend/main.py \
        backend/alembic/versions/dashlayout01_user_dashboard_layout.py \
        backend/tests/test_dashboard_layout.py
git commit -m "feat(dashboard): per-user layout store endpoint (#52 §3)"
```

---

## Task 2: Frontend widget registry (lift existing blocks)

**Goal:** Extract the existing dashboard blocks into a registry of render functions with **no behavior change**. This task does not touch `page.tsx` rendering yet beyond what's needed to compile; the registry is consumed in Task 4.

**Files:**
- Modify: `frontend/package.json` (add `@dnd-kit/*`)
- Create: `frontend/src/lib/dashboardWidgets.tsx`

- [ ] **Step 1: Install @dnd-kit**

Run: `cd frontend && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`
Expected: three packages added to `package.json` dependencies; no peer-dep errors.

- [ ] **Step 2: Create the registry file shell with shared types + helpers**

Create `frontend/src/lib/dashboardWidgets.tsx`. Start with the data interfaces and chart-config type (these are the single source of truth — `page.tsx` will import them in Task 4), the presentational helpers moved verbatim from the bottom of the current `page.tsx`, and the widget interfaces:

```tsx
import React from "react"
import Link from "next/link"
import { Bar, Doughnut, Line } from "react-chartjs-2"
import type { ChartOptions } from "chart.js"
import RecentTransactions from "@/components/RecentTransactions"
import type { AppSettings } from "@/context/SettingsContext"

// ── Shared data shapes (moved here from page.tsx; page now imports them) ──────
export interface ArAging {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
}
export interface DashboardSummary {
  total_revenue: number; total_expense: number; transaction_count: number
  ar_outstanding: number; ap_outstanding: number; overdue_invoices: number
  unpaid_bills: number; low_stock_items: number; cash_balance: number
  ar_aging: ArAging | null; ap_due_week: number
}
export interface DashboardData { summary: DashboardSummary }
export interface ChartData {
  monthly: { month: string; revenue: number; expenses: number; profit: number }[]
  expense_breakdown: { account: string; amount: number }[]
  top_customers: { name: string; total: number }[]
}

// chart.js configs + options computed once in page.tsx and passed down
export interface DashboardChartConfigs {
  barData: { labels: string[]; datasets: object[] }
  lineData: { labels: string[]; datasets: object[] }
  doughnutData: { labels: string[]; datasets: object[] }
  customerBarData: { labels: string[]; datasets: object[] }
  agingBarData: { labels: string[]; datasets: { data: number[]; backgroundColor: string[]; borderRadius: number }[] }
  baseChartOpts: ChartOptions<"bar">
  lineOpts: ChartOptions<"line">
  doughnutOpts: ChartOptions<"doughnut">
}

export interface WidgetContext {
  data: DashboardData | null
  charts: ChartData | null
  s: DashboardSummary | undefined
  netProfit: number
  margin: string | null
  fmt: (n: number) => string
  agingLabels: string[]
  agingValues: number[] | null
  chartConfigs: DashboardChartConfigs
  settings: AppSettings
  reloadSettings: () => void
  checklistDismissed: boolean
  setChecklistDismissed: (v: boolean) => void
}

export interface WidgetDef {
  id: string
  title: string
  defaultVisible: boolean
  conditional?: boolean
  render: (ctx: WidgetContext) => React.ReactNode
}

// ── Presentational helpers (moved verbatim from page.tsx bottom) ──────────────
export function ChartSkeleton() {
  return <div className="h-full w-full shimmer rounded-lg" />
}

interface PrimaryKpiProps {
  label: string; value: string | null; icon: React.ElementType
  bg: string; border: string; text: string; sub?: string; compact?: boolean
}
export function PrimaryKpi({ label, value, icon: Icon, bg, border, text, sub, compact }: PrimaryKpiProps) {
  // ⟵ paste the EXACT body of PrimaryKpi from the current page.tsx (lines ~422-435)
}

interface SecondaryKpiProps {
  label: string; value: string | null; icon: React.ElementType; color: string
  href: string; badge?: { count: number; label: string; color: string }; valueClass?: string
}
export function SecondaryKpi({ label, value, icon: Icon, color, href, badge, valueClass }: SecondaryKpiProps) {
  // ⟵ paste the EXACT body of SecondaryKpi from the current page.tsx (lines ~441-452)
}
```

**Implementer note:** copy the `PrimaryKpi`, `SecondaryKpi`, and `ChartSkeleton` function bodies **verbatim** from the bottom of the current `frontend/src/app/(dashboard)/dashboard/page.tsx`. Add the `lucide-react` icon imports they need at the top of this file: `TrendingUp, TrendingDown, Hash, Wallet, ArrowDownLeft, ArrowUpRight, Clock, Package, AlertTriangle, FileSignature, Receipt, Banknote, CalendarClock`.

- [ ] **Step 3: Define the constants the widgets need**

Below the helpers, add the constants currently at the top of `page.tsx` (`ONBOARDING_STEPS`, `QUICK_ACTIONS`) — copy them **verbatim**:

```tsx
const ONBOARDING_STEPS = [
  { key: "company_profile", label: "Upload company logo",     href: "/settings#company" },
  { key: "first_customer",  label: "Add your first customer", href: "/customers" },
  { key: "payment_terms",   label: "Set up payment terms",    href: "/settings#payment-terms" },
  { key: "first_invoice",   label: "Create your first invoice", href: "/invoices" },
  { key: "first_bill",      label: "Record your first bill",  href: "/bills" },
]

const QUICK_ACTIONS = [
  { label: "New Invoice",    href: "/invoices", icon: FileSignature, color: "text-green-600" },
  { label: "New Bill",       href: "/bills",    icon: Receipt,       color: "text-orange-600" },
  { label: "New Entry",      href: "/entry",    icon: Hash,          color: "text-blue-600" },
  { label: "Products",       href: "/products", icon: Package,       color: "text-purple-600" },
  { label: "Workflow Guide", href: "/workflow", icon: TrendingUp,    color: "text-[#b8943f]" },
  { label: "User Guide",     href: "/guide",    icon: Wallet,        color: "text-[#1a1814]" },
]
```

- [ ] **Step 4: Build the registry by lifting each block**

Add `WIDGET_REGISTRY`. Each `render` returns the **exact JSX block** from the current `page.tsx`, with these mechanical substitutions:
- `s` → `ctx.s`, `data` → `ctx.data`, `charts` → `ctx.charts`, `fmt` → `ctx.fmt`, `netProfit` → `ctx.netProfit`, `margin` → `ctx.margin`, `settings` → `ctx.settings`, `reloadSettings` → `ctx.reloadSettings`, `checklistDismissed` → `ctx.checklistDismissed`, `setChecklistDismissed` → `ctx.setChecklistDismissed`, `agingLabels` → `ctx.agingLabels`, `agingValues` → `ctx.agingValues`.
- chart configs `barData/lineData/doughnutData/customerBarData/agingBarData` → `ctx.chartConfigs.barData` etc.; `baseChartOpts/lineOpts/doughnutOpts` → `ctx.chartConfigs.baseChartOpts` etc.
- A conditional block that currently renders `{cond && (<JSX>)}` returns `cond ? <JSX> : null` instead.

```tsx
export const WIDGET_REGISTRY: WidgetDef[] = [
  {
    id: "quick_actions", title: "Quick Actions", defaultVisible: true,
    render: () => (
      // ⟵ the "Quick Actions — top toolbar" <div> block (page.tsx ~235-244)
    ),
  },
  {
    id: "onboarding", title: "Setup Checklist", defaultVisible: true, conditional: true,
    render: (ctx) => {
      // ⟵ the IIFE body of the "Onboarding checklist" block (page.tsx ~249-298),
      //    with settings→ctx.settings, checklistDismissed→ctx.checklistDismissed,
      //    setChecklistDismissed→ctx.setChecklistDismissed, reloadSettings→ctx.reloadSettings.
      //    Keep its early `return null` paths — that's the conditional behavior.
    },
  },
  {
    id: "primary_kpis", title: "Key Figures", defaultVisible: true,
    render: (ctx) => {
      const { s, fmt, netProfit, margin } = ctx
      return (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {/* ⟵ the five <PrimaryKpi .../> from page.tsx ~302-306, s→passed locals */}
        </div>
      )
    },
  },
  {
    id: "secondary_kpis", title: "Receivables / Payables", defaultVisible: true,
    render: (ctx) => (
      // ⟵ the "Secondary metrics" grid block (page.tsx ~310-316), s→ctx.s, fmt→ctx.fmt
    ),
  },
  {
    id: "ar_aging", title: "AR Aging", defaultVisible: true, conditional: true,
    render: (ctx) => ctx.s?.ar_aging ? (
      // ⟵ the "AR Aging Mini-Chart" block INNER JSX (page.tsx ~320-346),
      //    agingBarData→ctx.chartConfigs.agingBarData, agingLabels→ctx.agingLabels,
      //    agingValues→ctx.agingValues, fmt→ctx.fmt
    ) : null,
  },
  {
    id: "alerts", title: "Action Alerts", defaultVisible: true, conditional: true,
    render: (ctx) => (ctx.s && (ctx.s.overdue_invoices > 0 || ctx.s.low_stock_items > 0)) ? (
      // ⟵ the "Alert" block INNER JSX (page.tsx ~351-357), s→ctx.s
    ) : null,
  },
  {
    id: "monthly_rev_exp", title: "Monthly Revenue vs Expenses", defaultVisible: true,
    render: (ctx) => (
      <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">
        {/* ⟵ the LEFT card of "Charts row 1" (page.tsx ~362-373) WITHOUT the lg:col-span-2
              wrapper grid; charts→ctx.charts, barData→ctx.chartConfigs.barData,
              baseChartOpts→ctx.chartConfigs.baseChartOpts */}
      </div>
    ),
  },
  {
    id: "net_profit_trend", title: "Net Profit Trend", defaultVisible: true,
    render: (ctx) => (
      <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">
        {/* ⟵ the RIGHT card of "Charts row 1" (page.tsx ~374-379); charts→ctx.charts,
              lineData→ctx.chartConfigs.lineData, lineOpts→ctx.chartConfigs.lineOpts */}
      </div>
    ),
  },
  {
    id: "expense_breakdown", title: "Expense Breakdown", defaultVisible: true,
    render: (ctx) => (
      <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">
        {/* ⟵ the LEFT card of "Charts row 2" (page.tsx ~384-393); charts→ctx.charts,
              doughnutData→ctx.chartConfigs.doughnutData, doughnutOpts→ctx.chartConfigs.doughnutOpts */}
      </div>
    ),
  },
  {
    id: "top_customers", title: "Top Customers", defaultVisible: true,
    render: (ctx) => (
      <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm">
        {/* ⟵ the RIGHT card of "Charts row 2" (page.tsx ~394-403); charts→ctx.charts,
              customerBarData→ctx.chartConfigs.customerBarData, baseChartOpts→ctx.chartConfigs.baseChartOpts */}
      </div>
    ),
  },
  {
    id: "recent_transactions", title: "Recent Transactions", defaultVisible: true,
    render: () => <RecentTransactions />,
  },
]
```

**Note on the chart rows:** the current page wraps the two row-1 cards in `lg:grid-cols-3` (left card `lg:col-span-2`) and the two row-2 cards in `lg:grid-cols-2`. Because widgets now stack single-column, drop those wrapper grids — each card becomes a full-width widget. This is the intended single-column flow per the spec (no behavior loss; cards simply stack).

- [ ] **Step 5: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds (registry is not yet rendered by the page, but must type-check — `AppSettings` import resolves, no unused-symbol errors).

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/dashboardWidgets.tsx
git commit -m "feat(dashboard): widget registry from existing blocks + @dnd-kit (#52 §3)"
```

---

## Task 3: Layout hook + pure merge

**Files:**
- Create: `frontend/src/hooks/useDashboardLayout.ts`

- [ ] **Step 1: Create the hook file with `resolveLayout` + types**

Create `frontend/src/hooks/useDashboardLayout.ts`:

```ts
import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { WIDGET_REGISTRY, type WidgetDef } from "@/lib/dashboardWidgets"

export interface StoredWidget { id: string; visible: boolean }
export interface StoredLayout { version: number; widgets: StoredWidget[] }
export interface ResolvedWidget { def: WidgetDef; visible: boolean }

/** Merge a saved layout against the registry:
 *  - keep saved order, dropping unknown/duplicate ids
 *  - append any registry widget missing from saved (forward-compat) */
export function resolveLayout(registry: WidgetDef[], saved: StoredLayout | null): ResolvedWidget[] {
  const byId = new Map(registry.map(w => [w.id, w]))
  const result: ResolvedWidget[] = []
  const seen = new Set<string>()
  for (const sw of saved?.widgets ?? []) {
    const def = byId.get(sw.id)
    if (!def || seen.has(sw.id)) continue
    result.push({ def, visible: sw.visible })
    seen.add(sw.id)
  }
  for (const def of registry) {
    if (!seen.has(def.id)) result.push({ def, visible: def.defaultVisible })
  }
  return result
}

function toStored(list: ResolvedWidget[]): StoredLayout {
  return { version: 1, widgets: list.map(w => ({ id: w.def.id, visible: w.visible })) }
}

export interface UseDashboardLayout {
  widgets: ResolvedWidget[]
  loading: boolean
  dirty: boolean
  setOrder: (orderedIds: string[]) => void
  toggle: (id: string) => void
  reset: () => void
  reload: () => void
  save: () => Promise<void>
}

export function useDashboardLayout(): UseDashboardLayout {
  const [widgets, setWidgets] = useState<ResolvedWidget[]>(() => resolveLayout(WIDGET_REGISTRY, null))
  const [saved, setSaved] = useState<StoredLayout | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<{ layout: StoredLayout | null }>("/api/dashboard/layout")
      .then(r => { setSaved(r.layout); setWidgets(resolveLayout(WIDGET_REGISTRY, r.layout)) })
      .catch(() => {})            // keep registry default on failure
      .finally(() => setLoading(false))
  }, [])

  const setOrder = (orderedIds: string[]) => setWidgets(prev => {
    const byId = new Map(prev.map(w => [w.def.id, w]))
    return orderedIds.map(id => byId.get(id)).filter((w): w is ResolvedWidget => Boolean(w))
  })
  const toggle = (id: string) => setWidgets(prev => prev.map(w => w.def.id === id ? { ...w, visible: !w.visible } : w))
  const reset = () => setWidgets(resolveLayout(WIDGET_REGISTRY, null))
  const reload = () => setWidgets(resolveLayout(WIDGET_REGISTRY, saved))

  const save = async () => {
    const stored = toStored(widgets)
    await apiFetch("/api/dashboard/layout", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout: stored }),
    })
    setSaved(stored)
  }

  const baseline = saved ?? toStored(resolveLayout(WIDGET_REGISTRY, null))
  const dirty = JSON.stringify(toStored(widgets)) !== JSON.stringify(baseline)

  return { widgets, loading, dirty, setOrder, toggle, reset, reload, save }
}
```

- [ ] **Step 2: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds (hook not yet consumed, but type-checks).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useDashboardLayout.ts
git commit -m "feat(dashboard): useDashboardLayout hook + resolveLayout merge (#52 §3)"
```

---

## Task 4: DashboardCanvas (view mode) + slim the page

**Goal:** Render the resolved widgets through the registry — the dashboard looks identical to before, now driven by the registry/hook. No Customize mode yet.

**Files:**
- Create: `frontend/src/components/dashboard/DashboardCanvas.tsx`
- Modify: `frontend/src/app/(dashboard)/dashboard/page.tsx`

- [ ] **Step 1: Create the canvas (view-only for now)**

Create `frontend/src/components/dashboard/DashboardCanvas.tsx`:

```tsx
"use client"

import React from "react"
import type { WidgetContext } from "@/lib/dashboardWidgets"
import type { ResolvedWidget } from "@/hooks/useDashboardLayout"

export default function DashboardCanvas({ widgets, ctx }: {
  widgets: ResolvedWidget[]
  ctx: WidgetContext
}) {
  return (
    <div className="space-y-4">
      {widgets.filter(w => w.visible).map(w => (
        <React.Fragment key={w.def.id}>{w.def.render(ctx)}</React.Fragment>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Rewrite `page.tsx` to build `ctx` and render the canvas**

Replace `frontend/src/app/(dashboard)/dashboard/page.tsx` with the version below. It keeps every fetch and chart-config computation, removes the inline JSX blocks (now in the registry) and the moved helpers/constants, imports the shared interfaces from the registry, and renders `<DashboardCanvas>`:

```tsx
"use client"

import { useEffect, useState } from "react"
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Title, Tooltip, Legend, Filler,
  type ChartOptions,
} from "chart.js"
import { useFmt, useSettings } from "@/context/SettingsContext"
import { apiFetch } from "@/lib/api"
import DateRangePicker from "@/components/DateRangePicker"
import DashboardCanvas from "@/components/dashboard/DashboardCanvas"
import { useDashboardLayout } from "@/hooks/useDashboardLayout"
import {
  WIDGET_REGISTRY,
  type DashboardData, type ChartData, type WidgetContext, type DashboardChartConfigs,
} from "@/lib/dashboardWidgets"
import { Settings2 } from "lucide-react"
import CustomizeBar from "@/components/dashboard/CustomizeBar"

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Title, Tooltip, Legend, Filler
)

const DOUGHNUT_COLORS = [
  "#b8943f","#2563eb","#16a34a","#dc2626","#7c3aed",
  "#0891b2","#ea580c","#db2777","#65a30d",
]

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

export default function Dashboard() {
  const fmt = useFmt()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd]     = useState(range.end)
  const [data, setData]   = useState<DashboardData | null>(null)
  const [charts, setCharts] = useState<ChartData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { settings, reload: reloadSettings } = useSettings()
  const [checklistDismissed, setChecklistDismissed] = useState(false)

  const layout = useDashboardLayout()
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    setData(null)
    apiFetch<DashboardData>(`/api/reports/dashboard?start=${start}&end=${end}`)
      .then(d => { if (!d.summary) throw new Error("Invalid response"); setData(d) })
      .catch(err => setError((err as Error).message))
  }, [start, end])

  useEffect(() => {
    apiFetch<ChartData>("/api/reports/dashboard/charts?months=12")
      .then(setCharts)
      .catch(() => {})
  }, [])

  const s = data?.summary
  const netProfit = s ? s.total_revenue - s.total_expense : 0
  const margin = s && s.total_revenue > 0 ? (netProfit / s.total_revenue * 100).toFixed(1) : null

  const monthLabels = charts?.monthly.map(m => {
    const [y, mo] = m.month.split("-")
    return new Date(+y, +mo - 1).toLocaleString("default", { month: "short" })
  }) ?? []

  const barData = {
    labels: monthLabels,
    datasets: [
      { label: "Revenue",  data: charts?.monthly.map(m => m.revenue) ?? [],  backgroundColor: "rgba(22,163,74,0.75)",  borderRadius: 4 },
      { label: "Expenses", data: charts?.monthly.map(m => m.expenses) ?? [], backgroundColor: "rgba(220,38,38,0.70)", borderRadius: 4 },
    ],
  }
  const lineData = {
    labels: monthLabels,
    datasets: [{ label: "Net Profit", data: charts?.monthly.map(m => m.profit) ?? [], borderColor: "#b8943f", backgroundColor: "rgba(184,148,63,0.10)", pointBackgroundColor: "#b8943f", pointRadius: 4, tension: 0.4, fill: true }],
  }
  const doughnutData = {
    labels: charts?.expense_breakdown.map(e => e.account) ?? [],
    datasets: [{ data: charts?.expense_breakdown.map(e => e.amount) ?? [], backgroundColor: DOUGHNUT_COLORS, borderWidth: 2, borderColor: "#fff" }],
  }
  const customerBarData = {
    labels: charts?.top_customers.map(c => c.name.length > 14 ? c.name.slice(0, 12) + "…" : c.name) ?? [],
    datasets: [{ label: "Invoice Total", data: charts?.top_customers.map(c => c.total) ?? [], backgroundColor: "rgba(184,148,63,0.80)", borderRadius: 4 }],
  }

  const agingLabels = ["Current", "1–30d", "31–60d", "61–90d", "90d+"]
  const agingValues = s?.ar_aging
    ? [s.ar_aging.current, s.ar_aging["1_30"], s.ar_aging["31_60"], s.ar_aging["61_90"], s.ar_aging.over_90]
    : null
  const agingBarData = {
    labels: agingLabels,
    datasets: [{
      data: agingValues ?? [0, 0, 0, 0, 0],
      backgroundColor: [
        "rgba(22,163,74,0.78)", "rgba(234,179,8,0.78)", "rgba(249,115,22,0.78)",
        "rgba(239,68,68,0.82)", "rgba(185,28,28,0.88)",
      ],
      borderRadius: 4,
    }],
  }

  const baseChartOpts: ChartOptions<"bar"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmt(ctx.parsed.y as number) } } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmt(v as number) } },
    },
  }
  const lineOpts: ChartOptions<"line"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmt((ctx.parsed.y ?? 0) as number) } } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
      y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmt(v as number) } },
    },
  }
  const doughnutOpts: ChartOptions<"doughnut"> = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 12, padding: 8 } },
      tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.parsed)}` } },
    },
    cutout: "62%",
  }

  const chartConfigs: DashboardChartConfigs = {
    barData, lineData, doughnutData, customerBarData, agingBarData,
    baseChartOpts, lineOpts, doughnutOpts,
  }

  const ctx: WidgetContext = {
    data, charts, s, netProfit, margin, fmt,
    agingLabels, agingValues, chartConfigs,
    settings, reloadSettings, checklistDismissed, setChecklistDismissed,
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">Dashboard</h1>
          <p className="text-xs text-[#1a1814]/50 mt-0.5 font-medium tracking-wide uppercase">Financial Overview</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="bg-white border border-[#ede9e2] rounded-xl px-3 py-2 shadow-sm">
            <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
          </div>
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[#ede9e2] bg-white shadow-sm text-sm font-medium text-[#1a1814]/75 hover:border-[#b8943f]/40 transition-colors"
            >
              <Settings2 className="w-4 h-4 text-[#b8943f]" /> Customize
            </button>
          )}
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>}

      {editing ? (
        <CustomizeBar layout={layout} onDone={() => setEditing(false)} ctx={ctx} />
      ) : (
        <DashboardCanvas widgets={layout.widgets} ctx={ctx} />
      )}
    </div>
  )
}
```

**Note:** `CustomizeBar` is created in Task 5. For Task 4 to build standalone, temporarily render `<DashboardCanvas>` in both branches — i.e., replace the `editing ? ... : ...` ternary with just `<DashboardCanvas widgets={layout.widgets} ctx={ctx} />` and omit the `CustomizeBar`/`editing`/customize-button imports. Task 5 adds them back. (If executing Tasks 4+5 back-to-back, you may create `CustomizeBar` first and keep the ternary.)

- [ ] **Step 3: Verify the build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build succeeds; lint at repo baseline (2 errors / 14 warnings — all pre-existing). Watch for unused imports left in `page.tsx` after removing the blocks (e.g., `Link`, lucide icons now only used in the registry) — remove any that lint flags.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)/dashboard/page.tsx" frontend/src/components/dashboard/DashboardCanvas.tsx
git commit -m "feat(dashboard): registry-driven canvas; slim dashboard page (#52 §3)"
```

---

## Task 5: Customize mode (drag, toggle, tray, Done/Cancel/Reset)

**Files:**
- Create: `frontend/src/components/dashboard/CustomizeBar.tsx`
- Modify: `frontend/src/app/(dashboard)/dashboard/page.tsx` (wire `CustomizeBar` if Task 4 used the temporary single-branch render)

- [ ] **Step 1: Create `CustomizeBar` with @dnd-kit sortable + show/hide tray**

Create `frontend/src/components/dashboard/CustomizeBar.tsx`:

```tsx
"use client"

import React, { useState } from "react"
import {
  DndContext, closestCenter, PointerSensor, KeyboardSensor,
  useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,
  arrayMove, useSortable,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, Eye, EyeOff, Check, X, RotateCcw, Plus } from "lucide-react"
import type { WidgetContext } from "@/lib/dashboardWidgets"
import type { UseDashboardLayout } from "@/hooks/useDashboardLayout"

function SortableRow({ id, title, conditional, visible, onToggle, children }: {
  id: string; title: string; conditional?: boolean; visible: boolean
  onToggle: () => void; children: React.ReactNode
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 }
  return (
    <div ref={setNodeRef} style={style} className="border border-dashed border-[#b8943f]/40 rounded-xl bg-white/60">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[#ede9e2]">
        <button {...attributes} {...listeners} className="cursor-grab text-[#1a1814]/40 hover:text-[#1a1814]/70" aria-label={`Drag ${title}`}>
          <GripVertical className="w-4 h-4" />
        </button>
        <span className="text-sm font-semibold text-[#1a1814]/80">{title}</span>
        {conditional && <span className="text-[10px] text-[#1a1814]/40">(shows only when relevant)</span>}
        <button onClick={onToggle} className="ml-auto text-[#1a1814]/50 hover:text-[#b8943f]" aria-label={visible ? `Hide ${title}` : `Show ${title}`}>
          {visible ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
        </button>
      </div>
      <div className="p-3 pointer-events-none select-none opacity-90">{children}</div>
    </div>
  )
}

export default function CustomizeBar({ layout, onDone, ctx }: {
  layout: UseDashboardLayout
  onDone: () => void
  ctx: WidgetContext
}) {
  const { widgets, setOrder, toggle, reset, reload, save } = layout
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const visibleIds = widgets.filter(w => w.visible).map(w => w.def.id)
  const hidden = widgets.filter(w => !w.visible)

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id) return
    const oldIndex = visibleIds.indexOf(active.id as string)
    const newIndex = visibleIds.indexOf(over.id as string)
    const reorderedVisible = arrayMove(visibleIds, oldIndex, newIndex)
    // rebuild full order: visible widgets in new order, then hidden in their current order
    setOrder([...reorderedVisible, ...hidden.map(w => w.def.id)])
  }

  const handleDone = async () => {
    setSaving(true); setErr(null)
    try { await save(); onDone() }
    catch { setErr("Couldn't save layout. Please try again.") }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 bg-[#faf6ec] border border-[#b8943f]/30 rounded-xl px-3 py-2 sticky top-2 z-10">
        <span className="text-xs font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">Customizing dashboard</span>
        <span className="text-[11px] text-[#1a1814]/45">Drag to reorder · toggle the eye to show/hide</span>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={reset} className="inline-flex items-center gap-1 text-xs text-[#1a1814]/60 hover:text-[#1a1814] px-2 py-1">
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </button>
          <button onClick={() => { reload(); onDone() }} className="inline-flex items-center gap-1 text-xs text-[#1a1814]/60 hover:text-[#1a1814] px-2 py-1">
            <X className="w-3.5 h-3.5" /> Cancel
          </button>
          <button onClick={handleDone} disabled={saving} className="inline-flex items-center gap-1 text-xs font-semibold text-white bg-[#b8943f] hover:bg-[#a07f33] rounded-lg px-3 py-1.5 disabled:opacity-60">
            <Check className="w-3.5 h-3.5" /> {saving ? "Saving…" : "Done"}
          </button>
        </div>
      </div>

      {err && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-2 text-sm text-red-700">{err}</div>}

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={visibleIds} strategy={verticalListSortingStrategy}>
          <div className="space-y-3">
            {widgets.filter(w => w.visible).map(w => (
              <SortableRow
                key={w.def.id} id={w.def.id} title={w.def.title}
                conditional={w.def.conditional} visible={true}
                onToggle={() => toggle(w.def.id)}
              >
                {w.def.render(ctx)}
              </SortableRow>
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {hidden.length > 0 && (
        <div className="bg-white border border-[#ede9e2] rounded-xl p-3">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/45 mb-2">Hidden widgets</p>
          <div className="flex flex-wrap gap-2">
            {hidden.map(w => (
              <button key={w.def.id} onClick={() => toggle(w.def.id)}
                className="inline-flex items-center gap-1 text-xs border border-[#ede9e2] rounded-lg px-2.5 py-1.5 hover:border-[#b8943f]/40 text-[#1a1814]/70">
                <Plus className="w-3.5 h-3.5 text-[#b8943f]" /> {w.def.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Ensure `page.tsx` wires `CustomizeBar`**

If Task 4 used the temporary single-branch render, restore the ternary in `page.tsx` exactly as shown in Task 4 Step 2 (the `editing ? <CustomizeBar .../> : <DashboardCanvas .../>` block and its imports: `CustomizeBar`, `Settings2`, and the `editing` state + Customize button). If you kept the full ternary in Task 4, no change is needed here. Remove the unused `Check, X, RotateCcw` imports from `page.tsx` if present (they live in `CustomizeBar`, not the page).

- [ ] **Step 3: Verify the build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build succeeds; lint at repo baseline (2 errors / 14 warnings). No new warnings from `CustomizeBar.tsx` or `page.tsx`.

- [ ] **Step 4: Manual smoke (describe, do not automate)**

With `dev.sh` running and logged in: open `/dashboard` → click **Customize** → drag a widget to reorder → toggle an eye to hide a widget → it moves to the "Hidden widgets" tray → click its chip to restore → **Done** → reload the page and confirm the order/visibility persisted → re-enter Customize → **Reset** → **Done** → confirm default restored.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/CustomizeBar.tsx "frontend/src/app/(dashboard)/dashboard/page.tsx"
git commit -m "feat(dashboard): customize mode — drag, show/hide, save-on-done (#52 §3)"
```

---

## Task 6: Final verification

- [ ] **Step 1: Backend suite**

Run: `cd backend && PYTHONPATH=. uv run pytest -q`
Expected: all pass (369 total).

- [ ] **Step 2: Frontend build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at repo baseline (2 errors / 14 warnings — all pre-existing and in files untouched by this work).

- [ ] **Step 3: Confirm no stray behavior change in view mode**

Load `/dashboard` (not editing): the page must look identical to before — same blocks, same order (registry default), same data. Conditional widgets (Onboarding when complete/dismissed, AR Aging when no aging data, Alerts when nothing actionable) still self-hide.

---

## Self-review (completed at write time)

- **Spec coverage:** §2 Unit A (registry) → Task 2; Unit B (hook + `resolveLayout`) → Task 3; Unit C (canvas + customize mode) → Tasks 4-5; Unit D (backend store) → Task 1. §3 data flow → Task 4 `page.tsx` (`ctx` build + parallel layout fetch). §4 edge cases: default-when-null → Task 1 test + `resolveLayout`; append-missing/unknown-id → `resolveLayout` (Task 3); conditional self-hide → registry render returns `null` (Task 2) + Task 6 Step 3; save-fail banner → `CustomizeBar` `err` state (Task 5); malformed stored JSON → router GET try/except (Task 1). §5 testing: backend isolation tests → Task 1; pure `resolveLayout` + build/lint gate → Tasks 3-6.
- **Type consistency:** `WidgetContext`/`WidgetDef`/`DashboardChartConfigs` defined in Task 2 (`dashboardWidgets.tsx`); `ResolvedWidget`/`StoredLayout`/`UseDashboardLayout` defined in Task 3 (`useDashboardLayout.ts`); both consumed unchanged in Tasks 4-5. `ctx` fields built in `page.tsx` (Task 4) match `WidgetContext` exactly (`data, charts, s, netProfit, margin, fmt, agingLabels, agingValues, chartConfigs, settings, reloadSettings, checklistDismissed, setChecklistDismissed`). Endpoint shape `{layout: ...}` consistent across router (Task 1), hook GET/PUT (Task 3), and tests (Task 1).
- **No placeholders for NEW code:** all backend code, the hook, the canvas, `CustomizeBar`, and the full rewritten `page.tsx` are verbatim. The registry render bodies are **lift instructions** with exact source-line anchors + a complete substitution table (Task 2 Step 4) — the existing JSX is moved, not re-invented; one widget (`primary_kpis`) and the trivial ones (`recent_transactions`) are shown fully as the pattern.
- **Ordering/standalone:** Task 1 ships independently (backend). Tasks 2-3 compile without being rendered. Task 4 notes the temporary single-branch render so it builds before `CustomizeBar` exists; Task 5 restores the ternary. Each task ends green + committed.
- **Library:** `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities` added in Task 2 Step 1 (used in Task 5).
