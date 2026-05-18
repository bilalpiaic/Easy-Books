'use client'

import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'
import { fmtPKR } from '@/lib/utils'
import DateRangePicker from '@/components/DateRangePicker'

interface CashFlowData {
  period: { start: string; end: string }
  net_income: number
  operating_adjustments: { ar_change: number; ap_change: number }
  operating_cash: number
  investing_items: { name: string; amount: number }[]
  investing_cash: number
  financing_items: { name: string; amount: number }[]
  financing_cash: number
  net_cash_change: number
  beginning_balance: number
  ending_balance: number
}

function defaultRange() {
  const to = new Date()
  const from = new Date(to.getFullYear(), 0, 1)
  return { start: from.toISOString().split('T')[0], end: to.toISOString().split('T')[0] }
}

function Row({ label, value, indent = false, bold = false }: { label: string; value: number; indent?: boolean; bold?: boolean }) {
  return (
    <div className={`flex justify-between py-2 ${bold ? 'border-t border-[#ede9e2] font-semibold' : ''}`}>
      <span className={indent ? 'ml-6 text-sm text-black/70' : ''}>{label}</span>
      <span className={`font-mono ${bold ? 'text-lg' : 'text-sm'} ${value < 0 ? 'text-red-600' : ''}`}>{fmtPKR(value)}</span>
    </div>
  )
}

export default function CashFlow() {
  const range = defaultRange()
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [data, setData] = useState<CashFlowData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch<CashFlowData>(`/api/reports/cash-flow?start=${start}&end=${end}`)
      .then(setData)
      .catch(err => setError((err as Error).message))
  }, [start, end])

  return (
    <div className="space-y-6 p-8 max-w-4xl">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-medium">Cash Flow Statement</h1>
          <p className="text-sm text-black/75 mt-1">Sources and uses of cash — Indirect Method</p>
        </div>
        <div className="p-3 bg-white border border-[#ede9e2] rounded-xl">
          <DateRangePicker start={start} end={end} onStartChange={setStart} onEndChange={setEnd} label="Period" />
        </div>
      </div>

      {error && <div className="text-red-600 font-semibold">{error}</div>}

      {!data ? (
        <div className="text-center py-12 text-black/40">Loading...</div>
      ) : (
        <div className="bg-white rounded-xl border border-[#ede9e2] p-8 space-y-8">
          <div className="text-center pb-6 border-b border-[#ede9e2]">
            <h2 className="text-xl font-serif font-medium mb-1">Statement of Cash Flows</h2>
            <p className="text-xs text-black/60 mt-1">{data.period.start} — {data.period.end}</p>
          </div>

          {/* Operating */}
          <div>
            <h3 className="text-base font-semibold mb-3 pb-2 border-b border-[#ede9e2]">Operating Activities</h3>
            <Row label="Net Income" value={data.net_income} />
            <Row label="Decrease (Increase) in Accounts Receivable" value={-data.operating_adjustments.ar_change} indent />
            <Row label="Increase (Decrease) in Accounts Payable" value={data.operating_adjustments.ap_change} indent />
            <Row label="Net Cash from Operations" value={data.operating_cash} bold />
          </div>

          {/* Investing */}
          <div>
            <h3 className="text-base font-semibold mb-3 pb-2 border-b border-[#ede9e2]">Investing Activities</h3>
            {data.investing_items.length === 0 ? (
              <p className="text-sm text-black/40 mb-3">No fixed asset movements</p>
            ) : data.investing_items.map((item, i) => (
              <Row key={i} label={item.name} value={item.amount} indent />
            ))}
            <Row label="Net Cash from Investing" value={data.investing_cash} bold />
          </div>

          {/* Financing */}
          <div>
            <h3 className="text-base font-semibold mb-3 pb-2 border-b border-[#ede9e2]">Financing Activities</h3>
            {data.financing_items.length === 0 ? (
              <p className="text-sm text-black/40 mb-3">No financing movements</p>
            ) : data.financing_items.map((item, i) => (
              <Row key={i} label={item.name} value={item.amount} indent />
            ))}
            <Row label="Net Cash from Financing" value={data.financing_cash} bold />
          </div>

          {/* Summary */}
          <div className="bg-[#f6f3ee] p-6 rounded-xl space-y-3">
            <div className="flex justify-between pb-3 border-b border-[#ede9e2]">
              <span className="font-semibold">Net Change in Cash</span>
              <span className={`font-mono font-bold text-lg ${data.net_cash_change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {data.net_cash_change >= 0 ? '+' : ''}{fmtPKR(data.net_cash_change)}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Beginning Cash Balance</span>
              <span className="font-mono">{fmtPKR(data.beginning_balance)}</span>
            </div>
            <div className="flex justify-between text-lg font-bold border-t border-[#ede9e2] pt-3">
              <span>Ending Cash Balance</span>
              <span className="font-mono text-[#b8943f]">{fmtPKR(data.ending_balance)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
