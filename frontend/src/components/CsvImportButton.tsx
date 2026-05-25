"use client"

import { useRef, useState } from "react"
import { Upload, Download, X, CheckCircle, AlertTriangle, FileText, Loader2, ArrowLeft } from "lucide-react"
import { apiBase } from "@/lib/api"
import { getAuthToken } from "@/lib/auth"

export type ImportEntity = "transactions" | "accounts" | "customers" | "vendors" | "products"

interface ImportError {
  row: number
  message: string
}

interface ValidationResult {
  valid_count: number
  total_rows: number
  errors: ImportError[]
}

interface ImportResult {
  imported: number
  errors: ImportError[]
}

interface Props {
  entity: ImportEntity
  label?: string
  onSuccess?: () => void
}

const ENTITY_LABELS: Record<ImportEntity, string> = {
  transactions: "Journal Transactions",
  accounts:     "Chart of Accounts",
  customers:    "Customers",
  vendors:      "Vendors",
  products:     "Products",
}

const ENTITY_FIELDS: Record<ImportEntity, { field: string; required: boolean; note?: string }[]> = {
  transactions: [
    { field: "date",         required: true,  note: "YYYY-MM-DD" },
    { field: "description",  required: true,  note: "rows with same date+description = 1 transaction" },
    { field: "account_code", required: true,  note: "must exist in Chart of Accounts" },
    { field: "debit",        required: true,  note: "numeric, 0 if not applicable" },
    { field: "credit",       required: true,  note: "numeric, 0 if not applicable" },
  ],
  accounts: [
    { field: "code",  required: false, note: "optional unique code" },
    { field: "name",  required: true },
    { field: "type",  required: true,  note: "Asset / Liability / Equity / Revenue / Expense" },
  ],
  customers: [
    { field: "name",            required: true },
    { field: "email",           required: false },
    { field: "phone",           required: false },
    { field: "address",         required: false },
    { field: "opening_balance", required: false, note: "numeric, default 0" },
  ],
  vendors: [
    { field: "name",            required: true },
    { field: "email",           required: false },
    { field: "phone",           required: false },
    { field: "address",         required: false },
    { field: "opening_balance", required: false, note: "numeric, default 0" },
  ],
  products: [
    { field: "code",          required: false },
    { field: "name",          required: true },
    { field: "unit",          required: false, note: "pcs / kg / mtr / hrs / ltr / box / doz" },
    { field: "product_type",  required: false, note: "stock or service (default: service)" },
    { field: "default_rate",  required: false, note: "numeric" },
    { field: "reorder_level", required: false, note: "numeric, only for stock" },
  ],
}

type Step = "upload" | "review" | "done"

export default function CsvImportButton({ entity, label, onSuccess }: Props) {
  const [open, setOpen]             = useState(false)
  const [step, setStep]             = useState<Step>("upload")
  const [file, setFile]             = useState<File | null>(null)
  const [preview, setPreview]       = useState<{ headers: string[]; rows: string[][] }>({ headers: [], rows: [] })
  const [fileError, setFileError]   = useState<string | null>(null)
  const [validating, setValidating] = useState(false)
  const [importing, setImporting]   = useState(false)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [result, setResult]         = useState<ImportResult | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const reset = () => {
    setFile(null); setPreview({ headers: [], rows: [] }); setFileError(null)
    setValidation(null); setResult(null); setStep("upload")
    if (inputRef.current) inputRef.current.value = ""
  }
  const close = () => { setOpen(false); reset() }

  const downloadSample = async () => {
    const token = getAuthToken()
    const res = await fetch(
      `${apiBase}/api/import/${entity}/sample`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url; a.download = `sample_${entity}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  const parsePreview = (f: File) => {
    const reader = new FileReader()
    reader.onload = e => {
      const text = (e.target?.result as string) || ""
      const lines = text.trim().split("\n").map(l =>
        l.split(",").map(c => c.trim().replace(/^"|"$/g, ""))
      )
      setPreview({ headers: lines[0] || [], rows: lines.slice(1, 6) })
    }
    reader.readAsText(f)
  }

  const handleFile = async (f: File) => {
    if (!f.name.endsWith(".csv")) { setFileError("Please select a .csv file"); return }
    setFileError(null); setFile(f)
    parsePreview(f)
    // auto-validate on file select
    setValidating(true)
    try {
      const token = getAuthToken()
      const form = new FormData()
      form.append("file", f)
      const res = await fetch(
        `${apiBase}/api/import/${entity}/validate`,
        { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form }
      )
      const data: ValidationResult = await res.json()
      if (!res.ok) throw new Error((data as unknown as { detail: string }).detail || "Validation failed")
      setValidation(data)
      setStep("review")
    } catch (err) {
      setFileError((err as Error).message)
    } finally {
      setValidating(false)
    }
  }

  const handleImport = async () => {
    if (!file) return
    setImporting(true)
    try {
      const token = getAuthToken()
      const form = new FormData()
      form.append("file", file)
      const res = await fetch(
        `${apiBase}/api/import/${entity}`,
        { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form }
      )
      const data: ImportResult = await res.json()
      if (!res.ok) throw new Error((data as unknown as { detail: string }).detail || "Import failed")
      setResult(data)
      setStep("done")
      if (data.imported > 0) onSuccess?.()
    } catch (err) {
      setResult({ imported: 0, errors: [{ row: 0, message: (err as Error).message }] })
      setStep("done")
    } finally {
      setImporting(false)
    }
  }

  const stepLabel = { upload: "1 of 3 — Upload", review: "2 of 3 — Review", done: "3 of 3 — Done" }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 px-3 py-2 text-xs font-bold uppercase tracking-wider text-[#b8943f] border border-[#b8943f]/40 rounded-lg hover:bg-[#b8943f]/10 transition-colors"
      >
        <Upload className="w-3.5 h-3.5" />
        {label ?? "Import CSV"}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={close} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#ede9e2]">
              <div className="flex items-center gap-2.5">
                <FileText className="w-5 h-5 text-[#b8943f]" />
                <div>
                  <h2 className="font-serif font-semibold text-[#1a1814] text-base">
                    Import {ENTITY_LABELS[entity]}
                  </h2>
                  <p className="text-[11px] text-[#1a1814]/50">{stepLabel[step]}</p>
                </div>
              </div>
              <button onClick={close} className="text-[#1a1814]/40 hover:text-[#1a1814] transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="px-6 py-5 space-y-5">

              {/* ── Step 1: Upload ── */}
              {step === "upload" && (
                <>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50 mb-2">Download sample CSV</p>
                    <button
                      onClick={downloadSample}
                      className="flex items-center gap-2 px-4 py-2.5 bg-[#f6f3ee] border border-[#ede9e2] rounded-xl text-sm font-medium text-[#1a1814]/80 hover:bg-[#ede9e2] transition-colors"
                    >
                      <Download className="w-4 h-4 text-[#b8943f]" />
                      Download sample_{entity}.csv
                    </button>
                  </div>

                  <div className="bg-[#f6f3ee] rounded-xl p-4">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/50 mb-2.5">Required columns</p>
                    <div className="flex flex-wrap gap-2">
                      {ENTITY_FIELDS[entity].map(({ field, required, note }) => (
                        <div key={field} className="flex items-center gap-1.5">
                          <code className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold ${required ? "bg-[#b8943f]/15 text-[#8a6d2e]" : "bg-white/80 text-[#1a1814]/60 border border-[#ede9e2]"}`}>
                            {field}
                          </code>
                          {required && <span className="text-[9px] text-red-500 font-bold">REQ</span>}
                          {note && <span className="text-[10px] text-[#1a1814]/40 italic hidden sm:inline">{note}</span>}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50 mb-2">Upload CSV</p>
                    <div
                      onClick={() => !validating && inputRef.current?.click()}
                      onDragOver={e => e.preventDefault()}
                      onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFile(f) }}
                      className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors ${
                        validating ? "border-[#b8943f]/40 bg-[#b8943f]/5 cursor-wait"
                          : file ? "border-[#b8943f]/60 bg-[#b8943f]/5 cursor-pointer"
                          : "border-[#ede9e2] hover:border-[#b8943f]/40 hover:bg-[#faf8f4] cursor-pointer"
                      }`}
                    >
                      {validating ? (
                        <div className="flex flex-col items-center gap-2">
                          <Loader2 className="w-6 h-6 text-[#b8943f] animate-spin" />
                          <p className="text-sm text-[#1a1814]/60">Validating…</p>
                        </div>
                      ) : file ? (
                        <p className="text-sm font-medium text-[#1a1814]">{file.name}</p>
                      ) : (
                        <>
                          <Upload className="w-6 h-6 text-[#b8943f]/60 mx-auto mb-2" />
                          <p className="text-sm text-[#1a1814]/60">Drop CSV here or <span className="text-[#b8943f] font-semibold">browse</span></p>
                          <p className="text-[11px] text-[#1a1814]/40 mt-1">.csv files only · validation runs automatically</p>
                        </>
                      )}
                    </div>
                    <input ref={inputRef} type="file" accept=".csv" className="hidden"
                      onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
                    {fileError && <p className="text-xs text-red-500 mt-1.5">{fileError}</p>}
                  </div>

                  <div className="flex justify-end">
                    <button onClick={close} className="px-4 py-2 text-sm rounded-xl border border-[#ede9e2] text-[#1a1814]/70 hover:bg-[#f6f3ee] transition-colors">
                      Cancel
                    </button>
                  </div>
                </>
              )}

              {/* ── Step 2: Review validation ── */}
              {step === "review" && validation && (
                <>
                  {/* Validation summary */}
                  <div className={`rounded-xl p-4 border ${validation.errors.length === 0 ? "bg-green-50 border-green-200" : validation.valid_count > 0 ? "bg-amber-50 border-amber-200" : "bg-red-50 border-red-200"}`}>
                    <div className="flex items-center gap-2 mb-1">
                      {validation.errors.length === 0
                        ? <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
                        : <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                      }
                      <span className="text-sm font-bold text-[#1a1814]">
                        {validation.valid_count} of {validation.total_rows} row{validation.total_rows !== 1 ? "s" : ""} valid
                        {validation.errors.length > 0 && ` · ${validation.errors.length} error${validation.errors.length !== 1 ? "s" : ""}`}
                      </span>
                    </div>
                    {validation.errors.length > 0 && (
                      <div className="space-y-1 max-h-32 overflow-y-auto mt-2">
                        {validation.errors.map((e, i) => (
                          <div key={i} className="flex gap-2 text-xs">
                            {e.row > 0 && <span className="text-[#1a1814]/40 font-mono flex-shrink-0">Row {e.row}</span>}
                            <span className="text-red-700">{e.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Preview table */}
                  {preview.rows.length > 0 && (
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50 mb-2">Preview (first 5 rows)</p>
                      <div className="overflow-x-auto rounded-xl border border-[#ede9e2]">
                        <table className="w-full text-xs min-w-[400px]">
                          <thead className="bg-[#f6f3ee]">
                            <tr>{preview.headers.map(h => <th key={h} className="px-3 py-2 text-left font-bold text-[#1a1814]/60 uppercase tracking-wider">{h}</th>)}</tr>
                          </thead>
                          <tbody className="divide-y divide-[#ede9e2]">
                            {preview.rows.map((row, ri) => (
                              <tr key={ri} className="hover:bg-[#faf8f4]">
                                {row.map((cell, ci) => <td key={ci} className="px-3 py-2 text-[#1a1814]/80 font-mono">{cell}</td>)}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-1">
                    <button onClick={reset} className="flex items-center gap-1.5 text-sm text-[#1a1814]/50 hover:text-[#1a1814] transition-colors">
                      <ArrowLeft className="w-3.5 h-3.5" /> Upload different file
                    </button>
                    <div className="flex gap-3">
                      <button onClick={close} className="px-4 py-2 text-sm rounded-xl border border-[#ede9e2] text-[#1a1814]/70 hover:bg-[#f6f3ee] transition-colors">
                        Cancel
                      </button>
                      <button
                        onClick={handleImport}
                        disabled={importing || validation.valid_count === 0}
                        className="flex items-center gap-2 px-5 py-2 bg-[#b8943f] text-black text-sm font-bold rounded-xl hover:bg-[#d4af60] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        {importing ? "Importing…" : `Confirm Import (${validation.valid_count} rows)`}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {/* ── Step 3: Done ── */}
              {step === "done" && result && (
                <>
                  <div className={`rounded-xl p-4 border ${result.imported > 0 ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
                    <div className="flex items-center gap-2 mb-2">
                      {result.imported > 0
                        ? <CheckCircle className="w-4 h-4 text-green-600" />
                        : <AlertTriangle className="w-4 h-4 text-red-500" />
                      }
                      <span className="text-sm font-bold text-[#1a1814]">
                        {result.imported} record{result.imported !== 1 ? "s" : ""} imported
                        {result.errors.length > 0 && `, ${result.errors.length} error${result.errors.length !== 1 ? "s" : ""}`}
                      </span>
                    </div>
                    {result.errors.length > 0 && (
                      <div className="space-y-1 max-h-40 overflow-y-auto">
                        {result.errors.map((e, i) => (
                          <div key={i} className="flex gap-2 text-xs">
                            {e.row > 0 && <span className="text-[#1a1814]/40 font-mono flex-shrink-0">Row {e.row}</span>}
                            <span className="text-red-700">{e.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <button onClick={reset} className="text-sm text-[#b8943f] hover:underline font-medium">
                      Import another file
                    </button>
                    <button onClick={close} className="px-5 py-2 text-sm rounded-xl bg-[#1a1814] text-white font-bold hover:bg-[#b8943f] transition-colors">
                      Close
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
