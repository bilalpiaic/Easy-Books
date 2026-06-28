"use client"

import { useEffect, useState } from "react"
import { Plus, Pencil, ToggleLeft, ToggleRight, Percent, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface TaxCode {
  id: number
  code: string
  name: string
  rate: number
  type: "output" | "input"
  gl_account_id: number
  is_active: boolean
}

interface Account { id: number; code: string; name: string; type: string }

const TYPE_TONE: Record<string, string> = {
  output: "bg-amber-50 text-amber-800 border-amber-200",
  input:  "bg-blue-50 text-blue-800 border-blue-200",
}

const TYPE_LABELS: Record<string, string> = {
  output: "Output (Sales)",
  input:  "Input (Purchase)",
}

interface FormState {
  code: string
  name: string
  rate: string
  type: string
  gl_account_id: string
}

const emptyForm: FormState = { code: "", name: "", rate: "", type: "output", gl_account_id: "" }

export default function TaxCodesPage() {
  const { t } = useTranslation()

  const [codes, setCodes]         = useState<TaxCode[]>([])
  const [accounts, setAccounts]   = useState<Account[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing]     = useState<TaxCode | null>(null)
  const [form, setForm]           = useState<FormState>(emptyForm)
  const [saving, setSaving]       = useState(false)
  const [formErr, setFormErr]     = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      apiFetch<{ total: number; items: TaxCode[] }>("/api/tax-codes?limit=200"),
      apiFetch<{ total: number; items: Account[] }>("/api/accounts?limit=500"),
    ])
      .then(([tc, ac]) => {
        setCodes(tc.items)
        setAccounts(ac.items.filter(a => !a.type.includes("group")))
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const h = () => openAdd()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openAdd = () => {
    setEditing(null); setForm(emptyForm); setFormErr(null); setModalOpen(true)
  }

  const openEdit = (tc: TaxCode) => {
    setEditing(tc)
    setForm({
      code: tc.code,
      name: tc.name,
      rate: String(tc.rate),
      type: tc.type,
      gl_account_id: String(tc.gl_account_id),
    })
    setFormErr(null); setModalOpen(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.code.trim())        { setFormErr("Code is required"); return }
    if (!form.name.trim())        { setFormErr("Name is required"); return }
    const rate = parseFloat(form.rate)
    if (isNaN(rate) || rate < 0) { setFormErr("Rate must be a non-negative number"); return }
    if (!form.gl_account_id)      { setFormErr("GL account is required"); return }

    setSaving(true); setFormErr(null)
    try {
      if (editing) {
        await apiFetch(`/api/tax-codes/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify({ name: form.name, rate }),
        })
      } else {
        await apiFetch("/api/tax-codes", {
          method: "POST",
          body: JSON.stringify({
            code: form.code.trim().toUpperCase(),
            name: form.name.trim(),
            rate,
            type: form.type,
            gl_account_id: parseInt(form.gl_account_id),
          }),
        })
      }
      setModalOpen(false)
      load()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Save failed"
      setFormErr(msg.includes("already") ? `Code '${form.code}' is already in use` : msg)
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (tc: TaxCode) => {
    try {
      await apiFetch(`/api/tax-codes/${tc.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !tc.is_active }),
      })
      load()
    } catch {}
  }

  // Suggest relevant GL accounts based on type selection
  const suggestedAccounts = accounts.filter(a =>
    form.type === "output" ? a.type === "Liability" : a.type === "Asset"
  )
  const otherAccounts = accounts.filter(a =>
    form.type === "output" ? a.type !== "Liability" : a.type !== "Asset"
  )

  const active   = codes.filter(c => c.is_active)
  const inactive = codes.filter(c => !c.is_active)

  const accountMap: Record<number, Account> = {}
  accounts.forEach(a => { accountMap[a.id] = a })

  return (
    <div className="space-y-6">
      <PrintHeader title="Tax Codes" />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Tax Codes</h1>
          <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
            Catalog of tax rates applied to invoice and bill lines.
          </p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button
            onClick={() => downloadCSV('tax-codes.csv', codes.map(c => ({ Code: c.code, Name: c.name, "Rate (%)": c.rate, Type: c.type, Active: c.is_active ? 'Yes' : 'No' })))}
            disabled={codes.length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
          >
            <Plus className="w-4 h-4" /> New Tax Code
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {loading ? (
        <div className="text-sm text-[var(--text-primary)]/50 py-8 text-center">Loading…</div>
      ) : codes.length === 0 ? (
        <div className="bg-white border border-[var(--border)] rounded-xl px-6 py-12 text-center">
          <Percent className="w-10 h-10 text-[var(--primary)]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[var(--text-primary)]">No tax codes yet</p>
          <p className="text-xs text-[var(--text-primary)]/55 mt-1 mb-4">
            Create tax codes to apply GST, VAT, or withholding tax to invoice and bill lines.
          </p>
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
          >
            <Plus className="w-4 h-4" /> Create first tax code
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <CodeTable
            items={active}
            title={`Active (${active.length})`}
            accountMap={accountMap}
            onEdit={openEdit}
            onToggle={toggleActive}
          />
          {inactive.length > 0 && (
            <CodeTable
              items={inactive}
              title={`Inactive (${inactive.length})`}
              dimmed
              accountMap={accountMap}
              onEdit={openEdit}
              onToggle={toggleActive}
            />
          )}
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-[var(--border)]">
              <h2 className="text-lg font-bold text-[var(--text-primary)]">
                {editing ? "Edit Tax Code" : "New Tax Code"}
              </h2>
            </div>
            <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Code</label>
                  <input
                    value={form.code}
                    onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                    disabled={!!editing}
                    placeholder="GST17"
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)] disabled:bg-[#f5f2ed] font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Type</label>
                  <select
                    value={form.type}
                    onChange={e => setForm(f => ({ ...f, type: e.target.value, gl_account_id: "" }))}
                    disabled={!!editing}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)] disabled:bg-[#f5f2ed]"
                  >
                    <option value="output">Output (Sales)</option>
                    <option value="input">Input (Purchase)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Name</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Standard GST 17%"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">
                  Rate (%)
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="any"
                    value={form.rate}
                    onChange={e => setForm(f => ({ ...f, rate: e.target.value }))}
                    placeholder="17"
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 pr-8 text-sm focus:outline-none focus:border-[var(--primary)] tabular-nums"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[var(--text-primary)]/40">%</span>
                </div>
              </div>

              {!editing && (
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">
                    GL Account{" "}
                    <span className="font-normal text-[var(--text-primary)]/40 normal-case tracking-normal">
                      ({form.type === "output" ? "Liability — tax payable" : "Asset — tax receivable"})
                    </span>
                  </label>
                  <select
                    value={form.gl_account_id}
                    onChange={e => setForm(f => ({ ...f, gl_account_id: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                  >
                    <option value="">Select account…</option>
                    {suggestedAccounts.length > 0 && (
                      <>
                        <optgroup label={form.type === "output" ? "Liability (recommended)" : "Asset (recommended)"}>
                          {suggestedAccounts.map(a => (
                            <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                          ))}
                        </optgroup>
                      </>
                    )}
                    {otherAccounts.length > 0 && (
                      <optgroup label="Other accounts">
                        {otherAccounts.map(a => (
                          <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                </div>
              )}

              {formErr && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{formErr}</p>
              )}

              <div className="flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 bg-[var(--primary)] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50 transition-colors"
                >
                  {saving ? "Saving…" : editing ? "Save Changes" : "Create"}
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

function CodeTable({
  items, title, dimmed = false, accountMap, onEdit, onToggle,
}: {
  items: TaxCode[]
  title: string
  dimmed?: boolean
  accountMap: Record<number, Account>
  onEdit: (tc: TaxCode) => void
  onToggle: (tc: TaxCode) => void
}) {
  return (
    <div>
      <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]/50 mb-2">{title}</h2>
      <div className={`bg-white border border-[var(--border)] rounded-xl overflow-hidden ${dimmed ? "opacity-60" : ""}`}>
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[#faf8f4]">
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70 w-24">Code</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">Name</th>
              <th className="text-right px-4 py-3 font-semibold text-[var(--text-primary)]/70 w-20">Rate</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70 w-32">Type</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">GL Account</th>
              <th className="px-4 py-3 w-20" />
            </tr>
          </thead>
          <tbody>
            {items.map(tc => {
              const acc = accountMap[tc.gl_account_id]
              return (
                <tr key={tc.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[#faf8f4]">
                  <td className="px-4 py-3 font-mono text-xs text-[var(--text-primary)]/80">{tc.code}</td>
                  <td className="px-4 py-3 text-[var(--text-primary)]">{tc.name}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium">
                    {Number(tc.rate).toFixed(Number(tc.rate) % 1 === 0 ? 0 : 2)}%
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block border rounded-full px-2.5 py-0.5 text-xs font-medium ${TYPE_TONE[tc.type] ?? "bg-slate-50 text-slate-700 border-slate-200"}`}>
                      {TYPE_LABELS[tc.type] ?? tc.type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--text-primary)]/70">
                    {acc ? `${acc.code} — ${acc.name}` : `#${tc.gl_account_id}`}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => onEdit(tc)}
                        className="text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors"
                        title="Edit name / rate"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => onToggle(tc)}
                        className={`transition-colors ${tc.is_active ? "text-emerald-500 hover:text-red-400" : "text-[var(--text-primary)]/30 hover:text-emerald-500"}`}
                        title={tc.is_active ? "Deactivate" : "Activate"}
                      >
                        {tc.is_active
                          ? <ToggleRight className="w-4 h-4" />
                          : <ToggleLeft  className="w-4 h-4" />}
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  )
}
