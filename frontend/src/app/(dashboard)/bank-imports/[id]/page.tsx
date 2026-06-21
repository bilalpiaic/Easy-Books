"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { CheckCircle2, Clock, Zap, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { fmtDate } from "@/lib/utils"
import { useTranslation } from "react-i18next"

interface BankImport {
  id: number
  bank_account_id: number
  file_name: string
  line_count: number
  matched_count: number
  status: string
  created_at: string
}

interface StatementLine {
  id: number
  date: string
  description: string
  debit: number
  credit: number
  balance: number
  is_matched: boolean
  matched_transaction_id: number | null
}

interface JournalLine {
  transaction_id: number
  jv_number: string
  date: string
  description: string
  debit: number
  credit: number
}

export default function BankImportDetailPage() {
  const { t } = useTranslation()

  const { id }    = useParams<{ id: string }>()
  const fmt       = useFmt()

  const [imp, setImp]           = useState<BankImport | null>(null)
  const [lines, setLines]       = useState<StatementLine[]>([])
  const [txnMap, setTxnMap]     = useState<Record<number, JournalLine>>({})  // transaction_id → first JL
  const [matching, setMatching] = useState(false)
  const [matchMsg, setMatchMsg] = useState<string | null>(null)
  const [error, setError]       = useState<string | null>(null)
  const [loading, setLoading]   = useState(true)

  // Inline match selectors: line_id → selected transaction_id string
  const [selectors, setSelectors] = useState<Record<number, string>>({})

  const load = useCallback(() => {
    Promise.all([
      apiFetch<BankImport[]>("/api/bank-imports"),
      apiFetch<StatementLine[]>(`/api/bank-imports/${id}/lines`),
      apiFetch<JournalLine[]>("/api/reports/journal?limit=500"),
    ])
      .then(([imps, ls, jls]) => {
        const imp = imps.find(i => i.id === parseInt(id)) ?? null
        setImp(imp)
        setLines(ls)
        // Build transaction_id → representative journal line map
        const map: Record<number, JournalLine> = {}
        jls.forEach(jl => {
          if (!(jl.transaction_id in map)) map[jl.transaction_id] = jl
        })
        setTxnMap(map)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => { load() }, [load])

  const runAutoMatch = async () => {
    setMatching(true)
    setMatchMsg(null)
    try {
      const res = await apiFetch<{ newly_matched: number; total_matched: number; import: BankImport }>(
        `/api/bank-imports/${id}/auto-match`, { method: "POST" }
      )
      setMatchMsg(`Auto-matched ${res.newly_matched} new line${res.newly_matched !== 1 ? "s" : ""} (${res.total_matched} total).`)
      setImp(res.import)
      // Reload lines to reflect new match state
      const ls = await apiFetch<StatementLine[]>(`/api/bank-imports/${id}/lines`)
      setLines(ls)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Auto-match failed")
    } finally {
      setMatching(false)
    }
  }

  const saveSingleMatch = async (lineId: number, txnId: string) => {
    if (!txnId) return
    try {
      await apiFetch(`/api/statement-lines/${lineId}`, {
        method: "PATCH",
        body: JSON.stringify({ matched_transaction_id: parseInt(txnId) }),
      })
      setLines(prev => prev.map(l =>
        l.id === lineId
          ? { ...l, is_matched: true, matched_transaction_id: parseInt(txnId) }
          : l
      ))
      setImp(prev => prev ? { ...prev, matched_count: prev.matched_count + 1 } : prev)
      setSelectors(prev => { const n = { ...prev }; delete n[lineId]; return n })
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed")
    }
  }

  const clearMatch = async (lineId: number) => {
    try {
      await apiFetch(`/api/statement-lines/${lineId}`, {
        method: "PATCH",
        body: JSON.stringify({ matched_transaction_id: null }),
      })
      setLines(prev => prev.map(l =>
        l.id === lineId
          ? { ...l, is_matched: false, matched_transaction_id: null }
          : l
      ))
      setImp(prev => prev ? { ...prev, matched_count: Math.max(0, prev.matched_count - 1) } : prev)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Clear failed")
    }
  }

  // Transactions whose total roughly equals the line's amount (debit or credit)
  const candidatesFor = (line: StatementLine): JournalLine[] => {
    const amount = line.debit > 0 ? line.debit : line.credit
    return Object.values(txnMap).filter(jl => {
      const jlAmt = jl.debit > 0 ? jl.debit : jl.credit
      return Math.abs(jlAmt - amount) < 0.005
    })
  }

  if (loading) return <div className="text-sm text-[#1a1814]/50 py-8 text-center">Loading…</div>
  if (!lines.length && !imp) return (
    <div className="text-sm text-red-700 py-8 text-center">{error ?? "Import not found"}</div>
  )

  const unmatched = lines.filter(l => !l.is_matched).length
  const pct = imp && imp.line_count > 0
    ? Math.round((imp.matched_count / imp.line_count) * 100)
    : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <Link href="/bank-imports" className="text-sm text-[#b8943f] hover:underline">
            ← Bank Statement Imports
          </Link>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814] mt-1">
            {imp?.file_name ?? `Import #${id}`}
          </h1>
          {imp && (
            <p className="text-sm text-[#1a1814]/60 mt-0.5">
              {imp.matched_count} / {imp.line_count} matched ({pct}%) · {fmtDate(imp.created_at)}
            </p>
          )}
        </div>
        <button
          onClick={runAutoMatch}
          disabled={matching || unmatched === 0}
          className="inline-flex items-center gap-2 bg-[#b8943f] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#a07c32] disabled:opacity-50 transition-colors self-start"
        >
          <Zap className="w-4 h-4" />
          {matching ? "Matching…" : "Run Auto-Match"}
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {matchMsg && (
        <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2.5">
          {matchMsg}
        </div>
      )}

      {/* Progress bar */}
      {imp && imp.line_count > 0 && (
        <div>
          <div className="flex justify-between text-xs text-[#1a1814]/60 mb-1">
            <span>{unmatched} unmatched</span>
            <span>{pct}% done</span>
          </div>
          <div className="h-1.5 bg-[#ede9e2] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#b8943f] rounded-full transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      {/* Lines table */}
      <div className="bg-white border border-[#ede9e2] rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[700px]">
          <thead>
            <tr className="border-b border-[#ede9e2] bg-[#faf8f4]">
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]/70">Date</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]/70">{t('col.description', 'Description')}</th>
              <th className="text-right px-4 py-3 font-semibold text-[#1a1814]/70">{t('col.debit', 'Debit')}</th>
              <th className="text-right px-4 py-3 font-semibold text-[#1a1814]/70">{t('col.credit', 'Credit')}</th>
              <th className="text-right px-4 py-3 font-semibold text-[#1a1814]/70">{t('col.balance', 'Balance')}</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]/70 w-56">Match</th>
            </tr>
          </thead>
          <tbody>
            {lines.map(line => {
              const candidates = candidatesFor(line)
              const matchedJl  = line.matched_transaction_id ? txnMap[line.matched_transaction_id] : null
              return (
                <tr
                  key={line.id}
                  className={`border-b border-[#ede9e2] last:border-0 ${line.is_matched ? "" : "bg-amber-50/30"}`}
                >
                  <td className="px-4 py-2.5 text-[#1a1814]/80 whitespace-nowrap">{fmtDate(line.date)}</td>
                  <td className="px-4 py-2.5 text-[#1a1814] max-w-[220px]">
                    <span className="line-clamp-2">{line.description}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">
                    {line.debit > 0 ? fmt(line.debit) : ""}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">
                    {line.credit > 0 ? fmt(line.credit) : ""}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-[#1a1814]/60">
                    {fmt(line.balance)}
                  </td>
                  <td className="px-4 py-2.5">
                    {line.is_matched ? (
                      <div className="flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <span className="text-xs text-emerald-700 truncate max-w-[120px]">
                          {matchedJl ? matchedJl.jv_number : `#${line.matched_transaction_id}`}
                        </span>
                        <button
                          onClick={() => clearMatch(line.id)}
                          className="text-[#1a1814]/30 hover:text-red-500 text-xs ml-1"
                          title="Clear match"
                        >
                          ×
                        </button>
                      </div>
                    ) : candidates.length > 0 ? (
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                        <select
                          value={selectors[line.id] ?? ""}
                          onChange={e => {
                            const v = e.target.value
                            setSelectors(prev => ({ ...prev, [line.id]: v }))
                            saveSingleMatch(line.id, v)
                          }}
                          className="text-xs border border-[#d4cfc7] rounded px-1.5 py-1 focus:outline-none focus:border-[#b8943f] max-w-[160px]"
                        >
                          <option value="">Select JV…</option>
                          {candidates.map(c => (
                            <option key={c.transaction_id} value={c.transaction_id}>
                              {c.jv_number} · {fmtDate(c.date)}
                            </option>
                          ))}
                        </select>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-[#1a1814]/30 shrink-0" />
                        <span className="text-xs text-[#1a1814]/40">No match found</span>
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
