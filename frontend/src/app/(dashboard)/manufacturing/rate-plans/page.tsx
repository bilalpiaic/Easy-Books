"use client"

import { useEffect, useState } from "react"
import { Tags, Printer } from "lucide-react"
import PrintHeader from "@/components/PrintHeader"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { EmptyStateGuide } from "@/components/guidance/EmptyStateGuide"

interface RatePlan {
  id: number; code: string; name: string; version: number; is_active: boolean
  per_unit_rate: string; includes_materials_at_cost: boolean
  overhead_pct: string; margin_pct: string
}

export default function RatePlansPage() {
  const [plans, setPlans] = useState<RatePlan[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ items: RatePlan[] }>("/api/rate-plans")
      .then(d => setPlans(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-sm text-[#1a1814]/60">Loading…</p>

  return (
    <div className="space-y-5">
      <PrintHeader title="Rate Plans" orientation="landscape" />
      <header className="flex items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <Tags className="w-7 h-7 text-[#b8943f]" />
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Rate Plans</h1>
            <p className="text-sm text-[#1a1814]/60">How you charge customers for your value-addition work.</p>
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

      <HelpCallout title="Anatomy of a rate plan" tone="tip">
        The billing formula a production order uses when invoicing:
        <pre className="mt-2 bg-white/50 rounded px-2 py-1 text-[11px] leading-relaxed">
{`base       = per_unit_rate × output_qty
if includes_materials_at_cost:
  base    += sum of own-stock consumed (at WAvg cost)
overhead   = base × overhead_pct%
subtotal   = base + overhead
margin     = subtotal × margin_pct%
total      = subtotal + margin`}
        </pre>
        <p className="mt-2 opacity-80">
          Each customer is assigned <i>one active plan at a time</i>. Reassigning auto-deactivates
          the previous one. Plans are versioned, so historical invoices stay reproducible.
        </p>
      </HelpCallout>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {plans.length === 0 ? (
        <EmptyStateGuide
          title="No rate plans yet"
          description="Define how much you charge per processed unit and any markups."
          steps={[
            "Choose a short code (e.g. STITCH-STD) and a friendly name.",
            "Set per_unit_rate (flat charge per output unit).",
            "Decide whether to pass own-stock material cost back to the customer.",
            "Optionally add overhead % and margin % uplifts.",
            "Assign the plan to one or more customers.",
          ]}
        />
      ) : (
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#faf6ec] text-[#1a1814]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">Code</th>
                <th className="text-left px-4 py-2">Name</th>
                <th className="text-left px-4 py-2">Per unit</th>
                <th className="text-left px-4 py-2">Mat&apos;l</th>
                <th className="text-left px-4 py-2">Ovh%</th>
                <th className="text-left px-4 py-2">Margin%</th>
                <th className="text-left px-4 py-2">v</th>
                <th className="text-left px-4 py-2">Active</th>
              </tr>
            </thead>
            <tbody>
              {plans.map(p => (
                <tr key={p.id} className="border-t border-[#ede9e2]">
                  <td className="px-4 py-2 font-mono text-xs">{p.code}</td>
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-4 py-2">{p.per_unit_rate}</td>
                  <td className="px-4 py-2">{p.includes_materials_at_cost ? "yes" : "no"}</td>
                  <td className="px-4 py-2">{p.overhead_pct}</td>
                  <td className="px-4 py-2">{p.margin_pct}</td>
                  <td className="px-4 py-2">v{p.version}</td>
                  <td className="px-4 py-2">
                    {p.is_active
                      ? <span className="text-emerald-700 font-semibold">Active</span>
                      : <span className="text-[#1a1814]/50">Archived</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
