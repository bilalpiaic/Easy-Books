# Section Hub Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four tile-based hub landing pages (Receivable, Payable, Inventory, Banking) that show 4 KPIs, a section-specific data band, and a quick-action grid — zero backend changes.

**Architecture:** A shared `HubPage` component driven by `HubConfig` config objects; three band sub-components (AgingBand, LowStockBand, AccountListBand) render section-specific data previews. All data is fetched from existing endpoints via `Promise.all`. Nav wired by adding 4 Overview items to `nav.ts` and making 4 sidebar section headers clickable.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4, lucide-react, existing `apiFetch` + `useFmt` helpers.

---

## File Map

| File | Action |
|------|--------|
| `frontend/src/components/hub/AgingBand.tsx` | **Create** |
| `frontend/src/components/hub/LowStockBand.tsx` | **Create** |
| `frontend/src/components/hub/AccountListBand.tsx` | **Create** |
| `frontend/src/components/hub/HubPage.tsx` | **Create** |
| `frontend/src/lib/hubConfigs.ts` | **Create** |
| `frontend/src/app/(dashboard)/receivable/page.tsx` | **Create** |
| `frontend/src/app/(dashboard)/payable/page.tsx` | **Create** |
| `frontend/src/app/(dashboard)/inventory/page.tsx` | **Create** |
| `frontend/src/app/(dashboard)/banking/page.tsx` | **Create** |
| `frontend/src/lib/nav.ts` | **Modify** — add `LayoutGrid` import + 4 Overview items |
| `frontend/src/components/Sidebar.tsx` | **Modify** — clickable section headers for 4 hub sections |

---

## API Shape Reference

These endpoints are consumed by the hub configs — no backend changes needed.

```
GET /api/invoices/aging  → { current: float, "1_30": float, "31_60": float, "61_90": float, over_90: float, items: [{..., days_past: int}] }
GET /api/bills/aging     → same shape
GET /api/invoices?limit=1 → { total: int, items: [] }
GET /api/bills?limit=1   → { total: int, items: [] }
GET /api/reports/inventory-performance → { items: [{name, on_hand, reorder_level, stock_value, low_stock, ...}] }
GET /api/bank-accounts   → BankAccount[]  (each has .balance computed server-side)
GET /api/bank-imports    → BankStatementImport[]  (status: "parsed" | "matched" | "reconciled")
```

---

## Task 1: Band Components

**Files:**
- Create: `frontend/src/components/hub/AgingBand.tsx`
- Create: `frontend/src/components/hub/LowStockBand.tsx`
- Create: `frontend/src/components/hub/AccountListBand.tsx`

These are pure presentational components. No API calls, no hooks except `useFmt`.

- [ ] **Step 1: Create AgingBand**

```tsx
// frontend/src/components/hub/AgingBand.tsx
"use client"
import { useFmt } from "@/context/SettingsContext"

export interface AgingBandProps {
  current: number
  d1_30:   number
  d31_60:  number
  d60plus: number   // 61_90 + over_90 combined
}

const SEGMENTS = [
  { key: "current" as const, label: "Current", bg: "bg-green-500",  fg: "#16a34a" },
  { key: "d1_30"   as const, label: "1–30d",   bg: "bg-amber-500",  fg: "#d97706" },
  { key: "d31_60"  as const, label: "31–60d",  bg: "bg-orange-500", fg: "#ea580c" },
  { key: "d60plus" as const, label: "60d+",    bg: "bg-red-600",    fg: "#dc2626" },
]

export default function AgingBand(props: AgingBandProps) {
  const fmt = useFmt()
  const total = props.current + props.d1_30 + props.d31_60 + props.d60plus
  if (total === 0)
    return (
      <div className="bg-white rounded-xl p-3 text-sm text-[#1a1814]/40 text-center">
        No outstanding items
      </div>
    )
  return (
    <div className="bg-white rounded-xl p-3">
      <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/40 mb-2">
        Aging Breakdown
      </div>
      <div className="flex gap-px h-2 rounded-full overflow-hidden mb-2">
        {SEGMENTS.map(s =>
          props[s.key] > 0 ? (
            <div
              key={s.key}
              className={s.bg}
              style={{ flex: props[s.key] }}
              title={`${s.label}: ${fmt(props[s.key])}`}
            />
          ) : null
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {SEGMENTS.map(s => {
          const pct = Math.round((props[s.key] / total) * 100)
          return pct > 0 ? (
            <span key={s.key} className="text-[9px]" style={{ color: s.fg }}>
              ■ {s.label} {pct}%
            </span>
          ) : null
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create LowStockBand**

```tsx
// frontend/src/components/hub/LowStockBand.tsx
export interface LowStockItem {
  name: string
  on_hand: number
  reorder_level: number
}

export interface LowStockBandProps {
  items: LowStockItem[]
}

export default function LowStockBand({ items }: LowStockBandProps) {
  if (items.length === 0) return null
  return (
    <div className="bg-white rounded-xl p-3">
      <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-amber-600 mb-2">
        ⚠ Low Stock Alerts
      </div>
      <div className="flex flex-col gap-1.5">
        {items.slice(0, 3).map((item, i) => {
          const out = item.on_hand <= 0
          return (
            <div
              key={i}
              className={`flex justify-between items-center rounded-lg px-2.5 py-1.5 ${out ? "bg-red-50" : "bg-amber-50"}`}
            >
              <span className="text-xs text-[#1a1814] truncate">{item.name}</span>
              <span className={`text-xs font-bold ml-2 shrink-0 ${out ? "text-red-600" : "text-amber-600"}`}>
                {out ? "Out of stock" : `${item.on_hand} left`}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create AccountListBand**

```tsx
// frontend/src/components/hub/AccountListBand.tsx
"use client"
import Link from "next/link"
import { useFmt } from "@/context/SettingsContext"

export interface BankAccountRow {
  id: number
  name: string
  balance: number
}

export interface AccountListBandProps {
  accounts: BankAccountRow[]
}

export default function AccountListBand({ accounts }: AccountListBandProps) {
  const fmt = useFmt()
  const sorted = [...accounts].sort((a, b) => b.balance - a.balance)
  const shown = sorted.slice(0, 5)
  const overflow = sorted.length - 5

  return (
    <div className="bg-white rounded-xl p-3">
      <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/40 mb-2">
        Account Balances
      </div>
      <div className="flex flex-col gap-1.5">
        {shown.map(acc => (
          <div
            key={acc.id}
            className="flex justify-between items-center bg-[#f8f5ef] rounded-lg px-2.5 py-1.5"
          >
            <span className="text-xs text-[#1a1814] truncate">{acc.name}</span>
            <span className="text-xs font-bold text-[#1a1814] ml-2 shrink-0">{fmt(acc.balance)}</span>
          </div>
        ))}
        {overflow > 0 && (
          <Link
            href="/bank-accounts"
            className="text-[10px] text-[#b8943f] hover:underline text-right mt-0.5"
          >
            +{overflow} more →
          </Link>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verify no TS errors**

Run from `frontend/`:
```bash
npm run build 2>&1 | head -40
```
Expected: no errors related to the new hub/ files. (Other pages may still compile fine.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/hub/
git commit -m "feat: add AgingBand, LowStockBand, AccountListBand hub sub-components"
```

---

## Task 2: HubPage Generic Component

**Files:**
- Create: `frontend/src/components/hub/HubPage.tsx`

This is the generic renderer. It owns: header, KPI tiles, band slot, action grid, loading skeleton, and error banner.

- [ ] **Step 1: Create HubPage.tsx**

```tsx
// frontend/src/components/hub/HubPage.tsx
"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import AgingBand, { type AgingBandProps } from "./AgingBand"
import LowStockBand, { type LowStockBandProps } from "./LowStockBand"
import AccountListBand, { type AccountListBandProps } from "./AccountListBand"

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type HubRawData = any[]

export interface KpiDef {
  label: string
  value: (raw: HubRawData) => string | number
  tone?: (raw: HubRawData) => "normal" | "warning" | "danger"
  /** "currency" = pass the number through fmt(); "text" = use value string as-is */
  format?: "currency" | "text"
}

export interface ActionDef {
  label: string
  href: string
  icon: LucideIcon
  primary?: boolean
}

export type BandType = "aging" | "low-stock" | "account-list"

export interface HubConfig {
  section: string
  title: string
  icon: LucideIcon
  kpis: KpiDef[]             // exactly 4
  band: BandType
  bandData: (raw: HubRawData) => unknown   // cast at render site
  actions: ActionDef[]       // 4–8 tiles; first should be primary
  fetch: () => Promise<HubRawData>
}

const TONE: Record<string, string> = {
  normal:  "text-[#1a1814]",
  warning: "text-amber-600",
  danger:  "text-red-600",
}

export default function HubPage({ config }: { config: HubConfig }) {
  const router = useRouter()
  const fmt = useFmt()
  const [raw, setRaw] = useState<HubRawData | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    config.fetch().then(setRaw).catch(() => setError(true))
  }, [config])

  const loading = !raw && !error

  const displayKpi = (kpi: KpiDef, val: string | number): string =>
    kpi.format === "currency" && typeof val === "number" ? fmt(val) : String(val)

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#b8943f] mb-0.5">
            {config.section}
          </div>
          <h1 className="text-3xl font-serif text-[#1a1814]">{config.title}</h1>
        </div>
        <config.icon className="w-10 h-10 text-[#b8943f]/40 mt-1" />
      </div>

      {/* Error banner — action grid still renders below */}
      {error && (
        <div className="mb-4 rounded-xl bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-800">
          Could not load summary — data may be stale.
        </div>
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        {config.kpis.map((kpi, i) => {
          const val = raw ? kpi.value(raw) : null
          const tone = raw && kpi.tone ? kpi.tone(raw) : "normal"
          return (
            <div
              key={i}
              className="bg-white rounded-2xl p-4 shadow-sm shadow-black/5 border border-[#1a1814]/5"
            >
              <div
                className={cn(
                  "text-lg font-bold font-mono truncate",
                  loading ? "text-[#1a1814]/10 animate-pulse" : TONE[tone]
                )}
              >
                {loading ? "—" : val !== null ? displayKpi(kpi, val) : "—"}
              </div>
              <div className="text-[9px] font-bold uppercase tracking-[0.1em] text-[#1a1814]/40 mt-1">
                {kpi.label}
              </div>
            </div>
          )
        })}
      </div>

      {/* Data band */}
      <div className="mb-4">
        {loading && <div className="bg-white rounded-xl h-20 animate-pulse" />}
        {!loading && raw && config.band === "aging" && (
          <AgingBand {...(config.bandData(raw) as AgingBandProps)} />
        )}
        {!loading && raw && config.band === "low-stock" && (
          <LowStockBand {...(config.bandData(raw) as LowStockBandProps)} />
        )}
        {!loading && raw && config.band === "account-list" && (
          <AccountListBand {...(config.bandData(raw) as AccountListBandProps)} />
        )}
      </div>

      {/* Action grid */}
      <div className="grid grid-cols-4 gap-3">
        {config.actions.map((action, i) => (
          <button
            key={i}
            onClick={() => router.push(action.href)}
            className={cn(
              "flex flex-col items-center gap-2 rounded-2xl p-4 text-center transition-all",
              "hover:scale-[1.02] shadow-sm shadow-black/5 border",
              action.primary
                ? "bg-[#1a1814] text-white border-transparent hover:bg-[#b8943f]"
                : "bg-white text-[#1a1814] border-[#1a1814]/5 hover:bg-[#f6f3ee]"
            )}
          >
            <action.icon
              className={cn("w-5 h-5", action.primary ? "text-white" : "text-[#b8943f]")}
            />
            <span
              className={cn(
                "text-[10px] font-medium leading-tight",
                action.primary ? "text-white" : "text-[#1a1814]/70"
              )}
            >
              {action.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error" | head -20
```
Expected: no errors in `hub/` files.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/hub/HubPage.tsx
git commit -m "feat: add generic HubPage renderer driven by HubConfig"
```

---

## Task 3: Hub Config Objects

**Files:**
- Create: `frontend/src/lib/hubConfigs.ts`

Four config objects — one per hub section. All data is composed from existing endpoints; no new backend code.

**Important API notes:**
- `GET /api/bank-imports` returns a plain array (not paginated): `BankStatementImport[]`
- `BankStatementImport.status` values: `"parsed"` (uploaded, not matched), `"matched"` (matched, not reconciled), `"reconciled"` (done)
- Pending Imports KPI = `status === "parsed"` count; Unreconciled = `status === "matched"` count

- [ ] **Step 1: Create hubConfigs.ts**

```ts
// frontend/src/lib/hubConfigs.ts
import {
  FileSignature, PlusCircle, ArrowDownLeft, Users, Clock,
  Receipt, Percent, Tags, TrendingUp, FileText, ArrowUpRight,
  Truck, Undo2, CalendarCheck, ShoppingCart, Package,
  BookOpen, PieChart, Landmark, Upload, CheckCheck, Wallet,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import type { HubConfig, HubRawData } from "@/components/hub/HubPage"

const sum = (...vals: number[]) => vals.reduce((a, b) => a + (b || 0), 0)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const meanDays = (items: any[]): number => {
  const overdue = items.filter(i => (i.days_past ?? 0) > 0).map(i => i.days_past as number)
  return overdue.length ? Math.round(overdue.reduce((a, b) => a + b, 0) / overdue.length) : 0
}

export const RECEIVABLE_CONFIG: HubConfig = {
  section: "Receivable",
  title: "Accounts Receivable",
  icon: FileSignature,
  fetch: () =>
    Promise.all([
      apiFetch<Record<string, number> & { items?: { days_past: number }[] }>("/api/invoices/aging"),
      apiFetch<{ total: number }>("/api/invoices?limit=1"),
    ]) as Promise<HubRawData>,
  kpis: [
    {
      label: "Total AR",
      format: "currency",
      value: ([aging]) => sum(aging.current, aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90),
    },
    {
      label: "Overdue",
      format: "currency",
      value: ([aging]) => sum(aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90),
      tone: ([aging]) =>
        sum(aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90) > 0 ? "danger" : "normal",
    },
    {
      label: "Open Invoices",
      value: ([, inv]) => inv.total ?? 0,
    },
    {
      label: "Avg Days Overdue",
      value: ([aging]) => {
        const d = meanDays(aging.items ?? [])
        return d > 0 ? `${d}d` : "0d"
      },
      tone: ([aging]) => {
        const d = meanDays(aging.items ?? [])
        return d > 30 ? "danger" : d > 0 ? "warning" : "normal"
      },
    },
  ],
  band: "aging",
  bandData: ([aging]) => ({
    current: aging.current    || 0,
    d1_30:   aging["1_30"]   || 0,
    d31_60:  aging["31_60"]  || 0,
    d60plus: sum(aging["61_90"] || 0, aging.over_90 || 0),
  }),
  actions: [
    { label: "New Invoice",     href: "/invoices/new",         icon: PlusCircle,   primary: true },
    { label: "Payments",        href: "/payments-received",    icon: ArrowDownLeft              },
    { label: "Customers",       href: "/customers",            icon: Users                      },
    { label: "AR Aging",        href: "/aging/receivable",     icon: Clock                      },
    { label: "Credit Notes",    href: "/credit-notes",         icon: Receipt                    },
    { label: "Commissions",     href: "/commissions",          icon: Percent                    },
    { label: "Promo Discounts", href: "/promo-discounts",      icon: Tags                       },
    { label: "Performance",     href: "/customer-performance", icon: TrendingUp                 },
  ],
}

export const PAYABLE_CONFIG: HubConfig = {
  section: "Payable",
  title: "Accounts Payable",
  icon: FileText,
  fetch: () =>
    Promise.all([
      apiFetch<Record<string, number> & { items?: { days_past: number }[] }>("/api/bills/aging"),
      apiFetch<{ total: number }>("/api/bills?limit=1"),
    ]) as Promise<HubRawData>,
  kpis: [
    {
      label: "Total AP",
      format: "currency",
      value: ([aging]) => sum(aging.current, aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90),
    },
    {
      label: "Overdue",
      format: "currency",
      value: ([aging]) => sum(aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90),
      tone: ([aging]) =>
        sum(aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90) > 0 ? "danger" : "normal",
    },
    {
      label: "Open Bills",
      value: ([, bills]) => bills.total ?? 0,
    },
    {
      label: "Avg Days Overdue",
      value: ([aging]) => {
        const d = meanDays(aging.items ?? [])
        return d > 0 ? `${d}d` : "0d"
      },
      tone: ([aging]) => {
        const d = meanDays(aging.items ?? [])
        return d > 30 ? "danger" : d > 0 ? "warning" : "normal"
      },
    },
  ],
  band: "aging",
  bandData: ([aging]) => ({
    current: aging.current    || 0,
    d1_30:   aging["1_30"]   || 0,
    d31_60:  aging["31_60"]  || 0,
    d60plus: sum(aging["61_90"] || 0, aging.over_90 || 0),
  }),
  actions: [
    { label: "New Bill",        href: "/bills/new",                     icon: PlusCircle,   primary: true },
    { label: "Bill Payments",   href: "/bill-payments",                 icon: ArrowUpRight               },
    { label: "Vendors",         href: "/vendors",                       icon: Truck                      },
    { label: "AP Aging",        href: "/aging/payable",                 icon: Clock                      },
    { label: "Debit Notes",     href: "/debit-notes",                   icon: Undo2                      },
    { label: "Bills",           href: "/bills",                         icon: FileText                   },
    { label: "Payment Terms",   href: "/payment-terms",                 icon: CalendarCheck              },
    { label: "Purchase Orders", href: "/manufacturing/purchase-orders", icon: ShoppingCart               },
  ],
}

export const INVENTORY_CONFIG: HubConfig = {
  section: "Inventory",
  title: "Inventory",
  icon: Package,
  fetch: () =>
    apiFetch<{ items: Record<string, unknown>[] }>("/api/reports/inventory-performance").then(r => [r]),
  kpis: [
    {
      label: "Products",
      value: ([data]) => (data.items ?? []).length,
    },
    {
      label: "Stock Value",
      format: "currency",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([data]) => (data.items ?? []).reduce((a: number, i: any) => a + (i.stock_value || 0), 0),
    },
    {
      label: "Low Stock",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([data]) => (data.items ?? []).filter((i: any) => i.low_stock && i.on_hand > 0).length,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      tone: ([data]) =>
        (data.items ?? []).filter((i: any) => i.low_stock && i.on_hand > 0).length > 0
          ? "warning"
          : "normal",
    },
    {
      label: "Out of Stock",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([data]) => (data.items ?? []).filter((i: any) => i.on_hand <= 0).length,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      tone: ([data]) =>
        (data.items ?? []).filter((i: any) => i.on_hand <= 0).length > 0 ? "danger" : "normal",
    },
  ],
  band: "low-stock",
  bandData: ([data]) => ({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    items: [...(data.items ?? [])]
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .filter((i: any) => i.low_stock || i.on_hand <= 0)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .sort((a: any, b: any) => {
        if (a.on_hand <= 0 && b.on_hand > 0) return -1
        if (b.on_hand <= 0 && a.on_hand > 0) return 1
        const ra = a.on_hand / (a.reorder_level || 1)
        const rb = b.on_hand / (b.reorder_level || 1)
        return ra - rb
      })
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .map((i: any) => ({ name: i.name, on_hand: i.on_hand, reorder_level: i.reorder_level ?? 0 })),
  }),
  actions: [
    { label: "New Product",      href: "/products/new",          icon: PlusCircle, primary: true },
    { label: "Product Ledger",   href: "/products/ledger",       icon: BookOpen                 },
    { label: "Categories",       href: "/products/categories",   icon: Tags                     },
    { label: "Inventory Report", href: "/inventory/performance", icon: PieChart                 },
  ],
}

export const BANKING_CONFIG: HubConfig = {
  section: "Banking",
  title: "Banking",
  icon: Landmark,
  fetch: () =>
    Promise.all([
      apiFetch<{ id: number; name: string; balance?: number }[]>("/api/bank-accounts"),
      apiFetch<{ status: string }[]>("/api/bank-imports"),
    ]) as Promise<HubRawData>,
  kpis: [
    {
      label: "Total Funds",
      format: "currency",
      value: ([accounts]) =>
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (accounts as any[]).reduce((a: number, acc: any) => a + (acc.balance || 0), 0),
    },
    {
      label: "Accounts",
      value: ([accounts]) => (accounts as unknown[]).length,
    },
    {
      label: "Pending Imports",
      value: ([, imports]) =>
        (imports as { status: string }[]).filter(i => i.status === "parsed").length,
      tone: ([, imports]) =>
        (imports as { status: string }[]).filter(i => i.status === "parsed").length > 0
          ? "warning"
          : "normal",
    },
    {
      label: "Unreconciled",
      value: ([, imports]) =>
        (imports as { status: string }[]).filter(i => i.status === "matched").length,
      tone: ([, imports]) =>
        (imports as { status: string }[]).filter(i => i.status === "matched").length > 0
          ? "warning"
          : "normal",
    },
  ],
  band: "account-list",
  bandData: ([accounts]) => ({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    accounts: (accounts as any[]).map((a: any) => ({
      id: a.id,
      name: a.name,
      balance: a.balance || 0,
    })),
  }),
  actions: [
    { label: "Import CSV",      href: "/bank-imports",    icon: Upload,      primary: true },
    { label: "Bank Accounts",   href: "/bank-accounts",   icon: Landmark                  },
    { label: "Reconciliations", href: "/reconciliations", icon: CheckCheck                },
    { label: "Cash Book",       href: "/cash-book",       icon: Wallet                    },
    { label: "Bank Book",       href: "/bank-book",       icon: BookOpen                  },
    { label: "Exchange Rates",  href: "/exchange-rates",  icon: TrendingUp                },
  ],
}
```

- [ ] **Step 2: Verify types compile**

```bash
cd frontend && npm run build 2>&1 | grep -E "error TS" | head -20
```
Expected: no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/hubConfigs.ts
git commit -m "feat: add hub config objects for Receivable, Payable, Inventory, Banking"
```

---

## Task 4: Hub Page Files

**Files:**
- Create: `frontend/src/app/(dashboard)/receivable/page.tsx`
- Create: `frontend/src/app/(dashboard)/payable/page.tsx`
- Create: `frontend/src/app/(dashboard)/inventory/page.tsx`
- Create: `frontend/src/app/(dashboard)/banking/page.tsx`

Each file is a thin wrapper that passes its config to `HubPage`. These four directories should already exist from prior nav structure — if `inventory/` doesn't exist, Next.js creates the route automatically when the file is added.

- [ ] **Step 1: Create receivable/page.tsx**

```tsx
// frontend/src/app/(dashboard)/receivable/page.tsx
"use client"
import HubPage from "@/components/hub/HubPage"
import { RECEIVABLE_CONFIG } from "@/lib/hubConfigs"

export default function ReceivableHub() {
  return <HubPage config={RECEIVABLE_CONFIG} />
}
```

- [ ] **Step 2: Create payable/page.tsx**

```tsx
// frontend/src/app/(dashboard)/payable/page.tsx
"use client"
import HubPage from "@/components/hub/HubPage"
import { PAYABLE_CONFIG } from "@/lib/hubConfigs"

export default function PayableHub() {
  return <HubPage config={PAYABLE_CONFIG} />
}
```

- [ ] **Step 3: Create inventory/page.tsx**

```tsx
// frontend/src/app/(dashboard)/inventory/page.tsx
"use client"
import HubPage from "@/components/hub/HubPage"
import { INVENTORY_CONFIG } from "@/lib/hubConfigs"

export default function InventoryHub() {
  return <HubPage config={INVENTORY_CONFIG} />
}
```

- [ ] **Step 4: Create banking/page.tsx**

```tsx
// frontend/src/app/(dashboard)/banking/page.tsx
"use client"
import HubPage from "@/components/hub/HubPage"
import { BANKING_CONFIG } from "@/lib/hubConfigs"

export default function BankingHub() {
  return <HubPage config={BANKING_CONFIG} />
}
```

- [ ] **Step 5: Verify routes build**

```bash
cd frontend && npm run build 2>&1 | grep -E "error TS|Route" | head -30
```
Expected: 4 new routes visible in build output (`/receivable`, `/payable`, `/inventory`, `/banking`), no TS errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/\(dashboard\)/receivable/ frontend/src/app/\(dashboard\)/payable/ frontend/src/app/\(dashboard\)/inventory/page.tsx frontend/src/app/\(dashboard\)/banking/
git commit -m "feat: add Receivable, Payable, Inventory, Banking hub pages"
```

---

## Task 5: Nav Changes

**Files:**
- Modify: `frontend/src/lib/nav.ts`

Add `LayoutGrid` to the import line and insert one "Overview" item at the top of each of the four hub sections.

Current line 1 of nav.ts starts with:
```ts
import {
  LayoutDashboard, PlusCircle, ClipboardList, BookOpen, TableProperties,
```

- [ ] **Step 1: Add LayoutGrid to the import**

In `frontend/src/lib/nav.ts`, change the first import line to add `LayoutGrid`:

```ts
import {
  LayoutDashboard, LayoutGrid, PlusCircle, ClipboardList, BookOpen, TableProperties,
  Scale, FileText, PieChart, TrendingUp, FileSignature, Users,
  ArrowDownLeft, Receipt, Truck, ArrowUpRight, Landmark, CheckCheck,
  Percent, Settings, Package, GitBranch, HelpCircle,
  Factory, ListChecks, Tags, PackagePlus, Warehouse, ShoppingCart,
  Radio, Wallet, Network, Smartphone, Target, Banknote, ReceiptText,
  ScrollText, Tablet, UserCircle, UsersRound, RefreshCw,
  Building2, Undo2, CalendarCheck, Clock, Table2, Upload, Layers, Play, BarChart2,
  ShieldCheck,
} from "lucide-react"
```

- [ ] **Step 2: Insert 4 Overview items**

In the `NAV` array, insert one Overview item before the first item of each hub section. After the change, the relevant NAV entries are:

```ts
// — Receivable section (add Overview before Invoices at line ~31) —
{ label: "Overview",         href: "/receivable",        icon: LayoutGrid,   section: "Receivable" },
{ label: "Invoices",         href: "/invoices",          icon: FileSignature,    section: "Receivable" },
// ... rest of Receivable unchanged ...

// — Payable section (add Overview before Bills) —
{ label: "Overview",         href: "/payable",           icon: LayoutGrid,   section: "Payable" },
{ label: "Bills",            href: "/bills",             icon: Receipt,          section: "Payable" },
// ... rest of Payable unchanged ...

// — Inventory section (add Overview before Products) —
{ label: "Overview",         href: "/inventory",         icon: LayoutGrid,   section: "Inventory" },
{ label: "Products",          href: "/products",            icon: Package,          section: "Inventory" },
// ... rest of Inventory unchanged ...

// — Banking section (add Overview before Bank Accounts) —
{ label: "Overview",         href: "/banking",           icon: LayoutGrid,   section: "Banking" },
{ label: "Bank Accounts",    href: "/bank-accounts",     icon: Landmark,         section: "Banking" },
// ... rest of Banking unchanged ...
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npm run build 2>&1 | grep "error TS" | head -10
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/nav.ts
git commit -m "feat: add Overview nav items for Receivable, Payable, Inventory, Banking hub sections"
```

---

## Task 6: Sidebar Clickable Section Headers

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`

The sidebar section header is currently a plain `<div>` at line ~153. For the four hub sections, it becomes a `<button>` that navigates to the hub. A `ChevronRight` hint (12px, opacity-40) appears on the right.

- [ ] **Step 1: Add HUB_ROUTES constant**

After the `SECTION_COLORS` constant (around line 22), add:

```ts
const HUB_ROUTES: Record<string, string> = {
  Receivable: "/receivable",
  Payable:    "/payable",
  Inventory:  "/inventory",
  Banking:    "/banking",
}
```

- [ ] **Step 2: Replace the section header div with conditional button**

The section header block currently looks like:
```tsx
<div className={cn("px-4 pt-3 pb-1 text-[9px] font-bold uppercase tracking-[0.15em]", SECTION_COLORS[section])}>
  {section}
</div>
```

Replace it with:
```tsx
{HUB_ROUTES[section] ? (
  <button
    onClick={() => go(HUB_ROUTES[section])}
    className={cn(
      "w-full flex items-center justify-between px-4 pt-3 pb-1",
      "text-[9px] font-bold uppercase tracking-[0.15em]",
      "hover:opacity-80 transition-opacity",
      SECTION_COLORS[section],
      pathname.startsWith(HUB_ROUTES[section]) && "underline underline-offset-2"
    )}
  >
    {section}
    <ChevronRight className="w-3 h-3 opacity-40" />
  </button>
) : (
  <div className={cn("px-4 pt-3 pb-1 text-[9px] font-bold uppercase tracking-[0.15em]", SECTION_COLORS[section])}>
    {section}
  </div>
)}
```

Note: `ChevronRight` and `pathname` are already imported/available in Sidebar.tsx. The `go()` function is already defined in the component body and handles mobile-close behaviour.

- [ ] **Step 3: Verify**

```bash
cd frontend && npm run build 2>&1 | grep "error TS" | head -10
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat: make Receivable/Payable/Inventory/Banking sidebar section headers navigate to hub"
```

---

## Task 7: Full Build + Smoke Test

- [ ] **Step 1: Run full build**

```bash
cd frontend && npm run build
```
Expected: exits 0 with no TypeScript errors. All 4 hub routes appear in the build output.

- [ ] **Step 2: Start dev server and smoke-test all 4 hubs**

```bash
cd frontend && npm run dev
```

Navigate to each hub and verify:

| URL | Expected |
|-----|----------|
| `/receivable` | 4 KPI tiles (Total AR, Overdue, Open Invoices, Avg Days Overdue), aging bar, 8 action tiles |
| `/payable` | 4 KPI tiles (Total AP, Overdue, Open Bills, Avg Days Overdue), aging bar, 8 action tiles |
| `/inventory` | 4 KPI tiles (Products, Stock Value, Low Stock, Out of Stock), low-stock list or empty, 4 action tiles |
| `/banking` | 4 KPI tiles (Total Funds, Accounts, Pending Imports, Unreconciled), account balance list, 6 action tiles |

Also verify:
- [ ] Loading skeleton (—  pulse) shows briefly before data loads
- [ ] Sidebar section labels "Receivable", "Payable", "Inventory", "Banking" are now buttons with ChevronRight hint
- [ ] Clicking a sidebar section header navigates to hub
- [ ] New "Overview" nav item appears as first item in each of the four sections
- [ ] All action tiles navigate to the correct pages
- [ ] No console errors

- [ ] **Step 3: Commit final clean build**

```bash
git add -A
git commit -m "feat: section hub pages — 4 hub landing pages with KPIs, data bands, action grids"
```
