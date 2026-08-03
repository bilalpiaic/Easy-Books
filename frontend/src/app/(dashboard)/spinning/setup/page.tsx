"use client"

import { useCallback, useEffect, useState } from "react"
import { Plus, Pencil } from "lucide-react"
import { apiFetch } from "@/lib/api"

type Master = {
  id: number
  code: string
  name: string
  description?: string | null
  machine_type?: string | null
  spindle_count?: number | null
  start_time?: string | null
  end_time?: string | null
  phone?: string | null
  count_ne?: number | null
  count_nm?: number | null
  twist_direction?: string | null
  blend_cotton_pct?: number | null
  blend_poly_pct?: number | null
  staple_mm?: number | null
  micronaire?: number | null
  grade?: string | null
  gl_account_code?: string | null
  default_stage?: string | null
  is_active: boolean
}

type TabKey = "yarn-specs" | "fiber-grades" | "machines" | "shifts" | "operators" | "waste-types"

const TABS: { key: TabKey; label: string }[] = [
  { key: "yarn-specs", label: "Yarn Specs" },
  { key: "fiber-grades", label: "Fiber Grades" },
  { key: "machines", label: "Machines" },
  { key: "shifts", label: "Shifts" },
  { key: "operators", label: "Operators" },
  { key: "waste-types", label: "Waste Types" },
]

const STAGES = ["opening", "carding", "drawing", "roving", "spinning", "winding"]

const BLANK = {
  code: "", name: "", description: "", machine_type: "", spindle_count: "",
  start_time: "", end_time: "", phone: "", count_ne: "", count_nm: "",
  twist_direction: "", blend_cotton_pct: "", blend_poly_pct: "",
  staple_mm: "", micronaire: "", grade: "", gl_account_code: "5901",
  default_stage: "", is_active: true,
}

export default function SpinningSetupPage() {
  const [tab, setTab] = useState<TabKey>("yarn-specs")
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
      const data = await apiFetch<Master[]>(`/api/spinning/${tab}`)
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
      machine_type: r.machine_type ?? "",
      spindle_count: r.spindle_count != null ? String(r.spindle_count) : "",
      start_time: r.start_time ?? "",
      end_time: r.end_time ?? "",
      phone: r.phone ?? "",
      count_ne: r.count_ne != null ? String(r.count_ne) : "",
      count_nm: r.count_nm != null ? String(r.count_nm) : "",
      twist_direction: r.twist_direction ?? "",
      blend_cotton_pct: r.blend_cotton_pct != null ? String(r.blend_cotton_pct) : "",
      blend_poly_pct: r.blend_poly_pct != null ? String(r.blend_poly_pct) : "",
      staple_mm: r.staple_mm != null ? String(r.staple_mm) : "",
      micronaire: r.micronaire != null ? String(r.micronaire) : "",
      grade: r.grade ?? "",
      gl_account_code: r.gl_account_code ?? "5901",
      default_stage: r.default_stage ?? "",
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
    if (tab === "yarn-specs") {
      body.count_ne = form.count_ne.trim() === "" ? null : parseFloat(form.count_ne)
      body.count_nm = form.count_nm.trim() === "" ? null : parseFloat(form.count_nm)
      body.twist_direction = form.twist_direction || null
      body.blend_cotton_pct = form.blend_cotton_pct.trim() === "" ? null : parseFloat(form.blend_cotton_pct)
      body.blend_poly_pct = form.blend_poly_pct.trim() === "" ? null : parseFloat(form.blend_poly_pct)
    } else if (tab === "fiber-grades") {
      body.staple_mm = form.staple_mm.trim() === "" ? null : parseFloat(form.staple_mm)
      body.micronaire = form.micronaire.trim() === "" ? null : parseFloat(form.micronaire)
      body.grade = form.grade || null
    } else if (tab === "machines") {
      body.machine_type = form.machine_type || null
      body.spindle_count = form.spindle_count.trim() === "" ? null : parseInt(form.spindle_count, 10)
    } else if (tab === "shifts") {
      body.start_time = form.start_time || null
      body.end_time = form.end_time || null
    } else if (tab === "operators") {
      body.phone = form.phone || null
    } else if (tab === "waste-types") {
      body.gl_account_code = form.gl_account_code || "5901"
      body.default_stage = form.default_stage || null
    }
    try {
      if (editing) {
        await apiFetch(`/api/spinning/${tab}/${editing.id}`, { method: "PUT", body: JSON.stringify(body) })
      } else {
        await apiFetch(`/api/spinning/${tab}`, { method: "POST", body: JSON.stringify(body) })
      }
      setShowForm(false)
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const input = "w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
  const tabLabel = TABS.find(t => t.key === tab)?.label ?? tab

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">Spinning Setup</h1>
          <p className="text-sm text-[var(--text-muted)]">Yarn specs, fiber grades, machines, shifts, operators, waste types</p>
        </div>
        <button onClick={openNew} className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm">
          <Plus className="w-4 h-4" /> Add
        </button>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-[var(--border)] print:hidden">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-sm border-b-2 -mb-px transition-colors ${
              tab === t.key
                ? "border-[var(--primary)] text-[var(--primary)] font-medium"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}>
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
              {tab === "yarn-specs" && <th className="px-3 py-2">Count Ne/Nm</th>}
              {tab === "fiber-grades" && <th className="px-3 py-2">Grade</th>}
              {tab === "machines" && <th className="px-3 py-2">Type / Spindles</th>}
              {tab === "shifts" && <th className="px-3 py-2">Hours</th>}
              {tab === "operators" && <th className="px-3 py-2">Phone</th>}
              {tab === "waste-types" && <th className="px-3 py-2">GL / Stage</th>}
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right print:hidden">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">Loading…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">No records yet</td></tr>
            ) : rows.map(r => (
              <tr key={r.id} className={`border-t border-[var(--border)] ${!r.is_active ? "opacity-50" : ""}`}>
                <td className="px-3 py-2 whitespace-nowrap font-medium">{r.code}</td>
                <td className="px-3 py-2">{r.name}</td>
                {tab === "yarn-specs" && (
                  <td className="px-3 py-2 tabular-nums">{r.count_ne ?? "—"} / {r.count_nm ?? "—"}</td>
                )}
                {tab === "fiber-grades" && <td className="px-3 py-2">{r.grade || "—"}</td>}
                {tab === "machines" && (
                  <td className="px-3 py-2">{r.machine_type || "—"} · {r.spindle_count ?? "—"} sp</td>
                )}
                {tab === "shifts" && (
                  <td className="px-3 py-2 whitespace-nowrap">{r.start_time || "—"} – {r.end_time || "—"}</td>
                )}
                {tab === "operators" && <td className="px-3 py-2">{r.phone || "—"}</td>}
                {tab === "waste-types" && (
                  <td className="px-3 py-2">{r.gl_account_code || "—"} · {r.default_stage || "—"}</td>
                )}
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
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] shadow-xl w-full max-w-md p-5 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-3">{editing ? "Edit" : "Add"} {tabLabel}</h2>
            {err && <p className="text-sm text-red-600 mb-2">{err}</p>}
            <form onSubmit={save} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Code *</label>
                <input required value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))} className={input} />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Name *</label>
                <input required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className={input} />
              </div>
              {tab === "yarn-specs" && (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Count Ne</label>
                      <input type="number" step="any" value={form.count_ne} onChange={e => setForm(f => ({ ...f, count_ne: e.target.value }))} className={input} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Count Nm</label>
                      <input type="number" step="any" value={form.count_nm} onChange={e => setForm(f => ({ ...f, count_nm: e.target.value }))} className={input} />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Twist direction</label>
                    <input value={form.twist_direction} onChange={e => setForm(f => ({ ...f, twist_direction: e.target.value }))} className={input} />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Cotton %</label>
                      <input type="number" step="any" value={form.blend_cotton_pct} onChange={e => setForm(f => ({ ...f, blend_cotton_pct: e.target.value }))} className={input} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Poly %</label>
                      <input type="number" step="any" value={form.blend_poly_pct} onChange={e => setForm(f => ({ ...f, blend_poly_pct: e.target.value }))} className={input} />
                    </div>
                  </div>
                </>
              )}
              {tab === "fiber-grades" && (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Staple mm</label>
                      <input type="number" step="any" value={form.staple_mm} onChange={e => setForm(f => ({ ...f, staple_mm: e.target.value }))} className={input} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Micronaire</label>
                      <input type="number" step="any" value={form.micronaire} onChange={e => setForm(f => ({ ...f, micronaire: e.target.value }))} className={input} />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Grade</label>
                    <input value={form.grade} onChange={e => setForm(f => ({ ...f, grade: e.target.value }))} className={input} />
                  </div>
                </>
              )}
              {tab === "machines" && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Machine type</label>
                    <input value={form.machine_type} onChange={e => setForm(f => ({ ...f, machine_type: e.target.value }))} className={input} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Spindle count</label>
                    <input type="number" value={form.spindle_count} onChange={e => setForm(f => ({ ...f, spindle_count: e.target.value }))} className={input} />
                  </div>
                </>
              )}
              {tab === "shifts" && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Start time</label>
                    <input value={form.start_time} onChange={e => setForm(f => ({ ...f, start_time: e.target.value }))} placeholder="08:00" className={input} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">End time</label>
                    <input value={form.end_time} onChange={e => setForm(f => ({ ...f, end_time: e.target.value }))} placeholder="16:00" className={input} />
                  </div>
                </div>
              )}
              {tab === "operators" && (
                <div>
                  <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Phone</label>
                  <input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} className={input} />
                </div>
              )}
              {tab === "waste-types" && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">GL account code</label>
                    <input value={form.gl_account_code} onChange={e => setForm(f => ({ ...f, gl_account_code: e.target.value }))} className={input} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Default stage</label>
                    <select value={form.default_stage} onChange={e => setForm(f => ({ ...f, default_stage: e.target.value }))} className={input}>
                      <option value="">—</option>
                      {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                </>
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
