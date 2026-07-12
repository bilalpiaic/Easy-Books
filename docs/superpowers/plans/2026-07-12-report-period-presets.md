# Report Period Presets (#141) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** QuickBooks-style 26-preset date-range dropdown, fiscal-year- and week-start-aware, shared by every report screen (spec: `docs/superpowers/specs/2026-07-12-report-period-presets-design.md`).

**Architecture:** Pure resolver in `src/lib/datePresets.ts` (vitest-tested) → `components/DateRangePicker.tsx` rewritten in place with an unchanged prop contract (14 existing consumers upgrade free) → hand-rolled from/to filters on report pages swapped for the component. New `week_start_day` tenant setting.

**Tech Stack:** Next.js 16 / React 19 / TypeScript, Tailwind v4, vitest (new devDep, pure Node), FastAPI settings KV.

## Global Constraints

- Branch: `feat/report-period-presets` off `main`.
- Frontend checks: `cd frontend && npm run lint && npm run build`. New unit tests: `npm run test` (vitest).
- Backend tests: `cd backend && PYTHONPATH=. uv run pytest` — 2 pre-existing failures (`test_account_hierarchy`, `test_update_migration`) are the baseline.
- Dates in UI always render via `fmtDate`/`fmtDateJs` (`dd-mm-yy`); resolver emits ISO `YYYY-MM-DD` for API params.
- All date math is local-time with day-clamped month arithmetic; no new runtime dependency.
- Only **range filters driving report queries** are converted in the sweep. Document forms and single-date "as of" filters stay untouched. If a page's date inputs turn out not to be a range filter on inspection, skip it and note it in the commit message.
- Next.js 16: check `node_modules/next/dist/docs/` conventions before non-trivial frontend changes (`frontend/AGENTS.md`).

---

### Task 1: `week_start_day` setting

**Files:**
- Modify: `backend/routers/settings.py` (add field to `SettingsUpdate`, ~line 55)
- Modify: `frontend/src/context/SettingsContext.tsx` (interface + defaults)
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx` (dropdown next to Fiscal Year Start)
- Test: `backend/tests/test_week_start_setting.py` (create)

**Interfaces:**
- Produces: settings key `week_start_day` (string day name, default `"Monday"`), readable via `useSettings().settings.week_start_day`.

- [ ] **Step 1: Write the failing backend test**

```python
"""#141 — week_start_day setting round-trips through the settings KV."""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> dict:
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co", "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_week_start_day_roundtrip(client: TestClient):
    auth = _signup(client, "ws1@t.com")
    r = client.patch("/api/settings", headers=auth, json={"week_start_day": "Sunday"})
    assert r.status_code == 200
    assert client.get("/api/settings", headers=auth).json().get("week_start_day") == "Sunday"
```

- [ ] **Step 2: Run it — expect FAIL** (`week_start_day` missing from response): `PYTHONPATH=. uv run pytest tests/test_week_start_setting.py -v`

- [ ] **Step 3: Implement**

`backend/routers/settings.py` — add to `SettingsUpdate`:

```python
    # Report period presets (#141): first day of week for This/Last/Next Week
    week_start_day: Optional[str] = None
```

`frontend/src/context/SettingsContext.tsx` — add `week_start_day: string` to `AppSettings` and `week_start_day: "Monday"` to `defaults`.

`frontend/src/app/(dashboard)/settings/page.tsx` — add next to the Fiscal Year Start field (same card, same select styling as fiscal_year_start's month dropdown):

```tsx
<div>
  <label className="block text-sm font-medium mb-1">Week Starts On</label>
  <select
    value={form.week_start_day}
    onChange={(e) => setForm({ ...form, week_start_day: e.target.value })}
    className={/* copy the fiscal_year_start select's className verbatim */}
  >
    {["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"].map((d) => (
      <option key={d} value={d}>{d}</option>
    ))}
  </select>
  <p className="text-xs text-[var(--text-muted)] mt-1">Used by report period presets (This/Last/Next Week).</p>
</div>
```

(Follow the page's actual form-state idiom — read how `fiscal_year_start` is bound and mirror it exactly, including its save handler membership.)

- [ ] **Step 4: Run tests — expect PASS**: `PYTHONPATH=. uv run pytest tests/test_week_start_setting.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/routers/settings.py backend/tests/test_week_start_setting.py frontend/src/context/SettingsContext.tsx "frontend/src/app/(dashboard)/settings/page.tsx"
git commit -m "feat(settings): week_start_day setting (default Monday) for report period presets (#141)"
```

---

### Task 2: vitest + `datePresets.ts` resolver

**Files:**
- Modify: `frontend/package.json` (devDep `vitest`, script `"test": "vitest run"`)
- Create: `frontend/src/lib/datePresets.ts`
- Test: `frontend/src/lib/__tests__/datePresets.test.ts`

**Interfaces:**
- Produces (consumed by Task 3):
  - `PRESETS: { id: PresetId; label: string }[]` — QB order, 26 entries ending in `custom`
  - `resolvePreset(id: PresetId, opts: PresetOpts): { start: string; end: string } | null`
  - `matchPreset(start: string, end: string, opts: PresetOpts): PresetId | null`
  - `fiscalStartMonthFromSetting(v?: string): number`, `weekStartFromSetting(v?: string): number`
  - `PresetOpts = { today?: Date; fiscalStartMonth: number; weekStartDay?: number }`

- [ ] **Step 1: Install vitest and add script**

```bash
cd frontend && npm install -D vitest
```

Add to `package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 2: Write the failing tests** (`src/lib/__tests__/datePresets.test.ts`)

```ts
import { describe, expect, it } from "vitest"
import {
  PRESETS, resolvePreset, matchPreset,
  fiscalStartMonthFromSetting, weekStartFromSetting,
} from "../datePresets"

// Wed 2026-07-15; fiscal year starts July (like a Pakistani FY tenant)
const T = new Date(2026, 6, 15)
const julyFY = { today: T, fiscalStartMonth: 7 }
const calFY = { today: T, fiscalStartMonth: 1 }

const r = (id: any, opts = julyFY) => resolvePreset(id, opts)

describe("setting parsers", () => {
  it("parses month names and falls back to January", () => {
    expect(fiscalStartMonthFromSetting("July")).toBe(7)
    expect(fiscalStartMonthFromSetting("nonsense")).toBe(1)
    expect(fiscalStartMonthFromSetting(undefined)).toBe(1)
  })
  it("parses week days and falls back to Monday", () => {
    expect(weekStartFromSetting("Sunday")).toBe(0)
    expect(weekStartFromSetting("Saturday")).toBe(6)
    expect(weekStartFromSetting(undefined)).toBe(1)
  })
})

describe("simple presets", () => {
  it("today / yesterday", () => {
    expect(r("today")).toEqual({ start: "2026-07-15", end: "2026-07-15" })
    expect(r("yesterday")).toEqual({ start: "2026-07-14", end: "2026-07-14" })
  })
  it("all is unbounded, custom is null", () => {
    expect(r("all")).toEqual({ start: "", end: "" })
    expect(r("custom")).toBeNull()
  })
})

describe("weeks respect week_start_day", () => {
  it("Monday start (default)", () => {
    expect(r("this_week")).toEqual({ start: "2026-07-13", end: "2026-07-19" })
    expect(r("this_week_to_date")).toEqual({ start: "2026-07-13", end: "2026-07-15" })
    expect(r("last_week")).toEqual({ start: "2026-07-06", end: "2026-07-12" })
    expect(r("last_week_to_date")).toEqual({ start: "2026-07-06", end: "2026-07-08" })
    expect(r("next_week")).toEqual({ start: "2026-07-20", end: "2026-07-26" })
  })
  it("Sunday start", () => {
    const opts = { ...julyFY, weekStartDay: 0 }
    expect(r("this_week", opts)).toEqual({ start: "2026-07-12", end: "2026-07-18" })
  })
  it("Saturday start", () => {
    const opts = { ...julyFY, weekStartDay: 6 }
    expect(r("this_week", opts)).toEqual({ start: "2026-07-11", end: "2026-07-17" })
  })
})

describe("months", () => {
  it("this / last / next month", () => {
    expect(r("this_month")).toEqual({ start: "2026-07-01", end: "2026-07-31" })
    expect(r("this_month_to_date")).toEqual({ start: "2026-07-01", end: "2026-07-15" })
    expect(r("last_month")).toEqual({ start: "2026-06-01", end: "2026-06-30" })
    expect(r("last_month_to_date")).toEqual({ start: "2026-06-01", end: "2026-06-15" })
    expect(r("next_month")).toEqual({ start: "2026-08-01", end: "2026-08-31" })
  })
  it("month-end clamping: Jul 31 → last_month_to_date ends Jun 30", () => {
    const opts = { ...julyFY, today: new Date(2026, 6, 31) }
    expect(r("last_month_to_date", opts)).toEqual({ start: "2026-06-01", end: "2026-06-30" })
  })
  it("leap-year clamping: Mar 30 2028 → Feb 29", () => {
    const opts = { ...calFY, today: new Date(2028, 2, 30) }
    expect(r("last_month_to_date", opts)).toEqual({ start: "2028-02-01", end: "2028-02-29" })
  })
})

describe("fiscal periods (July FY)", () => {
  it("this fiscal quarter/year", () => {
    expect(r("this_fiscal_quarter")).toEqual({ start: "2026-07-01", end: "2026-09-30" })
    expect(r("this_fiscal_quarter_to_date")).toEqual({ start: "2026-07-01", end: "2026-07-15" })
    expect(r("this_fiscal_year")).toEqual({ start: "2026-07-01", end: "2027-06-30" })
    expect(r("this_fiscal_year_to_date")).toEqual({ start: "2026-07-01", end: "2026-07-15" })
  })
  it("last / next fiscal quarter and year", () => {
    expect(r("last_fiscal_quarter")).toEqual({ start: "2026-04-01", end: "2026-06-30" })
    expect(r("last_fiscal_quarter_to_date")).toEqual({ start: "2026-04-01", end: "2026-04-15" })
    expect(r("last_fiscal_year")).toEqual({ start: "2025-07-01", end: "2026-06-30" })
    expect(r("last_fiscal_year_to_date")).toEqual({ start: "2025-07-01", end: "2025-07-15" })
    expect(r("next_fiscal_quarter")).toEqual({ start: "2026-10-01", end: "2026-12-31" })
    expect(r("next_fiscal_year")).toEqual({ start: "2027-07-01", end: "2028-06-30" })
  })
  it("fiscal-year-to-last-month clamps in FY's first month", () => {
    // T inside first FY month: end (Jun 30) < FY start (Jul 1) → clamp to start
    expect(r("this_fiscal_year_to_last_month")).toEqual({ start: "2026-07-01", end: "2026-07-01" })
    // Later in the FY it behaves normally
    const oct = { ...julyFY, today: new Date(2026, 9, 10) }
    expect(r("this_fiscal_year_to_last_month", oct)).toEqual({ start: "2026-07-01", end: "2026-09-30" })
  })
  it("calendar FY (January) matches calendar quarters", () => {
    expect(r("this_fiscal_quarter", calFY)).toEqual({ start: "2026-07-01", end: "2026-09-30" })
    expect(r("this_fiscal_year", calFY)).toEqual({ start: "2026-01-01", end: "2026-12-31" })
  })
})

describe("next 4 weeks", () => {
  it("is a 28-day window from today", () => {
    expect(r("next_4_weeks")).toEqual({ start: "2026-07-15", end: "2026-08-11" })
  })
})

describe("matchPreset", () => {
  it("round-trips every resolvable preset", () => {
    for (const p of PRESETS) {
      if (p.id === "custom") continue
      const range = resolvePreset(p.id, julyFY)!
      const back = matchPreset(range.start, range.end, julyFY)
      // earlier presets in QB order may produce identical ranges; the match
      // must at least resolve to the SAME range
      expect(resolvePreset(back!, julyFY)).toEqual(range)
    }
  })
  it("returns null for a range no preset produces", () => {
    expect(matchPreset("2026-01-03", "2026-01-09", julyFY)).toBeNull()
  })
  it("PRESETS has the QB list, 26 entries, custom last", () => {
    expect(PRESETS).toHaveLength(26)
    expect(PRESETS[0].id).toBe("all")
    expect(PRESETS[PRESETS.length - 1].id).toBe("custom")
  })
})
```

- [ ] **Step 3: Run — expect FAIL (module missing)**: `npm run test`

- [ ] **Step 4: Implement `src/lib/datePresets.ts`**

```ts
// QuickBooks-style report period presets (#141).
// Pure date math — no React, no I/O. All local-time; ISO YYYY-MM-DD out.

export type PresetId =
  | "all" | "today"
  | "this_week" | "this_week_to_date"
  | "this_month" | "this_month_to_date"
  | "this_fiscal_quarter" | "this_fiscal_quarter_to_date"
  | "this_fiscal_year" | "this_fiscal_year_to_last_month" | "this_fiscal_year_to_date"
  | "yesterday"
  | "last_week" | "last_week_to_date"
  | "last_month" | "last_month_to_date"
  | "last_fiscal_quarter" | "last_fiscal_quarter_to_date"
  | "last_fiscal_year" | "last_fiscal_year_to_date"
  | "next_week" | "next_4_weeks" | "next_month"
  | "next_fiscal_quarter" | "next_fiscal_year"
  | "custom"

export interface PresetOpts {
  today?: Date
  fiscalStartMonth: number // 1-12
  weekStartDay?: number    // 0=Sunday … 6=Saturday; default 1 (Monday)
}

export const PRESETS: { id: PresetId; label: string }[] = [
  { id: "all", label: "All" },
  { id: "today", label: "Today" },
  { id: "this_week", label: "This Week" },
  { id: "this_week_to_date", label: "This Week-to-date" },
  { id: "this_month", label: "This Month" },
  { id: "this_month_to_date", label: "This Month-to-date" },
  { id: "this_fiscal_quarter", label: "This Fiscal Quarter" },
  { id: "this_fiscal_quarter_to_date", label: "This Fiscal Quarter-to-date" },
  { id: "this_fiscal_year", label: "This Fiscal Year" },
  { id: "this_fiscal_year_to_last_month", label: "This Fiscal Year-to-Last Month" },
  { id: "this_fiscal_year_to_date", label: "This Fiscal Year-to-date" },
  { id: "yesterday", label: "Yesterday" },
  { id: "last_week", label: "Last Week" },
  { id: "last_week_to_date", label: "Last Week-to-date" },
  { id: "last_month", label: "Last Month" },
  { id: "last_month_to_date", label: "Last Month-to-date" },
  { id: "last_fiscal_quarter", label: "Last Fiscal Quarter" },
  { id: "last_fiscal_quarter_to_date", label: "Last Fiscal Quarter-to-date" },
  { id: "last_fiscal_year", label: "Last Fiscal Year" },
  { id: "last_fiscal_year_to_date", label: "Last Fiscal Year-to-date" },
  { id: "next_week", label: "Next Week" },
  { id: "next_4_weeks", label: "Next 4 Weeks" },
  { id: "next_month", label: "Next Month" },
  { id: "next_fiscal_quarter", label: "Next Fiscal Quarter" },
  { id: "next_fiscal_year", label: "Next Fiscal Year" },
  { id: "custom", label: "Custom" },
]

const MONTHS = ["january","february","march","april","may","june",
  "july","august","september","october","november","december"]
const DAYS = ["sunday","monday","tuesday","wednesday","thursday","friday","saturday"]

export function fiscalStartMonthFromSetting(v?: string): number {
  const i = MONTHS.indexOf((v ?? "").trim().toLowerCase())
  return i === -1 ? 1 : i + 1
}

export function weekStartFromSetting(v?: string): number {
  const i = DAYS.indexOf((v ?? "").trim().toLowerCase())
  return i === -1 ? 1 : i
}

const pad = (n: number) => String(n).padStart(2, "0")
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const mk = (y: number, m: number, day: number) => new Date(y, m, day) // m 0-based; overflow-normalizing
const addDays = (d: Date, n: number) => mk(d.getFullYear(), d.getMonth(), d.getDate() + n)
const monthEndDay = (y: number, m: number) => mk(y, m + 1, 0).getDate()
/** first day of the month n months away */
const monthStart = (d: Date, n = 0) => mk(d.getFullYear(), d.getMonth() + n, 1)
/** same day n months away, clamped to that month's length (Mar 31 −1mo → Feb 28/29) */
const addMonthsClamped = (d: Date, n: number) => {
  const s = monthStart(d, n)
  return mk(s.getFullYear(), s.getMonth(), Math.min(d.getDate(), monthEndDay(s.getFullYear(), s.getMonth())))
}
const weekStart = (d: Date, ws: number) => addDays(d, -((d.getDay() - ws + 7) % 7))
/** first day of the fiscal year containing d */
const fyStart = (d: Date, fm: number) => {
  const s = mk(d.getFullYear(), fm - 1, 1)
  return s <= d ? s : mk(d.getFullYear() - 1, fm - 1, 1)
}
/** first day of the fiscal quarter containing d */
const fqStart = (d: Date, fm: number) => {
  const fy = fyStart(d, fm)
  const monthsIn = (d.getFullYear() - fy.getFullYear()) * 12 + d.getMonth() - fy.getMonth()
  return monthStart(fy, Math.floor(monthsIn / 3) * 3)
}
const range = (a: Date, b: Date) => ({ start: iso(a), end: iso(b) })
/** full period starting at s, len months */
const period = (s: Date, len: number) => range(s, addDays(monthStart(s, len), -1))
const min = (a: Date, b: Date) => (a <= b ? a : b)
const max = (a: Date, b: Date) => (a >= b ? a : b)

export function resolvePreset(id: PresetId, opts: PresetOpts): { start: string; end: string } | null {
  const T0 = opts.today ?? new Date()
  const T = mk(T0.getFullYear(), T0.getMonth(), T0.getDate()) // normalize to midnight
  const ws = opts.weekStartDay ?? 1
  const fm = opts.fiscalStartMonth

  switch (id) {
    case "all": return { start: "", end: "" }
    case "custom": return null
    case "today": return range(T, T)
    case "yesterday": return range(addDays(T, -1), addDays(T, -1))

    case "this_week": return range(weekStart(T, ws), addDays(weekStart(T, ws), 6))
    case "this_week_to_date": return range(weekStart(T, ws), T)
    case "last_week": return range(addDays(weekStart(T, ws), -7), addDays(weekStart(T, ws), -1))
    case "last_week_to_date": return range(addDays(weekStart(T, ws), -7), addDays(T, -7))
    case "next_week": return range(addDays(weekStart(T, ws), 7), addDays(weekStart(T, ws), 13))
    case "next_4_weeks": return range(T, addDays(T, 27))

    case "this_month": return period(monthStart(T), 1)
    case "this_month_to_date": return range(monthStart(T), T)
    case "last_month": return period(monthStart(T, -1), 1)
    case "last_month_to_date":
      return range(monthStart(T, -1), addMonthsClamped(T, -1))
    case "next_month": return period(monthStart(T, 1), 1)

    case "this_fiscal_quarter": return period(fqStart(T, fm), 3)
    case "this_fiscal_quarter_to_date": return range(fqStart(T, fm), T)
    case "last_fiscal_quarter": return period(monthStart(fqStart(T, fm), -3), 3)
    case "last_fiscal_quarter_to_date": {
      const s = monthStart(fqStart(T, fm), -3)
      return range(s, max(s, min(addMonthsClamped(T, -3), addDays(monthStart(s, 3), -1))))
    }
    case "next_fiscal_quarter": return period(monthStart(fqStart(T, fm), 3), 3)

    case "this_fiscal_year": return period(fyStart(T, fm), 12)
    case "this_fiscal_year_to_date": return range(fyStart(T, fm), T)
    case "this_fiscal_year_to_last_month": {
      const s = fyStart(T, fm)
      return range(s, max(s, addDays(monthStart(T), -1)))
    }
    case "last_fiscal_year": return period(monthStart(fyStart(T, fm), -12), 12)
    case "last_fiscal_year_to_date": {
      const s = monthStart(fyStart(T, fm), -12)
      return range(s, max(s, min(addMonthsClamped(T, -12), addDays(monthStart(s, 12), -1))))
    }
    case "next_fiscal_year": return period(monthStart(fyStart(T, fm), 12), 12)
  }
}

export function matchPreset(start: string, end: string, opts: PresetOpts): PresetId | null {
  for (const p of PRESETS) {
    if (p.id === "custom") continue
    const r = resolvePreset(p.id, opts)
    if (r && r.start === start && r.end === end) return p.id
  }
  return null
}
```

- [ ] **Step 5: Run — expect PASS**: `npm run test`

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/datePresets.ts frontend/src/lib/__tests__/datePresets.test.ts
git commit -m "feat(reports): datePresets resolver — 26 QB presets, fiscal + week-start aware, vitest (#141)"
```

---

### Task 3: rewrite `DateRangePicker.tsx`

**Files:**
- Modify: `frontend/src/components/DateRangePicker.tsx` (full rewrite)

**Interfaces:**
- Consumes: everything Task 2 produces; `useSettings()` (`{ settings }`); `fmtDate` from `@/lib/utils`.
- Produces: same props as before + optional `hideAll?: boolean`. Existing 14 consumers compile unchanged.

- [ ] **Step 1: Rewrite the component**

```tsx
"use client"

import { useMemo, useState } from "react"
import { Calendar } from "lucide-react"
import { useSettings } from "@/context/SettingsContext"
import { fmtDate } from "@/lib/utils"
import {
  PRESETS, PresetId, resolvePreset, matchPreset,
  fiscalStartMonthFromSetting, weekStartFromSetting,
} from "@/lib/datePresets"

interface DateRangePickerProps {
  start: string
  end: string
  onStartChange: (v: string) => void
  onEndChange: (v: string) => void
  label?: string
  hideAll?: boolean
}

export default function DateRangePicker({
  start, end, onStartChange, onEndChange, label = "Period", hideAll = false,
}: DateRangePickerProps) {
  const { settings } = useSettings()
  const opts = useMemo(() => ({
    fiscalStartMonth: fiscalStartMonthFromSetting(settings.fiscal_year_start),
    weekStartDay: weekStartFromSetting(settings.week_start_day),
  }), [settings.fiscal_year_start, settings.week_start_day])

  // Dropdown state derives from the incoming dates so deep links and
  // externally-changed ranges show the right preset. A manual "Custom"
  // choice is sticky until the user picks a preset again.
  const [manualCustom, setManualCustom] = useState(false)
  const matched = useMemo(() => matchPreset(start, end, opts), [start, end, opts])
  const selected: PresetId = manualCustom ? "custom" : (matched ?? "custom")

  const presets = hideAll ? PRESETS.filter((p) => p.id !== "all") : PRESETS

  const pick = (id: PresetId) => {
    if (id === "custom") { setManualCustom(true); return }
    setManualCustom(false)
    const r = resolvePreset(id, opts)
    if (r) { onStartChange(r.start); onEndChange(r.end) }
  }

  const inputCls =
    "px-3 py-1.5 text-sm border border-[var(--border)] rounded-lg focus:outline-none " +
    "focus:ring-2 focus:ring-[var(--primary)] disabled:opacity-60 disabled:cursor-not-allowed"
  const hint =
    selected === "all" ? "All dates"
    : start && end ? `${fmtDate(start)} – ${fmtDate(end)}`
    : ""

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Calendar className="w-4 h-4 text-[var(--text-muted)]" />
      <span className="text-xs font-bold uppercase tracking-widest text-[var(--text-muted)]">{label}</span>
      <select
        value={selected}
        onChange={(e) => pick(e.target.value as PresetId)}
        className={inputCls}
      >
        {presets.map((p) => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
      </select>
      <input
        type="date" value={start} disabled={selected !== "custom"}
        onChange={(e) => onStartChange(e.target.value)} className={inputCls}
      />
      <span className="text-[var(--text-muted)] text-sm">to</span>
      <input
        type="date" value={end} disabled={selected !== "custom"}
        onChange={(e) => onEndChange(e.target.value)} className={inputCls}
      />
      {hint && <span className="text-xs text-[var(--text-muted)]">{hint}</span>}
    </div>
  )
}
```

Note: when the incoming dates happen to equal a preset's range, the dropdown shows that preset (QB behaves the same); `manualCustom` keeps an explicit Custom choice from snapping back mid-edit.

- [ ] **Step 2: Build + lint**: `npm run lint && npm run build` — expect clean; all 14 consumers compile untouched.

- [ ] **Step 3: Manual verify** on `/trial-balance` (uses DateRangePicker): presets fill From/To and disable them; Custom re-enables; hint label shows `dd-mm-yy` range; a July fiscal tenant (`demo.pra` or set Settings → Fiscal Year Start = July) shifts the fiscal presets.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/DateRangePicker.tsx
git commit -m "feat(reports): QB-style preset dropdown in DateRangePicker — same prop contract (#141)"
```

---

### Task 4: sweep — core + AR/AP report pages

**Files (modify each; convert only paired from/to range filters):**
- `app/(dashboard)/customers/[id]/statement/page.tsx`
- `app/(dashboard)/vendors/[id]/statement/page.tsx`
- `app/(dashboard)/audit/page.tsx`
- `app/(dashboard)/deferred-revenue/page.tsx`
- `app/(dashboard)/commissions/page.tsx`
- `app/(dashboard)/analytic-accounts/[id]/page.tsx`
- `app/(dashboard)/attendance/report/page.tsx`
- `app/(dashboard)/promo-discounts/page.tsx`
- `app/(dashboard)/telecom/page.tsx`
- `app/(dashboard)/advances/page.tsx`
- `app/(dashboard)/credit-notes/page.tsx`
- `app/(dashboard)/debit-notes/page.tsx`
- `app/(dashboard)/reconciliations/page.tsx`
- `app/(dashboard)/recurring/page.tsx`

**Recipe (worked example — customer statement, lines 86-93):** replace

```tsx
<div className="flex items-center gap-2 text-sm">
  <label className="text-[var(--text-muted)]">From</label>
  <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="..." />
  <label className="text-[var(--text-muted)]">To</label>
  <input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="..." />
</div>
```

with

```tsx
<DateRangePicker start={fromDate} end={toDate} onStartChange={setFromDate} onEndChange={setToDate} />
```

plus `import DateRangePicker from "@/components/DateRangePicker"`. Keep the page's state names, defaults, and fetch triggers exactly as they are (setters unchanged ⇒ existing `useEffect`/refetch wiring keeps working). Statements require a bounded period → pass `hideAll` there; list-filter pages (credit/debit notes, advances, audit) may keep All.

- [ ] **Step 1:** Convert each file per the recipe. For any file whose date inputs are NOT a from/to range filter (single-date form fields), skip and note in the commit message.
- [ ] **Step 2:** `npm run lint && npm run build` — clean.
- [ ] **Step 3:** Commit:

```bash
git add "frontend/src/app/(dashboard)"
git commit -m "feat(reports): adopt preset DateRangePicker across core/AR/AP report filters (#141)"
```

---

### Task 5: sweep — purchases, store, healthcare report pages

**Files (same recipe as Task 4):**
- `app/(dashboard)/purchases/gate-register/page.tsx`
- `app/(dashboard)/purchases/three-way-match/page.tsx`
- `app/(dashboard)/purchases/vendor-performance/page.tsx`
- `app/(dashboard)/store/issue-register/page.tsx`
- `app/(dashboard)/store/gate-outward-register/page.tsx`
- `app/(dashboard)/store/dispatch-reconciliation/page.tsx`
- `app/(dashboard)/store/stock-tie-out/page.tsx`
- `app/(dashboard)/healthcare/reports/page.tsx`
- `app/(dashboard)/healthcare/opd/page.tsx`
- `app/(dashboard)/healthcare/ipd/page.tsx`
- `app/(dashboard)/healthcare/lab/page.tsx`
- `app/(dashboard)/healthcare/patients/page.tsx`
- `app/(dashboard)/healthcare/procedures/page.tsx`
- `app/(dashboard)/healthcare/store/page.tsx`

Note the grid-style filter layout on these pages (label-above-input inside a grid cell, e.g. gate-register lines 73-90): replace the two grid cells with ONE cell spanning two columns containing `<DateRangePicker …/>`, or place the component above the grid — match each page's visual rhythm, don't force the inline layout where the grid looks better. Stock Tie-out: its `end` param intentionally disables reconciliation columns — keep its explanatory hint text as-is.

- [ ] **Step 1:** Convert each file; skip non-range files with a commit-message note.
- [ ] **Step 2:** `npm run lint && npm run build` — clean.
- [ ] **Step 3:** Commit:

```bash
git add "frontend/src/app/(dashboard)"
git commit -m "feat(reports): adopt preset DateRangePicker on purchases/store/healthcare reports (#141)"
```

---

### Task 6: verification + docs

**Files:**
- Modify: `CLAUDE.md` (Settings System bullet list — add `week_start_day`; note DateRangePicker presets)
- Modify: `BLUEPRINT.md` (sprint delta entry for #141)

- [ ] **Step 1:** `cd frontend && npm run test && npm run lint && npm run build` — all clean.
- [ ] **Step 2:** `cd backend && PYTHONPATH=. uv run pytest` — baseline (2 pre-existing failures only).
- [ ] **Step 3:** Manual drive (dev server): Trial Balance + GL + one statement + one store register with presets incl. a fiscal preset under Fiscal Year Start = July and Week Starts On = Sunday.
- [ ] **Step 4:** Update CLAUDE.md (add `week_start_day` to the settings list; one line on DateRangePicker's preset behavior) and BLUEPRINT.md (delta entry).
- [ ] **Step 5:** Commit + PR:

```bash
git add CLAUDE.md BLUEPRINT.md
git commit -m "docs: report period presets (#141) — settings + component notes"
```
