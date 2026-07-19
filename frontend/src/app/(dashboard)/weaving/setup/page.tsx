"use client"

import { useCallback, useEffect, useState } from "react"
import { Plus, Pencil } from "lucide-react"
import { apiFetch } from "@/lib/api"

type Master = {
  id: number
  code: string
  name: string
  description?: string | null
  loom_type?: string | null
  is_active: boolean
}

type TabKey = "fabric-qualities" | "looms" | "yarn-types" | "shifts" | "operators"

const TABS: { key: TabKey; label: string; extra?: string }[] = [
  { key: "fabric-qualities", label: "Fabric Qualities" },
  { key: "looms", label: "Looms", extra: "loom_type" },
  { key: "yarn-types", label: "Yarn Types" },
  { key: "shifts", label: "Shifts" },
  { key: "operators", label: "Operators" },
]

const BLANK = { code: "", name: "", description: "", loom_type: "", is_active: true }

export default function WeavingSetupPage() {
  const [tab, setTab] = useState<TabKey>("fabric-qualities")
  const [rows, setRows] = useState<Master[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Master | null>(null)
  const [form, setForm] = useState(BLANK)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch<Master[]>(`/api/weaving/${tab}`)
      setRows(Array.isArray(data) ? data : [])
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => { load() }, [load])

  function openNew() {
    setEditing(null)
    setForm(BLANK)
    setErr("")
    setShowForm(true)
  }

  function openEdit(r: Master) {
    setEditing(r)
    setForm({
      code: r.code,
      name: r.name,
      description: r.description ?? "",
      loom_type: r.loom_type ?? "",
      is_active: r.is_active,
    })
    setErr("")
    setShowForm(true)
  }

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    const body: Record<string, unknown> = {
      code: form.code.trim(),
      name: form.name.trim(),
      is_active: form.is_active,
    }
    if (tab === "looms") body.loom_type = form.loom_type || null
    else body.description = form.description || null
    try {
      if (editing) {
        await apiFetch(`/api/weaving/${tab}/${editing.id}`, { method: "PUT", body: JSON.stringify(body) })
      } else {
        await apiFetch(`/api/weaving/${tab}`, { method: "POST", body: JSON.stringify(body) })
      }
      setShowForm(false)
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const showLoomType = tab === "looms"

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">Weaving Setup</h1>
          <p className="text-sm text-[var(--text-muted)]">Master data — customers and sizing vendors use existing Customer / Vendor masters</p>
        </div>
        <button
          onClick={openNew}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm"
        >
          <Plus className="w-4 h-4" /> Add
        </button>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-[var(--border)] print:hidden">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-sm border-b-2 -mb-px transition-colors ${
              tab === t.key
                ? "border-[var(--primary)] text-[var(--primary)] font-medium"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Code</th>
              <th className="px-3 py-2">Name</th>
              {showLoomType ? <th className="px-3 py-2">Type</th> : <th className="px-3 py-2">Description</th>}
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right print:hidden">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--text-muted)]">Loading…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--text-muted)]">No records yet</td></tr>
            ) : rows.map(r => (
              <tr key={r.id} className={`border-t border-[var(--border)] ${!r.is_active ? "opacity-50" : ""}`}>
                <td className="px-3 py-2 whitespace-nowrap font-medium">{r.code}</td>
                <td className="px-3 py-2">{r.name}</td>
                <td className="px-3 py-2 text-[var(--text-muted)]">
                  {showLoomType ? (r.loom_type || "—") : (r.description || "—")}
                </td>
                <td className="px-3 py-2">{r.is_active ? "Active" : "Inactive"}</td>
                <td className="px-3 py-2 text-right print:hidden">
                  <button onClick={() => openEdit(r)} className="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)]" title="Edit">
                    <Pencil className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 print:hidden">
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] shadow-xl w-full max-w-md p-5">
            <h2 className="text-lg font-semibold mb-3">{editing ? "Edit" : "Add"} {TABS.find(t => t.key === tab)?.label}</h2>
            {err && <p className="text-sm text-red-600 mb-2">{err}</p>}
            <form onSubmit={save} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Code *</label>
                <input required value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))}
                  className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Name *</label>
                <input required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm" />
              </div>
              {showLoomType ? (
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Loom type</label>
                  <input value={form.loom_type} onChange={e => setForm(f => ({ ...f, loom_type: e.target.value }))}
                    className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm" />
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Description</label>
                  <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                    className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm" />
                </div>
              )}
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} />
                Active
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="px-3 py-2 text-sm rounded-lg border border-[var(--border)]">Cancel</button>
                <button type="submit" disabled={saving} className="px-3 py-2 text-sm rounded-lg bg-[var(--primary)] text-white disabled:opacity-50">
                  {saving ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
