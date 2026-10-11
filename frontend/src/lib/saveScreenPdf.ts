/**
 * Formatted A4 PDF save for reports, vouchers, ledgers, and forms.
 *
 * Save PDF does not snapshot the live cream/gold UI. It clones the printable
 * root, strips filters / LOVs / buttons / search chrome, reveals PrintHeader,
 * lays the clone out at A4 content width, and paginates onto A4 with margins
 * and a "Page n / N" footer.
 */

export const SAVE_PDF_CLASS = "eb-saving-pdf"
export const PDF_HOST_ATTR = "data-eb-pdf-host"

const A4_MM = { width: 210, height: 297 }
const A4_LANDSCAPE_MM = { width: 297, height: 210 }

/** Match `@media print` `@page` margins (top, right, bottom, left). */
export const PAGE_MARGINS_MM = {
  portrait: { top: 14, right: 13, bottom: 18, left: 15 },
  landscape: { top: 12, right: 12, bottom: 16, left: 12 },
} as const

export type PdfOrientation = "portrait" | "landscape"

export type PageMarginsMm = {
  top: number
  right: number
  bottom: number
  left: number
}

export function pageMargins(orientation: PdfOrientation): PageMarginsMm {
  return PAGE_MARGINS_MM[orientation]
}

export function pageSizeMm(orientation: PdfOrientation): { width: number; height: number } {
  return orientation === "landscape" ? A4_LANDSCAPE_MM : A4_MM
}

export function contentBoxMm(orientation: PdfOrientation): {
  width: number
  height: number
  pageWidth: number
  pageHeight: number
} & PageMarginsMm {
  const size = pageSizeMm(orientation)
  const m = pageMargins(orientation)
  return {
    ...m,
    pageWidth: size.width,
    pageHeight: size.height,
    width: size.width - m.left - m.right,
    height: size.height - m.top - m.bottom,
  }
}

export function mmToPx(mm: number, dpi = 96): number {
  return Math.round((mm * dpi) / 25.4)
}

export function pdfPageLabel(page: number, total: number): string {
  return `${page} / ${total}`
}

export function sanitizePdfFilename(raw: string | undefined | null, fallback = "document"): string {
  const stem = (raw || fallback)
    .replace(/\.pdf$/i, "")
    .replace(/[^\w\s.-]+/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80)
  return `${stem || fallback}.pdf`
}

export function filenameFromHeading(doc: Document = document): string {
  const h1 = doc.querySelector("h1")?.textContent?.trim()
  const title = doc.title?.split("—")[0]?.trim()
  return sanitizePdfFilename(h1 || title || "document")
}

export function detectPdfOrientation(doc: Document = document): PdfOrientation {
  if (doc.querySelector(".print-landscape, style[data-print-landscape]")) return "landscape"
  return "portrait"
}

const FORM_TAGS = new Set(["INPUT", "SELECT", "TEXTAREA"])

export function shouldOmitFromPdf(node: Node): boolean {
  const el = node as Partial<Element> & { tagName?: string; closest?: (s: string) => Element | null }
  if (typeof el.getAttribute !== "function") return false
  if (el.classList?.contains("print-header")) return false
  if (el.getAttribute(PDF_HOST_ATTR) != null) return false
  if (el.getAttribute("data-print-hide") != null) return true
  if (el.getAttribute("data-eb-chrome") != null) return true
  if (el.getAttribute("data-eb-print-chrome") != null) return true
  if (el.classList?.contains("eb-print-save-bar")) return true
  if (el.classList?.contains("print:hidden")) return true
  const tag = (el.tagName || "").toUpperCase()
  if (FORM_TAGS.has(tag)) return true
  if (tag === "BUTTON") {
    try {
      if (typeof el.closest === "function" && el.closest("article")) return false
    } catch {
      /* test fakes have no closest */
    }
    return true
  }
  const role = el.getAttribute("role")
  if (role === "tab" || role === "tablist") return true
  return false
}

export function resolvePdfRoot(doc: Document = document): HTMLElement {
  return (
    doc.querySelector<HTMLElement>("[data-print-root]") ||
    doc.querySelector<HTMLElement>("article") ||
    doc.querySelector<HTMLElement>("main") ||
    doc.body
  )
}

export function imageHeightMm(imgWidthPx: number, imgHeightPx: number, contentWidthMm: number): number {
  if (imgWidthPx <= 0) return 0
  return (imgHeightPx * contentWidthMm) / imgWidthPx
}

export function pdfPageCount(imgHeightMm: number, pageHeightMm: number): number {
  if (imgHeightMm <= 0 || pageHeightMm <= 0) return 1
  return Math.max(1, Math.ceil(imgHeightMm / pageHeightMm))
}

/** Selector used to drop UI chrome from the PDF clone (and from print). */
export const PDF_STRIP_SELECTOR = [
  '[class*="print:hidden"]',
  ".eb-print-save-bar",
  "[data-print-hide]",
  "[data-eb-chrome]",
  "[data-eb-print-chrome]",
  "input",
  "select",
  "textarea",
  "[role='tab']",
  "[role='tablist']",
  "nav",
  "aside",
].join(",")

export function stripPdfChrome(root: HTMLElement): void {
  root.querySelectorAll(PDF_STRIP_SELECTOR).forEach((el) => {
    if (el.classList.contains("print-header") || el.closest(".print-header")) return
    if (el.tagName === "BUTTON" && el.closest("article")) return
    el.remove()
  })
  root.querySelectorAll("button").forEach((btn) => {
    if (btn.closest("article") || btn.closest(".print-header")) return
    btn.remove()
  })
  root.querySelectorAll("header").forEach((el) => {
    if (el.classList.contains("print-header") || el.closest(".print-header")) return
    if (el.classList.contains("print:hidden") || el.getAttribute("data-eb-chrome") != null) {
      el.remove()
    }
  })
  root.querySelectorAll("svg").forEach((svg) => {
    if (svg.closest("table, .print-header, article")) return
    const parent = svg.parentElement
    if (!parent || parent === root) return
    if ((parent.textContent || "").trim()) return
    parent.remove()
  })
}

export function revealPrintDocument(root: HTMLElement): void {
  root.querySelectorAll(".print-header").forEach((el) => {
    el.classList.remove("hidden")
    const node = el as HTMLElement
    node.style.display = "block"
    node.style.visibility = "visible"
  })
  root.querySelectorAll(".eb-print-expand").forEach((el) => {
    el.classList.remove("hidden")
    const node = el as HTMLElement
    node.style.display = el.tagName === "TR" ? "table-row" : ""
  })
}

function preparePdfHost(source: HTMLElement, orientation: PdfOrientation): HTMLElement {
  const box = contentBoxMm(orientation)
  const host = document.createElement("div")
  host.setAttribute(PDF_HOST_ATTR, "")
  host.style.cssText = [
    "position:fixed",
    "left:0",
    "top:0",
    `width:${mmToPx(box.width)}px`,
    "max-width:100%",
    "background:#fff",
    "color:#000",
    "z-index:2147483000",
    "overflow:visible",
    "pointer-events:none",
    "box-sizing:border-box",
  ].join(";")

  const clone = source.cloneNode(true) as HTMLElement
  clone.style.padding = "0"
  clone.style.margin = "0"
  clone.style.width = "100%"
  clone.style.maxWidth = "100%"
  clone.style.overflow = "visible"
  clone.style.height = "auto"
  stripPdfChrome(clone)
  revealPrintDocument(clone)
  host.appendChild(clone)
  document.body.appendChild(host)
  return host
}

function paintPageMargins(
  pdf: import("jspdf").jsPDF,
  box: ReturnType<typeof contentBoxMm>,
): void {
  pdf.setFillColor(255, 255, 255)
  pdf.rect(0, 0, box.pageWidth, box.top, "F")
  pdf.rect(0, box.pageHeight - box.bottom, box.pageWidth, box.bottom, "F")
  pdf.rect(0, 0, box.left, box.pageHeight, "F")
  pdf.rect(box.pageWidth - box.right, 0, box.right, box.pageHeight, "F")
}

function paintPageFooter(
  pdf: import("jspdf").jsPDF,
  box: ReturnType<typeof contentBoxMm>,
  page: number,
  total: number,
): void {
  pdf.setFont("courier", "normal")
  pdf.setFontSize(8)
  pdf.setTextColor(0, 0, 0)
  pdf.text(pdfPageLabel(page, total), box.pageWidth - box.right, box.pageHeight - 8, {
    align: "right",
  })
}

export async function saveScreenPdf(opts?: {
  filename?: string
  root?: HTMLElement
  orientation?: PdfOrientation
}): Promise<void> {
  if (typeof window === "undefined" || typeof document === "undefined") {
    throw new Error("PDF save is only available in the browser")
  }

  const filename = sanitizePdfFilename(opts?.filename || filenameFromHeading())
  const orientation = opts?.orientation ?? detectPdfOrientation()
  const root = opts?.root ?? resolvePdfRoot()
  const box = contentBoxMm(orientation)

  let host: HTMLElement | null = null
  document.documentElement.classList.add(SAVE_PDF_CLASS)
  try {
    host = preparePdfHost(root, orientation)
    await document.fonts?.ready.catch(() => undefined)
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))

    const { toPng } = await import("html-to-image")
    const { jsPDF } = await import("jspdf")

    const capture = (pixelRatio: number) =>
      toPng(host!, {
        pixelRatio,
        cacheBust: true,
        backgroundColor: "#ffffff",
        filter: (node) => node === host || !shouldOmitFromPdf(node),
      })

    let dataUrl: string
    try {
      dataUrl = await capture(2)
    } catch {
      dataUrl = await capture(1)
    }

    const img = await loadImage(dataUrl)
    const imgH = imageHeightMm(img.width, img.height, box.width)
    const pdf = new jsPDF({ orientation, unit: "mm", format: "a4" })
    const pages = pdfPageCount(imgH, box.height)

    for (let i = 0; i < pages; i++) {
      if (i > 0) pdf.addPage()
      const y = box.top - i * box.height
      pdf.addImage(dataUrl, "PNG", box.left, y, box.width, imgH, undefined, "FAST")
      paintPageMargins(pdf, box)
      paintPageFooter(pdf, box, i + 1, pages)
    }

    pdf.save(filename)
  } finally {
    host?.remove()
    document.documentElement.classList.remove(SAVE_PDF_CLASS)
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error("Could not render the page for PDF"))
    img.src = src
  })
}
