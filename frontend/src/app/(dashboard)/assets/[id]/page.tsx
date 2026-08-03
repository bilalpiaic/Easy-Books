"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { Building2, Printer, AlertCircle, CheckCircle, TrendingDown, RotateCcw, Archive } from "lucide-react"
import { useBreadcrumb } from "@/context/BreadcrumbContext"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import DocLink from "@/components/DocLink"
import { fmtDate, todayLocal } from "@/lib/utils"
import { useTranslation } from "react-i18next"
import { useMessages } from "@/context/MessageContext"

interface DepreciationEntry {
  id: number
  depreciation_date: string
  depreciation_amount: number
  transaction_id: number
}

interface ImpairmentEntry {
  id: number
  impairment_date: string
  recoverable_amount: number
  carrying_before: number
  amount: number
  notes: string | null
  transaction_id: number
}

interface ComponentAsset {
  id: number
  name: string
  code: string | null
  book_value: number
  is_disposed: boolean
}

interface AssetDetail {
  id: number
  name: string
  code: string | null
  parent_id: number | null
  acquisition_date: string
  acquisition_cost: number
  salvage_value: number
  useful_life_months: number
  method: string
  accumulated_depreciation: number
  accum_impairment: number
  book_value: number
  is_disposed: boolean
  disposal_date: string | null
  disposal_proceeds: number
  depreciation_entries: DepreciationEntry[]
  impairments: ImpairmentEntry[]
  components: ComponentAsset[]
}

interface Account { id: number; code: string; name: string; type?: string }

function isCashOrBank(a: Account) {
  const name = (a.name ?? "").toLowerCase()
  return (
    a.type === "Asset" &&
    (name.includes("cash") || name.includes("bank") ||
      a.code.startsWith("100") || a.code.startsWith("101"))
  ) || a.code === "1010" || a.code === "1000" || /bank|cash/i.test(a.name)
}

type ModalKind = "impair" | "reverse" | "dispose" | null

export default function FixedAssetRegisterPage({ params }: { params: Promise<{ id: string }> }) {
  const { confirm, toast } = useMessages()
  const { t } = useTranslation()

  const { id } = use(params)
  const fmt = useFmt()
  const [asset, setAsset] = useState<AssetDetail | null>(null)
  const [parentName, setParentName] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [deprDate, setDeprDate] = useState(todayLocal)
  const [busy, setBusy] = useState(false)
  const [actionMsg, setActionMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [modal, setModal] = useState<ModalKind>(null)
  const [impairRecoverable, setImpairRecoverable] = useState("")
  const [impairDate, setImpairDate] = useState(todayLocal)
  const [impairNotes, setImpairNotes] = useState("")
  const [reverseAmount, setReverseAmount] = useState("")
  const [reverseDate, setReverseDate] = useState(todayLocal)
  const [reverseNotes, setReverseNotes] = useState("")
  const [disposeDate, setDisposeDate] = useState(todayLocal)
  const [disposeMode, setDisposeMode] = useState<"sale" | "scrap">("sale")
  const [disposeProceeds, setDisposeProceeds] = useState("0")
  const [disposeAccountId, setDisposeAccountId] = useState("")
  const [cashBankAccounts, setCashBankAccounts] = useState<Account[]>([])
  const [modalError, setModalError] = useState("")
  useBreadcrumb(asset ? asset.name : undefined)

  const reload = () =>
    apiFetch<AssetDetail>(`/api/assets/${id}`)
      .then(d => {
        setAsset({
          ...d,
          accum_impairment: d.accum_impairment ?? 0,
          impairments: d.impairments ?? [],
          components: d.components ?? [],
        })
      }).catch(() => {})

  useEffect(() => {
    apiFetch<AssetDetail>(`/api/assets/${id}`)
      .then(d => {
        setAsset({
          ...d,
          accum_impairment: d.accum_impairment ?? 0,
          impairments: d.impairments ?? [],
          components: d.components ?? [],
        })
        setLoading(false)
        if (d.parent_id) {
          apiFetch<{ name: string }>(`/api/assets/${d.parent_id}`)
            .then(p => setParentName(p.name))
            .catch(() => setParentName(`#${d.parent_id}`))
        }
      })
      .catch(() => setLoading(false))
  }, [id])

  const openModal = async (kind: ModalKind) => {
    setModalError("")
    setModal(kind)
    if (kind === "dispose") {
      try {
        const coa = await apiFetch<{ items: Account[] }>("/api/accounts?limit=300")
        setCashBankAccounts((coa.items ?? []).filter(isCashOrBank))
      } catch { /* ignore */ }
    }
  }

  const runDepreciate = async () => {
    if (!asset) return
    setBusy(true); setActionMsg(null)
    try {
      const res = await apiFetch<{ jv_number?: string; depreciation_amount: number; message?: string }>(
        `/api/assets/${id}/depreciate`,
        { method: "POST", body: JSON.stringify({ depreciation_date: deprDate }) },
      )
      if (res.message) {
        setActionMsg({ ok: false, text: res.message })
      } else {
        setActionMsg({ ok: true, text: `Posted ${fmt(res.depreciation_amount)} depreciation — ${res.jv_number}` })
        toast(`Depreciation posted: ${fmt(res.depreciation_amount)}`, "success")
        await reload()
      }
    } catch (e) {
      setActionMsg({ ok: false, text: e instanceof Error ? e.message : "Depreciation failed" })
    } finally { setBusy(false) }
  }

  const submitImpair = async () => {
    const recoverable = parseFloat(impairRecoverable)
    if (Number.isNaN(recoverable) || recoverable < 0) {
      setModalError("Enter a valid recoverable amount"); return
    }
    setBusy(true); setModalError("")
    try {
      await apiFetch(`/api/assets/${id}/impair`, {
        method: "POST",
        body: JSON.stringify({
          recoverable_amount: recoverable,
          impairment_date: impairDate,
          notes: impairNotes.trim() || null,
        }),
      })
      toast("Impairment posted", "success")
      setModal(null)
      setImpairRecoverable(""); setImpairNotes("")
      await reload()
    } catch (e) {
      setModalError(e instanceof Error ? e.message : "Impairment failed")
    } finally { setBusy(false) }
  }

  const submitReverse = async () => {
    const amount = parseFloat(reverseAmount)
    if (Number.isNaN(amount) || amount <= 0) {
      setModalError("Enter a positive reversal amount"); return
    }
    setBusy(true); setModalError("")
    try {
      await apiFetch(`/api/assets/${id}/impair-reverse`, {
        method: "POST",
        body: JSON.stringify({
          amount,
          impairment_date: reverseDate,
          notes: reverseNotes.trim() || null,
        }),
      })
      toast("Impairment reversed", "success")
      setModal(null)
      setReverseAmount(""); setReverseNotes("")
      await reload()
    } catch (e) {
      setModalError(e instanceof Error ? e.message : "Reversal failed")
    } finally { setBusy(false) }
  }

  const submitDispose = async () => {
    if (!asset) return
    if (disposeMode === "sale" && !disposeAccountId) {
      setModalError("Select a proceeds (cash/bank) account for sale"); return
    }
    const ok = await confirm({
      title: `Dispose "${asset.name}"?`,
      message: disposeMode === "sale"
        ? "Posts sale proceeds and derecognises the asset. This cannot be undone."
        : "Scrap disposal derecognises the asset with no proceeds. This cannot be undone.",
      confirmLabel: "Dispose",
      danger: true,
    })
    if (!ok) return
    setBusy(true); setModalError("")
    try {
      await apiFetch(`/api/assets/${id}/dispose`, {
        method: "PATCH",
        body: JSON.stringify({
          disposal_date: disposeDate,
          proceeds: parseFloat(disposeProceeds) || 0,
          mode: disposeMode,
          proceeds_account_id: disposeMode === "sale" && disposeAccountId
            ? parseInt(disposeAccountId)
            : null,
        }),
      })
      toast("Asset disposed", "success")
      setModal(null)
      setActionMsg({ ok: true, text: "Asset marked as disposed." })
      await reload()
    } catch (e) {
      setModalError(e instanceof Error ? e.message : "Dispose failed")
    } finally { setBusy(false) }
  }

  if (loading) return <div className="text-center py-20 text-[var(--text-primary)]/50">Loading…</div>
  if (!asset) return <div className="text-center py-20 text-[var(--text-primary)]/50">Asset not found.</div>

  const entries = [...(asset.depreciation_entries ?? [])].sort((a, b) =>
    a.depreciation_date.localeCompare(b.depreciation_date))
  let runningAccum = 0
  const rows = entries.map(e => {
    runningAccum += e.depreciation_amount
    return {
      ...e,
      accumulated: runningAccum,
      book: asset.acquisition_cost - runningAccum - (asset.accum_impairment ?? 0),
    }
  })

  const impairments = [...(asset.impairments ?? [])].sort((a, b) =>
    a.impairment_date.localeCompare(b.impairment_date))

  return (
    <div className="max-w-4xl mx-auto space-y-6">

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--text-primary)] flex items-center justify-center flex-shrink-0">
            <Building2 className="w-5 h-5 text-[#ffd966]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">{asset.name}</h1>
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mt-0.5">
              Fixed Asset Register{asset.code ? ` · ${asset.code}` : ""}
              {asset.is_disposed ? " · DISPOSED" : ""}
            </p>
            {asset.parent_id && (
              <p className="text-sm text-[var(--text-primary)]/60 mt-1">
                Component of{" "}
                <Link href={`/assets/${asset.parent_id}`} className="text-[var(--primary)] hover:underline font-medium">
                  {parentName ?? `Asset #${asset.parent_id}`}
                </Link>
              </p>
            )}
          </div>
        </div>
        <button onClick={() => window.print()} className="p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] text-[var(--text-primary)]/60 print:hidden" title="Print">
          <Printer className="w-5 h-5" />
        </button>
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          ["Acquisition Cost", fmt(asset.acquisition_cost)],
          ["Accumulated Depreciation", `(${fmt(asset.accumulated_depreciation)})`],
          ["Accum. Impairment", (asset.accum_impairment ?? 0) > 0 ? `(${fmt(asset.accum_impairment)})` : "—"],
          ["Net Book Value", fmt(asset.book_value)],
          ["Method / Life", `${asset.method.replace("_", " ")} · ${asset.useful_life_months}m`],
          ["Acquired", fmtDate(asset.acquisition_date)],
        ].map(([label, val]) => (
          <div key={label} className="bg-white border border-[var(--border)] rounded-xl px-4 py-3">
            <p className="text-[10px] uppercase tracking-widest text-[var(--text-primary)]/50">{label}</p>
            <p className="font-mono text-sm mt-1 text-[var(--text-primary)]">{val}</p>
          </div>
        ))}
      </div>

      {/* Components */}
      {(asset.components?.length ?? 0) > 0 && (
        <div className="bg-white rounded-2xl border border-[var(--text-primary)]/5 overflow-hidden">
          <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--bg-page)]">
            <h2 className="text-sm font-bold text-[var(--text-primary)]">Components</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)]/50">
              <tr>
                {["Name", "Code", "NBV", "Status"].map(h => (
                  <th key={h} className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {asset.components.map(c => (
                <tr key={c.id} className="border-t border-[var(--text-primary)]/5 hover:bg-[var(--bg-page)]/40">
                  <td className="px-4 py-2">
                    <DocLink type="fixed_asset" id={c.id} label={c.name} className="font-medium" />
                  </td>
                  <td className="px-4 py-2 text-[var(--text-primary)]/50 text-xs">{c.code ?? "—"}</td>
                  <td className="px-4 py-2 font-mono">{fmt(c.book_value)}</td>
                  <td className="px-4 py-2 text-xs uppercase tracking-wide text-[var(--text-primary)]/50">
                    {c.is_disposed ? "Disposed" : "Active"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Actions */}
      {!asset.is_disposed && (
        <div className="bg-white border border-[var(--border)] rounded-2xl p-5 print:hidden space-y-4">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/60">{t("col.actions", "Actions")}</h2>

          {actionMsg && (
            <div className={`flex items-start gap-2 p-3 rounded-xl text-sm ${
              actionMsg.ok
                ? "bg-emerald-50 border border-emerald-200 text-emerald-800"
                : "bg-amber-50 border border-amber-200 text-amber-800"
            }`}>
              {actionMsg.ok
                ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                : <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              }
              {actionMsg.text}
            </div>
          )}

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Depreciation date</label>
              <input
                type="date"
                value={deprDate}
                onChange={e => setDeprDate(e.target.value)}
                className="ui-field bg-[var(--bg-page)] rounded-xl text-sm"
              />
            </div>
            <button
              onClick={runDepreciate}
              disabled={busy}
              className="px-5 py-2.5 bg-[var(--text-primary)] text-white rounded-xl text-sm font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50"
            >
              {busy ? "Working…" : "Post Depreciation"}
            </button>
            <button
              onClick={() => openModal("impair")}
              disabled={busy}
              className="flex items-center gap-1.5 px-5 py-2.5 border border-amber-300 text-amber-800 rounded-xl text-sm font-bold hover:bg-amber-50 transition-colors disabled:opacity-50"
            >
              <TrendingDown className="w-4 h-4" /> Impair
            </button>
            {(asset.accum_impairment ?? 0) > 0 && (
              <button
                onClick={() => openModal("reverse")}
                disabled={busy}
                className="flex items-center gap-1.5 px-5 py-2.5 border border-[var(--border)] text-[var(--text-primary)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-50"
              >
                <RotateCcw className="w-4 h-4" /> Reverse Impairment
              </button>
            )}
            <button
              onClick={() => openModal("dispose")}
              disabled={busy}
              className="flex items-center gap-1.5 px-5 py-2.5 border border-red-200 text-red-700 rounded-xl text-sm font-bold hover:bg-red-50 transition-colors disabled:opacity-50"
            >
              <Archive className="w-4 h-4" /> Dispose Asset
            </button>
          </div>
        </div>
      )}

      {asset.is_disposed && asset.disposal_date && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-900">
          Disposed on {fmtDate(asset.disposal_date)}
          {(asset.disposal_proceeds ?? 0) > 0 ? ` · proceeds ${fmt(asset.disposal_proceeds)}` : " · scrap"}
        </div>
      )}

      {/* Impairment history */}
      <div className="bg-white rounded-2xl border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--bg-page)]">
          <h2 className="text-sm font-bold text-[var(--text-primary)]">Impairment History</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)]/50">
            <tr>
              {["Date", "JV", "Type", "Amount", "Recoverable", "Carrying before", "Notes"].map(h => (
                <th key={h} className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {impairments.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-[var(--text-primary)]/40 italic">No impairments recorded.</td></tr>
            ) : impairments.map(r => (
              <tr key={r.id} className="border-t border-[var(--text-primary)]/5 hover:bg-[var(--bg-page)]/40">
                <td className="px-4 py-2 whitespace-nowrap text-[var(--text-primary)]/70">{fmtDate(r.impairment_date)}</td>
                <td className="px-4 py-2 font-mono text-xs">
                  <DocLink type="jv" id={r.transaction_id} label={`JV-${String(r.transaction_id).padStart(5, "0")}`} />
                </td>
                <td className="px-4 py-2 text-xs uppercase tracking-wide">
                  {r.amount >= 0 ? (
                    <span className="text-red-600">Loss</span>
                  ) : (
                    <span className="text-emerald-700">Reversal</span>
                  )}
                </td>
                <td className="px-4 py-2 font-mono">{fmt(Math.abs(r.amount))}</td>
                <td className="px-4 py-2 font-mono">{fmt(r.recoverable_amount)}</td>
                <td className="px-4 py-2 font-mono">{fmt(r.carrying_before)}</td>
                <td className="px-4 py-2 text-[var(--text-primary)]/60 text-xs">{r.notes ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Depreciation schedule */}
      <div className="bg-white rounded-2xl border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--bg-page)]">
          <h2 className="text-sm font-bold text-[var(--text-primary)]">Depreciation Schedule</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)]/50">
            <tr>
              {["Date", "JV", "Charge", "Accumulated", "Book Value"].map(h => (
                <th key={h} className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-[var(--text-primary)]/5">
              <td className="px-4 py-2 whitespace-nowrap text-[var(--text-primary)]/70">{fmtDate(asset.acquisition_date)}</td>
              <td className="px-4 py-2 text-[var(--text-primary)]/40 italic">acquisition</td>
              <td className="px-4 py-2 font-mono">{fmt(asset.acquisition_cost)}</td>
              <td className="px-4 py-2 font-mono">—</td>
              <td className="px-4 py-2 font-mono">{fmt(asset.acquisition_cost)}</td>
            </tr>
            {rows.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-[var(--text-primary)]/40 italic">No depreciation posted yet.</td></tr>
            ) : rows.map(r => (
              <tr key={r.id} className="border-t border-[var(--text-primary)]/5 hover:bg-[var(--bg-page)]/40">
                <td className="px-4 py-2 whitespace-nowrap text-[var(--text-primary)]/70">{fmtDate(r.depreciation_date)}</td>
                <td className="px-4 py-2 font-mono text-xs">
                  <DocLink type="jv" id={r.transaction_id} label={`JV-${String(r.transaction_id).padStart(5, "0")}`} />
                </td>
                <td className="px-4 py-2 font-mono text-red-500">({fmt(r.depreciation_amount)})</td>
                <td className="px-4 py-2 font-mono text-[var(--text-primary)]/60">({fmt(r.accumulated)})</td>
                <td className="px-4 py-2 font-mono font-bold">{fmt(r.book)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modals */}
      {modal === "impair" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl">
            <div className="p-5 border-b border-[var(--border)] flex justify-between items-center">
              <h2 className="text-lg font-bold text-[var(--text-primary)]">Record Impairment</h2>
              <button onClick={() => setModal(null)} className="text-[var(--text-primary)]/40 hover:text-[var(--text-primary)] text-xl">✕</button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-xs text-[var(--text-primary)]/50">
                Current NBV {fmt(asset.book_value)}. Loss = max(0, NBV − recoverable amount).
              </p>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Recoverable amount</label>
                <input type="number" min="0" value={impairRecoverable}
                  onChange={e => setImpairRecoverable(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Date</label>
                <input type="date" value={impairDate} onChange={e => setImpairDate(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Notes (optional)</label>
                <input value={impairNotes} onChange={e => setImpairNotes(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
              </div>
              {modalError && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{modalError}</p>}
              <button onClick={submitImpair} disabled={busy}
                className="w-full py-3 bg-[var(--text-primary)] text-white rounded-xl font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50">
                {busy ? "Posting…" : "Post Impairment"}
              </button>
            </div>
          </div>
        </div>
      )}

      {modal === "reverse" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl">
            <div className="p-5 border-b border-[var(--border)] flex justify-between items-center">
              <h2 className="text-lg font-bold text-[var(--text-primary)]">Reverse Impairment</h2>
              <button onClick={() => setModal(null)} className="text-[var(--text-primary)]/40 hover:text-[var(--text-primary)] text-xl">✕</button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-xs text-[var(--text-primary)]/50">
                Accumulated impairment {fmt(asset.accum_impairment)}. Reversal cannot exceed this balance.
              </p>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Amount</label>
                <input type="number" min="0" value={reverseAmount}
                  onChange={e => setReverseAmount(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Date</label>
                <input type="date" value={reverseDate} onChange={e => setReverseDate(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Notes (optional)</label>
                <input value={reverseNotes} onChange={e => setReverseNotes(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
              </div>
              {modalError && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{modalError}</p>}
              <button onClick={submitReverse} disabled={busy}
                className="w-full py-3 bg-[var(--text-primary)] text-white rounded-xl font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50">
                {busy ? "Posting…" : "Post Reversal"}
              </button>
            </div>
          </div>
        </div>
      )}

      {modal === "dispose" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl">
            <div className="p-5 border-b border-[var(--border)] flex justify-between items-center">
              <h2 className="text-lg font-bold text-[var(--text-primary)]">Dispose Asset</h2>
              <button onClick={() => setModal(null)} className="text-[var(--text-primary)]/40 hover:text-[var(--text-primary)] text-xl">✕</button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Mode</label>
                <div className="flex gap-2">
                  {(["sale", "scrap"] as const).map(m => (
                    <button key={m} type="button"
                      onClick={() => setDisposeMode(m)}
                      className={`flex-1 py-2 rounded-xl text-sm font-bold capitalize border transition-colors ${
                        disposeMode === m
                          ? "bg-[var(--text-primary)] text-white border-[var(--text-primary)]"
                          : "border-[var(--border)] text-[var(--text-primary)]/70 hover:bg-[var(--bg-page)]"
                      }`}
                    >{m}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Disposal date</label>
                <input type="date" value={disposeDate} onChange={e => setDisposeDate(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
              </div>
              {disposeMode === "sale" && (
                <>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Proceeds</label>
                    <input type="number" min="0" value={disposeProceeds}
                      onChange={e => setDisposeProceeds(e.target.value)}
                      className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm" />
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">Proceeds account (cash/bank)</label>
                    <select value={disposeAccountId} onChange={e => setDisposeAccountId(e.target.value)}
                      className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
                      <option value="">Select account…</option>
                      {cashBankAccounts.map(a => (
                        <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                      ))}
                    </select>
                  </div>
                </>
              )}
              {modalError && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{modalError}</p>}
              <button onClick={submitDispose} disabled={busy}
                className="w-full py-3 bg-red-700 text-white rounded-xl font-bold hover:bg-red-800 transition-all disabled:opacity-50">
                {busy ? "Disposing…" : "Confirm Dispose"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
