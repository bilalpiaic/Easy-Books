'use client'

import { Plus, CheckCircle } from 'lucide-react'
import { useState } from 'react'
import { fmtPKR } from '@/lib/utils'

interface Reconciliation {
  id: number
  account_name: string
  reconciliation_date: string
  bank_balance: number
  book_balance: number
  difference: number
  status: 'complete' | 'in_progress'
}

const mockReconciliations: Reconciliation[] = []

export default function Reconciliations() {
  const completeCount = mockReconciliations.filter(r => r.status === 'complete').length
  const inProgressCount = mockReconciliations.filter(r => r.status === 'in_progress').length

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-medium">Reconciliations</h1>
          <p className="text-sm text-black/50 mt-1">Bank reconciliation • Verify cash balance</p>
        </div>
        <button className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 bg-[#b8943f] text-white rounded-lg hover:bg-[#a07c35]">
          <Plus className="w-4 h-4" />
          New Reconciliation
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">Completed</p>
          <p className="text-3xl font-bold text-green-600 mt-2">{completeCount}</p>
        </div>
        <div className="bg-white rounded-lg border border-[#ede9e2] p-6">
          <p className="text-xs text-black/50 uppercase tracking-widest font-bold">In Progress</p>
          <p className="text-3xl font-bold text-blue-600 mt-2">{inProgressCount}</p>
        </div>
      </div>

      <div className="space-y-4">
        {mockReconciliations.length === 0 ? (
          <div className="text-center py-12 text-black/40">No reconciliations recorded. Start one to ensure accuracy.</div>
        ) : (
          mockReconciliations.map((rec) => (
            <div key={rec.id} className="bg-white rounded-lg border border-[#ede9e2] p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold">{rec.account_name}</h3>
                  <p className="text-xs text-black/50 mt-1">{rec.reconciliation_date}</p>
                </div>
                {rec.status === 'complete' && (
                  <CheckCircle className="w-5 h-5 text-green-600" />
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
                <div>
                  <p className="text-black/50 uppercase tracking-widest text-[10px] font-bold">Bank Balance</p>
                  <p className="font-mono font-bold mt-2">{fmtPKR(rec.bank_balance)}</p>
                </div>
                <div>
                  <p className="text-black/50 uppercase tracking-widest text-[10px] font-bold">Book Balance</p>
                  <p className="font-mono font-bold mt-2">{fmtPKR(rec.book_balance)}</p>
                </div>
                <div>
                  <p className="text-black/50 uppercase tracking-widest text-[10px] font-bold">Difference</p>
                  <p className={`font-mono font-bold mt-2 ${Math.abs(rec.difference) < 0.01 ? 'text-green-600' : 'text-red-600'}`}>
                    {fmtPKR(rec.difference)}
                  </p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">💡 Reconciliation Best Practices</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Reconcile bank accounts monthly as statements arrive</li>
          <li>✓ Match deposits and withdrawals to accounting records</li>
          <li>✓ Identify and investigate differences immediately</li>
          <li>✓ Record reconciling items (NSF checks, bank charges, etc.)</li>
          <li>✓ Document and approve all reconciliations</li>
        </ul>
      </div>
    </div>
  )
}
