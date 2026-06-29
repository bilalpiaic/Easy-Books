"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Clock, Printer, Download } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV, fmtDateJs } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface AgingItem {
  id: number
  name: string
  number: string
  due_date: string
  amount: number
  days_past: number
  bucket: string
  customer_id: number | null
}

interface AgingData {
  current: number
  "1_30": number
  "31_60": number
  "61_90": number
  over_90: number
  items: AgingItem[]
}

const BUCKETS = [
  { key: "current",  label: "Current",   bucketLabel: "current", color: "bg-green-50 border-green-200 text-green-700" },
  { key: "1_30",     label: "1-30 Days", bucketLabel: "1-30",    color: "bg-yellow-50 border-yellow-200 text-yellow-700" },
  { key: "31_60",    label: "31-60 Days",bucketLabel: "31-60",   color: "bg-orange-50 border-orange-200 text-orange-700" },
  { key: "61_90",    label: "61-90 Days",bucketLabel: "61-90",   color: "bg-red-50 border-red-200 text-red-700" },
  { key: "over_90",  label: "90+ Days",  bucketLabel: "90+",     color: "bg-red-100 border-red-300 text-red-800" },
] as const

export default function ARAgingPage() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const [data, setData] = useState<AgingData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedBucket, setSelectedBucket] = useState<string | null>(null)

  useEffect(() => {
    setIsLoading(true)
    apiFetch<AgingData>("/api/invoices/aging")
      .then(d => { setData(d); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [])

  const exportCsv = () => {
    if (!data) return
    downloadCSV("ar-aging.csv", data.items.map(r => ({
      Customer: r.name,
      "Invoice #": r.number,
      "Due Date": r.due_date,
      "Days Past Due": r.days_past,
      Outstanding: r.amount,
      Bucket: r.bucket,
    })))
  }

  const activeBucket = BUCKETS.find(b => b.key === selectedBucket) ?? null
  const filteredItems = data
    ? (activeBucket ? data.items.filter(i => i.bucket === activeBucket.bucketLabel) : data.items)
    : []

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">AR Aging</h1>
          <p className="text-[var(--text-primary)]/60">Outstanding receivables by age bucket</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={exportCsv}
            disabled={!data}
            className="p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60 disabled:opacity-40"
            title="Export CSV"
          >
            <Download className="w-5 h-5" />
          </button>
          <button
            onClick={() => window.print()}
            className="p-3 bg-white border border-[var(--text-primary)]/10 rounded-xl hover:bg-[var(--bg-page)] transition-colors text-[var(--text-primary)]/60"
            title="Print"
          >
            <Printer className="w-5 h-5" />
          </button>
          <Clock className="w-7 h-7 text-[var(--primary)] hidden md:block ml-2" />
        </div>
      </div>

      <PrintHeader title="AR Aging Report" subtitle={`As of ${fmtDateJs(new Date())}`} orientation="landscape" />

      {/* Bucket summary cards — click to filter the table below */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3 print:hidden">
        {BUCKETS.map(b => {
          const isActive = selectedBucket === b.key
          const isDimmed = selectedBucket !== null && !isActive
          return (
            <button
              key={b.key}
              onClick={() => setSelectedBucket(prev => prev === b.key ? null : b.key)}
              className={`rounded-xl border p-4 text-left transition-all select-none ${b.color}
                ${isActive ? "ring-2 ring-inset shadow-md scale-[1.02]" : "hover:shadow-sm hover:scale-[1.01]"}
                ${isDimmed ? "opacity-40" : ""}`}
              title={isActive ? "Click to show all" : `Filter by ${b.label}`}
            >
              <p className="text-xs font-bold uppercase tracking-widest mb-1 opacity-70">{b.label}</p>
              <p className="text-lg font-mono font-bold">
                {data ? fmt(data[b.key as keyof AgingData] as number) : "—"}
              </p>
            </button>
          )
        })}
      </div>

      {/* Active filter indicator */}
      {selectedBucket && (
        <div className="flex items-center justify-between mb-4 px-1 print:hidden">
          <p className="text-xs text-[var(--text-primary)]/50">
            Showing <strong>{filteredItems.length}</strong> item{filteredItems.length !== 1 ? "s" : ""} in <strong>{activeBucket?.label}</strong>
          </p>
          <button
            onClick={() => setSelectedBucket(null)}
            className="text-xs text-[var(--primary)] hover:underline underline-offset-2"
          >
            Show all
          </button>
        </div>
      )}
      {!selectedBucket && <div className="mb-4" />}

      {/* Items table */}
      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden print:rounded-none print:shadow-none print:border-0">
        <div className="overflow-x-auto freeze-col">
          <table className="w-full text-left border-collapse min-w-[600px]">
            <thead>
              <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">{t('col.customer', 'Customer')}</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Invoice #</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">{t('col.dueDate', 'Due Date')}</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Days Past</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">Outstanding</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Bucket</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-[var(--text-primary)]/75">{t('common.loading', 'Loading...')}</td>
                </tr>
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-[var(--text-primary)]/75">
                    {selectedBucket ? "No items in this bucket." : "No outstanding receivables."}
                  </td>
                </tr>
              ) : (
                filteredItems.map(item => (
                  <tr key={item.id} className="hover:bg-[var(--bg-page)]/30 transition-colors">
                    <td className="ui-td font-medium text-[var(--text-primary)]">
                      {item.customer_id ? (
                        <Link
                          href={`/customers/${item.customer_id}/ledger`}
                          className="hover:text-[var(--primary)] hover:underline underline-offset-2 transition-colors print:no-underline"
                        >
                          {item.name}
                        </Link>
                      ) : (
                        item.name
                      )}
                    </td>
                    <td className="ui-td font-mono text-sm">
                      <Link href={`/invoices/${item.id}`} className="text-[var(--primary)] hover:underline print:text-[var(--text-primary)]">{item.number}</Link>
                    </td>
                    <td className="ui-td text-sm text-[var(--text-primary)]/70">{item.due_date}</td>
                    <td className="ui-td text-right font-mono text-sm text-[var(--text-primary)]/70">{item.days_past}</td>
                    <td className="ui-td text-right font-mono text-sm font-semibold">{fmt(item.amount)}</td>
                    <td className="ui-td">
                      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-[var(--primary)]/10 text-[var(--primary)]">
                        {item.bucket}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
