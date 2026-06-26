"use client"
import { useState, useEffect, useCallback } from "react"
import { Search, Plus, User } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { PatientBadge, StatusBadge } from "@/components/healthcare/primitives"
import { useRouter } from "next/navigation"
import { fmtDate } from "@/lib/utils"

type Patient = {
  id: number
  mr_number: string
  name: string
  gender: string
  dob?: string
  phone?: string
  cnic?: string
  blood_group?: string
  is_active: boolean
}

type PatientListResponse = { items: Patient[]; total: number } | Patient[]

export default function PatientsPage() {
  const router = useRouter()
  const [search, setSearch] = useState("")
  const [patients, setPatients] = useState<Patient[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)
  const [form, setForm] = useState({ name: "", gender: "male", phone: "", dob: "", cnic: "", blood_group: "", address: "" })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const qs = new URLSearchParams({ search, limit: "50" })
      const json = await apiFetch<PatientListResponse>(`/api/healthcare/patients?${qs}`)
      if (Array.isArray(json)) {
        setPatients(json)
        setTotal(json.length)
      } else {
        setPatients(json.items ?? [])
        setTotal(json.total ?? 0)
      }
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => { load() }, [load])

  async function createPatient(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr("")
    try {
      await apiFetch("/api/healthcare/patients", { method: "POST", body: JSON.stringify(form) })
      setShowNew(false)
      setForm({ name: "", gender: "male", phone: "", dob: "", cnic: "", blood_group: "", address: "" })
      load()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to create patient")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Patients</h1>
          <p className="text-sm text-neutral-500">{total} registered</p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-1.5 bg-rose-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-rose-600 transition-colors"
        >
          <Plus className="w-4 h-4" /> New Patient
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by name, MR number, or CNIC…"
          className="w-full pl-9 pr-4 py-2 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-rose-300"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 text-neutral-500 text-xs uppercase">
            <tr>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Gender</th>
              <th className="text-left px-4 py-3">DOB</th>
              <th className="text-left px-4 py-3">Phone</th>
              <th className="text-left px-4 py-3">Blood</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-neutral-400">Loading…</td></tr>
            ) : patients.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-neutral-400">
                <User className="w-8 h-8 mx-auto mb-2 opacity-30" />
                No patients found
              </td></tr>
            ) : patients.map(p => (
              <tr
                key={p.id}
                onClick={() => router.push(`/healthcare/patients/${p.id}`)}
                className="hover:bg-neutral-50 cursor-pointer"
              >
                <td className="px-4 py-3">
                  <PatientBadge name={p.name} mr={p.mr_number} />
                </td>
                <td className="px-4 py-3 capitalize text-neutral-600">{p.gender}</td>
                <td className="px-4 py-3 text-neutral-600">{p.dob ? fmtDate(p.dob) : "—"}</td>
                <td className="px-4 py-3 text-neutral-600">{p.phone || "—"}</td>
                <td className="px-4 py-3">
                  {p.blood_group ? (
                    <span className="bg-red-50 text-red-700 px-1.5 py-0.5 rounded text-xs font-medium">{p.blood_group}</span>
                  ) : "—"}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={p.is_active ? "available" : "maintenance"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* New patient modal */}
      {showNew && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Register New Patient</h2>
            {err && <div className="mb-3 text-red-600 text-sm">{err}</div>}
            <form onSubmit={createPatient} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Full Name *</label>
                  <input required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-300" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Gender</label>
                  <select value={form.gender} onChange={e => setForm(f => ({ ...f, gender: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Date of Birth</label>
                  <input type="date" value={form.dob} onChange={e => setForm(f => ({ ...f, dob: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Phone</label>
                  <input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">CNIC</label>
                  <input value={form.cnic} onChange={e => setForm(f => ({ ...f, cnic: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none" placeholder="12345-1234567-1" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Blood Group</label>
                  <select value={form.blood_group} onChange={e => setForm(f => ({ ...f, blood_group: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                    <option value="">— Unknown —</option>
                    {["A+","A-","B+","B-","AB+","AB-","O+","O-"].map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Address</label>
                  <input value={form.address} onChange={e => setForm(f => ({ ...f, address: e.target.value }))}
                    className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowNew(false)}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-lg hover:bg-neutral-50">
                  Cancel
                </button>
                <button type="submit" disabled={saving}
                  className="px-4 py-2 text-sm bg-rose-500 text-white rounded-lg hover:bg-rose-600 disabled:opacity-50">
                  {saving ? "Saving…" : "Register"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
