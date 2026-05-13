'use client'

import { Download, TrendingUp, TrendingDown } from 'lucide-react'
import { fmtPKR } from '@/lib/utils'

interface CashFlowData {
  operating_cash: number
  investing_cash: number
  financing_cash: number
  net_cash_change: number
  beginning_balance: number
  ending_balance: number
}

const mockData: CashFlowData = {
  operating_cash: 150000,
  investing_cash: -75000,
  financing_cash: 25000,
  net_cash_change: 100000,
  beginning_balance: 500000,
  ending_balance: 600000
}

export default function CashFlow() {
  const { operating_cash, investing_cash, financing_cash, net_cash_change, beginning_balance, ending_balance } = mockData

  return (
    <div className="space-y-6 p-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-medium">Cash Flow Statement</h1>
          <p className="text-sm text-black/50 mt-1">Sources and uses of cash • Liquidity analysis</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
          <Download className="w-4 h-4" />
          Export PDF
        </button>
      </div>

      {/* Main Report */}
      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="p-8 space-y-8">
          {/* Title */}
          <div className="text-center pb-6 border-b border-[#ede9e2]">
            <h2 className="text-2xl font-serif font-medium mb-1">Malik Enterprises</h2>
            <p className="text-sm text-black/50">Statement of Cash Flows</p>
            <p className="text-xs text-black/40 mt-3">For the Period</p>
          </div>

          {/* Operating Activities */}
          <div>
            <h3 className="text-lg font-semibold mb-4 pb-3 border-b border-[#ede9e2]">Operating Activities</h3>
            <div className="flex justify-between items-center mb-3">
              <span>Net Income</span>
              <span className="font-mono font-bold">{fmtPKR(0)}</span>
            </div>
            <div className="flex justify-between items-center mb-3 text-sm text-black/70">
              <span className="ml-6">+ Depreciation</span>
              <span className="font-mono">{fmtPKR(0)}</span>
            </div>
            <div className="flex justify-between items-center mb-4 text-sm text-black/70">
              <span className="ml-6">Changes in Working Capital</span>
              <span className="font-mono">{fmtPKR(0)}</span>
            </div>
            <div className="flex justify-between border-t border-[#ede9e2] pt-4 font-semibold">
              <span>Net Cash from Operations</span>
              <span className={`font-mono text-lg ${operating_cash >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {fmtPKR(operating_cash)}
              </span>
            </div>
          </div>

          {/* Investing Activities */}
          <div>
            <h3 className="text-lg font-semibold mb-4 pb-3 border-b border-[#ede9e2]">Investing Activities</h3>
            <div className="flex justify-between items-center mb-3 text-sm text-black/70">
              <span>Capital Expenditures</span>
              <span className="font-mono">{fmtPKR(0)}</span>
            </div>
            <div className="flex justify-between items-center mb-4 text-sm text-black/70">
              <span>Asset Sales</span>
              <span className="font-mono">{fmtPKR(0)}</span>
            </div>
            <div className="flex justify-between border-t border-[#ede9e2] pt-4 font-semibold">
              <span>Net Cash from Investing</span>
              <span className={`font-mono text-lg ${investing_cash >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {fmtPKR(investing_cash)}
              </span>
            </div>
          </div>

          {/* Financing Activities */}
          <div>
            <h3 className="text-lg font-semibold mb-4 pb-3 border-b border-[#ede9e2]">Financing Activities</h3>
            <div className="flex justify-between items-center mb-3 text-sm text-black/70">
              <span>Loan Proceeds</span>
              <span className="font-mono">{fmtPKR(0)}</span>
            </div>
            <div className="flex justify-between items-center mb-4 text-sm text-black/70">
              <span>Debt Repayment</span>
              <span className="font-mono">{fmtPKR(0)}</span>
            </div>
            <div className="flex justify-between border-t border-[#ede9e2] pt-4 font-semibold">
              <span>Net Cash from Financing</span>
              <span className={`font-mono text-lg ${financing_cash >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {fmtPKR(financing_cash)}
              </span>
            </div>
          </div>

          {/* Net Change in Cash */}
          <div className="bg-[#f6f3ee] p-6 rounded space-y-3">
            <div className="flex justify-between items-center pb-3 border-b border-[#ede9e2]">
              <span className="font-semibold">Net Change in Cash</span>
              <span className={`font-mono font-bold text-lg ${net_cash_change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {net_cash_change >= 0 ? '+' : ''}{fmtPKR(net_cash_change)}
              </span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span>Beginning Cash Balance</span>
              <span className="font-mono">{fmtPKR(beginning_balance)}</span>
            </div>
            <div className="flex justify-between items-center text-lg font-bold border-t border-[#ede9e2] pt-3">
              <span>Ending Cash Balance</span>
              <span className="font-mono text-[#b8943f]">{fmtPKR(ending_balance)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Best Practices */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 Cash Flow Analysis Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Prepare cash flow statements monthly to monitor liquidity</li>
          <li>✓ Analyze differences between profit and cash flow</li>
          <li>✓ Monitor operating cash flow as primary liquidity measure</li>
          <li>✓ Plan for seasonal cash flow variations</li>
          <li>✓ Ensure adequate working capital for operations</li>
        </ul>
      </div>
    </div>
  )
}
