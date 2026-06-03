"use client"
import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import ReportGrid from "@/components/report-builder/ReportGrid"
import ColumnChooser from "@/components/report-builder/ColumnChooser"
import FilterBar from "@/components/report-builder/FilterBar"
import GroupByPicker from "@/components/report-builder/GroupByPicker"
import SavedReportsMenu from "@/components/report-builder/SavedReportsMenu"
import ExportMenu from "@/components/report-builder/ExportMenu"
import { emptyConfig } from "@/lib/reportTypes"
import type { SourceMeta, ReportConfig, RunResult, SavedReport } from "@/lib/reportTypes"

export default function ReportBuilderPage() {
  const [sources, setSources] = useState<SourceMeta[]>([])
  const [sourceKey, setSourceKey] = useState("")
  const [config, setConfig] = useState<ReportConfig>(emptyConfig())
  const [result, setResult] = useState<RunResult | null>(null)
  const [saved, setSaved] = useState<SavedReport[]>([])
  const source = sources.find(s => s.key === sourceKey)

  useEffect(() => {
    apiFetch<SourceMeta[]>("/api/report-builder/sources").then(s => {
      setSources(s)
      if (s[0]) { setSourceKey(s[0].key); setConfig(emptyConfig(s[0].default_columns)) }
    })
    apiFetch<SavedReport[]>("/api/report-builder/reports").then(setSaved)
  }, [])

  const run = useCallback((sk: string, cfg: ReportConfig) => {
    if (!sk) return
    apiFetch<RunResult>("/api/report-builder/run", {
      method: "POST", body: JSON.stringify({ source_key: sk, config: cfg }),
    }).then(setResult).catch(() => setResult(null))
  }, [])

  useEffect(() => { run(sourceKey, config) }, [sourceKey, config, run])

  const patch = (p: Partial<ReportConfig>) => setConfig(c => ({ ...c, ...p }))
  const pickSource = (k: string) => {
    const s = sources.find(x => x.key === k)
    setSourceKey(k); setConfig(emptyConfig(s?.default_columns ?? []))
  }
  const onSort = (field: string, dir: "asc" | "desc") => patch({ sort: [{ field, dir }] })
  const onCellFilter = (field: string, value: string) =>
    patch({ filters: [...config.filters, { field, op: "equals", value }] })

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
      <div className="flex flex-wrap items-center gap-2">
        <select value={sourceKey} onChange={e => pickSource(e.target.value)}
          className="text-sm border border-[#ede9e2] rounded-lg px-3 py-2 bg-white">
          {sources.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
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
      {source && <FilterBar source={source} filters={config.filters} onChange={f => patch({ filters: f })} />}
      <ReportGrid result={result} sort={config.sort} onSort={onSort} onCellFilter={onCellFilter} />
      {result && <p className="text-xs text-black/40">{result.total_count} rows</p>}
    </div>
  )
}
