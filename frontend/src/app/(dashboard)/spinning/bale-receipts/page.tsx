"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { RateKgLb, WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { weightTriple } from "@/lib/spinningUnits"

type Row = {
  id: number
  number: string
  product_id: number
  date: string
  gross_kg: number
  tare_kg: number
  net_kg: number
  net_lbs: number
  net_bags: number
  rate_per_kg: number
  total_value: number
  status: string
  spin_lot_id?: number | null
}

type Product = { id: number; name: string }
type Lot = { id: number; number: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function BaleReceiptsPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [lots, setLots] = useState<Lot[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    product_id: "", spin_lot_id: "", date: today(),
    gross_kg: "", tare_kg: "", moisture_pct: "0", rate_per_kg: "", lot_no: "", notes: "",
  })

  const load = useCallback(() => {
    apiFetch<Row[]>("/api/spinning/bale-receipts").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    Promise.all([
      apiFetch<{ items: Product[] }>("/api/products?limit=500").catch(() => ({ items: [] })),
      apiFetch<Lot[]>("/api/spinning/lots").catch(() => []),
    ]).then(([p, l]) => {
      setProducts(p.items ?? [])
      setLots(Array.isArray(l) ? l : [])
    })
  }, [load])

  const gross = parseFloat(form.gross_kg) || 0
  const tare = parseFloat(form.tare_kg) || 0
  const net = Math.max(gross - tare, 0)
  const netT = weightTriple(net)
  const rateKg = parseFloat(form.rate_per_kg) || 0

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/spinning/bale-receipts", {
        method: "POST",
        body: JSON.stringify({
          product_id: Number(form.product_id),
          date: form.date,
          gross_kg: gross,
          tare_kg: tare,
          moisture_pct: parseFloat(form.moisture_pct) || 0,
          rate_per_kg: rateKg,
          spin_lot_id: form.spin_lot_id ? Number(form.spin_lot_id) : null,
          lot_no: form.lot_no || null,
          notes: form.notes || null,
        }),
      })
      setShowForm(false)
      setForm({ product_id: "", spin_lot_id: "", date: today(), gross_kg: "", tare_kg: "", moisture_pct: "0", rate_per_kg: "", lot_no: "", notes: "" })
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  async function approve(id: number) {
    try {
      await apiFetch(`/api/spinning/bale-receipts/${id}/approve`, { method: "PATCH" })
      load()
    } catch { /* ignore */ }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const pmap = Object.fromEntries(products.map(p => [p.id, p.name]))
  const lmap = Object.fromEntries(lots.map(l => [l.id, l.number]))

  return (
    <div className="p-4 space-y-4">
      <div className="flex justify-end print:hidden">
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Bale Receipt
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">BR #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Product</th>
              <th className="px-3 py-2">Net weight</th>
              <th className="px-3 py-2">Rate</th>
              <th className="px-3 py-2 text-right">Value</th>
              <th className="px-3 py-2">Lot</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 print:hidden"></th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(r => (
              <tr key={r.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap font-medium">{r.number}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="px-3 py-2">{pmap[r.product_id] || `#${r.product_id}`}</td>
                <td className="px-3 py-2"><WeightTripleDisplay kg={r.net_kg} lbs={r.net_lbs} bags={r.net_bags} /></td>
                <td className="px-3 py-2"><RateKgLb ratePerKg={r.rate_per_kg} /></td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.total_value)}</td>
                <td className="px-3 py-2">
                  {r.spin_lot_id ? (
                    <Link href={`/spinning/lots/${r.spin_lot_id}`} className="text-[var(--primary)]">
                      {lmap[r.spin_lot_id] || `#${r.spin_lot_id}`}
                    </Link>
                  ) : "—"}
                </td>
                <td className="px-3 py-2 capitalize">{r.status}</td>
                <td className="px-3 py-2 print:hidden">
                  {r.status === "draft" && (
                    <button onClick={() => approve(r.id)} className="text-xs text-[var(--primary)]">Approve</button>
                  )}
                </td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={9} className="px-3 py-8 text-center text-[var(--text-muted)]">No bale receipts yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold">New Bale Receipt</h2>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Product *</label>
                <select required value={form.product_id} onChange={e => setForm(f => ({ ...f, product_id: e.target.value }))} className={input}>
                  <option value="">Select…</option>
                  {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Spin lot</label>
                <select value={form.spin_lot_id} onChange={e => setForm(f => ({ ...f, spin_lot_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {lots.map(l => <option key={l.id} value={l.id}>{l.number}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Date *</label>
                <input type="date" required value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Rate / kg *</label>
                <input type="number" step="any" required value={form.rate_per_kg} onChange={e => setForm(f => ({ ...f, rate_per_kg: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Gross kg *</label>
                <input type="number" step="any" required value={form.gross_kg} onChange={e => setForm(f => ({ ...f, gross_kg: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Tare kg</label>
                <input type="number" step="any" value={form.tare_kg} onChange={e => setForm(f => ({ ...f, tare_kg: e.target.value }))} className={input} />
              </div>
              <div className="col-span-2 text-xs text-[var(--text-muted)]">
                Net: {netT.kg.toFixed(2)} kg · {netT.lbs.toFixed(2)} lb · {netT.bags.toFixed(2)} bags
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Moisture %</label>
                <input type="number" step="any" value={form.moisture_pct} onChange={e => setForm(f => ({ ...f, moisture_pct: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Lot no</label>
                <input value={form.lot_no} onChange={e => setForm(f => ({ ...f, lot_no: e.target.value }))} className={input} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowForm(false)} className="px-3 py-2 text-sm rounded-lg border border-[var(--border)]">Cancel</button>
              <button type="submit" disabled={saving} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50">
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
