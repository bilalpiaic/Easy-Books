"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Clock } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"

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
  { key: "current",  label: "Current",  color: "bg-green-50 border-green-200 text-green-700" },
  { key: "1_30",    label: "1-30 Days", color: "bg-yellow-50 border-yellow-200 text-yellow-700" },
  { key: "31_60",   label: "31-60 Days",color: "bg-orange-50 border-orange-200 text-orange-700" },
  { key: "61_90",   label: "61-90 Days",color: "bg-red-50 border-red-200 text-red-700" },
  { key: "over_90", label: "90+ Days",  color: "bg-red-100 border-red-300 text-red-800" },
] as const

export default function ARAgingPage() {
  const fmt = useFmt()
  const [data, setData] = useState<AgingData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setIsLoading(true)
    apiFetch<AgingData>("/api/invoices/aging")
      .then(d => { setData(d); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [])

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">AR Aging</h1>
          <p className="text-[#1a1814]/60">Outstanding receivables by age bucket</p>
        </div>
        <Clock className="w-7 h-7 text-[#b8943f] hidden md:block" />
      </div>

      {/* Bucket summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
        {BUCKETS.map(b => (
          <div key={b.key} className={`rounded-xl border p-4 ${b.color}`}>
            <p className="text-xs font-bold uppercase tracking-widest mb-1 opacity-70">{b.label}</p>
            <p className="text-lg font-mono font-bold">
              {data ? fmt(data[b.key as keyof AgingData] as number) : "—"}
            </p>
          </div>
        ))}
      </div>

      {/* Items table */}
      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[600px]">
            <thead>
              <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Customer</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Invoice #</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Due Date</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Days Past</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Outstanding</th>
                <th className="ui-th text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Bucket</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1a1814]/5">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-[#1a1814]/75">Loading...</td>
                </tr>
              ) : !data || data.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-[#1a1814]/75">No outstanding receivables.</td>
                </tr>
              ) : (
                data.items.map(item => (
                  <tr key={item.id} className="hover:bg-[#f6f3ee]/30 transition-colors">
                    <td className="ui-td font-medium text-[#1a1814]">
                      {item.customer_id ? (
                        <Link
                          href={`/customers/${item.customer_id}/ledger`}
                          className="hover:text-[#b8943f] hover:underline underline-offset-2 transition-colors"
                        >
                          {item.name}
                        </Link>
                      ) : (
                        item.name
                      )}
                    </td>
                    <td className="ui-td font-mono text-sm text-[#b8943f]">{item.number}</td>
                    <td className="ui-td text-sm text-[#1a1814]/70">{item.due_date}</td>
                    <td className="ui-td text-right font-mono text-sm text-[#1a1814]/70">{item.days_past}</td>
                    <td className="ui-td text-right font-mono text-sm font-semibold">{fmt(item.amount)}</td>
                    <td className="ui-td">
                      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-[#b8943f]/10 text-[#b8943f]">
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
