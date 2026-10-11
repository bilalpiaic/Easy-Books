import { describe, expect, it } from "vitest"
import {
  contentBoxMm,
  detectPdfOrientation,
  filenameFromHeading,
  imageHeightMm,
  mmToPx,
  pageMargins,
  pageSizeMm,
  PDF_STRIP_SELECTOR,
  pdfPageCount,
  pdfPageLabel,
  sanitizePdfFilename,
  shouldOmitFromPdf,
} from "../saveScreenPdf"

describe("sanitizePdfFilename", () => {
  it("keeps a simple stem and adds .pdf", () => {
    expect(sanitizePdfFilename("Trial Balance")).toBe("Trial-Balance.pdf")
  })

  it("strips an existing .pdf suffix", () => {
    expect(sanitizePdfFilename("invoice.pdf")).toBe("invoice.pdf")
  })

  it("drops path/punctuation and caps length", () => {
    expect(sanitizePdfFilename("Inv/2026: #12 (paid)?")).toBe("Inv2026-12-paid.pdf")
  })

  it("falls back when empty", () => {
    expect(sanitizePdfFilename("   ")).toBe("document.pdf")
    expect(sanitizePdfFilename(null)).toBe("document.pdf")
  })
})

describe("A4 geometry", () => {
  it("uses ISO A4 millimetres", () => {
    expect(pageSizeMm("portrait")).toEqual({ width: 210, height: 297 })
    expect(pageSizeMm("landscape")).toEqual({ width: 297, height: 210 })
  })

  it("keeps portrait content inside print margins", () => {
    const box = contentBoxMm("portrait")
    expect(box.left).toBe(15)
    expect(box.right).toBe(13)
    expect(box.top).toBe(14)
    expect(box.bottom).toBe(18)
    expect(box.width).toBe(210 - 15 - 13)
    expect(box.height).toBe(297 - 14 - 18)
    expect(box.width).toBeLessThan(210)
    expect(box.height).toBeLessThan(297)
  })

  it("keeps landscape content inside print margins", () => {
    const box = contentBoxMm("landscape")
    const m = pageMargins("landscape")
    expect(box.width).toBe(297 - m.left - m.right)
    expect(box.height).toBe(210 - m.top - m.bottom)
  })

  it("converts millimetres to CSS pixels at 96dpi", () => {
    expect(mmToPx(25.4)).toBe(96)
  })
})

describe("pdf pagination maths", () => {
  it("scales image height into millimetres", () => {
    expect(imageHeightMm(794, 1123, 194)).toBeCloseTo(274.5, 0)
  })

  it("uses one page when content fits", () => {
    expect(pdfPageCount(200, 265)).toBe(1)
  })

  it("splits a tall document across pages", () => {
    expect(pdfPageCount(800, 265)).toBe(4)
  })
})

describe("pdfPageLabel", () => {
  it("formats n / N for the footer", () => {
    expect(pdfPageLabel(1, 2)).toBe("1 / 2")
    expect(pdfPageLabel(2, 2)).toBe("2 / 2")
    expect(pdfPageLabel(1, 1)).toBe("1 / 1")
  })
})

describe("detectPdfOrientation", () => {
  it("is portrait by default", () => {
    const doc = { querySelector: () => null } as unknown as Document
    expect(detectPdfOrientation(doc)).toBe("portrait")
  })

  it("is landscape when PrintHeader injected the landscape marker", () => {
    const doc = { querySelector: (sel: string) => (sel.includes("print-landscape") ? {} : null) } as unknown as Document
    expect(detectPdfOrientation(doc)).toBe("landscape")
  })
})

describe("filenameFromHeading", () => {
  it("prefers h1 over the browser tab title", () => {
    const doc = {
      querySelector: () => ({ textContent: "  Balance Sheet  " }),
      title: "Dashboard — Easy-Books",
    } as unknown as Document
    expect(filenameFromHeading(doc)).toBe("Balance-Sheet.pdf")
  })
})

describe("shouldOmitFromPdf", () => {
  const fake = (opts: {
    attr?: string
    cls?: string
    tag?: string
    role?: string
  }) =>
    ({
      tagName: opts.tag,
      getAttribute: (n: string) => {
        if (opts.attr && n === opts.attr) return ""
        if (opts.role && n === "role") return opts.role
        return null
      },
      classList: { contains: (c: string) => c === opts.cls },
    }) as unknown as Element

  it("omits chrome and the print/save bar", () => {
    expect(shouldOmitFromPdf(fake({ cls: "eb-print-save-bar" }))).toBe(true)
    expect(shouldOmitFromPdf(fake({ attr: "data-eb-chrome" }))).toBe(true)
    expect(shouldOmitFromPdf(fake({ attr: "data-print-hide" }))).toBe(true)
    expect(shouldOmitFromPdf(fake({ attr: "data-eb-print-chrome" }))).toBe(true)
    expect(shouldOmitFromPdf(fake({}))).toBe(false)
  })

  it("omits filters, LOVs, and form controls", () => {
    expect(shouldOmitFromPdf(fake({ cls: "print:hidden" }))).toBe(true)
    expect(shouldOmitFromPdf(fake({ tag: "INPUT" }))).toBe(true)
    expect(shouldOmitFromPdf(fake({ tag: "SELECT" }))).toBe(true)
    expect(shouldOmitFromPdf(fake({ tag: "TEXTAREA" }))).toBe(true)
    expect(shouldOmitFromPdf(fake({ tag: "BUTTON" }))).toBe(true)
    expect(shouldOmitFromPdf(fake({ role: "tab" }))).toBe(true)
  })

  it("keeps the branded print header", () => {
    expect(shouldOmitFromPdf(fake({ cls: "print-header" }))).toBe(false)
  })

  it("keeps text nodes", () => {
    expect(shouldOmitFromPdf({} as Node)).toBe(false)
  })
})

describe("PDF_STRIP_SELECTOR", () => {
  it("targets print:hidden chrome, filters, and form controls", () => {
    expect(PDF_STRIP_SELECTOR).toContain('print:hidden')
    expect(PDF_STRIP_SELECTOR).toContain("data-eb-print-chrome")
    expect(PDF_STRIP_SELECTOR).toContain("input")
    expect(PDF_STRIP_SELECTOR).toContain("select")
  })
})
