# Recent Transactions Enhancement (#41) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the minimal dashboard Recent-Transactions widget with a richer, journal-backed table — full columns, user-selectable (persisted) columns, voucher-type filter, date sort, quick search, click-to-open — with no backend change.

**Architecture:** A new client component `frontend/src/components/RecentTransactions.tsx` fetches `GET /api/reports/journal?limit=100` once and does all filtering/sorting/searching client-side over that window. Column visibility persists in `localStorage`. `dashboard/page.tsx` renders the component in place of the current inline widget.

**Tech Stack:** Next.js 16 / React 19 / TypeScript / Tailwind v4. Helpers: `apiFetch` (`@/lib/api`), `VOUCHER_TYPES` + `voucherTypeBadgeClass` (`@/lib/voucherTypes`).

**Spec:** `docs/superpowers/specs/2026-06-08-recent-transactions-design.md`

**Verification:** frontend has no unit-test harness — gate each task on **`cd frontend && npm run lint`** (no new errors in the touched files) + the component renders. No backend change → no pytest impact. **Heed `frontend/AGENTS.md`** (Next.js 16 differs from older versions).

**Endpoint shape** (`GET /api/reports/journal?limit=100` → `{total, items:[…]}`), each item: `transaction_id`, `jv_number`, `voucher_type`, `legacy_jv_number`, `date` (ISO string), `description`, `account_name`, `debit` (number), `credit` (number), `is_reversed` (bool).

---

### Task 1: Base `RecentTransactions` component + wire into dashboard

**Files:**
- Create: `frontend/src/components/RecentTransactions.tsx`
- Modify: `frontend/src/app/(dashboard)/dashboard/page.tsx` (the Recent-Transactions block, ~lines 408-450)

- [ ] **Step 1: Create the component**

Create `frontend/src/components/RecentTransactions.tsx`:

```tsx
"use client"
import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { voucherTypeBadgeClass } from "@/lib/voucherTypes"

interface JournalRow {
  transaction_id: number
  jv_number: string
  voucher_type: string
  date: string
  description: string
  account_name: string
  debit: number
  credit: number
  is_reversed: boolean
}

type ColKey = "voucher" | "vtype" | "date" | "account" | "narration" | "amount"

const ALL_COLUMNS: { key: ColKey; label: string; fixed?: boolean }[] = [
  { key: "date", label: "Date", fixed: true },
  { key: "voucher", label: "Voucher No" },
  { key: "vtype", label: "Type" },
  { key: "account", label: "Account" },
  { key: "narration", label: "Narration" },
  { key: "amount", label: "Amount", fixed: true },
]

function fmtAmount(n: number): string {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function RecentTransactions() {
  const [rows, setRows] = useState<JournalRow[] | null>(null)

  useEffect(() => {
    apiFetch<{ items: JournalRow[] }>("/api/reports/journal?limit=100")
      .then(res => setRows(res.items ?? []))
      .catch(() => setRows([]))
  }, [])

  const visible = ALL_COLUMNS  // Task 2 makes this user-selectable

  return (
    <div className="bg-white rounded-xl border border-[#ede9e2] shadow-sm overflow-hidden">
      <div className="px-5 py-3.5 border-b border-[#ede9e2] flex items-center justify-between gap-3">
        <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">Recent Transactions</p>
        <Link href="/journal" className="text-[11px] text-[#b8943f] font-semibold hover:text-[#8a6d2e]">View all →</Link>
      </div>
      <div className="overflow-x-auto">
        {rows === null ? (
          <div className="px-5 py-6 flex flex-col gap-2.5">
            {[...Array(5)].map((_, i) => <div key={i} className="flex gap-3"><div className="shimmer h-4 w-20 rounded" /><div className="shimmer h-4 w-24 rounded" /><div className="shimmer h-4 flex-1 rounded" /></div>)}
          </div>
        ) : rows.length === 0 ? (
          <div className="px-5 py-8 text-center text-[#1a1814]/40 text-sm">No transactions for this period.</div>
        ) : (
          <table className="w-full text-left min-w-[560px]">
            <thead>
              <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">
                {visible.map(c => (
                  <th key={c.key} className={`px-5 py-2.5 ${c.key === "amount" ? "text-right" : ""}`}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {rows.map((r, i) => (
                <tr key={`${r.transaction_id}-${i}`} className={`hover:bg-[#faf8f4] transition-colors text-sm ${r.is_reversed ? "opacity-50" : ""}`}>
                  {visible.map(c => <RowCell key={c.key} col={c.key} row={r} />)}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function RowCell({ col, row }: { col: ColKey; row: JournalRow }) {
  switch (col) {
    case "date":
      return <td className="px-5 py-3 text-[#1a1814]/55 text-xs whitespace-nowrap">{row.date}</td>
    case "voucher":
      return (
        <td className="px-5 py-3">
          <Link href={`/journal?jv=${row.jv_number}`}
            className="font-mono text-[11px] text-[#b8943f] font-semibold hover:underline underline-offset-2 whitespace-nowrap">
            {row.jv_number}{row.is_reversed && <span className="ml-1 text-[#1a1814]/40">(reversed)</span>}
          </Link>
        </td>
      )
    case "vtype":
      return (
        <td className="px-5 py-3">
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${voucherTypeBadgeClass(row.voucher_type)}`}>{row.voucher_type}</span>
        </td>
      )
    case "account":
      return <td className="px-5 py-3 text-[#1a1814]/70 text-xs max-w-[160px] truncate">{row.account_name}</td>
    case "narration":
      return <td className="px-5 py-3 text-[#1a1814]/80 max-w-[220px] truncate">{row.description}</td>
    case "amount": {
      const isDebit = Number(row.debit) > 0
      const amt = isDebit ? row.debit : row.credit
      return (
        <td className="px-5 py-3 text-right tabular-nums whitespace-nowrap">
          {fmtAmount(amt)}
          <span className={`ml-1.5 text-[10px] font-bold ${isDebit ? "text-blue-600" : "text-green-600"}`}>{isDebit ? "Dr" : "Cr"}</span>
        </td>
      )
    }
  }
}
```

- [ ] **Step 2: Wire it into the dashboard**

In `frontend/src/app/(dashboard)/dashboard/page.tsx`, add the import near the others (after the `DateRangePicker` import, ~line 20):

```tsx
import RecentTransactions from "@/components/RecentTransactions"
```

Replace the entire Recent-transactions block (the `{/* ── Recent transactions (full width) ── */}` wrapper through its closing `</div>`, ~lines 408-450) with:

```tsx
      {/* ── Recent transactions (full width) ─────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4">
        <RecentTransactions />
      </div>
```

(The old widget read `data.recent`; the component now fetches its own data. Leave the `data.recent` field and its `RecentTx` interface in place — harmless if still referenced elsewhere; if the `RecentTx` type or `recent` field becomes unused and lint flags it, remove just that unused declaration.)

- [ ] **Step 3: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors in `RecentTransactions.tsx` or `dashboard/page.tsx`. (If lint flags a now-unused `RecentTx`/`recent` in dashboard, remove that single unused symbol.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/RecentTransactions.tsx "frontend/src/app/(dashboard)/dashboard/page.tsx"
git commit -m "feat(dashboard): journal-backed Recent Transactions widget with full columns (#41)"
```

---

### Task 2: User-selectable columns persisted to localStorage

**Files:**
- Modify: `frontend/src/components/RecentTransactions.tsx`

- [ ] **Step 1: Add column-visibility state + persistence**

In `RecentTransactions.tsx`, replace the `const visible = ALL_COLUMNS` line and add the persistence logic. Add near the top of the component:

```tsx
  const STORAGE_KEY = "eb.recentTx.cols"
  const toggleableKeys: ColKey[] = ALL_COLUMNS.filter(c => !c.fixed).map(c => c.key)
  const [hidden, setHidden] = useState<Set<ColKey>>(new Set())
  const [menuOpen, setMenuOpen] = useState(false)

  // Restore saved hidden-column set on mount.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) setHidden(new Set(JSON.parse(raw) as ColKey[]))
    } catch { /* ignore malformed storage */ }
  }, [])

  function toggleCol(key: ColKey) {
    setHidden(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...next])) } catch { /* ignore */ }
      return next
    })
  }

  const visible = ALL_COLUMNS.filter(c => c.fixed || !hidden.has(c.key))
```

- [ ] **Step 2: Add the column-config dropdown to the header**

In the header `<div>` (next to the "View all →" link), add a columns button + dropdown before the `<Link>`:

```tsx
        <div className="flex items-center gap-3">
          <div className="relative">
            <button onClick={() => setMenuOpen(o => !o)}
              className="text-[11px] text-[#1a1814]/55 font-semibold hover:text-[#1a1814] border border-[#ede9e2] rounded-lg px-2 py-1">
              Columns ▾
            </button>
            {menuOpen && (
              <div className="absolute right-0 mt-1 z-10 bg-white border border-[#ede9e2] rounded-lg shadow-lg p-2 min-w-[160px]">
                {ALL_COLUMNS.filter(c => !c.fixed).map(c => (
                  <label key={c.key} className="flex items-center gap-2 px-2 py-1 text-xs text-[#1a1814]/80 cursor-pointer hover:bg-[#faf8f4] rounded">
                    <input type="checkbox" checked={!hidden.has(c.key)} onChange={() => toggleCol(c.key)} />
                    {c.label}
                  </label>
                ))}
              </div>
            )}
          </div>
          <Link href="/journal" className="text-[11px] text-[#b8943f] font-semibold hover:text-[#8a6d2e]">View all →</Link>
        </div>
```

(Replace the lone `<Link …>View all →</Link>` in the header with this wrapper. `toggleableKeys` is unused if you prefer — omit it; the dropdown maps `ALL_COLUMNS.filter(c => !c.fixed)` directly.)

- [ ] **Step 2b:** Remove the now-unused `toggleableKeys` line if you didn't reference it (avoid a lint no-unused-vars error).

- [ ] **Step 3: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors in `RecentTransactions.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/RecentTransactions.tsx
git commit -m "feat(dashboard): user-selectable Recent Transactions columns persisted to localStorage (#41)"
```

---

### Task 3: Voucher-type filter, date sort, quick search

**Files:**
- Modify: `frontend/src/components/RecentTransactions.tsx`

- [ ] **Step 1: Add filter/sort/search state + derived rows**

In `RecentTransactions.tsx`, add state below the existing hooks:

```tsx
  const [vtypeFilter, setVtypeFilter] = useState<string>("")   // "" = All
  const [search, setSearch] = useState("")
  const [newestFirst, setNewestFirst] = useState(true)
```

Then derive the displayed rows from the loaded `rows`. After `rows` is known (guard for null), compute:

```tsx
  const present = Array.from(new Set((rows ?? []).map(r => r.voucher_type))).sort()
  const q = search.trim().toLowerCase()
  const shown = (rows ?? [])
    .filter(r => !vtypeFilter || r.voucher_type === vtypeFilter)
    .filter(r => !q || r.jv_number.toLowerCase().includes(q) || r.account_name.toLowerCase().includes(q) || (r.description ?? "").toLowerCase().includes(q))
    .sort((a, b) => newestFirst ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date))
```

Render the table body from `shown` instead of `rows` (change `rows.map(...)` in the `<tbody>` to `shown.map(...)`), and base the empty-state on `shown.length === 0` while keeping the loading guard on `rows === null`.

- [ ] **Step 2: Add the controls bar**

Between the header `<div>` and the table `<div className="overflow-x-auto">`, insert a controls row:

```tsx
      <div className="px-5 py-2.5 border-b border-[#ede9e2] flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search voucher, account, narration…"
          className="flex-1 min-w-[160px] text-xs border border-[#ede9e2] rounded-lg px-2.5 py-1.5 bg-[#f6f3ee] outline-none focus:ring-2 focus:ring-[#b8943f]"
        />
        <select value={vtypeFilter} onChange={e => setVtypeFilter(e.target.value)}
          className="text-xs border border-[#ede9e2] rounded-lg px-2 py-1.5 bg-[#f6f3ee] outline-none">
          <option value="">All types</option>
          {present.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button onClick={() => setNewestFirst(v => !v)}
          className="text-xs border border-[#ede9e2] rounded-lg px-2.5 py-1.5 text-[#1a1814]/70 hover:bg-[#faf8f4]">
          Date {newestFirst ? "↓" : "↑"}
        </button>
      </div>
```

(`present` — the distinct voucher types in the loaded window — drives the filter options, so it works regardless of any catalog/code mismatch.)

- [ ] **Step 3: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors in `RecentTransactions.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/RecentTransactions.tsx
git commit -m "feat(dashboard): voucher-type filter, date sort, quick search on Recent Transactions (#41)"
```

---

### Task 4: Final verification

- [ ] **Step 1: Full frontend lint**

Run: `cd frontend && npm run lint`
Expected: no new errors in `RecentTransactions.tsx` or `dashboard/page.tsx` (pre-existing warnings elsewhere are fine).

- [ ] **Step 2: Manual smoke (if running the app)**

Confirm: widget loads recent rows; the Columns dropdown hides/shows columns and the choice survives a reload; the voucher-type filter, Date sort toggle, and search all narrow the rows; clicking a Voucher No opens `/journal?jv=…`; reversed rows are visually muted.

- [ ] **Step 3: Done** — no commit needed if lint is clean and no fixes were required.

---

## Self-Review notes

- **Spec coverage:** §1 data source → Task 1 fetch; §2 component + columns + persistence → Tasks 1-2; §3 filter/sort/search → Task 3; §4 click-to-open → Task 1 (`/journal?jv=`); §5 verification → each task's lint + Task 4.
- **Type consistency:** `JournalRow`, `ColKey`, `ALL_COLUMNS`, `RowCell`, `visible`, `shown`, `present`, `hidden`, `vtypeFilter`, `search`, `newestFirst` defined in Task 1/2/3 and reused consistently; table body switches `rows.map` → `shown.map` in Task 3.
- **No backend change** — backend suite unaffected; verification is lint + manual (frontend has no unit-test harness).
- **Catalog robustness:** filter options come from the distinct `voucher_type`s actually present in the loaded rows, so seeded values like `PU` (not in `voucherTypes.ts`) still appear and filter correctly; `voucherTypeBadgeClass` falls back to a neutral badge for unknown codes.
