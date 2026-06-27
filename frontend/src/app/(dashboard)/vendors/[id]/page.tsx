"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import {
  Building2, Mail, Phone, MapPin, BookOpen, FileText,
  Pencil, ArrowLeft, TrendingDown, Plus,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { useTranslation } from "react-i18next"

interface Vendor {
  id: number
  name: string
  email: string | null
  phone: string | null
  address: string | null
  opening_balance: number
  is_active: boolean
  payment_term_id: number | null
}

interface Bill {
  id: number
  number: string
  bill_date: string
  due_date: string
  total: number
  status: string
}

const STATUS_TONE: Record<string, string> = {
  draft:    "bg-slate-100 text-slate-700",
  received: "bg-blue-100 text-blue-700",
  overdue:  "bg-red-100 text-red-700",
  partial:  "bg-amber-100 text-amber-700",
  paid:     "bg-emerald-100 text-emerald-700",
  reversed: "bg-slate-100 text-slate-500",
}

export default function VendorHubPage() {
  const { t } = useTranslation()

  const params = useParams()
  const id = params.id as string
  const fmt = useFmt()

  const [vendor, setVendor] = useState<Vendor | null>(null)
  const [bills, setBills]   = useState<Bill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch<Vendor>(`/api/vendors/${id}`),
      apiFetch<{ total: number; items: Bill[] }>(
        `/api/bills?vendor_id=${id}&limit=10&sort_by=bill_date&sort_dir=desc`
      ),
    ])
      .then(([vend, b]) => {
        setVendor(vend)
        setBills(b.items)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="p-8 text-sm text-[var(--text-primary)]/50 text-center">Loading…</div>
  if (error)   return <div className="p-8 text-sm text-red-600">{error}</div>
  if (!vendor) return null

  const outstanding = bills
    .filter(b => !["paid", "reversed"].includes(b.status))
    .reduce((s, b) => s + Number(b.total), 0)
  const totalBilled   = bills.reduce((s, b) => s + Number(b.total), 0)
  const overdueCount  = bills.filter(b => b.status === "overdue").length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Link href="/vendors" className="text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">{vendor.name}</h1>
            <p className="text-sm text-[var(--text-primary)]/55 mt-0.5">Vendor profile</p>
          </div>
          {!vendor.is_active && (
            <span className="inline-block bg-slate-100 text-slate-500 text-xs font-medium px-2.5 py-0.5 rounded-full border border-slate-200">{t('status.inactive', 'Inactive')}</span>
          )}
        </div>
        <Link
          href={`/vendors/${id}/edit`}
          className="inline-flex items-center gap-2 border border-[var(--border)] px-3 py-2 rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[var(--bg-page)] transition-colors"
        >
          <Pencil className="w-4 h-4" /> Edit
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Contact info */}
        <div className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]/50 mb-3">Contact</h2>
          <div className="flex items-start gap-2 text-sm text-[var(--text-primary)]">
            <Building2 className="w-4 h-4 text-[var(--text-primary)]/30 mt-0.5 shrink-0" />
            <span>{vendor.name}</span>
          </div>
          {vendor.email && (
            <div className="flex items-start gap-2 text-sm text-[var(--text-primary)]/70">
              <Mail className="w-4 h-4 text-[var(--text-primary)]/30 mt-0.5 shrink-0" />
              <a href={`mailto:${vendor.email}`} className="hover:text-[var(--primary)]">{vendor.email}</a>
            </div>
          )}
          {vendor.phone && (
            <div className="flex items-start gap-2 text-sm text-[var(--text-primary)]/70">
              <Phone className="w-4 h-4 text-[var(--text-primary)]/30 mt-0.5 shrink-0" />
              <span>{vendor.phone}</span>
            </div>
          )}
          {vendor.address && (
            <div className="flex items-start gap-2 text-sm text-[var(--text-primary)]/70">
              <MapPin className="w-4 h-4 text-[var(--text-primary)]/30 mt-0.5 shrink-0" />
              <span className="whitespace-pre-line">{vendor.address}</span>
            </div>
          )}
        </div>

        {/* Financial summary */}
        <div className="lg:col-span-2 grid grid-cols-3 gap-3">
          <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">Outstanding AP</p>
            <p className={`text-xl font-bold tabular-nums ${outstanding > 0 ? "text-amber-700" : "text-emerald-600"}`}>
              {fmt(outstanding)}
            </p>
          </div>
          <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">Billed (last 10)</p>
            <p className="text-xl font-bold tabular-nums text-[var(--text-primary)]">{fmt(totalBilled)}</p>
          </div>
          <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">{t('status.overdue', 'Overdue')}</p>
            <p className={`text-xl font-bold tabular-nums ${overdueCount > 0 ? "text-red-600" : "text-emerald-600"}`}>
              {overdueCount}
            </p>
          </div>
        </div>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Link
          href={`/vendors/${id}/ledger`}
          className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[var(--bg-page)] transition-colors group"
        >
          <BookOpen className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">Ledger</span>
        </Link>
        <Link
          href={`/vendors/${id}/statement`}
          className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[var(--bg-page)] transition-colors group"
        >
          <FileText className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">Statement</span>
        </Link>
        <Link
          href={`/bills?vendor_id=${id}`}
          className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[var(--bg-page)] transition-colors group"
        >
          <TrendingDown className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">All Bills</span>
        </Link>
        <Link
          href={`/bills/new?vendor_id=${id}`}
          className="bg-[var(--primary)] rounded-xl p-4 flex flex-col items-center gap-2 hover:bg-[var(--primary-dark)] transition-colors group"
        >
          <Plus className="w-5 h-5 text-white" />
          <span className="text-sm font-medium text-white">New Bill</span>
        </Link>
      </div>

      {/* Recent bills */}
      <div className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Recent Bills</h2>
          <Link href={`/bills?vendor_id=${id}`} className="text-xs text-[var(--primary)] hover:underline">
            View all
          </Link>
        </div>
        {bills.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--text-primary)]/40">
            No bills yet for this vendor.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--bg-page)]">
                <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">Number</th>
                <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">Date</th>
                <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">Due</th>
                <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">{t('col.status', 'Status')}</th>
                <th className="text-right px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">{t('col.total', 'Total')}</th>
              </tr>
            </thead>
            <tbody>
              {bills.map(bill => (
                <tr key={bill.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-page)]">
                  <td className="px-4 py-2">
                    <Link href={`/bills/${bill.id}`} className="font-mono text-[var(--primary)] hover:underline text-xs">
                      {bill.number}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-[var(--text-primary)]/60 text-xs tabular-nums">{bill.bill_date}</td>
                  <td className="px-4 py-2 text-[var(--text-primary)]/60 text-xs tabular-nums">{bill.due_date}</td>
                  <td className="px-4 py-2">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_TONE[bill.status] ?? "bg-slate-100 text-slate-600"}`}>
                      {bill.status}
                    </span>
                  </td>
                  <td className={`px-4 py-2 text-right tabular-nums text-xs ${["paid","reversed"].includes(bill.status) ? "text-[var(--text-primary)]/40" : "font-medium"}`}>
                    {fmt(bill.total)}
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
