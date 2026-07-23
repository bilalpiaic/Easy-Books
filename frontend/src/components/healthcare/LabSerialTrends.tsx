"use client"

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js"
import { Line } from "react-chartjs-2"
import { fmtDate } from "@/lib/utils"
import LabResultFlag, { type LabFlag } from "@/components/healthcare/LabResultFlag"

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Filler, Tooltip, Legend)

export type HistoryPoint = {
  order_id: number
  order_number: string
  order_date: string
  result_value: string | null
  result_unit?: string | null
  reference_range?: string | null
  is_abnormal: boolean
  numeric_value: number | null
  is_current: boolean
  resulted_at?: string | null
  flag?: LabFlag
}

export type TrendItem = {
  test_id: number
  test_code?: string | null
  test_name: string
  result_unit?: string | null
  catalogue_unit?: string | null
  reference_range?: string | null
  catalogue_normal_range?: string | null
  reference_interval?: { low?: number; high?: number }
  history: HistoryPoint[]
}

type Props = {
  items: TrendItem[]
}

/** Numeric serial trend charts for repeat-patient analytes (CLSI cumulative). */
export default function LabSerialTrends({ items }: Props) {
  const chartable = items.filter(item => {
    const nums = (item.history || []).filter(p => p.numeric_value != null)
    return nums.length >= 2
  })
  const tableOnly = items.filter(item => {
    const hist = item.history || []
    const nums = hist.filter(p => p.numeric_value != null)
    return hist.length >= 2 && nums.length < 2
  })

  if (chartable.length === 0 && tableOnly.length === 0) return null

  return (
    <section className="space-y-4 break-inside-avoid">
      <div>
        <h2 className="text-base font-semibold text-neutral-900">
          Serial Results — Patient Trend
        </h2>
        <p className="text-xs text-neutral-500 mt-0.5">
          Cumulative prior results for this patient (ISO 15189 / CLSI-style serial reporting).
          Shaded band = reference interval where available.
        </p>
      </div>

      {chartable.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {chartable.map(item => (
            <TrendCard key={item.test_id} item={item} />
          ))}
        </div>
      )}

      {tableOnly.length > 0 && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <div className="px-4 py-2.5 bg-neutral-50 border-b border-neutral-200 text-xs font-semibold uppercase text-neutral-600">
            Qualitative serial history
          </div>
          <table className="w-full text-sm">
            <thead className="text-xs text-neutral-500 uppercase border-b border-neutral-100">
              <tr>
                <th className="text-left px-4 py-2">Test</th>
                <th className="text-left px-4 py-2">Date</th>
                <th className="text-left px-4 py-2">Result</th>
                <th className="text-left px-4 py-2">Flag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {tableOnly.flatMap(item =>
                item.history.map((p, idx) => (
                  <tr
                    key={`${item.test_id}-${p.order_id}-${idx}`}
                    className={p.is_current ? "bg-rose-50/50" : undefined}
                  >
                    <td className="px-4 py-2 font-medium">
                      {idx === 0 ? item.test_name : ""}
                    </td>
                    <td className="px-4 py-2 whitespace-nowrap">{fmtDate(p.order_date)}</td>
                    <td className={`px-4 py-2 ${p.is_abnormal ? "font-bold text-rose-800" : ""}`}>
                      {p.result_value}
                      {p.is_current && (
                        <span className="ml-1.5 text-[10px] uppercase text-rose-600 font-semibold">
                          current
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs">
                      <LabResultFlag
                        flag={p.flag ?? (p.is_abnormal
                          ? { code: "abnormal", label: "Abnormal", symbol: "!" }
                          : { code: "normal", label: "Normal", symbol: "N" })}
                        compact
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function TrendCard({ item }: { item: TrendItem }) {
  const points = item.history.filter(p => p.numeric_value != null)
  const labels = points.map(p => fmtDate(p.order_date))
  const values = points.map(p => p.numeric_value as number)
  const unit = item.result_unit || item.catalogue_unit || ""
  const interval = item.reference_interval || {}
  const low = interval.low
  const high = interval.high
  const hasBand = low != null || high != null

  // Pad y-scale so the band and points have breathing room
  const dataMin = Math.min(...values, ...(low != null ? [low] : []))
  const dataMax = Math.max(...values, ...(high != null ? [high] : []))
  const pad = (dataMax - dataMin) * 0.15 || 1

  const datasets: object[] = []
  if (hasBand) {
    const hiVals = points.map(() => (high != null ? high : dataMax + pad))
    const loVals = points.map(() => (low != null ? low : dataMin - pad))
    datasets.push({
      label: "Ref. high",
      data: hiVals,
      borderColor: "rgba(16,185,129,0.35)",
      borderDash: [4, 3],
      borderWidth: 1,
      pointRadius: 0,
      fill: "+1",
      backgroundColor: "rgba(16,185,129,0.12)",
      tension: 0,
      order: 2,
    })
    datasets.push({
      label: "Ref. low",
      data: loVals,
      borderColor: "rgba(16,185,129,0.35)",
      borderDash: [4, 3],
      borderWidth: 1,
      pointRadius: 0,
      fill: false,
      tension: 0,
      order: 2,
    })
  }
  datasets.push({
    label: unit ? `Result (${unit})` : "Result",
    data: values,
    borderColor: "#e11d48",
    backgroundColor: "#e11d48",
    borderWidth: 2,
    pointRadius: points.map(p => (p.is_current ? 5 : 3)),
    pointBackgroundColor: points.map(p => (p.is_abnormal ? "#be123c" : "#e11d48")),
    pointBorderColor: points.map(p => (p.is_current ? "#1a1814" : "#e11d48")),
    pointBorderWidth: points.map(p => (p.is_current ? 2 : 0)),
    tension: 0.25,
    fill: false,
    order: 1,
  })

  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4 break-inside-avoid">
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <div>
          <div className="text-sm font-semibold text-neutral-900">{item.test_name}</div>
          <div className="text-xs text-neutral-400">
            {[item.test_code, unit].filter(Boolean).join(" · ")}
            {(item.reference_range || item.catalogue_normal_range) &&
              ` · Ref ${item.reference_range || item.catalogue_normal_range}`}
          </div>
        </div>
        <div className="text-[10px] uppercase tracking-wide text-neutral-400 whitespace-nowrap">
          n={points.length}
        </div>
      </div>
      {/* Chart.js canvas prints blank — hide on print; under-chart table is the print surface */}
      <div className="h-40 print:hidden">
        <Line
          data={{ labels, datasets: datasets as never }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  afterLabel: (ctx) => {
                    if (ctx.datasetIndex !== datasets.length - 1) return ""
                    const p = points[ctx.dataIndex]
                    const bits = []
                    if (p?.is_current) bits.push("Current report")
                    if (p?.is_abnormal) bits.push("Abnormal")
                    if (p?.order_number) bits.push(p.order_number)
                    return bits.join(" · ")
                  },
                },
              },
            },
            scales: {
              x: {
                ticks: { font: { size: 10 }, maxRotation: 45 },
                grid: { display: false },
              },
              y: {
                min: dataMin - pad,
                max: dataMax + pad,
                ticks: { font: { size: 10 } },
                title: unit ? { display: true, text: unit, font: { size: 10 } } : undefined,
              },
            },
          }}
        />
      </div>
      {/* Compact prior table under chart — print-friendly (always shown; sole print surface for trends) */}
      <table className="w-full text-[11px] mt-2 border-t border-neutral-100 print:block">
        <thead>
          <tr className="text-neutral-400 uppercase">
            <th className="text-left py-1 font-medium">Date</th>
            <th className="text-right py-1 font-medium">Value</th>
            <th className="text-right py-1 font-medium">Flag</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p, i) => (
            <tr key={`${p.order_id}-${i}`} className={p.is_current ? "font-semibold text-rose-800" : "text-neutral-600"}>
              <td className="py-0.5 whitespace-nowrap">
                {fmtDate(p.order_date)}
                {p.is_current ? " *" : ""}
              </td>
              <td className={`py-0.5 text-right ${p.is_abnormal ? "text-rose-700" : ""}`}>
                {p.result_value}
              </td>
              <td className="py-0.5 text-right">
                <LabResultFlag
                  flag={p.flag ?? (p.is_abnormal
                    ? { code: "abnormal", label: "Abnormal", symbol: "!" }
                    : { code: "normal", label: "Within range", symbol: "N" })}
                  compact
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
