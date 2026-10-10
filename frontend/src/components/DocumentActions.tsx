"use client"

import { useState } from "react"
import { Download, Printer, Share2 } from "lucide-react"
import { saveScreenPdf } from "@/lib/saveScreenPdf"

interface DocumentActionsProps {
  onPrint?: () => void
  printDisabled?: boolean
  printTitle?: string
  onSavePdf?: () => void
  pdfDisabled?: boolean
  pdfBusy?: boolean
  onShare?: () => void
  shareDisabled?: boolean
  shareLabel?: string
  className?: string
}

/**
 * Screen-only toolbar for Print / Save PDF / Share next to document pages.
 * Pair with PrintHeader (print-only brand chrome).
 */
export default function DocumentActions({
  onPrint,
  printDisabled,
  printTitle,
  onSavePdf,
  pdfDisabled,
  pdfBusy,
  onShare,
  shareDisabled,
  shareLabel = "Share",
  className = "",
}: DocumentActionsProps) {
  const [screenBusy, setScreenBusy] = useState(false)
  const busy = pdfBusy || screenBusy

  async function handleSave() {
    if (onSavePdf) {
      onSavePdf()
      return
    }
    setScreenBusy(true)
    try {
      await saveScreenPdf()
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "PDF save failed")
    } finally {
      setScreenBusy(false)
    }
  }

  return (
    <div className={`eb-print-save-bar print:hidden flex flex-wrap items-center gap-2 ${className}`}>
      {onPrint && (
        <button
          type="button"
          onClick={onPrint}
          disabled={printDisabled}
          title={printTitle}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm border border-[var(--border)] rounded-lg hover:bg-[var(--bg-page)] disabled:opacity-50"
        >
          <Printer className="w-4 h-4" /> Print
        </button>
      )}
      <button
        type="button"
        onClick={() => void handleSave()}
        disabled={pdfDisabled || busy}
        className="inline-flex items-center gap-1.5 px-3 py-2 text-sm bg-[var(--primary)] text-white rounded-lg hover:opacity-90 disabled:opacity-50"
      >
        <Download className="w-4 h-4" /> {busy ? "Saving…" : "Save PDF"}
      </button>
      {onShare && (
        <button
          type="button"
          onClick={onShare}
          disabled={shareDisabled}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm border border-emerald-200 text-emerald-800 bg-emerald-50 rounded-lg hover:bg-emerald-100 disabled:opacity-50"
        >
          <Share2 className="w-4 h-4" /> {shareLabel}
        </button>
      )}
    </div>
  )
}
