'use client'

import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { fmtPKR } from '@/lib/utils'

interface Customer {
  id: number
  name: string
  email: string
  phone: string
  total_sales: number
  outstanding_balance: number
  status: 'active' | 'inactive'
}

const mockCustomers: Customer[] = []

export default function Customers() {
  const [searchTerm, setSearchTerm] = useState('')

  const filteredCustomers = mockCustomers.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.email.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const totalSales = filteredCustomers.reduce((sum, c) => sum + c.total_sales, 0)
  const totalOutstanding = filteredCustomers.reduce((sum, c) => sum + c.outstanding_balance, 0)

  return (
    <div className="space-y-6 p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-medium">Customers</h1>
          <p className="text-sm text-black/50 mt-1">Manage customers • Track credit accounts</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
          <Plus className="w-4 h-4" />
          Add Customer
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Sales</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-2">{fmtPKR(totalSales)}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Outstanding Balance</p>
          <p className="text-2xl font-bold text-red-600 mt-2">{fmtPKR(totalOutstanding)}</p>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
        <input
          type="text"
          placeholder="Search customers..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Name</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Email</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Phone</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/40">Total Sales</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/40">Outstanding</th>
              <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-black/40">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {filteredCustomers.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-black/40">No customers found.</td>
              </tr>
            ) : (
              filteredCustomers.map((c) => (
                <tr key={c.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="px-6 py-4 font-medium">{c.name}</td>
                  <td className="px-6 py-4 text-black/70">{c.email}</td>
                  <td className="px-6 py-4 text-black/70">{c.phone}</td>
                  <td className="px-6 py-4 text-right font-mono">{fmtPKR(c.total_sales)}</td>
                  <td className="px-6 py-4 text-right font-mono">{fmtPKR(c.outstanding_balance)}</td>
                  <td className="px-6 py-4 text-center">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${
                      c.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                    }`}>
                      {c.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Best Practices */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 Customer Management Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Maintain accurate customer contact and credit information</li>
          <li>✓ Set credit limits based on payment history</li>
          <li>✓ Regularly review aging of receivables</li>
          <li>✓ Follow up on overdue accounts promptly</li>
          <li>✓ Document all communication and agreements</li>
        </ul>
      </div>
    </div>
  )
}
