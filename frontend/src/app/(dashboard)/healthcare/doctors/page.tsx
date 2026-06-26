"use client"
import { useState, useEffect, useCallback } from "react"
import { Plus, Pencil, UserCheck, UserX } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { StatusBadge } from "@/components/healthcare/primitives"

type Doctor = {
  id: number
  name: string
  specialization?: string
  qualification?: string
  phone?: string
  opd_fee: number
  is_active: boolean
}

const BLANK = { name: "", specialization: "", qualification: "", phone: "", opd_fee: "" }

export default function DoctorsPage() {
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [showAll, setShowAll] = useState(true)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Doctor | null>(null)
  const [form, setForm] = useState(BLANK)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch<Doctor[]>(`/api/healthcare/doctors?active_only=${!showAll}`)
      setDoctors(Array.isArray(data) ? data : [])
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [showAll])

  useEffect(() => { load() }, [load])

  function openNew() {
    setEditing(null)
    setForm(BLANK)
    setErr("")
    setShowForm(true)
  }

  function openEdit(d: Doctor) {
    setEditing(d)
    setForm({
      name: d.name,
      specialization: d.specialization ?? "",
      qualification: d.qualification ?? "",
      phone: d.phone ?? "",
      opd_fee: String(d.opd_fee),
    })
    setErr("")
    setShowForm(true)
  }

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    const body = {
      name: form.name,
      specialization: form.specialization || null,
      qualification: form.qualification || null,
      phone: form.phone || null,
      opd_fee: parseFloat(form.opd_fee) || 0,
    }
    try {
      if (editing) {
        await apiFetch(`/api/healthcare/doctors/${editing.id}`, { method: "PUT", body: JSON.stringify(body) })
      } else {
        await apiFetch("/api/healthcare/doctors", { method: "POST", body: JSON.stringify(body) })
      }
      setShowForm(false)
      load()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(d: Doctor) {
    try {
      await apiFetch(`/api/healthcare/doctors/${d.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !d.is_active }),
      })
      load()
    } catch {
      // silent
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Doctors</h1>
          <p className="text-sm text-neutral-500">{doctors.length} {showAll ? "total" : "active"}</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-neutral-600 cursor-pointer">
            <input
              type="checkbox"
              checked={showAll}
              onChange={e => setShowAll(e.target.checked)}
              className="accent-rose-500"
            />
            Show inactive
          </label>
          <button
            onClick={openNew}
            className="flex items-center gap-1.5 bg-rose-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-rose-600 transition-colors"
          >
            <Plus className="w-4 h-4" /> Add Doctor
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 text-neutral-500 text-xs uppercase">
            <tr>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Specialization</th>
              <th className="text-left px-4 py-3">Qualification</th>
              <th className="text-left px-4 py-3">Phone</th>
              <th className="text-right px-4 py-3">OPD Fee</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-right px-4 py-3 print:hidden">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-neutral-400">Loading…</td></tr>
            ) : doctors.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-neutral-400">No doctors found</td></tr>
            ) : doctors.map(d => (
              <tr key={d.id} className={`hover:bg-neutral-50 ${!d.is_active ? "opacity-50" : ""}`}>
                <td className="px-4 py-3 font-medium">{d.name}</td>
                <td className="px-4 py-3 text-neutral-600">{d.specialization || "—"}</td>
                <td className="px-4 py-3 text-neutral-600">{d.qualification || "—"}</td>
                <td className="px-4 py-3 text-neutral-600">{d.phone || "—"}</td>
                <td className="px-4 py-3 text-right font-medium">{Number(d.opd_fee).toLocaleString()}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={d.is_active ? "active" : "inactive"} />
                </td>
                <td className="px-4 py-3 text-right print:hidden">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => openEdit(d)}
                      className="p-1.5 text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 rounded transition-colors"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => toggleActive(d)}
                      className={`p-1.5 rounded transition-colors ${d.is_active
                        ? "text-neutral-400 hover:text-red-600 hover:bg-red-50"
                        : "text-neutral-400 hover:text-emerald-600 hover:bg-emerald-50"}`}
                      title={d.is_active ? "Deactivate" : "Activate"}
                    >
                      {d.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add / Edit modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-semibold mb-4">{editing ? "Edit Doctor" : "Add Doctor"}</h2>
            {err && <div className="mb-3 text-red-600 text-sm">{err}</div>}
            <form onSubmit={save} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">Full Name *</label>
                <input
                  required
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-300"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Specialization</label>
                  <input
                    value={form.specialization}
                    onChange={e => setForm(f => ({ ...f, specialization: e.target.value }))}
                    placeholder="e.g. Cardiology"
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Qualification</label>
                  <input
                    value={form.qualification}
                    onChange={e => setForm(f => ({ ...f, qualification: e.target.value }))}
                    placeholder="e.g. MBBS, FCPS"
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Phone</label>
                  <input
                    value={form.phone}
                    onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                    placeholder="0300-0000000"
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">OPD Fee *</label>
                  <input
                    required
                    type="number"
                    min="0"
                    step="any"
                    value={form.opd_fee}
                    onChange={e => setForm(f => ({ ...f, opd_fee: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-300"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-lg hover:bg-neutral-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg hover:bg-rose-600 disabled:opacity-50"
                >
                  {saving ? "Saving…" : editing ? "Update" : "Add Doctor"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
