"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus, Upload, CheckCircle2, Clock, FileText, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { downloadCSV } from "@/lib/utils"

interface BankImport {
  id: number
  bank_account_id: number
  file_name: string
  line_count: number
  matched_count: number
  status: string
  created_at: string
}

interface BankAccount {
  id: number
  name: string
  bank_name: string | null
}

const STATUS_TONE: Record<string, string> = {
  parsed:      "bg-amber-50 text-amber-800 border-amber-200",
  matched:     "bg-emerald-50 text-emerald-800 border-emerald-200",
  reconciled:  "bg-blue-50 text-blue-800 border-blue-200",
}

export default function BankImportsPage() {
  const [imports, setImports]     = useState<BankImport[]>([])
  const [accounts, setAccounts]   = useState<Record<number, BankAccount>>({})
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<BankImport[]>("/api/bank-imports"),
      apiFetch<BankAccount[]>("/api/bank-accounts"),
    ])
      .then(([imps, accts]) => {
        setImports(imps)
        const map: Record<number, BankAccount> = {}
        accts.forEach(a => { map[a.id] = a })
        setAccounts(map)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Bank Statement Imports</h1>
          <p className="text-sm text-[#1a1814]/60 mt-0.5">
            Upload CSV statements and reconcile lines to journal entries.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => downloadCSV('bank-imports.csv', imports.map(i => ({ File: i.file_name, Account: accounts[i.bank_account_id]?.name ?? String(i.bank_account_id), Lines: i.line_count, Matched: i.matched_count, Status: i.status, Uploaded: i.created_at })))}
            disabled={imports.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <Link
            href="/bank-imports/new"
            className="inline-flex items-center gap-2 bg-[#b8943f] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#a07c32] transition-colors"
          >
            <Plus className="w-4 h-4" />
            Upload Statement
          </Link>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {loading ? (
        <div className="text-sm text-[#1a1814]/50 py-8 text-center">Loading…</div>
      ) : imports.length === 0 ? (
        <div className="bg-white border border-[#ede9e2] rounded-xl px-6 py-12 text-center">
          <Upload className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]">No statements imported yet</p>
          <p className="text-xs text-[#1a1814]/55 mt-1 mb-4">
            Upload a CSV with columns: date, description, debit, credit, balance
          </p>
          <Link
            href="/bank-imports/new"
            className="inline-flex items-center gap-2 bg-[#b8943f] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#a07c32] transition-colors"
          >
            <Plus className="w-4 h-4" /> Upload your first statement
          </Link>
        </div>
      ) : (
        <div className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#ede9e2] bg-[#faf8f4]">
                <th className="text-left px-4 py-3 font-semibold text-[#1a1814]/70">File</th>
                <th className="text-left px-4 py-3 font-semibold text-[#1a1814]/70">Bank Account</th>
                <th className="text-left px-4 py-3 font-semibold text-[#1a1814]/70">Uploaded</th>
                <th className="text-right px-4 py-3 font-semibold text-[#1a1814]/70">Lines</th>
                <th className="text-right px-4 py-3 font-semibold text-[#1a1814]/70">Matched</th>
                <th className="text-left px-4 py-3 font-semibold text-[#1a1814]/70">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {imports.map(imp => {
                const acct = accounts[imp.bank_account_id]
                const pct  = imp.line_count > 0
                  ? Math.round((imp.matched_count / imp.line_count) * 100)
                  : 0
                return (
                  <tr key={imp.id} className="border-b border-[#ede9e2] last:border-0 hover:bg-[#faf8f4]">
                    <td className="px-4 py-3 text-[#1a1814]">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-[#b8943f]/60 shrink-0" />
                        <span className="truncate max-w-[180px]">{imp.file_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[#1a1814]/80">
                      {acct ? (
                        <span>{acct.name}{acct.bank_name ? ` — ${acct.bank_name}` : ""}</span>
                      ) : (
                        <span className="text-[#1a1814]/40">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-[#1a1814]/70">
                      {new Date(imp.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{imp.line_count}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span className={pct === 100 ? "text-emerald-700 font-medium" : ""}>
                        {imp.matched_count} / {imp.line_count}
                      </span>
                      {pct > 0 && pct < 100 && (
                        <span className="text-[#1a1814]/40 text-xs ml-1">({pct}%)</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 border rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_TONE[imp.status] ?? "bg-slate-50 text-slate-700 border-slate-200"}`}>
                        {imp.status === "matched" ? <CheckCircle2 className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                        {imp.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/bank-imports/${imp.id}`}
                        className="text-[#b8943f] hover:underline font-medium text-xs"
                      >
                        Review →
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
