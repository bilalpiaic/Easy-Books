"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Plus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { RateKgLb, WeightTripleDisplay } from "@/components/weaving/WeightDisplays"
import { ratePerLb, weightTriple } from "@/lib/weavingUnits"

type Contract = { id: number; number: string; assumed_yarn_rate_per_kg: number }
type YarnType = { id: number; code: string; name: string }
type Row = {
  id: number
  number: string
  contract_id: number
  date: string
  gross_kg: number
  tare_kg: number
  net_kg: number
  net_lbs: number
  net_bags: number
  rate_per_kg: number
  rate_per_lb: number
  yarn_value: number
}

const today = () => new Date().toISOString().slice(0, 10)

export default function YarnInwardPage() {
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [yarnTypes, setYarnTypes] = useState<YarnType[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    contract_id: "", yarn_type_id: "", date: today(),
    gross_kg: "", tare_kg: "", rate_per_kg: "", yarn_value: "",
  })

  const load = useCallback(() => {
    apiFetch<Row[]>("/api/weaving/yarn-inwards").then(d => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([]))
  }, [])

  useEffect(() => {
    load()
    Promise.all([
      apiFetch<Contract[]>("/api/weaving/contracts").catch(() => []),
      apiFetch<YarnType[]>("/api/weaving/yarn-types").catch(() => []),
    ]).then(([c, y]) => {
      setContracts(Array.isArray(c) ? c : [])
      setYarnTypes(Array.isArray(y) ? y : [])
    })
  }, [load])

  const gross = parseFloat(form.gross_kg) || 0
  const tare = parseFloat(form.tare_kg) || 0
  const net = Math.max(gross - tare, 0)
  const netT = weightTriple(net)
  const selected = contracts.find(c => String(c.id) === form.contract_id)
  const rateKg = form.rate_per_kg !== ""
    ? parseFloat(form.rate_per_kg) || 0
    : (selected?.assumed_yarn_rate_per_kg ?? 0)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/weaving/yarn-inwards", {
        method: "POST",
        body: JSON.stringify({
          contract_id: Number(form.contract_id),
          yarn_type_id: form.yarn_type_id ? Number(form.yarn_type_id) : null,
          date: form.date,
          gross_kg: gross,
          tare_kg: tare,
          rate_per_kg: form.rate_per_kg !== "" ? rateKg : null,
          yarn_value: form.yarn_value !== "" ? parseFloat(form.yarn_value) : null,
        }),
      })
      setShowForm(false)
      setForm({ contract_id: "", yarn_type_id: "", date: today(), gross_kg: "", tare_kg: "", rate_per_kg: "", yarn_value: "" })
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const cmap = Object.fromEntries(contracts.map(c => [c.id, c.number]))

  return (
    <div className="p-4 space-y-4">
      <div className="flex justify-end print:hidden">
        <button onClick={() => { setShowForm(true); setErr("") }}
          className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> New Yarn Inward
        </button>
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">YI #</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Contract</th>
              <th className="px-3 py-2">Net weight</th>
              <th className="px-3 py-2">Rate</th>
              <th className="px-3 py-2 text-right">Value</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map(r => (
              <tr key={r.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 whitespace-nowrap font-medium">{r.number}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="px-3 py-2">
                  <Link href={`/weaving/contracts/${r.contract_id}`} className="text-[var(--primary)]">
                    {cmap[r.contract_id] || `#${r.contract_id}`}
                  </Link>
                </td>
                <td className="px-3 py-2"><WeightTripleDisplay kg={r.net_kg} lbs={r.net_lbs} bags={r.net_bags} /></td>
                <td className="px-3 py-2"><RateKgLb ratePerKg={r.rate_per_kg} ratePerLbValue={r.rate_per_lb} /></td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(r.yarn_value)}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">No yarn inwards yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <form onSubmit={submit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] w-full max-w-lg p-5 space-y-3">
            <h2 className="text-lg font-semibold">New Yarn Inward</h2>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs text-[var(--text-muted)]">Contract *</label>
                <select required value={form.contract_id} onChange={e => setForm(f => ({ ...f, contract_id: e.target.value }))} className={input}>
                  <option value="">Select…</option>
                  {contracts.map(c => <option key={c.id} value={c.id}>{c.number}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Yarn type</label>
                <select value={form.yarn_type_id} onChange={e => setForm(f => ({ ...f, yarn_type_id: e.target.value }))} className={input}>
                  <option value="">—</option>
                  {yarnTypes.map(y => <option key={y.id} value={y.id}>{y.code} — {y.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Date *</label>
                <input type="date" required value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className={input} />
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
                <label className="text-xs text-[var(--text-muted)]">Rate / kg (blank = contract)</label>
                <input type="number" step="any" value={form.rate_per_kg} onChange={e => setForm(f => ({ ...f, rate_per_kg: e.target.value }))} className={input} />
                <p className="text-xs text-[var(--text-muted)] mt-1">/lb: {ratePerLb(rateKg).toFixed(4)}</p>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">Yarn value (blank = net × rate)</label>
                <input type="number" step="any" value={form.yarn_value} onChange={e => setForm(f => ({ ...f, yarn_value: e.target.value }))} className={input} />
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
