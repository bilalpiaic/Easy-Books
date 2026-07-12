"use client"
import { useState, useEffect } from "react"
import { BarChart2, TrendingUp, Activity, FlaskConical, BedDouble, PieChart } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import DateRangePicker from "@/components/DateRangePicker"

type Tab = "opd" | "doctors" | "lab" | "ipd" | "revenue"

export default function HcReportsPage() {
  const [tab, setTab] = useState<Tab>("revenue")
  const thisYear = new Date().getFullYear()
  const [from, setFrom] = useState(`${thisYear}-01-01`)
  const [to, setTo] = useState(`${thisYear}-12-31`)
  const [data, setData] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)

  async function loadReport() {
    setLoading(true)
    setData(null)
    const qs = new URLSearchParams({ from_date: from, to_date: to })
    const endpointMap: Record<Tab, string> = {
      opd: "opd-summary",
      doctors: "doctor-collections",
      lab: "lab-summary",
      ipd: "ipd-census",
      revenue: "revenue-by-type",
    }
    const res = await apiFetch(`/api/healthcare/reports/${endpointMap[tab]}?${qs}`).catch(() => null)
    if (res) setData(res)
    setLoading(false)
  }

  useEffect(() => { loadReport() }, [tab, from, to])

  const tabs = [
    { id: "revenue" as Tab, label: "Revenue by Type", icon: PieChart },
    { id: "opd" as Tab, label: "OPD Summary", icon: Activity },
    { id: "doctors" as Tab, label: "Doctor Collections", icon: TrendingUp },
    { id: "lab" as Tab, label: "Lab Summary", icon: FlaskConical },
    { id: "ipd" as Tab, label: "IPD Census", icon: BedDouble },
  ]

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between print:hidden">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Healthcare Reports</h1>
          <p className="text-sm text-neutral-500">Clinical & financial analytics</p>
        </div>
        <button onClick={() => window.print()}
          className="px-3 py-2 text-sm border border-neutral-200 rounded-lg hover:bg-neutral-50">
          Print
        </button>
      </div>

      {/* Date filter */}
      <div className="flex items-center gap-3 print:hidden">
        <DateRangePicker start={from} end={to} onStartChange={setFrom} onEndChange={setTo} hideAll />
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-neutral-200 print:hidden overflow-x-auto">
        {tabs.map(t => {
          const Icon = t.icon
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium whitespace-nowrap ${
                tab === t.id ? "border-b-2 border-rose-500 text-rose-600" : "text-neutral-600 hover:text-neutral-800"
              }`}>
              <Icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          )
        })}
      </div>

      {/* Report content */}
      {loading ? (
        <div className="text-sm text-neutral-400 py-8 text-center">Loading…</div>
      ) : (
        <ReportContent tab={tab} data={data} from={from} to={to} />
      )}
    </div>
  )
}

function ReportContent({ tab, data, from, to }: { tab: Tab; data: unknown; from: string; to: string }) {
  if (!data) return <div className="text-sm text-neutral-400">No data</div>

  if (tab === "revenue") {
    const d = data as { breakdown: Array<{ label: string; revenue: string; pct: number; account_code: string }>; total: string }
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Revenue by Type — {fmtDate(from)} to {fmtDate(to)}</h2>
        <div className="bg-white rounded-xl border border-neutral-200 table-freeze">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
              <tr>
                <th className="text-left px-4 py-3">Revenue Type</th>
                <th className="text-left px-4 py-3">Account</th>
                <th className="text-right px-4 py-3">Amount</th>
                <th className="text-right px-4 py-3">%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {d.breakdown?.map(r => (
                <tr key={r.account_code}>
                  <td className="px-4 py-3 font-medium">{r.label}</td>
                  <td className="px-4 py-3 text-neutral-500 font-mono text-xs">{r.account_code}</td>
                  <td className="px-4 py-3 text-right">{parseFloat(r.revenue).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-neutral-500">{r.pct}%</td>
                </tr>
              ))}
              <tr className="font-semibold border-t-2 border-neutral-300">
                <td className="px-4 py-3" colSpan={2}>Total Revenue</td>
                <td className="px-4 py-3 text-right">{parseFloat(String(d.total)).toLocaleString()}</td>
                <td className="px-4 py-3 text-right">100%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  if (tab === "doctors") {
    const rows = Array.isArray(data) ? data as Array<{ doctor_name: string; specialization?: string; total_visits: number; billed_visits: number; estimated_revenue: string }> : []
    return (
      <div className="bg-white rounded-xl border border-neutral-200 table-freeze">
        <div className="px-4 py-3 border-b border-neutral-100 font-medium text-sm">Doctor Collections — {fmtDate(from)} to {fmtDate(to)}</div>
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
            <tr>
              <th className="text-left px-4 py-3">Doctor</th>
              <th className="text-left px-4 py-3">Specialization</th>
              <th className="text-right px-4 py-3">Visits</th>
              <th className="text-right px-4 py-3">Billed</th>
              <th className="text-right px-4 py-3">Est. Revenue</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {rows?.map((r, i) => (
              <tr key={i}>
                <td className="px-4 py-3 font-medium">{r.doctor_name}</td>
                <td className="px-4 py-3 text-neutral-500">{r.specialization || "—"}</td>
                <td className="px-4 py-3 text-right">{r.total_visits}</td>
                <td className="px-4 py-3 text-right">{r.billed_visits}</td>
                <td className="px-4 py-3 text-right">{parseFloat(r.estimated_revenue).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (tab === "lab") {
    const d = data as { by_status: Record<string, number>; by_source: Record<string, number>; total: number }
    return (
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-neutral-200 p-4">
          <h3 className="font-medium text-sm mb-3">Orders by Status</h3>
          <div className="space-y-2">
            {Object.entries(d.by_status ?? {}).map(([s, c]) => (
              <div key={s} className="flex justify-between text-sm">
                <span className="capitalize text-neutral-600">{s.replace("_", " ")}</span>
                <span className="font-medium">{c}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-neutral-200 p-4">
          <h3 className="font-medium text-sm mb-3">Orders by Source</h3>
          <div className="space-y-2">
            {Object.entries(d.by_source ?? {}).map(([s, c]) => (
              <div key={s} className="flex justify-between text-sm">
                <span className="capitalize text-neutral-600">{s.replace("_", " ")}</span>
                <span className="font-medium">{c}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="col-span-2 bg-neutral-50 rounded-xl border border-neutral-200 p-4 text-center">
          <div className="text-3xl font-bold text-neutral-900">{d.total}</div>
          <div className="text-sm text-neutral-500">Total Lab Orders</div>
        </div>
      </div>
    )
  }

  if (tab === "ipd") {
    const rows = Array.isArray(data) ? data as Array<{ ward_name: string; ward_type: string; admissions: number; discharges: number; avg_length_of_stay_days: number; occupied_beds: number; total_beds: number }> : []
    return (
      <div className="bg-white rounded-xl border border-neutral-200 table-freeze">
        <div className="px-4 py-3 border-b border-neutral-100 font-medium text-sm">IPD Census — {fmtDate(from)} to {fmtDate(to)}</div>
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
            <tr>
              <th className="text-left px-4 py-3">Ward</th>
              <th className="text-left px-4 py-3">Type</th>
              <th className="text-right px-4 py-3">Beds</th>
              <th className="text-right px-4 py-3">Admissions</th>
              <th className="text-right px-4 py-3">Discharges</th>
              <th className="text-right px-4 py-3">Avg LOS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {rows?.map((r, i) => (
              <tr key={i}>
                <td className="px-4 py-3 font-medium">{r.ward_name}</td>
                <td className="px-4 py-3 capitalize text-neutral-500">{r.ward_type}</td>
                <td className="px-4 py-3 text-right">{r.occupied_beds}/{r.total_beds}</td>
                <td className="px-4 py-3 text-right">{r.admissions}</td>
                <td className="px-4 py-3 text-right">{r.discharges}</td>
                <td className="px-4 py-3 text-right">{r.avg_length_of_stay_days} days</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  // OPD summary
  if (tab !== "opd") return null
  const rows = Array.isArray(data) ? data as Array<{ doctor: string; date: string; visits: number }> : []
  return (
    <div className="bg-white rounded-xl border border-neutral-200 table-freeze">
      <div className="px-4 py-3 border-b border-neutral-100 font-medium text-sm">OPD Summary</div>
      <table className="w-full text-sm">
        <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase">
          <tr>
            <th className="text-left px-4 py-3">Doctor</th>
            <th className="text-left px-4 py-3">Date</th>
            <th className="text-right px-4 py-3">Visits</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {rows?.map((r, i) => (
            <tr key={i}>
              <td className="px-4 py-3">{r.doctor}</td>
              <td className="px-4 py-3 whitespace-nowrap">{fmtDate(r.date)}</td>
              <td className="px-4 py-3 text-right">{r.visits}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
