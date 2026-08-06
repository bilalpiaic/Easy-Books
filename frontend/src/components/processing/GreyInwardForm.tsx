"use client"

/**
 * GREY IN voucher layout — header + lot band + SAFI THAN DETAIL + summary /
 * rejection-return. Matches the classic processing-unit Grey Inward form.
 */

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Plus, Trash2 } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

type SO = {
  id: number
  number: string
  customer_id: number
  quality_id: number
  grey_rate: number
  quality_lines?: { quality_id: number }[]
}
type Quality = { id: number; code: string }
type Process = { id: number; code: string; name: string; is_active: boolean }
type Contractor = { id: number; code: string; name: string; is_active: boolean }
type Customer = { id: number; name: string }

type ThanRow = {
  than_no: string
  meters: string
  g_kami_mtr: string
  rejection_mtr: string
  cp_mtr: string
  des_date: string
}

export type GreyLotView = {
  id: number
  number: string
  date: string
  status: string
  sales_order_id: number
  sales_order_number?: string | null
  customer_id: number
  party_name?: string | null
  party_code?: string | null
  quality_id: number
  quality_code?: string | null
  mending_date?: string | null
  contractor_id?: number | null
  contractor_name?: string | null
  contractor_code?: string | null
  category?: string | null
  process_name?: string | null
  rate?: number
  lot_no?: string | null
  lot_remarks?: string | null
  l_kami_mtr?: number
  manual_rejection_mtr?: number | null
  rej_driver_name?: string | null
  rej_mobile?: string | null
  rej_vehicle?: string | null
  notes?: string | null
  received_mtr?: number
  ready_mtr?: number
  rejection_mtr?: number
  thans?: {
    id?: number
    than_no: string
    meters: number
    g_kami_mtr: number
    rejection_mtr: number
    cp_mtr: number
    safi_mtr: number
    des_date?: string | null
  }[]
  summary?: Record<
    string,
    { than: number; detail_mtrs: number; manual_mtrs: number; variance: number }
  >
  kachi_parchi?: { id: number; number: string }
  mending?: { id: number; number: string }
}

const today = () => new Date().toISOString().slice(0, 10)

function emptyThan(n: number): ThanRow {
  return {
    than_no: String(n),
    meters: "",
    g_kami_mtr: "0",
    rejection_mtr: "0",
    cp_mtr: "0",
    des_date: "",
  }
}

function n(v: string | number | null | undefined) {
  if (v === "" || v == null) return 0
  const x = typeof v === "number" ? v : parseFloat(v)
  return Number.isFinite(x) ? x : 0
}

function calcSafi(t: { meters: string; g_kami_mtr: string; rejection_mtr: string; cp_mtr: string }) {
  return Math.max(0, n(t.meters) - n(t.g_kami_mtr) - n(t.rejection_mtr) - n(t.cp_mtr))
}

function fmtQty(v: number) {
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function thanRowTone(t: { meters: string | number; rejection_mtr: string | number; cp_mtr: string | number; safi?: number }) {
  const greigh = n(t.meters)
  const rej = n(t.rejection_mtr)
  const cp = n(t.cp_mtr)
  const safi = t.safi != null ? t.safi : Math.max(0, greigh - rej - cp - n((t as ThanRow).g_kami_mtr))
  if (greigh > 0 && rej >= greigh - 0.0001 && safi <= 0.0001) return "bg-red-100 dark:bg-red-950/40"
  if (cp > 0) return "bg-emerald-100 dark:bg-emerald-950/40"
  return ""
}

const field =
  "border border-[var(--border)] rounded px-2 py-1.5 text-sm w-full bg-[var(--surface)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
const fieldReadonly =
  "border border-[var(--border)] rounded px-2 py-1.5 text-sm w-full bg-[var(--bg)] text-[var(--text)]"
const label = "text-[11px] uppercase tracking-wide text-[var(--text-muted)] mb-0.5"

type Props = {
  mode: "create" | "view"
  initial?: GreyLotView | null
}

export default function GreyInwardForm({ mode, initial }: Props) {
  const router = useRouter()
  const readOnly = mode === "view"

  const [sos, setSos] = useState<SO[]>([])
  const [qualities, setQualities] = useState<Quality[]>([])
  const [processes, setProcesses] = useState<Process[]>([])
  const [contractors, setContractors] = useState<Contractor[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [err, setErr] = useState("")
  const [saving, setSaving] = useState(false)

  const [salesOrderId, setSalesOrderId] = useState(initial ? String(initial.sales_order_id) : "")
  const [qualityId, setQualityId] = useState(initial ? String(initial.quality_id) : "")
  const [date, setDate] = useState(initial?.date || today())
  const [mendingDate, setMendingDate] = useState(initial?.mending_date || "")
  const [contractorId, setContractorId] = useState(
    initial?.contractor_id ? String(initial.contractor_id) : "",
  )
  const [category, setCategory] = useState(initial?.category || "")
  const [processName, setProcessName] = useState(initial?.process_name || "")
  const [rate, setRate] = useState(initial?.rate != null ? String(initial.rate) : "")
  const [lotNo, setLotNo] = useState(initial?.lot_no || "")
  const [lotRemarks, setLotRemarks] = useState(initial?.lot_remarks || "")
  const [lKami, setLKami] = useState(initial?.l_kami_mtr != null ? String(initial.l_kami_mtr) : "0")
  const [manualRej, setManualRej] = useState(
    initial?.manual_rejection_mtr != null ? String(initial.manual_rejection_mtr) : "",
  )
  const [notes, setNotes] = useState(initial?.notes || "")
  const [rejDriver, setRejDriver] = useState(initial?.rej_driver_name || "")
  const [rejMobile, setRejMobile] = useState(initial?.rej_mobile || "")
  const [rejVehicle, setRejVehicle] = useState(initial?.rej_vehicle || "")
  const [thans, setThans] = useState<ThanRow[]>(() => {
    if (initial?.thans?.length) {
      return initial.thans.map(t => ({
        than_no: t.than_no,
        meters: String(t.meters ?? ""),
        g_kami_mtr: String(t.g_kami_mtr ?? 0),
        rejection_mtr: String(t.rejection_mtr ?? 0),
        cp_mtr: String(t.cp_mtr ?? 0),
        des_date: t.des_date || "",
      }))
    }
    return [emptyThan(1), emptyThan(2), emptyThan(3)]
  })

  useEffect(() => {
    if (readOnly) return
    apiFetch<SO[]>("/api/textile-processing/sales-orders")
      .then(d => setSos(Array.isArray(d) ? d : []))
      .catch(() => setSos([]))
    apiFetch<Quality[]>("/api/textile-processing/qualities")
      .then(d => setQualities(Array.isArray(d) ? d : []))
      .catch(() => setQualities([]))
    apiFetch<Process[]>("/api/textile-processing/processes")
      .then(d => setProcesses(Array.isArray(d) ? d.filter(p => p.is_active !== false) : []))
      .catch(() => setProcesses([]))
    apiFetch<Contractor[]>("/api/textile-processing/contractors?active_only=true")
      .then(d => setContractors(Array.isArray(d) ? d : []))
      .catch(() => setContractors([]))
    apiFetch<Customer[]>("/api/customers")
      .then(d => setCustomers(Array.isArray(d) ? d : []))
      .catch(() => setCustomers([]))
  }, [readOnly])

  const selectedSo = sos.find(s => String(s.id) === salesOrderId)
  const party = useMemo(() => {
    if (readOnly) {
      return {
        id: initial?.customer_id,
        name: initial?.party_name || "—",
        code: initial?.party_code || "",
      }
    }
    const c = customers.find(x => x.id === selectedSo?.customer_id)
    return { id: c?.id, name: c?.name || "—", code: c ? String(c.id) : "" }
  }, [readOnly, initial, customers, selectedSo])

  const soQualIds = selectedSo
    ? Array.from(
        new Set([
          selectedSo.quality_id,
          ...(selectedSo.quality_lines || []).map(l => l.quality_id),
        ]),
      )
    : []

  const qualMap = Object.fromEntries(qualities.map(q => [q.id, q.code]))
  const fabricCode = readOnly
    ? initial?.quality_code || "—"
    : (qualityId && qualMap[Number(qualityId)]) ||
      (selectedSo && qualMap[selectedSo.quality_id]) ||
      "—"

  useEffect(() => {
    if (readOnly || !selectedSo) return
    if (!qualityId) setQualityId(String(selectedSo.quality_id))
    if (!rate && selectedSo.grey_rate) setRate(String(selectedSo.grey_rate))
  }, [selectedSo, readOnly, qualityId, rate])

  const totals = useMemo(() => {
    const greigh = thans.reduce((s, t) => s + n(t.meters), 0)
    const gKami = thans.reduce((s, t) => s + n(t.g_kami_mtr), 0)
    const rej = thans.reduce((s, t) => s + n(t.rejection_mtr), 0)
    const cp = thans.reduce((s, t) => s + n(t.cp_mtr), 0)
    const safi = thans.reduce((s, t) => s + calcSafi(t), 0)
    const thanRej = thans.filter(t => n(t.rejection_mtr) > 0 && calcSafi(t) <= 0.0001 && n(t.meters) > 0).length
    const thanCp = thans.filter(t => n(t.cp_mtr) > 0).length
    const thanSafi = thans.filter(t => calcSafi(t) > 0).length
    const manual = manualRej !== "" ? n(manualRej) : rej
    return {
      greigh,
      gKami,
      rej,
      cp,
      safi,
      thanRej,
      thanCp,
      thanSafi,
      thanTotal: thans.filter(t => t.than_no.trim() && n(t.meters) > 0).length,
      lKami: n(lKami),
      manualRej: manual,
      rejVariance: manual - rej,
    }
  }, [thans, lKami, manualRej])

  function updateThan(i: number, patch: Partial<ThanRow>) {
    setThans(rows => rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  }

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (readOnly) return
    setErr("")
    setSaving(true)
    const payloadThans = thans
      .filter(t => t.than_no.trim() && n(t.meters) > 0)
      .map(t => ({
        than_no: t.than_no.trim(),
        meters: n(t.meters),
        g_kami_mtr: n(t.g_kami_mtr),
        rejection_mtr: n(t.rejection_mtr),
        cp_mtr: n(t.cp_mtr),
        des_date: t.des_date || null,
        safi_mtr: calcSafi(t),
      }))
    if (!payloadThans.length) {
      setErr("Enter at least one than with Greigh meters")
      setSaving(false)
      return
    }
    try {
      const created = await apiFetch<GreyLotView>("/api/textile-processing/lots", {
        method: "POST",
        body: JSON.stringify({
          sales_order_id: Number(salesOrderId),
          quality_id: qualityId ? Number(qualityId) : undefined,
          date,
          mending_date: mendingDate || null,
          contractor_id: contractorId ? Number(contractorId) : null,
          category: category || null,
          process_name: processName || null,
          rate: rate !== "" ? n(rate) : undefined,
          lot_no: lotNo || null,
          lot_remarks: lotRemarks || null,
          l_kami_mtr: n(lKami),
          manual_rejection_mtr: manualRej !== "" ? n(manualRej) : null,
          rej_driver_name: rejDriver || null,
          rej_mobile: rejMobile || null,
          rej_vehicle: rejVehicle || null,
          notes: notes || null,
          thans: payloadThans,
        }),
      })
      router.push(`/processing/lots/${created.id}`)
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Failed to save")
      setSaving(false)
    }
  }

  const summaryRows: {
    key: string
    label: string
    than: number
    detail: number
    manual: number
    variance: number
    tone?: string
  }[] = [
    {
      key: "safi",
      label: "TOTAL SAFI",
      than: totals.thanSafi,
      detail: totals.safi,
      manual: totals.safi,
      variance: 0,
    },
    {
      key: "gk",
      label: "TOTAL G.KAMI",
      than: 0,
      detail: totals.gKami,
      manual: totals.gKami,
      variance: 0,
    },
    {
      key: "lk",
      label: "TOTAL L.KAMI",
      than: 0,
      detail: totals.lKami,
      manual: totals.lKami,
      variance: 0,
    },
    {
      key: "rej",
      label: "TOTAL REJECTION",
      than: totals.thanRej,
      detail: totals.rej,
      manual: totals.manualRej,
      variance: totals.rejVariance,
      tone: "bg-orange-100 dark:bg-orange-950/40",
    },
    {
      key: "cp",
      label: "TOTAL CP",
      than: totals.thanCp,
      detail: totals.cp,
      manual: totals.cp,
      variance: 0,
      tone: "bg-emerald-100 dark:bg-emerald-950/40",
    },
    {
      key: "gt",
      label: "G.TOTAL",
      than: totals.thanTotal,
      detail: totals.greigh,
      manual: totals.greigh,
      variance: 0,
    },
  ]

  return (
    <form onSubmit={save} className="p-3 md:p-4 space-y-3 max-w-[1400px] mx-auto">
      {/* Title + actions */}
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <div>
          <h1 className="text-xl font-semibold tracking-wide">GREY IN</h1>
          <p className="text-xs text-[var(--text-muted)]">
            {readOnly
              ? `${initial?.number || ""} · ${initial?.status || ""}`
              : "Receive grey fabric — than detail, rejection & cut piece"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {readOnly && initial?.mending && (
            <Link
              href="/processing/mending"
              className="rounded border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--surface)]"
            >
              MENDING BILL
            </Link>
          )}
          {readOnly && initial?.kachi_parchi && (
            <Link
              href={`/processing/kachi-parchi/${initial.kachi_parchi.id}`}
              className="rounded border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--surface)]"
            >
              K.P. {initial.kachi_parchi.number}
            </Link>
          )}
          <Link
            href="/processing/lots"
            className="rounded border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--surface)]"
          >
            Close
          </Link>
          {!readOnly && (
            <button
              type="submit"
              disabled={saving}
              className="rounded bg-[var(--primary)] text-white px-4 py-1.5 text-xs font-medium disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          )}
        </div>
      </div>

      {err && <p className="text-sm text-red-600 print:hidden">{err}</p>}

      {/* Header metadata */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2 border border-[var(--border)] rounded-lg p-3 bg-[var(--surface)]">
        <div>
          <div className={label}>Grey IN#</div>
          <input
            className={fieldReadonly}
            readOnly
            value={readOnly ? initial?.number || "" : "(auto)"}
          />
        </div>
        <div>
          <div className={label}>Date</div>
          {readOnly ? (
            <div className={fieldReadonly}>{fmtDate(date)}</div>
          ) : (
            <input type="date" className={field} value={date} onChange={e => setDate(e.target.value)} required />
          )}
        </div>
        <div className="col-span-2">
          <div className={label}>Party</div>
          {readOnly ? (
            <div className={fieldReadonly}>
              {[party.code, party.name].filter(Boolean).join(" · ") || "—"}
            </div>
          ) : (
            <select
              className={field}
              value={salesOrderId}
              onChange={e => {
                setSalesOrderId(e.target.value)
                setQualityId("")
              }}
              required
            >
              <option value="">Sales order (party)…</option>
              {sos.map(s => (
                <option key={s.id} value={s.id}>
                  {s.number}
                </option>
              ))}
            </select>
          )}
          {!readOnly && selectedSo && (
            <p className="text-xs text-[var(--text-muted)] mt-0.5 truncate">
              {party.code ? `${party.code} · ` : ""}
              {party.name}
            </p>
          )}
        </div>
        <div>
          <div className={label}>Mending Date</div>
          {readOnly ? (
            <div className={fieldReadonly}>{mendingDate ? fmtDate(mendingDate) : "—"}</div>
          ) : (
            <input
              type="date"
              className={field}
              value={mendingDate}
              onChange={e => setMendingDate(e.target.value)}
            />
          )}
        </div>
        <div>
          <div className={label}>Contractor Name</div>
          {readOnly ? (
            <div className={fieldReadonly}>
              {initial?.contractor_code
                ? `${initial.contractor_code} · ${initial.contractor_name || ""}`
                : initial?.contractor_name || "—"}
            </div>
          ) : (
            <select
              className={field}
              value={contractorId}
              onChange={e => setContractorId(e.target.value)}
            >
              <option value="">—</option>
              {contractors.map(c => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.name}
                </option>
              ))}
            </select>
          )}
        </div>
        <div>
          <div className={label}>Category</div>
          {readOnly ? (
            <div className={fieldReadonly}>{category || "—"}</div>
          ) : (
            <input
              className={field}
              value={category}
              onChange={e => setCategory(e.target.value)}
              placeholder="e.g. CHOTA ARZ"
            />
          )}
        </div>
      </div>

      {/* Main grid: lot band + than detail */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_min(380px,100%)] gap-3 items-start">
        <div className="space-y-3 min-w-0">
          {/* Lot summary table */}
          <div className="overflow-auto border border-[var(--border)] rounded-lg">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-[var(--border)] bg-[var(--bg)] text-[11px] uppercase text-[var(--text-muted)]">
                  <th className="p-2 w-8">S#</th>
                  <th className="p-2">Lot#</th>
                  <th className="p-2">Fabric Qlty</th>
                  <th className="p-2">Process</th>
                  <th className="p-2 text-right">Mtrs</th>
                  <th className="p-2 text-right">G-Kami</th>
                  <th className="p-2 text-right">L-Kami</th>
                  <th className="p-2 text-right">Reject</th>
                  <th className="p-2 text-right">Safi</th>
                  <th className="p-2 text-right">Rate</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[var(--border)]/60">
                  <td className="p-2">1</td>
                  <td className="p-1">
                    {readOnly ? (
                      <span className="px-2">{lotNo || "—"}</span>
                    ) : (
                      <input
                        className={field}
                        value={lotNo}
                        onChange={e => setLotNo(e.target.value)}
                        placeholder="Lot#"
                      />
                    )}
                  </td>
                  <td className="p-1 min-w-[10rem]">
                    {readOnly ? (
                      <span className="px-2 whitespace-nowrap">{fabricCode}</span>
                    ) : (
                      <select
                        className={field}
                        value={qualityId}
                        onChange={e => setQualityId(e.target.value)}
                      >
                        <option value="">Quality…</option>
                        {soQualIds.map(id => (
                          <option key={id} value={id}>
                            {qualMap[id] || id}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                  <td className="p-1 min-w-[7rem]">
                    {readOnly ? (
                      <span className="px-2">{processName || "—"}</span>
                    ) : (
                      <select
                        className={field}
                        value={processName}
                        onChange={e => setProcessName(e.target.value)}
                      >
                        <option value="">Process…</option>
                        {processes.map(p => (
                          <option key={p.id} value={p.name}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                  <td className="p-2 text-right tabular-nums whitespace-nowrap">{fmtQty(totals.greigh)}</td>
                  <td className="p-2 text-right tabular-nums whitespace-nowrap">{fmtQty(totals.gKami)}</td>
                  <td className="p-1">
                    {readOnly ? (
                      <div className="text-right tabular-nums px-2">{fmtQty(totals.lKami)}</div>
                    ) : (
                      <input
                        className={`${field} text-right`}
                        value={lKami}
                        onChange={e => setLKami(e.target.value)}
                      />
                    )}
                  </td>
                  <td className="p-1">
                    {readOnly ? (
                      <div className="text-right tabular-nums px-2">{fmtQty(totals.manualRej)}</div>
                    ) : (
                      <input
                        className={`${field} text-right`}
                        value={manualRej}
                        placeholder={fmtQty(totals.rej)}
                        onChange={e => setManualRej(e.target.value)}
                        title="Manual rejection (variance vs than detail)"
                      />
                    )}
                  </td>
                  <td className="p-2 text-right tabular-nums whitespace-nowrap font-medium">
                    {fmtQty(totals.safi)}
                  </td>
                  <td className="p-1">
                    {readOnly ? (
                      <div className="text-right tabular-nums px-2">{fmtQty(n(rate))}</div>
                    ) : (
                      <input
                        className={`${field} text-right`}
                        value={rate}
                        onChange={e => setRate(e.target.value)}
                      />
                    )}
                  </td>
                </tr>
              </tbody>
              <tfoot>
                <tr className="font-semibold border-t border-[var(--border)] bg-[var(--bg)]">
                  <td className="p-2" colSpan={4}>
                    Total
                  </td>
                  <td className="p-2 text-right tabular-nums">{fmtQty(totals.greigh)}</td>
                  <td className="p-2 text-right tabular-nums">{fmtQty(totals.gKami)}</td>
                  <td className="p-2 text-right tabular-nums">{fmtQty(totals.lKami)}</td>
                  <td className="p-2 text-right tabular-nums">{fmtQty(totals.manualRej)}</td>
                  <td className="p-2 text-right tabular-nums">{fmtQty(totals.safi)}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Remarks */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div>
              <div className={label}>Lot Remarks</div>
              {readOnly ? (
                <div className={`${fieldReadonly} min-h-[2.5rem]`}>{lotRemarks || "—"}</div>
              ) : (
                <input
                  className={field}
                  value={lotRemarks}
                  onChange={e => setLotRemarks(e.target.value)}
                />
              )}
            </div>
            <div>
              <div className={label}>Remarks</div>
              {readOnly ? (
                <div className={`${fieldReadonly} min-h-[2.5rem]`}>{notes || "—"}</div>
              ) : (
                <input className={field} value={notes} onChange={e => setNotes(e.target.value)} />
              )}
            </div>
          </div>

          {/* Summary + Rejection return */}
          <div className="grid grid-cols-1 md:grid-cols-[1.4fr_1fr] gap-3">
            <div className="overflow-auto border border-[var(--border)] rounded-lg">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left border-b border-[var(--border)] bg-[var(--bg)] text-[11px] uppercase text-[var(--text-muted)]">
                    <th className="p-2" />
                    <th className="p-2 text-right">Than</th>
                    <th className="p-2 text-right">Detail Mtrs</th>
                    <th className="p-2 text-right">Manual Mtrs</th>
                    <th className="p-2 text-right">Variance</th>
                  </tr>
                </thead>
                <tbody>
                  {summaryRows.map(r => (
                    <tr
                      key={r.key}
                      className={`border-b border-[var(--border)]/50 ${r.tone || ""} ${
                        r.key === "gt" ? "font-semibold" : ""
                      }`}
                    >
                      <td className="p-2 whitespace-nowrap">{r.label}</td>
                      <td className="p-2 text-right tabular-nums">{fmtQty(r.than)}</td>
                      <td className="p-2 text-right tabular-nums">{fmtQty(r.detail)}</td>
                      <td className="p-2 text-right tabular-nums">{fmtQty(r.manual)}</td>
                      <td className="p-2 text-right tabular-nums">{fmtQty(r.variance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="border border-[var(--border)] rounded-lg p-3 space-y-2 bg-[var(--surface)]">
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Rejection Return
              </div>
              <div>
                <div className={label}>Driver Name</div>
                {readOnly ? (
                  <div className={fieldReadonly}>{rejDriver || "—"}</div>
                ) : (
                  <input
                    className={field}
                    value={rejDriver}
                    onChange={e => setRejDriver(e.target.value)}
                  />
                )}
              </div>
              <div>
                <div className={label}>Mobile #</div>
                {readOnly ? (
                  <div className={fieldReadonly}>{rejMobile || "—"}</div>
                ) : (
                  <input
                    className={field}
                    value={rejMobile}
                    onChange={e => setRejMobile(e.target.value)}
                  />
                )}
              </div>
              <div>
                <div className={label}>Vehicle #</div>
                {readOnly ? (
                  <div className={fieldReadonly}>{rejVehicle || "—"}</div>
                ) : (
                  <input
                    className={field}
                    value={rejVehicle}
                    onChange={e => setRejVehicle(e.target.value)}
                  />
                )}
              </div>
            </div>
          </div>
        </div>

        {/* SAFI THAN DETAIL */}
        <div className="border border-[var(--border)] rounded-lg overflow-hidden flex flex-col max-h-[min(70vh,720px)] bg-[var(--surface)]">
          <div className="px-3 py-2 border-b border-[var(--border)] text-xs font-semibold uppercase tracking-wide flex items-center justify-between">
            <span>Safi Than Detail</span>
            {!readOnly && (
              <button
                type="button"
                className="text-[var(--primary)] flex items-center gap-1 normal-case font-medium"
                onClick={() => setThans(rows => [...rows, emptyThan(rows.length + 1)])}
              >
                <Plus className="w-3.5 h-3.5" /> Add
              </button>
            )}
          </div>
          <div className="overflow-auto flex-1 table-freeze">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left border-b border-[var(--border)] bg-[var(--bg)] sticky top-0">
                  <th className="p-1.5">Than#</th>
                  <th className="p-1.5 text-right">Greigh</th>
                  <th className="p-1.5 text-right">G.Kami</th>
                  <th className="p-1.5 text-right">Reject</th>
                  <th className="p-1.5 text-right">CP</th>
                  <th className="p-1.5 text-right">Safi</th>
                  <th className="p-1.5">Des.Date</th>
                  {!readOnly && <th className="p-1.5 w-7" />}
                </tr>
              </thead>
              <tbody>
                {thans.map((t, i) => {
                  const safi = calcSafi(t)
                  const tone = thanRowTone({ ...t, safi })
                  return (
                    <tr key={i} className={`border-b border-[var(--border)]/40 ${tone}`}>
                      <td className="p-0.5">
                        {readOnly ? (
                          <span className="px-1.5">{t.than_no}</span>
                        ) : (
                          <input
                            className={`${field} !py-1 !text-xs`}
                            value={t.than_no}
                            onChange={e => updateThan(i, { than_no: e.target.value })}
                          />
                        )}
                      </td>
                      {(
                        [
                          ["meters", "Greigh"],
                          ["g_kami_mtr", "G.Kami"],
                          ["rejection_mtr", "Reject"],
                          ["cp_mtr", "CP"],
                        ] as const
                      ).map(([key]) => (
                        <td key={key} className="p-0.5">
                          {readOnly ? (
                            <div className="text-right tabular-nums px-1.5">{fmtQty(n(t[key]))}</div>
                          ) : (
                            <input
                              className={`${field} !py-1 !text-xs text-right`}
                              value={t[key]}
                              onChange={e => updateThan(i, { [key]: e.target.value })}
                            />
                          )}
                        </td>
                      ))}
                      <td className="p-1.5 text-right tabular-nums font-medium">{fmtQty(safi)}</td>
                      <td className="p-0.5">
                        {readOnly ? (
                          <span className="px-1.5 whitespace-nowrap">
                            {t.des_date ? fmtDate(t.des_date) : ""}
                          </span>
                        ) : (
                          <input
                            type="date"
                            className={`${field} !py-1 !text-xs`}
                            value={t.des_date}
                            onChange={e => updateThan(i, { des_date: e.target.value })}
                          />
                        )}
                      </td>
                      {!readOnly && (
                        <td className="p-0.5">
                          <button
                            type="button"
                            className="text-red-500 disabled:opacity-30"
                            disabled={thans.length <= 1}
                            onClick={() => setThans(rows => rows.filter((_, j) => j !== i))}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr className="font-semibold border-t border-[var(--border)] bg-[var(--bg)] sticky bottom-0">
                  <td className="p-1.5">Total</td>
                  <td className="p-1.5 text-right tabular-nums">{fmtQty(totals.greigh)}</td>
                  <td className="p-1.5 text-right tabular-nums">{fmtQty(totals.gKami)}</td>
                  <td className="p-1.5 text-right tabular-nums">{fmtQty(totals.rej)}</td>
                  <td className="p-1.5 text-right tabular-nums">{fmtQty(totals.cp)}</td>
                  <td className="p-1.5 text-right tabular-nums">{fmtQty(totals.safi)}</td>
                  <td colSpan={readOnly ? 1 : 2} />
                </tr>
              </tfoot>
            </table>
          </div>
          <div className="px-3 py-1.5 text-[10px] text-[var(--text-muted)] border-t border-[var(--border)] print:hidden">
            Red = full reject · Green = cut piece · Safi = Greigh − G.Kami − Reject − CP
          </div>
        </div>
      </div>
    </form>
  )
}
