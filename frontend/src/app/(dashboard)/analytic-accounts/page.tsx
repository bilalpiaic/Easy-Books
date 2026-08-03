"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus, Pencil, ToggleLeft, ToggleRight, Layers, TrendingUp, Download, Printer, Settings2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"
import type { AnalyticDimension } from "@/components/DimensionPickers"

interface AnalyticAccount {
  id: number
  code: string
  name: string
  type: "cost_center" | "project" | "department"
  dimension_id?: number | null
  is_active: boolean
}

const TYPE_LABELS: Record<string, string> = {
  cost_center: "Cost Center",
  project:     "Project",
  department:  "Department",
}

const TYPE_TONE: Record<string, string> = {
  cost_center: "bg-blue-50 text-blue-800 border-blue-200",
  project:     "bg-violet-50 text-violet-800 border-violet-200",
  department:  "bg-amber-50 text-amber-800 border-amber-200",
}

interface FormState {
  code: string
  name: string
  type: string
  dimension_id: string
}

const emptyForm: FormState = { code: "", name: "", type: "cost_center", dimension_id: "" }

interface DimForm {
  code: string
  name: string
  required: boolean
}

export default function AnalyticAccountsPage() {
  const { t } = useTranslation()

  const [items, setItems]         = useState<AnalyticAccount[]>([])
  const [dimensions, setDimensions] = useState<AnalyticDimension[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [dimModal, setDimModal]   = useState(false)
  const [editing, setEditing]     = useState<AnalyticAccount | null>(null)
  const [form, setForm]           = useState<FormState>(emptyForm)
  const [dimForm, setDimForm]     = useState<DimForm>({ code: "", name: "", required: false })
  const [saving, setSaving]       = useState(false)
  const [formErr, setFormErr]     = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      apiFetch<{ total: number; items: AnalyticAccount[] }>("/api/analytic-accounts?limit=200"),
      apiFetch<{ items: AnalyticDimension[] }>("/api/analytic-dimensions").catch(() => ({ items: [] })),
    ])
      .then(([d, dims]) => {
        setItems(d.items)
        setDimensions(dims.items ?? [])
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

  const dimName = (id: number | null | undefined) =>
    dimensions.find(d => d.id === id)?.name ?? "—"

  const openAdd = () => {
    setEditing(null)
    setForm({
      ...emptyForm,
      dimension_id: dimensions[0] ? String(dimensions[0].id) : "",
    })
    setFormErr(null)
    setModalOpen(true)
  }

  const openEdit = (aa: AnalyticAccount) => {
    setEditing(aa)
    setForm({
      code: aa.code,
      name: aa.name,
      type: aa.type,
      dimension_id: aa.dimension_id ? String(aa.dimension_id) : "",
    })
    setFormErr(null)
    setModalOpen(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.code.trim()) { setFormErr("Code is required"); return }
    if (!form.name.trim()) { setFormErr("Name is required"); return }
    setSaving(true); setFormErr(null)
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        type: form.type,
        dimension_id: form.dimension_id ? parseInt(form.dimension_id) : null,
      }
      if (editing) {
        await apiFetch(`/api/analytic-accounts/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        })
      } else {
        await apiFetch("/api/analytic-accounts", {
          method: "POST",
          body: JSON.stringify({ ...payload, code: form.code }),
        })
      }
      setModalOpen(false)
      load()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Save failed"
      setFormErr(msg.includes("already exists") ? `Code '${form.code}' is already in use` : msg)
    } finally {
      setSaving(false)
    }
  }

  const handleSaveDim = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!dimForm.code.trim() || !dimForm.name.trim()) {
      setFormErr("Code and name are required"); return
    }
    setSaving(true); setFormErr(null)
    try {
      await apiFetch("/api/analytic-dimensions", {
        method: "POST",
        body: JSON.stringify(dimForm),
      })
      setDimModal(false)
      setDimForm({ code: "", name: "", required: false })
      load()
    } catch (err: unknown) {
      setFormErr(err instanceof Error ? err.message : "Failed to create dimension")
    } finally {
      setSaving(false)
    }
  }

  const toggleDimRequired = async (d: AnalyticDimension) => {
    try {
      await apiFetch(`/api/analytic-dimensions/${d.id}`, {
        method: "PUT",
        body: JSON.stringify({ required: !d.required }),
      })
      load()
    } catch {}
  }

  const toggleActive = async (aa: AnalyticAccount) => {
    try {
      await apiFetch(`/api/analytic-accounts/${aa.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !aa.is_active }),
      })
      load()
    } catch {}
  }

  const activeItems   = items.filter(i => i.is_active)
  const inactiveItems = items.filter(i => !i.is_active)

  return (
    <div className="space-y-6">
      <PrintHeader title="Analytic Accounts" />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Analytic Accounts</h1>
          <p className="text-sm text-[var(--text-primary)]/60 mt-0.5">
            Dimension types (up to 3) and their values for segment reporting.
          </p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <Link
            href="/reports/dimensional-pl"
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <TrendingUp className="w-4 h-4" /> Dimensional P&amp;L
          </Link>
          <button
            onClick={() => { setFormErr(null); setDimModal(true) }}
            disabled={dimensions.length >= 3}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Settings2 className="w-4 h-4" /> Dimension
          </button>
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button
            onClick={() => downloadCSV('analytic-accounts.csv', items.map(a => ({
              Code: a.code, Name: a.name,
              Dimension: dimName(a.dimension_id),
              Type: TYPE_LABELS[a.type] ?? a.type,
              Active: a.is_active ? 'Yes' : 'No',
            })))}
            disabled={items.length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
          >
            <Plus className="w-4 h-4" /> New
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {/* Dimensions band */}
      {dimensions.length > 0 && (
        <div className="bg-white border border-[var(--border)] rounded-xl p-4 print:hidden">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]/50 mb-3">
            Dimension types ({dimensions.length}/3)
          </h2>
          <div className="flex flex-wrap gap-3">
            {dimensions.map(d => (
              <div
                key={d.id}
                className="flex items-center gap-3 border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
              >
                <span className="font-mono text-xs text-[var(--text-primary)]/60">{d.code}</span>
                <span className="font-medium">{d.name}</span>
                <span className="text-xs text-[var(--text-primary)]/45">slot {d.sort_order}</span>
                <button
                  type="button"
                  onClick={() => toggleDimRequired(d)}
                  className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                    d.required
                      ? "bg-red-50 text-red-700 border-red-200"
                      : "bg-slate-50 text-slate-600 border-slate-200"
                  }`}
                  title="Toggle required on posting"
                >
                  {d.required ? "Required" : "Optional"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-[var(--text-primary)]/50 py-8 text-center">Loading…</div>
      ) : items.length === 0 ? (
        <div className="bg-white border border-[var(--border)] rounded-xl px-6 py-12 text-center">
          <Layers className="w-10 h-10 text-[var(--primary)]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[var(--text-primary)]">No analytic accounts yet</p>
          <p className="text-xs text-[var(--text-primary)]/55 mt-1 mb-4">
            Create a dimension type, then add values to tag journal entries for segment P&amp;L.
          </p>
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors"
          >
            <Plus className="w-4 h-4" /> Create first account
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <AccountTable
            items={activeItems}
            title={`Active (${activeItems.length})`}
            dimName={dimName}
            onEdit={openEdit}
            onToggle={toggleActive}
          />
          {inactiveItems.length > 0 && (
            <AccountTable
              items={inactiveItems}
              title={`Inactive (${inactiveItems.length})`}
              dimmed
              dimName={dimName}
              onEdit={openEdit}
              onToggle={toggleActive}
            />
          )}
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-[var(--border)]">
              <h2 className="text-lg font-bold text-[var(--text-primary)]">
                {editing ? "Edit Analytic Account" : "New Analytic Account"}
              </h2>
            </div>
            <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Code</label>
                  <input
                    value={form.code}
                    onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                    disabled={!!editing}
                    placeholder="CC-01"
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)] disabled:bg-[#f5f2ed] font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Type</label>
                  <select
                    value={form.type}
                    onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                  >
                    <option value="cost_center">Cost Center</option>
                    <option value="project">Project</option>
                    <option value="department">Department</option>
                  </select>
                </div>
              </div>
              {dimensions.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Dimension</label>
                  <select
                    value={form.dimension_id}
                    onChange={e => setForm(f => ({ ...f, dimension_id: e.target.value }))}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                  >
                    <option value="">— none —</option>
                    {dimensions.map(d => (
                      <option key={d.id} value={d.id}>{d.code} — {d.name}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Name</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Marketing Department"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
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

      {dimModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-[var(--border)]">
              <h2 className="text-lg font-bold text-[var(--text-primary)]">New Dimension Type</h2>
            </div>
            <form onSubmit={handleSaveDim} className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Code</label>
                  <input
                    value={dimForm.code}
                    onChange={e => setDimForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                    placeholder="PROJ"
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[var(--primary)]"
                  />
                </div>
                <div className="flex items-end pb-1">
                  <label className="inline-flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={dimForm.required}
                      onChange={e => setDimForm(f => ({ ...f, required: e.target.checked }))}
                    />
                    Required on posting
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Name</label>
                <input
                  value={dimForm.name}
                  onChange={e => setDimForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Project"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
              {formErr && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{formErr}</p>
              )}
              <div className="flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 bg-[var(--primary)] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Create"}
                </button>
                <button
                  type="button"
                  onClick={() => setDimModal(false)}
                  className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm"
                >{t('common.cancel', 'Cancel')}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function AccountTable({
  items, title, dimmed = false, dimName, onEdit, onToggle,
}: {
  items: AnalyticAccount[]
  title: string
  dimmed?: boolean
  dimName: (id: number | null | undefined) => string
  onEdit: (aa: AnalyticAccount) => void
  onToggle: (aa: AnalyticAccount) => void
}) {
  return (
    <div>
      <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]/50 mb-2">{title}</h2>
      <div className={`bg-white border border-[var(--border)] rounded-xl overflow-hidden ${dimmed ? "opacity-60" : ""}`}>
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[480px]">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[#faf8f4]">
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70 w-28">Code</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">Name</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">Dimension</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]/70">Type</th>
              <th className="px-4 py-3 w-24" />
            </tr>
          </thead>
          <tbody>
            {items.map(aa => (
              <tr key={aa.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[#faf8f4]">
                <td className="px-4 py-3 font-mono text-xs text-[var(--text-primary)]/80">{aa.code}</td>
                <td className="px-4 py-3 text-[var(--text-primary)]">{aa.name}</td>
                <td className="px-4 py-3 text-sm text-[var(--text-primary)]/70">{dimName(aa.dimension_id)}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block border rounded-full px-2.5 py-0.5 text-xs font-medium ${TYPE_TONE[aa.type] ?? "bg-slate-50 text-slate-700 border-slate-200"}`}>
                    {TYPE_LABELS[aa.type] ?? aa.type}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Link
                      href={`/analytic-accounts/${aa.id}`}
                      className="text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors"
                      title="View P&L"
                    >
                      <TrendingUp className="w-3.5 h-3.5" />
                    </Link>
                    <button
                      onClick={() => onEdit(aa)}
                      className="text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors"
                      title="Edit"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => onToggle(aa)}
                      className={`transition-colors ${aa.is_active ? "text-emerald-500 hover:text-red-400" : "text-[var(--text-primary)]/30 hover:text-emerald-500"}`}
                      title={aa.is_active ? "Deactivate" : "Activate"}
                    >
                      {aa.is_active
                        ? <ToggleRight className="w-4 h-4" />
                        : <ToggleLeft  className="w-4 h-4" />
                      }
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  )
}
