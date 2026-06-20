"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, Printer, Package, Download } from "lucide-react"
import { downloadCSV } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"

interface MovementEntry {
  date: string
  direction: string
  lot_no: string | null
  from_location_id: number | null
  to_location_id: number | null
  qty_in: string | null
  qty_out: string | null
  unit_cost: string
  total_cost: string
  running_qty: string
  running_value: string
  source_doc_type: string | null
  source_doc_id: number | null
  posted_to_gl: boolean
  notes: string | null
}
interface StockCard {
  product: { id: number; code: string | null; name: string; unit: string; product_type: string; stock_qty_snapshot: string; avg_cost_snapshot: string }
  period: { start: string | null; end: string | null }
  opening_qty: string
  opening_value: string
  entries: MovementEntry[]
  closing_qty: string
  closing_value: string
  totals: { qty_in: string; qty_out: string }
}

const DOC_HREF: Record<string, (id: number) => string> = {
  bill:               id => `/bills/${id}`,
  invoice:            id => `/invoices/${id}`,
  grn:                id => `/manufacturing/grn/${id}/print`,
  production_order:   id => `/manufacturing/production-orders/${id}/print`,
}

const DIRECTION_TONE: Record<string, string> = {
  RECEIPT:               "bg-emerald-100 text-emerald-900",
  CUSTODIAL_RECEIPT:     "bg-teal-100 text-teal-900",
  ISSUE:                 "bg-amber-100 text-amber-900",
  CUSTODIAL_ISSUE:       "bg-amber-100 text-amber-900",
  COMPLETION:            "bg-blue-100 text-blue-900",
  CUSTODIAL_COMPLETION:  "bg-blue-100 text-blue-900",
  DELIVERY:              "bg-violet-100 text-violet-900",
  SHIPMENT:              "bg-violet-100 text-violet-900",
  ADJUSTMENT:            "bg-slate-100 text-slate-700",
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

export default function ProductStockCardPage({ params }: { params: Promise<{ id: string }> }) {
  const fmt = useFmt()
  const { id } = use(params)
  const r0 = defaultRange()
  const [start, setStart] = useState(r0.start)
  const [end, setEnd]     = useState(r0.end)
  const [data, setData]   = useState<StockCard | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<StockCard>(`/api/products/${id}/stock-card?start=${start}&end=${end}`)
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id, start, end])

  if (error && !data) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!data)          return <p className="p-4 text-[#1a1814]/60 text-sm">Loading stock card…</p>

  const p = data.product

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <PrintHeader title={`Stock Card — ${p.code ?? p.name}`} subtitle={`Period ${start} → ${end}`} orientation="landscape" />

      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <Link href={`/products/${id}`} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-[#1a1814]/65 hover:text-[#b8943f]">
          <ArrowLeft className="w-4 h-4" /> Product
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={() => data && downloadCSV(`stock-card-${data.product.code ?? data.product.name}.csv`, data.entries.map(e => ({ Date: e.date, Direction: e.direction, "Lot #": e.lot_no ?? '', "Qty In": e.qty_in ?? '', "Qty Out": e.qty_out ?? '', "Unit Cost": e.unit_cost, "Total Cost": e.total_cost, "Running Qty": e.running_qty, "Running Value": e.running_value, Source: e.source_doc_type ?? '' })))}
            disabled={!data || data.entries.length === 0}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button onClick={() => window.print()} className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] print:hidden">
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
      </div>

      <header className="bg-white border border-[#ede9e2] rounded-xl p-5 flex items-start gap-3 print:hidden">
        <Package className="w-7 h-7 text-[#b8943f] shrink-0 mt-1" />
        <div className="min-w-0">
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814] truncate">{p.name}</h1>
          <p className="text-xs text-[#1a1814]/60">
            {p.code && <span className="font-mono">{p.code}</span>}
            <span> · {p.product_type} · unit: {p.unit}</span>
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 print:hidden">
        <div className="bg-white border border-[#ede9e2] rounded-xl p-4">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
        </div>
        <div className="bg-white border border-[#ede9e2] rounded-xl p-4 grid grid-cols-4 gap-3 text-center">
          <Stat label="Opening qty" value={data.opening_qty} />
          <Stat label="Qty in"      value={data.totals.qty_in}  tone="emerald" />
          <Stat label="Qty out"     value={data.totals.qty_out} tone="amber"   />
          <Stat label="Closing qty" value={data.closing_qty} />
        </div>
      </div>

      <section className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-xs min-w-[920px]">
          <thead className="bg-[#faf6ec]">
            <tr>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Date</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Direction</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Lot</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Source</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-20">Qty in</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-20">Qty out</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-24">Unit cost</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-24">Run qty</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Run value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            <tr className="bg-[#faf8f4]">
              <td colSpan={7} className="px-3 py-2 text-[11px] font-bold text-[#1a1814]/55">Opening</td>
              <td className="px-3 py-2 text-right font-mono font-bold">{data.opening_qty}</td>
              <td className="px-3 py-2 text-right font-mono font-bold">{fmt(Number(data.opening_value))}</td>
            </tr>
            {data.entries.map((m, i) => {
              const href = m.source_doc_id && m.source_doc_type ? DOC_HREF[m.source_doc_type]?.(m.source_doc_id) : undefined
              return (
                <tr key={i}>
                  <td className="px-3 py-2 text-[#1a1814]/70">{m.date}</td>
                  <td className="px-3 py-2">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${DIRECTION_TONE[m.direction] ?? "bg-slate-100 text-slate-700"}`}>
                      {m.direction}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono">{m.lot_no ?? "—"}</td>
                  <td className="px-3 py-2 font-mono">
                    {m.source_doc_type ? (
                      href ? (
                        <Link href={href} className="text-[#b8943f] hover:underline">{m.source_doc_type}#{m.source_doc_id}</Link>
                      ) : <>{m.source_doc_type}#{m.source_doc_id}</>
                    ) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-emerald-700">{m.qty_in ?? ""}</td>
                  <td className="px-3 py-2 text-right font-mono text-amber-700">{m.qty_out ?? ""}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(Number(m.unit_cost))}</td>
                  <td className="px-3 py-2 text-right font-mono font-semibold">{m.running_qty}</td>
                  <td className="px-3 py-2 text-right font-mono font-semibold">{fmt(Number(m.running_value))}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-[#1a1814] bg-[#faf6ec]">
              <td colSpan={4} className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Closing</td>
              <td className="px-3 py-2 text-right font-mono font-bold text-emerald-700">{data.totals.qty_in}</td>
              <td className="px-3 py-2 text-right font-mono font-bold text-amber-700">{data.totals.qty_out}</td>
              <td className="px-3 py-2"></td>
              <td className="px-3 py-2 text-right font-mono font-bold">{data.closing_qty}</td>
              <td className="px-3 py-2 text-right font-mono font-bold">{fmt(Number(data.closing_value))}</td>
            </tr>
          </tfoot>
        </table>
        </div>
      </section>
    </div>
  )
}

function Stat({ label, value, tone = "default" }: {
  label: string; value: string; tone?: "default" | "amber" | "emerald"
}) {
  const toneCls = tone === "amber"   ? "text-amber-700"
                : tone === "emerald" ? "text-emerald-700"
                : "text-[#1a1814]"
  return (
    <div>
      <div className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-0.5">{label}</div>
      <div className={`font-mono text-sm font-bold ${toneCls}`}>{value}</div>
    </div>
  )
}
