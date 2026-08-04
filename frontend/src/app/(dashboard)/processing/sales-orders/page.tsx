"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type SO = { id: number; number: string; customer_id: number; quality_id: number; date: string; expected_mtr: number; grey_rate: number; status: string }
type Customer = { id: number; name: string }
type Quality = { id: number; code: string; name: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function SalesOrdersPage() {
  const [rows, setRows] = useState<SO[] | null>(null)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [qualities, setQualities] = useState<Quality[]>([])
  const [show, setShow] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({ customer_id: "", quality_id: "", date: today(), expected_mtr: "", grey_rate: "" })

  function load() {
    apiFetch<SO[]>("/api/textile-processing/sales-orders").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }
  useEffect(() => {
    load()
    apiFetch<Customer[]>("/api/customers").then(d => setCustomers(Array.isArray(d) ? d : [])).catch(() => setCustomers([]))
    apiFetch<Quality[]>("/api/textile-processing/qualities").then(d => setQualities(Array.isArray(d) ? d : [])).catch(() => setQualities([]))
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    try {
      await apiFetch("/api/textile-processing/sales-orders", {
        method: "POST",
        body: JSON.stringify({
          customer_id: Number(form.customer_id),
          quality_id: Number(form.quality_id),
          date: form.date,
          expected_mtr: parseFloat(form.expected_mtr) || 0,
          grey_rate: parseFloat(form.grey_rate) || 0,
        }),
      })
      setShow(false); load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"
  const custMap = Object.fromEntries(customers.map(c => [c.id, c.name]))
  const qualMap = Object.fromEntries(qualities.map(q => [q.id, `${q.code} — ${q.name}`]))

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-xl font-semibold">Sales Orders</h1>
        <button type="button" onClick={() => setShow(s => !s)} className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">New SO</button>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      {show && (
        <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-2 border border-[var(--border)] rounded-xl p-3 print:hidden">
          <select className={input} value={form.customer_id} onChange={e => setForm({ ...form, customer_id: e.target.value })} required>
            <option value="">Customer…</option>
            {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select className={input} value={form.quality_id} onChange={e => setForm({ ...form, quality_id: e.target.value })} required>
            <option value="">Quality…</option>
            {qualities.map(q => <option key={q.id} value={q.id}>{q.code} — {q.name}</option>)}
          </select>
          <input type="date" className={input} value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} />
          <input className={input} placeholder="Expected MTR" value={form.expected_mtr} onChange={e => setForm({ ...form, expected_mtr: e.target.value })} />
          <input className={input} placeholder="Grey rate" value={form.grey_rate} onChange={e => setForm({ ...form, grey_rate: e.target.value })} />
          <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Create</button>
        </form>
      )}
      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-[var(--border)]">
            <th className="p-2">Number</th><th className="p-2">Date</th><th className="p-2">Customer</th>
            <th className="p-2">Quality</th><th className="p-2 text-right">Expected</th>
            <th className="p-2 text-right">Grey rate</th><th className="p-2">Status</th>
          </tr></thead>
          <tbody>
            {(rows || []).map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2 whitespace-nowrap">{r.number}</td>
                <td className="p-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="p-2">{custMap[r.customer_id] || r.customer_id}</td>
                <td className="p-2">{qualMap[r.quality_id] || r.quality_id}</td>
                <td className="p-2 text-right">{r.expected_mtr}</td>
                <td className="p-2 text-right">{r.grey_rate}</td>
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
