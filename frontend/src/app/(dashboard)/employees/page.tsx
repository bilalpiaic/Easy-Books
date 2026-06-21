"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Users, Plus, Search, Edit2 } from "lucide-react"
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

  return (
    <div className="space-y-4">
      <PrintHeader title="Employees" />

      <div className="print:hidden flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-xl sm:text-3xl font-bold text-[#1a1814]">
          {t("Employees")}
        </h1>
        <Link
          href="/employees/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:opacity-90 text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          New Employee
        </Link>
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
            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm bg-white border-gray-200 focus:outline-none focus:ring-2 focus:ring-[#b8943f]/30"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowActive(false)}
            className={`px-3 py-2 rounded-lg text-sm font-medium border ${!showActive ? "bg-[#b8943f] text-white border-[#b8943f]" : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"}`}
          >
            All
          </button>
          <button
            onClick={() => setShowActive(true)}
            className={`px-3 py-2 rounded-lg text-sm font-medium border ${showActive ? "bg-[#b8943f] text-white border-[#b8943f]" : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"}`}
          >
            Active
          </button>
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-gray-100">
            <tr>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Code</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Name</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Department</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Designation</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Join Date</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Status</th>
              <th className="text-left px-4 py-3 font-semibold text-[#1a1814] print:hidden">Actions</th>
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
              <tr key={emp.id} className="hover:bg-[#f6f3ee]/50 transition-colors">
                <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{emp.employee_code}</td>
                <td className="px-4 py-3 font-medium text-[#1a1814]">{emp.name}</td>
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
                    className="inline-flex items-center gap-1 text-[#b8943f] hover:underline text-xs font-medium"
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
