"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Download, Printer, ArrowLeft } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV, fmtDate, todayLocal } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
import DocLink from "@/components/DocLink"
import { useTranslation } from "react-i18next"

interface RollforwardRow {
  asset_id: number
  name: string
  code: string | null
  parent_id: number | null
  opening: number
  additions: number
  disposals: number
  depreciation: number
  impairment: number
  closing: number
}

interface RollforwardTotals {
  opening: number
  additions: number
  disposals: number
  depreciation: number
  impairment: number
  closing: number
}

interface RollforwardData {
  rows: RollforwardRow[]
  totals: RollforwardTotals
}

function defaultRange() {
  const end = todayLocal()
  const y = new Date().getFullYear()
  return { start: `${y}-01-01`, end }
}

export default function AssetRollforwardPage() {
  const { t } = useTranslation()
  const fmt = useFmt()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<RollforwardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!start || !end) return
    setLoading(true)
    setError("")
    apiFetch<RollforwardData>(`/api/assets/reports/rollforward?start=${start}&end=${end}`)
      .then(setData)
      .catch(e => { setError(e instanceof Error ? e.message : "Failed to load"); setData(null) })
      .finally(() => setLoading(false))
  }, [start, end])

  const rows = data?.rows ?? []
  const totals = data?.totals

  const exportCsv = () => {
    if (!rows.length) return
    downloadCSV(`asset-rollforward-${start}-${end}.csv`, rows.map(r => ({
      Name: r.name,
      Code: r.code ?? "",
      Parent: r.parent_id ?? "",
      Opening: r.opening,
      Additions: r.additions,
      Disposals: r.disposals,
      Depreciation: r.depreciation,
      Impairment: r.impairment,
      Closing: r.closing,
    })))
  }

  const subtitle = start && end ? `${fmtDate(start)} – ${fmtDate(end)}` : ""

  return (
    <div className="space-y-6">
      <PrintHeader title="Fixed Asset Rollforward" subtitle={subtitle} orientation="landscape" />

      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 print:hidden">
        <div>
          <Link href="/assets" className="inline-flex items-center gap-1 text-xs text-[var(--text-primary)]/50 hover:text-[var(--primary)] mb-2">
            <ArrowLeft className="w-3.5 h-3.5" /> Fixed Assets
          </Link>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Fixed Asset Rollforward</h1>
          <p className="text-sm text-[var(--text-primary)]/60 mt-1">
            Opening → additions → disposals → depreciation → impairment → closing NBV
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={exportCsv}
            disabled={!rows.length}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t("common.print", "Print")}
          </button>
        </div>
      </div>

      <div className="print:hidden bg-white border border-[var(--border)] rounded-xl px-4 py-3">
        <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">{error}</div>
      )}

      <div className="bg-white rounded-2xl border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="overflow-x-auto table-freeze freeze-col">
          <table className="w-full text-sm min-w-[800px]">
            <thead className="bg-[var(--bg-page)]">
              <tr>
                {["Asset", "Opening", "Additions", "Disposals", "Depreciation", "Impairment", "Closing"].map(h => (
                  <th
                    key={h}
                    className={`ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/50 ${h === "Asset" ? "text-left" : "text-right"}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="ui-td text-center text-[var(--text-primary)]/40 italic">
                    {t("common.loading", "Loading...")}
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="ui-td text-center text-[var(--text-primary)]/40 italic py-10">
                    No assets in this period
                  </td>
                </tr>
              ) : rows.map(r => (
                <tr key={r.asset_id} className="border-t border-[var(--text-primary)]/5 hover:bg-[var(--bg-page)]/50">
                  <td className="ui-td font-medium">
                    <span className={r.parent_id ? "pl-5 inline-flex items-center gap-1" : ""}>
                      {r.parent_id ? <span className="text-[var(--text-primary)]/30 text-xs">↳</span> : null}
                      <DocLink type="fixed_asset" id={r.asset_id} label={r.name} className="font-medium" />
                    </span>
                    {r.code && <span className="ml-2 text-xs text-[var(--text-primary)]/40">{r.code}</span>}
                  </td>
                  <td className="ui-td font-mono text-right">{fmt(r.opening)}</td>
                  <td className="ui-td font-mono text-right">{r.additions ? fmt(r.additions) : "—"}</td>
                  <td className="ui-td font-mono text-right text-red-600">{r.disposals ? `(${fmt(Math.abs(r.disposals))})` : "—"}</td>
                  <td className="ui-td font-mono text-right text-red-600">{r.depreciation ? `(${fmt(Math.abs(r.depreciation))})` : "—"}</td>
                  <td className="ui-td font-mono text-right text-red-600">{r.impairment ? `(${fmt(Math.abs(r.impairment))})` : "—"}</td>
                  <td className="ui-td font-mono text-right font-bold">{fmt(r.closing)}</td>
                </tr>
              ))}
            </tbody>
            {totals && rows.length > 0 && (
              <tfoot>
                <tr className="border-t-2 border-[var(--text-primary)]/20 bg-[var(--bg-page)] font-bold">
                  <td className="ui-td">Totals</td>
                  <td className="ui-td font-mono text-right">{fmt(totals.opening)}</td>
                  <td className="ui-td font-mono text-right">{fmt(totals.additions)}</td>
                  <td className="ui-td font-mono text-right text-red-600">({fmt(Math.abs(totals.disposals))})</td>
                  <td className="ui-td font-mono text-right text-red-600">({fmt(Math.abs(totals.depreciation))})</td>
                  <td className="ui-td font-mono text-right text-red-600">({fmt(Math.abs(totals.impairment))})</td>
                  <td className="ui-td font-mono text-right">{fmt(totals.closing)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </div>
  )
}
