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

const MONTHS = ["january", "february", "march", "april", "may", "june",
  "july", "august", "september", "october", "november", "december"]
const DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

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
const dmin = (a: Date, b: Date) => (a <= b ? a : b)
const dmax = (a: Date, b: Date) => (a >= b ? a : b)

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
      return range(s, dmax(s, dmin(addMonthsClamped(T, -3), addDays(monthStart(s, 3), -1))))
    }
    case "next_fiscal_quarter": return period(monthStart(fqStart(T, fm), 3), 3)

    case "this_fiscal_year": return period(fyStart(T, fm), 12)
    case "this_fiscal_year_to_date": return range(fyStart(T, fm), T)
    case "this_fiscal_year_to_last_month": {
      const s = fyStart(T, fm)
      return range(s, dmax(s, addDays(monthStart(T), -1)))
    }
    case "last_fiscal_year": return period(monthStart(fyStart(T, fm), -12), 12)
    case "last_fiscal_year_to_date": {
      const s = monthStart(fyStart(T, fm), -12)
      return range(s, dmax(s, dmin(addMonthsClamped(T, -12), addDays(monthStart(s, 12), -1))))
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
