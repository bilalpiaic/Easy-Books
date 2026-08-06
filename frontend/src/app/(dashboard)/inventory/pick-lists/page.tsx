"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"

interface PickList {
  id: number
  number: string
  invoice_id: number
  invoice_number?: string
  status: string
  created_at?: string
  lines: { id: number; product_name?: string; qty_ordered: number; qty_picked: number }[]
}

export default function PickListsPage() {
  const [items, setItems] = useState<PickList[]>([])
  const [error, setError] = useState<string | null>(null)
  const [invoiceId, setInvoiceId] = useState("")
  const [busy, setBusy] = useState(false)
  const [detail, setDetail] = useState<PickList | null>(null)

  const load = useCallback(() => {
    apiFetch<{ total: number; items: PickList[] }>("/api/pick-lists")
      .then((r) => setItems(r.items))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [])

  useEffect(() => { load() }, [load])

  const create = async () => {
    if (!invoiceId) return
    setBusy(true)
    setError(null)
    try {
      await apiFetch("/api/pick-lists", {
        method: "POST",
        body: JSON.stringify({ invoice_id: Number(invoiceId), reserve: true }),
      })
      setInvoiceId("")
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed")
    } finally {
      setBusy(false)
    }
  }

  const act = async (id: number, action: string, body?: object) => {
    setBusy(true)
    setError(null)
    try {
      const r = await apiFetch<PickList>(`/api/pick-lists/${id}/${action}`, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      })
      setDetail(r)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed")
    } finally {
      setBusy(false)
    }
  }

  const open = async (id: number) => {
    try {
      const r = await apiFetch<PickList>(`/api/pick-lists/${id}`)
      setDetail(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed")
    }
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Pick / Pack</h1>
          <p className="text-sm text-[var(--text-primary)]/55">
            Warehouse pick lists from invoices with optional stock reservation.
          </p>
        </div>
        <Link href="/inventory/transfers" className="text-sm text-[var(--primary)] hover:underline">
          Transfers
        </Link>
      </div>

      <div className="flex flex-wrap gap-2 print:hidden">
        <input
          className="border rounded-lg px-3 py-2 text-sm"
          placeholder="Invoice ID"
          value={invoiceId}
          onChange={(e) => setInvoiceId(e.target.value)}
        />
        <button
          type="button"
          disabled={busy || !invoiceId}
          onClick={create}
          className="bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
        >
          Create pick list
        </button>
      </div>

      {error && (
        <p className="text-sm text-red-600 print:hidden">{error}</p>
      )}

      <div className="overflow-x-auto table-freeze">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-[var(--text-primary)]/60">
              <th className="py-2 pr-3">Number</th>
              <th className="py-2 pr-3">Invoice</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id} className="border-b border-[var(--border)]">
                <td className="py-2 pr-3 whitespace-nowrap">
                  <button type="button" className="text-[var(--primary)] hover:underline" onClick={() => open(p.id)}>
                    {p.number}
                  </button>
                </td>
                <td className="py-2 pr-3 whitespace-nowrap">{p.invoice_number || p.invoice_id}</td>
                <td className="py-2 pr-3">{p.status}</td>
                <td className="py-2 print:hidden space-x-2">
                  {p.status === "draft" && (
                    <button type="button" className="text-xs text-[var(--primary)]" onClick={() => act(p.id, "start")}>Start</button>
                  )}
                  {(p.status === "picking" || p.status === "picked") && (
                    <button type="button" className="text-xs text-[var(--primary)]" onClick={() => act(p.id, "pack")}>Pack</button>
                  )}
                  {p.status !== "packed" && p.status !== "cancelled" && (
                    <button type="button" className="text-xs text-red-600" onClick={() => act(p.id, "cancel")}>Cancel</button>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={4} className="py-6 text-[var(--text-primary)]/45">No pick lists yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {detail && (
        <div className="border border-[var(--border)] rounded-lg p-4 space-y-3 print:hidden">
          <div className="flex justify-between">
            <h2 className="font-semibold">{detail.number} · {detail.status}</h2>
            <button type="button" className="text-sm" onClick={() => setDetail(null)}>Close</button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-primary)]/60">
                <th className="py-1">Product</th>
                <th className="py-1">Ordered</th>
                <th className="py-1">Picked</th>
              </tr>
            </thead>
            <tbody>
              {detail.lines.map((ln) => (
                <tr key={ln.id} className="border-t border-[var(--border)]">
                  <td className="py-1">{ln.product_name}</td>
                  <td className="py-1">{ln.qty_ordered}</td>
                  <td className="py-1">
                    {(detail.status === "draft" || detail.status === "picking") ? (
                      <input
                        type="number"
                        className="w-20 border rounded px-2 py-1"
                        defaultValue={ln.qty_picked || ln.qty_ordered}
                        onBlur={(e) => {
                          const qty = Number(e.target.value)
                          act(detail.id, "pick", { lines: [{ line_id: ln.id, qty_picked: qty }] })
                        }}
                      />
                    ) : ln.qty_picked}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-[var(--text-primary)]/45">
            Created {detail.created_at ? fmtDate(String(detail.created_at).slice(0, 10)) : "—"}
          </p>
        </div>
      )}
    </div>
  )
}
