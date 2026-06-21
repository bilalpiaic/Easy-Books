"use client"

import { useEffect, useState } from "react"
import { Plus, Edit2, Trash2, Check, X } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

interface Account {
  id: number
  code: string
  name: string
  type: string
}

interface AccountsResponse {
  items?: Account[]
  accounts?: Account[]
}

interface SalaryComponent {
  id: number
  name: string
  code: string
  component_type: string
  is_taxable: boolean
  is_fixed: boolean
  gl_account_id: number | null
  is_active: boolean
}

type EditRow = Omit<SalaryComponent, "id"> & { id?: number }

const TYPE_LABEL: Record<string, string> = {
  earnings: "Earnings",
  deductions: "Deductions",
  statutory: "Statutory",
}

const emptyRow = (): EditRow => ({
  name: "",
  code: "",
  component_type: "earnings",
  is_taxable: false,
  is_fixed: true,
  gl_account_id: null,
  is_active: true,
})

export default function SalaryComponentsPage() {
  const { t } = useTranslation()
  const [components, setComponents] = useState<SalaryComponent[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | "new" | null>(null)
  const [editRow, setEditRow] = useState<EditRow>(emptyRow())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const loadData = () => {
    Promise.all([
      apiFetch<SalaryComponent[]>("/api/payroll/components"),
      apiFetch<AccountsResponse | Account[]>("/api/accounts"),
    ]).then(([comps, accts]) => {
      setComponents(Array.isArray(comps) ? comps : [])
      const allAccts: Account[] = Array.isArray(accts)
        ? accts
        : ((accts as AccountsResponse).items ?? (accts as AccountsResponse).accounts ?? [])
      setAccounts(allAccts.filter((a: Account) => a.type === "expense" || a.type === "liability" || a.type === "Expense" || a.type === "Liability"))
    }).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [])

  const startNew = () => {
    setEditRow(emptyRow())
    setEditingId("new")
    setError("")
  }

  const startEdit = (comp: SalaryComponent) => {
    setEditRow({ ...comp })
    setEditingId(comp.id)
    setError("")
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditRow(emptyRow())
    setError("")
  }

  const save = async () => {
    if (!editRow.name || !editRow.code) { setError("Name and code are required"); return }
    setSaving(true)
    setError("")
    try {
      const isNew = editingId === "new"
      await apiFetch(
        isNew ? "/api/payroll/components" : `/api/payroll/components/${editingId}`,
        {
          method: isNew ? "POST" : "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(editRow),
        }
      )
      cancelEdit()
      loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSaving(false)
    }
  }

  const deleteComp = async (id: number) => {
    if (!confirm("Delete this component?")) return
    setError("")
    try {
      await apiFetch(`/api/payroll/components/${id}`, { method: "DELETE" })
      loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete")
    }
  }

  const updateEdit = (field: keyof EditRow, value: string | number | boolean | null) =>
    setEditRow(prev => ({ ...prev, [field]: value }))

  const renderEditRow = () => (
    <tr className="bg-[#b8943f]/5 border-b-2 border-[#b8943f]/20">
      <td className="px-4 py-2">
        <input
          autoFocus
          value={editRow.name} onChange={e => updateEdit("name", e.target.value)}
          placeholder="e.g. Basic Salary"
          className="w-full border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
        />
      </td>
      <td className="px-4 py-2">
        <input
          value={editRow.code} onChange={e => updateEdit("code", e.target.value.toUpperCase())}
          placeholder="BASIC"
          className="w-full border border-gray-200 rounded px-2 py-1 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
        />
      </td>
      <td className="px-4 py-2">
        <select
          value={editRow.component_type} onChange={e => updateEdit("component_type", e.target.value)}
          className="border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
        >
          <option value="earnings">Earnings</option>
          <option value="deductions">Deductions</option>
          <option value="statutory">Statutory</option>
        </select>
      </td>
      <td className="px-4 py-2 text-center">
        <input
          type="checkbox" checked={editRow.is_taxable}
          onChange={e => updateEdit("is_taxable", e.target.checked)}
          className="w-4 h-4 accent-[#b8943f]"
        />
      </td>
      <td className="px-4 py-2 text-center">
        <input
          type="checkbox" checked={editRow.is_fixed}
          onChange={e => updateEdit("is_fixed", e.target.checked)}
          className="w-4 h-4 accent-[#b8943f]"
        />
      </td>
      <td className="px-4 py-2">
        <select
          value={editRow.gl_account_id ?? ""}
          onChange={e => updateEdit("gl_account_id", e.target.value ? parseInt(e.target.value) : null)}
          className="border border-gray-200 rounded px-2 py-1 text-sm w-full focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
        >
          <option value="">— None —</option>
          {accounts.map(a => (
            <option key={a.id} value={a.id}>{a.code} {a.name}</option>
          ))}
        </select>
      </td>
      <td className="px-4 py-2 text-center">
        <input
          type="checkbox" checked={editRow.is_active}
          onChange={e => updateEdit("is_active", e.target.checked)}
          className="w-4 h-4 accent-[#b8943f]"
        />
      </td>
      <td className="px-4 py-2">
        <div className="flex gap-1">
          <button
            onClick={save} disabled={saving}
            className="text-emerald-600 hover:text-emerald-700 disabled:opacity-50"
            title="Save"
          >
            <Check className="w-4 h-4" />
          </button>
          <button onClick={cancelEdit} className="text-gray-400 hover:text-gray-600" title="Cancel">
            <X className="w-4 h-4" />
          </button>
        </div>
      </td>
    </tr>
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-xl sm:text-3xl font-bold text-[#1a1814]">{t("Salary Components")}</h1>
        <button
          onClick={startNew}
          disabled={editingId !== null}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:opacity-90 text-sm font-medium disabled:opacity-50"
        >
          <Plus className="w-4 h-4" />
          New Component
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-gray-100">
            <tr>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Name</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Code</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Type</th>
              <th className="text-center px-4 py-3 font-semibold text-[#1a1814]">Taxable</th>
              <th className="text-center px-4 py-3 font-semibold text-[#1a1814]">Fixed</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">GL Account</th>
              <th className="text-center px-4 py-3 font-semibold text-[#1a1814]">Active</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {editingId === "new" && renderEditRow()}
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            ) : components.length === 0 && editingId !== "new" ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                  No salary components yet. Click &quot;New Component&quot; to add one.
                </td>
              </tr>
            ) : components.map(comp => (
              editingId === comp.id ? (
                renderEditRow()
              ) : (
                <tr key={comp.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="px-4 py-3 font-medium text-[#1a1814]">{comp.name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{comp.code}</td>
                  <td className="px-4 py-3 text-gray-600">{TYPE_LABEL[comp.component_type] ?? comp.component_type}</td>
                  <td className="px-4 py-3 text-center">
                    {comp.is_taxable ? <span className="text-emerald-600 font-medium">Yes</span> : <span className="text-gray-300">No</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {comp.is_fixed ? <span className="text-gray-600">Fixed</span> : <span className="text-blue-500">% Basic</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {accounts.find(a => a.id === comp.gl_account_id)?.name ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {comp.is_active ? <span className="text-emerald-600">Yes</span> : <span className="text-gray-300">No</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => startEdit(comp)}
                        className="text-[#b8943f] hover:underline text-xs font-medium inline-flex items-center gap-1"
                      >
                        <Edit2 className="w-3 h-3" /> Edit
                      </button>
                      <button
                        onClick={() => deleteComp(comp.id)}
                        className="text-red-400 hover:text-red-600 text-xs inline-flex items-center gap-1"
                      >
                        <Trash2 className="w-3 h-3" /> Delete
                      </button>
                    </div>
                  </td>
                </tr>
              )
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
