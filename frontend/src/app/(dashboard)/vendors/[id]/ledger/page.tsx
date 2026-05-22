"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, Printer, Truck } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtPKR } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"
import PrintHeader from "@/components/PrintHeader"

interface LedgerEntry {
  date: string
  doc_type: string
  doc_id: number
  doc_number: string
  description: string
  debit: string
  credit: string
  running_balance: string
  qty_in: string | null
  qty_out: string | null
  unit: string | null
  currency: string
  doc_amount: string
}
interface Ledger {
  vendor: { id: number; name: string; email: string | null; phone: string | null; opening_balance: string }
  period: { start: string | null; end: string | null }
  opening_balance: string
  entries: LedgerEntry[]
  closing_balance: string
  totals: { debit: string; credit: string; qty_in: string | null }
}

const DOC_HREF: Record<string, (id: number) => string> = {
  bill:         id => `/bills/${id}`,
  bill_payment: id => `/bill-payments/${id}/print`,
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split("T")[0], end: to.toISOString().split("T")[0] }
}

export default function VendorLedgerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const r0 = defaultRange()
  const [start, setStart] = useState(r0.start)
  const [end, setEnd]     = useState(r0.end)
  const [data, setData]   = useState<Ledger | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Ledger>(`/api/vendors/${id}/ledger?start=${start}&end=${end}`)
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id, start, end])

  if (error && !data) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!data)          return <p className="p-4 text-[#1a1814]/60 text-sm">Loading ledger…</p>

  const v = data.vendor

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <PrintHeader title={`Vendor Ledger — ${v.name}`} subtitle={`Period ${start} → ${end}`} orientation="landscape" />

      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <Link href="/vendors" className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-[#1a1814]/65 hover:text-[#b8943f]">
          <ArrowLeft className="w-4 h-4" /> Vendors
        </Link>
        <button onClick={() => window.print()} className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee]">
          <Printer className="w-4 h-4" /> Print
        </button>
      </div>

      <header className="bg-white border border-[#ede9e2] rounded-xl p-5 flex items-start gap-3 print:hidden">
        <Truck className="w-7 h-7 text-[#b8943f] shrink-0 mt-1" />
        <div className="min-w-0">
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814] truncate">{v.name}</h1>
          <p className="text-xs text-[#1a1814]/60">
            {v.email && <span>{v.email}</span>}
            {v.email && v.phone && <span> · </span>}
            {v.phone && <span>{v.phone}</span>}
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 print:hidden">
        <div className="bg-white border border-[#ede9e2] rounded-xl p-4">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
        </div>
        <div className="bg-white border border-[#ede9e2] rounded-xl p-4 grid grid-cols-3 gap-3 text-center">
          <Stat label="Opening" value={fmtPKR(Number(data.opening_balance))} />
          <Stat label="Closing"
                value={fmtPKR(Number(data.closing_balance))}
                tone={Number(data.closing_balance) > 0 ? "amber" : "emerald"}
                hint={Number(data.closing_balance) > 0 ? "We owe" : ""}
          />
          {data.totals.qty_in && (
            <Stat label="Qty purchased" value={data.totals.qty_in} />
          )}
        </div>
      </div>

      <section className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[760px]">
          <thead className="bg-[#faf6ec]">
            <tr>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Date</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Document</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Description</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-24">Qty</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Debit</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Credit</th>
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Balance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            <tr className="bg-[#faf8f4]">
              <td colSpan={6} className="px-3 py-2 text-[11px] font-bold text-[#1a1814]/55">Opening Balance</td>
              <td className="px-3 py-2 text-right font-mono font-bold">{fmtPKR(Number(data.opening_balance))}</td>
            </tr>
            {data.entries.map((e, i) => {
              const href = DOC_HREF[e.doc_type]?.(e.doc_id)
              return (
                <tr key={i}>
                  <td className="px-3 py-2 text-[#1a1814]/70">{e.date}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {href ? <Link href={href} className="text-[#b8943f] hover:underline">{e.doc_number}</Link> : e.doc_number}
                  </td>
                  <td className="px-3 py-2 text-[#1a1814]/80">{e.description}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs">
                    {e.qty_in ? <>+{e.qty_in} {e.unit ?? ""}</> : ""}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{Number(e.debit)  > 0 ? fmtPKR(Number(e.debit))  : ""}</td>
                  <td className="px-3 py-2 text-right font-mono">{Number(e.credit) > 0 ? fmtPKR(Number(e.credit)) : ""}</td>
                  <td className="px-3 py-2 text-right font-mono font-semibold">{fmtPKR(Number(e.running_balance))}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-[#1a1814] bg-[#faf6ec]">
              <td colSpan={3} className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Totals</td>
              <td className="px-3 py-2 text-right font-mono text-xs">{data.totals.qty_in ?? ""}</td>
              <td className="px-3 py-2 text-right font-mono font-bold">{fmtPKR(Number(data.totals.debit))}</td>
              <td className="px-3 py-2 text-right font-mono font-bold">{fmtPKR(Number(data.totals.credit))}</td>
              <td className="px-3 py-2 text-right font-mono font-bold">{fmtPKR(Number(data.closing_balance))}</td>
            </tr>
          </tfoot>
        </table>
        </div>
      </section>
    </div>
  )
}

function Stat({ label, value, hint, tone = "default" }: {
  label: string; value: string; hint?: string; tone?: "default" | "amber" | "emerald"
}) {
  const toneCls = tone === "amber"   ? "text-amber-700"
                : tone === "emerald" ? "text-emerald-700"
                : "text-[#1a1814]"
  return (
    <div>
      <div className="text-[9px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-0.5">{label}</div>
      <div className={`font-mono text-base font-bold ${toneCls}`}>{value}</div>
      {hint && <div className="text-[10px] text-[#1a1814]/45 mt-0.5">{hint}</div>}
    </div>
  )
}
