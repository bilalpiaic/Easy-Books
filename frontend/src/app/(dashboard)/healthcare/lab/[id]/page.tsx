"use client"

import { use, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { ArrowLeft, Printer, Save } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { StatusBadge } from "@/components/healthcare/primitives"
import LabSerialTrends from "@/components/healthcare/LabSerialTrends"
import LabResultFlag, {
  classifyLabFlag,
  isAbnormalFlag,
  type LabFlag,
} from "@/components/healthcare/LabResultFlag"

type PatientInfo = {
  id: number
  name: string
  mr_number: string
  gender: string
  dob?: string | null
  age?: number | null
  phone?: string | null
  blood_group?: string | null
}

type DoctorInfo = {
  id: number
  name: string
  specialization?: string | null
}

type SampleInfo = {
  id: number
  collected_at?: string | null
  collection_point: string
  specimen_type: string
  barcode?: string | null
  status: string
}

type HistoryPoint = {
  order_id: number
  order_number: string
  order_date: string
  result_value: string | null
  result_unit?: string | null
  is_abnormal: boolean
  numeric_value: number | null
  is_current: boolean
  flag?: LabFlag
}

type LabItem = {
  id: number
  test_id: number
  test_code?: string | null
  test_name: string
  category: string
  fee: number | string
  result_value?: string | null
  result_unit?: string | null
  reference_range?: string | null
  is_abnormal: boolean
  resulted_at?: string | null
  catalogue_unit?: string | null
  catalogue_normal_range?: string | null
  reference_interval?: { low?: number; high?: number }
  flag?: LabFlag
  previous_result?: HistoryPoint | null
  history?: HistoryPoint[]
}

type LabOrderDetail = {
  id: number
  order_number: string
  order_date: string
  source: string
  status: string
  patient_id: number
  doctor_id?: number | null
  patient: PatientInfo | null
  doctor: DoctorInfo | null
  sample: SampleInfo | null
  items: LabItem[]
}

type DraftResult = {
  result_value: string
  result_unit: string
  reference_range: string
  is_abnormal: boolean
}

const CATEGORY_LABELS: Record<string, string> = {
  hematology: "Hematology",
  biochemistry: "Biochemistry",
  microbiology: "Microbiology",
  radiology: "Radiology",
  other: "Other",
}

function draftFromItem(item: LabItem): DraftResult {
  return {
    result_value: item.result_value ?? "",
    result_unit: item.result_unit || item.catalogue_unit || "",
    reference_range: item.reference_range || item.catalogue_normal_range || "",
    is_abnormal: item.is_abnormal,
  }
}

export default function LabOrderReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [order, setOrder] = useState<LabOrderDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [msg, setMsg] = useState("")
  const [drafts, setDrafts] = useState<Record<number, DraftResult>>({})
  const [savingId, setSavingId] = useState<number | null>(null)
  const [delivering, setDelivering] = useState(false)

  async function load() {
    setLoading(true)
    setError("")
    try {
      const data = await apiFetch<LabOrderDetail>(`/api/healthcare/lab/orders/${id}`)
      setOrder(data)
      const next: Record<number, DraftResult> = {}
      for (const item of data.items) {
        if (!item.resulted_at) next[item.id] = draftFromItem(item)
      }
      setDrafts(next)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load lab order")
      setOrder(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const grouped = useMemo(() => {
    if (!order) return [] as [string, LabItem[]][]
    const map = new Map<string, LabItem[]>()
    for (const item of order.items) {
      const key = item.category || "other"
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(item)
    }
    return Array.from(map.entries())
  }, [order])

  const pendingCount = order?.items.filter(i => !i.resulted_at).length ?? 0
  const canPrint = (order?.items.length ?? 0) > 0 && pendingCount === 0
  const canDeliver = order?.status === "resulted"

  const trendItems = useMemo(() => {
    if (!order) return []
    return order.items
      .filter(i => (i.history?.length ?? 0) >= 2)
      .map(i => ({
        test_id: i.test_id,
        test_code: i.test_code,
        test_name: i.test_name,
        result_unit: i.result_unit,
        catalogue_unit: i.catalogue_unit,
        reference_range: i.reference_range,
        catalogue_normal_range: i.catalogue_normal_range,
        reference_interval: i.reference_interval,
        history: i.history ?? [],
      }))
  }, [order])

  async function saveResult(item: LabItem) {
    const draft = drafts[item.id]
    if (!draft || !draft.result_value.trim()) {
      setMsg("Enter a result value before saving")
      return
    }
    setSavingId(item.id)
    setMsg("")
    try {
      await apiFetch(`/api/healthcare/lab/orders/${id}/items/${item.id}/result`, {
        method: "PUT",
        body: JSON.stringify({
          result_value: draft.result_value.trim(),
          result_unit: draft.result_unit.trim() || null,
          reference_range: draft.reference_range.trim() || null,
          is_abnormal: draft.is_abnormal,
        }),
      })
      setMsg("Result saved")
      await load()
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Failed to save result")
    } finally {
      setSavingId(null)
    }
  }

  async function deliver() {
    setDelivering(true)
    setMsg("")
    try {
      await apiFetch(`/api/healthcare/lab/orders/${id}/deliver`, { method: "PUT" })
      setMsg("Results marked as delivered")
      await load()
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Failed to deliver")
    } finally {
      setDelivering(false)
    }
  }

  if (loading) return <div className="p-6 text-neutral-400">Loading lab report…</div>
  if (!order) return <div className="p-6 text-red-600">{error || "Lab order not found"}</div>

  const patient = order.patient
  const subtitle = `${order.order_number} · ${fmtDate(order.order_date)}`

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <PrintHeader title="Laboratory Test Report" subtitle={subtitle} />

      <div className="print:hidden flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/healthcare/lab"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-600 hover:text-rose-600"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Laboratory
        </Link>
        <div className="flex items-center gap-2">
          {canDeliver && (
            <button
              onClick={deliver}
              disabled={delivering}
              className="px-3 py-2 text-sm border border-green-200 text-green-700 bg-green-50 rounded-lg hover:bg-green-100 disabled:opacity-50"
            >
              {delivering ? "Delivering…" : "Mark Delivered"}
            </button>
          )}
          <button
            onClick={() => window.print()}
            disabled={!canPrint}
            title={canPrint ? "Print report" : "Enter all results before printing"}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm bg-rose-500 text-white rounded-lg hover:bg-rose-600 disabled:opacity-50"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
      </div>

      {msg && (
        <div className={`print:hidden text-sm p-3 rounded-lg ${
          msg.toLowerCase().includes("fail") || msg.toLowerCase().includes("enter")
            ? "bg-amber-50 text-amber-800"
            : "bg-green-50 text-green-700"
        }`}>
          {msg}
        </div>
      )}

      {/* Screen title */}
      <div className="print:hidden">
        <h1 className="text-2xl font-semibold text-neutral-900">Laboratory Test Report</h1>
        <p className="text-sm text-neutral-500 mt-0.5">{subtitle}</p>
      </div>

      {/* Patient + order meta */}
      <div className="bg-white rounded-xl border border-neutral-200 p-5 grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
        <Meta label="Patient" value={patient?.name ?? "—"} bold />
        <Meta label="MR Number" value={patient?.mr_number ?? "—"} />
        <Meta label="Gender / Age" value={[
          patient?.gender ? patient.gender.charAt(0).toUpperCase() + patient.gender.slice(1) : null,
          patient?.age != null ? `${patient.age} yrs` : null,
        ].filter(Boolean).join(" · ") || "—"} />
        <Meta label="DOB" value={patient?.dob ? fmtDate(patient.dob) : "—"} />
        <Meta label="Blood Group" value={patient?.blood_group || "—"} />
        <Meta label="Phone" value={patient?.phone || "—"} />
        <Meta label="Order No." value={order.order_number} />
        <Meta label="Order Date" value={fmtDate(order.order_date)} />
        <Meta label="Source" value={order.source.replace(/_/g, " ")} />
        <div>
          <div className="text-xs text-neutral-500 uppercase font-medium mb-0.5">Status</div>
          <StatusBadge status={order.status} />
        </div>
        <Meta
          label="Referring Doctor"
          value={order.doctor
            ? `${order.doctor.name}${order.doctor.specialization ? ` (${order.doctor.specialization})` : ""}`
            : "—"}
        />
        <Meta
          label="Specimen"
          value={order.sample
            ? `${order.sample.specimen_type}${order.sample.collected_at ? ` · ${fmtDate(order.sample.collected_at)}` : ""}`
            : "—"}
        />
      </div>

      {/* Results by category */}
      {order.items.length === 0 ? (
        <div className="bg-white rounded-xl border border-neutral-200 p-8 text-center text-neutral-400 text-sm">
          No tests on this order
        </div>
      ) : grouped.map(([category, items]) => (
        <div key={category} className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <div className="px-4 py-2.5 bg-neutral-50 border-b border-neutral-200 text-xs font-semibold uppercase tracking-wide text-neutral-600">
            {CATEGORY_LABELS[category] || category}
          </div>
          <table className="w-full text-sm">
            <thead className="text-xs text-neutral-500 uppercase border-b border-neutral-100">
              <tr>
                <th className="text-left px-4 py-2.5">Test</th>
                <th className="text-left px-4 py-2.5">Result</th>
                <th className="text-left px-4 py-2.5">Previous</th>
                <th className="text-left px-4 py-2.5">Unit</th>
                <th className="text-left px-4 py-2.5">Reference Range</th>
                <th className="text-left px-4 py-2.5">Flag</th>
                <th className="text-left px-4 py-2.5 print:hidden">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {items.map(item => {
                const pending = !item.resulted_at
                const draft = drafts[item.id]
                const draftFlag = draft
                  ? classifyLabFlag(draft.result_value, {
                      referenceRange: draft.reference_range,
                      referenceInterval: item.reference_interval,
                      isAbnormal: draft.is_abnormal,
                    })
                  : null
                const displayFlag = pending && draftFlag ? draftFlag : item.flag
                const flagged = isAbnormalFlag(displayFlag) || item.is_abnormal

                function updateDraft(patch: Partial<DraftResult>) {
                  if (!draft) return
                  const next = { ...draft, ...patch }
                  // Auto-toggle abnormal from live range / Pos-Neg classification
                  if ("result_value" in patch || "reference_range" in patch) {
                    const live = classifyLabFlag(next.result_value, {
                      referenceRange: next.reference_range,
                      referenceInterval: item.reference_interval,
                      isAbnormal: next.is_abnormal,
                    })
                    if (live.code !== "pending" && live.code !== "abnormal") {
                      next.is_abnormal = isAbnormalFlag(live)
                    }
                  }
                  setDrafts(d => ({ ...d, [item.id]: next }))
                }

                return (
                  <tr key={item.id} className={flagged ? "bg-rose-50/40" : undefined}>
                    <td className="px-4 py-3">
                      <div className={`font-medium ${flagged ? "text-rose-800" : "text-neutral-900"}`}>
                        {item.test_name}
                      </div>
                      {item.test_code && (
                        <div className="text-xs text-neutral-400">{item.test_code}</div>
                      )}
                    </td>
                    {pending && draft ? (
                      <>
                        <td className="px-4 py-2">
                          <input
                            value={draft.result_value}
                            onChange={e => updateDraft({ result_value: e.target.value })}
                            className="w-full border border-neutral-200 rounded-lg px-2 py-1.5 text-sm"
                            placeholder="Value"
                          />
                        </td>
                        <td className="px-4 py-2 text-xs text-neutral-500 whitespace-nowrap">
                          {item.previous_result ? (
                            <div className="flex flex-col gap-0.5">
                              <span className="inline-flex items-center gap-1">
                                <span className={item.previous_result.is_abnormal ? "text-rose-700 font-medium" : ""}>
                                  {item.previous_result.result_value}
                                </span>
                                {item.previous_result.flag && (
                                  <LabResultFlag flag={item.previous_result.flag} compact />
                                )}
                              </span>
                              <div className="text-[10px] text-neutral-400">
                                {fmtDate(item.previous_result.order_date)}
                              </div>
                            </div>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-2">
                          <input
                            value={draft.result_unit}
                            onChange={e => updateDraft({ result_unit: e.target.value })}
                            className="w-full border border-neutral-200 rounded-lg px-2 py-1.5 text-sm"
                            placeholder="Unit"
                          />
                        </td>
                        <td className="px-4 py-2">
                          <input
                            value={draft.reference_range}
                            onChange={e => updateDraft({ reference_range: e.target.value })}
                            className="w-full border border-neutral-200 rounded-lg px-2 py-1.5 text-sm"
                            placeholder="Range"
                          />
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex flex-col gap-1.5">
                            <LabResultFlag flag={draftFlag} />
                            <label className="inline-flex items-center gap-1.5 text-xs text-neutral-600 cursor-pointer print:hidden">
                              <input
                                type="checkbox"
                                checked={draft.is_abnormal}
                                onChange={e => updateDraft({ is_abnormal: e.target.checked })}
                              />
                              Mark abnormal
                            </label>
                          </div>
                        </td>
                        <td className="px-4 py-2 print:hidden">
                          <button
                            onClick={() => saveResult(item)}
                            disabled={savingId === item.id}
                            className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 bg-rose-500 text-white rounded-lg hover:bg-rose-600 disabled:opacity-50"
                          >
                            <Save className="w-3.5 h-3.5" />
                            {savingId === item.id ? "Saving…" : "Save"}
                          </button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className={`px-4 py-3 whitespace-nowrap ${flagged ? "font-bold text-rose-800" : ""}`}>
                          {item.result_value || "—"}
                        </td>
                        <td className="px-4 py-3 text-xs text-neutral-500 whitespace-nowrap">
                          {item.previous_result ? (
                            <div className="flex flex-col gap-0.5">
                              <span className="inline-flex items-center gap-1">
                                <span className={item.previous_result.is_abnormal ? "text-rose-700 font-medium" : ""}>
                                  {item.previous_result.result_value}
                                </span>
                                {item.previous_result.flag && (
                                  <LabResultFlag flag={item.previous_result.flag} compact />
                                )}
                              </span>
                              <div className="text-[10px] text-neutral-400">
                                {fmtDate(item.previous_result.order_date)}
                              </div>
                            </div>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-neutral-600">
                          {item.result_unit || "—"}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-neutral-600">
                          {item.reference_range || "—"}
                        </td>
                        <td className="px-4 py-3">
                          <LabResultFlag flag={item.flag} />
                        </td>
                        <td className="px-4 py-3 print:hidden text-xs text-neutral-400">
                          {item.resulted_at ? fmtDate(item.resulted_at) : "—"}
                        </td>
                      </>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ))}

      {trendItems.length > 0 && <LabSerialTrends items={trendItems} />}

      <div className="text-xs text-neutral-500 border-t border-neutral-200 pt-3 space-y-2">
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <span className="font-medium text-neutral-600">Flag key:</span>
          <span>↑ H Excess (above range)</span>
          <span>↓ L Reduced (below range)</span>
          <span>+ Positive / reactive</span>
          <span>− Negative / non-reactive</span>
          <span>N Within range / normal</span>
        </div>
        <p>*** End of Laboratory Test Report ***</p>
        {order.items.some(i => i.resulted_at) && (
          <p>
            Results entered:{" "}
            {order.items
              .filter(i => i.resulted_at)
              .map(i => fmtDate(i.resulted_at!))
              .filter((v, i, a) => a.indexOf(v) === i)
              .join(", ")}
          </p>
        )}
        {pendingCount > 0 && (
          <p className="print:hidden text-amber-700">
            {pendingCount} test(s) still awaiting results — enter values above to complete the report.
          </p>
        )}
      </div>
    </div>
  )
}

function Meta({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div>
      <div className="text-xs text-neutral-500 uppercase font-medium mb-0.5">{label}</div>
      <div className={`text-sm text-neutral-800 capitalize ${bold ? "font-semibold text-base normal-case" : ""}`}>
        {value}
      </div>
    </div>
  )
}
