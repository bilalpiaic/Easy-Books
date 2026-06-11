"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { Printer, RotateCcw, ScrollText } from "lucide-react"
import { useBreadcrumb } from "@/context/BreadcrumbContext"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import AttachmentPanel, { AttachmentPreviewPane, type Attachment as AttachmentT } from "@/components/AttachmentPanel"

interface Entry {
  account_id: number
  account_name: string
  account_type: string
  debit: number
  credit: number
}
interface SourceDoc {
  type: string
  id: number
  number: string
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
  is_reversed: boolean
  reversed_by_id: number | null
  entries: Entry[]
  source_docs: SourceDoc[]
}

const DOC_HREF: Record<string, (id: number) => string> = {
  invoice:           id => `/invoices/${id}`,
  bill:              id => `/bills/${id}`,
  payment_received:  id => `/payments-received/${id}/print`,
  bill_payment:      id => `/bill-payments/${id}/print`,
  grn:               id => `/manufacturing/grn/${id}/print`,
  production_order:  id => `/manufacturing/production-orders/${id}/print`,
}

export default function JvDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const fmt = useFmt()
  const { id } = use(params)
  const [txn, setTxn]     = useState<Txn | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy]   = useState(false)
  const [selectedAtt, setSelectedAtt] = useState<AttachmentT | null>(null)
  useBreadcrumb(txn ? txn.jv_number : undefined)

  const load = () =>
    apiFetch<Txn>(`/api/transactions/${id}`)
      .then(setTxn)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load() }, [id])

  const reverse = async () => {
    if (!txn) return
    if (!window.confirm(`Reverse ${txn.jv_number}? A new equal-and-opposite JV will be posted today.`)) return
    setBusy(true); setError(null)
    try {
      const r = await apiFetch<{ reversal_jv_number: string }>(`/api/transactions/${txn.id}/reverse`, { method: "POST" })
      window.alert(`Reversal posted as ${r.reversal_jv_number}`)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reverse failed")
    } finally {
      setBusy(false)
    }
  }

  if (error && !txn) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!txn)          return <p className="p-4 text-[#1a1814]/60 text-sm">Loading voucher…</p>

  const totalDr = txn.entries.reduce((s, e) => s + (Number(e.debit)  || 0), 0)
  const totalCr = txn.entries.reduce((s, e) => s + (Number(e.credit) || 0), 0)

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div className="flex items-center gap-2">
          <Link href={`/journal/${txn.id}/print`} className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee]">
            <Printer className="w-4 h-4" /> Print
          </Link>
          {!txn.is_reversed && (
            <button onClick={reverse} disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-red-50 hover:text-red-700 disabled:opacity-50">
              <RotateCcw className="w-4 h-4" /> {busy ? "Reversing…" : "Reverse"}
            </button>
          )}
        </div>
      </div>

      <header className="bg-white border border-[#ede9e2] rounded-xl p-5 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <ScrollText className="w-7 h-7 text-[#b8943f] shrink-0 mt-1" />
          <div className="min-w-0">
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Voucher {txn.jv_number}</h1>
            <p className="text-sm text-[#1a1814]/60">Posted {txn.date}</p>
          </div>
        </div>
        {txn.is_reversed && (
          <span className="inline-block border border-gray-300 bg-gray-100 text-gray-600 rounded-full px-3 py-1 text-xs font-semibold uppercase">
            Reversed
          </span>
        )}
      </header>

      {error && <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2 rounded text-sm">{error}</div>}

      {/* Header fields */}
      <section className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <tbody className="divide-y divide-[#ede9e2]">
            <Row k="JV Number" v={txn.jv_number} mono />
            <Row k="Date" v={txn.date} />
            {txn.description && <Row k="Description" v={txn.description} />}
            {txn.reference && <Row k="Reference" v={txn.reference} />}
            {txn.party && <Row k="Party" v={txn.party} />}
            {txn.payment_method && <Row k="Payment Method" v={txn.payment_method} />}
          </tbody>
        </table>
      </section>

      {/* Source docs drill-down */}
      {txn.source_docs.length > 0 && (
        <section className="bg-white border border-[#ede9e2] rounded-xl p-4">
          <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-2">Source documents</h2>
          <div className="flex flex-wrap gap-2">
            {txn.source_docs.map(d => {
              const href = DOC_HREF[d.type]?.(d.id)
              const label = `${d.type.replace("_", " ")}: ${d.number}`
              return href ? (
                <Link key={`${d.type}-${d.id}`} href={href}
                  className="inline-flex items-center px-3 py-1 border border-[#b8943f]/40 bg-[#faf6ec] rounded-full text-xs font-mono text-[#b8943f] hover:bg-[#b8943f]/15">
                  {label}
                </Link>
              ) : (
                <span key={`${d.type}-${d.id}`} className="inline-flex items-center px-3 py-1 border border-[#ede9e2] rounded-full text-xs font-mono text-[#1a1814]/65">
                  {label}
                </span>
              )
            })}
          </div>
        </section>
      )}

      {/* Entries */}
      <section className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#faf6ec]">
            <tr>
              <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Account</th>
              <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-24">Type</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Debit</th>
              <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-32">Credit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {txn.entries.map((e, i) => (
              <tr key={i}>
                <td className="px-4 py-2">
                  <Link href={`/ledger?account=${encodeURIComponent(e.account_name)}`} className="hover:text-[#b8943f] hover:underline">
                    {e.account_name}
                  </Link>
                </td>
                <td className="px-4 py-2 text-[10px] uppercase text-[#1a1814]/55">{e.account_type}</td>
                <td className="px-4 py-2 text-right font-mono">{e.debit > 0 ? fmt(e.debit) : "—"}</td>
                <td className="px-4 py-2 text-right font-mono">{e.credit > 0 ? fmt(e.credit) : "—"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-[#1a1814] bg-[#faf6ec]">
              <td colSpan={2} className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">Totals</td>
              <td className="px-4 py-2 text-right font-mono font-bold">{fmt(totalDr)}</td>
              <td className="px-4 py-2 text-right font-mono font-bold">{fmt(totalCr)}</td>
            </tr>
          </tfoot>
        </table>
      </section>

      {txn.notes && (
        <section className="bg-white border border-[#ede9e2] rounded-xl p-4">
          <h2 className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Notes</h2>
          <p className="text-sm whitespace-pre-wrap">{txn.notes}</p>
        </section>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4 print:hidden">
        <AttachmentPanel parentType="transaction" parentId={txn.id} embedded onSelect={setSelectedAtt} />
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-hidden min-h-[60vh]">
          <AttachmentPreviewPane att={selectedAtt} />
        </div>
      </section>
    </div>
  )
}

function Row({ k, v, mono = false }: { k: string; v: string; mono?: boolean }) {
  return (
    <tr>
      <td className="px-4 py-2 text-[#1a1814]/65 w-1/3 text-[11px] uppercase tracking-wider font-semibold">{k}</td>
      <td className={`px-4 py-2 text-sm ${mono ? "font-mono" : ""}`}>{v}</td>
    </tr>
  )
}
