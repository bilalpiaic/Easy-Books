"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface PO {
  id: number
  number: string
  state: string
  bom_id: number
  customer_id: number
  rate_plan_id: number | null
  output_qty: string | number
  own_material_cost: string | number
  output_unit_cost: string | number
  invoice_id: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  delivered_at: string | null
  billed_at: string | null
  cancelled_at: string | null
  notes: string | null
}

const fmt = (v: string | number) => {
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  const abs = Math.abs(n)
  const s = abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? `(${s})` : s
}

const STATE_TONE: Record<string, string> = {
  draft:     "bg-slate-100 text-slate-800 border-slate-300",
  started:   "bg-amber-100 text-amber-900 border-amber-300",
  completed: "bg-blue-100 text-blue-900 border-blue-300",
  delivered: "bg-emerald-100 text-emerald-900 border-emerald-300",
  billed:    "bg-violet-100 text-violet-900 border-violet-300",
  cancelled: "bg-red-100 text-red-900 border-red-300",
}

export default function POPrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const { id } = use(params)
  const router = useRouter()
  const [po, setPo]       = useState<PO | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<PO>(`/api/production-orders/${id}`)
      .then(d => { setPo(d); setTimeout(() => window.print(), 300) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!po)   return <p className="p-4 text-[#1a1814]/60 text-sm">Loading production order…</p>

  const timeline = [
    { state: "draft",     label: "Drafted",   at: po.created_at },
    { state: "started",   label: "Started",   at: po.started_at },
    { state: "completed", label: "Completed", at: po.completed_at },
    { state: "delivered", label: "Delivered", at: po.delivered_at },
    { state: "billed",    label: "Billed",    at: po.billed_at },
  ].filter(t => t.at)

  return (
    <div className="bg-white min-h-screen">
      <div className="print:hidden flex items-center justify-between bg-[#1a1814] text-white px-4 py-2 mb-4">
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm hover:text-[#ffd966]">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#b8943f] hover:bg-[#d4af60] text-black rounded-md text-sm font-semibold"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-10">
        <PrintHeader title={`Production Order ${po.number}`} subtitle={`Customer #${po.customer_id} · ${po.state.toUpperCase()}`} />

        <article className="text-[#1a1814]">
          <header className="mb-6 print:hidden border-b border-[#ede9e2] pb-4 flex items-start justify-between">
            <div>
              <h1 className="text-lg sm:text-2xl font-serif font-semibold">Production Order {po.number}</h1>
              <p className="text-sm text-[#1a1814]/60">For customer #{po.customer_id}</p>
            </div>
            <span className={`inline-block border rounded-full px-3 py-1 text-xs font-semibold ${STATE_TONE[po.state] ?? ""}`}>
              {po.state}
            </span>
          </header>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6 text-sm">
            <Stat label="Output qty"        value={fmt(po.output_qty)} />
            <Stat label="Material cost"     value={fmt(po.own_material_cost)} />
            <Stat label="Unit cost"         value={fmt(po.output_unit_cost)} />
            <Stat label="Invoice"           value={po.invoice_id ? `#${po.invoice_id}` : "—"} />
          </div>

          <section className="mb-6">
            <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-2">References</h2>
            <table className="w-full text-sm border border-[#ede9e2]">
              <tbody className="divide-y divide-[#ede9e2]">
                <Row k="Bill of Material"      v={`#${po.bom_id}`} />
                <Row k="Customer"              v={`#${po.customer_id}`} />
                <Row k="Rate plan"             v={po.rate_plan_id ? `#${po.rate_plan_id}` : "— (no plan assigned)"} />
                {po.invoice_id && <Row k="Invoice"  v={`#${po.invoice_id}`} />}
              </tbody>
            </table>
          </section>

          <section className="mb-6">
            <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-2">Lifecycle</h2>
            <table className="w-full text-sm border border-[#ede9e2]">
              <tbody className="divide-y divide-[#ede9e2]">
                {timeline.map(t => (
                  <Row key={t.state} k={t.label} v={new Date(t.at as string).toLocaleString()} />
                ))}
                {po.cancelled_at && <Row k="Cancelled" v={new Date(po.cancelled_at).toLocaleString()} />}
              </tbody>
            </table>
          </section>

          {po.notes && (
            <section className="mb-6">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-2">{t('col.notes', 'Notes')}</h2>
              <p className="text-sm text-[#1a1814]/80 whitespace-pre-wrap">{po.notes}</p>
            </section>
          )}

          <footer className="mt-12 pt-6 border-t border-[#ede9e2] text-xs text-[#1a1814]/55 leading-relaxed">
            <p>Costs at point of completion. Customer-supplied material tracked off-balance-sheet (memo accounts 1210/2150).</p>
          </footer>
        </article>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[#ede9e2] rounded px-2.5 py-2">
      <div className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-0.5">{label}</div>
      <div className="font-mono text-sm font-semibold">{value}</div>
    </div>
  )
}
function Row({ k, v }: { k: string; v: string }) {
  return (
    <tr>
      <td className="px-3 py-1.5 text-[#1a1814]/65 w-1/3">{k}</td>
      <td className="px-3 py-1.5 font-mono">{v}</td>
    </tr>
  )
}
