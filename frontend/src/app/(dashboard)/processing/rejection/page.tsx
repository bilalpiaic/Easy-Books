"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Note = {
  id: number; number: string; date: string; issued_mtr: number
  lifted_mtr: number; balance_mtr: number; status: string; lot_id: number
}
type Ogp = { id: number; number: string; date: string; qty_mtr: number; vehicle?: string; challan?: string; rejection_issue_note_id: number }

const today = () => new Date().toISOString().slice(0, 10)

export default function RejectionPage() {
  const [notes, setNotes] = useState<Note[]>([])
  const [ogps, setOgps] = useState<Ogp[]>([])
  const [err, setErr] = useState("")
  const [form, setForm] = useState({ rejection_issue_note_id: "", date: today(), qty_mtr: "", vehicle: "", challan: "" })

  function load() {
    apiFetch<Note[]>("/api/textile-processing/rejection-notes").then(d => setNotes(Array.isArray(d) ? d : [])).catch(() => setNotes([]))
    apiFetch<Ogp[]>("/api/textile-processing/rejection-ogps").then(d => setOgps(Array.isArray(d) ? d : [])).catch(() => setOgps([]))
  }
  useEffect(() => { load() }, [])

  async function createOgp(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    try {
      await apiFetch("/api/textile-processing/rejection-ogps", {
        method: "POST",
        body: JSON.stringify({
          rejection_issue_note_id: Number(form.rejection_issue_note_id),
          date: form.date,
          qty_mtr: parseFloat(form.qty_mtr) || 0,
          vehicle: form.vehicle || null,
          challan: form.challan || null,
        }),
      })
      setForm({ rejection_issue_note_id: "", date: today(), qty_mtr: "", vehicle: "", challan: "" })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"

  return (
    <div className="p-4 space-y-6 max-w-6xl mx-auto">
      <h1 className="text-xl font-semibold">Rejection Issuance & OGP</h1>
      {err && <p className="text-sm text-red-600">{err}</p>}

      <form onSubmit={createOgp} className="grid grid-cols-2 md:grid-cols-5 gap-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
        <select className={input} value={form.rejection_issue_note_id} onChange={e => setForm({ ...form, rejection_issue_note_id: e.target.value })} required>
          <option value="">Rejection note…</option>
          {notes.filter(n => n.balance_mtr > 0).map(n => (
            <option key={n.id} value={n.id}>{n.number} (bal {n.balance_mtr})</option>
          ))}
        </select>
        <input type="date" className={input} value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} />
        <input className={input} placeholder="Qty MTR" value={form.qty_mtr} onChange={e => setForm({ ...form, qty_mtr: e.target.value })} required />
        <input className={input} placeholder="Vehicle" value={form.vehicle} onChange={e => setForm({ ...form, vehicle: e.target.value })} />
        <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Post OGP</button>
      </form>

      <div>
        <h2 className="font-semibold mb-2">Rejection notes</h2>
        <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
          <table className="w-full text-sm">
            <thead><tr className="text-left border-b border-[var(--border)]">
              <th className="p-2">Note</th><th className="p-2">Date</th>
              <th className="p-2 text-right">Issued</th><th className="p-2 text-right">Lifted</th>
              <th className="p-2 text-right">Balance</th><th className="p-2">Status</th>
            </tr></thead>
            <tbody>
              {notes.map(n => (
                <tr key={n.id} className="border-b border-[var(--border)]/60">
                  <td className="p-2 whitespace-nowrap">{n.number}</td>
                  <td className="p-2 whitespace-nowrap">{fmtDate(n.date)}</td>
                  <td className="p-2 text-right">{n.issued_mtr}</td>
                  <td className="p-2 text-right">{n.lifted_mtr}</td>
                  <td className="p-2 text-right">{n.balance_mtr}</td>
                  <td className="p-2">{n.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h2 className="font-semibold mb-2">OGPs</h2>
        <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
          <table className="w-full text-sm">
            <thead><tr className="text-left border-b border-[var(--border)]">
              <th className="p-2">OGP</th><th className="p-2">Date</th><th className="p-2 text-right">Qty</th>
              <th className="p-2">Vehicle</th><th className="p-2">Challan</th>
            </tr></thead>
            <tbody>
              {ogps.map(o => (
                <tr key={o.id} className="border-b border-[var(--border)]/60">
                  <td className="p-2 whitespace-nowrap">{o.number}</td>
                  <td className="p-2 whitespace-nowrap">{fmtDate(o.date)}</td>
                  <td className="p-2 text-right">{o.qty_mtr}</td>
                  <td className="p-2">{o.vehicle || "—"}</td>
                  <td className="p-2">{o.challan || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
