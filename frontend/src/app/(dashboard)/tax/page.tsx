'use client'

import { Download, FileText } from 'lucide-react'
import { fmtPKR } from '@/lib/utils'

interface TaxData {
  total_revenue: number
  business_expenses: number
  taxable_income: number
  tax_rate: number
  estimated_tax: number
  quarters: { q: number; estimated: number; paid: number }[]
}

const mockData: TaxData = {
  total_revenue: 1000000,
  business_expenses: 600000,
  taxable_income: 400000,
  tax_rate: 25,
  estimated_tax: 100000,
  quarters: [
    { q: 1, estimated: 25000, paid: 25000 },
    { q: 2, estimated: 25000, paid: 0 },
    { q: 3, estimated: 25000, paid: 0 },
    { q: 4, estimated: 25000, paid: 0 }
  ]
}

export default function TaxReports() {
  const { total_revenue, business_expenses, taxable_income, tax_rate, estimated_tax, quarters } = mockData

  return (
    <div className="space-y-6 p-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-medium">Tax Reports</h1>
          <p className="text-sm text-black/50 mt-1">Tax planning & estimated tax calculations</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
          <Download className="w-4 h-4" />
          Export PDF
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Revenue</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmtPKR(total_revenue)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Business Expenses</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-2">{fmtPKR(business_expenses)}</p>
        </div>
      </div>

      {/* Tax Calculation */}
      <div className="bg-white rounded-xl border border-[#ede9e2] p-8">
        <h3 className="text-lg font-semibold mb-6">Tax Calculation</h3>
        
        <div className="space-y-3 mb-6">
          <div className="flex justify-between py-2 border-b border-[#ede9e2]">
            <span>Total Revenue</span>
            <span className="font-mono font-bold">{fmtPKR(total_revenue)}</span>
          </div>
          <div className="flex justify-between py-2 border-b border-[#ede9e2]">
            <span>Less: Business Expenses</span>
            <span className="font-mono font-bold">({fmtPKR(business_expenses)})</span>
          </div>
          <div className="flex justify-between py-3 border-t-2 border-[#1a1814] font-semibold text-lg">
            <span>Taxable Income</span>
            <span className="font-mono text-[#b8943f]">{fmtPKR(taxable_income)}</span>
          </div>
        </div>

        <div className="space-y-3 bg-[#f6f3ee] p-6 rounded">
          <div className="flex justify-between">
            <span>Tax Rate</span>
            <span className="font-mono font-bold">{tax_rate}%</span>
          </div>
          <div className="flex justify-between pt-3 border-t border-[#ede9e2] font-semibold text-lg">
            <span>Estimated Tax Liability</span>
            <span className="font-mono text-red-600">{fmtPKR(estimated_tax)}</span>
          </div>
        </div>
      </div>

      {/* Quarterly Estimates */}
      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Quarter</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/40">Estimated Payment</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/40">Paid</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/40">Outstanding</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {quarters.map((q) => (
              <tr key={q.q} className="hover:bg-[#f6f3ee]/50">
                <td className="px-6 py-4 font-medium">Q{q.q} {new Date().getFullYear()}</td>
                <td className="px-6 py-4 text-right font-mono">{fmtPKR(q.estimated)}</td>
                <td className="px-6 py-4 text-right font-mono text-green-600">{fmtPKR(q.paid)}</td>
                <td className="px-6 py-4 text-right font-mono text-red-600">{fmtPKR(q.estimated - q.paid)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-[#1a1814] text-white font-bold">
            <tr>
              <td className="px-6 py-4">TOTALS</td>
              <td className="px-6 py-4 text-right font-mono">{fmtPKR(quarters.reduce((s, q) => s + q.estimated, 0))}</td>
              <td className="px-6 py-4 text-right font-mono">{fmtPKR(quarters.reduce((s, q) => s + q.paid, 0))}</td>
              <td className="px-6 py-4 text-right font-mono">{fmtPKR(quarters.reduce((s, q) => s + (q.estimated - q.paid), 0))}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Best Practices */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 Tax Planning Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Calculate and pay estimated taxes quarterly to avoid penalties</li>
          <li>✓ Keep detailed records of all deductible business expenses</li>
          <li>✓ Consult with a tax professional for tax planning strategies</li>
          <li>✓ Track mileage, meals, and other easy-to-miss deductions</li>
          <li>✓ Plan for tax liability throughout the year</li>
          <li>✓ Maintain organized records for tax audit purposes</li>
        </ul>
      </div>
    </div>
  )
}
