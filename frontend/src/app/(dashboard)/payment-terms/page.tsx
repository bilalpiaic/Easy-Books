"use client"

import { useEffect, useState } from "react"
import { Clock, Plus, Pencil, Trash2, Check, X, Download, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface PaymentTerm {
  id: number
  code: string
  name: string
  days: number
}

interface TermForm {
  code: string
  name: string
  days: string
}

const emptyForm: TermForm = { code: "", name: "", days: "" }

export default function PaymentTermsPage() {
  const { t } = useTranslation()

  const [terms, setTerms]       = useState<PaymentTerm[]>([])
  const [modalOpen, setModal]   = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm]         = useState<TermForm>(emptyForm)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState<string | null>(null)

  const load = () =>
    apiFetch<PaymentTerm[]>("/api/payment-terms").then(setTerms).catch(() => {})

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyForm)
    setError(null)
    setModal(true)
  }

  const openEdit = (t: PaymentTerm) => {
    setEditingId(t.id)
    setForm({ code: t.code, name: t.name, days: String(t.days) })
    setError(null)
    setModal(true)
  }

  const closeModal = () => { setModal(false); setError(null) }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    const days = parseInt(form.days)
    if (!form.code.trim())  { setError("Code is required"); return }
    if (!form.name.trim())  { setError("Name is required"); return }
    if (isNaN(days) || days < 0) { setError("Days must be a non-negative number"); return }

    setSaving(true); setError(null)
    try {
      const body = JSON.stringify({ code: form.code.trim().toUpperCase(), name: form.name.trim(), days })
      if (editingId != null) {
        await apiFetch(`/api/payment-terms/${editingId}`, { method: "PATCH", body })
      } else {
        await apiFetch("/api/payment-terms", { method: "POST", body })
      }
      closeModal()
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (t: PaymentTerm) => {
    if (!confirm(`Delete payment term "${t.name}"?`)) return
    try {
      await apiFetch(`/api/payment-terms/${t.id}`, { method: "DELETE" })
      load()
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed")
    }
  }

  return (
    <div className="space-y-5 max-w-2xl">
      <PrintHeader title="Payment Terms" />
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Clock className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Payment Terms</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Net-day terms assigned to customers and vendors.</p>
          </div>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button
            onClick={() => downloadCSV('payment-terms.csv', terms.map(t => ({ Code: t.code, Name: t.name, Days: t.days })))}
            disabled={terms.length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button onClick={openCreate}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors">
            <Plus className="w-4 h-4" /> New Term
          </button>
        </div>
      </header>

      {terms.length === 0 ? (
        <div className="bg-white border border-[var(--border)] rounded-xl px-6 py-10 text-center">
          <Clock className="w-9 h-9 text-[var(--primary)]/30 mx-auto mb-3" />
          <p className="text-sm font-medium text-[var(--text-primary)]">No payment terms yet</p>
          <p className="text-xs text-[var(--text-primary)]/55 mt-1 mb-4">Common examples: Net 30, Net 60, Immediate.</p>
          <button onClick={openCreate}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors">
            <Plus className="w-4 h-4" /> Add first term
          </button>
        </div>
      ) : (
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-page)] text-[var(--text-primary)]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2.5">Code</th>
                <th className="text-left px-4 py-2.5">Name</th>
                <th className="text-right px-4 py-2.5">Days</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {terms.map(t => (
                <tr key={t.id} className="border-t border-[var(--border)] hover:bg-[#faf8f4]">
                  <td className="px-4 py-2.5 font-mono text-xs font-semibold text-[var(--primary)]">{t.code}</td>
                  <td className="px-4 py-2.5 font-medium text-[var(--text-primary)]">{t.name}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-[var(--text-primary)]/70">
                    {t.days === 0 ? (
                      <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2 py-0.5">Immediate</span>
                    ) : (
                      <>{t.days} days</>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => openEdit(t)} title="Edit"
                        className="p-1.5 rounded hover:bg-[#f0ede6] text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDelete(t)} title="Delete"
                        className="p-1.5 rounded hover:bg-red-50 text-[var(--text-primary)]/30 hover:text-red-600 transition-colors">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
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
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
              <h2 className="text-base font-bold text-[var(--text-primary)]">
                {editingId != null ? "Edit Payment Term" : "New Payment Term"}
              </h2>
              <button onClick={closeModal} className="text-[var(--text-primary)]/40 hover:text-[var(--text-primary)]">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Code</label>
                <input
                  autoFocus
                  value={form.code}
                  onChange={e => setForm(f => ({ ...f, code: e.target.value }))}
                  disabled={editingId != null}
                  placeholder="NET30"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[var(--primary)] disabled:bg-[var(--bg-page)] disabled:text-[var(--text-primary)]/40"
                />
                {editingId != null && (
                  <p className="text-xs text-[var(--text-primary)]/40 mt-1">Code cannot be changed after creation.</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Name</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Net 30 Days"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Days</label>
                <input
                  type="number"
                  min={0}
                  value={form.days}
                  onChange={e => setForm(f => ({ ...f, days: e.target.value }))}
                  placeholder="30"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm tabular-nums focus:outline-none focus:border-[var(--primary)]"
                />
                <p className="text-xs text-[var(--text-primary)]/40 mt-1">0 = due immediately upon invoicing.</p>
              </div>
              {error && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
              )}
              <div className="flex gap-3 pt-1">
                <button type="submit" disabled={saving}
                  className="flex-1 inline-flex items-center justify-center gap-2 bg-[var(--primary)] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50 transition-colors">
                  <Check className="w-4 h-4" />
                  {saving ? "Saving…" : editingId != null ? "Save Changes" : "Create Term"}
                </button>
                <button type="button" onClick={closeModal}
                  className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors">{t('common.cancel', 'Cancel')}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
