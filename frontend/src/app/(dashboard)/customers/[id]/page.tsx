"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import {
  User, Mail, Phone, MapPin, BookOpen, FileText,
  Package, Pencil, ArrowLeft, TrendingUp,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"

interface Customer {
  id: number
  name: string
  email: string | null
  phone: string | null
  address: string | null
  opening_balance: number
  is_active: boolean
  payment_term_id: number | null
}

interface Invoice {
  id: number
  number: string
  issue_date: string
  due_date: string
  total: number
  amount_due: number
  status: string
}

const STATUS_TONE: Record<string, string> = {
  draft:    "bg-slate-100 text-slate-700",
  sent:     "bg-blue-100 text-blue-700",
  posted:   "bg-blue-100 text-blue-700",
  overdue:  "bg-red-100 text-red-700",
  partial:  "bg-amber-100 text-amber-700",
  paid:     "bg-emerald-100 text-emerald-700",
  reversed: "bg-slate-100 text-slate-500",
  void:     "bg-slate-100 text-slate-400",
}

export default function CustomerHubPage() {
  const params = useParams()
  const id = params.id as string
  const fmt = useFmt()

  const [customer, setCustomer] = useState<Customer | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<Customer>(`/api/customers/${id}`),
      apiFetch<{ total: number; items: Invoice[] }>(
        `/api/invoices?customer_id=${id}&limit=10&sort_by=issue_date&sort_dir=desc`
      ),
    ])
      .then(([cust, inv]) => {
        setCustomer(cust)
        setInvoices(inv.items)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="p-8 text-sm text-[#1a1814]/50 text-center">Loading…</div>
  if (error)   return <div className="p-8 text-sm text-red-600">{error}</div>
  if (!customer) return null

  const outstanding = invoices
    .filter(i => !["paid", "void", "reversed"].includes(i.status))
    .reduce((s, i) => s + Number(i.amount_due), 0)
  const totalInvoiced = invoices.reduce((s, i) => s + Number(i.total), 0)
  const overdueCount  = invoices.filter(i => i.status === "overdue").length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Link href="/customers" className="text-[#1a1814]/40 hover:text-[#b8943f] transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">{customer.name}</h1>
            <p className="text-sm text-[#1a1814]/55 mt-0.5">Customer profile</p>
          </div>
          {!customer.is_active && (
            <span className="inline-block bg-slate-100 text-slate-500 text-xs font-medium px-2.5 py-0.5 rounded-full border border-slate-200">
              Inactive
            </span>
          )}
        </div>
        <Link
          href={`/customers/${id}/edit`}
          className="inline-flex items-center gap-2 border border-[#ede9e2] px-3 py-2 rounded-lg text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors"
        >
          <Pencil className="w-4 h-4" /> Edit
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Contact info */}
        <div className="bg-white border border-[#ede9e2] rounded-xl p-5 space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50 mb-3">Contact</h2>
          <div className="flex items-start gap-2 text-sm text-[#1a1814]">
            <User className="w-4 h-4 text-[#1a1814]/30 mt-0.5 shrink-0" />
            <span>{customer.name}</span>
          </div>
          {customer.email && (
            <div className="flex items-start gap-2 text-sm text-[#1a1814]/70">
              <Mail className="w-4 h-4 text-[#1a1814]/30 mt-0.5 shrink-0" />
              <a href={`mailto:${customer.email}`} className="hover:text-[#b8943f]">{customer.email}</a>
            </div>
          )}
          {customer.phone && (
            <div className="flex items-start gap-2 text-sm text-[#1a1814]/70">
              <Phone className="w-4 h-4 text-[#1a1814]/30 mt-0.5 shrink-0" />
              <span>{customer.phone}</span>
            </div>
          )}
          {customer.address && (
            <div className="flex items-start gap-2 text-sm text-[#1a1814]/70">
              <MapPin className="w-4 h-4 text-[#1a1814]/30 mt-0.5 shrink-0" />
              <span className="whitespace-pre-line">{customer.address}</span>
            </div>
          )}
        </div>

        {/* Financial summary */}
        <div className="lg:col-span-2 grid grid-cols-3 gap-3">
          <div className="bg-white border border-[#ede9e2] rounded-xl p-4 text-center">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-1">Outstanding</p>
            <p className={`text-xl font-bold tabular-nums ${outstanding > 0 ? "text-amber-700" : "text-emerald-600"}`}>
              {fmt(outstanding)}
            </p>
          </div>
          <div className="bg-white border border-[#ede9e2] rounded-xl p-4 text-center">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-1">Invoiced (last 10)</p>
            <p className="text-xl font-bold tabular-nums text-[#1a1814]">{fmt(totalInvoiced)}</p>
          </div>
          <div className="bg-white border border-[#ede9e2] rounded-xl p-4 text-center">
            <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide mb-1">Overdue</p>
            <p className={`text-xl font-bold tabular-nums ${overdueCount > 0 ? "text-red-600" : "text-emerald-600"}`}>
              {overdueCount}
            </p>
          </div>
        </div>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Link
          href={`/customers/${id}/ledger`}
          className="bg-white border border-[#ede9e2] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[#b8943f] hover:bg-[#faf8f4] transition-colors group"
        >
          <BookOpen className="w-5 h-5 text-[#b8943f]/70 group-hover:text-[#b8943f]" />
          <span className="text-sm font-medium text-[#1a1814]">Ledger</span>
        </Link>
        <Link
          href={`/customers/${id}/statement`}
          className="bg-white border border-[#ede9e2] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[#b8943f] hover:bg-[#faf8f4] transition-colors group"
        >
          <FileText className="w-5 h-5 text-[#b8943f]/70 group-hover:text-[#b8943f]" />
          <span className="text-sm font-medium text-[#1a1814]">Statement</span>
        </Link>
        <Link
          href={`/customers/${id}/products`}
          className="bg-white border border-[#ede9e2] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[#b8943f] hover:bg-[#faf8f4] transition-colors group"
        >
          <Package className="w-5 h-5 text-[#b8943f]/70 group-hover:text-[#b8943f]" />
          <span className="text-sm font-medium text-[#1a1814]">Products</span>
        </Link>
        <Link
          href={`/invoices?customer_id=${id}`}
          className="bg-white border border-[#ede9e2] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[#b8943f] hover:bg-[#faf8f4] transition-colors group"
        >
          <TrendingUp className="w-5 h-5 text-[#b8943f]/70 group-hover:text-[#b8943f]" />
          <span className="text-sm font-medium text-[#1a1814]">All Invoices</span>
        </Link>
      </div>

      {/* Recent invoices */}
      <div className="bg-white border border-[#ede9e2] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[#ede9e2] flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#1a1814]">Recent Invoices</h2>
          <Link href={`/invoices?customer_id=${id}`} className="text-xs text-[#b8943f] hover:underline">
            View all
          </Link>
        </div>
        {invoices.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[#1a1814]/40">
            No invoices yet for this customer.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#ede9e2] bg-[#faf8f4]">
                <th className="text-left px-4 py-2 font-semibold text-[#1a1814]/60 text-xs">Number</th>
                <th className="text-left px-4 py-2 font-semibold text-[#1a1814]/60 text-xs">Date</th>
                <th className="text-left px-4 py-2 font-semibold text-[#1a1814]/60 text-xs">Due</th>
                <th className="text-left px-4 py-2 font-semibold text-[#1a1814]/60 text-xs">Status</th>
                <th className="text-right px-4 py-2 font-semibold text-[#1a1814]/60 text-xs">Total</th>
                <th className="text-right px-4 py-2 font-semibold text-[#1a1814]/60 text-xs">Due</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map(inv => (
                <tr key={inv.id} className="border-b border-[#ede9e2] last:border-0 hover:bg-[#faf8f4]">
                  <td className="px-4 py-2">
                    <Link href={`/invoices/${inv.id}`} className="font-mono text-[#b8943f] hover:underline text-xs">
                      {inv.number}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-[#1a1814]/60 text-xs tabular-nums">{inv.issue_date}</td>
                  <td className="px-4 py-2 text-[#1a1814]/60 text-xs tabular-nums">{inv.due_date}</td>
                  <td className="px-4 py-2">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_TONE[inv.status] ?? "bg-slate-100 text-slate-600"}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-xs">{fmt(inv.total)}</td>
                  <td className={`px-4 py-2 text-right tabular-nums text-xs font-medium ${Number(inv.amount_due) > 0 ? "text-amber-700" : "text-[#1a1814]/40"}`}>
                    {Number(inv.amount_due) > 0 ? fmt(inv.amount_due) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
