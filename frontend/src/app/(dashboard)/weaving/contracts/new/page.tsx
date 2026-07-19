"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { ratePerLb } from "@/lib/weavingUnits"

type Opt = { id: number; name: string; code?: string }

const today = () => new Date().toISOString().slice(0, 10)

export default function NewContractPage() {
  const router = useRouter()
  const [customers, setCustomers] = useState<Opt[]>([])
  const [qualities, setQualities] = useState<Opt[]>([])
  const [yarnTypes, setYarnTypes] = useState<Opt[]>([])
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState({
    customer_id: "",
    fabric_quality_id: "",
    yarn_type_id: "",
    start_date: today(),
    end_date: "",
    contract_meters: "",
    pick_per_inch: "",
    assumed_yarn_rate_per_kg: "",
    fabric_return_price_per_meter: "",
    weaving_rate: "",
    expected_shrinkage_pct: "",
    payment_terms: "",
    status: "draft",
    notes: "",
  })

  useEffect(() => {
    Promise.all([
      apiFetch<{ items: Opt[] }>("/api/customers?limit=500").catch(() => ({ items: [] })),
      apiFetch<Opt[]>("/api/weaving/fabric-qualities").catch(() => []),
      apiFetch<Opt[]>("/api/weaving/yarn-types").catch(() => []),
    ]).then(([c, q, y]) => {
      setCustomers(c.items ?? [])
      setQualities(Array.isArray(q) ? q : [])
      setYarnTypes(Array.isArray(y) ? y : [])
    })
  }, [])

  const rateKg = parseFloat(form.assumed_yarn_rate_per_kg) || 0
  const meters = parseFloat(form.contract_meters) || 0
  const wRate = parseFloat(form.weaving_rate) || 0

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      const body = {
        customer_id: Number(form.customer_id),
        fabric_quality_id: form.fabric_quality_id ? Number(form.fabric_quality_id) : null,
        yarn_type_id: form.yarn_type_id ? Number(form.yarn_type_id) : null,
        start_date: form.start_date,
        end_date: form.end_date || null,
        contract_meters: meters,
        pick_per_inch: parseFloat(form.pick_per_inch) || 0,
        assumed_yarn_rate_per_kg: rateKg,
        fabric_return_price_per_meter: parseFloat(form.fabric_return_price_per_meter) || 0,
        weaving_rate: wRate,
        expected_shrinkage_pct: parseFloat(form.expected_shrinkage_pct) || 0,
        payment_terms: form.payment_terms || null,
        status: form.status,
        notes: form.notes || null,
      }
      const created = await apiFetch<{ id: number }>("/api/weaving/contracts", {
        method: "POST",
        body: JSON.stringify(body),
      })
      router.push(`/weaving/contracts/${created.id}`)
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Create failed")
      setSaving(false)
    }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm bg-[var(--bg-card)]"
  const label = "block text-xs font-medium text-[var(--text-muted)] mb-1"

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">New Contract</h1>
        <Link href="/weaving/contracts" className="text-sm text-[var(--text-muted)] hover:text-[var(--primary)]">Cancel</Link>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <form onSubmit={submit} className="space-y-4 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className={label}>Customer *</label>
            <select required value={form.customer_id} onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))} className={input}>
              <option value="">Select…</option>
              {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className={label}>Status</label>
            <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} className={input}>
              {["draft", "in_process", "completed", "delayed", "cancelled"].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={label}>Fabric quality</label>
            <select value={form.fabric_quality_id} onChange={e => setForm(f => ({ ...f, fabric_quality_id: e.target.value }))} className={input}>
              <option value="">—</option>
              {qualities.map(q => <option key={q.id} value={q.id}>{q.code} — {q.name}</option>)}
            </select>
          </div>
          <div>
            <label className={label}>Yarn type</label>
            <select value={form.yarn_type_id} onChange={e => setForm(f => ({ ...f, yarn_type_id: e.target.value }))} className={input}>
              <option value="">—</option>
              {yarnTypes.map(y => <option key={y.id} value={y.id}>{y.code} — {y.name}</option>)}
            </select>
          </div>
          <div>
            <label className={label}>Start date *</label>
            <input type="date" required value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} className={input} />
          </div>
          <div>
            <label className={label}>End date</label>
            <input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} className={input} />
          </div>
          <div>
            <label className={label}>Contract meters</label>
            <input type="number" step="any" value={form.contract_meters} onChange={e => setForm(f => ({ ...f, contract_meters: e.target.value }))} className={input} />
          </div>
          <div>
            <label className={label}>Pick / inch</label>
            <input type="number" step="any" value={form.pick_per_inch} onChange={e => setForm(f => ({ ...f, pick_per_inch: e.target.value }))} className={input} />
          </div>
          <div>
            <label className={label}>Assumed yarn rate / kg</label>
            <input type="number" step="any" value={form.assumed_yarn_rate_per_kg} onChange={e => setForm(f => ({ ...f, assumed_yarn_rate_per_kg: e.target.value }))} className={input} />
            <p className="text-xs text-[var(--text-muted)] mt-1">Rate / lb (derived): {ratePerLb(rateKg).toFixed(4)}</p>
          </div>
          <div>
            <label className={label}>Fabric return price / m</label>
            <input type="number" step="any" value={form.fabric_return_price_per_meter} onChange={e => setForm(f => ({ ...f, fabric_return_price_per_meter: e.target.value }))} className={input} />
          </div>
          <div>
            <label className={label}>Weaving rate</label>
            <input type="number" step="any" value={form.weaving_rate} onChange={e => setForm(f => ({ ...f, weaving_rate: e.target.value }))} className={input} />
            <p className="text-xs text-[var(--text-muted)] mt-1">Expected revenue: {(meters * wRate).toFixed(2)}</p>
          </div>
          <div>
            <label className={label}>Expected shrinkage %</label>
            <input type="number" step="any" value={form.expected_shrinkage_pct} onChange={e => setForm(f => ({ ...f, expected_shrinkage_pct: e.target.value }))} className={input} />
          </div>
          <div className="sm:col-span-2">
            <label className={label}>Payment terms</label>
            <input value={form.payment_terms} onChange={e => setForm(f => ({ ...f, payment_terms: e.target.value }))} className={input} />
          </div>
          <div className="sm:col-span-2">
            <label className={label}>Notes</label>
            <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className={input} rows={2} />
          </div>
        </div>
        <div className="flex justify-end">
          <button type="submit" disabled={saving} className="px-4 py-2 rounded-xl bg-[var(--primary)] text-white text-sm disabled:opacity-50">
            {saving ? "Creating…" : "Create contract"}
          </button>
        </div>
      </form>
    </div>
  )
}
