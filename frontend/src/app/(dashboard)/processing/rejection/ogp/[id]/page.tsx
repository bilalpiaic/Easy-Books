"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

type Ogp = {
  id: number; number: string; date: string; qty_mtr: number
  vehicle?: string; challan?: string; notes?: string
  customer_name?: string; quality_code?: string; lot_number?: string
  rejection_note?: { number: string; issued_mtr: number; lifted_mtr: number }
}

export default function GreyRejOutwardPrintPage() {
  const params = useParams()
  const id = Number(params?.id)
  const [row, setRow] = useState<Ogp | null>(null)
  const [err, setErr] = useState("")

  useEffect(() => {
    if (!id) return
    apiFetch<Ogp>(`/api/textile-processing/rejection-ogps/${id}`)
      .then(setRow)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Failed"))
  }, [id])

  if (err) return <div className="p-4 text-red-600">{err}</div>
  if (!row) return <div className="p-4">Loading…</div>

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-4">
      <div className="flex justify-between print:hidden">
        <Link href="/processing/rejection" className="text-sm text-[var(--primary)]">← Rejection / OGP</Link>
        <button type="button" onClick={() => window.print()} className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-1.5">Print</button>
      </div>
      <PrintHeader title="Grey Rej Outward" subtitle={`${row.number} · ${fmtDate(row.date)}`} />
      <div className="grid grid-cols-2 gap-3 text-sm border border-[var(--border)] rounded-xl p-4">
        <div><span className="text-[var(--text-muted)]">Customer</span><p className="font-semibold">{row.customer_name || "—"}</p></div>
        <div><span className="text-[var(--text-muted)]">Lot</span><p className="font-semibold">{row.lot_number || "—"}</p></div>
        <div><span className="text-[var(--text-muted)]">Grey Quality</span><p className="font-semibold font-mono">{row.quality_code || "—"}</p></div>
        <div><span className="text-[var(--text-muted)]">Rejection Note</span><p className="font-semibold">{row.rejection_note?.number || "—"}</p></div>
        <div><span className="text-[var(--text-muted)]">Qty Outward (MTR)</span><p className="font-semibold tabular-nums text-lg">{row.qty_mtr}</p></div>
        <div><span className="text-[var(--text-muted)]">Vehicle / Challan</span>
          <p className="font-semibold">{[row.vehicle, row.challan].filter(Boolean).join(" · ") || "—"}</p>
        </div>
      </div>
      {row.notes && <p className="text-sm">Notes: {row.notes}</p>}
      <div className="grid grid-cols-3 gap-6 pt-12 text-sm">
        <div className="border-t border-[var(--border)] pt-2">Prepared</div>
        <div className="border-t border-[var(--border)] pt-2">Gate Out</div>
        <div className="border-t border-[var(--border)] pt-2">Customer Received</div>
      </div>
    </div>
  )
}
