# Section Hub Pages — Design Spec

_Date: 2026-06-20_

## Goal

Add four tile-based "hub" landing pages — Receivable, Payable, Inventory, Banking — that give each major section a command-centre overview before users drill into raw lists. Each hub shows KPI tiles, a section-specific data band, and a quick-action grid. Zero backend changes required.

---

## Navigation wiring

Two entry points per hub (option C chosen):

1. **Sidebar section header** — the coloured section label (e.g. "RECEIVABLE") becomes a `<button>` that calls `router.push('/receivable')`.
2. **Explicit nav item** — an "Overview" entry is prepended to each section in `NAV` (`src/lib/nav.ts`).

New routes:

| Section | Route |
|---------|-------|
| Receivable | `/receivable` |
| Payable | `/payable` |
| Inventory | `/inventory` |
| Banking | `/banking` |

`/inventory` replaces the current dead route (only `/inventory/performance` existed before). The existing `/inventory/performance` page is unchanged.

---

## Component architecture

### Shared `HubPage` component

`src/components/hub/HubPage.tsx` — single generic component driven by a `HubConfig` object:

```ts
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type HubRawData = any[]   // tuple returned by Promise.all or single-item array

interface KpiDef {
  label: string
  value: (raw: HubRawData) => string | number
  tone?: (raw: HubRawData) => 'normal' | 'warning' | 'danger'   // controls text color
}

interface ActionDef {
  label: string
  href: string
  icon: LucideIcon
  primary?: boolean   // first action gets dark background
}

type BandType = 'aging' | 'low-stock' | 'account-list'

interface HubConfig {
  section: string           // matches Sidebar SECTIONS key
  title: string             // e.g. "Accounts Receivable"
  icon: LucideIcon
  route: string             // e.g. '/receivable'
  kpis: KpiDef[]            // exactly 4
  band: BandType
  actions: ActionDef[]      // 4–8 tiles; first is primary (dark)
  fetch: () => Promise<HubRawData>   // returns array; single-response hubs wrap in [response]
}
```

`HubPage` receives a `config: HubConfig`, calls `config.fetchFns()` on mount, and renders:

1. **Header row** — section label (gold, uppercase) + title (charcoal) + icon
2. **KPI row** — 4 tiles in a `grid-cols-4` grid; tone controls text color (normal = charcoal, warning = amber-600, danger = red-600)
3. **Data band** — one of three band components (see below)
4. **Action grid** — `grid-cols-4`; primary tile gets `bg-[#1a1814] text-white`, rest get `bg-white`

Loading state: skeleton shimmer on KPI tiles and band. Error state: inline amber banner ("Could not load summary — data may be stale") with the action grid still rendered (actions are navigation, not data-dependent).

### Four hub page files

Each is a thin wrapper:

```
src/app/(dashboard)/receivable/page.tsx   → <HubPage config={RECEIVABLE_CONFIG} />
src/app/(dashboard)/payable/page.tsx      → <HubPage config={PAYABLE_CONFIG} />
src/app/(dashboard)/inventory/page.tsx    → <HubPage config={INVENTORY_CONFIG} />  (replaces empty)
src/app/(dashboard)/banking/page.tsx      → <HubPage config={BANKING_CONFIG} />
```

Config objects live in `src/lib/hubConfigs.ts`.

---

## Data fetching per hub

All fetches are parallel `Promise.all` calls. No new backend endpoints.

### Receivable (`RECEIVABLE_CONFIG`)

```ts
fetchFns: () => Promise.all([
  apiFetch('/api/invoices/aging'),          // → {current, 1_30, 31_60, 61_90, over_90, items[]}
  apiFetch('/api/invoices?limit=1'),        // → {total, items[]}
])
```

**KPIs derived from response:**
| Label | Derivation |
|-------|-----------|
| Total AR | `sum(current + 1_30 + 31_60 + 61_90 + over_90)` from aging |
| Overdue | `sum(1_30 + 31_60 + 61_90 + over_90)` |
| Open Invoices | `invoices.total` |
| Avg Days Overdue | `mean(items[].days_past)` for items where `days_past > 0`; falls back to `0d` if none overdue |

**Band:** `aging` — horizontal bar with 4 segments (current=green, 1–30=amber, 31–60=orange, 60+=red), proportional to bucket amounts. Labels show bucket name + percentage.

### Payable (`PAYABLE_CONFIG`)

```ts
fetchFns: () => Promise.all([
  apiFetch('/api/bills/aging'),
  apiFetch('/api/bills?limit=1'),
])
```

Same derivation pattern as Receivable, using bill aging buckets.

**Band:** `aging` — same bar, AP buckets.

### Inventory (`INVENTORY_CONFIG`)

```ts
fetchFns: () => apiFetch('/api/reports/inventory-performance')
// → {items: [{name, on_hand, reorder_level, stock_value, low_stock, ...}]}
```

**KPIs derived:**
| Label | Derivation |
|-------|-----------|
| Products | `items.length` |
| Stock Value | `sum(items[].stock_value)` |
| Low Stock | `items.filter(i => i.low_stock && i.on_hand > 0).length`; tone=warning if > 0 |
| Out of Stock | `items.filter(i => i.on_hand <= 0).length`; tone=danger if > 0 |

**Band:** `low-stock` — top 3 products by urgency (out-of-stock first, then sorted by `on_hand / reorder_level` ratio ascending). Shows product name + qty remaining. Badge color: red if `on_hand <= 0`, amber otherwise. Hidden entirely if no low-stock items.

### Banking (`BANKING_CONFIG`)

```ts
fetchFns: () => Promise.all([
  apiFetch('/api/bank-accounts'),           // → [{id, name, account_type, coa_account_id, ...}]
  apiFetch('/api/bank-imports?limit=500'),  // → {total, items[{status}]}
])
```

**KPIs derived:**

Banking account balances are already included in the `GET /api/bank-accounts` response — the list endpoint calls `_bank_balance()` server-side and returns a `balance` field per account (confirmed in `backend/routers/bank_accounts.py:54`). No secondary account lookup needed.

| Label | Derivation |
|-------|-----------|
| Total Funds | `sum(accounts[].balance)` |
| Accounts | `accounts.length` |
| Pending Imports | `imports.items.filter(i => i.status === 'pending').length`; tone=warning if > 0 |
| Unreconciled | `imports.items.filter(i => i.status === 'imported').length`; tone=warning if > 0 |

**Band:** `account-list` — each bank account as a row (name + formatted balance). Sorted by balance descending. Max 5 rows shown; "+ N more" link to `/bank-accounts` if overflow.

---

## Band components

Three sub-components in `src/components/hub/`:

**`AgingBand.tsx`** — receives `{current, d1_30, d31_60, d61_90, over_90}` amounts (field names matching the API response, prefixed `d` to avoid leading-digit identifiers). Renders proportional 4-segment horizontal bar + legend. Shows "No outstanding items" if total is zero.

**`LowStockBand.tsx`** — receives sorted `items[]` with `{name, on_hand, reorder_level}`. Renders up to 3 alert rows. Hidden if `items.length === 0`.

**`AccountListBand.tsx`** — receives `accounts[]` with `{name, account_type, balance}`. Renders up to 5 balance rows + overflow link.

---

## Sidebar changes (`src/components/Sidebar.tsx`)

The section header `<div>` becomes a `<button>` only for the four hub sections. Other sections (Ledger, Reports, System, Manufacturing, Telecom) remain non-clickable headers.

```tsx
const HUB_ROUTES: Record<string, string> = {
  Receivable: '/receivable',
  Payable:    '/payable',
  Inventory:  '/inventory',
  Banking:    '/banking',
}
```

If `HUB_ROUTES[section]` exists, render a `<button onClick={() => go(HUB_ROUTES[section])}>` with an additional right-arrow hint icon (12px, fades in on hover). Active state: section label gets underline when `pathname.startsWith(HUB_ROUTES[section])`.

---

## Nav changes (`src/lib/nav.ts`)

Prepend one "Overview" item to each of the four hub sections:

```ts
{ label: "Overview", href: "/receivable", icon: LayoutGrid, section: "Receivable" },
{ label: "Overview", href: "/payable",    icon: LayoutGrid, section: "Payable"    },
{ label: "Overview", href: "/inventory",  icon: LayoutGrid, section: "Inventory"  },
{ label: "Overview", href: "/banking",    icon: LayoutGrid, section: "Banking"    },
```

`LayoutGrid` from `lucide-react` (already a dependency).

---

## Purchase Orders in Payable hub

The "Purchase Orders" action tile links to `/manufacturing/purchase-orders`. This route is gated by `forModel: 'manufacturing'` in the nav — but the hub action tile is not nav-filtered. Decision: include the tile for all tenants; the destination page already shows an empty state for non-manufacturing tenants. No special gating on the action tile.

---

## Currency formatting

All monetary KPI values use the existing `formatCurrency(value, currency)` helper (already used across the app). The hub reads `currency` from `useSettings()`.

---

## File map

| File | Action |
|------|--------|
| `src/components/hub/HubPage.tsx` | **Create** — generic hub renderer |
| `src/components/hub/AgingBand.tsx` | **Create** |
| `src/components/hub/LowStockBand.tsx` | **Create** |
| `src/components/hub/AccountListBand.tsx` | **Create** |
| `src/lib/hubConfigs.ts` | **Create** — 4 config objects |
| `src/app/(dashboard)/receivable/page.tsx` | **Create** |
| `src/app/(dashboard)/payable/page.tsx` | **Create** |
| `src/app/(dashboard)/inventory/page.tsx` | **Create** (replaces empty route) |
| `src/app/(dashboard)/banking/page.tsx` | **Create** |
| `src/lib/nav.ts` | **Modify** — add 4 Overview items |
| `src/components/Sidebar.tsx` | **Modify** — clickable section headers for hub sections |

No backend changes. No new dependencies.

---

## Testing

- `npm run build` must pass with no TypeScript errors.
- Manual smoke: navigate to each hub URL directly; confirm KPIs load, band renders, all action tiles navigate correctly.
- Manual: click each sidebar section header label; confirm navigation to hub.
- Manual: confirm loading skeleton shows during fetch; confirm error banner shows on network failure (throttle in DevTools).
- Non-manufacturing tenant: confirm Payable hub "Purchase Orders" tile navigates (page shows empty state — acceptable).
