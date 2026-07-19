"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import { RateKgLb } from "@/components/weaving/WeightDisplays"
import { ratePerLb } from "@/lib/weavingUnits"

type Contract = {
  id: number
  number: string
  customer_id: number
  fabric_quality_id?: number | null
  yarn_type_id?: number | null
  start_date: string
  end_date?: string | null
  contract_meters: number
  pick_per_inch: number
  assumed_yarn_rate_per_kg: number
  assumed_yarn_rate_per_lb: number
  fabric_return_price_per_meter: number
  weaving_rate: number
  expected_shrinkage_pct: number
  expected_weaving_revenue: number
  payment_terms?: string | null
  status: string
  notes?: string | null
}

type Opt = { id: number; name: string; code?: string }

export default function ContractDetailPage() {
  const { id } = useParams<{ id: string }>()
  const fmt = useFmt()
  const [c, setC] = useState<Contract | null>(null)
  const [customerName, setCustomerName] = useState("")
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")
  const [form, setForm] = useState<Record<string, string>>({})

  const load = useCallback(async () => {
    const row = await apiFetch<Contract>(`/api/weaving/contracts/${id}`).catch(() => null)
    if (!row) return
    setC(row)
    setForm({
      status: row.status,
      end_date: row.end_date ?? "",
      contract_meters: String(row.contract_meters),
      pick_per_inch: String(row.pick_per_inch),
      assumed_yarn_rate_per_kg: String(row.assumed_yarn_rate_per_kg),
      fabric_return_price_per_meter: String(row.fabric_return_price_per_meter),
      weaving_rate: String(row.weaving_rate),
      expected_shrinkage_pct: String(row.expected_shrinkage_pct),
      payment_terms: row.payment_terms ?? "",
      notes: row.notes ?? "",
    })
    const cust = await apiFetch<Opt>(`/api/customers/${row.customer_id}`).catch(() => null)
    if (cust) setCustomerName(cust.name)
  }, [id])

  useEffect(() => { load() }, [load])

  async function save() {
    if (!c) return
    setSaving(true)
    setErr("")
    try {
      await apiFetch(`/api/weaving/contracts/${c.id}`, {
        method: "PUT",
        body: JSON.stringify({
          status: form.status,
          end_date: form.end_date || null,
          contract_meters: parseFloat(form.contract_meters) || 0,
          pick_per_inch: parseFloat(form.pick_per_inch) || 0,
          assumed_yarn_rate_per_kg: parseFloat(form.assumed_yarn_rate_per_kg) || 0,
          fabric_return_price_per_meter: parseFloat(form.fabric_return_price_per_meter) || 0,
          weaving_rate: parseFloat(form.weaving_rate) || 0,
          expected_shrinkage_pct: parseFloat(form.expected_shrinkage_pct) || 0,
          payment_terms: form.payment_terms || null,
          notes: form.notes || null,
        }),
      })
      setEditing(false)
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  if (!c) return <div className="p-4 text-sm text-[var(--text-muted)]">Loading…</div>

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const rateKg = parseFloat(form.assumed_yarn_rate_per_kg) || 0

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">{c.number}</h1>
          <p className="text-sm text-[var(--text-muted)]">{customerName || `Customer #${c.customer_id}`} · started {fmtDate(c.start_date)}</p>
        </div>
        <div className="flex gap-2 print:hidden">
          <Link href={`/weaving/reports/contract-control?contract=${c.id}`} className="px-3 py-2 text-sm rounded-lg border border-[var(--border)]">
            Control panel
          </Link>
          {!editing ? (
            <button onClick={() => setEditing(true)} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white">Edit</button>
          ) : (
            <>
              <button onClick={() => setEditing(false)} className="px-3 py-2 text-sm rounded-lg border border-[var(--border)]">Cancel</button>
              <button onClick={save} disabled={saving} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50">
                {saving ? "Saving…" : "Save"}
              </button>
            </>
          )}
        </div>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <Field label="Status" editing={editing} value={c.status} input={
          <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} className={input}>
            {["draft", "in_process", "completed", "delayed", "cancelled"].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        } display={<span className="capitalize">{c.status.replace("_", " ")}</span>} />
        <Field label="End date" editing={editing} value={c.end_date ? fmtDate(c.end_date) : "—"} input={
          <input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} className={input} />
        } />
        <Field label="Contract meters" editing={editing} value={fmt(c.contract_meters)} input={
          <input type="number" step="any" value={form.contract_meters} onChange={e => setForm(f => ({ ...f, contract_meters: e.target.value }))} className={input} />
        } />
        <Field label="Pick / inch" editing={editing} value={fmt(c.pick_per_inch)} input={
          <input type="number" step="any" value={form.pick_per_inch} onChange={e => setForm(f => ({ ...f, pick_per_inch: e.target.value }))} className={input} />
        } />
        <div>
          <div className="text-xs text-[var(--text-muted)] mb-1">Assumed yarn rate</div>
          {editing ? (
            <>
              <input type="number" step="any" value={form.assumed_yarn_rate_per_kg}
                onChange={e => setForm(f => ({ ...f, assumed_yarn_rate_per_kg: e.target.value }))} className={input} />
              <p className="text-xs text-[var(--text-muted)] mt-1">/lb derived: {ratePerLb(rateKg).toFixed(4)}</p>
            </>
          ) : (
            <RateKgLb ratePerKg={c.assumed_yarn_rate_per_kg} ratePerLbValue={c.assumed_yarn_rate_per_lb} />
          )}
        </div>
        <Field label="Fabric return price / m" editing={editing} value={fmt(c.fabric_return_price_per_meter)} input={
          <input type="number" step="any" value={form.fabric_return_price_per_meter}
            onChange={e => setForm(f => ({ ...f, fabric_return_price_per_meter: e.target.value }))} className={input} />
        } />
        <Field label="Weaving rate" editing={editing} value={fmt(c.weaving_rate)} input={
          <input type="number" step="any" value={form.weaving_rate} onChange={e => setForm(f => ({ ...f, weaving_rate: e.target.value }))} className={input} />
        } />
        <Field label="Expected shrinkage %" editing={editing} value={fmt(c.expected_shrinkage_pct)} input={
          <input type="number" step="any" value={form.expected_shrinkage_pct}
            onChange={e => setForm(f => ({ ...f, expected_shrinkage_pct: e.target.value }))} className={input} />
        } />
        <div>
          <div className="text-xs text-[var(--text-muted)] mb-1">Expected weaving revenue</div>
          <div className="font-medium tabular-nums">{fmt(c.expected_weaving_revenue)}</div>
        </div>
        <Field label="Payment terms" editing={editing} value={c.payment_terms || "—"} input={
          <input value={form.payment_terms} onChange={e => setForm(f => ({ ...f, payment_terms: e.target.value }))} className={input} />
        } />
        <div className="sm:col-span-2">
          <div className="text-xs text-[var(--text-muted)] mb-1">Notes</div>
          {editing ? (
            <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className={input} rows={2} />
          ) : (
            <div>{c.notes || "—"}</div>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({
  label, editing, value, input, display,
}: {
  label: string
  editing: boolean
  value: string
  input: React.ReactNode
  display?: React.ReactNode
}) {
  return (
    <div>
      <div className="text-xs text-[var(--text-muted)] mb-1">{label}</div>
      {editing ? input : (display ?? <div className="font-medium">{value}</div>)}
    </div>
  )
}
