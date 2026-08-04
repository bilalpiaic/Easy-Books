"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Disp = { id: number; number: string; date: string; lot_id: number; meters: number; invoice_id?: number; status: string }
type PO = { id: number; number: string; status: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function DispatchPage() {
  const [rows, setRows] = useState<Disp[] | null>(null)
  const [pos, setPos] = useState<PO[]>([])
  const [err, setErr] = useState("")
  const [form, setForm] = useState({ production_order_id: "", date: today(), meters: "", vehicle: "", challan: "" })

  function load() {
    apiFetch<Disp[]>("/api/textile-processing/dispatches").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
    apiFetch<PO[]>("/api/textile-processing/production-orders").then(d => setPos(Array.isArray(d) ? d : [])).catch(() => setPos([]))
  }
  useEffect(() => { load() }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    try {
      await apiFetch("/api/textile-processing/dispatches", {
        method: "POST",
        body: JSON.stringify({
          production_order_id: Number(form.production_order_id),
          date: form.date,
          meters: parseFloat(form.meters) || 0,
          vehicle: form.vehicle || null,
          challan: form.challan || null,
          create_invoice: true,
        }),
      })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Fresh Dispatch</h1>
        <Link href="/processing" className="text-sm text-[var(--primary)] print:hidden">Hub</Link>
      </div>
      <p className="text-sm text-[var(--text-muted)]">Creates process-charge invoice from SO rates × billed meters.</p>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
        <select className={input} value={form.production_order_id} onChange={e => setForm({ ...form, production_order_id: e.target.value })} required>
          <option value="">Production order…</option>
          {pos.filter(p => p.status !== "cancelled").map(p => (
            <option key={p.id} value={p.id}>{p.number}</option>
          ))}
        </select>
        <input type="date" className={input} value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} />
        <input className={input} placeholder="Meters" value={form.meters} onChange={e => setForm({ ...form, meters: e.target.value })} required />
        <input className={input} placeholder="Vehicle" value={form.vehicle} onChange={e => setForm({ ...form, vehicle: e.target.value })} />
        <input className={input} placeholder="Challan" value={form.challan} onChange={e => setForm({ ...form, challan: e.target.value })} />
        <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Post dispatch</button>
      </form>
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Number</th><th className="p-2">Date</th><th className="p-2">Lot</th>
            <th className="p-2 text-right">Meters</th><th className="p-2">Invoice</th><th className="p-2">Status</th>
          </tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{r.number}</td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2">{r.lot_id}</td>
                <td className="p-2 text-right">{r.meters}</td>
                <td className="p-2">{r.invoice_id || "—"}</td>
                <td className="p-2">{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
