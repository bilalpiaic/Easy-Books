"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Bill = { id: number; number: string; date: string; contractor_id: number; labor_amount: number; bill_id?: number; status: string; stage_entry_ids: number[] }
type Contractor = { id: number; name: string }
type Stage = { id: number; number: string; labor_amount: number; contractor_id?: number }

const today = () => new Date().toISOString().slice(0, 10)

export default function LaborBillsPage() {
  const [rows, setRows] = useState<Bill[] | null>(null)
  const [contractors, setContractors] = useState<Contractor[]>([])
  const [stages, setStages] = useState<Stage[]>([])
  const [err, setErr] = useState("")
  const [form, setForm] = useState({ contractor_id: "", stage_ids: "" as string })

  function load() {
    apiFetch<Bill[]>("/api/textile-processing/labor-bills").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
    apiFetch<Contractor[]>("/api/textile-processing/contractors").then(d => setContractors(Array.isArray(d) ? d : [])).catch(() => setContractors([]))
    apiFetch<Stage[]>("/api/textile-processing/stages").then(d => setStages(Array.isArray(d) ? d : [])).catch(() => setStages([]))
  }
  useEffect(() => { load() }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    const ids = form.stage_ids.split(",").map(s => parseInt(s.trim(), 10)).filter(n => !Number.isNaN(n))
    try {
      await apiFetch("/api/textile-processing/labor-bills", {
        method: "POST",
        body: JSON.stringify({
          contractor_id: Number(form.contractor_id),
          date: today(),
          stage_entry_ids: ids,
        }),
      })
      setForm({ contractor_id: "", stage_ids: "" }); load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"
  const openStages = stages.filter(s => s.labor_amount > 0)

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Contractor Labor Bills</h1>
        <Link href="/processing" className="text-sm text-[var(--primary)] print:hidden">Hub</Link>
      </div>
      <p className="text-sm text-[var(--text-muted)]">Groups stage labor into a Vendor Bill (AP).</p>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
        <select className={input} value={form.contractor_id} onChange={e => setForm({ ...form, contractor_id: e.target.value })} required>
          <option value="">Contractor…</option>
          {contractors.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input className={input} placeholder="Stage entry IDs (comma-separated)" value={form.stage_ids}
          onChange={e => setForm({ ...form, stage_ids: e.target.value })} required />
        <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Create bill</button>
      </form>
      {openStages.length > 0 && (
        <p className="text-xs text-[var(--text-muted)] print:hidden">
          Stages with labor: {openStages.map(s => `${s.number}(#${s.id})=${s.labor_amount}`).join(", ")}
        </p>
      )}
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Number</th><th className="p-2">Date</th><th className="p-2">Contractor</th>
            <th className="p-2 text-right">Amount</th><th className="p-2">Bill</th><th className="p-2">Status</th>
          </tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{r.number}</td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2">{r.contractor_id}</td>
                <td className="p-2 text-right">{r.labor_amount}</td>
                <td className="p-2">{r.bill_id || "—"}</td>
                <td className="p-2">{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
