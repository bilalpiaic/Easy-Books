"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { Plus, Trash2 } from "lucide-react"

type QualityLine = { quality_id: number; expected_mtr: number; grey_rate: number }
type PackingLine = {
  item_type: string; quality_id: number; process_id?: number | null
  qty: number; meters: number; rate: number
}
type SO = {
  id: number; number: string; customer_id: number; quality_id: number
  date: string; expected_mtr: number; grey_rate: number; status: string
  quality_lines?: QualityLine[]; packing_lines?: PackingLine[]
}
type Customer = { id: number; name: string }
type Quality = { id: number; code: string; name: string }
type Process = { id: number; code: string; name: string; is_active: boolean }

const PACK_TYPES = ["KMZ", "SHL", "DPT", "2PC", "3PC", "OTHER"]
const today = () => new Date().toISOString().slice(0, 10)

export default function SalesOrdersPage() {
  const [rows, setRows] = useState<SO[] | null>(null)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [qualities, setQualities] = useState<Quality[]>([])
  const [processes, setProcesses] = useState<Process[]>([])
  const [show, setShow] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({ customer_id: "", date: today(), notes: "" })
  const [qLines, setQLines] = useState([{ quality_id: "", expected_mtr: "", grey_rate: "" }])
  const [pLines, setPLines] = useState([
    { item_type: "KMZ", quality_id: "", process_id: "", qty: "", meters: "", rate: "" },
  ])

  function load() {
    apiFetch<SO[]>("/api/textile-processing/sales-orders").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }
  useEffect(() => {
    load()
    apiFetch<Customer[]>("/api/customers").then(d => setCustomers(Array.isArray(d) ? d : [])).catch(() => setCustomers([]))
    apiFetch<Quality[]>("/api/textile-processing/qualities?active_only=true").then(d => setQualities(Array.isArray(d) ? d : [])).catch(() => setQualities([]))
    apiFetch<Process[]>("/api/textile-processing/processes").then(d => setProcesses(Array.isArray(d) ? d : [])).catch(() => setProcesses([]))
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    const quality_lines = qLines
      .filter(l => l.quality_id)
      .map(l => ({
        quality_id: Number(l.quality_id),
        expected_mtr: parseFloat(l.expected_mtr) || 0,
        grey_rate: parseFloat(l.grey_rate) || 0,
      }))
    if (!quality_lines.length) { setErr("Add at least one grey quality"); return }
    const packing_lines = pLines
      .filter(l => l.quality_id && l.item_type)
      .map(l => ({
        item_type: l.item_type,
        quality_id: Number(l.quality_id),
        process_id: l.process_id ? Number(l.process_id) : null,
        qty: parseFloat(l.qty) || 0,
        meters: parseFloat(l.meters) || 0,
        rate: parseFloat(l.rate) || 0,
      }))
    try {
      await apiFetch("/api/textile-processing/sales-orders", {
        method: "POST",
        body: JSON.stringify({
          customer_id: Number(form.customer_id),
          date: form.date,
          notes: form.notes || null,
          quality_lines,
          packing_lines,
        }),
      })
      setShow(false)
      setQLines([{ quality_id: "", expected_mtr: "", grey_rate: "" }])
      setPLines([{ item_type: "KMZ", quality_id: "", process_id: "", qty: "", meters: "", rate: "" }])
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"
  const custMap = Object.fromEntries(customers.map(c => [c.id, c.name]))
  const qualMap = Object.fromEntries(qualities.map(q => [q.id, q.code]))
  const dyePrint = processes.filter(p => p.is_active && (p.code === "dyeing" || p.code === "printing"))

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-xl font-semibold">Sales Orders</h1>
        <button type="button" onClick={() => setShow(s => !s)} className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">New SO</button>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      {show && (
        <form onSubmit={submit} className="space-y-4 border border-[var(--border)] rounded-xl p-4 print:hidden">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            <select className={input} value={form.customer_id} onChange={e => setForm({ ...form, customer_id: e.target.value })} required>
              <option value="">Customer…</option>
              {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <input type="date" className={input} value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} />
            <input className={input} placeholder="Notes" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold">Grey quality inputs</h2>
              <button type="button" className="text-xs text-[var(--primary)] flex items-center gap-1"
                onClick={() => setQLines(l => [...l, { quality_id: "", expected_mtr: "", grey_rate: "" }])}>
                <Plus className="w-3 h-3" /> Add quality
              </button>
            </div>
            <div className="space-y-2">
              {qLines.map((l, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-center">
                  <select className={`${input} col-span-5`} value={l.quality_id}
                    onChange={e => setQLines(rows => rows.map((r, j) => j === i ? { ...r, quality_id: e.target.value } : r))} required={i === 0}>
                    <option value="">Quality…</option>
                    {qualities.map(q => <option key={q.id} value={q.id}>{q.code}</option>)}
                  </select>
                  <input className={`${input} col-span-3`} placeholder="Expected MTR" value={l.expected_mtr}
                    onChange={e => setQLines(rows => rows.map((r, j) => j === i ? { ...r, expected_mtr: e.target.value } : r))} />
                  <input className={`${input} col-span-3`} placeholder="Grey rate" value={l.grey_rate}
                    onChange={e => setQLines(rows => rows.map((r, j) => j === i ? { ...r, grey_rate: e.target.value } : r))} />
                  <button type="button" className="col-span-1 text-red-500 disabled:opacity-30" disabled={qLines.length === 1}
                    onClick={() => setQLines(rows => rows.filter((_, j) => j !== i))}>
                    <Trash2 className="w-4 h-4 mx-auto" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold">Fresh packing items (KMZ / SHL / DPT / 2PC / 3PC…)</h2>
              <button type="button" className="text-xs text-[var(--primary)] flex items-center gap-1"
                onClick={() => setPLines(l => [...l, { item_type: "KMZ", quality_id: "", process_id: "", qty: "", meters: "", rate: "" }])}>
                <Plus className="w-3 h-3" /> Add packing
              </button>
            </div>
            <div className="space-y-2">
              {pLines.map((l, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-center">
                  <select className={`${input} col-span-2`} value={l.item_type}
                    onChange={e => setPLines(rows => rows.map((r, j) => j === i ? { ...r, item_type: e.target.value } : r))}>
                    {PACK_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <select className={`${input} col-span-3`} value={l.quality_id}
                    onChange={e => setPLines(rows => rows.map((r, j) => j === i ? { ...r, quality_id: e.target.value } : r))}>
                    <option value="">Grey quality…</option>
                    {qualities.map(q => <option key={q.id} value={q.id}>{q.code}</option>)}
                  </select>
                  <select className={`${input} col-span-2`} value={l.process_id}
                    onChange={e => setPLines(rows => rows.map((r, j) => j === i ? { ...r, process_id: e.target.value } : r))}>
                    <option value="">Process…</option>
                    {(dyePrint.length ? dyePrint : processes.filter(p => p.is_active)).map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                  <input className={`${input} col-span-1`} placeholder="Qty" value={l.qty}
                    onChange={e => setPLines(rows => rows.map((r, j) => j === i ? { ...r, qty: e.target.value } : r))} />
                  <input className={`${input} col-span-2`} placeholder="Mtrs" value={l.meters}
                    onChange={e => setPLines(rows => rows.map((r, j) => j === i ? { ...r, meters: e.target.value } : r))} />
                  <input className={`${input} col-span-1`} placeholder="Rate" value={l.rate}
                    onChange={e => setPLines(rows => rows.map((r, j) => j === i ? { ...r, rate: e.target.value } : r))} />
                  <button type="button" className="col-span-1 text-red-500"
                    onClick={() => setPLines(rows => rows.length === 1 ? rows : rows.filter((_, j) => j !== i))}>
                    <Trash2 className="w-4 h-4 mx-auto" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-4 py-2">Create sales order</button>
        </form>
      )}

      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Number</th><th className="p-2">Date</th><th className="p-2">Customer</th>
            <th className="p-2">Grey qualities</th><th className="p-2">Packing</th>
            <th className="p-2 text-right">Expected</th><th className="p-2">Status</th>
          </tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{r.number}</td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2">{custMap[r.customer_id] || r.customer_id}</td>
                <td className="p-2 text-xs">
                  {(r.quality_lines?.length
                    ? r.quality_lines.map(l => qualMap[l.quality_id] || l.quality_id).join(", ")
                    : (qualMap[r.quality_id] || r.quality_id))}
                </td>
                <td className="p-2 text-xs">
                  {(r.packing_lines || []).map(l => l.item_type).join(", ") || "—"}
                </td>
                <td className="p-2 text-right">{r.expected_mtr}</td>
                <td className="p-2">{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Link href="/processing" className="text-sm text-[var(--primary)] print:hidden">← Hub</Link>
    </div>
  )
}
