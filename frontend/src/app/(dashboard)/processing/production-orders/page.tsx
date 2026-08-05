"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type PO = { id: number; number: string; date: string; lot_id: number; issued_mtr: number; status: string }
type Lot = { id: number; number: string; ready_mtr: number; status: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function ProductionOrdersPage() {
  const [rows, setRows] = useState<PO[] | null>(null)
  const [lots, setLots] = useState<Lot[]>([])
  const [err, setErr] = useState("")
  const [lotId, setLotId] = useState("")

  function load() {
    apiFetch<PO[]>("/api/textile-processing/production-orders").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
    apiFetch<Lot[]>("/api/textile-processing/lots").then(d => setLots(Array.isArray(d) ? d : [])).catch(() => setLots([]))
  }
  useEffect(() => { load() }, [])

  async function create(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    try {
      await apiFetch("/api/textile-processing/production-orders", {
        method: "POST",
        body: JSON.stringify({ lot_id: Number(lotId), date: today() }),
      })
      setLotId(""); load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Production Orders</h1>
        <Link href="/processing" className="text-sm text-[var(--primary)] print:hidden">Hub</Link>
      </div>
      <p className="text-sm text-[var(--text-muted)]">Requires Pakki Parchi — only Safi grey under unit responsibility may enter PPC.</p>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <form onSubmit={create} className="flex gap-2 print:hidden">
        <select className="border border-[var(--border)] rounded-lg px-3 py-2 text-sm" value={lotId} onChange={e => setLotId(e.target.value)} required>
          <option value="">Ready lot…</option>
          {lots.filter(l => l.status === "ready").map(l => (
            <option key={l.id} value={l.id}>{l.number} ({l.ready_mtr} MTR)</option>
          ))}
        </select>
        <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Create PO</button>
      </form>
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Number</th><th className="p-2">Date</th><th className="p-2">Lot</th>
            <th className="p-2 text-right">Issued MTR</th><th className="p-2">Status</th>
          </tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{r.number}</td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2">
                  <Link href={`/processing/lots/${r.lot_id}`} className="text-[var(--primary)]">{r.lot_id}</Link>
                </td>
                <td className="p-2 text-right">{r.issued_mtr}</td>
                <td className="p-2">{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
