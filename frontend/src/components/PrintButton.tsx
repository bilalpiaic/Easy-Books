"use client"

import { useState } from "react"
import { FileDown, Printer } from "lucide-react"
import { useTranslation } from "react-i18next"
import { saveScreenPdf } from "@/lib/saveScreenPdf"

interface PrintButtonProps {
  label?: string
  saveLabel?: string
  filename?: string
  className?: string
  /** Applied to both Print and Save buttons. */
  buttonClassName?: string
  variant?: "labeled" | "icon" | "toolbar"
  disabled?: boolean
  printTitle?: string
  saveTitle?: string
}

const VARIANT_BTN: Record<NonNullable<PrintButtonProps["variant"]>, string> = {
  labeled:
    "inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors",
  icon:
    "p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60",
  toolbar:
    "inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--primary)] hover:bg-[#d4af60] text-black rounded-md text-sm font-semibold",
}

/** Save-only control for pages whose Print action is a link to a print view. */
export function SavePdfButton({
  filename,
  className = "",
  buttonClassName,
  variant = "labeled",
  label,
}: Pick<PrintButtonProps, "filename" | "className" | "buttonClassName" | "variant" | "label">) {
  const { t } = useTranslation()
  const [busy, setBusy] = useState(false)
  const saveText = label ?? t("common.savePdf", "Save PDF")
  const btn = buttonClassName ?? VARIANT_BTN[variant]
  const iconClass = variant === "icon" ? "w-5 h-5" : "w-4 h-4"

  async function onSave() {
    setBusy(true)
    try {
      await saveScreenPdf({ filename })
    } catch (err) {
      window.alert(err instanceof Error ? err.message : t("common.savePdfFailed", "PDF save failed"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      type="button"
      onClick={() => void onSave()}
      disabled={busy}
      title={saveText}
      className={`eb-print-save-bar print:hidden ${btn} disabled:opacity-40 disabled:cursor-not-allowed ${className}`}
    >
      <FileDown className={iconClass} />
      {variant !== "icon" ? (busy ? t("common.savingPdf", "Saving…") : saveText) : null}
    </button>
  )
}

/** Print (dot-matrix @media print) + Save PDF (formatted A4 document, not a UI screenshot). */
export default function PrintButton({
  label,
  saveLabel,
  filename,
  className = "",
  buttonClassName,
  variant = "labeled",
  disabled,
  printTitle,
  saveTitle,
}: PrintButtonProps) {
  const { t } = useTranslation()
  const [busy, setBusy] = useState(false)
  const printText = label ?? t("common.print", "Print")
  const saveText = saveLabel ?? t("common.savePdf", "Save PDF")
  const btn = buttonClassName ?? VARIANT_BTN[variant]
  const iconClass = variant === "icon" ? "w-5 h-5" : "w-4 h-4"

  async function onSave() {
    setBusy(true)
    try {
      await saveScreenPdf({ filename })
    } catch (err) {
      const msg = err instanceof Error ? err.message : t("common.savePdfFailed", "PDF save failed")
      window.alert(msg)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`eb-print-save-bar print:hidden inline-flex items-center gap-2 ${className}`}>
      <button
        type="button"
        onClick={() => window.print()}
        disabled={disabled}
        title={printTitle ?? printText}
        className={`${btn} disabled:opacity-40 disabled:cursor-not-allowed`}
      >
        <Printer className={iconClass} />
        {variant !== "icon" ? printText : null}
      </button>
      <button
        type="button"
        onClick={() => void onSave()}
        disabled={disabled || busy}
        title={saveTitle ?? saveText}
        className={`${btn} disabled:opacity-40 disabled:cursor-not-allowed`}
      >
        <FileDown className={iconClass} />
        {variant !== "icon" ? (busy ? t("common.savingPdf", "Saving…") : saveText) : null}
      </button>
    </div>
  )
}
