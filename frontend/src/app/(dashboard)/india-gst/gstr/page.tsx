"use client"

import { useEffect, useState } from "react"
import { Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV, fmtDate } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"
import { useBreadcrumb } from "@/context/BreadcrumbContext"

interface GstrRow {
  invoice_id: number
  invoice_number: string
  issue_date: string
  customer_name: string
  gstin: string
  state_code: string
  hsn_sac: string
  taxable: number
  cgst: number
  sgst: number
  igst: number
  total_tax: number
  invoice_total: number
}

interface Gstr1 {
  period: { start: string; end: string }
  gstin: string
  state_code: string
  b2b: GstrRow[]
  totals: {
    invoice_count: number
    taxable: number
    cgst: number
    sgst: number
    igst: number
    total_tax: number
  }
}

function defaultRange() {
  const today = new Date()
  const start = new Date(today.getFullYear(), today.getMonth(), 1)
  return {
    start: start.toISOString().split("T")[0],
    end: today.toISOString().split("T")[0],
  }
}

export default function IndiaGstrPage() {
  useBreadcrumb("GSTR Report")
  const fmt = useFmt()
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<Gstr1 | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setError("")
    apiFetch<Gstr1>(`/api/india-gst/gstr1?start=${start}&end=${end}`)
      .then(setData)
      .catch(err => setError((err as Error).message))
      .finally(() => setLoading(false))
  }, [start, end])

  const exportCsv = () => {
    if (!data) return
    downloadCSV(
      `gstr1-${start}-${end}.csv`,
      data.b2b.map(r => ({
        Invoice: r.invoice_number,
        Date: r.issue_date,
        Customer: r.customer_name,
        GSTIN: r.gstin,
        State: r.state_code,
        HSN_SAC: r.hsn_sac,
        Taxable: r.taxable,
        CGST: r.cgst,
        SGST: r.sgst,
        IGST: r.igst,
        TotalTax: r.total_tax,
        InvoiceTotal: r.invoice_total,
      })),
    )
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <PrintHeader
        title="GSTR-1 Summary"
        subtitle={`Period: ${fmtDate(start)} — ${fmtDate(end)}`}
        orientation="landscape"
      />
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold">GSTR Report</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            India GST B2B outward supplies (GSTR-1 style)
            {data?.gstin ? ` · GSTIN ${data.gstin}` : ""}
            {data?.state_code ? ` · State ${data.state_code}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="p-3 bg-white border border-[var(--border)] rounded-xl">
            <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Tax period" />
          </div>
          <button
            onClick={exportCsv}
            disabled={!data}
            className="p-3 bg-white border border-[var(--border)] rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60 disabled:opacity-40"
            title="Export CSV"
          >
            <Download className="w-5 h-5" />
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600 print:hidden">{error}</p>}
      {loading && !data && <p className="text-sm text-[var(--text-muted)]">Loading…</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 print:hidden">
            {[
              ["Invoices", data.totals.invoice_count],
              ["Taxable", fmt(data.totals.taxable)],
              ["CGST", fmt(data.totals.cgst)],
              ["SGST", fmt(data.totals.sgst)],
              ["IGST", fmt(data.totals.igst)],
            ].map(([label, val]) => (
              <div key={String(label)} className="bg-white border border-[var(--border)] rounded-xl p-3">
                <div className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">{label}</div>
                <div className="text-lg font-semibold tabular-nums mt-1">{val}</div>
              </div>
            ))}
          </div>

          <div className="table-freeze freeze-col bg-white border border-[var(--border)] rounded-xl overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-[var(--text-muted)]">
                  <th className="px-3 py-2 whitespace-nowrap">Invoice</th>
                  <th className="px-3 py-2 whitespace-nowrap">Date</th>
                  <th className="px-3 py-2">Customer</th>
                  <th className="px-3 py-2 whitespace-nowrap">GSTIN</th>
                  <th className="px-3 py-2 whitespace-nowrap">State</th>
                  <th className="px-3 py-2 text-right whitespace-nowrap">Taxable</th>
                  <th className="px-3 py-2 text-right whitespace-nowrap">CGST</th>
                  <th className="px-3 py-2 text-right whitespace-nowrap">SGST</th>
                  <th className="px-3 py-2 text-right whitespace-nowrap">IGST</th>
                </tr>
              </thead>
              <tbody>
                {data.b2b.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-3 py-8 text-center text-[var(--text-muted)]">
                      No B2B invoices in this period
                    </td>
                  </tr>
                ) : (
                  data.b2b.map(r => (
                    <tr key={r.invoice_id} className="border-b border-[var(--border)]/60">
                      <td className="px-3 py-2 whitespace-nowrap font-mono text-xs">{r.invoice_number}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.issue_date)}</td>
                      <td className="px-3 py-2">{r.customer_name}</td>
                      <td className="px-3 py-2 whitespace-nowrap font-mono text-xs">{r.gstin || "—"}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{r.state_code || "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmt(r.taxable)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmt(r.cgst)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmt(r.sgst)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmt(r.igst)}</td>
                    </tr>
                  ))
                )}
              </tbody>
              {data.b2b.length > 0 && (
                <tfoot>
                  <tr className="border-t border-[var(--border)] font-semibold">
                    <td className="px-3 py-2" colSpan={5}>Totals</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmt(data.totals.taxable)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmt(data.totals.cgst)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmt(data.totals.sgst)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmt(data.totals.igst)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </>
      )}
    </div>
  )
}
