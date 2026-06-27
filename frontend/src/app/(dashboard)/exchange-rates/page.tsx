"use client"

import { useEffect, useState } from "react"
import { Plus, Trash2, TrendingUp, RefreshCw, CheckCircle, AlertCircle, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useSettings } from "@/context/SettingsContext"
import { downloadCSV, fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface ExchangeRate {
  id: number
  date: string
  from_currency: string
  to_currency: string
  rate: number
}

interface FormState {
  date: string
  from_currency: string
  to_currency: string
  rate: string
}

const today = () => new Date().toISOString().slice(0, 10)

const emptyForm = (): FormState => ({
  date: today(),
  from_currency: "",
  to_currency: "",
  rate: "",
})

export default function ExchangeRatesPage() {
  const { t } = useTranslation()

  const { settings }          = useSettings()
  const baseCurrency          = settings.currency || "PKR"

  const [rates, setRates]         = useState<ExchangeRate[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm]           = useState<FormState>(emptyForm)
  const [saving, setSaving]       = useState(false)
  const [formErr, setFormErr]     = useState<string | null>(null)
  const [filterFrom, setFilterFrom] = useState("")
  const [filterTo, setFilterTo]   = useState("")

  const load = (from = filterFrom, to = filterTo) => {
    setLoading(true)
    const params = new URLSearchParams({ limit: "200" })
    if (from) params.set("from_currency", from)
    if (to)   params.set("to_currency",   to)
    apiFetch<{ total: number; items: ExchangeRate[] }>(`/api/exchange-rates?${params}`)
      .then(d => setRates(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const openAdd = () => {
    setForm({ ...emptyForm(), from_currency: baseCurrency })
    setFormErr(null)
    setModalOpen(true)
  }

  useEffect(() => {
    const h = () => openAdd()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseCurrency])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.date)          { setFormErr("Date is required"); return }
    if (!form.from_currency.trim()) { setFormErr("From currency is required"); return }
    if (!form.to_currency.trim())   { setFormErr("To currency is required"); return }
    const rate = parseFloat(form.rate)
    if (!form.rate || isNaN(rate) || rate <= 0) { setFormErr("Rate must be a positive number"); return }
    if (form.from_currency.trim().toUpperCase() === form.to_currency.trim().toUpperCase()) {
      setFormErr("From and To currencies must differ")
      return
    }

    setSaving(true); setFormErr(null)
    try {
      await apiFetch("/api/exchange-rates", {
        method: "POST",
        body: JSON.stringify({
          date: form.date,
          from_currency: form.from_currency.trim().toUpperCase(),
          to_currency:   form.to_currency.trim().toUpperCase(),
          rate,
        }),
      })
      setModalOpen(false)
      load()
    } catch (e) {
      setFormErr(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this rate?")) return
    try {
      await apiFetch(`/api/exchange-rates/${id}`, { method: "DELETE" })
      setRates(prev => prev.filter(r => r.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed")
    }
  }

  const applyFilter = () => load(filterFrom.toUpperCase(), filterTo.toUpperCase())

  // ── FX Revaluation ─────────────────────────────────────────────────────────
  const [revalDate, setRevalDate]   = useState(today)
  const [revalBusy, setRevalBusy]   = useState(false)
  const [revalMsg, setRevalMsg]     = useState<{ ok: boolean; text: string } | null>(null)

  const runRevaluation = async () => {
    setRevalBusy(true); setRevalMsg(null)
    try {
      const res = await apiFetch<{ jv_number?: string; entries_count: number; message?: string }>(
        `/api/reports/fx-revaluation?revaluation_date=${revalDate}`,
        { method: "POST" },
      )
      if (res.message) {
        setRevalMsg({ ok: false, text: res.message })
      } else {
        setRevalMsg({
          ok: true,
          text: `Posted ${res.entries_count} GL line${res.entries_count !== 1 ? "s" : ""} — ${res.jv_number}`,
        })
      }
    } catch (e) {
      setRevalMsg({ ok: false, text: e instanceof Error ? e.message : "Revaluation failed" })
    } finally { setRevalBusy(false) }
  }

  // Unique currency pairs for quick-filter chips
  const pairs = Array.from(
    new Set(rates.map(r => `${r.from_currency}/${r.to_currency}`))
  ).sort()

  return (
    <div className="space-y-6">
      <PrintHeader title="Exchange Rates" />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Exchange Rates</h1>
          <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
            Historical FX rates used for multi-currency transactions.
          </p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button
            onClick={() => downloadCSV('exchange-rates.csv', rates.map(r => ({ Date: r.date, From: r.from_currency, To: r.to_currency, Rate: r.rate })))}
            disabled={rates.length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
          >
            <Plus className="w-4 h-4" /> Add Rate
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {/* FX Revaluation */}
      <div className="bg-white border border-[var(--border)] rounded-2xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <RefreshCw className="w-4 h-4 text-[var(--primary)]" />
          <h2 className="text-sm font-bold text-[var(--text-primary)]">FX Revaluation <span className="text-[var(--text-primary)]/40 font-normal">(IAS 21)</span></h2>
        </div>
        <p className="text-xs text-[var(--text-primary)]/60">
          Restates open foreign-currency AR balances to the closing rate on the chosen date.
          Posts an Unrealised FX Gain/Loss entry (account 4901) for the difference.
        </p>
        {revalMsg && (
          <div className={`flex items-start gap-2 p-3 rounded-xl text-sm ${
            revalMsg.ok
              ? "bg-emerald-50 border border-emerald-200 text-emerald-800"
              : "bg-amber-50 border border-amber-200 text-amber-800"
          }`}>
            {revalMsg.ok
              ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
              : <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            }
            {revalMsg.text}
          </div>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/60 mb-1">Revaluation date</label>
            <input
              type="date"
              value={revalDate}
              onChange={e => setRevalDate(e.target.value)}
              className="border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
            />
          </div>
          <button
            onClick={runRevaluation}
            disabled={revalBusy}
            className="flex items-center gap-2 px-5 py-2 bg-[var(--text-primary)] text-white rounded-xl text-sm font-bold hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${revalBusy ? "animate-spin" : ""}`} />
            {revalBusy ? "Running…" : "Run Revaluation"}
          </button>
        </div>
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={filterFrom}
          onChange={e => setFilterFrom(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === "Enter" && applyFilter()}
          placeholder="From (e.g. USD)"
          className="border border-[#d4cfc7] rounded-lg px-3 py-1.5 text-sm w-32 focus:outline-none focus:border-[var(--primary)] font-mono uppercase"
        />
        <span className="text-[var(--text-primary)]/40 text-sm">→</span>
        <input
          value={filterTo}
          onChange={e => setFilterTo(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === "Enter" && applyFilter()}
          placeholder="To (e.g. PKR)"
          className="border border-[#d4cfc7] rounded-lg px-3 py-1.5 text-sm w-32 focus:outline-none focus:border-[var(--primary)] font-mono uppercase"
        />
        <button
          onClick={applyFilter}
          className="px-3 py-1.5 border border-[#d4cfc7] rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors"
        >
          Filter
        </button>
        {(filterFrom || filterTo) && (
          <button
            onClick={() => { setFilterFrom(""); setFilterTo(""); load("", "") }}
            className="text-xs text-[var(--primary)] hover:underline"
          >
            Clear
          </button>
        )}
        {pairs.length > 0 && pairs.slice(0, 6).map(p => {
          const [f, t] = p.split("/")
          return (
            <button
              key={p}
              onClick={() => { setFilterFrom(f); setFilterTo(t); load(f, t) }}
              className="text-xs border border-[#d4cfc7] rounded-full px-2.5 py-1 hover:border-[var(--primary)]/60 transition-colors font-mono"
            >
              {p}
            </button>
          )
        })}
      </div>

      {loading ? (
        <div className="text-sm text-[var(--text-primary)]/50 py-8 text-center">Loading…</div>
      ) : rates.length === 0 ? (
        <div className="bg-white border border-[var(--border)] rounded-xl px-6 py-12 text-center">
          <TrendingUp className="w-10 h-10 text-[var(--primary)]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[var(--text-primary)]">No exchange rates yet</p>
          <p className="text-xs text-[var(--text-primary)]/55 mt-1 mb-4">
            Add FX rates to support multi-currency invoicing and reporting.
          </p>
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
          >
            <Plus className="w-4 h-4" /> Add first rate
          </button>
        </div>
      ) : (
        <div className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[#faf8f4]">
                <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">Date</th>
                <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">From</th>
                <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">To</th>
                <th className="text-right px-4 py-3 font-semibold text-[var(--text-primary)]/70">Rate</th>
                <th className="text-right px-4 py-3 font-semibold text-[var(--text-primary)]/70">Inverse</th>
                <th className="px-4 py-3 w-10" />
              </tr>
            </thead>
            <tbody>
              {rates.map(r => (
                <tr key={r.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[#faf8f4]">
                  <td className="px-4 py-2.5 text-[var(--text-primary)]/80">{fmtDate(r.date)}</td>
                  <td className="px-4 py-2.5 font-mono text-[var(--text-primary)] font-medium">{r.from_currency}</td>
                  <td className="px-4 py-2.5 font-mono text-[var(--text-primary)] font-medium">{r.to_currency}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{Number(r.rate).toFixed(6)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-[var(--text-primary)]/55 text-xs">
                    {r.rate > 0 ? (1 / r.rate).toFixed(6) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={() => handleDelete(r.id)}
                      className="text-[var(--text-primary)]/30 hover:text-red-500 transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
            <div className="px-6 py-4 border-b border-[var(--border)]">
              <h2 className="text-lg font-bold text-[var(--text-primary)]">Add Exchange Rate</h2>
              <p className="text-xs text-[var(--text-primary)]/55 mt-0.5">Submitting an existing date+pair updates the rate.</p>
            </div>
            <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Date</label>
                <input
                  type="date"
                  value={form.date}
                  onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">From</label>
                  <input
                    value={form.from_currency}
                    onChange={e => setForm(f => ({ ...f, from_currency: e.target.value.toUpperCase() }))}
                    placeholder="USD"
                    maxLength={10}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)] font-mono uppercase"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">To</label>
                  <input
                    value={form.to_currency}
                    onChange={e => setForm(f => ({ ...f, to_currency: e.target.value.toUpperCase() }))}
                    placeholder="PKR"
                    maxLength={10}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)] font-mono uppercase"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">
                  Rate (1 {form.from_currency || "FROM"} = ? {form.to_currency || "TO"})
                </label>
                <input
                  type="number"
                  step="any"
                  min="0.000001"
                  value={form.rate}
                  onChange={e => setForm(f => ({ ...f, rate: e.target.value }))}
                  placeholder="278.500000"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)] tabular-nums"
                />
              </div>

              {formErr && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{formErr}</p>
              )}

              <div className="flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 bg-[var(--primary)] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50 transition-colors"
                >
                  {saving ? "Saving…" : "Save Rate"}
                </button>
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors"
                >{t('common.cancel', 'Cancel')}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
