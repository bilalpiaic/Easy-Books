"use client"

import { useEffect, useState } from "react"
import { Plus, Search, Trash2, Printer } from "lucide-react"
import PrintHeader from "@/components/PrintHeader"
import DocLink from "@/components/DocLink"
import { apiFetch } from "@/lib/api"
import { cn, fmtPKR } from "@/lib/utils"
import Pagination from "@/components/Pagination"
import AccountFormModal from "@/components/AccountFormModal"
import SkeletonRow from "@/components/SkeletonRow"
import CsvImportButton from "@/components/CsvImportButton"

interface Account {
  id: number
  code: string
  name: string
  type: string
  tenant_id: number
  parent_id?: number | null
}

interface AccountsResponse {
  total: number
  items: Account[]
}

interface TBItem {
  code: string
  total_debit: number
  total_credit: number
  type: string
}

const PAGE_SIZE = 50

export default function COAPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [balances, setBalances] = useState<Record<string, number>>({})
  const [modalOpen, setModalOpen] = useState(false)
  const [editAccount, setEditAccount] = useState<Account | null>(null)

  useEffect(() => { setPage(1) }, [search])

  const loadAccounts = () => {
    setIsLoading(true)
    const params = new URLSearchParams({ skip: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) })
    if (search) params.set("search", search)
    Promise.all([
      apiFetch<AccountsResponse>(`/api/accounts?${params}`),
      apiFetch<TBItem[]>("/api/reports/trial-balance"),
    ]).then(([accs, tb]) => {
      setAccounts(accs.items)
      setTotal(accs.total)
      const bals: Record<string, number> = {}
      for (const item of tb) {
        const net = item.type === "Asset" || item.type === "Expense"
          ? item.total_debit - item.total_credit
          : item.total_credit - item.total_debit
        bals[item.code] = net
      }
      setBalances(bals)
      setIsLoading(false)
    }).catch(() => setIsLoading(false))
  }

  useEffect(loadAccounts, [page, search])

  const handleDelete = async (acc: Account) => {
    if (!window.confirm(`Delete account "${acc.name}"? This cannot be undone.`)) return
    try {
      await apiFetch(`/api/accounts/${acc.id}`, { method: "DELETE" })
      loadAccounts()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  return (
    <div>
      <PrintHeader title="Chart of Accounts" />
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-3 print:hidden">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">Chart of Accounts</h1>
          <p className="text-[#1a1814]/60">Manage your organisation's ledger accounts</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <CsvImportButton entity="accounts" onSuccess={loadAccounts} />
          <button
            onClick={() => window.print()}
            className="border border-[#ede9e2] px-6 py-3 rounded-xl flex items-center gap-2 hover:bg-[#f6f3ee] transition-colors font-bold text-sm"
            title="Print"
          >
            <Printer className="w-4 h-4" />
            Print
          </button>
          <button
            onClick={() => { setEditAccount(null); setModalOpen(true) }}
            className="bg-[#b8943f] text-black font-bold px-6 py-3 rounded-xl flex items-center gap-2 hover:bg-[#a38338] transition-colors"
          >
            <Plus className="w-5 h-5" />
            Add Account
          </button>
        </div>
      </div>

      <div className="mb-4 relative">
        <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-[#1a1814]/40" />
        <input
          type="text"
          placeholder="Search by name or code..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-white border border-[#1a1814]/10 rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
        />
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full text-left min-w-[560px]">
          <thead>
            <tr className="bg-[#f6f3ee] border-b border-[#1a1814]/5">
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Code</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Account Name</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Type</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Parent</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 text-right">Balance</th>
              <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[#1a1814]/75">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1a1814]/5">
            {isLoading ? (
              <SkeletonRow cols={6} />
            ) : accounts.length === 0 ? (
              <tr><td colSpan={6} className="px-8 py-10 text-center text-[#1a1814]/75">No accounts found.</td></tr>
            ) : (
              accounts.map(acc => {
                const parent = acc.parent_id ? accounts.find(a => a.id === acc.parent_id) : null
                return (
                <tr key={acc.id} className="hover:bg-[#f6f3ee]/50 transition-colors">
                  <td className="px-8 py-5 font-mono text-sm">
                    <DocLink type="account" id={acc.name} label={acc.code} />
                  </td>
                  <td className="px-8 py-5 font-medium">
                    <DocLink type="account" id={acc.name} label={acc.name} className="font-medium" />
                  </td>
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
                  <td className="px-8 py-5 text-sm text-[#1a1814]/60">
                    {parent ? <span className="font-mono">{parent.code} — {parent.name}</span> : <span className="text-[#1a1814]/30">—</span>}
                  </td>
                  <td className="px-8 py-5 text-right font-mono text-sm">
                    {balances[acc.code] !== undefined ? fmtPKR(balances[acc.code]) : "-"}
                  </td>
                  <td className="px-8 py-5 flex items-center gap-3">
                    <button
                      onClick={() => { setEditAccount(acc); setModalOpen(true) }}
                      className="text-[#b8943f] text-sm font-bold hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(acc)}
                      className="text-red-400 hover:text-red-600 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
                )
              })
            )}
          </tbody>
        </table>
        </div>
        <div className="border-t border-[#1a1814]/5 px-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </div>
      </div>

      {modalOpen && (
        <AccountFormModal
          account={editAccount}
          allAccounts={accounts}
          onClose={() => setModalOpen(false)}
          onSaved={() => { setModalOpen(false); loadAccounts() }}
        />
      )}
    </div>
  )
}
