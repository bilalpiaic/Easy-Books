import { describe, expect, it } from "vitest"
import { fmtDate, fmtDateJs, fmtDateTime, fmtDateTimeJs } from "../utils"

describe("fmtDate", () => {
  it("formats ISO calendar dates as dd-mmm-yy", () => {
    expect(fmtDate("2026-06-20")).toBe("20-Jun-26")
    expect(fmtDate("2026-10-11")).toBe("11-Oct-26")
    expect(fmtDate("2026-01-01")).toBe("01-Jan-26")
  })

  it("strips a datetime suffix and keeps the calendar day", () => {
    expect(fmtDate("2026-10-11T14:30:00")).toBe("11-Oct-26")
    expect(fmtDate("2026-10-11T14:30:00Z")).toBe("11-Oct-26")
  })

  it("is idempotent for already-formatted values", () => {
    expect(fmtDate("11-Oct-26")).toBe("11-Oct-26")
  })

  it("returns empty / original for missing or odd input", () => {
    expect(fmtDate("")).toBe("")
    expect(fmtDate(null)).toBe("")
    expect(fmtDate(undefined)).toBe("")
    expect(fmtDate("not-a-date")).toBe("not-a-date")
  })
})

describe("fmtDateJs", () => {
  it("formats a local Date as dd-mmm-yy", () => {
    expect(fmtDateJs(new Date(2026, 9, 11))).toBe("11-Oct-26")
  })
})

describe("fmtDateTime", () => {
  it("keeps date-only values without a clock", () => {
    expect(fmtDateTime("2026-10-11")).toBe("11-Oct-26")
  })

  it("appends HH:mm for datetimes", () => {
    const out = fmtDateTimeJs(new Date(2026, 9, 11, 14, 5))
    expect(out).toBe("11-Oct-26 14:05")
  })
})
