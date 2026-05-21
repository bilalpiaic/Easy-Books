"use client"

import { useEffect, useState } from "react"
import { PackagePlus } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { EmptyStateGuide } from "@/components/guidance/EmptyStateGuide"

interface GrnLine { id: number; product_id: number; qty: string; lot_no: string | null }
interface Grn {
  id: number; number: string; customer_id: number; received_date: string
  declared_value: string; lines: GrnLine[]
}

export default function GrnPage() {
  const [grns, setGrns] = useState<Grn[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ items: Grn[] }>("/api/grn")
      .then(d => setGrns(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-sm text-[#1a1814]/60">Loading…</p>

  return (
    <div className="space-y-5">
      <header className="flex items-center gap-3">
        <PackagePlus className="w-7 h-7 text-[#b8943f]" />
        <div>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Goods Receipt (GRN)</h1>
          <p className="text-sm text-[#1a1814]/60">Customer-supplied material received into your godown.</p>
        </div>
      </header>

      <HelpCallout title="Why GRN is custodial, not a purchase" tone="tip">
        When a customer drops off fabric/material for you to process, it&apos;s never your asset —
        it stays the customer&apos;s property the whole time. A GRN posts to your <b>godown</b>
        location and (optionally) to a pair of <b>memo accounts</b> (1210 Customer Goods on
        Hand / 2150 Customer Goods Liability). Memo accounts show on a separate section of the
        balance sheet so they don&apos;t inflate your assets.
        <p className="mt-2 opacity-80">
          On delivery of the finished product, the memo balance is automatically released.
        </p>
      </HelpCallout>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {grns.length === 0 ? (
        <EmptyStateGuide
          title="No GRNs yet"
          description="Record what a customer has dropped off for processing."
          steps={[
            "Ensure the customer and product (raw material) records exist.",
            "Optionally set a declared_value so a memo JE is posted (Dr 1210 / Cr 2150).",
            "Add lot numbers per line for traceability.",
          ]}
        />
      ) : (
        <div className="bg-white border border-[#ede9e2] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#faf6ec] text-[#1a1814]/70 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">GRN #</th>
                <th className="text-left px-4 py-2">Customer</th>
                <th className="text-left px-4 py-2">Received</th>
                <th className="text-left px-4 py-2">Lines</th>
                <th className="text-left px-4 py-2">Declared value</th>
              </tr>
            </thead>
            <tbody>
              {grns.map(g => (
                <tr key={g.id} className="border-t border-[#ede9e2]">
                  <td className="px-4 py-2 font-mono text-xs">{g.number}</td>
                  <td className="px-4 py-2">#{g.customer_id}</td>
                  <td className="px-4 py-2">{g.received_date}</td>
                  <td className="px-4 py-2">{g.lines.length}</td>
                  <td className="px-4 py-2">{g.declared_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
