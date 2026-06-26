"use client"
import { useState, useEffect } from "react"
import { Plus, Check, X } from "lucide-react"
import { apiFetch } from "@/lib/api"

type LabTest = {
  id: number; code: string; name: string; category: string
  normal_range?: string; unit?: string; standard_fee: number; is_active: boolean
}

const CATEGORIES = ["hematology", "biochemistry", "microbiology", "radiology", "other"]

export default function LabTestsPage() {
  const [tests, setTests] = useState<LabTest[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<Partial<LabTest>>({})
  const [showNew, setShowNew] = useState(false)
  const [newForm, setNewForm] = useState({ code: "", name: "", category: "hematology", standard_fee: "", normal_range: "", unit: "" })
  const [saving, setSaving] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const data = await apiFetch<LabTest[]>("/api/healthcare/lab/tests?active_only=false")
      setTests(data ?? [])
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function startEdit(test: LabTest) {
    setEditing(test.id)
    setEditForm({ name: test.name, category: test.category, standard_fee: test.standard_fee, normal_range: test.normal_range, unit: test.unit })
  }

  async function saveEdit(id: number) {
    setSaving(true)
    await apiFetch(`/api/healthcare/lab/tests/${id}`, { method: "PUT", body: JSON.stringify(editForm) }).catch(() => null)
    setEditing(null)
    setSaving(false)
    load()
  }

  async function createTest(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const body = { ...newForm, standard_fee: parseFloat(newForm.standard_fee) || 0 }
      await apiFetch("/api/healthcare/lab/tests", { method: "POST", body: JSON.stringify(body) })
      setShowNew(false)
      setNewForm({ code: "", name: "", category: "hematology", standard_fee: "", normal_range: "", unit: "" })
      load()
    } catch {
      // silent
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(test: LabTest) {
    await apiFetch(`/api/healthcare/lab/tests/${test.id}`, { method: "PUT", body: JSON.stringify({ is_active: !test.is_active }) }).catch(() => null)
    load()
  }

  const byCategory = CATEGORIES.reduce((acc, cat) => {
    acc[cat] = tests.filter(t => t.category === cat)
    return acc
  }, {} as Record<string, LabTest[]>)

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Lab Test Catalogue</h1>
          <p className="text-sm text-neutral-500">{tests.filter(t => t.is_active).length} active tests</p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="flex items-center gap-1.5 bg-rose-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-rose-600">
          <Plus className="w-4 h-4" /> Add Test
        </button>
      </div>

      {loading ? (
        <div className="text-sm text-neutral-400">Loading…</div>
      ) : (
        CATEGORIES.map(cat => {
          const catTests = byCategory[cat]
          if (catTests.length === 0) return null
          return (
            <div key={cat} className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-neutral-100 bg-neutral-50">
                <span className="text-sm font-medium capitalize">{cat}</span>
                <span className="ml-2 text-xs text-neutral-400">{catTests.length} tests</span>
              </div>
              <table className="w-full text-sm">
                <thead className="text-xs text-neutral-500 uppercase">
                  <tr>
                    <th className="text-left px-4 py-2">Code</th>
                    <th className="text-left px-4 py-2">Name</th>
                    <th className="text-left px-4 py-2">Normal Range</th>
                    <th className="text-left px-4 py-2">Unit</th>
                    <th className="text-right px-4 py-2">Fee</th>
                    <th className="text-center px-4 py-2">Active</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {catTests.map(t => (
                    <tr key={t.id} className={`hover:bg-neutral-50 ${!t.is_active ? "opacity-50" : ""}`}>
                      {editing === t.id ? (
                        <>
                          <td className="px-4 py-2 text-neutral-500">{t.code}</td>
                          <td className="px-4 py-2">
                            <input value={String(editForm.name ?? "")} onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                              className="border border-neutral-200 rounded px-2 py-1 text-sm w-full" />
                          </td>
                          <td className="px-4 py-2">
                            <input value={String(editForm.normal_range ?? "")} onChange={e => setEditForm(f => ({ ...f, normal_range: e.target.value }))}
                              className="border border-neutral-200 rounded px-2 py-1 text-sm w-full" />
                          </td>
                          <td className="px-4 py-2">
                            <input value={String(editForm.unit ?? "")} onChange={e => setEditForm(f => ({ ...f, unit: e.target.value }))}
                              className="border border-neutral-200 rounded px-2 py-1 text-sm w-20" />
                          </td>
                          <td className="px-4 py-2">
                            <input type="number" value={String(editForm.standard_fee ?? "")} onChange={e => setEditForm(f => ({ ...f, standard_fee: Number(e.target.value) }))}
                              className="border border-neutral-200 rounded px-2 py-1 text-sm w-24 text-right" />
                          </td>
                          <td className="px-4 py-2"></td>
                          <td className="px-4 py-2">
                            <div className="flex gap-1">
                              <button onClick={() => saveEdit(t.id)} disabled={saving}
                                className="p-1 text-green-600 hover:bg-green-50 rounded"><Check className="w-3.5 h-3.5" /></button>
                              <button onClick={() => setEditing(null)}
                                className="p-1 text-neutral-400 hover:bg-neutral-50 rounded"><X className="w-3.5 h-3.5" /></button>
                            </div>
                          </td>
                        </>
                      ) : (
                        <>
                          <td className="px-4 py-2 text-neutral-500 font-mono text-xs">{t.code}</td>
                          <td className="px-4 py-2 font-medium">{t.name}</td>
                          <td className="px-4 py-2 text-neutral-500">{t.normal_range || "—"}</td>
                          <td className="px-4 py-2 text-neutral-500">{t.unit || "—"}</td>
                          <td className="px-4 py-2 text-right">{parseFloat(String(t.standard_fee)).toLocaleString()}</td>
                          <td className="px-4 py-2 text-center">
                            <button onClick={() => toggleActive(t)}
                              className={`w-5 h-5 rounded border ${t.is_active ? "bg-green-500 border-green-500" : "border-neutral-300"} flex items-center justify-center mx-auto`}>
                              {t.is_active && <Check className="w-3 h-3 text-white" />}
                            </button>
                          </td>
                          <td className="px-4 py-2">
                            <button onClick={() => startEdit(t)} className="text-xs text-rose-600 hover:underline">Edit</button>
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        })
      )}

      {/* New test modal */}
      {showNew && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">Add Lab Test</h2>
            <form onSubmit={createTest} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Code *</label>
                  <input required value={newForm.code} onChange={e => setNewForm(f => ({ ...f, code: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" placeholder="CBC" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Category</label>
                  <select value={newForm.category} onChange={e => setNewForm(f => ({ ...f, category: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm">
                    {CATEGORIES.map(c => <option key={c} value={c} className="capitalize">{c}</option>)}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Test Name *</label>
                  <input required value={newForm.name} onChange={e => setNewForm(f => ({ ...f, name: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" placeholder="Complete Blood Count" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Normal Range</label>
                  <input value={newForm.normal_range} onChange={e => setNewForm(f => ({ ...f, normal_range: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" placeholder="4.0–11.0" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Unit</label>
                  <input value={newForm.unit} onChange={e => setNewForm(f => ({ ...f, unit: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" placeholder="×10³/μL" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Standard Fee</label>
                  <input type="number" min="0" step="0.01" value={newForm.standard_fee}
                    onChange={e => setNewForm(f => ({ ...f, standard_fee: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowNew(false)}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-lg">Cancel</button>
                <button type="submit" disabled={saving}
                  className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg disabled:opacity-50">
                  {saving ? "Saving…" : "Add Test"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
