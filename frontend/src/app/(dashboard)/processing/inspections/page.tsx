"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Insp = {
  id: number; number: string; date: string; gate_inward_id: number
  accepted_qty: number; rejected_qty: number; hold_qty: number; status: string
}

const today = () => new Date().toISOString().slice(0, 10)

export default function InspectionsPage() {
  const [rows, setRows] = useState<Insp[] | null>(null)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    gate_inward_id: "", accepted_qty: "", rejected_qty: "0", hold_qty: "0",
  })

  function load() {
    apiFetch<Insp[]>("/api/textile-processing/inspections").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }
  useEffect(() => { load() }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    try {
      await apiFetch("/api/textile-processing/inspections", {
        method: "POST",
        body: JSON.stringify({
          gate_inward_id: Number(form.gate_inward_id),
          date: today(),
          accepted_qty: parseFloat(form.accepted_qty) || 0,
          rejected_qty: parseFloat(form.rejected_qty) || 0,
          hold_qty: parseFloat(form.hold_qty) || 0,
        }),
      })
      setForm({ gate_inward_id: "", accepted_qty: "", rejected_qty: "0", hold_qty: "0" })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">RM Inspections</h1>
        <Link href="/processing" className="text-sm text-[var(--primary)] print:hidden">Hub</Link>
      </div>
      <p className="text-sm text-[var(--text-muted)]">Inspection between Gate Inward and GRN for own-store materials.</p>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-4 gap-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
        <input className={input} placeholder="Gate Inward ID" value={form.gate_inward_id}
          onChange={e => setForm({ ...form, gate_inward_id: e.target.value })} required />
        <input className={input} placeholder="Accepted qty" value={form.accepted_qty}
          onChange={e => setForm({ ...form, accepted_qty: e.target.value })} />
        <input className={input} placeholder="Rejected qty" value={form.rejected_qty}
          onChange={e => setForm({ ...form, rejected_qty: e.target.value })} />
        <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Record</button>
      </form>
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Number</th><th className="p-2">Date</th><th className="p-2">GI</th>
            <th className="p-2 text-right">Accepted</th><th className="p-2 text-right">Rejected</th>
            <th className="p-2 text-right">Hold</th><th className="p-2">Status</th>
          </tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{r.number}</td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2">{r.gate_inward_id}</td>
                <td className="p-2 text-right">{r.accepted_qty}</td>
                <td className="p-2 text-right">{r.rejected_qty}</td>
                <td className="p-2 text-right">{r.hold_qty}</td>
                <td className="p-2">{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
