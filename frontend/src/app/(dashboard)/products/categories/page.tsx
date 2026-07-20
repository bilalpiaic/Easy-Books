'use client'
import { useEffect, useState } from 'react'
import { Tag, Plus, Pencil, Trash2, Check, X, Download } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { downloadCSV } from '@/lib/utils'
import { useTranslation } from "react-i18next"
import { useMessages } from "@/context/MessageContext"

interface Cat { id: number; name: string; parent_id: number | null; is_active: boolean; children?: Cat[] }

type ModalMode =
  | { kind: 'add-parent' }
  | { kind: 'add-sub'; parentId: number; parentName: string }
  | { kind: 'edit'; cat: Cat }
  | null

export default function CategoriesPage() {
  const { confirm, toast } = useMessages()
  const { t } = useTranslation()

  const [tree, setTree] = useState<Cat[]>([])
  const [modal, setModal]     = useState<ModalMode>(null)
  const [inputVal, setInputVal] = useState('')
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState<string | null>(null)

  const load = () => apiFetch<Cat[]>('/api/product-categories').then(setTree).catch(() => {})
  useEffect(() => { load() }, [])

  const openAdd = (parentId: number | null, parentName?: string) => {
    setInputVal('')
    setError(null)
    setModal(parentId == null
      ? { kind: 'add-parent' }
      : { kind: 'add-sub', parentId, parentName: parentName ?? '' })
  }

  const openEdit = (cat: Cat) => {
    setInputVal(cat.name)
    setError(null)
    setModal({ kind: 'edit', cat })
  }

  const closeModal = () => { setModal(null); setError(null) }

  const handleSave = async () => {
    if (!inputVal.trim()) { setError('Name is required'); return }
    setSaving(true); setError(null)
    try {
      if (modal?.kind === 'add-parent') {
        await apiFetch('/api/product-categories', {
          method: 'POST', body: JSON.stringify({ name: inputVal.trim(), parent_id: null }),
        })
      } else if (modal?.kind === 'add-sub') {
        await apiFetch('/api/product-categories', {
          method: 'POST', body: JSON.stringify({ name: inputVal.trim(), parent_id: modal.parentId }),
        })
      } else if (modal?.kind === 'edit') {
        await apiFetch(`/api/product-categories/${modal.cat.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            name: inputVal.trim(),
            parent_id: modal.cat.parent_id,
            is_active: modal.cat.is_active,
          }),
        })
      }
      closeModal()
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false) }
  }

  const remove = async (cat: Cat) => {
    const label = cat.parent_id == null ? 'category' : 'sub-category'
    const ok = await confirm({
      title: `Delete ${label} "${cat.name}"?`,
      confirmLabel: "Delete",
      danger: true,
    })
    if (!ok) return
    try { await apiFetch(`/api/product-categories/${cat.id}`, { method: 'DELETE' }); load() }
    catch (e) { toast(e instanceof Error ? e.message : "Delete failed", "error") }
  }

  const modalTitle =
    modal?.kind === 'add-parent' ? 'New Parent Category'
    : modal?.kind === 'add-sub'  ? `New Sub-category under "${modal.parentName}"`
    : modal?.kind === 'edit'     ? `Rename "${modal.cat.name}"`
    : ''

  return (
    <div className="space-y-5 max-w-2xl">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Tag className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Product Categories</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Two-level taxonomy: parent → sub-category.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const rows = tree.flatMap(p => p.children && p.children.length > 0
                ? p.children.map(c => ({ Parent: p.name, "Sub-category": c.name, Active: c.is_active ? 'Yes' : 'No' }))
                : [{ Parent: p.name, "Sub-category": '', Active: p.is_active ? 'Yes' : 'No' }])
              downloadCSV('product-categories.csv', rows)
            }}
            disabled={tree.length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-lg text-sm font-bold hover:bg-[var(--bg-page)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
          <button onClick={() => openAdd(null)}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors">
            <Plus className="w-4 h-4" /> Parent Category
          </button>
        </div>
      </header>

      {tree.length === 0 ? (
        <div className="bg-white border border-[var(--border)] rounded-xl px-6 py-10 text-center">
          <Tag className="w-9 h-9 text-[var(--primary)]/30 mx-auto mb-3" />
          <p className="text-sm font-medium text-[var(--text-primary)]">No categories yet</p>
          <p className="text-xs text-[var(--text-primary)]/55 mt-1 mb-4">Create a parent category, then add sub-categories under it.</p>
          <button onClick={() => openAdd(null)}
            className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] transition-colors">
            <Plus className="w-4 h-4" /> Add first category
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {tree.map(parent => (
            <div key={parent.id} className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
              {/* Parent row */}
              <div className="flex items-center justify-between px-4 py-3 bg-[var(--bg-page)]">
                <span className="font-semibold text-[var(--text-primary)] text-sm">{parent.name}</span>
                <div className="flex items-center gap-1">
                  <button onClick={() => openAdd(parent.id, parent.name)} title="Add sub-category"
                    className="p-1.5 rounded hover:bg-[#f0ede6] text-[var(--primary)] transition-colors">
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => openEdit(parent)} title="Rename"
                    className="p-1.5 rounded hover:bg-[#f0ede6] text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors">
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => remove(parent)} title="Delete"
                    className="p-1.5 rounded hover:bg-red-50 text-[var(--text-primary)]/30 hover:text-red-600 transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              {/* Sub-category chips */}
              {(parent.children ?? []).length > 0 && (
                <div className="px-4 py-2.5 flex flex-wrap gap-2 border-t border-[var(--border)]">
                  {(parent.children ?? []).map(sub => (
                    <span key={sub.id}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--bg-page)] border border-[var(--border)] text-xs text-[var(--text-primary)]/80">
                      {sub.name}
                      <button onClick={() => openEdit(sub)} title="Rename" className="text-[var(--text-primary)]/30 hover:text-[var(--primary)]">
                        <Pencil className="w-2.5 h-2.5" />
                      </button>
                      <button onClick={() => remove(sub)} title="Delete" className="text-[var(--text-primary)]/25 hover:text-red-600">
                        <X className="w-2.5 h-2.5" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
            <div className="px-6 py-4 border-b border-[var(--border)]">
              <h2 className="text-base font-bold text-[var(--text-primary)]">{modalTitle}</h2>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[var(--text-primary)]/70 mb-1.5 uppercase tracking-wide">Name</label>
                <input
                  autoFocus
                  value={inputVal}
                  onChange={e => setInputVal(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleSave() }}
                  placeholder="e.g. Fabrics"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                />
              </div>
              {error && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}
              <div className="flex gap-3">
                <button onClick={handleSave} disabled={saving}
                  className="flex-1 inline-flex items-center justify-center gap-2 bg-[var(--primary)] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-50 transition-colors">
                  <Check className="w-4 h-4" />
                  {saving ? 'Saving…' : modal.kind === 'edit' ? 'Rename' : 'Create'}
                </button>
                <button onClick={closeModal}
                  className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors">{t('common.cancel', 'Cancel')}</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
