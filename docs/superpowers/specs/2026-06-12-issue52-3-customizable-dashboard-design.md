# #52 §3 — User-customizable dashboard · Design

**Date:** 2026-06-12
**Issue:** #52 §3 (UX bundle) — "User-customizable dashboard"
**Effort:** L · **Priority:** Low-Med (last item in the #52 bundle)

## §1 · Goal & scope

Let each user tailor the main dashboard (`/dashboard`) by **reordering** and
**showing/hiding** the blocks already on the page, with the chosen layout
**persisted per user** (server-side, roams across devices). No new chart types
and no new data: every widget reads from the two endpoints the dashboard
already fetches.

**Locked decisions (from brainstorming 2026-06-12):**

1. **Customization model:** reorder + show/hide, single-column vertical flow
   (full-width widgets stack), **no resizing**, **no free 2D grid**.
2. **Widget catalog:** wrap the **existing** dashboard blocks only — **zero new
   backend aggregation**.
3. **KPI granularity:** the two KPI rows are **group-level** widgets (`Primary
   KPIs`, `Secondary KPIs`), not per-tile.
4. **Persistence:** **server-side, per user** (new tiny table), not localStorage.
5. **Save model:** **save-on-Done** (explicit), not autosave-per-change.

**Out of scope (YAGNI):** widget resizing, multi-column drag placement,
per-tile KPI toggling, new data widgets (Bank Balances list, Top Products,
standalone Inventory summary — deferred), cross-user/tenant default templates,
mobile-specific layouts (the single-column flow is already mobile-friendly).

## §2 · Architecture

Three isolated frontend units + one dumb backend KV store.

```
dashboard/page.tsx
  ├─ fetches /api/reports/dashboard + /api/reports/dashboard/charts   (UNCHANGED)
  ├─ useDashboardLayout()  ──▶  GET/PUT /api/dashboard/layout         (NEW, per-user)
  │     └─ resolveLayout(registry, saved): pure merge → ordered, visibility-resolved list
  └─ <DashboardCanvas>     ──▶  renders ordered visible widgets; hosts Customize mode (@dnd-kit)
        └─ WIDGET_REGISTRY  (single source of truth: id, title, defaultVisible, conditional?, render(ctx))
```

**Fixed chrome (never a widget):** the page header (`Dashboard` / `Financial
Overview`) and the `DateRangePicker` stay pinned at the top. The `Customize`
button lives in that header region. Everything below the header is widgets.

### Unit A — `frontend/src/lib/dashboardWidgets.tsx` (registry)

The single source of truth for *what widgets exist*, their default order, and
how each renders. Pure data + render functions; holds no fetching or layout
state.

```ts
export interface WidgetContext {
  data: DashboardData | null
  charts: ChartData | null
  s: DashboardSummary | undefined        // data?.summary, hoisted for convenience
  fmt: (n: number) => string
  // chart.js configs computed once in the page and passed down (barData, lineData, …)
  chartConfigs: DashboardChartConfigs
  settings: AppSettings
  reloadSettings: () => void
  checklistDismissed: boolean
  setChecklistDismissed: (v: boolean) => void
}

export interface WidgetDef {
  id: string                  // stable key persisted in layout JSON
  title: string               // shown in Customize mode + hidden tray
  defaultVisible: boolean
  conditional?: boolean       // may render null even when "visible" (Onboarding, Alerts)
  render: (ctx: WidgetContext) => React.ReactNode   // returns null when not applicable
}

export const WIDGET_REGISTRY: WidgetDef[] = [ /* ordered default layout */ ]
```

**Catalog (default order):**

| id | title | defaultVisible | conditional |
|----|-------|----------------|-------------|
| `quick_actions` | Quick Actions | true | — |
| `onboarding` | Setup Checklist | true | yes (hides when complete/dismissed) |
| `primary_kpis` | Key Figures | true | — |
| `secondary_kpis` | Receivables / Payables | true | — |
| `ar_aging` | AR Aging | true | yes (hides when no `ar_aging`) |
| `alerts` | Action Alerts | true | yes (hides when nothing actionable) |
| `monthly_rev_exp` | Monthly Revenue vs Expenses | true | — |
| `net_profit_trend` | Net Profit Trend | true | — |
| `expense_breakdown` | Expense Breakdown | true | — |
| `top_customers` | Top Customers | true | — |
| `recent_transactions` | Recent Transactions | true | — |

The render functions are the **existing JSX blocks** lifted verbatim from
`dashboard/page.tsx` (no visual change). Chart configs (`barData`, `lineData`,
`doughnutData`, `customerBarData`, `agingBarData`) and chart options are
computed once in the page and passed through `ctx.chartConfigs` so widgets stay
presentational.

### Unit B — `frontend/src/hooks/useDashboardLayout.ts`

Owns layout state + persistence. Exposes:

```ts
interface UseDashboardLayout {
  widgets: ResolvedWidget[]    // { def, visible } in display order, registry-merged
  loading: boolean
  setOrder: (orderedIds: string[]) => void   // local only
  toggle: (id: string) => void               // local only
  reset: () => void                          // local → registry default
  save: () => Promise<void>                  // PUT current local state
  dirty: boolean                             // local differs from last saved
}
```

- On mount: `GET /api/dashboard/layout`. If `null`/empty → registry default.
- `resolveLayout(registry, saved)` (pure, exported for clarity/testing) merges:
  saved order first (filtering unknown ids), then **appends any registry widget
  missing from saved** at the end with its `defaultVisible` (forward-compat when
  a future release adds a widget).
- `save()` serializes `{version:1, widgets:[{id,visible}]}` and PUTs it.

### Unit C — `frontend/src/components/dashboard/DashboardCanvas.tsx`

Renders the resolved widget list and hosts **Customize mode**.

- **View mode:** maps visible widgets → `widget.render(ctx)` in order. Identical
  to today's dashboard.
- **Customize mode** (toggled by the `Customize` button): wraps widgets in
  `@dnd-kit` `SortableContext` (vertical list). Each widget shows a **drag
  handle** + an **eye toggle** (show/hide) + its title. Hidden widgets collapse
  into a **"Hidden widgets" tray** below, each with a "+ Add" to restore.
  Conditional widgets show a muted "(shows only when relevant)" note.
- Footer actions in customize mode: **Done** (calls `save()`, exits edit mode),
  **Cancel** (discards local changes, reloads last saved), **Reset to default**
  (calls `reset()` — still requires Done to persist).
- DnD library: **`@dnd-kit/core` + `@dnd-kit/sortable`** (accessible,
  tree-shakeable, single-axis vertical). Add to `frontend/package.json`.

### Unit D — backend per-user layout store

A dumb KV store. The backend never interprets the JSON; the registry and merge
live entirely in the frontend.

```python
# models.py
class UserDashboardLayout(SQLModel, table=True):
    tenant_id: int = Field(foreign_key="tenant.id", primary_key=True)
    user_id:   int = Field(foreign_key="user.id",   primary_key=True)
    layout_json: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

```python
# routers/dashboard_layout.py  (mounted under /api/dashboard)
GET  /api/dashboard/layout   -> {"layout": <parsed json> | None}
PUT  /api/dashboard/layout   body {"layout": {...}}  -> upsert (tenant_id, current_user.id); 200
```

- Both endpoints scope by `user.tenant_id` **and** `user.id` — a user only ever
  reads/writes their own row.
- PUT validates the body is a JSON object and stores it as a string
  (`json.dumps`); GET returns `json.loads` or `None`. Malformed stored JSON →
  treated as `None` (defensive; frontend falls back to default).
- **Alembic migration** adds the table with a `bind.dialect.has_table(...)`
  guard so it coexists with dev `create_all()` (per CLAUDE.md new-table
  convention). No FK ALTER issues (table created fresh, FKs inline at create).

## §3 · Data flow

1. Page mounts → two existing fetches populate `data` + `charts` (unchanged).
2. `useDashboardLayout()` fetches the saved layout in parallel.
3. Page computes chart configs once, assembles `ctx: WidgetContext`.
4. `<DashboardCanvas>` renders resolved visible widgets via `widget.render(ctx)`.
5. User clicks **Customize** → edit mode (drag/toggle, local state only).
6. **Done** → `save()` PUTs `{version,widgets}` → exits edit mode.

The layout fetch is **independent** of the data fetch: widgets render skeletons
while `data`/`charts` load exactly as today; the layout only decides *order and
presence*, not readiness.

## §4 · Error handling & edge cases

| Case | Behavior |
|------|----------|
| New user, no saved layout | Registry default order, all `defaultVisible`. |
| Layout fetch fails | Fall back to registry default (dashboard still works). |
| Saved layout missing a registry widget | Append it at end with `defaultVisible` (forward-compat). |
| Saved layout has unknown id | Filtered out by `resolveLayout`. |
| Conditional widget "visible" but N/A | `render` returns `null`; occupies no space. In edit mode shown in list with "(shows only when relevant)". |
| Save (PUT) fails | Surface a non-blocking error toast/banner; keep edit mode open so the user can retry; local state preserved. |
| Malformed stored JSON (server) | GET returns `None`; frontend uses default. |
| Reset to default | `reset()` sets local to registry default; persisted only on Done. |

## §5 · Testing

**Backend** (`tests/test_dashboard_layout.py`):
- GET with no saved row → `{"layout": null}`.
- PUT then GET round-trips the exact JSON.
- **Per-user isolation:** two users in the *same tenant* have independent
  layouts (user A's PUT does not change user B's GET).
- **Tenant isolation:** a user cannot read/write another tenant's layout
  (implicit — store is keyed by the authenticated user; assert a second
  tenant's user starts at default).
- PUT rejects a non-object body (400).

**Frontend** (no JS unit runner — gate = `npm run build` + `npm run lint`):
- `resolveLayout` written as a **pure, exported** function so its merge logic
  (order preservation, unknown-id filtering, append-missing) is obvious and
  future-testable; verified via build/lint + manual smoke.
- Lint must stay at the repo baseline (2 errors / 14 warnings, all pre-existing)
  — no new warnings from the refactor (watch unused imports after extraction).
- Manual smoke checklist: drag reorders; eye toggles hide/show; Done persists
  across reload; Reset restores default; conditional widgets still self-hide.

## §6 · File inventory

**New:**
- `backend/models.py` → `UserDashboardLayout` table
- `backend/routers/dashboard_layout.py` → GET/PUT
- `backend/main.py` → mount the router
- `backend/alembic/versions/0020_user_dashboard_layout.py` → guarded table (next after current head 0019)
- `backend/tests/test_dashboard_layout.py`
- `frontend/src/lib/dashboardWidgets.tsx` → registry + `WidgetContext`
- `frontend/src/hooks/useDashboardLayout.ts` → hook + `resolveLayout`
- `frontend/src/components/dashboard/DashboardCanvas.tsx` → canvas + customize mode

**Modified:**
- `frontend/src/app/(dashboard)/dashboard/page.tsx` → slim to fetch + ctx +
  `<DashboardCanvas>`; move block JSX into the registry
- `frontend/package.json` → add `@dnd-kit/core`, `@dnd-kit/sortable`,
  `@dnd-kit/utilities`

**Unchanged:** both dashboard data endpoints; `RecentTransactions`,
`DateRangePicker`, KPI sub-components (reused inside registry render fns).

## §7 · Implementation order (for the plan)

1. Backend: model + migration + router + mount + tests (independent, ship-able).
2. Frontend: add @dnd-kit; create registry by lifting existing blocks (no
   behavior change yet — page renders registry in default order).
3. Frontend: `useDashboardLayout` + `resolveLayout` + wire GET on load.
4. Frontend: `DashboardCanvas` view mode (renders resolved widgets).
5. Frontend: Customize mode (drag, toggle, tray, Done/Cancel/Reset, PUT save).
6. Verify: backend suite green; `npm run build` + `npm run lint` at baseline.
