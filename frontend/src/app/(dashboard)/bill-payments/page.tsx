'use client'

import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { fmtPKR } from '@/lib/utils'

interface BillPayment {
  id: number
  check_number: string
  vendor_name: string
  bill_number: string
  amount: number
  payment_date: string
  status: 'draft' | 'submitted' | 'cleared'
}

const mockPayments: BillPayment[] = []

export default function BillPayments() {
  const [searchTerm, setSearchTerm] = useState('')

  const filtered = mockPayments.filter(p =>
    p.check_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.vendor_name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const totalPaid = filtered.reduce((sum, p) => sum + p.amount, 0)

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-medium">Bill Payments</h1>
          <p className="text-sm text-black/50 mt-1">Record vendor payments • Track cash outflows</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
          <Plus className="w-4 h-4" />
          Pay Bill
        </button>
      </div>

      <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
        <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Paid</p>
        <p className="text-3xl font-bold text-red-600 mt-2">{fmtPKR(totalPaid)}</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input
          type="text"
          placeholder="Search payments..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
        />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Check #</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Vendor</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Bill #</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Payment Date</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/40">Amount</th>
              <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-black/40">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-black/40">No payments recorded.</td>
              </tr>
            ) : (
              filtered.map((p) => (
                <tr key={p.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="px-6 py-4 font-mono font-bold text-[#b8943f]">{p.check_number}</td>
                  <td className="px-6 py-4">{p.vendor_name}</td>
                  <td className="px-6 py-4 font-mono">{p.bill_number}</td>
                  <td className="px-6 py-4">{p.payment_date}</td>
                  <td className="px-6 py-4 text-right font-mono">{fmtPKR(p.amount)}</td>
                  <td className="px-6 py-4 text-center">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${
                      p.status === 'cleared' ? 'bg-green-100 text-green-700' :
                      p.status === 'submitted' ? 'bg-blue-100 text-blue-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {p.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 Bill Payment Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Pay by due date to maintain vendor relationships</li>
          <li>✓ Use appropriate payment methods for each vendor</li>
          <li>✓ Verify invoice details before processing payment</li>
          <li>✓ Record payment method and check/reference numbers</li>
          <li>✓ Reconcile payments with bank statements</li>
        </ul>
      </div>
    </div>
  )
}
