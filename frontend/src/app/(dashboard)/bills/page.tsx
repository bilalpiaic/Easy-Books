'use client'

import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { fmtPKR } from '@/lib/utils'

interface Bill {
  id: number
  bill_number: string
  vendor_name: string
  amount: number
  tax: number
  total: number
  bill_date: string
  due_date: string
  status: 'draft' | 'received' | 'paid' | 'overdue'
}

const mockBills: Bill[] = []

export default function Bills() {
  const [searchTerm, setSearchTerm] = useState('')

  const filtered = mockBills.filter(b =>
    b.bill_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
    b.vendor_name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const totalAmount = filtered.reduce((sum, b) => sum + b.total, 0)
  const paidAmount = filtered.filter(b => b.status === 'paid').reduce((sum, b) => sum + b.total, 0)
  const pending = totalAmount - paidAmount

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-medium">Bills</h1>
          <p className="text-sm text-black/50 mt-1">Vendor bills • Purchase liabilities</p>
        </div>
        <button className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
          <Plus className="w-4 h-4" />
          New Bill
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Payable</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-2">{fmtPKR(pending)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Paid</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmtPKR(paidAmount)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Value</p>
          <p className="text-2xl font-bold text-[#1a1814] mt-2">{fmtPKR(totalAmount)}</p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input
          type="text"
          placeholder="Search bills..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
        />
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Bill #</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Vendor</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Bill Date</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Due Date</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/40">Amount</th>
              <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-black/40">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-black/40">No bills found.</td>
              </tr>
            ) : (
              filtered.map((b) => (
                <tr key={b.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="px-6 py-4 font-mono font-bold text-[#b8943f]">{b.bill_number}</td>
                  <td className="px-6 py-4">{b.vendor_name}</td>
                  <td className="px-6 py-4">{b.bill_date}</td>
                  <td className="px-6 py-4">{b.due_date}</td>
                  <td className="px-6 py-4 text-right font-mono">{fmtPKR(b.total)}</td>
                  <td className="px-6 py-4 text-center">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${
                      b.status === 'paid' ? 'bg-green-100 text-green-700' :
                      b.status === 'overdue' ? 'bg-red-100 text-red-700' :
                      'bg-blue-100 text-blue-700'
                    }`}>
                      {b.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 Bill Management Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Record bills when received (accrual basis)</li>
          <li>✓ Verify bill details against purchase orders</li>
          <li>✓ Process payments by due date to maintain vendor relationships</li>
          <li>✓ Take advantage of early payment discounts when beneficial</li>
          <li>✓ Maintain organized bill filing for audit purposes</li>
        </ul>
      </div>
    </div>
  )
}
