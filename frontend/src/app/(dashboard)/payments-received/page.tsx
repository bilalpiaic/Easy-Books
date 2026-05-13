'use client'

import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { fmtPKR } from '@/lib/utils'

interface PaymentReceived {
  id: number
  reference: string
  customer_name: string
  amount: number
  payment_date: string
  payment_method: 'check' | 'bank_transfer' | 'cash' | 'credit_card'
}

const mockPayments: PaymentReceived[] = []

export default function PaymentsReceived() {
  const [searchTerm, setSearchTerm] = useState('')

  const filtered = mockPayments.filter(p =>
    p.reference.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.customer_name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const totalReceived = filtered.reduce((sum, p) => sum + p.amount, 0)

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-medium">Payments Received</h1>
          <p className="text-sm text-black/50 mt-1">Record customer payments • Track cash receipts</p>
        </div>
        <button className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
          <Plus className="w-4 h-4" />
          Record Payment
        </button>
      </div>

      <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
        <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Received</p>
        <p className="text-3xl font-bold text-green-600 mt-2">{fmtPKR(totalReceived)}</p>
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
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Reference</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Customer</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Payment Date</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Method</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/40">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-black/40">No payments recorded.</td>
              </tr>
            ) : (
              filtered.map((p) => (
                <tr key={p.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="px-6 py-4 font-mono font-bold text-[#b8943f]">{p.reference}</td>
                  <td className="px-6 py-4">{p.customer_name}</td>
                  <td className="px-6 py-4">{p.payment_date}</td>
                  <td className="px-6 py-4 capitalize">{p.payment_method.replace('_', ' ')}</td>
                  <td className="px-6 py-4 text-right font-mono">{fmtPKR(p.amount)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 Payment Recording Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Record payments when received (cash basis)</li>
          <li>✓ Match payments to specific invoices</li>
          <li>✓ Document payment method and reference number</li>
          <li>✓ Reconcile with bank deposits weekly</li>
          <li>✓ Maintain copies of payment documentation</li>
        </ul>
      </div>
    </div>
  )
}
