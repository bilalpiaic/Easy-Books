"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Lot = {
  id: number; number: string; date: string; status: string
  received_mtr: number; ready_mtr: number; rejection_mtr: number
  sales_order_id: number; than_count: number
}
type SO = { id: number; number: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function LotsPage() {
  const [rows, setRows] = useState<Lot[] | null>(null)
  const [sos, setSos] = useState<SO[]>([])
  const [show, setShow] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    sales_order_id: "", date: today(),
    thans: "1,100\n2,100\n3,100",
  })

  function load() {
    apiFetch<Lot[]>("/api/textile-processing/lots").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }
  useEffect(() => {
    load()
    apiFetch<SO[]>("/api/textile-processing/sales-orders").then(d => setSos(Array.isArray(d) ? d : [])).catch(() => setSos([]))
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    const thans = form.thans.split("\n").map(l => l.trim()).filter(Boolean).map(l => {
      const [than_no, meters] = l.split(",").map(x => x.trim())
      return { than_no, meters: parseFloat(meters) || 0 }
    })
    if (!thans.length) { setErr("Enter than lines as than_no,meters"); return }
    try {
      await apiFetch("/api/textile-processing/lots", {
        method: "POST",
        body: JSON.stringify({
          sales_order_id: Number(form.sales_order_id),
          date: form.date,
          thans,
        }),
      })
      setShow(false); load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-xl font-semibold">Grey Lots</h1>
        <button type="button" onClick={() => setShow(s => !s)} className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Receive lot</button>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      {show && (
        <form onSubmit={submit} className="space-y-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
          <div className="grid grid-cols-2 gap-2">
            <select className={input} value={form.sales_order_id} onChange={e => setForm({ ...form, sales_order_id: e.target.value })} required>
              <option value="">Sales order…</option>
              {sos.map(s => <option key={s.id} value={s.id}>{s.number}</option>)}
            </select>
            <input type="date" className={input} value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} />
          </div>
          <textarea className={input} rows={5} value={form.thans}
            onChange={e => setForm({ ...form, thans: e.target.value })}
            placeholder="than_no,meters per line" />
          <p className="text-xs text-[var(--text-muted)]">Issues Kachi Parchi automatically on receipt.</p>
          <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Save lot</button>
        </form>
      )}
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Lot</th><th className="p-2">Date</th><th className="p-2 text-right">Received</th>
            <th className="p-2 text-right">Safi / Ready</th><th className="p-2 text-right">Rejection</th>
            <th className="p-2">Thans</th><th className="p-2">Status</th>
          </tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">
                  <Link href={`/processing/lots/${r.id}`} className="text-[var(--primary)]">{r.number}</Link>
                </td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2 text-right">{r.received_mtr}</td>
                <td className="p-2 text-right">{r.ready_mtr}</td>
                <td className="p-2 text-right">{r.rejection_mtr}</td>
                <td className="p-2">{r.than_count}</td>
                <td className="p-2">{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
