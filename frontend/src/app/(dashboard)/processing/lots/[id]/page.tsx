"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

export default function LotDetailPage() {
  const params = useParams()
  const id = Number(params.id)
  const [lot, setLot] = useState<any>(null)
  const [timeline, setTimeline] = useState<any>(null)

  useEffect(() => {
    if (!id) return
    apiFetch(`/api/textile-processing/lots/${id}`).then(setLot).catch(() => setLot(null))
    apiFetch(`/api/textile-processing/lots/${id}/timeline`).then(setTimeline).catch(() => setTimeline(null))
  }, [id])

  if (!lot) return <div className="p-4 text-sm text-[var(--text-muted)]">Loading…</div>

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{lot.number}</h1>
          <p className="text-sm text-[var(--text-muted)]">{fmtDate(lot.date)} · {lot.status}</p>
        </div>
        <Link href="/processing/lots" className="text-sm text-[var(--primary)] print:hidden">Lots</Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div className="rounded-xl border border-[var(--border)] p-3"><div className="text-[var(--text-muted)]">Received</div><div className="text-lg">{lot.received_mtr} MTR</div></div>
        <div className="rounded-xl border border-[var(--border)] p-3"><div className="text-[var(--text-muted)]">Safi / Ready</div><div className="text-lg">{lot.ready_mtr} MTR</div></div>
        <div className="rounded-xl border border-[var(--border)] p-3"><div className="text-[var(--text-muted)]">Visible waste</div><div className="text-lg">{lot.visible_wastage_mtr} MTR</div></div>
        <div className="rounded-xl border border-[var(--border)] p-3"><div className="text-[var(--text-muted)]">Invisible waste</div><div className="text-lg">{lot.invisible_wastage_mtr} MTR</div></div>
      </div>

      {lot.thans?.length > 0 && (
        <div>
          <h2 className="font-semibold mb-2">Thans</h2>
          <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
            <table className="w-full text-sm">
              <thead><tr className="text-left border-b border-[var(--border)]">
                <th className="p-2">Than</th><th className="p-2 text-right">Meters</th><th className="p-2">Width</th>
              </tr></thead>
              <tbody>
                {lot.thans.map((t: any) => (
                  <tr key={t.id} className="border-b border-[var(--border)]/60">
                    <td className="p-2">{t.than_no}</td>
                    <td className="p-2 text-right">{t.meters}</td>
                    <td className="p-2">{t.width || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div>
        <h2 className="font-semibold mb-2">Lot timeline</h2>
        <div className="space-y-2">
          {(timeline?.events || []).map((ev: any, i: number) => (
            <div key={i} className="rounded-xl border border-[var(--border)] p-3 text-sm">
              <div className="flex justify-between gap-2">
                <span className="font-medium capitalize">{String(ev.type).replaceAll("_", " ")}</span>
                <span className="text-[var(--text-muted)] whitespace-nowrap">{fmtDate(ev.date)}</span>
              </div>
              <pre className="mt-1 text-xs text-[var(--text-muted)] overflow-auto">{JSON.stringify(ev.data, null, 0)}</pre>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
