"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { Plus, Trash2 } from "lucide-react"

type Lot = {
  id: number; number: string; date: string; status: string
  received_mtr: number; ready_mtr: number; rejection_mtr: number
  sales_order_id: number; than_count: number
}
type SO = {
  id: number; number: string; quality_id: number
  quality_lines?: { quality_id: number }[]
}
type Quality = { id: number; code: string }

const today = () => new Date().toISOString().slice(0, 10)
type ThanRow = { than_no: string; meters: string; rejection_mtr: string; safi_mtr: string }

function emptyThan(n: number): ThanRow {
  return { than_no: String(n), meters: "", rejection_mtr: "0", safi_mtr: "" }
}

function calcSafi(m: string, rej: string) {
  const meters = parseFloat(m) || 0
  const rejection = parseFloat(rej) || 0
  return Math.max(0, meters - rejection)
}

export default function LotsPage() {
  const [rows, setRows] = useState<Lot[] | null>(null)
  const [sos, setSos] = useState<SO[]>([])
  const [qualities, setQualities] = useState<Quality[]>([])
  const [show, setShow] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({ sales_order_id: "", quality_id: "", date: today() })
  const [thans, setThans] = useState<ThanRow[]>([emptyThan(1), emptyThan(2), emptyThan(3)])

  function load() {
    apiFetch<Lot[]>("/api/textile-processing/lots").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }
  useEffect(() => {
    load()
    apiFetch<SO[]>("/api/textile-processing/sales-orders").then(d => setSos(Array.isArray(d) ? d : [])).catch(() => setSos([]))
    apiFetch<Quality[]>("/api/textile-processing/qualities").then(d => setQualities(Array.isArray(d) ? d : [])).catch(() => setQualities([]))
  }, [])

  const selectedSo = sos.find(s => String(s.id) === form.sales_order_id)
  const soQualIds = selectedSo
    ? Array.from(new Set([
        selectedSo.quality_id,
        ...(selectedSo.quality_lines || []).map(l => l.quality_id),
      ]))
    : []

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("")
    const payloadThans = thans
      .filter(t => t.than_no.trim() && (parseFloat(t.meters) || 0) > 0)
      .map(t => ({
        than_no: t.than_no.trim(),
        meters: parseFloat(t.meters) || 0,
        rejection_mtr: parseFloat(t.rejection_mtr) || 0,
        safi_mtr: t.safi_mtr !== "" ? parseFloat(t.safi_mtr) : calcSafi(t.meters, t.rejection_mtr),
      }))
    if (!payloadThans.length) { setErr("Enter at least one than with meters"); return }
    try {
      await apiFetch("/api/textile-processing/lots", {
        method: "POST",
        body: JSON.stringify({
          sales_order_id: Number(form.sales_order_id),
          quality_id: form.quality_id ? Number(form.quality_id) : undefined,
          date: form.date,
          thans: payloadThans,
        }),
      })
      setShow(false)
      setThans([emptyThan(1), emptyThan(2), emptyThan(3)])
      load()
    } catch (ex: unknown) { setErr(ex instanceof Error ? ex.message : "Failed") }
  }

  const input = "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full"
  const totalMtrs = thans.reduce((s, t) => s + (parseFloat(t.meters) || 0), 0)
  const totalRej = thans.reduce((s, t) => s + (parseFloat(t.rejection_mtr) || 0), 0)
  const totalSafi = thans.reduce((s, t) => s + calcSafi(t.meters, t.rejection_mtr), 0)
  const qualMap = Object.fromEntries(qualities.map(q => [q.id, q.code]))

  return (
    <div className="p-4 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-xl font-semibold">Grey Lots</h1>
        <button type="button" onClick={() => setShow(s => !s)} className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Receive lot</button>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      {show && (
        <form onSubmit={submit} className="space-y-3 border border-[var(--border)] rounded-xl p-3 print:hidden">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            <select className={input} value={form.sales_order_id}
              onChange={e => setForm({ ...form, sales_order_id: e.target.value, quality_id: "" })} required>
              <option value="">Sales order…</option>
              {sos.map(s => <option key={s.id} value={s.id}>{s.number}</option>)}
            </select>
            <select className={input} value={form.quality_id}
              onChange={e => setForm({ ...form, quality_id: e.target.value })}>
              <option value="">Quality (default primary)…</option>
              {soQualIds.map(id => (
                <option key={id} value={id}>{qualMap[id] || id}</option>
              ))}
            </select>
            <input type="date" className={input} value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} />
          </div>

          <div className="overflow-auto border border-[var(--border)] rounded-lg">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-[var(--border)] bg-[var(--surface)]">
                  <th className="p-2 w-24">Than#</th>
                  <th className="p-2 text-right">Mtrs</th>
                  <th className="p-2 text-right">Rej</th>
                  <th className="p-2 text-right">Safi</th>
                  <th className="p-2 w-10"></th>
                </tr>
              </thead>
              <tbody>
                {thans.map((t, i) => (
                  <tr key={i} className="border-b border-[var(--border)]/50">
                    <td className="p-1">
                      <input className={input} value={t.than_no}
                        onChange={e => setThans(rows => rows.map((r, j) => j === i ? { ...r, than_no: e.target.value } : r))} />
                    </td>
                    <td className="p-1">
                      <input className={`${input} text-right`} value={t.meters}
                        onChange={e => setThans(rows => rows.map((r, j) => j === i ? { ...r, meters: e.target.value } : r))} />
                    </td>
                    <td className="p-1">
                      <input className={`${input} text-right`} value={t.rejection_mtr}
                        onChange={e => setThans(rows => rows.map((r, j) => j === i ? { ...r, rejection_mtr: e.target.value } : r))} />
                    </td>
                    <td className="p-1 text-right tabular-nums px-3">
                      {calcSafi(t.meters, t.rejection_mtr).toFixed(2)}
                    </td>
                    <td className="p-1">
                      <button type="button" className="text-red-500 disabled:opacity-30" disabled={thans.length === 1}
                        onClick={() => setThans(rows => rows.filter((_, j) => j !== i))}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-semibold border-t border-[var(--border)]">
                  <td className="p-2">Total</td>
                  <td className="p-2 text-right tabular-nums">{totalMtrs.toFixed(2)}</td>
                  <td className="p-2 text-right tabular-nums">{totalRej.toFixed(2)}</td>
                  <td className="p-2 text-right tabular-nums">{totalSafi.toFixed(2)}</td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
          <div className="flex gap-2 items-center">
            <button type="button" className="text-xs text-[var(--primary)] flex items-center gap-1"
              onClick={() => setThans(rows => [...rows, emptyThan(rows.length + 1)])}>
              <Plus className="w-3 h-3" /> Add than
            </button>
            <p className="text-xs text-[var(--text-muted)] ml-auto">Issues Kachi Parchi automatically on receipt.</p>
            <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">Save lot</button>
          </div>
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
