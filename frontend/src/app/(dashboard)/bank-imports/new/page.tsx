"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Upload, FileText, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

interface BankAccount {
  id: number
  name: string
  bank_name: string | null
  is_active: boolean
}

export default function NewBankImportPage() {
  const { t } = useTranslation()
  const router = useRouter()
  const fileRef = useRef<HTMLInputElement>(null)

  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [accountId, setAccountId] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadErr, setLoadErr] = useState<string | null>(null)
  const [showMapping, setShowMapping] = useState(false)
  const [dateCol, setDateCol] = useState("date")
  const [descCol, setDescCol] = useState("description")
  const [debitCol, setDebitCol] = useState("debit")
  const [creditCol, setCreditCol] = useState("credit")
  const [amountCol, setAmountCol] = useState("")
  const [balanceCol, setBalanceCol] = useState("balance")

  useEffect(() => {
    apiFetch<BankAccount[]>("/api/bank-accounts")
      .then(accts => setAccounts(accts.filter(a => a.is_active)))
      .catch(() => setLoadErr("Failed to load bank accounts"))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!accountId) { setError("Please select a bank account"); return }
    if (!file) { setError("Please choose a CSV or OFX/QFX file"); return }

    setError(null)
    setUploading(true)

    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
    const form = new FormData()
    form.append("bank_account_id", accountId)
    form.append("file", file)
    form.append("date_col", dateCol)
    form.append("description_col", descCol)
    form.append("debit_col", debitCol)
    form.append("credit_col", creditCol)
    form.append("balance_col", balanceCol)
    if (amountCol.trim()) form.append("amount_col", amountCol.trim())

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/bank-imports`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: form,
        },
      )
      if (res.status === 409) {
        const data = await res.json()
        setError(data.detail ?? "This file has already been imported for this account.")
        return
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail ?? `Upload failed (${res.status})`)
        return
      }
      const imp = await res.json()
      router.push(`/bank-imports/${imp.id}`)
    } catch {
      setError("Network error — please try again")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <Link href="/bank-imports" className="text-sm text-[var(--primary)] hover:underline">
          ← Bank Statement Imports
        </Link>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] mt-2">Upload Statement</h1>
        <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
          CSV (with optional column mapping) or OFX/QFX. Same inbox as Plaid sync.
        </p>
      </div>

      {loadErr && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{loadErr}</div>
      )}

      <form onSubmit={handleSubmit} className="bg-white border border-[var(--border)] rounded-xl p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">Bank Account</label>
          <select
            value={accountId}
            onChange={e => setAccountId(e.target.value)}
            className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
          >
            <option value="">Select account…</option>
            {accounts.map(a => (
              <option key={a.id} value={a.id}>
                {a.name}{a.bank_name ? ` — ${a.bank_name}` : ""}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">Statement file</label>
          <div
            className="border-2 border-dashed border-[#d4cfc7] rounded-xl p-6 text-center cursor-pointer hover:border-[var(--primary)]/60 transition-colors"
            onClick={() => fileRef.current?.click()}
          >
            {file ? (
              <div className="flex items-center justify-center gap-2 text-sm text-[var(--text-primary)]">
                <FileText className="w-5 h-5 text-[var(--primary)]" />
                <span>{file.name}</span>
                <span className="text-[var(--text-primary)]/40">({(file.size / 1024).toFixed(1)} KB)</span>
              </div>
            ) : (
              <>
                <Upload className="w-8 h-8 text-[var(--primary)]/40 mx-auto mb-2" />
                <p className="text-sm text-[var(--text-primary)]/70">Click to choose CSV or OFX/QFX</p>
                <p className="text-xs text-[var(--text-primary)]/40 mt-1">UTF-8 encoded</p>
              </>
            )}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.ofx,.qfx,text/csv,application/x-ofx,application/vnd.intu.qfx"
            className="hidden"
            onChange={e => setFile(e.target.files?.[0] ?? null)}
          />
        </div>

        <button
          type="button"
          className="text-sm text-[var(--primary)] hover:underline"
          onClick={() => setShowMapping(v => !v)}
        >
          {showMapping ? "Hide CSV column mapping" : "CSV column mapping…"}
        </button>

        {showMapping && (
          <div className="grid grid-cols-2 gap-3 border border-[var(--border)] rounded-lg p-3">
            {([
              ["Date", dateCol, setDateCol],
              ["Description", descCol, setDescCol],
              ["Debit", debitCol, setDebitCol],
              ["Credit", creditCol, setCreditCol],
              ["Signed amount (optional)", amountCol, setAmountCol],
              ["Balance", balanceCol, setBalanceCol],
            ] as const).map(([label, val, set]) => (
              <label key={label} className="text-xs space-y-1">
                <span className="text-[var(--text-muted)]">{label}</span>
                <input
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={val}
                  onChange={e => set(e.target.value)}
                />
              </label>
            ))}
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button
            type="submit"
            disabled={uploading}
            className="flex-1 bg-[var(--primary)] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50 transition-colors"
          >
            {uploading ? "Uploading…" : "Upload & Import"}
          </button>
          <Link
            href="/bank-imports"
            className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors"
          >{t('common.cancel', 'Cancel')}</Link>
        </div>
      </form>
    </div>
  )
}
