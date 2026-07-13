"use client"

import { Fragment, useEffect, useState } from "react"
import { TrendingUp } from "lucide-react"
import { apiFetch } from "@/lib/api"
import DateRangePicker from "@/components/DateRangePicker"
import { useFmt } from "@/context/SettingsContext"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

interface Vendor {
  id: number
  name: string
}

interface RateTrendEntry {
  product_id: number
  product_name: string | null
  quote_date: string
  rate: number
}

interface VendorPerformanceRow {
  vendor_id: number
  vendor_name: string
  po_count: number
  avg_lead_time_days: number | null
  short_receipt_rate_pct: number
  rate_trend: RateTrendEntry[]
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return {
    start: from.toISOString().split("T")[0],
    end: to.toISOString().split("T")[0],
  }
}

export default function VendorPerformancePage() {
  const fmt = useFmt()
  const range = defaultRange()

  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [vendorId, setVendorId] = useState("")
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [rows, setRows] = useState<VendorPerformanceRow[] | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    apiFetch<{ items: Vendor[] }>("/api/vendors?limit=500")
      .then(d => setVendors(d.items))
      .catch(() => setVendors([]))
  }, [])

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams()
    if (start) params.set("start", start)
    if (end) params.set("end", end)
    if (vendorId) params.set("vendor_id", vendorId)
    apiFetch<VendorPerformanceRow[]>(`/api/purchase-reports/vendor-performance?${params.toString()}`)
      .then(d => { setRows(d); setIsLoading(false) })
      .catch(() => { setRows([]); setIsLoading(false) })
  }, [start, end, vendorId])

  const printSubtitle = `Period: ${start} – ${end}`

  return (
    <div className="max-w-6xl mx-auto p-4">
      <PrintHeader title="Vendor Performance" subtitle={printSubtitle} orientation="landscape" />

      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Vendor Performance</h1>
          <p className="text-[var(--text-primary)]/60">PO volume, average lead time, short-receipt rate and quoted-rate trend by vendor</p>
        </div>
        <TrendingUp className="w-7 h-7 text-[var(--primary)] hidden md:block" />
      </div>

      {/* Filters */}
      <div className="mb-6 p-4 bg-white border border-[var(--border)] rounded-xl grid grid-cols-1 md:grid-cols-3 gap-4 print:hidden">
        <div className="md:col-span-2 flex items-end">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Vendor</label>
          <select
            value={vendorId}
            onChange={e => setVendorId(e.target.value)}
            className="w-full border border-[var(--text-primary)]/10 rounded-lg px-3 py-2 text-sm bg-[var(--bg-page)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
          >
            <option value="">All Vendors</option>
            {vendors.map(v => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="table-freeze freeze-col">
          <table className="w-full text-left border-collapse min-w-[900px]">
            <thead>
              <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Vendor</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">PO Count</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Avg Lead Time (days)</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Short-Receipt Rate (%)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={4} className="px-6 py-10 text-center text-[var(--text-primary)]/75">Loading...</td>
                </tr>
              ) : !rows || rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-10 text-center text-[var(--text-primary)]/75">
                    No vendors with purchase orders or quotations found for the selected filters.
                  </td>
                </tr>
              ) : (
                rows.map(row => (
                  <Fragment key={row.vendor_id}>
                    <tr className="hover:bg-[var(--bg-page)]/30 transition-colors">
                      <td className="ui-td text-sm font-semibold text-[var(--text-primary)]">{row.vendor_name}</td>
                      <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{row.po_count}</td>
                      <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">
                        {row.avg_lead_time_days === null ? "—" : fmt(row.avg_lead_time_days)}
                      </td>
                      <td className={`ui-td text-right font-mono text-sm font-semibold ${row.short_receipt_rate_pct > 0 ? "text-red-600" : "text-[var(--text-primary)]/70"}`}>
                        {fmt(row.short_receipt_rate_pct)}
                      </td>
                    </tr>
                    {row.rate_trend.length > 0 && (
                      <tr className="bg-[var(--bg-page)]/40">
                        <td colSpan={4} className="ui-td px-6 py-3">
                          <div className="text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-2">
                            Rate Trend — {row.vendor_name}
                          </div>
                          <table className="w-full text-left border-collapse">
                            <thead>
                              <tr className="border-b border-[var(--text-primary)]/10">
                                <th className="py-1 pr-4 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Product</th>
                                <th className="py-1 pr-4 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60">Quote Date</th>
                                <th className="py-1 pr-4 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 text-right">Rate</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--text-primary)]/5">
                              {row.rate_trend.map((rt, idx) => (
                                <tr key={idx}>
                                  <td className="py-1 pr-4 text-sm text-[var(--text-primary)]/70">{rt.product_name || rt.product_id}</td>
                                  <td className="py-1 pr-4 text-sm text-[var(--text-primary)]/70 whitespace-nowrap">{fmtDate(rt.quote_date)}</td>
                                  <td className="py-1 pr-4 text-right font-mono text-sm text-[var(--text-primary)]/70">{fmt(rt.rate)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <p className="mt-4 text-xs text-[var(--text-primary)]/50 print:mt-2">
        Short-receipt rate approximates rejection rate from quantity variance; this system does not track a separate accepted/rejected quantity.
      </p>
    </div>
  )
}
