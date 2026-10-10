import { describe, expect, it } from "vitest"
import {
  detectPdfOrientation,
  filenameFromHeading,
  imageHeightMm,
  pdfPageCount,
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

describe("pdf pagination maths", () => {
  it("scales image height into millimetres", () => {
    expect(imageHeightMm(794, 1123, 194)).toBeCloseTo(274.5, 0)
  })

  it("uses one page when content fits", () => {
    expect(pdfPageCount(200, 281)).toBe(1)
  })

  it("splits a tall snapshot across pages", () => {
    expect(pdfPageCount(800, 281)).toBe(3)
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
  it("omits chrome and the print/save bar", () => {
    const bar = { getAttribute: () => null, classList: { contains: (c: string) => c === "eb-print-save-bar" } }
    const chrome = { getAttribute: (n: string) => (n === "data-eb-chrome" ? "" : null), classList: { contains: () => false } }
    const hide = { getAttribute: (n: string) => (n === "data-print-hide" ? "" : null), classList: { contains: () => false } }
    const keep = { getAttribute: () => null, classList: { contains: () => false } }
    expect(shouldOmitFromPdf(bar as unknown as Element)).toBe(true)
    expect(shouldOmitFromPdf(chrome as unknown as Element)).toBe(true)
    expect(shouldOmitFromPdf(hide as unknown as Element)).toBe(true)
    expect(shouldOmitFromPdf(keep as unknown as Element)).toBe(false)
  })

  it("keeps text nodes", () => {
    expect(shouldOmitFromPdf({} as Node)).toBe(false)
  })
})
