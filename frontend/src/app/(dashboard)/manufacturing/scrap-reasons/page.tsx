"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AlertTriangle, Plus, Trash2, Check, X } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useMessages } from "@/context/MessageContext"

interface ScrapReason {
  id: number
  code: string
  name: string
  is_active: boolean
}

type EditRow = { id?: number; code: string; name: string; is_active: boolean }

const empty = (): EditRow => ({ code: "", name: "", is_active: true })

export default function ScrapReasonsPage() {
  const { confirm } = useMessages()
  const [items, setItems] = useState<ScrapReason[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | "new" | null>(null)
  const [edit, setEdit] = useState<EditRow>(empty())
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  const load = () =>
    apiFetch<{ items: ScrapReason[] }>("/api/scrap-reasons")
      .then(d => setItems(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const save = async () => {
    if (!edit.code.trim() || !edit.name.trim()) {
      setError("Code and name are required")
      return
    }
    setSaving(true)
    setError("")
    try {
      if (editingId === "new") {
        await apiFetch("/api/scrap-reasons", {
          method: "POST",
          body: JSON.stringify(edit),
        })
      } else if (typeof editingId === "number") {
        await apiFetch(`/api/scrap-reasons/${editingId}`, {
          method: "PUT",
          body: JSON.stringify(edit),
        })
      }
      setEditingId(null)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const remove = async (r: ScrapReason) => {
    const ok = await confirm({
      title: `Delete ${r.code}?`,
      message: "Only unused reasons can be deleted. Prefer deactivating if referenced.",
      confirmLabel: "Delete",
      danger: true,
    })
    if (!ok) return
    try {
      await apiFetch(`/api/scrap-reasons/${r.id}`, { method: "DELETE" })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed")
    }
  }

  if (loading) return <p className="text-sm text-[var(--text-primary)]/60">Loading…</p>

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-7 h-7 text-[var(--primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Scrap Reasons</h1>
            <p className="text-sm text-[var(--text-primary)]/60">
              Reason codes for scrap and damage on production orders.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => { setEdit(empty()); setEditingId("new"); setError("") }}
          className="inline-flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          <Plus className="w-4 h-4" /> New reason
        </button>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)] text-xs uppercase tracking-wide text-[var(--text-primary)]/60">
            <tr>
              <th className="text-left px-4 py-2">Code</th>
              <th className="text-left px-4 py-2">Name</th>
              <th className="text-center px-4 py-2">Active</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {editingId === "new" && (
              <tr className="border-t border-[var(--border)] bg-amber-50/40">
                <td className="px-4 py-2">
                  <input value={edit.code} onChange={e => setEdit({ ...edit, code: e.target.value })}
                    className="w-full border border-[var(--border)] rounded px-2 py-1 text-sm font-mono uppercase" placeholder="DMG" />
                </td>
                <td className="px-4 py-2">
                  <input value={edit.name} onChange={e => setEdit({ ...edit, name: e.target.value })}
                    className="w-full border border-[var(--border)] rounded px-2 py-1 text-sm" placeholder="Damage in process" />
                </td>
                <td className="px-4 py-2 text-center">
                  <input type="checkbox" checked={edit.is_active}
                    onChange={e => setEdit({ ...edit, is_active: e.target.checked })} />
                </td>
                <td className="px-4 py-2 text-right space-x-1">
                  <button type="button" onClick={save} disabled={saving} className="p-1.5 text-emerald-700"><Check className="w-4 h-4" /></button>
                  <button type="button" onClick={() => setEditingId(null)} className="p-1.5 text-[var(--text-primary)]/40"><X className="w-4 h-4" /></button>
                </td>
              </tr>
            )}
            {items.map(r =>
              editingId === r.id ? (
                <tr key={r.id} className="border-t border-[var(--border)] bg-amber-50/40">
                  <td className="px-4 py-2">
                    <input value={edit.code} onChange={e => setEdit({ ...edit, code: e.target.value })}
                      className="w-full border border-[var(--border)] rounded px-2 py-1 text-sm font-mono uppercase" />
                  </td>
                  <td className="px-4 py-2">
                    <input value={edit.name} onChange={e => setEdit({ ...edit, name: e.target.value })}
                      className="w-full border border-[var(--border)] rounded px-2 py-1 text-sm" />
                  </td>
                  <td className="px-4 py-2 text-center">
                    <input type="checkbox" checked={edit.is_active}
                      onChange={e => setEdit({ ...edit, is_active: e.target.checked })} />
                  </td>
                  <td className="px-4 py-2 text-right space-x-1">
                    <button type="button" onClick={save} disabled={saving} className="p-1.5 text-emerald-700"><Check className="w-4 h-4" /></button>
                    <button type="button" onClick={() => setEditingId(null)} className="p-1.5 text-[var(--text-primary)]/40"><X className="w-4 h-4" /></button>
                  </td>
                </tr>
              ) : (
                <tr key={r.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2 font-mono text-xs font-semibold">{r.code}</td>
                  <td className="px-4 py-2">{r.name}</td>
                  <td className="px-4 py-2 text-center text-xs">
                    {r.is_active
                      ? <span className="text-emerald-700 font-semibold">Active</span>
                      : <span className="text-[var(--text-primary)]/40">Inactive</span>}
                  </td>
                  <td className="px-4 py-2 text-right space-x-1">
                    <button type="button"
                      onClick={() => { setEdit({ id: r.id, code: r.code, name: r.name, is_active: r.is_active }); setEditingId(r.id) }}
                      className="text-[var(--primary)] text-xs font-medium hover:underline">Edit</button>
                    <button type="button" onClick={() => remove(r)}
                      className="p-1.5 text-[var(--text-primary)]/30 hover:text-red-500 inline-flex align-middle">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              )
            )}
            {items.length === 0 && editingId !== "new" && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-sm text-[var(--text-primary)]/50">
                  No reason codes yet.{" "}
                  <Link href="#" onClick={e => { e.preventDefault(); setEdit(empty()); setEditingId("new") }}
                    className="text-[var(--primary)] hover:underline">Add one</Link>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
