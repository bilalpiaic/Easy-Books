"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

type Than = { than_no: string; meters: number; rejection_mtr: number; safi_mtr: number }
type Kachi = {
  id: number; number: string; date: string; meters: number; than_count: number
  lot_id: number; lot_number?: string; customer_name?: string
  quality_code?: string; quality_name?: string; thans?: Than[]; notes?: string
}

export default function KachiParchiPrintPage() {
  const params = useParams()
  const id = Number(params?.id)
  const [row, setRow] = useState<Kachi | null>(null)
  const [err, setErr] = useState("")

  useEffect(() => {
    if (!id) return
    apiFetch<Kachi>(`/api/textile-processing/kachi-parchis/${id}`)
      .then(setRow)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Failed"))
  }, [id])

  if (err) return <div className="p-4 text-red-600">{err}</div>
  if (!row) return <div className="p-4">Loading…</div>

  const thans = row.thans || []

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-4">
      <div className="flex justify-between print:hidden">
        <Link href="/processing/kachi-parchi" className="text-sm text-[var(--primary)]">← Kachi list</Link>
        <button type="button" onClick={() => window.print()} className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-1.5">Print</button>
      </div>
      <PrintHeader title="Kachi Parchi" subtitle={`${row.number} · ${fmtDate(row.date)}`} />
      <div className="grid grid-cols-2 gap-3 text-sm border border-[var(--border)] rounded-xl p-4">
        <div><span className="text-[var(--text-muted)]">Customer</span><p className="font-semibold">{row.customer_name || "—"}</p></div>
        <div><span className="text-[var(--text-muted)]">Lot</span><p className="font-semibold">{row.lot_number || row.lot_id}</p></div>
        <div><span className="text-[var(--text-muted)]">Grey Quality</span><p className="font-semibold font-mono">{row.quality_code || "—"}</p>
          {row.quality_name && <p className="text-xs text-[var(--text-muted)]">{row.quality_name}</p>}
        </div>
        <div><span className="text-[var(--text-muted)]">Total Meters</span><p className="font-semibold tabular-nums">{row.meters}</p></div>
      </div>
      <table className="w-full text-sm border border-[var(--border)] rounded-xl overflow-hidden">
        <thead>
          <tr className="border-b border-[var(--border)] text-left">
            <th className="p-2">Than#</th>
            <th className="p-2 text-right">Mtrs</th>
            <th className="p-2 text-right">Rej</th>
            <th className="p-2 text-right">Safi</th>
          </tr>
        </thead>
        <tbody>
          {thans.map(t => (
            <tr key={t.than_no} className="border-b border-[var(--border)]/50">
              <td className="p-2 whitespace-nowrap">{t.than_no}</td>
              <td className="p-2 text-right tabular-nums">{t.meters}</td>
              <td className="p-2 text-right tabular-nums">{t.rejection_mtr}</td>
              <td className="p-2 text-right tabular-nums">{t.safi_mtr || (t.meters - (t.rejection_mtr || 0))}</td>
            </tr>
          ))}
          {!thans.length && (
            <tr><td className="p-3 text-[var(--text-muted)]" colSpan={4}>{row.than_count} thans · {row.meters} mtr</td></tr>
          )}
        </tbody>
      </table>
      {row.notes && <p className="text-sm">Notes: {row.notes}</p>}
      <div className="grid grid-cols-2 gap-8 pt-10 text-sm">
        <div className="border-t border-[var(--border)] pt-2">Received by</div>
        <div className="border-t border-[var(--border)] pt-2">Customer / Gate</div>
      </div>
    </div>
  )
}
