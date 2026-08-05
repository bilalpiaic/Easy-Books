"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type Stage = {
  id: number; number: string; date: string; process_id: number; lot_id: number
  input_mtr: number; output_mtr: number; visible_wastage_mtr: number
  invisible_wastage_mtr: number; labor_amount: number; status: string
  contractor_id?: number | null
}
type PO = { id: number; number: string; issued_mtr: number; status: string }
type Process = { id: number; code: string; name: string; seq: number }
type Contractor = { id: number; name: string; default_process_id?: number | null }

const today = () => new Date().toISOString().slice(0, 10)

export default function StagesPage() {
  const [rows, setRows] = useState<Stage[]>([])
  const [pos, setPos] = useState<PO[]>([])
  const [processes, setProcesses] = useState<Process[]>([])
  const [contractors, setContractors] = useState<Contractor[]>([])
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    production_order_id: "", process_id: "", date: today(),
    input_mtr: "", output_mtr: "", visible_wastage_mtr: "0", invisible_wastage_mtr: "0",
    contractor_id: "", labor_qty: "", labor_rate: "",
  })

  function load() {
    apiFetch<Stage[]>("/api/textile-processing/stages").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
    apiFetch<PO[]>("/api/textile-processing/production-orders").then(d => setPos(Array.isArray(d) ? d : [])).catch(() => setPos([]))
    apiFetch<Process[]>("/api/textile-processing/processes").then(d => setProcesses(Array.isArray(d) ? d : [])).catch(() => setProcesses([]))
    apiFetch<Contractor[]>("/api/textile-processing/contractors").then(d => setContractors(Array.isArray(d) ? d : [])).catch(() => setContractors([]))
  }
  useEffect(() => { load() }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    try {
      await apiFetch("/api/textile-processing/stages", {
        method: "POST",
        body: JSON.stringify({
          production_order_id: Number(form.production_order_id),
          process_id: Number(form.process_id),
          date: form.date,
          input_mtr: parseFloat(form.input_mtr) || 0,
          output_mtr: parseFloat(form.output_mtr) || 0,
          visible_wastage_mtr: parseFloat(form.visible_wastage_mtr) || 0,
          invisible_wastage_mtr: parseFloat(form.invisible_wastage_mtr) || 0,
          contractor_id: form.contractor_id ? Number(form.contractor_id) : null,
          labor_qty: parseFloat(form.labor_qty) || 0,
          labor_rate: parseFloat(form.labor_rate) || 0,
        }),
      })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  async function tagContractor(stageId: number, contractorId: string) {
    setErr("")
    try {
      await apiFetch(`/api/textile-processing/stages/${stageId}`, {
        method: "PATCH",
        body: JSON.stringify({
          contractor_id: contractorId ? Number(contractorId) : null,
        }),
      })
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  // Prefer contractor tagged for selected process
  useEffect(() => {
    if (!form.process_id || form.contractor_id) return
    const tagged = contractors.find(c => String(c.default_process_id) === form.process_id)
    if (tagged) setForm(f => ({ ...f, contractor_id: String(tagged.id) }))
  }, [form.process_id, contractors]) // eslint-disable-line react-hooks/exhaustive-deps

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"
  const procMap = Object.fromEntries(processes.map(p => [p.id, p.name]))
  const contrMap = Object.fromEntries(contractors.map(c => [c.id, c.name]))

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <h1 className="text-xl font-semibold">PPC Stage Entries</h1>
      <p className="text-sm text-[var(--text-muted)]">Every stage records visible + invisible wastage. Balance: input ≈ output + visible + invisible.</p>
      {err && <p className="text-sm text-red-600">{err}</p>}

      <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-4 gap-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
        <select className={input} value={form.production_order_id} onChange={e => setForm({ ...form, production_order_id: e.target.value })} required>
          <option value="">Production order…</option>
          {pos.map(p => <option key={p.id} value={p.id}>{p.number}</option>)}
        </select>
        <select className={input} value={form.process_id} onChange={e => setForm({ ...form, process_id: e.target.value })} required>
          <option value="">Process…</option>
          {processes.map(p => <option key={p.id} value={p.id}>{p.seq}. {p.name}</option>)}
        </select>
        <input type="date" className={input} value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} />
        <select className={input} value={form.contractor_id} onChange={e => setForm({ ...form, contractor_id: e.target.value })}>
          <option value="">Contractor (optional)</option>
          {contractors.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input className={input} placeholder="Input MTR" value={form.input_mtr} onChange={e => setForm({ ...form, input_mtr: e.target.value })} required />
        <input className={input} placeholder="Output MTR" value={form.output_mtr} onChange={e => setForm({ ...form, output_mtr: e.target.value })} required />
        <input className={input} placeholder="Visible wastage" value={form.visible_wastage_mtr} onChange={e => setForm({ ...form, visible_wastage_mtr: e.target.value })} />
        <input className={input} placeholder="Invisible wastage" value={form.invisible_wastage_mtr} onChange={e => setForm({ ...form, invisible_wastage_mtr: e.target.value })} />
        <input className={input} placeholder="Labor qty" value={form.labor_qty} onChange={e => setForm({ ...form, labor_qty: e.target.value })} />
        <input className={input} placeholder="Labor rate" value={form.labor_rate} onChange={e => setForm({ ...form, labor_rate: e.target.value })} />
        <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2 md:col-span-2">Post stage</button>
      </form>

      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">#</th><th className="p-2">Date</th><th className="p-2">Process</th>
            <th className="p-2 text-right">In</th><th className="p-2 text-right">Out</th>
            <th className="p-2 text-right">Vis</th><th className="p-2 text-right">Invis</th>
            <th className="p-2 text-right">Labor</th>
            <th className="p-2 print:hidden">Contractor tag</th>
          </tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{r.number}</td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2">{procMap[r.process_id] || r.process_id}</td>
                <td className="p-2 text-right">{r.input_mtr}</td>
                <td className="p-2 text-right">{r.output_mtr}</td>
                <td className="p-2 text-right">{r.visible_wastage_mtr}</td>
                <td className="p-2 text-right">{r.invisible_wastage_mtr}</td>
                <td className="p-2 text-right">{r.labor_amount}</td>
                <td className="p-2 print:hidden">
                  <select
                    className="border border-[var(--border)] rounded px-2 py-1 text-xs max-w-[140px]"
                    value={r.contractor_id ?? ""}
                    onChange={e => tagContractor(r.id, e.target.value)}
                    title={r.contractor_id ? contrMap[r.contractor_id] : "Tag contractor"}
                  >
                    <option value="">—</option>
                    {contractors.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
