"use client"
import { useCallback, useEffect, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { apiFetch } from "@/lib/api"
import ReportGrid from "@/components/report-builder/ReportGrid"
import ColumnChooser from "@/components/report-builder/ColumnChooser"
import FilterBar from "@/components/report-builder/FilterBar"
import GroupByPicker from "@/components/report-builder/GroupByPicker"
import SavedReportsMenu from "@/components/report-builder/SavedReportsMenu"
import ExportMenu from "@/components/report-builder/ExportMenu"
import { emptyConfig } from "@/lib/reportTypes"
import type { SourceMeta, ReportConfig, RunResult, SavedReport } from "@/lib/reportTypes"
import { useTranslation } from "react-i18next"

const PAGE_SIZE = 100

const PERIOD_OPTIONS = [
  { label: "All time", value: "" },
  { label: "This month", value: "this_month" },
  { label: "This quarter", value: "this_quarter" },
  { label: "This year", value: "this_year" },
  { label: "YTD", value: "ytd" },
]

export default function ReportBuilderPage() {
  const { t } = useTranslation()

  const [sources, setSources] = useState<SourceMeta[]>([])
  const [sourceKey, setSourceKey] = useState("")
  const [config, setConfig] = useState<ReportConfig>(emptyConfig())
  const [result, setResult] = useState<RunResult | null>(null)
  const [saved, setSaved] = useState<SavedReport[]>([])
  const [page, setPage] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const source = sources.find(s => s.key === sourceKey)

  useEffect(() => {
    apiFetch<SourceMeta[]>("/api/report-builder/sources").then(s => {
      setSources(s)
      if (s[0]) { setSourceKey(s[0].key); setConfig(emptyConfig(s[0].default_columns)) }
    })
    apiFetch<SavedReport[]>("/api/report-builder/reports").then(setSaved)
  }, [])

  const run = useCallback((sk: string, cfg: ReportConfig, pg: number) => {
    if (!sk) return
    setError(null)
    apiFetch<RunResult>("/api/report-builder/run", {
      method: "POST",
      body: JSON.stringify({ source_key: sk, config: cfg, page: pg, page_size: PAGE_SIZE }),
    }).then(r => { setResult(r); setError(null) })
      .catch((e: unknown) => {
        setResult(null)
        setError(e instanceof Error ? e.message : "Report failed")
      })
  }, [])

  // Re-run whenever config changes — reset to page 0
  useEffect(() => {
    setPage(0)
    run(sourceKey, config, 0)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceKey, config, run])

  // Re-run when page changes (but page is already set)
  const goToPage = (pg: number) => {
    setPage(pg)
    run(sourceKey, config, pg)
  }

  const patch = (p: Partial<ReportConfig>) => setConfig(c => ({ ...c, ...p }))

  const pickSource = (k: string) => {
    const s = sources.find(x => x.key === k)
    setSourceKey(k); setConfig(emptyConfig(s?.default_columns ?? []))
  }

  const onSort = (field: string, dir: "asc" | "desc") => patch({ sort: [{ field, dir }] })
  const onCellFilter = (field: string, value: string) =>
    patch({ filters: [...config.filters, { field, op: "equals", value }] })

  const onPeriodChange = (preset: string) =>
    patch({ date_range: preset ? { preset } : null })

  const currentPreset = config.date_range?.preset ?? ""
  const hasPeriod = Boolean(source?.date_field)

  const totalPages = result ? Math.ceil(result.total_count / PAGE_SIZE) : 0

  const saveCurrent = async () => {
    const name = window.prompt("Report name?")
    if (!name) return
    const shared = window.confirm("Share with the whole organisation? (Cancel = private)")
    const rd = await apiFetch<SavedReport>("/api/report-builder/reports", {
      method: "POST",
      body: JSON.stringify({ name, source_key: sourceKey, config, visibility: shared ? "shared" : "private" }),
    })
    setSaved(s => [...s, rd])
  }
  const loadReport = (r: SavedReport) => { setSourceKey(r.source_key); setConfig(r.config) }
  const del = async (id: number) => {
    await apiFetch(`/api/report-builder/reports/${id}`, { method: "DELETE" })
    setSaved(s => s.filter(x => x.id !== id))
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-serif">Report Builder</h1>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <select value={sourceKey} onChange={e => pickSource(e.target.value)}
          className="text-sm border border-[#ede9e2] rounded-lg px-3 py-2 bg-white">
          {sources.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>

        {/* Period picker — only when source has a date_field */}
        {hasPeriod && (
          <select
            value={currentPreset}
            onChange={e => onPeriodChange(e.target.value)}
            className="text-sm border border-[#ede9e2] rounded-lg px-3 py-2 bg-white"
            title="Date period"
          >
            {PERIOD_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        )}

        {source && <ColumnChooser source={source} columns={config.columns} onChange={c => patch({ columns: c })} />}
        {source && <GroupByPicker source={source} groupBy={config.group_by}
          onChange={g => patch({ group_by: g, aggregates: g.length
            ? source.fields.filter(f => f.aggregatable && config.columns.includes(f.key)).map(f => ({ field: f.key, fn: "sum" as const }))
            : config.aggregates })} />}
        <div className="ml-auto flex gap-2">
          <SavedReportsMenu saved={saved} onLoad={loadReport} onSave={saveCurrent} onDelete={del} />
          <ExportMenu sourceKey={sourceKey} config={config} />
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          <span className="font-medium">Report failed:</span> {error}
        </div>
      )}

      {source && <FilterBar source={source} filters={config.filters} onChange={f => patch({ filters: f })} />}

      <ReportGrid result={result} sort={config.sort} onSort={onSort} onCellFilter={onCellFilter} />

      {/* Footer: row count + pagination */}
      {result && (
        <div className="flex items-center justify-between text-xs text-black/50">
          <span>{result.total_count} rows</span>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => goToPage(page - 1)}
                disabled={page === 0}
                className="flex items-center gap-1 px-2 py-1 border border-[#ede9e2] rounded disabled:opacity-40 enabled:hover:border-[#b8943f] enabled:hover:text-[#b8943f]"
              >
                <ChevronLeft size={14} /> Prev
              </button>
              <span>Page {page + 1} of {totalPages}</span>
              <button
                onClick={() => goToPage(page + 1)}
                disabled={page >= totalPages - 1}
                className="flex items-center gap-1 px-2 py-1 border border-[#ede9e2] rounded disabled:opacity-40 enabled:hover:border-[#b8943f] enabled:hover:text-[#b8943f]"
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
