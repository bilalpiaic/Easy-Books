"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Printer, AlertCircle } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import PrintHeader from "@/components/PrintHeader"

type SILine = { id: number; product_id: number; qty: number; unit_cost: number }

type StoreIssue = {
  id: number; number: string; issue_date: string
  from_location_id: number; analytic_account_id?: number; debit_account_id: number
  notes?: string
  location_name?: string; debit_account_name?: string; analytic_account_name?: string
  lines: SILine[]
}

type Product = { id: number; name: string; unit?: string }

export default function StoreIssueDetailPage() {
  const { id } = useParams<{ id: string }>()
  const fmt = useFmt()

  const [si, setSi] = useState<StoreIssue | null>(null)
  const [products, setProducts] = useState<Record<number, Product>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const d = await apiFetch<StoreIssue>(`/api/store-issues/${id}`)
      setSi(d)
      if (d.lines.length) {
        const prodIds = Array.from(new Set(d.lines.map(l => l.product_id)))
        const entries = await Promise.all(
          prodIds.map(pid => apiFetch<Product>(`/api/products/${pid}`).catch(() => null))
        )
        setProducts(Object.fromEntries(
          entries.filter((p): p is Product => !!p).map(p => [p.id, p])
        ))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Not found")
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  if (loading) return <p className="p-4 text-sm text-[var(--text-muted)]">Loading…</p>
  if (!si) return <p className="p-4 text-sm text-red-600">{error ?? "Store issue not found"}</p>

  const lineTotal = (l: SILine) => Number(l.qty) * Number(l.unit_cost)
  const total = si.lines.reduce((sum, l) => sum + lineTotal(l), 0)

  return (
    <div className="p-4 space-y-4 max-w-4xl">
      <PrintHeader title={si.number} subtitle={fmtDate(si.issue_date)} />

      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-lg font-bold text-[var(--text-primary)]">{si.number}</h1>
        <Link href="/store/issues"
          className="flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft className="w-4 h-4" /> All Store Issues
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
            <dd>{fmtDate(si.issue_date)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Location</dt>
            <dd>{si.location_name || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Debit Account</dt>
            <dd>{si.debit_account_name || "—"}</dd>
          </div>
          {si.analytic_account_name && (
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Analytic Account</dt>
              <dd>{si.analytic_account_name}</dd>
            </div>
          )}
        </dl>
        {si.notes && (
          <div className="mt-3 bg-[var(--bg-page)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs text-[var(--text-muted)]">
            {si.notes}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-start gap-2 print:hidden">
        <button onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--border)] text-sm hover:bg-[var(--bg-page)]">
          <Printer className="w-4 h-4" /> Print
        </button>
      </div>

      {/* Lines */}
      <div className="table-freeze rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="px-3 py-2">Product</th>
              <th className="px-3 py-2 text-right">Qty</th>
              <th className="px-3 py-2 text-right">Unit Cost</th>
              <th className="px-3 py-2 text-right">Line Total</th>
            </tr>
          </thead>
          <tbody>
            {si.lines.map(l => {
              const product = products[l.product_id]
              return (
                <tr key={l.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2">{product?.name || `Product #${l.product_id}`}</td>
                  <td className="px-3 py-2 text-right">{fmt(Number(l.qty))}</td>
                  <td className="px-3 py-2 text-right">{fmt(Number(l.unit_cost))}</td>
                  <td className="px-3 py-2 text-right">{fmt(lineTotal(l))}</td>
                </tr>
              )
            })}
            {si.lines.length === 0 && (
              <tr><td colSpan={4} className="px-3 py-8 text-center text-[var(--text-muted)]">No lines</td></tr>
            )}
          </tbody>
          {si.lines.length > 0 && (
            <tfoot>
              <tr className="border-t border-[var(--border)] font-semibold">
                <td className="px-3 py-2" colSpan={3}>Total</td>
                <td className="px-3 py-2 text-right">{fmt(total)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}
