"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import PrintHeader from "@/components/PrintHeader"

interface GrnLine {
  id: number
  product_id: number
  qty: string | number
  lot_no: string | null
  declared_value: string | number
  notes: string | null
}
interface Grn {
  id: number
  number: string
  customer_id: number
  received_date: string
  location_id: number
  declared_value: string | number
  notes: string | null
  lines: GrnLine[]
}

const fmt = (v: string | number) => {
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })
}

export default function GrnPrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [grn, setGrn]     = useState<Grn | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Grn>(`/api/grn/${id}`)
      .then(d => { setGrn(d); setTimeout(() => window.print(), 300) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!grn)  return <p className="p-4 text-[#1a1814]/60 text-sm">Loading GRN…</p>

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
          <Printer className="w-4 h-4" /> Print
        </button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-10">
        <PrintHeader title={`Goods Receipt Note ${grn.number}`} subtitle={`Received ${grn.received_date} · Custodial`} />

        <article className="text-[#1a1814]">
          <header className="mb-6 print:hidden border-b border-[#ede9e2] pb-4">
            <h1 className="text-2xl font-serif font-semibold">GRN {grn.number}</h1>
            <p className="text-sm text-[#1a1814]/60">Received {grn.received_date}</p>
          </header>

          <div className="grid grid-cols-2 gap-6 mb-6 text-sm">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Customer (owner)</div>
              <p className="font-semibold">#{grn.customer_id}</p>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Location</div>
              <p className="font-semibold">#{grn.location_id} (godown)</p>
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-2.5 rounded text-xs mb-6">
            <strong>Custodial intake.</strong> These goods belong to the customer and are not your asset.
            They are tracked off-balance-sheet via the memo pair 1210 / 2150.
          </div>

          <table className="w-full text-sm border border-[#ede9e2] mb-6">
            <thead className="bg-[#faf6ec]">
              <tr>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Product</th>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-24">Lot</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-24">Qty</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Declared Value</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {grn.lines.map(ln => (
                <tr key={ln.id}>
                  <td className="px-3 py-2">#{ln.product_id}</td>
                  <td className="px-3 py-2 font-mono text-xs">{ln.lot_no ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.qty)}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(ln.declared_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="flex justify-end mb-6">
            <div className="w-72 flex items-center justify-between text-sm border-t border-[#1a1814] pt-2">
              <span className="font-bold">Total declared value</span>
              <span className="font-mono font-bold">{fmt(grn.declared_value)}</span>
            </div>
          </div>

          {grn.notes && (
            <div className="mb-6">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Notes</h2>
              <p className="text-sm whitespace-pre-wrap">{grn.notes}</p>
            </div>
          )}

          <div className="flex justify-between mt-16 pt-6 border-t border-[#ede9e2] text-xs text-[#1a1814]/55">
            <div className="text-center w-44">
              <div className="border-t border-[#1a1814]/30 pt-1">Customer Representative</div>
            </div>
            <div className="text-center w-44">
              <div className="border-t border-[#1a1814]/30 pt-1">Received By (Godown)</div>
            </div>
          </div>
        </article>
      </div>
    </div>
  )
}
