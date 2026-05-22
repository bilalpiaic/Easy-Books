"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import PrintHeader from "@/components/PrintHeader"

interface Entry {
  account_id: number
  account_name: string
  account_type: string
  debit: string | number
  credit: string | number
}
interface Txn {
  id: number
  jv_number: string
  date: string
  description: string | null
  reference: string | null
  party: string | null
  payment_method: string | null
  notes: string | null
  entries: Entry[]
}

const fmt = (v: string | number) => {
  const n = Number(v)
  if (Number.isNaN(n) || n === 0) return ""
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function JvPrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [txn, setTxn]     = useState<Txn | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Txn>(`/api/transactions/${id}`)
      .then(d => { setTxn(d); setTimeout(() => window.print(), 300) })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!txn)  return <p className="p-4 text-[#1a1814]/60 text-sm">Loading voucher…</p>

  const totalDr = txn.entries.reduce((s, e) => s + (Number(e.debit)  || 0), 0)
  const totalCr = txn.entries.reduce((s, e) => s + (Number(e.credit) || 0), 0)

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
        <PrintHeader title={`Journal Voucher ${txn.jv_number}`} subtitle={`Date ${txn.date}`} />

        <article className="text-[#1a1814]">
          <header className="mb-6 print:hidden border-b border-[#ede9e2] pb-4">
            <h1 className="text-2xl font-serif font-semibold">Voucher {txn.jv_number}</h1>
            <p className="text-sm text-[#1a1814]/60">Posted {txn.date}</p>
          </header>

          {/* Header fields */}
          <table className="w-full text-sm border border-[#ede9e2] mb-6">
            <tbody className="divide-y divide-[#ede9e2]">
              <Row k="JV Number" v={txn.jv_number} />
              <Row k="Date"      v={txn.date} />
              {txn.description && <Row k="Description" v={txn.description} />}
              {txn.reference && <Row k="Reference" v={txn.reference} />}
              {txn.party && <Row k="Party" v={txn.party} />}
              {txn.payment_method && <Row k="Payment Method" v={txn.payment_method} />}
            </tbody>
          </table>

          {/* Entries */}
          <table className="w-full text-sm border border-[#ede9e2] mb-6">
            <thead className="bg-[#faf6ec]">
              <tr>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Account</th>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-20">Type</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Debit</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-28">Credit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {txn.entries.map((e, i) => (
                <tr key={i}>
                  <td className="px-3 py-2">{e.account_name}</td>
                  <td className="px-3 py-2 text-[10px] text-[#1a1814]/55 uppercase">{e.account_type}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(e.debit)}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(e.credit)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-[#1a1814] bg-[#faf6ec]">
                <td colSpan={2} className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Totals</td>
                <td className="px-3 py-2 text-right font-mono font-bold">
                  {totalDr.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </td>
                <td className="px-3 py-2 text-right font-mono font-bold">
                  {totalCr.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </td>
              </tr>
            </tfoot>
          </table>

          {txn.notes && (
            <div className="mb-6">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Notes</h2>
              <p className="text-sm whitespace-pre-wrap">{txn.notes}</p>
            </div>
          )}

          <div className="flex justify-between mt-16 pt-6 border-t border-[#ede9e2] text-xs text-[#1a1814]/55">
            <div className="text-center w-44">
              <div className="border-t border-[#1a1814]/30 pt-1">Prepared By</div>
            </div>
            <div className="text-center w-44">
              <div className="border-t border-[#1a1814]/30 pt-1">Approved By</div>
            </div>
          </div>
        </article>
      </div>
    </div>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <tr>
      <td className="px-3 py-1.5 text-[#1a1814]/65 w-1/3 text-[11px] uppercase tracking-wider font-semibold">{k}</td>
      <td className="px-3 py-1.5 text-sm">{v}</td>
    </tr>
  )
}
