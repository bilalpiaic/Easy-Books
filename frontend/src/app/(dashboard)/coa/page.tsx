"use client"

import { useEffect, useState, useCallback } from "react"
import { Plus, Search, Trash2, Printer, ChevronRight, ChevronDown, Download } from "lucide-react"
import PrintHeader from "@/components/PrintHeader"
import DocLink from "@/components/DocLink"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { downloadCSV } from "@/lib/utils"
import { cn } from "@/lib/utils"
import AccountFormModal from "@/components/AccountFormModal"
import SkeletonRow from "@/components/SkeletonRow"
import CsvImportButton from "@/components/CsvImportButton"
import { useTranslation } from "react-i18next"
import { useMessages } from "@/context/MessageContext"

interface Account {
  id: number
  code: string
  name: string
  type: string
  tenant_id: number
  parent_id?: number | null
  is_group?: boolean
  is_active?: boolean
  has_children?: boolean
  postable?: boolean
  depth?: number
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

/** Build a tree structure from the flat list for rendering. */
function buildTree(accounts: Account[]): Account[] {
  // Sort by code first
  const sorted = [...accounts].sort((a, b) => a.code.localeCompare(b.code))
  // Collect top-level accounts in code order
  const roots = sorted.filter(a => !a.parent_id)
  // Recursively interleave children after their parent
  function flatten(nodes: Account[]): Account[] {
    const out: Account[] = []
    for (const node of nodes) {
      out.push(node)
      const children = sorted.filter(a => a.parent_id === node.id)
      out.push(...flatten(children))
    }
    return out
  }
  return flatten(roots)
}

export default function COAPage() {
  const { confirm, toast } = useMessages()
  const { t } = useTranslation()

  const fmt = useFmt()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [search, setSearch] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [balances, setBalances] = useState<Record<string, number>>({})
  const [modalOpen, setModalOpen] = useState(false)
  const [editAccount, setEditAccount] = useState<Account | null>(null)
  // Set of collapsed parent IDs
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())

  const loadAccounts = useCallback(() => {
    setIsLoading(true)
    const params = new URLSearchParams({ skip: "0", limit: "500" })
    if (search) params.set("search", search)
    Promise.all([
      apiFetch<AccountsResponse>(`/api/accounts?${params}`),
      apiFetch<TBItem[]>("/api/reports/trial-balance"),
    ]).then(([accs, tb]) => {
      setAccounts(accs.items)
      const bals: Record<string, number> = {}
      for (const item of tb) {
        const net =
          item.type === "Asset" || item.type === "Expense"
            ? item.total_debit - item.total_credit
            : item.total_credit - item.total_debit
        bals[item.code] = net
      }
      setBalances(bals)
      setIsLoading(false)
    }).catch(() => setIsLoading(false))
  }, [search])

  useEffect(loadAccounts, [loadAccounts])

  const handleDelete = async (acc: Account) => {
    const ok = await confirm({
      title: `Delete account "${acc.name}"?`,
      message: "This cannot be undone.",
      confirmLabel: "Delete",
      danger: true,
    })
    if (!ok) return
    try {
      await apiFetch(`/api/accounts/${acc.id}`, { method: "DELETE" })
      loadAccounts()
    } catch (err) {
      toast((err as Error).message, "error")
    }
  }

  const handleToggleActive = async (acc: Account) => {
    const newActive = !(acc.is_active ?? true)
    try {
      await apiFetch(`/api/accounts/${acc.id}/active?is_active=${newActive}`, {
        method: "PATCH",
      })
      loadAccounts()
    } catch (err) {
      toast((err as Error).message, "error")
    }
  }

  const toggleCollapse = (id: number) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // When searching, show flat list; otherwise show tree
  const displayAccounts = search
    ? [...accounts].sort((a, b) => a.code.localeCompare(b.code))
    : buildTree(accounts)

  // Determine which accounts are hidden because a collapsed ancestor hides them
  function isVisible(acc: Account): boolean {
    if (search) return true
    let parentId = acc.parent_id
    while (parentId != null) {
      if (collapsed.has(parentId)) return false
      const parent = accounts.find(a => a.id === parentId)
      parentId = parent?.parent_id ?? null
    }
    return true
  }

  return (
    <div>
      <PrintHeader title="Chart of Accounts" />
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-3 print:hidden">
        <div>
          <h1 className="text-xl sm:text-3xl font-bold text-[var(--text-primary)]">Chart of Accounts</h1>
          <p className="text-[var(--text-primary)]/60">Manage your organisation&apos;s ledger accounts</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <CsvImportButton entity="accounts" onSuccess={loadAccounts} />
          <button
            onClick={() => downloadCSV('chart-of-accounts.csv', accounts.map(a => ({ Code: a.code, Name: a.name, Type: a.type, Group: a.is_group ? 'Yes' : 'No', Active: a.is_active !== false ? 'Yes' : 'No', Balance: balances[a.code] ?? 0 })))}
            disabled={accounts.length === 0}
            className="border border-[var(--border)] px-6 py-3 rounded-xl flex items-center gap-2 hover:bg-[var(--bg-page)] transition-colors font-bold text-sm disabled:opacity-40"
            title="Export CSV"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={() => window.print()}
            className="border border-[var(--border)] px-6 py-3 rounded-xl flex items-center gap-2 hover:bg-[var(--bg-page)] transition-colors font-bold text-sm"
            title="Print"
          >
            <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
          <button
            onClick={() => { setEditAccount(null); setModalOpen(true) }}
            className="bg-[var(--primary)] text-black font-bold px-6 py-3 rounded-xl flex items-center gap-2 hover:bg-[#a38338] transition-colors"
          >
            <Plus className="w-5 h-5" />
            Add Account
          </button>
        </div>
      </div>

      <div className="mb-4 relative">
        <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-primary)]/40" />
        <input
          type="text"
          placeholder="Search by name or code…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-white border border-[var(--text-primary)]/10 rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)]"
        />
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-black/5 border border-[var(--text-primary)]/5 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[640px]">
            <thead>
              <tr className="bg-[var(--bg-page)] border-b border-[var(--text-primary)]/5">
                <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Code</th>
                <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Account Name</th>
                <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">Type</th>
                <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75">{t('col.status', 'Status')}</th>
                <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 text-right">{t('col.balance', 'Balance')}</th>
                <th className="px-8 py-5 text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 print:hidden">{t('col.actions', 'Actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {isLoading ? (
                <SkeletonRow cols={6} />
              ) : displayAccounts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-8 py-10 text-center text-[var(--text-primary)]/75">
                    No accounts found.
                  </td>
                </tr>
              ) : (
                displayAccounts.filter(acc => isVisible(acc)).map(acc => {
                  const depth = acc.depth ?? 0
                  const isGroupAccount = acc.is_group || acc.has_children
                  const isCollapsed = collapsed.has(acc.id)
                  const isInactive = !(acc.is_active ?? true)

                  return (
                    <tr
                      key={acc.id}
                      className={cn(
                        "hover:bg-[var(--bg-page)]/50 transition-colors",
                        isInactive && "opacity-50"
                      )}
                    >
                      {/* Code with indentation */}
                      <td className="px-8 py-4 font-mono text-sm">
                        <div className="flex items-center gap-1" style={{ paddingLeft: `${depth * 16}px` }}>
                          {acc.has_children ? (
                            <button
                              type="button"
                              onClick={() => toggleCollapse(acc.id)}
                              className="text-[var(--text-primary)]/40 hover:text-[var(--primary)] transition-colors shrink-0"
                              aria-label={isCollapsed ? "Expand" : "Collapse"}
                            >
                              {isCollapsed
                                ? <ChevronRight className="w-3.5 h-3.5" />
                                : <ChevronDown className="w-3.5 h-3.5" />}
                            </button>
                          ) : (
                            <span className="w-3.5 shrink-0" />
                          )}
                          <DocLink type="account" id={acc.name} label={acc.code} />
                        </div>
                      </td>

                      {/* Name */}
                      <td className="px-8 py-4 font-medium">
                        <div style={{ paddingLeft: `${depth * 16}px` }}>
                          <DocLink type="account" id={acc.name} label={acc.name} className="font-medium" />
                        </div>
                      </td>

                      {/* Type badge */}
                      <td className="px-8 py-4">
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

                      {/* Status badges */}
                      <td className="px-8 py-4">
                        <div className="flex flex-wrap gap-1">
                          {isGroupAccount && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest bg-amber-100 text-amber-700">
                              Header
                            </span>
                          )}
                          {acc.postable && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest bg-emerald-100 text-emerald-700">
                              Posting
                            </span>
                          )}
                          {isInactive && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest bg-gray-100 text-gray-500">{t('status.inactive', 'Inactive')}</span>
                          )}
                        </div>
                      </td>

                      {/* Balance */}
                      <td className="px-8 py-4 text-right font-mono text-sm">
                        {balances[acc.code] !== undefined ? fmt(balances[acc.code]) : "—"}
                      </td>

                      {/* Actions */}
                      <td className="px-8 py-4 print:hidden">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => { setEditAccount(acc); setModalOpen(true) }}
                            className="text-[var(--primary)] text-sm font-bold hover:underline"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleToggleActive(acc)}
                            className={cn(
                              "text-xs font-semibold hover:underline",
                              isInactive ? "text-emerald-600" : "text-[var(--text-primary)]/40 hover:text-[var(--text-primary)]/70"
                            )}
                            title={isInactive ? "Activate account" : "Deactivate account"}
                          >
                            {isInactive ? "Activate" : "Deactivate"}
                          </button>
                          <button
                            onClick={() => handleDelete(acc)}
                            className="text-red-400 hover:text-red-600 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
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
