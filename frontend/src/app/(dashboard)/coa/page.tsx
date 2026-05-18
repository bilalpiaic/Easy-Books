"use client"

import { useEffect, useState } from "react"
import { Plus, Search } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { cn } from "@/lib/utils"
import Pagination from "@/components/Pagination"

interface Account {
  id: number
  code: string
  name: string
  type: string
  tenant_id: number
}

interface AccountsResponse {
  total: number
  items: Account[]
}

const PAGE_SIZE = 50

export default function COAPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => { setPage(1) }, [search])

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (search) params.set("search", search)
    apiFetch<AccountsResponse>(`/api/accounts?${params}`)
      .then(data => { setAccounts(data.items); setTotal(data.total); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [page, search])

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Chart of Accounts</h1>
          <p className="text-[#1a1814]/60">Manage your organisation's ledger accounts</p>
        </div>
        <button className="bg-[#b8943f] text-black font-bold px-6 py-3 rounded-xl flex items-center gap-2 hover:bg-[#a38338] transition-colors">
          <Plus className="w-5 h-5" />
          Add Account
        </button>
      </div>

      <div className="mb-4 relative">
        <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-[#1a1814]/40" />
        <input
          type="text"
          placeholder="Search by name or code..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-white border border-[#1a1814]/10 rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] focus:border-transparent"
        />
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Code</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Account Name</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Type</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1a1814]/5">
            {isLoading ? (
              <tr><td colSpan={4} className="px-8 py-10 text-center text-[#1a1814]/75">Loading accounts...</td></tr>
            ) : accounts.length === 0 ? (
              <tr><td colSpan={4} className="px-8 py-10 text-center text-[#1a1814]/75">No accounts found.</td></tr>
            ) : (
              accounts.map(acc => (
                <tr key={acc.id} className="hover:bg-[#f6f3ee]/50 transition-colors">
                  <td className="px-8 py-5 font-mono text-sm">{acc.code}</td>
                  <td className="px-8 py-5 font-medium">{acc.name}</td>
                  <td className="px-8 py-5">
                    <span className={cn(
                      "px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest",
                      acc.type === "Asset" && "bg-blue-100 text-blue-700",
                      acc.type === "Liability" && "bg-red-100 text-red-700",
                      acc.type === "Equity" && "bg-purple-100 text-purple-700",
                      acc.type === "Revenue" && "bg-green-100 text-green-700",
                      acc.type === "Expense" && "bg-orange-100 text-orange-700",
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
        <div className="border-t border-[#1a1814]/5 px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>
    </div>
  )
}
