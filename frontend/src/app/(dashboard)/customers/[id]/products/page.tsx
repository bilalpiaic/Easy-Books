'use client'
import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Download } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useFmt } from '@/context/SettingsContext'
import { downloadCSV } from '@/lib/utils'
import { useTranslation } from "react-i18next"

interface Row {
  product_id: number
  name: string
  code: string | null
  last_rate: number
  last_date: string
  total_qty: number
  invoice_count: number
}

export default function CustomerProducts({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const { id } = use(params)
  const fmt = useFmt()
  const [rows, setRows] = useState<Row[]>([])

  useEffect(() => {
    apiFetch<{ items: Row[] }>(`/api/customers/${id}/products`)
      .then(d => setRows(d.items))
      .catch(() => {})
  }, [id])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between print:hidden">
        <Link href="/customers" className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-[#1a1814]/65 hover:text-[#b8943f]">
          <ArrowLeft className="w-4 h-4" /> Customers
        </Link>
        <button
          onClick={() => downloadCSV('customer-products.csv', rows.map(r => ({ Product: r.name, Code: r.code ?? '', "Last Price": r.last_rate, "Last Date": r.last_date, "Total Qty": r.total_qty, Invoices: r.invoice_count })))}
          disabled={rows.length === 0}
          className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] disabled:opacity-40"
        >
          <Download className="w-4 h-4" /> CSV
        </button>
      </div>
      <h1 className="text-xl sm:text-3xl font-serif font-medium">Products Sold</h1>
      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">{t('col.product', 'Product')}</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Last Price</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Last Date</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Total Qty</th>
              <th className="ui-th text-right text-xs font-bold uppercase tracking-widest text-black/60">Invoices</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center text-black/50">No products sold yet.</td>
              </tr>
            ) : rows.map(r => (
              <tr key={r.product_id} className="hover:bg-[#f6f3ee]/50">
                <td className="ui-td">
                  <Link href={`/products/ledger?product=${r.product_id}`} className="hover:text-[#b8943f] hover:underline">
                    {r.name}
                  </Link>
                  {r.code && <span className="ml-2 font-mono text-xs text-[#b8943f]">{r.code}</span>}
                </td>
                <td className="ui-td text-right font-mono">{fmt(r.last_rate)}</td>
                <td className="ui-td text-right text-black/60">{r.last_date}</td>
                <td className="ui-td text-right font-mono">{r.total_qty.toLocaleString()}</td>
                <td className="ui-td text-right">{r.invoice_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
