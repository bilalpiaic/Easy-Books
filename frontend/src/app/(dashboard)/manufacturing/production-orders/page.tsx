"use client"

import { useEffect, useState } from "react"
import { Warehouse, Printer } from "lucide-react"
import PrintHeader from "@/components/PrintHeader"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { EmptyStateGuide } from "@/components/guidance/EmptyStateGuide"

interface Po {
  id: number; number: string; state: string
  bom_id: number; customer_id: number; rate_plan_id: number | null
  output_qty: string; own_material_cost: string; output_unit_cost: string
  invoice_id: number | null
  started_at: string | null; completed_at: string | null
  delivered_at: string | null; billed_at: string | null
}

const STATE_TONE: Record<string, string> = {
  draft:     "bg-slate-100 text-slate-800",
  started:   "bg-amber-100 text-amber-900",
  completed: "bg-blue-100 text-blue-900",
  delivered: "bg-emerald-100 text-emerald-900",
  billed:    "bg-violet-100 text-violet-900",
  cancelled: "bg-red-100 text-red-900",
}

export default function ProductionOrdersPage() {
  const [pos, setPos] = useState<Po[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const refresh = () =>
    apiFetch<{ items: Po[] }>("/api/production-orders")
      .then(d => setPos(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))

  useEffect(() => {
    refresh().finally(() => setLoading(false))
  }, [])

  const advance = async (po: Po, action: "start" | "complete" | "deliver" | "bill" | "cancel") => {
    setBusyId(po.id)
    setError(null)
    try {
      await apiFetch(`/api/production-orders/${po.id}/${action}`, { method: "POST" })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed")
    } finally {
      setBusyId(null)
    }
  }

  const nextAction = (state: string): "start" | "complete" | "deliver" | "bill" | null => {
    if (state === "draft")     return "start"
    if (state === "started")   return "complete"
    if (state === "completed") return "deliver"
    if (state === "delivered") return "bill"
    return null
  }

  if (loading) return <p className="text-sm text-[#1a1814]/60">Loading…</p>

  return (
    <div className="space-y-5">
      <PrintHeader title="Production Orders" orientation="landscape" />
      <header className="flex items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <Warehouse className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Production Orders</h1>
            <p className="text-sm text-[#1a1814]/60">Drive one batch from kickoff to invoice.</p>
          </div>
        </div>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors"
          title="Print"
        >
          <Printer className="w-4 h-4" />
          Print
        </button>
      </header>

      <HelpCallout title="The 5-step lifecycle" tone="tip">
        <ol className="list-decimal pl-4 space-y-1">
          <li><b>Draft</b> — PO created, references a BoM + customer + rate plan. No GL entries yet.</li>
          <li><b>Started</b> — material issued to WIP. Dr WIP / Cr Raw Material (own-stock only).</li>
          <li><b>Completed</b> — output capitalised. Dr Finished Goods / Cr WIP at total cost basis.</li>
          <li><b>Delivered</b> — FG ships out. Dr COGS / Cr Finished Goods. Custodial memo released.</li>
          <li><b>Billed</b> — Invoice created from the rate plan (Dr AR / Cr Service Revenue).</li>
        </ol>
      </HelpCallout>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {pos.length === 0 ? (
        <EmptyStateGuide
          title="No production orders yet"
          description="Once you have a BoM and a rate plan, create your first PO via the API."
          steps={[
            "Create or pick a BoM for the output product.",
            "Make sure the customer has an active rate plan assigned.",
            "POST /api/production-orders with bom_id, customer_id, output_qty.",
            "Then walk the PO through start → complete → deliver → bill.",
          ]}
          secondaryAction={{ label: "Open the guide →", href: "/guide" }}
        />
      ) : (
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#faf6ec] text-[#1a1814]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">PO #</th>
                <th className="text-left px-4 py-2">Customer</th>
                <th className="text-left px-4 py-2">Output qty</th>
                <th className="text-left px-4 py-2">WIP cost</th>
                <th className="text-left px-4 py-2">Unit cost</th>
                <th className="text-left px-4 py-2">State</th>
                <th className="text-right px-4 py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {pos.map(p => {
                const nxt = nextAction(p.state)
                return (
                  <tr key={p.id} className="border-t border-[#ede9e2]">
                    <td className="px-4 py-2 font-mono text-xs">{p.number}</td>
                    <td className="px-4 py-2">#{p.customer_id}</td>
                    <td className="px-4 py-2">{p.output_qty}</td>
                    <td className="px-4 py-2">{p.own_material_cost}</td>
                    <td className="px-4 py-2">{p.output_unit_cost}</td>
                    <td className="px-4 py-2">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold ${STATE_TONE[p.state] ?? ""}`}>
                        {p.state}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <div className="flex items-center justify-end gap-2 flex-wrap">
                        <a
                          href={`/manufacturing/production-orders/${p.id}/print`}
                          title="Print this PO"
                          className="p-1.5 rounded border border-[#ede9e2] hover:bg-[#faf6ec] text-[#1a1814]/55 hover:text-[#b8943f]"
                        >
                          <Printer className="w-3.5 h-3.5" />
                        </a>
                        {nxt && (
                          <button
                            disabled={busyId === p.id}
                            onClick={() => advance(p, nxt)}
                            className="px-3 py-1.5 text-xs font-semibold bg-[#1a1814] text-white rounded-lg hover:bg-[#b8943f] hover:text-[#1a1814] transition-colors disabled:opacity-50"
                          >
                            {busyId === p.id ? "Working…" : `→ ${nxt}`}
                          </button>
                        )}
                        {p.state === "draft" && (
                          <button
                            disabled={busyId === p.id}
                            onClick={() => advance(p, "cancel")}
                            className="px-3 py-1.5 text-xs text-red-700 hover:text-red-900 underline"
                          >
                            cancel
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
