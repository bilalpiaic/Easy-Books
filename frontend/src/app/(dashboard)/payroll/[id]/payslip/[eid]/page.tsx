"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt, useCurrency, useSettings } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface PayslipData {
  run: {
    id: number
    period_start: string
    period_end: string
    pay_date: string
    jv_number: string | null
    status: string
  }
  employee: {
    id: number
    employee_code: string
    name: string
    department: string | null
    designation: string | null
    bank_account: string | null
    bank_name: string | null
  }
  earnings: { name: string; code: string; amount: number }[]
  deductions: { name: string; code: string; amount: number }[]
  gross_earnings: number
  total_deductions: number
  net_pay: number
}

export default function PayslipPage() {
  const { t } = useTranslation()
  const params = useParams()
  const runId = params.id as string
  const eid = params.eid as string
  const fmt = useFmt()
  const currency = useCurrency()
  const { settings } = useSettings()

  const [data, setData] = useState<PayslipData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    apiFetch<PayslipData>(`/api/payroll/runs/${runId}/payslip/${eid}`)
      .then(setData)
      .catch(() => setError("Failed to load payslip"))
      .finally(() => setLoading(false))
  }, [runId, eid])

  if (loading) return <div className="p-8 text-gray-400">Loading...</div>
  if (!data) return <div className="p-8 text-red-500">{error || "Payslip not found"}</div>

  return (
    <div className="max-w-2xl space-y-4">
      <PrintHeader title="Pay Slip" />

      <div className="print:hidden flex items-center justify-between">
        <Link href={`/payroll/${runId}`} className="inline-flex items-center gap-2 text-[#b8943f] hover:underline text-sm">
          <ArrowLeft className="w-4 h-4" />
          Back to Payroll Run
        </Link>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
        >
          <Printer className="w-4 h-4" /> Print
        </button>
      </div>

      {/* Payslip document */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-6 print:shadow-none print:border-none print:rounded-none">
        {/* Header */}
        <div className="border-b border-gray-200 pb-4">
          <h2 className="text-lg font-bold text-[#1a1814]">{settings.company_name}</h2>
          <p className="text-xs text-gray-400">{settings.business_tagline}</p>
        </div>

        <div className="text-center">
          <h3 className="text-xl font-bold text-[#1a1814]">PAY SLIP</h3>
          <p className="text-sm text-gray-500">
            Period: {fmtDate(data.run.period_start)} to {fmtDate(data.run.period_end)}
          </p>
        </div>

        {/* Employee info */}
        <div className="grid grid-cols-2 gap-4 bg-[#f6f3ee] rounded-lg p-4 text-sm">
          <div>
            <p><span className="text-gray-500">Name:</span> <strong>{data.employee.name}</strong></p>
            <p><span className="text-gray-500">Code:</span> {data.employee.employee_code}</p>
            <p><span className="text-gray-500">Department:</span> {data.employee.department ?? "—"}</p>
          </div>
          <div>
            <p><span className="text-gray-500">Designation:</span> {data.employee.designation ?? "—"}</p>
            <p><span className="text-gray-500">Pay Date:</span> {fmtDate(data.run.pay_date)}</p>
            <p><span className="text-gray-500">Bank:</span> {data.employee.bank_name ?? "—"}</p>
          </div>
        </div>

        {/* Earnings and Deductions */}
        <div className="grid grid-cols-2 gap-6">
          {/* Earnings */}
          <div>
            <h4 className="font-semibold text-[#1a1814] border-b border-gray-200 pb-2 mb-3">Earnings ({currency})</h4>
            <table className="w-full text-sm">
              <tbody className="divide-y divide-gray-50">
                {data.earnings.map((e, i) => (
                  <tr key={i}>
                    <td className="py-1.5 text-gray-600">{e.name}</td>
                    <td className="py-1.5 text-right font-medium">{fmt(e.amount)}</td>
                  </tr>
                ))}
                {data.earnings.length === 0 && (
                  <tr><td colSpan={2} className="py-2 text-gray-300 text-xs">No earnings</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Deductions */}
          <div>
            <h4 className="font-semibold text-[#1a1814] border-b border-gray-200 pb-2 mb-3">Deductions ({currency})</h4>
            <table className="w-full text-sm">
              <tbody className="divide-y divide-gray-50">
                {data.deductions.map((d, i) => (
                  <tr key={i}>
                    <td className="py-1.5 text-gray-600">{d.name}</td>
                    <td className="py-1.5 text-right font-medium">{fmt(d.amount)}</td>
                  </tr>
                ))}
                {data.deductions.length === 0 && (
                  <tr><td colSpan={2} className="py-2 text-gray-300 text-xs">No deductions</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Summary */}
        <div className="border-t-2 border-gray-200 pt-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Gross Earnings</span>
            <span className="font-medium">{currency} {fmt(data.gross_earnings)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Total Deductions</span>
            <span className="font-medium text-red-500">{currency} {fmt(data.total_deductions)}</span>
          </div>
          <div className="flex justify-between items-center bg-[#b8943f]/10 rounded-lg px-3 py-2 border border-[#b8943f]/20">
            <span className="font-bold text-[#1a1814]">Net Pay</span>
            <span className="font-bold text-[#b8943f] text-lg">{currency} {fmt(data.net_pay)}</span>
          </div>
        </div>

        {data.employee.bank_account && (
          <p className="text-xs text-gray-400">
            Bank Account: {data.employee.bank_account} · {data.employee.bank_name}
          </p>
        )}
      </div>
    </div>
  )
}
