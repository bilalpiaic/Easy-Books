"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"

type Pakki = {
  id: number; number: string; date: string; meters: number; than_count: number
  lot_id: number; lot_number?: string; customer_name?: string
  quality_code?: string; quality_name?: string
  mending?: {
    grey_mtr: number; l_kami_mtr: number; rejection_mtr: number
    safai_mtr: number; ready_mtr: number
  }
  notes?: string
}

export default function PakkiParchiPrintPage() {
  const params = useParams()
  const id = Number(params?.id)
  const [row, setRow] = useState<Pakki | null>(null)
  const [err, setErr] = useState("")

  useEffect(() => {
    if (!id) return
    apiFetch<Pakki>(`/api/textile-processing/pakki-parchis/${id}`)
      .then(setRow)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Failed"))
  }, [id])

  if (err) return <div className="p-4 text-red-600">{err}</div>
  if (!row) return <div className="p-4">Loading…</div>
  const m = row.mending

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-4">
      <div className="flex justify-between print:hidden">
        <Link href="/processing/pakki-parchi" className="text-sm text-[var(--primary)]">← Pakki list</Link>
        <button type="button" onClick={() => window.print()} className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-1.5">Print</button>
      </div>
      <PrintHeader title="Pakki Parchi (Safi Grey)" subtitle={`${row.number} · ${fmtDate(row.date)}`} />
      <div className="grid grid-cols-2 gap-3 text-sm border border-[var(--border)] rounded-xl p-4">
        <div><span className="text-[var(--text-muted)]">Customer</span><p className="font-semibold">{row.customer_name || "—"}</p></div>
        <div><span className="text-[var(--text-muted)]">Lot</span><p className="font-semibold">{row.lot_number || row.lot_id}</p></div>
        <div><span className="text-[var(--text-muted)]">Grey Quality</span><p className="font-semibold font-mono">{row.quality_code || "—"}</p></div>
        <div><span className="text-[var(--text-muted)]">Safi Meters</span><p className="font-semibold tabular-nums text-lg">{row.meters}</p></div>
      </div>
      {m && (
        <table className="w-full text-sm border border-[var(--border)] rounded-xl overflow-hidden">
          <thead>
            <tr className="border-b border-[var(--border)] text-left">
              <th className="p-2">Grey</th>
              <th className="p-2 text-right">L-Kami</th>
              <th className="p-2 text-right">Rej</th>
              <th className="p-2 text-right">Safai</th>
              <th className="p-2 text-right">Safi</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="p-2 tabular-nums">{m.grey_mtr}</td>
              <td className="p-2 text-right tabular-nums">{m.l_kami_mtr}</td>
              <td className="p-2 text-right tabular-nums">{m.rejection_mtr}</td>
              <td className="p-2 text-right tabular-nums">{m.safai_mtr}</td>
              <td className="p-2 text-right tabular-nums font-semibold">{m.ready_mtr}</td>
            </tr>
          </tbody>
        </table>
      )}
      <p className="text-xs text-[var(--text-muted)]">Thans: {row.than_count}. Safi grey is under unit responsibility for PPC.</p>
      <div className="grid grid-cols-2 gap-8 pt-10 text-sm">
        <div className="border-t border-[var(--border)] pt-2">Checked by</div>
        <div className="border-t border-[var(--border)] pt-2">Authorized</div>
      </div>
    </div>
  )
}
