"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, CheckCircle, Save, ShoppingCart, AlertCircle, AlertTriangle, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"
import StatusBadge from "@/components/StatusBadge"

type DemandLine = { id: number; description: string; qty: number; unit?: string }

type Quotation = {
  id: number; number: string; vendor_id: number; vendor_name: string
  quote_date: string; total: number
}

type Cell = { quotation_id: number; rate: number | null; amount: number | null }

type MatrixRow = { demand_line: DemandLine; cells: Cell[] }

type CS = {
  id: number; number: string; cs_date: string; demand_id: number
  selected_quotation_id: number | null; justification: string | null
  status: string; po_id: number | null
  demand: { id: number; number: string; lines: DemandLine[] }
  quotations: Quotation[]
  matrix: MatrixRow[]
}

/** Lowest non-null amount in a row of cells — null cells are ignored. */
function isLowest(cells: { amount: number | null }[], cell: { amount: number | null }): boolean {
  if (cell.amount == null) return false
  const priced = cells.filter(c => c.amount != null).map(c => c.amount as number)
  if (!priced.length) return false
  return cell.amount === Math.min(...priced)
}

const LOW = "bg-green-50 text-green-700 font-medium"

export default function ComparativeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const fmt = useFmt()

  const [cs, setCs] = useState<CS | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [selected, setSelected] = useState<number | null>(null)
  const [justification, setJustification] = useState("")

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<CS>(`/api/comparatives/${id}`)
      setCs(data)
      setSelected(data.selected_quotation_id)
      setJustification(data.justification ?? "")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Not found")
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  const runAction = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed")
    } finally {
      setBusy(false)
    }
  }

  const save = () => runAction(async () => {
    await apiFetch(`/api/comparatives/${id}`, {
      method: "PUT",
      body: JSON.stringify({
        selected_quotation_id: selected,
        justification: justification.trim() || null,
      }),
    })
    await load()
  })

  const approve = () => runAction(async () => {
    await apiFetch(`/api/comparatives/${id}/approve`, { method: "PATCH" })
    await load()
  })

  const convertToPo = () => runAction(async () => {
    const po = await apiFetch<{ id: number }>(`/api/comparatives/${id}/convert-to-po`, { method: "POST" })
    router.push(`/manufacturing/purchase-orders/${po.id}`)
  })

  if (loading) return <p className="p-4 text-sm text-[var(--text-muted)]">Loading…</p>
  if (!cs) return <p className="p-4 text-sm text-red-600">{error ?? "Comparative not found"}</p>

  const isDraft = cs.status === "draft"

  // Lowest grand total among quotations (all totals are non-null numbers)
  const totalCells = cs.quotations.map(q => ({ quotation_id: q.id, amount: q.total }))
  const lowestTotalQuotationId = cs.quotations.length
    ? cs.quotations.reduce((low, q) => (q.total < low.total ? q : low), cs.quotations[0]).id
    : null

  const needsJustification =
    cs.quotations.length < 2 || (selected != null && selected !== lowestTotalQuotationId)

  return (
    <div className="p-4 space-y-4">
      <PrintHeader title={cs.number} subtitle={fmtDate(cs.cs_date)} />

      <div className="flex items-center justify-between print:hidden">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-[var(--text-primary)]">{cs.number}</h1>
          <StatusBadge status={cs.status} />
        </div>
        <Link href="/purchases/comparatives"
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft className="w-4 h-4" /> All Comparatives
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm flex items-start gap-2 print:hidden">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {/* Header fields */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Date</dt>
            <dd>{fmtDate(cs.cs_date)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Demand</dt>
            <dd>
              <Link href={`/purchases/demands/${cs.demand_id}`} className="text-[var(--primary)] print:text-inherit">
                {cs.demand.number}
              </Link>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Quotations</dt>
            <dd>{cs.quotations.length}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Status</dt>
            <dd className="capitalize">{cs.status}</dd>
          </div>
        </dl>
      </div>

      {/* Comparison matrix */}
      <div className="table-freeze freeze-col rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2 align-bottom">Demand Line</th>
              {cs.quotations.map(q => (
                <th key={q.id} className="px-3 py-2 align-bottom">
                  <div className="flex items-start gap-2">
                    <input
                      type="radio"
                      name="winner"
                      className="mt-0.5 print:hidden accent-[var(--primary)]"
                      checked={selected === q.id}
                      disabled={!isDraft}
                      onChange={() => setSelected(q.id)}
                      aria-label={`Select ${q.vendor_name}`}
                    />
                    <div>
                      <div className="font-semibold text-[var(--text-primary)]">{q.vendor_name}</div>
                      <div className="text-xs font-normal">{q.number}</div>
                      {cs.selected_quotation_id === q.id && (
                        <div className="text-[10px] uppercase tracking-wide text-emerald-700 font-bold">Selected</div>
                      )}
                    </div>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cs.matrix.map(row => (
              <tr key={row.demand_line.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-2">
                  <div className="font-medium text-[var(--text-primary)]">{row.demand_line.description}</div>
                  <div className="text-xs text-[var(--text-muted)]">
                    {row.demand_line.qty} {row.demand_line.unit || ""}
                  </div>
                </td>
                {row.cells.map(cell => (
                  <td key={cell.quotation_id}
                    className={`px-3 py-2 whitespace-nowrap ${isLowest(row.cells, cell) ? LOW : ""}`}>
                    {cell.rate == null ? (
                      <span className="text-[var(--text-muted)]">—</span>
                    ) : (
                      <>
                        <div>{fmt(cell.rate)}</div>
                        <div className="text-xs opacity-70">= {fmt(cell.amount ?? 0)}</div>
                      </>
                    )}
                  </td>
                ))}
              </tr>
            ))}
            {cs.matrix.length === 0 && (
              <tr>
                <td colSpan={1 + cs.quotations.length} className="px-3 py-8 text-center text-[var(--text-muted)]">
                  No demand lines
                </td>
              </tr>
            )}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-[var(--border)] font-semibold">
              <td className="px-3 py-2">Total</td>
              {cs.quotations.map(q => (
                <td key={q.id}
                  className={`px-3 py-2 whitespace-nowrap ${isLowest(totalCells, { amount: q.total }) ? LOW : ""}`}>
                  {fmt(q.total)}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Selection + justification */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 space-y-3">
        <h2 className="text-sm font-bold text-[var(--text-primary)]">Justification</h2>
        {needsJustification && (
          <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2 text-xs flex items-start gap-2 print:hidden">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            Justification required — selection is not the lowest quote / single quotation
          </div>
        )}
        {isDraft ? (
          <>
            <textarea
              value={justification}
              onChange={e => setJustification(e.target.value)}
              rows={3}
              placeholder="Why this vendor? Required when the selection is not the lowest quote, or only one quotation exists."
              className="w-full px-3 py-2 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm print:hidden"
            />
            <p className="hidden print:block text-sm">{justification || "—"}</p>
          </>
        ) : (
          <p className="text-sm">{cs.justification || "—"}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 print:hidden">
        {isDraft && (
          <>
            <button onClick={save} disabled={busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[var(--primary)] text-white text-sm disabled:opacity-50">
              <Save className="w-4 h-4" /> Save Selection
            </button>
            <button onClick={approve} disabled={busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-blue-600 text-white text-sm disabled:opacity-50">
              <CheckCircle className="w-4 h-4" /> Approve
            </button>
          </>
        )}
        {cs.status === "approved" && (
          <button onClick={convertToPo} disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-600 text-white text-sm disabled:opacity-50">
            <ShoppingCart className="w-4 h-4" /> Convert to PO
          </button>
        )}
        {cs.status === "converted" && cs.po_id && (
          <Link href={`/manufacturing/purchase-orders/${cs.po_id}`}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--border)] text-sm hover:bg-[var(--bg-page)]">
            <ShoppingCart className="w-4 h-4" /> View PO
          </Link>
        )}
        <button onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--border)] text-sm hover:bg-[var(--bg-page)]">
          <Printer className="w-4 h-4" /> Print
        </button>
      </div>
    </div>
  )
}
