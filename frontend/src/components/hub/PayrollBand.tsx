"use client"
import Link from "next/link"
import { useFmt } from "@/context/SettingsContext"
import { fmtDate } from "@/lib/utils"

export interface PayrollRunRow {
  id: number
  jv_number: string | null
  period_start: string
  period_end: string
  pay_date: string
  status: string
  total_net_pay: number
  total_lines: number
}

export interface PayrollBandProps {
  runs: PayrollRunRow[]
}

const STATUS_COLOR: Record<string, string> = {
  draft:    "text-gray-400",
  approved: "text-blue-600",
  posted:   "text-emerald-600",
  void:     "text-red-400",
}

export default function PayrollBand({ runs }: PayrollBandProps) {
  const fmt = useFmt()

  return (
    <div className="bg-white rounded-xl p-3">
      <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/40 mb-2">
        Recent Payroll Runs
      </div>
      {runs.length === 0 ? (
        <p className="text-xs text-[#1a1814]/40 py-2 text-center">No payroll runs yet</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {runs.map(run => (
            <div key={run.id} className="flex items-center justify-between bg-[#f8f5ef] rounded-lg px-2.5 py-1.5 gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-mono text-[10px] text-[#1a1814]/60 shrink-0">
                  {run.jv_number ?? `#${run.id}`}
                </span>
                <span className="text-xs text-[#1a1814]/70 truncate">
                  {fmtDate(run.period_start)} – {fmtDate(run.period_end)}
                </span>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className={`text-[10px] font-medium capitalize ${STATUS_COLOR[run.status] ?? ""}`}>
                  {run.status}
                </span>
                <span className="text-xs font-bold text-[#1a1814]">{fmt(run.total_net_pay)}</span>
                <Link href={`/payroll/${run.id}`} className="text-[10px] text-[#b8943f] hover:underline">
                  View
                </Link>
              </div>
            </div>
          ))}
          <Link href="/payroll" className="text-[10px] text-[#b8943f] hover:underline text-right mt-0.5">
            All runs →
          </Link>
        </div>
      )}
    </div>
  )
}
