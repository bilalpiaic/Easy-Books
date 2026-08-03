"use client"

import { useEffect, useState } from "react"
import { Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV, fmtDateJs } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
import type { AnalyticDimension, AnalyticAccount } from "@/components/DimensionPickers"

interface PlLine {
  name: string
  code: string
  type: string
  total_debit: number
  total_credit: number
  amount: number
}

interface Segment {
  analytic: { id: number; code: string; name: string }
  lines: PlLine[]
  totals: { revenue: number; expenses: number; net_profit: number }
}

interface DimPlResponse {
  mode: "analytic" | "breakdown"
  analytic?: { id: number; code: string; name: string }
  dimension?: { id: number; code: string; name: string } | null
  lines?: PlLine[]
  totals?: { revenue: number; expenses: number; net_profit: number }
  segments?: Segment[]
}

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function yearStartISO() {
  const d = new Date()
  return `${d.getFullYear()}-01-01`
}

export default function DimensionalPlPage() {
  const { fmt } = useFmt()
  const [start, setStart] = useState(yearStartISO())
  const [end, setEnd] = useState(todayISO())
  const [dimensions, setDimensions] = useState<AnalyticDimension[]>([])
  const [accounts, setAccounts] = useState<AnalyticAccount[]>([])
  const [dimensionId, setDimensionId] = useState("")
  const [analyticId, setAnalyticId] = useState("")
  const [data, setData] = useState<DimPlResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    Promise.all([
      apiFetch<{ items: AnalyticDimension[] }>("/api/analytic-dimensions"),
      apiFetch<{ items: AnalyticAccount[] }>("/api/analytic-accounts?limit=500"),
    ]).then(([d, a]) => {
      setDimensions(d.items ?? [])
      setAccounts(a.items ?? [])
      if (d.items?.[0]) setDimensionId(String(d.items[0].id))
    }).catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [])

  const load = () => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ start, end })
    if (analyticId) params.set("analytic_id", analyticId)
    else if (dimensionId) params.set("dimension_id", dimensionId)
    apiFetch<DimPlResponse>(`/api/reports/dimensional-pl?${params}`)
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load report"))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (dimensionId || analyticId) load()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dimensionId, analyticId, start, end])

  const filteredAccounts = dimensionId
    ? accounts.filter(a => !a.dimension_id || String(a.dimension_id) === dimensionId)
    : accounts

  const subtitle = `${fmtDateJs(new Date(start + "T00:00:00"))} – ${fmtDateJs(new Date(end + "T00:00:00"))}`

  return (
    <div className="space-y-6">
      <PrintHeader title="Dimensional P&L" subtitle={subtitle} />
      <div className="flex items-center justify-between print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Dimensional P&amp;L</h1>
          <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
            Income statement filtered or broken down by analytic dimension.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)]"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
          <button
            onClick={() => {
              const rows: Record<string, unknown>[] = []
              if (data?.mode === "analytic" && data.lines) {
                for (const l of data.lines) {
                  rows.push({ Account: l.name, Code: l.code, Type: l.type, Amount: l.amount })
                }
              } else if (data?.segments) {
                for (const seg of data.segments) {
                  for (const l of seg.lines) {
                    rows.push({
                      Analytic: `${seg.analytic.code} ${seg.analytic.name}`,
                      Account: l.name, Code: l.code, Type: l.type, Amount: l.amount,
                    })
                  }
                }
              }
              downloadCSV("dimensional-pl.csv", rows)
            }}
            disabled={!data}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
        </div>
      </div>

      <div className="bg-white border border-[var(--border)] rounded-xl p-4 print:hidden space-y-3">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Dimension</label>
            <select
              value={dimensionId}
              onChange={e => { setDimensionId(e.target.value); setAnalyticId("") }}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl text-sm outline-none focus:ring-2 focus:ring-[var(--primary)]"
            >
              <option value="">— all —</option>
              {dimensions.map(d => (
                <option key={d.id} value={d.id}>{d.code} — {d.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Analytic value</label>
            <select
              value={analyticId}
              onChange={e => setAnalyticId(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl text-sm outline-none focus:ring-2 focus:ring-[var(--primary)]"
            >
              <option value="">— breakdown —</option>
              {filteredAccounts.map(a => (
                <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}
      {loading && <p className="text-sm text-[var(--text-primary)]/50">Loading…</p>}

      {data?.mode === "analytic" && data.lines && (
        <PlTable
          title={`${data.analytic?.code} — ${data.analytic?.name}`}
          lines={data.lines}
          totals={data.totals!}
          fmt={fmt}
        />
      )}

      {data?.mode === "breakdown" && (
        <div className="space-y-6">
          {(data.segments ?? []).length === 0 ? (
            <p className="text-sm text-[var(--text-primary)]/50 py-8 text-center">
              No tagged P&amp;L activity for this selection.
            </p>
          ) : (
            (data.segments ?? []).map(seg => (
              <PlTable
                key={seg.analytic.id}
                title={`${seg.analytic.code} — ${seg.analytic.name}`}
                lines={seg.lines}
                totals={seg.totals}
                fmt={fmt}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

function PlTable({
  title, lines, totals, fmt,
}: {
  title: string
  lines: PlLine[]
  totals: { revenue: number; expenses: number; net_profit: number }
  fmt: (n: number | string) => string
}) {
  return (
    <div className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--border)] bg-[#faf8f4]">
        <h2 className="text-sm font-bold text-[var(--text-primary)]">{title}</h2>
      </div>
      <div className="table-freeze overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/70">Account</th>
              <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/70">Type</th>
              <th className="text-right px-4 py-2 font-semibold text-[var(--text-primary)]/70">Amount</th>
            </tr>
          </thead>
          <tbody>
            {lines.map(l => (
              <tr key={`${l.code}-${l.type}`} className="border-b border-[var(--border)] last:border-0">
                <td className="px-4 py-2 whitespace-nowrap">
                  <span className="font-mono text-xs text-[var(--text-primary)]/55 mr-2">{l.code}</span>
                  {l.name}
                </td>
                <td className="px-4 py-2 text-[var(--text-primary)]/60">{l.type}</td>
                <td className="px-4 py-2 text-right font-medium">{fmt(Number(l.amount))}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-[var(--border)] bg-[#faf8f4] font-semibold">
              <td className="px-4 py-2" colSpan={2}>Net profit</td>
              <td className="px-4 py-2 text-right">{fmt(Number(totals.net_profit))}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}
