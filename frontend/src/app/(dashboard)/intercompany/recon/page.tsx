"use client"

import { useEffect, useState } from "react"
import { GitCompareArrows, Search } from "lucide-react"
import { apiFetch } from "@/lib/api"
import Pagination from "@/components/Pagination"
import PrintHeader from "@/components/PrintHeader"
import { useFmt, useCurrency } from "@/context/SettingsContext"

interface ReconRow {
  from_tenant_id: number
  to_tenant_id: number
  from_tenant: string
  to_tenant: string
  ar_open: number
  ap_open: number
  variance: number
  status: "matched" | "break"
}

const PAGE_SIZE = 50

export default function IntercompanyReconPage() {
  const fmt = useFmt()
  const currency = useCurrency()
  const [q, setQ] = useState("")
  const [rows, setRows] = useState<ReconRow[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams()
    if (q) params.set("q", q)
    params.set("skip", String((page - 1) * PAGE_SIZE))
    params.set("limit", String(PAGE_SIZE))
    apiFetch<{ total: number; items: ReconRow[] }>(`/api/intercompany/recon?${params}`)
      .then(d => { setRows(d.items); setTotal(d.total); setIsLoading(false) })
      .catch(() => { setRows([]); setTotal(0); setIsLoading(false) })
  }, [q, page])

  useEffect(() => { setPage(1) }, [q])

  return (
    <div className="max-w-6xl mx-auto p-4">
      <PrintHeader title="Intercompany Reconciliation" orientation="landscape" />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">IC Reconciliation</h1>
          <p className="text-[var(--text-primary)]/60">
            Open intercompany AR vs AP by consolidation group pair
          </p>
        </div>
        <GitCompareArrows className="w-7 h-7 text-[var(--primary)] hidden md:block" />
      </div>

      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl print:hidden">
        <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">
          Search entity / status
        </label>
        <div className="relative max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-primary)]/40" />
          <input
            type="text"
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="e.g. SubCo or break"
            className="w-full border border-[var(--text-primary)]/10 rounded-lg pl-9 pr-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
          />
        </div>
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="table-freeze freeze-col">
          <table className="w-full text-left border-collapse min-w-[900px]">
            <thead>
              <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">From</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">To</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">AR Open ({currency})</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">AP Open ({currency})</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Variance ({currency})</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-[var(--text-primary)]/50">Loading…</td>
                </tr>
              ) : !rows?.length ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-[var(--text-primary)]/50">
                    No IC activity for this group
                  </td>
                </tr>
              ) : rows.map(r => (
                <tr key={`${r.from_tenant_id}-${r.to_tenant_id}`} className="hover:bg-[var(--bg-page)]/50">
                  <td className="px-4 py-3 text-sm whitespace-nowrap freeze-col">{r.from_tenant}</td>
                  <td className="px-4 py-3 text-sm whitespace-nowrap">{r.to_tenant}</td>
                  <td className="px-4 py-3 text-sm text-right font-mono">{fmt(r.ar_open)}</td>
                  <td className="px-4 py-3 text-sm text-right font-mono">{fmt(r.ap_open)}</td>
                  <td className="px-4 py-3 text-sm text-right font-mono">{fmt(r.variance)}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className={r.status === "break" ? "text-amber-700 font-medium" : "text-emerald-700"}>
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 print:hidden">
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
      </div>
    </div>
  )
}
