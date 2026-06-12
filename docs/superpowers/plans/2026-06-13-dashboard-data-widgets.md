# B2 — Dashboard Data Widgets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three opt-in dashboard widgets — Bank Balances, Top Products, Inventory Summary — each a self-fetching grid widget reusing an existing endpoint.

**Architecture:** Three self-contained components (the `RecentTransactions` pattern: a registry entry whose `render` returns a component that owns its `useEffect` fetch) plus a pure aggregation helper. Bank Balances reads `GET /api/bank-accounts`; Top Products + Inventory Summary read `GET /api/reports/inventory-performance`. A new `WidgetDef.defaultOnGrid` flag (default true) keeps the three off the default dashboard while the existing Add-widget panel surfaces them automatically.

**Tech Stack:** Next.js 16 / React 19 / TypeScript. Frontend-only, no backend changes.

**Spec:** `docs/superpowers/specs/2026-06-13-dashboard-data-widgets-design.md`

**Gate:** No JS unit runner — every task ends with `npm run build` green and `npm run lint` at the repo baseline (**2 errors / 14 warnings**, pre-existing/unrelated). Backend untouched (suite stays 369).

---

## File Structure

**New:**
- `frontend/src/lib/inventorySummary.ts` — `InventoryPerfItem`/`InventoryTotals` types + pure `summarizeInventory` / `topByUnitsSold`.
- `frontend/src/components/dashboard/widgets/BankBalancesWidget.tsx`
- `frontend/src/components/dashboard/widgets/TopProductsWidget.tsx`
- `frontend/src/components/dashboard/widgets/InventorySummaryWidget.tsx`

**Modified:**
- `frontend/src/lib/dashboardWidgets.tsx` — `WidgetDef.defaultOnGrid?` + 3 registry entries (+ component imports).
- `frontend/src/hooks/useDashboardLayout.ts` — `defaultGrid()` excludes `defaultOnGrid === false`.

---

## Task 1: Pure inventory helpers

**Files:** Create `frontend/src/lib/inventorySummary.ts`

- [ ] **Step 1: Create the file with EXACTLY:**

```ts
// Shape of an item from GET /api/reports/inventory-performance (subset we use).
// Money/Decimal fields may arrive as number or numeric-string → coerce with Number().
export interface InventoryPerfItem {
  id: number
  name: string
  code: string
  on_hand: number | string
  stock_value: number | string
  low_stock: boolean
  units_sold: number | string
}

export interface InventoryTotals { totalValue: number; itemCount: number; lowStock: number }

export function summarizeInventory(items: InventoryPerfItem[]): InventoryTotals {
  return {
    totalValue: items.reduce((sum, i) => sum + Number(i.stock_value), 0),
    itemCount: items.length,
    lowStock: items.filter(i => i.low_stock).length,
  }
}

export function topByUnitsSold(items: InventoryPerfItem[], n: number): InventoryPerfItem[] {
  return [...items].sort((a, b) => Number(b.units_sold) - Number(a.units_sold)).slice(0, n)
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: green (pure, unconsumed).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/inventorySummary.ts
git commit -m "feat(dashboard): pure inventory summary + top-products helpers (B2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: BankBalancesWidget

**Files:** Create `frontend/src/components/dashboard/widgets/BankBalancesWidget.tsx`

- [ ] **Step 1: Create the file with EXACTLY:**

```tsx
"use client"

import { useEffect, useState } from "react"
import { useFmt } from "@/context/SettingsContext"
import { apiFetch } from "@/lib/api"

interface BankAccountRow { id: number; name: string; bank_name?: string | null; balance: number | string }

export default function BankBalancesWidget() {
  const fmt = useFmt()
  const [rows, setRows] = useState<BankAccountRow[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiFetch<BankAccountRow[]>("/api/bank-accounts")
      .then(setRows)
      .catch(() => setError(true))
  }, [])

  const total = rows ? rows.reduce((s, r) => s + Number(r.balance), 0) : 0

  return (
    <div className="h-full flex flex-col bg-white border border-[#ede9e2] rounded-xl p-4 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-2">Bank Balances</p>
      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !rows ? (
        <div className="shimmer h-20 rounded-lg" />
      ) : rows.length === 0 ? (
        <div className="text-sm text-[#1a1814]/40">No bank accounts.</div>
      ) : (
        <>
          <div className="flex-1 min-h-0 overflow-y-auto -mx-1 px-1">
            {rows.map(r => (
              <div key={r.id} className="flex items-center justify-between gap-2 py-1.5 border-b border-[#ede9e2] last:border-0 text-sm">
                <span className="truncate text-[#1a1814]/80">{r.name}</span>
                <span className="font-medium tabular-nums whitespace-nowrap">{fmt(Number(r.balance))}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between pt-2 mt-1 border-t-2 border-[#b8943f]/30 text-sm font-bold">
            <span>Total</span>
            <span className="tabular-nums">{fmt(total)}</span>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: green. (`useFmt` is exported from `@/context/SettingsContext` and returns `(n: number) => string` — same import the dashboard page uses.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/widgets/BankBalancesWidget.tsx
git commit -m "feat(dashboard): Bank Balances widget (B2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: TopProductsWidget

**Files:** Create `frontend/src/components/dashboard/widgets/TopProductsWidget.tsx`

- [ ] **Step 1: Create the file with EXACTLY:**

```tsx
"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { topByUnitsSold, type InventoryPerfItem } from "@/lib/inventorySummary"

export default function TopProductsWidget() {
  const [items, setItems] = useState<InventoryPerfItem[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiFetch<{ items: InventoryPerfItem[] }>("/api/reports/inventory-performance")
      .then(r => setItems(r.items))
      .catch(() => setError(true))
  }, [])

  const top = items ? topByUnitsSold(items, 5) : []

  return (
    <div className="h-full flex flex-col bg-white border border-[#ede9e2] rounded-xl p-4 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-2">Top Products</p>
      <p className="text-[10px] text-[#1a1814]/40 -mt-1 mb-2">by units sold</p>
      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !items ? (
        <div className="shimmer h-20 rounded-lg" />
      ) : top.length === 0 ? (
        <div className="text-sm text-[#1a1814]/40">No products yet.</div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto -mx-1 px-1">
          {top.map((p, i) => (
            <div key={p.id} className="flex items-center gap-2 py-1.5 border-b border-[#ede9e2] last:border-0 text-sm">
              <span className="text-[10px] font-bold text-[#b8943f] w-4 flex-shrink-0">{i + 1}</span>
              <span className="flex-1 truncate text-[#1a1814]/80">{p.name}</span>
              <span className="font-medium tabular-nums whitespace-nowrap">{Number(p.units_sold)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: green.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/widgets/TopProductsWidget.tsx
git commit -m "feat(dashboard): Top Products widget (B2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: InventorySummaryWidget

**Files:** Create `frontend/src/components/dashboard/widgets/InventorySummaryWidget.tsx`

- [ ] **Step 1: Create the file with EXACTLY:**

```tsx
"use client"

import { useEffect, useState } from "react"
import { useFmt } from "@/context/SettingsContext"
import { apiFetch } from "@/lib/api"
import { summarizeInventory, type InventoryPerfItem } from "@/lib/inventorySummary"

export default function InventorySummaryWidget() {
  const fmt = useFmt()
  const [items, setItems] = useState<InventoryPerfItem[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiFetch<{ items: InventoryPerfItem[] }>("/api/reports/inventory-performance")
      .then(r => setItems(r.items))
      .catch(() => setError(true))
  }, [])

  const t = items ? summarizeInventory(items) : null

  return (
    <div className="h-full flex flex-col bg-white border border-[#ede9e2] rounded-xl p-4 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-3">Inventory Summary</p>
      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !t ? (
        <div className="shimmer h-16 rounded-lg" />
      ) : (
        <div className="flex-1 grid grid-cols-3 gap-2 items-center">
          <Figure label="Stock Value" value={fmt(t.totalValue)} />
          <Figure label="Stock Items" value={String(t.itemCount)} />
          <Figure label="Low Stock" value={String(t.lowStock)} warn={t.lowStock > 0} />
        </div>
      )}
    </div>
  )
}

function Figure({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="text-center min-w-0">
      <p className={`text-lg font-bold leading-none truncate ${warn ? "text-amber-600" : "text-[#1a1814]"}`}>{value}</p>
      <p className="text-[10px] text-[#1a1814]/55 mt-1 uppercase tracking-wide">{label}</p>
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: green.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/widgets/InventorySummaryWidget.tsx
git commit -m "feat(dashboard): Inventory Summary widget (B2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Register the widgets (opt-in)

**Files:**
- Modify `frontend/src/lib/dashboardWidgets.tsx`
- Modify `frontend/src/hooks/useDashboardLayout.ts`

- [ ] **Step 1: Add `defaultOnGrid` to `WidgetDef`**

In `frontend/src/lib/dashboardWidgets.tsx`, the `WidgetDef` interface currently is:

```tsx
export interface WidgetDef {
  id: string
  title: string
  defaultVisible: boolean
  defaultSize: WidgetSize
  minSize: WidgetSize
  pinned?: boolean
  conditional?: boolean
  render: (ctx: WidgetContext) => React.ReactNode
}
```

Add the `defaultOnGrid` field (default behavior = on the grid; set `false` to make a widget opt-in):

```tsx
export interface WidgetDef {
  id: string
  title: string
  defaultVisible: boolean
  defaultSize: WidgetSize
  minSize: WidgetSize
  pinned?: boolean
  conditional?: boolean
  defaultOnGrid?: boolean        // default true; false = not on the default dashboard, add via panel
  render: (ctx: WidgetContext) => React.ReactNode
}
```

- [ ] **Step 2: Import the three widget components**

Add these imports near the other component imports at the top of `dashboardWidgets.tsx` (it already imports `RecentTransactions` — add alongside it):

```tsx
import BankBalancesWidget from "@/components/dashboard/widgets/BankBalancesWidget"
import TopProductsWidget from "@/components/dashboard/widgets/TopProductsWidget"
import InventorySummaryWidget from "@/components/dashboard/widgets/InventorySummaryWidget"
```

- [ ] **Step 3: Append the three registry entries**

In `dashboardWidgets.tsx`, add these three entries to the END of the `WIDGET_REGISTRY` array (just before its closing `]`). The trailing comma after the existing last entry (`recent_transactions`) must be present:

```tsx
  {
    id: "bank_balances", title: "Bank Balances", defaultVisible: true, defaultOnGrid: false,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <BankBalancesWidget />,
  },
  {
    id: "top_products", title: "Top Products", defaultVisible: true, defaultOnGrid: false,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <TopProductsWidget />,
  },
  {
    id: "inventory_summary", title: "Inventory Summary", defaultVisible: true, defaultOnGrid: false,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    render: () => <InventorySummaryWidget />,
  },
```

- [ ] **Step 4: Exclude opt-in widgets from the default grid**

In `frontend/src/hooks/useDashboardLayout.ts`, `defaultGrid()` currently is:

```ts
export function defaultGrid(): GridItem[] {
  return packItems(gridDefs.map(d => ({ id: d.id, w: d.defaultSize.w, h: d.defaultSize.h })))
}
```

Change it to filter out `defaultOnGrid === false`:

```ts
export function defaultGrid(): GridItem[] {
  return packItems(
    gridDefs
      .filter(d => d.defaultOnGrid !== false)
      .map(d => ({ id: d.id, w: d.defaultSize.w, h: d.defaultSize.h })),
  )
}
```

(`gridDefs` = `WIDGET_REGISTRY.filter(w => !w.pinned)`, defined at the top of the hook file. `validateV2` is unchanged: a non-pinned opt-in widget is still a valid grid item once a user adds it, so saved layouts containing `bank_balances`/`top_products`/`inventory_summary` resolve normally.)

- [ ] **Step 5: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline **2 errors / 14 warnings** (none in the new files or the two modified files). Report exact counts.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/dashboardWidgets.tsx frontend/src/hooks/useDashboardLayout.ts
git commit -m "feat(dashboard): register Bank Balances / Top Products / Inventory Summary (opt-in) (B2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Final verification

- [ ] **Step 1: Frontend build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build green; lint at baseline (2 errors / 14 warnings, all pre-existing/unrelated).

- [ ] **Step 2: Confirm backend untouched**

Run: `cd /home/mbilal71/projects/Easy-Books && git diff --name-only main...HEAD | grep -c '^backend/' || true`
Expected: `0`.

- [ ] **Step 3: Manual smoke (describe; do not automate)**

With `dev.sh` running, logged in, on `/dashboard`:
- The **default** dashboard (fresh user / after Customize → Reset → Done) does **not** show the three new widgets.
- Customize → **Add widget** → **Widgets** tab lists **Bank Balances**, **Top Products**, **Inventory Summary** → add each.
- Bank Balances shows one row per account with its balance + a Total footer (empty-state if no accounts).
- Top Products shows the top 5 by units sold (fewer if <5; "No products yet." if none).
- Inventory Summary shows Stock Value · Stock Items · Low Stock (Low Stock amber when > 0).
- **Done** → reload → the added widgets persist. Resize each → content reflows.
- A tenant with no inventory module still renders the widgets with sane empty/zero states.

---

## Self-review (completed at write time)

- **Spec coverage:** §2 Unit A (`inventorySummary.ts`) → Task 1; Unit B/C/D (3 widgets) → Tasks 2/3/4; Unit E (registry + `defaultOnGrid` + `defaultGrid` filter; AddWidgetPanel unchanged) → Task 5. §3 data flow (self-fetch on mount, not date-range-coupled) → Tasks 2-4. §4 edge cases: empty (no accounts/products) → each widget's empty branch; fetch error → `setError(true)` inline message; <5 products → `topByUnitsSold` slice; money-as-string → `Number()` coercion in helpers + widgets; existing-user default unchanged → `defaultOnGrid:false` excluded from `defaultGrid`. §5 testing (pure helpers + build/lint + smoke) → Tasks 1/6. §6 file inventory = Tasks 1-5 exactly.
- **Type consistency:** `InventoryPerfItem`/`InventoryTotals` + `summarizeInventory`/`topByUnitsSold` defined in Task 1; imported by Tasks 3 (`topByUnitsSold`, `InventoryPerfItem`) and 4 (`summarizeInventory`, `InventoryPerfItem`). `WidgetDef.defaultOnGrid?` defined Task 5 Step 1; set on the 3 entries (Step 3); read in `defaultGrid` (Step 4). The three render fns are `() => <Component />` (no `ctx` use) — matches the `render: (ctx) => React.ReactNode` signature (ctx optional to use). Endpoint paths: `/api/bank-accounts` (Task 2), `/api/reports/inventory-performance` (Tasks 3-4) — both existing.
- **No placeholders:** full verbatim for all new files + exact interface/array/function edits for the two modified files.
- **No backend / hook-rule issues:** widgets own their hooks as real components (the `RecentTransactions` pattern); `render` returns them as elements (no hooks in `render` bodies). Backend, layout schema, `resolveLayout`/`validateV2`, `AddWidgetPanel`, `DashboardGrid` all unchanged.
