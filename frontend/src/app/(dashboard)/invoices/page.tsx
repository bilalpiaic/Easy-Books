'use client'

import { useEffect, useState } from 'react'
import { Plus, Search, Download, Filter } from 'lucide-react'
import { getAuthHeader } from '@/lib/auth'
import { fmtPKR } from '@/lib/utils'

interface Invoice {
  id: number
  invoice_number: string
  customer_name: string
  amount: number
  tax: number
  total: number
  issue_date: string
  due_date: string
  status: 'draft' | 'sent' | 'paid' | 'overdue'
}

export default function Invoices() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    fetchInvoices()
  }, [])

  const fetchInvoices = async () => {
    try {
      setLoading(true)
      // TODO: Replace with actual API endpoint once backend is ready
      // const res = await fetch('http://localhost:8000/api/invoices', {
      //   headers: getAuthHeader()
      // })
      // if (!res.ok) throw new Error(`HTTP ${res.status}`)
      // const data = await res.json()
      // setInvoices(data)
      setInvoices([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch invoices')
    } finally {
      setLoading(false)
    }
  }

  const filteredInvoices = invoices.filter(inv =>
    inv.invoice_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
    inv.customer_name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const totalAmount = filteredInvoices.reduce((sum, inv) => sum + inv.total, 0)
  const paidAmount = filteredInvoices.filter(inv => inv.status === 'paid').reduce((sum, inv) => sum + inv.total, 0)
  const pendingAmount = totalAmount - paidAmount

  const statusColors = {
    draft: 'bg-gray-100 text-gray-700',
    sent: 'bg-blue-100 text-blue-700',
    paid: 'bg-green-100 text-green-700',
    overdue: 'bg-red-100 text-red-700'
  }

  return (
    <div className="space-y-6 p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-medium">Invoices</h1>
          <p className="text-sm text-black/50 mt-1">Sales invoices to customers • Track payments</p>
        </div>
        <div className="flex gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" />
            New Invoice
          </button>
          <button className="flex items-center gap-2 px-4 py-2 border border-[#1a1814]/20 rounded-lg hover:bg-[#f6f3ee]">
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Outstanding</p>
          <p className="text-2xl font-bold text-[#b8943f] mt-2">{fmtPKR(pendingAmount)}</p>
          <p className="text-xs text-black/40 mt-2">{filteredInvoices.filter(inv => inv.status !== 'paid').length} invoices</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Paid</p>
          <p className="text-2xl font-bold text-green-600 mt-2">{fmtPKR(paidAmount)}</p>
          <p className="text-xs text-black/40 mt-2">{filteredInvoices.filter(inv => inv.status === 'paid').length} invoices</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Value</p>
          <p className="text-2xl font-bold text-[#1a1814] mt-2">{fmtPKR(totalAmount)}</p>
          <p className="text-xs text-black/40 mt-2">{filteredInvoices.length} invoices</p>
        </div>
      </div>

      {/* Search & Filter */}
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 w-4 h-4 text-black/40" />
          <input
            type="text"
            placeholder="Search by invoice # or customer..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f]"
          />
        </div>
        <button className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee]">
          <Filter className="w-4 h-4" />
          Filter
        </button>
      </div>

      {/* Invoices Table */}
      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Invoice #</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Customer</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Issue Date</th>
              <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/40">Due Date</th>
              <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/40">Amount</th>
              <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-black/40">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-black/40">Loading invoices...</td>
              </tr>
            ) : filteredInvoices.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-black/40">No invoices found. Create one to get started.</td>
              </tr>
            ) : (
              filteredInvoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-[#f6f3ee]/50">
                  <td className="px-6 py-4 font-mono font-bold text-[#b8943f]">{inv.invoice_number}</td>
                  <td className="px-6 py-4">{inv.customer_name}</td>
                  <td className="px-6 py-4 text-black/70">{inv.issue_date}</td>
                  <td className="px-6 py-4 text-black/70">{inv.due_date}</td>
                  <td className="px-6 py-4 text-right font-mono">{fmtPKR(inv.total)}</td>
                  <td className="px-6 py-4 text-center">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${statusColors[inv.status]}`}>
                      {inv.status}
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
        <h4 className="font-semibold text-blue-900 mb-2">💡 Invoice Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Issue invoices immediately after delivering goods/services</li>
          <li>✓ Clearly state payment terms (net 30, net 60, etc.)</li>
          <li>✓ Include invoice number, date, and due date</li>
          <li>✓ Itemize products/services with quantities and rates</li>
          <li>✓ Follow up on overdue invoices promptly</li>
          <li>✓ Keep copies for audit trail and tax purposes</li>
        </ul>
      </div>
    </div>
  )
}
