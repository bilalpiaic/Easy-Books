"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Mending = {
  id: number; number: string; lot_id: number; date: string
  grey_mtr: number; l_kami_mtr: number; rejection_mtr: number
  safai_mtr: number; ready_mtr: number; status: string
}
type Lot = { id: number; number: string; received_mtr: number; status: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function MendingPage() {
  const [rows, setRows] = useState<Mending[] | null>(null)
  const [lots, setLots] = useState<Lot[]>([])
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    lot_id: "", date: today(), l_kami_mtr: "10", rejection_mtr: "15", safai_mtr: "75",
  })

  function load() {
    apiFetch<Mending[]>("/api/textile-processing/mendings").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
    apiFetch<Lot[]>("/api/textile-processing/lots").then(d => setLots(Array.isArray(d) ? d : [])).catch(() => setLots([]))
  }
  useEffect(() => { load() }, [])

  const lot = lots.find(l => l.id === Number(form.lot_id))
  const grey = lot?.received_mtr ?? 0
  const ready = Math.max(0, grey - (parseFloat(form.l_kami_mtr) || 0) - (parseFloat(form.rejection_mtr) || 0) - (parseFloat(form.safai_mtr) || 0))

  async function create(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    try {
      await apiFetch("/api/textile-processing/mendings", {
        method: "POST",
        body: JSON.stringify({
          lot_id: Number(form.lot_id), date: form.date,
          l_kami_mtr: parseFloat(form.l_kami_mtr) || 0,
          rejection_mtr: parseFloat(form.rejection_mtr) || 0,
          safai_mtr: parseFloat(form.safai_mtr) || 0,
        }),
      })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  async function post(id: number) {
    setErr("")
    try {
      await apiFetch(`/api/textile-processing/mendings/${id}/post`, { method: "PATCH" })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <h1 className="text-xl font-semibold">Mending</h1>
      <p className="text-sm text-[var(--text-muted)]">
        Ready (Safi) = Grey − L-Kami − Rejection − Safai (mending loss). Posting issues Pakki Parchi and Rejection Note.
      </p>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <form onSubmit={create} className="grid grid-cols-2 md:grid-cols-3 gap-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
        <select className={input} value={form.lot_id} onChange={e => setForm({ ...form, lot_id: e.target.value })} required>
          <option value="">Lot…</option>
          {lots.filter(l => l.status === "received" || l.status === "mending").map(l => (
            <option key={l.id} value={l.id}>{l.number} ({l.received_mtr} MTR)</option>
          ))}
        </select>
        <input type="date" className={input} value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} />
        <input className={input} placeholder="L-Kami MTR" value={form.l_kami_mtr} onChange={e => setForm({ ...form, l_kami_mtr: e.target.value })} />
        <input className={input} placeholder="Rejection MTR" value={form.rejection_mtr} onChange={e => setForm({ ...form, rejection_mtr: e.target.value })} />
        <input className={input} placeholder="Safai (loss) MTR" value={form.safai_mtr} onChange={e => setForm({ ...form, safai_mtr: e.target.value })} />
        <div className="text-sm flex items-center">Safi / Ready: <strong className="ml-1">{ready.toFixed(2)} MTR</strong></div>
        <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Create draft</button>
      </form>
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Number</th><th className="p-2">Date</th><th className="p-2 text-right">Grey</th>
            <th className="p-2 text-right">L-Kami</th><th className="p-2 text-right">Rejection</th>
            <th className="p-2 text-right">Safai loss</th><th className="p-2 text-right">Ready</th>
            <th className="p-2">Status</th><th className="p-2 print:hidden"></th>
          </tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{r.number}</td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2 text-right">{r.grey_mtr}</td>
                <td className="p-2 text-right">{r.l_kami_mtr}</td>
                <td className="p-2 text-right">{r.rejection_mtr}</td>
                <td className="p-2 text-right">{r.safai_mtr}</td>
                <td className="p-2 text-right">{r.ready_mtr}</td>
                <td className="p-2">{r.status}</td>
                <td className="p-2 print:hidden">
                  {r.status === "draft" && (
                    <button type="button" onClick={() => post(r.id)} className="text-[var(--primary)] text-sm">Post</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
