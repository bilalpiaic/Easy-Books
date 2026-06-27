"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Users, Plus, Search, Edit2, Home, Printer, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface Employee {
  id: number
  employee_code: string
  name: string
  department: string | null
  designation: string | null
  join_date: string | null
  is_active: boolean
}

export default function EmployeesPage() {
  const { t } = useTranslation()
  const [employees, setEmployees] = useState<Employee[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [search, setSearch] = useState("")
  const [showActive, setShowActive] = useState(false)

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (showActive) params.set("active_only", "true")
    if (search) params.set("search", search)
    apiFetch<Employee[]>(`/api/employees?${params}`)
      .then(setEmployees)
      .catch(() => setError("Failed to load employees"))
      .finally(() => setLoading(false))
  }, [search, showActive])

  function exportCsv() {
    const header = ["Code", "Name", "Department", "Designation", "Join Date", "Status"]
    const rows = employees.map(e => [
      e.employee_code, e.name,
      e.department ?? "", e.designation ?? "",
      e.join_date ? fmtDate(e.join_date) : "",
      e.is_active ? "Active" : "Inactive",
    ])
    const csv = [header, ...rows].map(row => row.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n")
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(new Blob([csv], { type: "text/csv" })),
      download: "employees.csv",
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="space-y-4">
      <PrintHeader title="Employees" />

      <div className="print:hidden flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <Link href="/dashboard" className="inline-flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-[var(--primary)] mb-1 transition-colors">
            <Home className="w-3 h-3" /> Dashboard
          </Link>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">
            {t("Employees")}
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-3 py-2 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 text-sm">
            <Printer className="w-4 h-4" /> Print
          </button>
          <button onClick={exportCsv}
            className="inline-flex items-center gap-2 px-3 py-2 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 text-sm">
            <Download className="w-4 h-4" /> Export CSV
          </button>
          <Link
            href="/employees/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg hover:opacity-90 text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Employee
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="print:hidden flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or code..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm bg-white border-gray-200 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowActive(false)}
            className={`px-3 py-2 rounded-lg text-sm font-medium border ${!showActive ? "bg-[var(--primary)] text-white border-[var(--primary)]" : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"}`}
          >
            All
          </button>
          <button
            onClick={() => setShowActive(true)}
            className={`px-3 py-2 rounded-lg text-sm font-medium border ${showActive ? "bg-[var(--primary)] text-white border-[var(--primary)]" : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"}`}
          >
            Active
          </button>
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-page)] border-b border-gray-100">
            <tr>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]">Code</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]">Name</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]">Department</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]">Designation</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]">Join Date</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)]">Status</th>
              <th className="text-left px-4 py-3 font-semibold text-[var(--text-primary)] print:hidden">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">Loading...</td>
              </tr>
            ) : employees.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  <Users className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  No employees found
                </td>
              </tr>
            ) : employees.map(emp => (
              <tr key={emp.id} className="hover:bg-[var(--bg-page)]/50 transition-colors">
                <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{emp.employee_code}</td>
                <td className="px-4 py-3 font-medium text-[var(--text-primary)]">{emp.name}</td>
                <td className="px-4 py-3 text-gray-600">{emp.department ?? "—"}</td>
                <td className="px-4 py-3 text-gray-600">{emp.designation ?? "—"}</td>
                <td className="px-4 py-3 whitespace-nowrap text-gray-600">
                  {emp.join_date ? fmtDate(emp.join_date) : "—"}
                </td>
                <td className="px-4 py-3">
                  <span className={emp.is_active ? "text-emerald-600 font-medium" : "text-gray-400"}>
                    {emp.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-4 py-3 print:hidden">
                  <Link
                    href={`/employees/${emp.id}/edit`}
                    className="inline-flex items-center gap-1 text-[var(--primary)] hover:underline text-xs font-medium"
                  >
                    <Edit2 className="w-3 h-3" />
                    Edit
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
