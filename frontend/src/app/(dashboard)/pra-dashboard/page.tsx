"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  PlusCircle, CheckCircle2, XCircle, Clock, Banknote,
  CreditCard, FileSignature, ChevronRight,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt, useSettings } from "@/context/SettingsContext"
import { usePRAPortal } from "@/hooks/usePRAPortal"

interface InvoiceItem {
  id: number
  number: string
  customer_name: string
  issue_date: string
  total: number
  pra_status: string
  pra_fiscal_number: string | null
  payment_mode: number | null
}

interface InvoiceList {
  total: number
  items: InvoiceItem[]
}

function praStatusBadge(status: string) {
  if (status === "submitted")
    return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-100 text-green-700">✓ Submitted</span>
  if (status === "failed")
    return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700">✗ Failed</span>
  if (status === "pending")
    return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">⏳ Pending</span>
  return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">—</span>
}

function paymentLabel(mode: number | null) {
  const map: Record<number, string> = { 1: "Cash", 2: "Card", 3: "Gift", 4: "Loyalty", 5: "Mixed", 6: "Cheque" }
  return mode ? (map[mode] ?? "—") : "—"
}

export default function PRADashboardPage() {
  const { isPortal, settled } = usePRAPortal()
  const router = useRouter()
  const fmt = useFmt()
  const { settings } = useSettings()
  const currency = settings.currency ?? "PKR"

  const [invoices, setInvoices] = useState<InvoiceItem[]>([])
  const [loading, setLoading] = useState(true)

  // Non-portal users shouldn't land here
  useEffect(() => {
    if (settled && !isPortal) router.replace("/dashboard")
  }, [settled, isPortal, router])

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10)
    apiFetch<InvoiceList>(`/api/invoices?date_from=${today}&date_to=${today}&limit=100&sort_by=issue_date&sort_dir=desc`)
      .then(d => setInvoices(d.items))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // Derive KPIs from today's invoices
  const todayCount  = invoices.length
  const todaySales  = invoices.reduce((s, i) => s + i.total, 0)
  const submitted   = invoices.filter(i => i.pra_status === "submitted").length
  const failed      = invoices.filter(i => i.pra_status === "failed").length
  const pending     = invoices.filter(i => i.pra_status === "pending").length
  const cashTotal   = invoices.filter(i => i.payment_mode === 1).reduce((s, i) => s + i.total, 0)
  const cardTotal   = invoices.filter(i => i.payment_mode === 2).reduce((s, i) => s + i.total, 0)

  const recent = invoices.slice(0, 8)

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-5xl mx-auto">

      {/* Header + New Invoice CTA */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-serif text-[#1a1814]">Sales Dashboard</h1>
          <p className="text-xs text-[#1a1814]/50 mt-0.5">
            {new Date().toLocaleDateString("en-PK", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
          </p>
        </div>
        <Link
          href="/invoices/new"
          className="flex items-center gap-2 px-4 py-2.5 bg-[#b8943f] hover:bg-[#a07830] text-white rounded-xl font-semibold text-sm transition-colors shadow-sm"
        >
          <PlusCircle className="w-4 h-4" />
          New Invoice
        </Link>
      </div>

      {/* KPI cards — row 1: sales summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white rounded-xl p-4 border border-[#ede9e2] shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">Today&apos;s Sales</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-1 tabular-nums">{fmt(todaySales)}</p>
          <p className="text-[11px] text-[#1a1814]/50 mt-0.5">{todayCount} invoice{todayCount !== 1 ? "s" : ""} · {currency}</p>
        </div>

        <div className="bg-white rounded-xl p-4 border border-[#ede9e2] shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">PRA Submitted</p>
          <p className="text-2xl font-bold text-green-600 mt-1 tabular-nums">{submitted}</p>
          <div className="flex items-center gap-1 mt-0.5">
            <CheckCircle2 className="w-3 h-3 text-green-500" />
            <p className="text-[11px] text-[#1a1814]/50">of {todayCount} invoices</p>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-[#ede9e2] shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">Failed / Pending</p>
          <p className="text-2xl font-bold text-red-500 mt-1 tabular-nums">{failed}</p>
          <div className="flex items-center gap-1 mt-0.5">
            {pending > 0
              ? <><Clock className="w-3 h-3 text-amber-500" /><p className="text-[11px] text-[#1a1814]/50">{pending} pending</p></>
              : <p className="text-[11px] text-[#1a1814]/50">0 pending</p>
            }
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 border border-[#ede9e2] shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">Cash / Card</p>
          <div className="flex items-center gap-1.5 mt-1">
            <Banknote className="w-4 h-4 text-emerald-500 flex-shrink-0" />
            <p className="text-base font-bold text-[#1a1814] tabular-nums">{fmt(cashTotal)}</p>
          </div>
          <div className="flex items-center gap-1.5 mt-1">
            <CreditCard className="w-4 h-4 text-blue-500 flex-shrink-0" />
            <p className="text-base font-bold text-[#1a1814] tabular-nums">{fmt(cardTotal)}</p>
          </div>
        </div>
      </div>

      {/* Recent invoices */}
      <div className="bg-white rounded-xl border border-[#ede9e2] shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#ede9e2]">
          <div className="flex items-center gap-2">
            <FileSignature className="w-4 h-4 text-[#b8943f]" />
            <h2 className="text-sm font-semibold text-[#1a1814]">Today&apos;s Invoices</h2>
          </div>
          <Link href="/invoices" className="flex items-center gap-1 text-xs text-[#b8943f] hover:underline">
            View all <ChevronRight className="w-3 h-3" />
          </Link>
        </div>

        {loading ? (
          <div className="p-8 text-center text-sm text-[#1a1814]/40">Loading…</div>
        ) : recent.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm text-[#1a1814]/40 mb-3">No invoices yet today</p>
            <Link
              href="/invoices/new"
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg text-sm font-medium hover:bg-[#a07830] transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              Create first invoice
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#ede9e2] bg-[#f6f3ee]/60">
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/40">Invoice #</th>
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/40">Customer</th>
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/40 hidden sm:table-cell">Payment</th>
                  <th className="text-right px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/40">Amount ({currency})</th>
                  <th className="text-center px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/40">PRA</th>
                  <th className="px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/40 hidden md:table-cell">FIN</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((inv, idx) => (
                  <tr
                    key={inv.id}
                    className={`border-b border-[#ede9e2] hover:bg-[#f6f3ee]/60 cursor-pointer transition-colors ${idx % 2 === 0 ? "" : "bg-[#f6f3ee]/30"}`}
                    onClick={() => router.push(`/invoices/${inv.id}`)}
                  >
                    <td className="px-4 py-2.5 font-mono text-xs text-[#b8943f] whitespace-nowrap">{inv.number}</td>
                    <td className="px-4 py-2.5 text-[#1a1814] truncate max-w-[140px]">{inv.customer_name || "Walk-in"}</td>
                    <td className="px-4 py-2.5 text-[#1a1814]/60 text-xs hidden sm:table-cell">{paymentLabel(inv.payment_mode)}</td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-[#1a1814]">{fmt(inv.total)}</td>
                    <td className="px-4 py-2.5 text-center">{praStatusBadge(inv.pra_status)}</td>
                    <td className="px-4 py-2.5 font-mono text-[10px] text-[#1a1814]/50 hidden md:table-cell">
                      {inv.pra_fiscal_number ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Quick links */}
      {failed > 0 && (
        <div className="flex items-center gap-3 p-3 rounded-xl bg-red-50 border border-red-200">
          <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-red-700">{failed} invoice{failed !== 1 ? "s" : ""} failed PRA submission</p>
            <p className="text-xs text-red-500">Check the submission logs to retry</p>
          </div>
          <Link href="/pra-logs" className="text-xs font-bold text-red-700 hover:underline whitespace-nowrap">
            View Logs →
          </Link>
        </div>
      )}

    </div>
  )
}
