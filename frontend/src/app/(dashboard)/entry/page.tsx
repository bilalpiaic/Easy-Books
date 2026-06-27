"use client"

import { useEffect, useMemo, useState } from "react"
import { Plus, Trash2, Save, AlertCircle, ScrollText, ArrowUpFromLine, ArrowDownToLine, BookOpen, Info } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { filterAccountsForSide, VOUCHER_SIDE_FILTERS } from "@/lib/voucherTypes"
import { useDp } from "@/context/SettingsContext"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import { useTranslation } from "react-i18next"

// ── Types ────────────────────────────────────────────────────────────────────

interface Account {
  id: number
  code: string
  name: string
  type?: string
  postable?: boolean
  party_type?: string
}

interface PartyItem { id: number; name: string }

interface AnalyticAccount { id: number; code: string; name: string; type: string }

// Multi-row table entry (Journal mode)
interface EntryRow { account_id: string; debit: string; credit: string }

// Single-side row (Payment Dr / Receipt Cr)
interface AmountRow { account_id: string; amount: string }

interface OpenDoc {
  id: number
  number: string
  customer_name?: string
  vendor_name?: string
  issue_date?: string
  bill_date?: string
  total: number
  balance_due: number
}

type FormMode = "journal" | "payment" | "receipt"
type CashBank  = "cash" | "bank"

// ── Helpers ──────────────────────────────────────────────────────────────────

const isCashOrBank = (a: Account) =>
  a.type === "Asset" &&
  (a.name.toLowerCase().includes("cash") ||
   a.name.toLowerCase().includes("bank") ||
   a.code.startsWith("100") ||
   a.code.startsWith("101"))

// Groups accounts by type into ordered optgroup buckets
function groupByType(accounts: Account[], order: string[]): { type: string; accounts: Account[] }[] {
  const map: Record<string, Account[]> = {}
  for (const a of accounts) {
    const t = a.type ?? "Other"
    if (!map[t]) map[t] = []
    map[t].push(a)
  }
  return order.filter(t => map[t]?.length).map(t => ({ type: t, accounts: map[t] }))
}

// ── Component ────────────────────────────────────────────────────────────────

export default function NewEntryPage() {
  const { t } = useTranslation()

  const router  = useRouter()
  const dp      = useDp()

  // ── Shared reference data ─────────────────────────────────────────────────
  const [accounts,       setAccounts]       = useState<Account[]>([])
  const [analyticAccounts, setAnalyticAccounts] = useState<AnalyticAccount[]>([])
  const [customers,      setCustomers]      = useState<PartyItem[]>([])
  const [vendors,        setVendors]        = useState<PartyItem[]>([])

  // ── Shared header fields ──────────────────────────────────────────────────
  const [date,              setDate]              = useState(new Date().toISOString().split("T")[0])
  const [description,       setDescription]       = useState("")
  const [analyticAccountId, setAnalyticAccountId] = useState("")
  const [customerId,        setCustomerId]        = useState("")
  const [vendorId,          setVendorId]          = useState("")

  // ── Mode ──────────────────────────────────────────────────────────────────
  const [mode, setMode] = useState<FormMode>("journal")

  // ── Journal-mode state ────────────────────────────────────────────────────
  const [jvType, setJvType] = useState("JV")
  const [rows,   setRows]   = useState<EntryRow[]>([
    { account_id: "", debit: "", credit: "" },
    { account_id: "", debit: "", credit: "" },
  ])

  // ── Payment-mode state ────────────────────────────────────────────────────
  const [payCashBank,      setPayCashBank]      = useState<CashBank>("cash")
  const [payToRows,        setPayToRows]        = useState<AmountRow[]>([{ account_id: "", amount: "" }])
  const [payFromAccountId, setPayFromAccountId] = useState("")

  // ── Receipt-mode state ────────────────────────────────────────────────────
  const [recCashBank,        setRecCashBank]        = useState<CashBank>("cash")
  const [recFromRows,        setRecFromRows]        = useState<AmountRow[]>([{ account_id: "", amount: "" }])
  const [recIntoAccountId,   setRecIntoAccountId]   = useState("")

  // ── Allocation panel ──────────────────────────────────────────────────────
  const [openDocs,    setOpenDocs]    = useState<OpenDoc[]>([])
  const [allocations, setAllocations] = useState<Record<number, string>>({})

  // ── Submission ────────────────────────────────────────────────────────────
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error,        setError]        = useState("")

  // ── Load reference data ───────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      apiFetch<{ total: number; items: Account[] }>("/api/accounts?limit=500"),
      apiFetch<AnalyticAccount[] | { items: AnalyticAccount[] }>("/api/analytic-accounts"),
      apiFetch<{ total: number; items: PartyItem[] }>("/api/customers?limit=500"),
      apiFetch<{ total: number; items: PartyItem[] }>("/api/vendors?limit=500"),
    ])
      .then(([d, an, custs, vends]) => {
        setAccounts(d.items.filter(a => a.postable !== false))
        const anItems = Array.isArray(an) ? an : ((an as { items: AnalyticAccount[] }).items ?? [])
        setAnalyticAccounts(anItems)
        setCustomers(custs.items ?? [])
        setVendors(vends.items ?? [])
      })
      .catch(console.error)
  }, [])

  // ── Allocation docs ───────────────────────────────────────────────────────
  const voucherTypeForMode =
    mode === "payment" ? (payCashBank === "cash" ? "CP" : "BP")
    : mode === "receipt" ? (recCashBank === "cash" ? "CR" : "BR")
    : jvType

  const showAllocation =
    (!!customerId || !!vendorId) &&
    ["CP","CR","BP","BR"].includes(voucherTypeForMode)

  useEffect(() => {
    if (!showAllocation) { setOpenDocs([]); setAllocations({}); return }
    const url = customerId
      ? `/api/invoices/open-for-allocation?customer_id=${customerId}`
      : `/api/bills/open-for-allocation?vendor_id=${vendorId}`
    apiFetch<OpenDoc[]>(url).then(setOpenDocs).catch(console.error)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId, vendorId, voucherTypeForMode])

  // ── Derived account lists ─────────────────────────────────────────────────

  // Payment Dr: everything EXCEPT cash/bank (those belong on Cr)
  const payToGroups = useMemo(() =>
    groupByType(
      accounts.filter(a => !isCashOrBank(a)),
      ["Expense", "Asset", "Liability", "Equity", "Revenue"],
    ),
  [accounts])

  // Receipt Cr: everything EXCEPT cash/bank (those belong on Dr)
  const recFromGroups = useMemo(() =>
    groupByType(
      accounts.filter(a => !isCashOrBank(a)),
      ["Revenue", "Asset", "Equity", "Liability", "Expense"],
    ),
  [accounts])

  // Cash or Bank accounts for the offsetting side
  const cashAccounts = useMemo(
    () => filterAccountsForSide(accounts, "CP", "credit").accounts,
    [accounts],
  )
  const bankAccounts = useMemo(
    () => filterAccountsForSide(accounts, "BP", "credit").accounts,
    [accounts],
  )
  const cashBankOptions = (cb: CashBank) => cb === "cash" ? cashAccounts : bankAccounts

  // ── Journal: per-row account filter (unchanged from before) ──────────────
  const hasJvFilter = !!VOUCHER_SIDE_FILTERS[jvType]

  const debitAccountIds = useMemo(
    () => new Set(rows.filter(r => parseFloat(r.debit) > 0 && r.account_id).map(r => parseInt(r.account_id))),
    [rows],
  )
  const creditAccountIds = useMemo(
    () => new Set(rows.filter(r => parseFloat(r.credit) > 0 && r.account_id).map(r => parseInt(r.account_id))),
    [rows],
  )

  function jvRowSide(row: EntryRow): "debit" | "credit" | "none" {
    if (parseFloat(row.debit)  > 0) return "debit"
    if (parseFloat(row.credit) > 0) return "credit"
    return "none"
  }

  function accountsForJvRow(row: EntryRow) {
    if (!hasJvFilter) return { debitAccounts: accounts, creditAccounts: accounts, side: "none" as const }
    const side = jvRowSide(row)
    if (side === "debit") {
      const { accounts: filtered } = filterAccountsForSide(accounts, jvType, "debit", creditAccountIds)
      return { debitAccounts: filtered, creditAccounts: [], side: "debit" as const }
    }
    if (side === "credit") {
      const { accounts: filtered } = filterAccountsForSide(accounts, jvType, "credit", debitAccountIds)
      return { debitAccounts: [], creditAccounts: filtered, side: "credit" as const }
    }
    const { accounts: db } = filterAccountsForSide(accounts, jvType, "debit")
    const { accounts: cr } = filterAccountsForSide(accounts, jvType, "credit")
    return { debitAccounts: db, creditAccounts: cr, side: "none" as const }
  }

  const hasArAccount = useMemo(
    () => rows.some(r => accounts.find(a => a.id === parseInt(r.account_id))?.party_type === "customer"),
    [rows, accounts],
  )
  const hasApAccount = useMemo(
    () => rows.some(r => accounts.find(a => a.id === parseInt(r.account_id))?.party_type === "vendor"),
    [rows, accounts],
  )

  // Journal totals
  const totalDebit  = rows.reduce((s, r) => s + (parseFloat(r.debit)  || 0), 0)
  const totalCredit = rows.reduce((s, r) => s + (parseFloat(r.credit) || 0), 0)
  const difference  = Math.abs(totalDebit - totalCredit)
  const balanced    = difference < 0.005

  // Payment / Receipt totals
  const payTotal = payToRows.reduce((s, r) => s + (parseFloat(r.amount) || 0), 0)
  const recTotal = recFromRows.reduce((s, r) => s + (parseFloat(r.amount) || 0), 0)

  // ── Journal row helpers ───────────────────────────────────────────────────
  const addJvRow = () => setRows(r => [...r, { account_id: "", debit: "", credit: "" }])
  const removeJvRow = (i: number) => { if (rows.length > 2) setRows(r => r.filter((_, j) => j !== i)) }
  const updateJvRow = (i: number, field: keyof EntryRow, value: string) => {
    setRows(prev => prev.map((r, j) => {
      if (j !== i) return r
      const copy = { ...r, [field]: value }
      if (field === "debit"  && value) copy.credit = ""
      if (field === "credit" && value) copy.debit  = ""
      return copy
    }))
  }

  // ── Payment / Receipt row helpers ─────────────────────────────────────────
  const addPayRow = () => setPayToRows(r => [...r, { account_id: "", amount: "" }])
  const removePayRow = (i: number) => { if (payToRows.length > 1) setPayToRows(r => r.filter((_, j) => j !== i)) }
  const updatePayRow = (i: number, field: keyof AmountRow, value: string) =>
    setPayToRows(prev => prev.map((r, j) => j === i ? { ...r, [field]: value } : r))

  const addRecRow = () => setRecFromRows(r => [...r, { account_id: "", amount: "" }])
  const removeRecRow = (i: number) => { if (recFromRows.length > 1) setRecFromRows(r => r.filter((_, j) => j !== i)) }
  const updateRecRow = (i: number, field: keyof AmountRow, value: string) =>
    setRecFromRows(prev => prev.map((r, j) => j === i ? { ...r, [field]: value } : r))

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    let entries: { account_id: number; debit: number; credit: number }[] = []
    const voucherType = voucherTypeForMode

    if (mode === "journal") {
      if (!balanced) { setError("Journal entry is not balanced. Debits must equal Credits."); return }
      entries = rows
        .filter(r => r.account_id && (parseFloat(r.debit) > 0 || parseFloat(r.credit) > 0))
        .map(r => ({ account_id: parseInt(r.account_id), debit: parseFloat(r.debit) || 0, credit: parseFloat(r.credit) || 0 }))
    } else if (mode === "payment") {
      if (!payFromAccountId) { setError("Select the cash/bank account to pay from."); return }
      if (payTotal <= 0) { setError("Enter at least one payment amount."); return }
      entries = [
        ...payToRows
          .filter(r => r.account_id && parseFloat(r.amount) > 0)
          .map(r => ({ account_id: parseInt(r.account_id), debit: parseFloat(r.amount), credit: 0 })),
        { account_id: parseInt(payFromAccountId), debit: 0, credit: payTotal },
      ]
    } else {
      if (!recIntoAccountId) { setError("Select the cash/bank account to receive into."); return }
      if (recTotal <= 0) { setError("Enter at least one receipt amount."); return }
      entries = [
        { account_id: parseInt(recIntoAccountId), debit: recTotal, credit: 0 },
        ...recFromRows
          .filter(r => r.account_id && parseFloat(r.amount) > 0)
          .map(r => ({ account_id: parseInt(r.account_id), debit: 0, credit: parseFloat(r.amount) })),
      ]
    }

    const allocationEntries = Object.entries(allocations)
      .filter(([, amt]) => parseFloat(amt) > 0)
      .map(([id, amt]) => customerId
        ? { invoice_id: parseInt(id), amount: parseFloat(amt) }
        : { bill_id:    parseInt(id), amount: parseFloat(amt) })

    const payload = {
      date, description,
      voucher_type: voucherType,
      analytic_account_id: analyticAccountId ? parseInt(analyticAccountId) : null,
      customer_id: customerId ? parseInt(customerId) : null,
      vendor_id:   vendorId   ? parseInt(vendorId)   : null,
      entries,
      allocations: allocationEntries.length ? allocationEntries : undefined,
    }

    setIsSubmitting(true)
    try {
      const created = await apiFetch<{ id: number }>("/api/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      router.push(`/journal/${created.id}/print`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setIsSubmitting(false)
    }
  }

  // ── Shared header fields block ────────────────────────────────────────────
  const SharedHeader = (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Date</label>
        <input type="date" value={date} onChange={e => setDate(e.target.value)} required
          className="w-full px-3 py-2.5 bg-[var(--bg-page)] border border-transparent rounded-lg focus:ring-2 focus:ring-[var(--primary)] focus:bg-white outline-none text-sm" />
      </div>
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Description / Memo</label>
        <input type="text" value={description} onChange={e => setDescription(e.target.value)}
          placeholder="e.g. Monthly Rent Payment" required
          className="w-full px-3 py-2.5 bg-[var(--bg-page)] border border-transparent rounded-lg focus:ring-2 focus:ring-[var(--primary)] focus:bg-white outline-none text-sm" />
      </div>
    </div>
  )

  // ── Analytic + Party pickers (shared) ─────────────────────────────────────
  const SharedParty = (showAr: boolean, showAp: boolean) => (
    <>
      {analyticAccounts.length > 0 && (
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">
            Analytic Account <span className="font-normal normal-case">(optional)</span>
          </label>
          <select value={analyticAccountId} onChange={e => setAnalyticAccountId(e.target.value)}
            className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
            <option value="">— none —</option>
            {analyticAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
          </select>
        </div>
      )}
      {showAr && customers.length > 0 && (
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.customer', 'Customer')}<span className="font-normal normal-case">(optional)</span>
          </label>
          <select value={customerId} onChange={e => setCustomerId(e.target.value)}
            className="w-full px-3 py-2.5 bg-[var(--bg-page)] border border-transparent rounded-lg focus:ring-2 focus:ring-[var(--primary)] focus:bg-white outline-none text-sm">
            <option value="">— none —</option>
            {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
      )}
      {showAp && vendors.length > 0 && (
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.vendor', 'Vendor')}<span className="font-normal normal-case">(optional)</span>
          </label>
          <select value={vendorId} onChange={e => setVendorId(e.target.value)}
            className="w-full px-3 py-2.5 bg-[var(--bg-page)] border border-transparent rounded-lg focus:ring-2 focus:ring-[var(--primary)] focus:bg-white outline-none text-sm">
            <option value="">— none —</option>
            {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </div>
      )}
    </>
  )

  // ── Allocation panel (shared) ──────────────────────────────────────────────
  const AllocationPanel = showAllocation && (
    <div>
      <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-2">
        Allocate to Open {customerId ? "Invoices" : "Bills"}
        <span className="font-normal normal-case ml-1">(optional)</span>
      </label>
      {openDocs.length === 0 ? (
        <p className="text-xs text-[var(--text-primary)]/40 italic">No outstanding {customerId ? "invoices" : "bills"} found.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-xs">
            <thead className="bg-[var(--bg-page)]">
              <tr>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">{customerId ? "Invoice" : "Bill"}</th>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Date</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Balance Due</th>
                <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-32">Allocate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {openDocs.map(doc => (
                <tr key={doc.id}>
                  <td className="px-3 py-2 font-mono">{doc.number}</td>
                  <td className="px-3 py-2 text-[var(--text-primary)]/60">{doc.issue_date ?? doc.bill_date ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-mono">{doc.balance_due.toFixed(dp)}</td>
                  <td className="px-2 py-1.5">
                    <input type="number" step="0.01" min="0" max={doc.balance_due}
                      value={allocations[doc.id] ?? ""}
                      onChange={e => setAllocations(prev => ({ ...prev, [doc.id]: e.target.value }))}
                      placeholder="0.00"
                      className="w-full px-2 py-1.5 bg-white border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--primary)] outline-none text-right font-mono" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )

  // ── Cash/Bank toggle (Payment + Receipt) ──────────────────────────────────
  const CashBankToggle = (value: CashBank, onChange: (v: CashBank) => void) => (
    <div className="flex gap-1 p-1 bg-[var(--bg-page)] rounded-lg w-fit">
      {(["cash", "bank"] as CashBank[]).map(opt => (
        <button key={opt} type="button" onClick={() => onChange(opt)}
          className={cn(
            "px-4 py-1.5 rounded-md text-xs font-bold uppercase tracking-wider transition-all",
            value === opt
              ? "bg-[#1a1814] text-white shadow-sm"
              : "text-[var(--text-primary)]/50 hover:text-[var(--text-primary)]",
          )}>
          {opt === "cash" ? "💵 Cash" : "🏦 Bank"}
        </button>
      ))}
    </div>
  )

  // ── Account optgroup select (Payment Dr / Receipt Cr) ────────────────────
  const GroupedSelect = (
    groups: { type: string; accounts: Account[] }[],
    value: string,
    onChange: (v: string) => void,
    placeholder: string,
  ) => (
    <select value={value} onChange={e => onChange(e.target.value)} required
      className="w-full px-3 py-2.5 bg-white border border-[var(--border)] rounded-lg focus:ring-2 focus:ring-[var(--primary)] outline-none text-sm">
      <option value="">{placeholder}</option>
      {groups.map(g => (
        <optgroup key={g.type} label={`── ${g.type} ──`}>
          {g.accounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
        </optgroup>
      ))}
    </select>
  )

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-4xl mx-auto">
      {/* Page header */}
      <header className="flex items-center gap-3 mb-5">
        <ScrollText className="w-6 h-6 text-[var(--primary)] shrink-0" />
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[var(--text-primary)]">New Entry</h1>
          <p className="text-xs sm:text-sm text-[var(--text-primary)]/60">Record a manual double-entry transaction</p>
        </div>
      </header>

      {/* Mode tabs */}
      <div className="flex gap-2 mb-4">
        {([
          { key: "journal", label: "Journal", Icon: BookOpen,        desc: "JV / Contra" },
          { key: "payment", label: "Payment", Icon: ArrowUpFromLine, desc: "Cash / Bank payment" },
          { key: "receipt", label: "Receipt", Icon: ArrowDownToLine, desc: "Cash / Bank receipt" },
        ] as const).map(({ key, label, Icon, desc }) => (
          <button key={key} type="button" onClick={() => setMode(key)}
            className={cn(
              "flex-1 flex flex-col items-center gap-1 py-3 px-2 rounded-xl border-2 transition-all text-center",
              mode === key
                ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--text-primary)]"
                : "border-[var(--border)] bg-white text-[var(--text-primary)]/50 hover:border-[var(--primary)]/40 hover:text-[var(--text-primary)]",
            )}>
            <Icon className={cn("w-5 h-5", mode === key && "text-[var(--primary)]")} />
            <span className="text-xs font-bold uppercase tracking-wider">{label}</span>
            <span className="text-[10px] hidden sm:block">{desc}</span>
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <section className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-[var(--border)] space-y-4">

          {/* ══════════════════════ JOURNAL MODE ════════════════════════════ */}
          {mode === "journal" && (<>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Voucher Type</label>
                <select value={jvType} onChange={e => setJvType(e.target.value)}
                  className="w-full px-3 py-2.5 bg-[var(--bg-page)] border border-transparent rounded-lg focus:ring-2 focus:ring-[var(--primary)] focus:bg-white outline-none text-sm">
                  <option value="JV">Journal Voucher</option>
                  <option value="CO">Contra</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Date</label>
                <input type="date" value={date} onChange={e => setDate(e.target.value)} required
                  className="w-full px-3 py-2.5 bg-[var(--bg-page)] border border-transparent rounded-lg focus:ring-2 focus:ring-[var(--primary)] focus:bg-white outline-none text-sm" />
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">Description / Memo</label>
                <input type="text" value={description} onChange={e => setDescription(e.target.value)}
                  placeholder="e.g. Month-end accrual" required
                  className="w-full px-3 py-2.5 bg-[var(--bg-page)] border border-transparent rounded-lg focus:ring-2 focus:ring-[var(--primary)] focus:bg-white outline-none text-sm" />
              </div>
            </div>

            {analyticAccounts.length > 0 && (
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">
                  Analytic Account <span className="font-normal normal-case">(optional)</span>
                </label>
                <select value={analyticAccountId} onChange={e => setAnalyticAccountId(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm">
                  <option value="">— none —</option>
                  {analyticAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                </select>
              </div>
            )}
            {hasArAccount && SharedParty(true, false)}
            {hasApAccount && SharedParty(false, true)}
            {AllocationPanel}

            {/* Line items table */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Line Items</span>
                {hasJvFilter && (
                  <span className="text-[10px] text-[var(--primary)] font-semibold">Accounts filtered for {jvType}</span>
                )}
              </div>

              {/* Desktop table */}
              <div className="hidden md:block overflow-x-auto rounded-lg border border-[var(--border)]">
                <table className="w-full text-sm">
                  <thead className="bg-[var(--bg-page)]">
                    <tr>
                      <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">{t('col.account', 'Account')}</th>
                      <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-36">{t('col.debit', 'Debit')}</th>
                      <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 w-36">{t('col.credit', 'Credit')}</th>
                      <th className="w-10"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {rows.map((row, idx) => {
                      const { debitAccounts, creditAccounts, side } = accountsForJvRow(row)
                      return (
                        <tr key={idx}>
                          <td className="px-3 py-2">
                            <select value={row.account_id} onChange={e => updateJvRow(idx, "account_id", e.target.value)} required
                              className="w-full px-2 py-2 bg-white border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--primary)] outline-none text-sm">
                              <option value="">Select Account</option>
                              {side === "none" && hasJvFilter ? (
                                <>
                                  {debitAccounts.length > 0 && <optgroup label="── Debit side ──">{debitAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</optgroup>}
                                  {creditAccounts.length > 0 && <optgroup label="── Credit side ──">{creditAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</optgroup>}
                                </>
                              ) : (
                                (side === "debit" ? debitAccounts : side === "credit" ? creditAccounts : accounts).map(a =>
                                  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)
                              )}
                            </select>
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" step="0.01" value={row.debit}
                              onChange={e => updateJvRow(idx, "debit", e.target.value)} placeholder="0.00"
                              className="w-full px-2 py-2 bg-white border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--primary)] outline-none text-right font-mono text-sm" />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" step="0.01" value={row.credit}
                              onChange={e => updateJvRow(idx, "credit", e.target.value)} placeholder="0.00"
                              className="w-full px-2 py-2 bg-white border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--primary)] outline-none text-right font-mono text-sm" />
                          </td>
                          <td className="px-2 py-2 text-center">
                            <button type="button" onClick={() => removeJvRow(idx)} disabled={rows.length <= 2}
                              className="p-1.5 text-red-400 hover:text-red-600 disabled:opacity-30 transition-colors">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="md:hidden space-y-2">
                {rows.map((row, idx) => {
                  const { debitAccounts, creditAccounts, side } = accountsForJvRow(row)
                  return (
                    <div key={idx} className="border border-[var(--border)] rounded-lg p-3 bg-[#faf8f4]">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-primary)]/55">Line {idx + 1}</span>
                        <button type="button" onClick={() => removeJvRow(idx)} disabled={rows.length <= 2}
                          className="p-1 text-red-400 hover:text-red-600 disabled:opacity-30 transition-colors">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <select value={row.account_id} onChange={e => updateJvRow(idx, "account_id", e.target.value)} required
                        className="w-full px-3 py-2 bg-white border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--primary)] outline-none text-sm mb-2">
                        <option value="">Select Account</option>
                        {side === "none" && hasJvFilter ? (
                          <>
                            {debitAccounts.length > 0 && <optgroup label="── Debit side ──">{debitAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</optgroup>}
                            {creditAccounts.length > 0 && <optgroup label="── Credit side ──">{creditAccounts.map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</optgroup>}
                          </>
                        ) : (
                          (side === "debit" ? debitAccounts : side === "credit" ? creditAccounts : accounts).map(a =>
                            <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)
                        )}
                      </select>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-[9px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.debit', 'Debit')}</label>
                          <input type="number" step="0.01" inputMode="decimal" value={row.debit}
                            onChange={e => updateJvRow(idx, "debit", e.target.value)} placeholder="0.00"
                            className="w-full px-2 py-2 bg-white border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--primary)] outline-none text-right font-mono text-sm" />
                        </div>
                        <div>
                          <label className="block text-[9px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">{t('col.credit', 'Credit')}</label>
                          <input type="number" step="0.01" inputMode="decimal" value={row.credit}
                            onChange={e => updateJvRow(idx, "credit", e.target.value)} placeholder="0.00"
                            className="w-full px-2 py-2 bg-white border border-[var(--border)] rounded-md focus:ring-2 focus:ring-[var(--primary)] outline-none text-right font-mono text-sm" />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>

              <button type="button" onClick={addJvRow}
                className="mt-3 inline-flex items-center gap-1.5 text-[var(--primary)] text-sm font-bold hover:underline">
                <Plus className="w-4 h-4" /> Add Line
              </button>
            </div>

            {/* Totals */}
            <div className="pt-3 border-t border-[var(--border)]">
              <div className="grid grid-cols-3 gap-2 sm:gap-4 text-right font-mono">
                <div>
                  <div className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">{t('col.debit', 'Debit')}</div>
                  <div className="text-sm sm:text-base font-bold text-[var(--text-primary)]">{totalDebit.toFixed(dp)}</div>
                </div>
                <div>
                  <div className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">{t('col.credit', 'Credit')}</div>
                  <div className="text-sm sm:text-base font-bold text-[var(--text-primary)]">{totalCredit.toFixed(dp)}</div>
                </div>
                <div className="border-l border-[var(--border)] pl-2 sm:pl-4">
                  <div className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">Diff</div>
                  <div className={cn("text-sm sm:text-base font-bold", balanced ? "text-emerald-600" : "text-red-600")}>
                    {difference.toFixed(dp)}
                  </div>
                </div>
              </div>
            </div>
          </>)}

          {/* ══════════════════════ PAYMENT MODE ════════════════════════════ */}
          {mode === "payment" && (<>
            {/* Cash / Bank toggle */}
            <div className="flex items-center gap-4">
              {CashBankToggle(payCashBank, setPayCashBank)}
              <span className="text-xs text-[var(--text-primary)]/40">
                Voucher type: <strong>{payCashBank === "cash" ? "CP" : "BP"}</strong>
              </span>
            </div>

            {SharedHeader}

            {/* Cr: Cash / Bank source — shown early so user picks the account first */}
            <div>
              <div className="flex items-center justify-between gap-4">
                <div className="flex-1">
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">
                    Pay From — {payCashBank === "cash" ? "Cash Account" : "Bank Account"} (Cr)
                  </label>
                  <select value={payFromAccountId} onChange={e => setPayFromAccountId(e.target.value)} required
                    className="w-full px-3 py-2.5 bg-white border border-[var(--border)] rounded-lg focus:ring-2 focus:ring-[var(--primary)] outline-none text-sm">
                    <option value="">Select {payCashBank === "cash" ? "cash" : "bank"} account</option>
                    {cashBankOptions(payCashBank).map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                  </select>
                </div>
                <div className="text-right shrink-0 pt-5">
                  <div className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">{t('col.total', 'Total')}</div>
                  <div className="text-lg font-bold font-mono text-[var(--text-primary)]">{payTotal.toFixed(dp)}</div>
                </div>
              </div>
              {cashBankOptions(payCashBank).length === 0 && (
                <div className="mt-2 flex items-start gap-2 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2 text-xs">
                  <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  No {payCashBank} account found — add one in Chart of Accounts
                </div>
              )}
            </div>

            {SharedParty(false, vendors.length > 0)}
            {AllocationPanel}

            {/* Dr: Items being paid */}
            <div className="pt-3 border-t border-[var(--border)]">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Pay To (Dr)</span>
                <span className="text-[10px] text-[var(--primary)]">Expenses · Assets · Liabilities</span>
              </div>
              <div className="space-y-2">
                {payToRows.map((row, idx) => (
                  <div key={idx} className="flex gap-2 items-center">
                    <div className="flex-1">
                      {GroupedSelect(payToGroups, row.account_id, v => updatePayRow(idx, "account_id", v), "Select account to pay")}
                    </div>
                    <input type="number" step="0.01" inputMode="decimal" value={row.amount}
                      onChange={e => updatePayRow(idx, "amount", e.target.value)}
                      placeholder="0.00"
                      className="w-32 px-3 py-2.5 bg-white border border-[var(--border)] rounded-lg focus:ring-2 focus:ring-[var(--primary)] outline-none text-right font-mono text-sm" />
                    <button type="button" onClick={() => removePayRow(idx)} disabled={payToRows.length <= 1}
                      className="p-2 text-red-400 hover:text-red-600 disabled:opacity-30 transition-colors shrink-0">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
              <button type="button" onClick={addPayRow}
                className="mt-2 inline-flex items-center gap-1.5 text-[var(--primary)] text-sm font-bold hover:underline">
                <Plus className="w-4 h-4" /> Add Line
              </button>
            </div>
          </>)}

          {/* ══════════════════════ RECEIPT MODE ════════════════════════════ */}
          {mode === "receipt" && (<>
            {/* Cash / Bank toggle */}
            <div className="flex items-center gap-4">
              {CashBankToggle(recCashBank, setRecCashBank)}
              <span className="text-xs text-[var(--text-primary)]/40">
                Voucher type: <strong>{recCashBank === "cash" ? "CR" : "BR"}</strong>
              </span>
            </div>

            {SharedHeader}

            {/* Dr: Cash / Bank destination — shown early so user picks the account first */}
            <div>
              <div className="flex items-center justify-between gap-4">
                <div className="flex-1">
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-1">
                    Received Into — {recCashBank === "cash" ? "Cash Account" : "Bank Account"} (Dr)
                  </label>
                  <select value={recIntoAccountId} onChange={e => setRecIntoAccountId(e.target.value)} required
                    className="w-full px-3 py-2.5 bg-white border border-[var(--border)] rounded-lg focus:ring-2 focus:ring-[var(--primary)] outline-none text-sm">
                    <option value="">Select {recCashBank === "cash" ? "cash" : "bank"} account</option>
                    {cashBankOptions(recCashBank).map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                  </select>
                </div>
                <div className="text-right shrink-0 pt-5">
                  <div className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55 mb-0.5">{t('col.total', 'Total')}</div>
                  <div className="text-lg font-bold font-mono text-[var(--text-primary)]">{recTotal.toFixed(dp)}</div>
                </div>
              </div>
              {cashBankOptions(recCashBank).length === 0 && (
                <div className="mt-2 flex items-start gap-2 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2 text-xs">
                  <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  No {recCashBank} account found — add one in Chart of Accounts
                </div>
              )}
            </div>

            {SharedParty(customers.length > 0, false)}
            {AllocationPanel}

            {/* Cr: Source items */}
            <div className="pt-3 border-t border-[var(--border)]">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/55">Received From (Cr)</span>
                <span className="text-[10px] text-[var(--primary)]">Revenue · Assets · Equity · Liabilities</span>
              </div>
              <div className="space-y-2">
                {recFromRows.map((row, idx) => (
                  <div key={idx} className="flex gap-2 items-center">
                    <div className="flex-1">
                      {GroupedSelect(recFromGroups, row.account_id, v => updateRecRow(idx, "account_id", v), "Select income / source account")}
                    </div>
                    <input type="number" step="0.01" inputMode="decimal" value={row.amount}
                      onChange={e => updateRecRow(idx, "amount", e.target.value)}
                      placeholder="0.00"
                      className="w-32 px-3 py-2.5 bg-white border border-[var(--border)] rounded-lg focus:ring-2 focus:ring-[var(--primary)] outline-none text-right font-mono text-sm" />
                    <button type="button" onClick={() => removeRecRow(idx)} disabled={recFromRows.length <= 1}
                      className="p-2 text-red-400 hover:text-red-600 disabled:opacity-30 transition-colors shrink-0">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
              <button type="button" onClick={addRecRow}
                className="mt-2 inline-flex items-center gap-1.5 text-[var(--primary)] text-sm font-bold hover:underline">
                <Plus className="w-4 h-4" /> Add Line
              </button>
            </div>
          </>)}
        </section>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2.5 rounded-lg flex items-start gap-2 text-xs sm:text-sm">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col sm:flex-row sm:justify-end gap-2 sm:gap-3 sticky bottom-0 sm:static bg-[var(--bg-page)] sm:bg-transparent py-2 sm:py-0 -mx-3 sm:mx-0 px-3 sm:px-0 border-t sm:border-t-0 border-[var(--border)]">
          <button type="button" onClick={() => router.back()}
            className="px-5 py-2.5 bg-white border border-[var(--border)] rounded-lg font-semibold hover:bg-[var(--bg-page)] transition-colors text-sm">{t('common.cancel', 'Cancel')}</button>
          <button type="submit"
            disabled={isSubmitting || (mode === "journal" && !balanced)}
            className="px-5 py-2.5 bg-[#1a1814] text-white rounded-lg font-semibold flex items-center justify-center gap-2 hover:bg-[var(--primary)] hover:text-black transition-all disabled:opacity-50 text-sm">
            <Save className="w-4 h-4" />
            {isSubmitting ? "Saving…" : "Post Transaction"}
          </button>
        </div>
      </form>
    </div>
  )
}
