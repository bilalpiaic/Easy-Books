/**
 * Screen-faithful PDF save.
 *
 * Print uses `@media print` (Courier / black dot-matrix). Save must NOT go
 * through that stylesheet — it snapshots the on-screen document (colors,
 * type, layout) and downloads a PDF.
 */

export const SAVE_PDF_CLASS = "eb-saving-pdf"

const A4_MM = { width: 210, height: 297 }
const A4_LANDSCAPE_MM = { width: 297, height: 210 }
const MARGIN_MM = 8

export type PdfOrientation = "portrait" | "landscape"

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

export function shouldOmitFromPdf(node: Node): boolean {
  const el = node as Partial<Element>
  if (typeof el.getAttribute !== "function") return false
  if (el.getAttribute("data-print-hide") != null) return true
  if (el.getAttribute("data-eb-chrome") != null) return true
  if (el.classList?.contains("eb-print-save-bar")) return true
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

export function pageSizeMm(orientation: PdfOrientation): { width: number; height: number } {
  return orientation === "landscape" ? A4_LANDSCAPE_MM : A4_MM
}

export function imageHeightMm(imgWidthPx: number, imgHeightPx: number, contentWidthMm: number): number {
  if (imgWidthPx <= 0) return 0
  return (imgHeightPx * contentWidthMm) / imgWidthPx
}

export function pdfPageCount(imgHeightMm: number, pageHeightMm: number): number {
  if (imgHeightMm <= 0 || pageHeightMm <= 0) return 1
  return Math.max(1, Math.ceil(imgHeightMm / pageHeightMm))
}

function pageBackground(): string {
  if (typeof window === "undefined") return "#f6f3ee"
  const raw = getComputedStyle(document.documentElement).getPropertyValue("--bg-page").trim()
  return raw || "#f6f3ee"
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

  document.documentElement.classList.add(SAVE_PDF_CLASS)
  try {
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))

    const { toPng } = await import("html-to-image")
    const { jsPDF } = await import("jspdf")

    const capture = (pixelRatio: number) =>
      toPng(root, {
        pixelRatio,
        cacheBust: true,
        backgroundColor: pageBackground(),
        filter: (node) => !shouldOmitFromPdf(node),
      })

    let dataUrl: string
    try {
      dataUrl = await capture(2)
    } catch {
      dataUrl = await capture(1)
    }

    const img = await loadImage(dataUrl)
    const size = pageSizeMm(orientation)
    const contentWidth = size.width - MARGIN_MM * 2
    const contentHeight = size.height - MARGIN_MM * 2
    const imgH = imageHeightMm(img.width, img.height, contentWidth)

    const pdf = new jsPDF({ orientation, unit: "mm", format: "a4" })
    const pages = pdfPageCount(imgH, contentHeight)

    for (let i = 0; i < pages; i++) {
      if (i > 0) pdf.addPage()
      const y = MARGIN_MM - i * contentHeight
      pdf.addImage(dataUrl, "PNG", MARGIN_MM, y, contentWidth, imgH, undefined, "FAST")
    }

    pdf.save(filename)
  } finally {
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
