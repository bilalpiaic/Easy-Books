"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { ChevronRight, Undo2, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import DocLink from "@/components/DocLink"
import { useTranslation } from "react-i18next"

interface Line { id: number; description: string; qty: number; rate: number; amount: number; unit: string | null }
interface DebitNoteDetail {
  id: number
  number: string
  bill_id: number
  vendor_id: number | null
  vendor_name: string | null
  issue_date: string
  description: string | null
  subtotal: number
  gst_amount: number
  total: number
  status: string
  transaction_id: number | null
  lines: Line[]
}

export default function DebitNoteDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const { id } = use(params)
  const fmt = useFmt()
  const [dn, setDn] = useState<DebitNoteDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<DebitNoteDetail>(`/api/debit-notes/${id}`)
      .then(d => { setDn(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [id])

  if (loading) return <div className="text-center py-20 text-[var(--text-primary)]/50">Loading…</div>
  if (!dn) return <div className="text-center py-20 text-[var(--text-primary)]/50">Debit note not found.</div>

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <nav className="flex items-center gap-1.5 text-xs text-[var(--text-primary)]/50 print:hidden">
        <Link href="/dashboard" className="hover:text-[var(--primary)]">Dashboard</Link>
        <ChevronRight className="w-3 h-3" />
        <Link href="/debit-notes" className="hover:text-[var(--primary)]">Debit Notes</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-[var(--text-primary)]/80 font-medium">{dn.number}</span>
      </nav>

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--text-primary)] flex items-center justify-center flex-shrink-0">
            <Undo2 className="w-5 h-5 text-[var(--primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">{dn.number}</h1>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mt-0.5">Purchase Return · {dn.status}</p>
          </div>
        </div>
        <Link href={`/debit-notes/${id}/print`} className="p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] text-[var(--text-primary)]/60 print:hidden" title="Print">
          <Printer className="w-5 h-5" />
        </Link>
      </div>

      <div className="bg-white border border-[var(--border)] rounded-xl p-5 grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[var(--text-primary)]/50">{t('col.vendor', 'Vendor')}</p>
          <p className="mt-0.5">{dn.vendor_id
            ? <DocLink type="vendor" id={dn.vendor_id} label={dn.vendor_name ?? "Vendor"} />
            : (dn.vendor_name ?? "—")}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[var(--text-primary)]/50">Original Bill</p>
          <p className="mt-0.5"><DocLink type="bill" id={dn.bill_id} label={`Bill #${dn.bill_id}`} /></p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[var(--text-primary)]/50">Issue Date</p>
          <p className="mt-0.5 text-[var(--text-primary)]/70">{dn.issue_date}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[var(--text-primary)]/50">Journal Entry</p>
          <p className="mt-0.5">{dn.transaction_id
            ? <DocLink type="jv" id={dn.transaction_id} label={`JV-${String(dn.transaction_id).padStart(5, "0")}`} />
            : "—"}</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-[var(--text-primary)]/5 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)]">
            <tr>{["Description", "Qty", "Rate", "Amount"].map(h => (
              <th key={h} className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {dn.lines.map(l => (
              <tr key={l.id} className="border-t border-[var(--text-primary)]/5">
                <td className="px-4 py-2">{l.description}</td>
                <td className="px-4 py-2 font-mono">{l.qty}</td>
                <td className="px-4 py-2 font-mono">{fmt(l.rate)}</td>
                <td className="px-4 py-2 font-mono">{fmt(l.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-3 border-t border-[var(--border)] text-sm space-y-1">
          <div className="flex justify-between"><span className="text-[var(--text-primary)]/60">Subtotal</span><span className="font-mono">{fmt(dn.subtotal)}</span></div>
          {dn.gst_amount > 0 && <div className="flex justify-between"><span className="text-[var(--text-primary)]/60">GST reversed</span><span className="font-mono">{fmt(dn.gst_amount)}</span></div>}
          <div className="flex justify-between font-bold border-t border-[var(--border)] pt-1"><span>Total Return</span><span className="font-mono">{fmt(dn.total)}</span></div>
        </div>
      </div>
      <p className="text-xs text-[var(--text-primary)]/40 italic">GL: Dr Accounts Payable / Cr Inventory (at original cost) + Cr GST Input.</p>
    </div>
  )
}
