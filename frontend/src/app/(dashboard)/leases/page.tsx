"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { FileKey2, Plus, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt, useSettings } from "@/context/SettingsContext"
import { useMessages } from "@/context/MessageContext"
import PrintHeader from "@/components/PrintHeader"
import { fmtDate } from "@/lib/utils"

interface Lease {
  id: number
  number: string
  name: string
  lessor: string | null
  commencement_date: string
  term_months: number
  payment_amount: number
  annual_discount_rate: number
  present_value: number
  rou_cost: number
  liability_carrying: number
  rou_nbv: number
  status: string
}

interface Maturity {
  as_of: string
  buckets: {
    within_1_year: number
    years_1_to_5: number
    after_5_years: number
    total: number
  }
}

interface Account { id: number; code: string; name: string }

const emptyForm = {
  name: "",
  lessor: "",
  commencement_date: new Date().toISOString().slice(0, 10),
  term_months: "12",
  payment_amount: "",
  annual_discount_rate: "8",
  payment_timing: "arrears",
  initial_direct_costs: "0",
  payment_account_id: "",
  activate: true,
}

export default function LeasesPage() {
  const fmt = useFmt()
  const { settings } = useSettings()
  const { toast } = useMessages()
  const [items, setItems] = useState<Lease[]>([])
  const [maturity, setMaturity] = useState<Maturity | null>(null)
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState<{ present_value: number; rou_cost: number } | null>(null)

  const enabled = (settings.leases_enabled || "true").toLowerCase() !== "false"

  async function load() {
    setLoading(true)
    try {
      const [list, mat] = await Promise.all([
        apiFetch<{ total: number; items: Lease[] }>("/api/leases?limit=100"),
        apiFetch<Maturity>("/api/leases/maturity"),
      ])
      setItems(list.items)
      setMaturity(mat)
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Failed to load leases", "error")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (enabled) load()
    else setLoading(false)
  }, [enabled])

  async function openModal() {
    setForm(emptyForm)
    setPreview(null)
    const coa = await apiFetch<{ items: Account[] }>("/api/accounts?limit=300")
    setAccounts(coa.items.filter((a) => a.code === "1010" || a.code === "1000" || /bank|cash/i.test(a.name)))
    const bank = coa.items.find((a) => a.code === "1010")
    setForm((f) => ({ ...f, payment_account_id: bank ? String(bank.id) : "" }))
    setModal(true)
  }

  async function runPreview() {
    try {
      const p = await apiFetch<{ present_value: number; rou_cost: number }>("/api/leases/preview", {
        method: "POST",
        body: JSON.stringify({
          commencement_date: form.commencement_date,
          term_months: Number(form.term_months),
          payment_amount: Number(form.payment_amount),
          annual_discount_rate: Number(form.annual_discount_rate),
          payment_timing: form.payment_timing,
          initial_direct_costs: Number(form.initial_direct_costs) || 0,
        }),
      })
      setPreview(p)
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Preview failed", "error")
    }
  }

  async function save() {
    setBusy(true)
    try {
      const lease = await apiFetch<Lease>("/api/leases", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          lessor: form.lessor || null,
          commencement_date: form.commencement_date,
          term_months: Number(form.term_months),
          payment_amount: Number(form.payment_amount),
          annual_discount_rate: Number(form.annual_discount_rate),
          payment_timing: form.payment_timing,
          initial_direct_costs: Number(form.initial_direct_costs) || 0,
          payment_account_id: form.payment_account_id ? Number(form.payment_account_id) : null,
          activate: form.activate,
        }),
      })
      toast(`Lease ${lease.number} created`, "success")
      setModal(false)
      window.location.href = `/leases/${lease.id}`
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Create failed", "error")
      setBusy(false)
    }
  }

  if (!enabled) {
    return (
      <div className="space-y-2">
        <h1 className="font-serif text-2xl">Leases</h1>
        <p className="text-sm text-[var(--text-muted)]">
          IFRS 16 leases are disabled. Turn on <strong>IFRS 16 leases</strong> under Settings → Advanced.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PrintHeader title="Lease liability maturity" subtitle={maturity ? `As of ${fmtDate(maturity.as_of)}` : undefined} />

      <div className="flex flex-wrap items-start justify-between gap-3 print:hidden">
        <div>
          <h1 className="font-serif text-2xl text-[var(--text-primary)] flex items-center gap-2">
            <FileKey2 className="w-6 h-6 text-[var(--accent)]" />
            Leases
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            IFRS 16 right-of-use assets and lease liabilities — schedule, period post, maturity disclosure.
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => window.print()} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[var(--text-primary)]/20">
            <Printer className="w-4 h-4" /> Print disclosure
          </button>
          <button type="button" onClick={openModal} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--text-primary)] text-white">
            <Plus className="w-4 h-4" /> New lease
          </button>
        </div>
      </div>

      {maturity && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/70">
            Maturity analysis (undiscounted)
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50 border-b">
                  <th className="py-2 text-left">Bucket</th>
                  <th className="py-2 text-right">Payments</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--text-primary)]/5">
                <tr><td className="py-2">Within 1 year</td><td className="py-2 text-right font-mono">{fmt(maturity.buckets.within_1_year)}</td></tr>
                <tr><td className="py-2">1–5 years</td><td className="py-2 text-right font-mono">{fmt(maturity.buckets.years_1_to_5)}</td></tr>
                <tr><td className="py-2">After 5 years</td><td className="py-2 text-right font-mono">{fmt(maturity.buckets.after_5_years)}</td></tr>
                <tr className="font-bold"><td className="py-2">Total</td><td className="py-2 text-right font-mono underline decoration-double">{fmt(maturity.buckets.total)}</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="space-y-2 print:hidden">
        <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/70">Register</h2>
        {loading ? (
          <p className="text-sm text-[var(--text-muted)]">Loading…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">No leases yet.</p>
        ) : (
          <div className="overflow-x-auto table-freeze">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50 border-b">
                  <th className="py-2 text-left">Number</th>
                  <th className="py-2 text-left">Name</th>
                  <th className="py-2 text-left">Start</th>
                  <th className="py-2 text-right">Payment</th>
                  <th className="py-2 text-right">Liability</th>
                  <th className="py-2 text-right">RoU NBV</th>
                  <th className="py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--text-primary)]/5">
                {items.map((l) => (
                  <tr key={l.id}>
                    <td className="py-2.5 whitespace-nowrap">
                      <Link href={`/leases/${l.id}`} className="text-[var(--accent)] hover:underline font-mono">{l.number}</Link>
                    </td>
                    <td className="py-2.5">{l.name}</td>
                    <td className="py-2.5 whitespace-nowrap">{fmtDate(l.commencement_date)}</td>
                    <td className="py-2.5 text-right font-mono">{fmt(l.payment_amount)}</td>
                    <td className="py-2.5 text-right font-mono">{fmt(l.liability_carrying)}</td>
                    <td className="py-2.5 text-right font-mono">{fmt(l.rou_nbv)}</td>
                    <td className="py-2.5 capitalize">{l.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 print:hidden">
          <div className="bg-[var(--bg-page)] border border-[var(--text-primary)]/10 w-full max-w-lg p-5 space-y-3 max-h-[90vh] overflow-y-auto">
            <h3 className="font-serif text-lg">New lease</h3>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <label className="col-span-2 space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Name</span>
                <input className="w-full border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </label>
              <label className="col-span-2 space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Lessor</span>
                <input className="w-full border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5" value={form.lessor} onChange={(e) => setForm({ ...form, lessor: e.target.value })} />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Commencement</span>
                <input type="date" className="w-full border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5" value={form.commencement_date} onChange={(e) => setForm({ ...form, commencement_date: e.target.value })} />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Term (months)</span>
                <input type="number" className="w-full border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5" value={form.term_months} onChange={(e) => setForm({ ...form, term_months: e.target.value })} />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Monthly payment</span>
                <input type="number" className="w-full border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5" value={form.payment_amount} onChange={(e) => setForm({ ...form, payment_amount: e.target.value })} />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Discount rate % p.a.</span>
                <input type="number" step="0.01" className="w-full border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5" value={form.annual_discount_rate} onChange={(e) => setForm({ ...form, annual_discount_rate: e.target.value })} />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Timing</span>
                <select className="w-full border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5" value={form.payment_timing} onChange={(e) => setForm({ ...form, payment_timing: e.target.value })}>
                  <option value="arrears">In arrears</option>
                  <option value="advance">In advance</option>
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Initial direct costs</span>
                <input type="number" className="w-full border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5" value={form.initial_direct_costs} onChange={(e) => setForm({ ...form, initial_direct_costs: e.target.value })} />
              </label>
              <label className="col-span-2 space-y-1">
                <span className="text-xs text-[var(--text-muted)]">Payment account</span>
                <select className="w-full border border-[var(--text-primary)]/15 bg-transparent px-2 py-1.5" value={form.payment_account_id} onChange={(e) => setForm({ ...form, payment_account_id: e.target.value })}>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                  ))}
                </select>
              </label>
              <label className="col-span-2 flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.activate} onChange={(e) => setForm({ ...form, activate: e.target.checked })} />
                Activate on create (initial recognition + schedule)
              </label>
            </div>
            {preview && (
              <p className="text-sm text-[var(--text-muted)]">
                PV {fmt(preview.present_value)} · RoU cost {fmt(preview.rou_cost)}
              </p>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setModal(false)} className="px-3 py-1.5 text-sm border border-[var(--text-primary)]/20">Cancel</button>
              <button type="button" onClick={runPreview} className="px-3 py-1.5 text-sm border border-[var(--text-primary)]/20">Preview PV</button>
              <button type="button" disabled={busy || !form.name || !form.payment_amount} onClick={save} className="px-3 py-1.5 text-sm bg-[var(--accent)] text-white disabled:opacity-40">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
