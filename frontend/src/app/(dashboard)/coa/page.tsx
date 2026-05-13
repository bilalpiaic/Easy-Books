"use client"

import { useEffect, useState } from "react"
import { TableProperties, Plus } from "lucide-react"
import { getAuthHeader } from "@/lib/auth"

interface Account {
  id: number
  code: string
  name: string
  type: string
  tenant_id: number
}

export default function COAPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetch("http://localhost:8000/api/accounts", {
      headers: getAuthHeader()
    })
      .then(res => res.json())
      .then(data => {
        setAccounts(data)
        setIsLoading(false)
      })
      .catch(err => {
        console.error(err)
        setIsLoading(false)
      })
  }, [])

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Chart of Accounts</h1>
          <p className="text-[#1a1814]/60">Manage your organization's ledger accounts</p>
        </div>
        <button className="bg-[#b8943f] text-black font-bold px-6 py-3 rounded-xl flex items-center gap-2 hover:bg-[#a38338] transition-colors">
          <Plus className="w-5 h-5" />
          Add Account
        </button>
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/40">Code</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/40">Account Name</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/40">Type</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/40">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1a1814]/5">
            {isLoading ? (
              <tr>
                <td colSpan={4} className="px-8 py-10 text-center text-[#1a1814]/40">Loading accounts...</td>
              </tr>
            ) : accounts.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-8 py-10 text-center text-[#1a1814]/40">No accounts found.</td>
              </tr>
            ) : (
              accounts.map((acc) => (
                <tr key={acc.id} className="hover:bg-[#f6f3ee]/50 transition-colors">
                  <td className="px-8 py-5 font-mono text-sm">{acc.code}</td>
                  <td className="px-8 py-5 font-medium">{acc.name}</td>
                  <td className="px-8 py-5">
                    <span className={cn(
                      "px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest",
                      acc.type === 'Asset' && "bg-blue-100 text-blue-700",
                      acc.type === 'Liability' && "bg-red-100 text-red-700",
                      acc.type === 'Equity' && "bg-purple-100 text-purple-700",
                      acc.type === 'Revenue' && "bg-green-100 text-green-700",
                      acc.type === 'Expense' && "bg-orange-100 text-orange-700",
                    )}>
                      {acc.type}
                    </span>
                  </td>
                  <td className="px-8 py-5">
                    <button className="text-[#b8943f] text-sm font-bold hover:underline">Edit</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function cn(...classes: any[]) {
  return classes.filter(Boolean).join(" ")
}
