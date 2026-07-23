"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import {
  User, Mail, Phone, MapPin, BookOpen, FileText,
  Package, Pencil, ArrowLeft, TrendingUp, Plus,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { useTranslation } from "react-i18next"
import StatusBadge from "@/components/StatusBadge"

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
  status: string
}

export default function CustomerHubPage() {
  const { t } = useTranslation()

  const params = useParams()
  const id = params.id as string
  const fmt = useFmt()

  const [customer, setCustomer] = useState<Customer | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [portalMsg, setPortalMsg] = useState<string | null>(null)

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

  if (loading) return <div className="p-8 text-sm text-[var(--text-primary)]/50 text-center">Loading…</div>
  if (error)   return <div className="p-8 text-sm text-red-600">{error}</div>
  if (!customer) return null

  const mintPortal = async () => {
    setPortalMsg(null)
    try {
      const r = await apiFetch<{ token: string; path: string }>(
        `/api/portal/mint?entity_type=customer&entity_id=${id}`,
        { method: "POST" },
      )
      const url = `${window.location.origin}${r.path}`
      await navigator.clipboard.writeText(url)
      setPortalMsg("Portal link copied to clipboard")
    } catch (e) {
      setPortalMsg(e instanceof Error ? e.message : "Failed to mint portal link")
    }
  }

  const outstanding = invoices
    .filter(i => !["paid", "void", "reversed"].includes(i.status))
    .reduce((s, i) => s + Number(i.total), 0)
  const totalInvoiced = invoices.reduce((s, i) => s + Number(i.total), 0)
  const overdueCount  = invoices.filter(i => i.status === "overdue").length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Link href="/customers" className="text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">{customer.name}</h1>
            <p className="text-sm text-[var(--text-primary)]/55 mt-0.5">Customer profile</p>
          </div>
          {!customer.is_active && (
            <span className="inline-block bg-slate-100 text-slate-500 text-xs font-medium px-2.5 py-0.5 rounded-full border border-slate-200">{t('status.inactive', 'Inactive')}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={mintPortal}
            className="inline-flex items-center gap-2 border border-[var(--border)] px-3 py-2 rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors"
          >
            Portal link
          </button>
          <Link
            href={`/customers/${id}/edit`}
            className="inline-flex items-center gap-2 border border-[var(--border)] px-3 py-2 rounded-lg text-sm text-[var(--text-primary)]/70 hover:bg-[#f0ede6] transition-colors"
          >
            <Pencil className="w-4 h-4" /> Edit
          </Link>
        </div>
      </div>
      {portalMsg && (
        <p className="text-sm text-[var(--text-primary)]/70">{portalMsg}</p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Contact info */}
        <div className="bg-white border border-[var(--border)] rounded-xl p-5 space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]/50 mb-3">Contact</h2>
          <div className="flex items-start gap-2 text-sm text-[var(--text-primary)]">
            <User className="w-4 h-4 text-[var(--text-primary)]/30 mt-0.5 shrink-0" />
            <span>{customer.name}</span>
          </div>
          {customer.email && (
            <div className="flex items-start gap-2 text-sm text-[var(--text-primary)]/70">
              <Mail className="w-4 h-4 text-[var(--text-primary)]/30 mt-0.5 shrink-0" />
              <a href={`mailto:${customer.email}`} className="hover:text-[var(--primary)]">{customer.email}</a>
            </div>
          )}
          {customer.phone && (
            <div className="flex items-start gap-2 text-sm text-[var(--text-primary)]/70">
              <Phone className="w-4 h-4 text-[var(--text-primary)]/30 mt-0.5 shrink-0" />
              <span>{customer.phone}</span>
            </div>
          )}
          {customer.address && (
            <div className="flex items-start gap-2 text-sm text-[var(--text-primary)]/70">
              <MapPin className="w-4 h-4 text-[var(--text-primary)]/30 mt-0.5 shrink-0" />
              <span className="whitespace-pre-line">{customer.address}</span>
            </div>
          )}
        </div>

        {/* Financial summary */}
        <div className="lg:col-span-2 grid grid-cols-3 gap-3">
          <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">Outstanding</p>
            <p className={`text-xl font-bold tabular-nums ${outstanding > 0 ? "text-amber-700" : "text-emerald-600"}`}>
              {fmt(outstanding)}
            </p>
          </div>
          <div className="bg-white border border-[var(--border)] rounded-xl p-4 text-center">
            <p className="text-xs text-[var(--text-primary)]/50 uppercase tracking-wide mb-1">Invoiced (last 10)</p>
            <p className="text-xl font-bold tabular-nums text-[var(--text-primary)]">{fmt(totalInvoiced)}</p>
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
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Link
          href={`/customers/${id}/ledger`}
          className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
        >
          <BookOpen className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">Ledger</span>
        </Link>
        <Link
          href={`/customers/${id}/statement`}
          className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
        >
          <FileText className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">Statement</span>
        </Link>
        <Link
          href={`/customers/${id}/products`}
          className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
        >
          <Package className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">Products</span>
        </Link>
        <Link
          href={`/invoices?customer_id=${id}`}
          className="bg-white border border-[var(--border)] rounded-xl p-4 flex flex-col items-center gap-2 hover:border-[var(--primary)] hover:bg-[#faf8f4] transition-colors group"
        >
          <TrendingUp className="w-5 h-5 text-[var(--primary)]/70 group-hover:text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">All Invoices</span>
        </Link>
        <Link
          href={`/invoices/new?customer_id=${id}`}
          className="bg-[var(--primary)] rounded-xl p-4 flex flex-col items-center gap-2 hover:bg-[var(--primary-dark)] transition-colors group"
        >
          <Plus className="w-5 h-5 text-white" />
          <span className="text-sm font-medium text-white">New Invoice</span>
        </Link>
      </div>

      {/* Recent invoices */}
      <div className="bg-white border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Recent Invoices</h2>
          <Link href={`/invoices?customer_id=${id}`} className="text-xs text-[var(--primary)] hover:underline">
            View all
          </Link>
        </div>
        {invoices.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--text-primary)]/40">
            No invoices yet for this customer.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[#faf8f4]">
                <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">Number</th>
                <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">Date</th>
                <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">Due</th>
                <th className="text-left px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">{t('col.status', 'Status')}</th>
                <th className="text-right px-4 py-2 font-semibold text-[var(--text-primary)]/60 text-xs">{t('col.total', 'Total')}</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map(inv => (
                <tr key={inv.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[#faf8f4]">
                  <td className="px-4 py-2">
                    <Link href={`/invoices/${inv.id}`} className="font-mono text-[var(--primary)] hover:underline text-xs">
                      {inv.number}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-[var(--text-primary)]/60 text-xs tabular-nums">{inv.issue_date}</td>
                  <td className="px-4 py-2 text-[var(--text-primary)]/60 text-xs tabular-nums">{inv.due_date}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={inv.status} />
                  </td>
                  <td className={`px-4 py-2 text-right tabular-nums text-xs ${["paid","void","reversed"].includes(inv.status) ? "text-[var(--text-primary)]/40" : "font-medium"}`}>
                    {fmt(inv.total)}
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
