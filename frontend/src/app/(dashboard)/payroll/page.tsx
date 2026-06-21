"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Users, Plus, Settings2, CalendarDays, DollarSign, ClipboardList, Home, Printer, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt, useCurrency } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface PayrollRun {
  id: number
  period_start: string
  period_end: string
  pay_date: string
  status: string
  jv_number: string | null
  total_lines: number
  total_net_pay: number
  created_at: string | null
}

interface EmployeeItem {
  id: number
  is_active: boolean
}

const STATUS_COLOR: Record<string, string> = {
  draft:    "text-gray-500",
  approved: "text-blue-600",
  posted:   "text-emerald-600",
  void:     "text-red-400",
}

export default function PayrollHubPage() {
  const { t } = useTranslation()
  const fmt = useFmt()
  const currency = useCurrency()

  const [runs, setRuns] = useState<PayrollRun[]>([])
  const [empCount, setEmpCount] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      apiFetch<PayrollRun[]>("/api/payroll/runs"),
      apiFetch<EmployeeItem[]>("/api/employees?active_only=true"),
    ]).then(([runsData, empsData]) => {
      setRuns(Array.isArray(runsData) ? runsData : [])
      setEmpCount(Array.isArray(empsData) ? empsData.length : 0)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const lastPosted = runs.find(r => r.status === "posted")
  const draftCount = runs.filter(r => r.status === "draft").length
  const recentRuns = runs.slice(0, 10)

  function exportCsv() {
    const header = ["Run #", "Period Start", "Period End", "Pay Date", "Employees", "Net Pay", "Status"]
    const rows = runs.map(r => [
      r.jv_number ?? `#${r.id}`,
      r.period_start, r.period_end, r.pay_date,
      r.total_lines, r.total_net_pay, r.status,
    ])
    const csv = [header, ...rows].map(row => row.join(",")).join("\n")
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(new Blob([csv], { type: "text/csv" })),
      download: "payroll_runs.csv",
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="space-y-6">
      <PrintHeader title="Payroll" />

      <div className="print:hidden flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <Link href="/dashboard" className="inline-flex items-center gap-1 text-xs text-black/45 hover:text-[#b8943f] mb-1 transition-colors">
            <Home className="w-3 h-3" /> Dashboard
          </Link>
          <h1 className="text-xl sm:text-3xl font-bold text-[#1a1814]">{t("Payroll")}</h1>
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
            href="/payroll/components"
            className="inline-flex items-center gap-2 px-4 py-2 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 text-sm font-medium"
          >
            <Settings2 className="w-4 h-4" />
            Salary Components
          </Link>
          <Link
            href="/payroll/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:opacity-90 text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Payroll Run
          </Link>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#b8943f]/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-[#b8943f]" />
            </div>
            <div>
              <p className="text-xs text-gray-500">Active Employees</p>
              <p className="text-2xl font-bold text-[#1a1814]">{empCount}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <CalendarDays className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <p className="text-xs text-gray-500">Last Run</p>
              <p className="text-sm font-bold text-[#1a1814]">
                {lastPosted ? fmtDate(lastPosted.pay_date) : "—"}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center">
              <DollarSign className="w-5 h-5 text-emerald-500" />
            </div>
            <div>
              <p className="text-xs text-gray-500">Last Net Pay ({currency})</p>
              <p className="text-sm font-bold text-[#1a1814]">
                {lastPosted ? fmt(lastPosted.total_net_pay) : "—"}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center">
              <ClipboardList className="w-5 h-5 text-amber-500" />
            </div>
            <div>
              <p className="text-xs text-gray-500">Pending Drafts</p>
              <p className="text-2xl font-bold text-[#1a1814]">{draftCount}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Recent runs */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-[#1a1814]">Recent Payroll Runs</h3>
          <Link href="/employees" className="text-sm text-[#b8943f] hover:underline">
            Manage Employees →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#f6f3ee]">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-[#1a1814] whitespace-nowrap">Run #</th>
                <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Period</th>
                <th className="text-left px-4 py-3 font-semibold text-[#1a1814] whitespace-nowrap">Pay Date</th>
                <th className="text-right px-4 py-3 font-semibold text-[#1a1814]">Employees</th>
                <th className="text-right px-4 py-3 font-semibold text-[#1a1814]">Net Pay ({currency})</th>
                <th className="text-left px-4 py-3 font-semibold text-[#1a1814]">Status</th>
                <th className="text-left px-4 py-3 font-semibold text-[#1a1814] print:hidden"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
              ) : recentRuns.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No payroll runs yet</td></tr>
              ) : recentRuns.map(run => (
                <tr key={run.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{run.jv_number ?? `#${run.id}`}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {fmtDate(run.period_start)} – {fmtDate(run.period_end)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-gray-600">{fmtDate(run.pay_date)}</td>
                  <td className="px-4 py-3 text-right">{run.total_lines}</td>
                  <td className="px-4 py-3 text-right font-medium">{fmt(run.total_net_pay)}</td>
                  <td className="px-4 py-3">
                    <span className={`capitalize font-medium ${STATUS_COLOR[run.status] ?? ""}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 print:hidden">
                    <Link href={`/payroll/${run.id}`} className="text-[#b8943f] hover:underline text-xs font-medium">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
