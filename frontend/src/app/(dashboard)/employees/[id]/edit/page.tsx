"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Plus, Trash2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

interface Component {
  id: number
  name: string
  code: string
  component_type: string
  is_fixed: boolean
}

interface StructureRow {
  component_id: number
  amount: number
  pct_of_basic: number | null
  effective_from: string | null
  effective_to: string | null
}

interface EmployeeDetail {
  id: number
  employee_code: string
  name: string
  department: string | null
  designation: string | null
  join_date: string | null
  cnic: string | null
  bank_account: string | null
  bank_name: string | null
  is_active: boolean
}

export default function EditEmployeePage() {
  const { t } = useTranslation()
  const params = useParams()
  const empId = params.id as string

  const [tab, setTab] = useState<"details" | "structure">("details")
  const [emp, setEmp] = useState<EmployeeDetail | null>(null)
  const [form, setForm] = useState({
    name: "", department: "", designation: "", join_date: "",
    cnic: "", bank_account: "", bank_name: "", is_active: true,
  })
  const [components, setComponents] = useState<Component[]>([])
  const [structure, setStructure] = useState<StructureRow[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savingStructure, setSavingStructure] = useState(false)
  const [error, setError] = useState("")
  const [successMsg, setSuccessMsg] = useState("")

  useEffect(() => {
    Promise.all([
      apiFetch<EmployeeDetail>(`/api/employees/${empId}`),
      apiFetch<Component[]>("/api/payroll/components"),
      apiFetch<StructureRow[]>(`/api/employees/${empId}/structure`),
    ]).then(([empData, compsData, structData]) => {
      setEmp(empData)
      setForm({
        name: empData.name ?? "",
        department: empData.department ?? "",
        designation: empData.designation ?? "",
        join_date: empData.join_date ?? "",
        cnic: empData.cnic ?? "",
        bank_account: empData.bank_account ?? "",
        bank_name: empData.bank_name ?? "",
        is_active: empData.is_active,
      })
      setComponents(Array.isArray(compsData) ? compsData : [])
      setStructure(Array.isArray(structData) ? structData : [])
    }).catch(() => setError("Failed to load employee"))
      .finally(() => setLoading(false))
  }, [empId])

  const saveDetails = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError("")
    setSuccessMsg("")
    try {
      await apiFetch(`/api/employees/${empId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      })
      setSuccessMsg("Details saved")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSaving(false)
    }
  }

  const saveStructure = async () => {
    setSavingStructure(true)
    setError("")
    setSuccessMsg("")
    try {
      await apiFetch(`/api/employees/${empId}/structure`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(structure),
      })
      setSuccessMsg("Salary structure saved")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save structure")
    } finally {
      setSavingStructure(false)
    }
  }

  const addStructureRow = () => {
    if (components.length === 0) return
    setStructure(prev => [...prev, {
      component_id: components[0].id,
      amount: 0,
      pct_of_basic: null,
      effective_from: null,
      effective_to: null,
    }])
  }

  const removeStructureRow = (idx: number) => {
    setStructure(prev => prev.filter((_, i) => i !== idx))
  }

  const updateStructureRow = (idx: number, field: keyof StructureRow, value: string | number | null) => {
    setStructure(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r))
  }

  if (loading) return <div className="p-8 text-gray-400">Loading...</div>

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/employees" className="text-[#b8943f] hover:underline">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[#1a1814]">{emp?.name ?? "Employee"}</h1>
          <p className="text-sm text-gray-500">{emp?.employee_code}</p>
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>}
      {successMsg && <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg px-4 py-3 text-sm">{successMsg}</div>}

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setTab("details")}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${tab === "details" ? "border-[#b8943f] text-[#b8943f]" : "border-transparent text-gray-500 hover:text-gray-700"}`}
        >
          Details
        </button>
        <button
          onClick={() => setTab("structure")}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${tab === "structure" ? "border-[#b8943f] text-[#b8943f]" : "border-transparent text-gray-500 hover:text-gray-700"}`}
        >
          Salary Structure
        </button>
      </div>

      {tab === "details" && (
        <form onSubmit={saveDetails} className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[#1a1814] mb-1">Full Name <span className="text-red-500">*</span></label>
              <input
                type="text" required value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#1a1814] mb-1">Department</label>
              <input
                type="text" value={form.department}
                onChange={e => setForm(p => ({ ...p, department: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#1a1814] mb-1">Designation</label>
              <input
                type="text" value={form.designation}
                onChange={e => setForm(p => ({ ...p, designation: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#1a1814] mb-1">Join Date</label>
              <input
                type="date" value={form.join_date}
                onChange={e => setForm(p => ({ ...p, join_date: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#1a1814] mb-1">CNIC</label>
              <input
                type="text" value={form.cnic}
                onChange={e => setForm(p => ({ ...p, cnic: e.target.value }))}
                placeholder="XXXXX-XXXXXXX-X"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#1a1814] mb-1">Bank Account</label>
              <input
                type="text" value={form.bank_account}
                onChange={e => setForm(p => ({ ...p, bank_account: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#1a1814] mb-1">Bank Name</label>
              <input
                type="text" value={form.bank_name}
                onChange={e => setForm(p => ({ ...p, bank_name: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
              />
            </div>
            <div className="flex items-center gap-3 pt-2">
              <input
                type="checkbox" id="is_active" checked={form.is_active}
                onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))}
                className="w-4 h-4 accent-[#b8943f]"
              />
              <label htmlFor="is_active" className="text-sm font-medium text-[#1a1814]">Active</label>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="submit" disabled={saving}
              className="px-6 py-2 bg-[#b8943f] text-white rounded-lg hover:opacity-90 text-sm font-medium disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Details"}
            </button>
          </div>
        </form>
      )}

      {tab === "structure" && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-[#1a1814]">Salary Components</h3>
            <button
              onClick={addStructureRow}
              className="inline-flex items-center gap-1 text-[#b8943f] hover:underline text-sm font-medium"
            >
              <Plus className="w-4 h-4" /> Add Component
            </button>
          </div>

          {structure.length === 0 ? (
            <p className="text-gray-400 text-sm py-4 text-center">No components added yet. Click "Add Component" to start.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#f6f3ee]">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium text-[#1a1814]">Component</th>
                    <th className="text-left px-3 py-2 font-medium text-[#1a1814]">Type</th>
                    <th className="text-right px-3 py-2 font-medium text-[#1a1814]">Amount</th>
                    <th className="text-right px-3 py-2 font-medium text-[#1a1814]">% of Basic</th>
                    <th className="text-left px-3 py-2 font-medium text-[#1a1814]">Effective From</th>
                    <th className="text-left px-3 py-2 font-medium text-[#1a1814]">Effective To</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {structure.map((row, idx) => {
                    const comp = components.find(c => c.id === row.component_id)
                    return (
                      <tr key={idx}>
                        <td className="px-3 py-2">
                          <select
                            value={row.component_id}
                            onChange={e => updateStructureRow(idx, "component_id", parseInt(e.target.value))}
                            className="border border-gray-200 rounded px-2 py-1 text-sm w-full focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
                          >
                            {components.map(c => (
                              <option key={c.id} value={c.id}>{c.name} ({c.code})</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2 text-gray-600 capitalize">{comp?.component_type ?? "—"}</td>
                        <td className="px-3 py-2">
                          <input
                            type="number" min={0} step="0.01"
                            value={row.amount}
                            onChange={e => updateStructureRow(idx, "amount", parseFloat(e.target.value) || 0)}
                            className="border border-gray-200 rounded px-2 py-1 text-sm text-right w-28 focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
                          />
                        </td>
                        <td className="px-3 py-2">
                          {comp && !comp.is_fixed ? (
                            <input
                              type="number" min={0} max={100} step="0.01"
                              value={row.pct_of_basic ?? ""}
                              onChange={e => updateStructureRow(idx, "pct_of_basic", e.target.value ? parseFloat(e.target.value) : null)}
                              className="border border-gray-200 rounded px-2 py-1 text-sm text-right w-20 focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
                            />
                          ) : <span className="text-gray-300">—</span>}
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="date"
                            value={row.effective_from ?? ""}
                            onChange={e => updateStructureRow(idx, "effective_from", e.target.value || null)}
                            className="border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="date"
                            value={row.effective_to ?? ""}
                            onChange={e => updateStructureRow(idx, "effective_to", e.target.value || null)}
                            className="border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <button
                            onClick={() => removeStructureRow(idx)}
                            className="text-red-400 hover:text-red-600"
                            title="Remove"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          <button
            onClick={saveStructure}
            disabled={savingStructure}
            className="px-6 py-2 bg-[#b8943f] text-white rounded-lg hover:opacity-90 text-sm font-medium disabled:opacity-50"
          >
            {savingStructure ? "Saving..." : "Save Salary Structure"}
          </button>
        </div>
      )}
    </div>
  )
}
