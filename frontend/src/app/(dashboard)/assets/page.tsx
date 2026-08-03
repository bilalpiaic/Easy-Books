"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { Plus, Building2, Play, Archive, Download, Printer, Table2 } from "lucide-react"
import { downloadCSV, fmtDate, todayLocal } from "@/lib/utils"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import DocLink from "@/components/DocLink"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"
import { useMessages } from "@/context/MessageContext"

interface FixedAsset {
  id: number
  name: string
  code: string | null
  parent_id: number | null
  acquisition_date: string
  acquisition_cost: number
  accumulated_depreciation: number
  accum_impairment: number
  book_value: number
  method: string
  useful_life_months: number
  is_disposed: boolean
  last_depreciation_date: string | null
}

interface Account { id: number; code: string; name: string; type?: string }

interface AssetForm {
  name: string
  code: string
  parent_id: string
  asset_account_id: string
  accum_depr_account_id: string
  depr_expense_account_id: string
  acquisition_date: string
  acquisition_cost: string
  salvage_value: string
  useful_life_months: string
  method: string
  funding_account_id: string | null
}

interface DisposeForm {
  disposal_date: string
  mode: "sale" | "scrap"
  proceeds: string
  proceeds_account_id: string
}

const emptyForm: AssetForm = {
  name: "", code: "", parent_id: "",
  asset_account_id: "", accum_depr_account_id: "", depr_expense_account_id: "",
  acquisition_date: todayLocal(),
  acquisition_cost: "", salvage_value: "0",
  useful_life_months: "60", method: "straight_line",
  funding_account_id: null,
}

const emptyDispose: DisposeForm = {
  disposal_date: todayLocal(),
  mode: "sale",
  proceeds: "0",
  proceeds_account_id: "",
}

function isCashOrBank(a: Account) {
  const name = (a.name ?? "").toLowerCase()
  return (
    a.type === "Asset" &&
    (name.includes("cash") || name.includes("bank") ||
      a.code.startsWith("100") || a.code.startsWith("101"))
  ) || a.code === "1010" || a.code === "1000" || /bank|cash/i.test(a.name)
}

/** Parents first with children indented; orphans (missing parent) at end. */
function hierarchicalRows(items: FixedAsset[]): { asset: FixedAsset; depth: number }[] {
  const parents = items.filter(a => !a.parent_id)
  const parentIds = new Set(parents.map(p => p.id))
  const byParent = new Map<number, FixedAsset[]>()
  const orphans: FixedAsset[] = []
  for (const a of items) {
    if (!a.parent_id) continue
    if (!parentIds.has(a.parent_id)) { orphans.push(a); continue }
    const list = byParent.get(a.parent_id) ?? []
    list.push(a)
    byParent.set(a.parent_id, list)
  }
  const rows: { asset: FixedAsset; depth: number }[] = []
  for (const p of parents) {
    rows.push({ asset: p, depth: 0 })
    for (const c of byParent.get(p.id) ?? []) {
      rows.push({ asset: c, depth: 1 })
    }
  }
  for (const o of orphans) rows.push({ asset: o, depth: 1 })
  return rows
}

export default function AssetsPage() {
  const { confirm, toast } = useMessages()
  const { t } = useTranslation()

  const fmt = useFmt()
  const [items, setItems] = useState<FixedAsset[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [includeDisposed, setIncludeDisposed] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<AssetForm>(emptyForm)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState("")
  const [deprDate, setDeprDate] = useState(todayLocal())
  const [deprTarget, setDeprTarget] = useState<number | null>(null)
  const [disposeTarget, setDisposeTarget] = useState<FixedAsset | null>(null)
  const [disposeForm, setDisposeForm] = useState<DisposeForm>(emptyDispose)
  const [cashBankAccounts, setCashBankAccounts] = useState<Account[]>([])
  const [disposeBusy, setDisposeBusy] = useState(false)
  const [disposeError, setDisposeError] = useState("")

  function load() {
    setIsLoading(true)
    const qs = new URLSearchParams({ limit: "200", include_disposed: includeDisposed ? "1" : "0" })
    apiFetch<{ total: number; items: FixedAsset[] }>(`/api/assets?${qs}`)
      .then(d => { setItems(d.items); setTotal(d.total); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }

  useEffect(() => { load() }, [includeDisposed])

  const rows = useMemo(() => hierarchicalRows(items), [items])
  const parentOptions = useMemo(
    () => items.filter(a => !a.is_disposed && !a.parent_id),
    [items],
  )

  async function openModal() {
    setForm(emptyForm)
    setFormError("")
    const coa = await apiFetch<{ items: Account[] }>("/api/accounts?limit=300")
    setAccounts(coa.items ?? [])
    setModalOpen(true)
  }

  async function handleSave() {
    setFormError("")
    if (!form.name.trim()) { setFormError("Name is required"); return }
    if (!form.acquisition_cost || parseFloat(form.acquisition_cost) <= 0) {
      setFormError("Acquisition cost must be > 0"); return
    }
    setSaving(true)
    try {
      await apiFetch("/api/assets", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          code: form.code || null,
          parent_id: form.parent_id ? parseInt(form.parent_id) : null,
          asset_account_id: parseInt(form.asset_account_id),
          accum_depr_account_id: parseInt(form.accum_depr_account_id),
          depr_expense_account_id: parseInt(form.depr_expense_account_id),
          acquisition_date: form.acquisition_date,
          acquisition_cost: parseFloat(form.acquisition_cost),
          salvage_value: parseFloat(form.salvage_value) || 0,
          useful_life_months: parseInt(form.useful_life_months),
          method: form.method,
          funding_account_id: form.funding_account_id ? parseInt(form.funding_account_id) : null,
        }),
      })
      setModalOpen(false)
      load()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function openDispose(asset: FixedAsset) {
    setDisposeTarget(asset)
    setDisposeForm(emptyDispose)
    setDisposeError("")
    try {
      const coa = await apiFetch<{ items: Account[] }>("/api/accounts?limit=300")
      setCashBankAccounts((coa.items ?? []).filter(isCashOrBank))
    } catch { /* ignore */ }
  }

  async function submitDispose() {
    if (!disposeTarget) return
    if (disposeForm.mode === "sale" && !disposeForm.proceeds_account_id) {
      setDisposeError("Select a proceeds (cash/bank) account for sale")
      return
    }
    const ok = await confirm({
      title: `Dispose "${disposeTarget.name}"?`,
      message: disposeForm.mode === "sale"
        ? "Posts sale proceeds and derecognises the asset. This cannot be undone."
        : "Scrap disposal derecognises the asset with no proceeds. This cannot be undone.",
      confirmLabel: "Dispose",
      danger: true,
    })
    if (!ok) return
    setDisposeBusy(true)
    setDisposeError("")
    try {
      await apiFetch(`/api/assets/${disposeTarget.id}/dispose`, {
        method: "PATCH",
        body: JSON.stringify({
          disposal_date: disposeForm.disposal_date,
          proceeds: parseFloat(disposeForm.proceeds) || 0,
          mode: disposeForm.mode,
          proceeds_account_id: disposeForm.mode === "sale" && disposeForm.proceeds_account_id
            ? parseInt(disposeForm.proceeds_account_id)
            : null,
        }),
      })
      toast("Asset disposed", "success")
      setDisposeTarget(null)
      load()
    } catch (err) {
      setDisposeError((err as Error).message)
    } finally {
      setDisposeBusy(false)
    }
  }

  async function runDepreciation(assetId: number) {
    try {
      const result = await apiFetch<{ jv_number?: string; depreciation_amount?: number; message?: string }>(
        `/api/assets/${assetId}/depreciate`,
        { method: "POST", body: JSON.stringify({ depreciation_date: deprDate }) },
      )
      toast(result.message ?? `Depreciation posted: ${fmt(result.depreciation_amount ?? 0)} (${result.jv_number})`, "success")
      load()
    } catch (err) {
      toast((err as Error).message, "error")
    }
    setDeprTarget(null)
  }

  const accountOptions = accounts.map(a => (
    <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
  ))

  return (
    <div className="space-y-6">
      <PrintHeader title="Fixed Assets" />
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Fixed Assets</h1>
          <p className="text-[var(--text-primary)]/60 text-sm mt-1">{total} assets · IAS 16 / IAS 36</p>
        </div>
        <div className="flex items-center gap-2 print:hidden flex-wrap">
          <label className="flex items-center gap-2 text-xs text-[var(--text-primary)]/60 cursor-pointer">
            <input
              type="checkbox"
              checked={includeDisposed}
              onChange={e => setIncludeDisposed(e.target.checked)}
              className="rounded border-[var(--border)]"
            />
            Include disposed
          </label>
          <Link
            href="/assets/rollforward"
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Table2 className="w-4 h-4" /> Rollforward
          </Link>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t("common.print", "Print")}
          </button>
          <button
            onClick={() => downloadCSV("fixed-assets.csv", items.map(a => ({
              Name: a.name, Code: a.code ?? "", Parent: a.parent_id ?? "",
              "Acquisition Date": a.acquisition_date, "Acquisition Cost": a.acquisition_cost,
              "Accum. Depr.": a.accumulated_depreciation, "Accum. Impairment": a.accum_impairment ?? 0,
              "Book Value": a.book_value, Method: a.method,
              "Useful Life (months)": a.useful_life_months,
              Status: a.is_disposed ? "Disposed" : "Active",
            })))}
            disabled={items.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download size={16} /> CSV
          </button>
          <button onClick={openModal}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--text-primary)] text-white rounded-xl text-sm font-bold hover:bg-[var(--primary)] hover:text-black transition-all">
            <Plus size={16} /> New Asset
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="overflow-x-auto table-freeze freeze-col">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-[var(--bg-page)]">
            <tr>
              {["Name", "Date", "Cost", "Accum. Depr", "Impairment", "NBV", "Method", "Actions"].map(h => (
                <th key={h} className="ui-th text-left text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/50">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={8} className="ui-td text-center text-[var(--text-primary)]/40 italic">{t("common.loading", "Loading...")}</td></tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="ui-td text-center">
                  <Building2 className="w-8 h-8 mx-auto text-[var(--text-primary)]/20 mb-3" />
                  <p className="text-[var(--text-primary)]/50 text-sm">No fixed assets yet</p>
                  <button onClick={openModal} className="mt-3 text-[var(--primary)] text-sm underline">Register your first asset</button>
                </td>
              </tr>
            ) : rows.map(({ asset: a, depth }) => (
              <tr key={a.id} className={`border-t border-[var(--text-primary)]/5 hover:bg-[var(--bg-page)]/50${a.is_disposed ? " opacity-50" : ""}`}>
                <td className="ui-td font-medium" style={{ paddingLeft: depth ? undefined : undefined }}>
                  <span className={depth ? "pl-6 inline-flex items-center gap-1" : "inline-flex items-center gap-1"}>
                    {depth > 0 && <span className="text-[var(--text-primary)]/30 text-xs">↳</span>}
                    <DocLink type="fixed_asset" id={a.id} label={a.name} className="font-medium" />
                  </span>
                  {a.code && <span className="ml-2 text-xs text-[var(--text-primary)]/40">{a.code}</span>}
                  {a.is_disposed && <span className="ml-2 text-[10px] bg-[var(--text-primary)]/10 text-[var(--text-primary)]/50 rounded px-1.5 py-0.5 uppercase tracking-wide">Disposed</span>}
                </td>
                <td className="ui-td text-[var(--text-primary)]/60 whitespace-nowrap">{fmtDate(a.acquisition_date)}</td>
                <td className="ui-td font-mono">{fmt(a.acquisition_cost)}</td>
                <td className="ui-td font-mono text-red-500">({fmt(a.accumulated_depreciation)})</td>
                <td className="ui-td font-mono text-red-500">
                  {(a.accum_impairment ?? 0) > 0 ? `(${fmt(a.accum_impairment)})` : "—"}
                </td>
                <td className="ui-td font-mono font-bold">{fmt(a.book_value)}</td>
                <td className="ui-td text-xs text-[var(--text-primary)]/50 capitalize">{a.method.replace("_", " ")}</td>
                <td className="ui-td print:hidden">
                  {a.is_disposed ? null : deprTarget === a.id ? (
                    <div className="flex items-center gap-2">
                      <input type="date" value={deprDate} onChange={e => setDeprDate(e.target.value)}
                        className="border rounded px-2 py-1 text-xs" />
                      <button onClick={() => runDepreciation(a.id)}
                        className="px-2 py-1 bg-[var(--text-primary)] text-white rounded text-xs">Post</button>
                      <button onClick={() => setDeprTarget(null)} className="text-xs text-[var(--text-primary)]/40">✕</button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <button onClick={() => setDeprTarget(a.id)}
                        className="flex items-center gap-1 text-xs text-[var(--primary)] hover:underline">
                        <Play size={12} /> Depreciate
                      </button>
                      <button onClick={() => openDispose(a)}
                        className="flex items-center gap-1 text-xs text-[var(--text-primary)]/40 hover:text-red-600 hover:underline">
                        <Archive size={12} /> Dispose
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b border-[var(--border)] flex justify-between items-center">
              <h2 className="text-xl font-bold text-[var(--text-primary)]">Register Fixed Asset</h2>
              <button onClick={() => setModalOpen(false)} className="text-[var(--text-primary)]/40 hover:text-[var(--text-primary)] text-xl">✕</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Asset Name</label>
                  <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Office Laptop"
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Asset Code (optional)</label>
                  <input value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))} placeholder="e.g. FA-001"
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
                  Parent asset <span className="font-normal normal-case">(optional — component)</span>
                </label>
                <select value={form.parent_id} onChange={e => setForm(f => ({ ...f, parent_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
                  <option value="">— standalone asset —</option>
                  {parentOptions.map(p => (
                    <option key={p.id} value={p.id}>{p.code ? `${p.code} — ` : ""}{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Asset GL Account</label>
                <select value={form.asset_account_id} onChange={e => setForm(f => ({ ...f, asset_account_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
                  <option value="">Select account…</option>
                  {accountOptions}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Accumulated Depreciation Account (1090)</label>
                <select value={form.accum_depr_account_id} onChange={e => setForm(f => ({ ...f, accum_depr_account_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
                  <option value="">Select account…</option>
                  {accountOptions}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Depreciation Expense Account (5050)</label>
                <select value={form.depr_expense_account_id} onChange={e => setForm(f => ({ ...f, depr_expense_account_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
                  <option value="">Select account…</option>
                  {accountOptions}
                </select>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Acquisition Date</label>
                  <input type="date" value={form.acquisition_date} onChange={e => setForm(f => ({ ...f, acquisition_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Acquisition Cost</label>
                  <input type="number" min="0" value={form.acquisition_cost} onChange={e => setForm(f => ({ ...f, acquisition_cost: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Salvage Value</label>
                  <input type="number" min="0" value={form.salvage_value} onChange={e => setForm(f => ({ ...f, salvage_value: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Useful Life (months)</label>
                  <input type="number" min="1" value={form.useful_life_months} onChange={e => setForm(f => ({ ...f, useful_life_months: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Method</label>
                  <select value={form.method} onChange={e => setForm(f => ({ ...f, method: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
                    <option value="straight_line">Straight Line</option>
                    <option value="reducing_balance">Reducing Balance</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
                  Funded By <span className="font-normal normal-case">(optional — posts acquisition JV)</span>
                </label>
                <select
                  value={form.funding_account_id ?? ""}
                  onChange={e => setForm(f => ({ ...f, funding_account_id: e.target.value || null }))}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
                >
                  <option value="">— no GL entry —</option>
                  {accountOptions}
                </select>
              </div>
              {formError && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{formError}</p>}
              <button onClick={handleSave} disabled={saving}
                className="w-full py-3 bg-[var(--text-primary)] text-white rounded-xl font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50">
                {saving ? "Registering…" : "Register Asset"}
              </button>
            </div>
          </div>
        </div>
      )}

      {disposeTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl">
            <div className="p-5 border-b border-[var(--border)] flex justify-between items-center">
              <h2 className="text-lg font-bold text-[var(--text-primary)]">Dispose — {disposeTarget.name}</h2>
              <button onClick={() => setDisposeTarget(null)} className="text-[var(--text-primary)]/40 hover:text-[var(--text-primary)] text-xl">✕</button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Mode</label>
                <div className="flex gap-2">
                  {(["sale", "scrap"] as const).map(m => (
                    <button key={m} type="button"
                      onClick={() => setDisposeForm(f => ({ ...f, mode: m }))}
                      className={`flex-1 py-2 rounded-xl text-sm font-bold capitalize border transition-colors ${
                        disposeForm.mode === m
                          ? "bg-[var(--text-primary)] text-white border-[var(--text-primary)]"
                          : "border-[var(--border)] text-[var(--text-primary)]/70 hover:bg-[var(--bg-page)]"
                      }`}
                    >{m}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Disposal date</label>
                <input type="date" value={disposeForm.disposal_date}
                  onChange={e => setDisposeForm(f => ({ ...f, disposal_date: e.target.value }))}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
              </div>
              {disposeForm.mode === "sale" && (
                <>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Proceeds</label>
                    <input type="number" min="0" value={disposeForm.proceeds}
                      onChange={e => setDisposeForm(f => ({ ...f, proceeds: e.target.value }))}
                      className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Proceeds account (cash/bank)</label>
                    <select value={disposeForm.proceeds_account_id}
                      onChange={e => setDisposeForm(f => ({ ...f, proceeds_account_id: e.target.value }))}
                      className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
                      <option value="">Select account…</option>
                      {cashBankAccounts.map(a => (
                        <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                      ))}
                    </select>
                  </div>
                </>
              )}
              {disposeError && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{disposeError}</p>}
              <button onClick={submitDispose} disabled={disposeBusy}
                className="w-full py-3 bg-red-700 text-white rounded-xl font-bold hover:bg-red-800 transition-all disabled:opacity-50">
                {disposeBusy ? "Disposing…" : "Confirm Dispose"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
