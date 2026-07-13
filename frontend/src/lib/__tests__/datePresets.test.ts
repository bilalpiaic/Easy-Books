import { describe, expect, it } from "vitest"
import {
  PRESETS, resolvePreset, matchPreset,
  fiscalStartMonthFromSetting, weekStartFromSetting,
} from "../datePresets"

// Wed 2026-07-15; fiscal year starts July (like a Pakistani FY tenant)
const T = new Date(2026, 6, 15)
const julyFY = { today: T, fiscalStartMonth: 7 }
const calFY = { today: T, fiscalStartMonth: 1 }

type Opts = typeof julyFY & { weekStartDay?: number }
const r = (id: Parameters<typeof resolvePreset>[0], opts: Opts = julyFY) => resolvePreset(id, opts)

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
