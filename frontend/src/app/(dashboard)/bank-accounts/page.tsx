'use client'

import { Plus, Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'
import { fmtPKR } from '@/lib/utils'

interface BankAccount {
  id: number
  account_name: string
  account_number: string
  bank_name: string
  balance: number
  status: 'active' | 'inactive'
  last_reconciled: string
}

const mockAccounts: BankAccount[] = []

export default function BankAccounts() {
  const [hideBalance, setHideBalance] = useState(false)

  const totalBalance = mockAccounts.reduce((sum, acc) => sum + acc.balance, 0)

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-medium">Bank Accounts</h1>
          <p className="text-sm text-black/50 mt-1">Monitor bank balances • Track cash positions</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setHideBalance(!hideBalance)}
            className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg hover:bg-[#f6f3ee]"
          >
            {hideBalance ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            {hideBalance ? 'Show' : 'Hide'} Balance
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
            <Plus className="w-4 h-4" />
            Add Account
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
        <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Total Cash Position</p>
        <p className={`text-3xl font-bold mt-2 ${totalBalance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {hideBalance ? '••••••' : fmtPKR(totalBalance)}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {mockAccounts.length === 0 ? (
          <div className="text-center py-12 text-black/40">No bank accounts configured. Add one to track balances.</div>
        ) : (
          mockAccounts.map((acc) => (
            <div key={acc.id} className="bg-white rounded-lg border border-[#ede9e2] p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold">{acc.account_name}</h3>
                  <p className="text-xs text-black/50 mt-1">{acc.bank_name} • {acc.account_number}</p>
                </div>
                <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${
                  acc.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                }`}>
                  {acc.status}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Current Balance</p>
                  <p className="text-2xl font-bold text-[#b8943f] mt-2">
                    {hideBalance ? '••••••' : fmtPKR(acc.balance)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Last Reconciled</p>
                  <p className="text-sm font-medium mt-2">{acc.last_reconciled}</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 Bank Account Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Maintain separate bank accounts for business and personal use</li>
          <li>✓ Monitor bank statements weekly for errors or fraud</li>
          <li>✓ Reconcile accounts monthly with bank statements</li>
          <li>✓ Investigate discrepancies immediately</li>
          <li>✓ Maintain sufficient cash reserves for operations</li>
        </ul>
      </div>
    </div>
  )
}
