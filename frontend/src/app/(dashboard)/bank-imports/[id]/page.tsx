"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { CheckCircle2, Clock, Zap, AlertCircle, X } from "lucide-react"
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

interface Suggestion {
  transaction_id: number
  jv_number?: string
  date?: string
  description?: string
  confidence: number
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
  suggested_transaction_id?: number | null
  match_confidence?: number | null
  match_status?: string | null
  categorized_account_id?: number | null
  expense_draft_suggested?: boolean
  suggestions?: Suggestion[]
}

interface JournalLine {
  transaction_id: number
  jv_number: string
  date: string
  description: string
  debit: number
  credit: number
}

function confTone(c: number | null | undefined): string {
  if (c == null) return "text-[var(--text-muted)]"
  if (c >= 90) return "text-emerald-700"
  if (c >= 70) return "text-amber-700"
  return "text-[var(--text-muted)]"
}

export default function BankImportDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const fmt = useFmt()

  const [imp, setImp] = useState<BankImport | null>(null)
  const [lines, setLines] = useState<StatementLine[]>([])
  const [txnMap, setTxnMap] = useState<Record<number, JournalLine>>({})
  const [matching, setMatching] = useState(false)
  const [matchMsg, setMatchMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    Promise.all([
      apiFetch<BankImport[]>("/api/bank-imports"),
      apiFetch<StatementLine[]>(`/api/bank-imports/${id}/lines`),
      apiFetch<JournalLine[]>("/api/reports/journal?limit=500"),
    ])
      .then(([imps, ls, jls]) => {
        setImp(imps.find(i => i.id === parseInt(id)) ?? null)
        setLines(ls)
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
      const res = await apiFetch<{
        newly_matched: number
        suggested: number
        total_matched: number
        import: BankImport
      }>(`/api/bank-imports/${id}/auto-match`, { method: "POST" })
      setMatchMsg(
        `Auto-matched ${res.newly_matched}; ${res.suggested} suggestion(s) ready (${res.total_matched} total matched).`,
      )
      setImp(res.import)
      const ls = await apiFetch<StatementLine[]>(`/api/bank-imports/${id}/lines`)
      setLines(ls)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Auto-match failed")
    } finally {
      setMatching(false)
    }
  }

  const accept = async (lineId: number, txnId?: number) => {
    try {
      await apiFetch(`/api/statement-lines/${lineId}/accept`, {
        method: "POST",
        body: JSON.stringify(txnId ? { transaction_id: txnId } : {}),
      })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Accept failed")
    }
  }

  const reject = async (lineId: number) => {
    try {
      await apiFetch(`/api/statement-lines/${lineId}/reject`, { method: "POST" })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed")
    }
  }

  if (loading) return <div className="text-sm text-[var(--text-primary)]/50 py-8 text-center">Loading…</div>
  if (!lines.length && !imp) return (
    <div className="text-sm text-red-700 py-8 text-center">{error ?? "Import not found"}</div>
  )

  const unmatched = lines.filter(l => !l.is_matched).length
  const pct = imp && imp.line_count > 0
    ? Math.round((imp.matched_count / imp.line_count) * 100)
    : 0

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <Link href="/bank-imports" className="text-sm text-[var(--primary)] hover:underline">
            ← Bank Statement Imports
          </Link>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] mt-1">
            {imp?.file_name ?? `Import #${id}`}
          </h1>
          {imp && (
            <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
              {imp.matched_count} / {imp.line_count} matched ({pct}%) · {fmtDate(imp.created_at)}
            </p>
          )}
        </div>
        <div className="flex gap-2 self-start">
          <Link href="/bank-imports/rules" className="text-sm border px-3 py-2 rounded-lg hover:bg-[#f0ede6]">
            Rules
          </Link>
          <button
            onClick={runAutoMatch}
            disabled={matching || unmatched === 0}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50 transition-colors"
          >
            <Zap className="w-4 h-4" />
            {matching ? "Matching…" : "Run Auto-Match"}
          </button>
        </div>
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

      {imp && imp.line_count > 0 && (
        <div>
          <div className="flex justify-between text-xs text-[var(--text-primary)]/60 mb-1">
            <span>{unmatched} unmatched</span>
            <span>{pct}% done</span>
          </div>
          <div className="h-1.5 bg-[var(--border)] rounded-full overflow-hidden">
            <div className="h-full bg-[var(--primary)] rounded-full transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      <div className="bg-white border border-[var(--border)] rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[780px]">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[#faf8f4]">
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">Date</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">{t('col.description', 'Description')}</th>
              <th className="text-right px-4 py-3 font-semibold text-[var(--text-primary)]/70">{t('col.debit', 'Debit')}</th>
              <th className="text-right px-4 py-3 font-semibold text-[var(--text-primary)]/70">{t('col.credit', 'Credit')}</th>
              <th className="text-right px-4 py-3 font-semibold text-[var(--text-primary)]/70">Conf.</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70 w-64">Match</th>
            </tr>
          </thead>
          <tbody>
            {lines.map(line => {
              const matchedJl = line.matched_transaction_id ? txnMap[line.matched_transaction_id] : null
              const suggestions = line.suggestions?.length
                ? line.suggestions
                : line.suggested_transaction_id
                  ? [{
                      transaction_id: line.suggested_transaction_id,
                      confidence: line.match_confidence ?? 0,
                      jv_number: txnMap[line.suggested_transaction_id]?.jv_number,
                    }]
                  : []
              return (
                <tr
                  key={line.id}
                  className={`border-b border-[var(--border)] last:border-0 ${line.is_matched ? "" : "bg-amber-50/30"}`}
                >
                  <td className="px-4 py-2.5 whitespace-nowrap">{fmtDate(line.date)}</td>
                  <td className="px-4 py-2.5 max-w-[220px]">
                    <span className="line-clamp-2">{line.description}</span>
                    {line.categorized_account_id && (
                      <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
                        Rule → account #{line.categorized_account_id}
                        {line.expense_draft_suggested ? " · expense draft" : ""}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{line.debit > 0 ? fmt(line.debit) : ""}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{line.credit > 0 ? fmt(line.credit) : ""}</td>
                  <td className={`px-4 py-2.5 text-right tabular-nums font-medium ${confTone(line.match_confidence)}`}>
                    {line.match_confidence != null ? `${Math.round(line.match_confidence)}%` : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    {line.is_matched ? (
                      <div className="flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <span className="text-xs text-emerald-700 truncate max-w-[120px]">
                          {matchedJl ? matchedJl.jv_number : `#${line.matched_transaction_id}`}
                        </span>
                        <button
                          onClick={() => reject(line.id)}
                          className="text-[var(--text-primary)]/30 hover:text-red-500 text-xs ml-1"
                          title="Reject / clear"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : suggestions.length > 0 ? (
                      <div className="space-y-1">
                        {suggestions.slice(0, 2).map(s => (
                          <div key={s.transaction_id} className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                            <span className="text-xs truncate max-w-[100px]">
                              {s.jv_number || `#${s.transaction_id}`} · {Math.round(s.confidence)}%
                            </span>
                            <button
                              type="button"
                              onClick={() => accept(line.id, s.transaction_id)}
                              className="text-xs bg-emerald-600 text-white px-1.5 py-0.5 rounded"
                            >
                              Accept
                            </button>
                          </div>
                        ))}
                        <button type="button" onClick={() => reject(line.id)} className="text-[10px] text-[var(--text-muted)] hover:text-red-600">
                          Reject suggestions
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-[var(--text-primary)]/30 shrink-0" />
                        <span className="text-xs text-[var(--text-primary)]/40">No match found</span>
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
