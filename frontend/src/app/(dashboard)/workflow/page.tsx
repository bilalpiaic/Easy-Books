"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Printer, ChevronRight, GitBranch, BookOpen, BarChart3, RefreshCw, Package, CheckCircle, Globe, Calendar, RotateCcw, Factory, Link2, Radio, Undo2, Wallet, LayoutDashboard } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

type BusinessModel = "simple" | "services" | "trader" | "manufacturing" | "telecom_franchise"
const INVENTORY_MODELS: BusinessModel[] = ["trader", "manufacturing", "telecom_franchise"]

// ── Primitive building blocks ────────────────────────────────────────────────

interface StepBoxProps {
  title: string
  gl?: string
  impact?: string
  accent?: "gold" | "green" | "blue" | "orange" | "purple" | "teal"
  small?: boolean
}

const ACCENT_STYLES: Record<NonNullable<StepBoxProps["accent"]>, { border: string; bg: string; title: string; badge: string }> = {
  gold:   { border: "border-[#b8943f]",   bg: "bg-[#faf6ec]",   title: "text-[#7a5c1e]",   badge: "bg-[#b8943f]/15 text-[#7a5c1e]"   },
  green:  { border: "border-green-400",   bg: "bg-green-50",    title: "text-green-800",    badge: "bg-green-100 text-green-800"       },
  blue:   { border: "border-blue-400",    bg: "bg-blue-50",     title: "text-blue-800",     badge: "bg-blue-100 text-blue-800"         },
  orange: { border: "border-orange-400",  bg: "bg-orange-50",   title: "text-orange-800",   badge: "bg-orange-100 text-orange-800"     },
  purple: { border: "border-purple-400",  bg: "bg-purple-50",   title: "text-purple-800",   badge: "bg-purple-100 text-purple-800"     },
  teal:   { border: "border-teal-400",    bg: "bg-teal-50",     title: "text-teal-800",     badge: "bg-teal-100 text-teal-800"         },
}

function StepBox({ title, gl, impact, accent = "gold", small = false }: StepBoxProps) {
  const s = ACCENT_STYLES[accent]
  return (
    <div className={`border-2 ${s.border} ${s.bg} rounded-xl ${small ? "px-3 py-2" : "px-4 py-3"} min-w-0`}>
      <p className={`font-semibold ${small ? "text-xs" : "text-sm"} ${s.title} leading-tight`}>{title}</p>
      {gl && (
        <p className={`font-mono text-[10px] mt-1.5 ${s.badge} rounded px-1.5 py-0.5 inline-block leading-tight`}>{gl}</p>
      )}
      {impact && (
        <p className="text-[10px] text-[#1a1814]/55 mt-1 leading-tight">{impact}</p>
      )}
    </div>
  )
}

function Arrow({ vertical = false }: { vertical?: boolean }) {
  if (vertical) {
    return (
      <div className="flex flex-col items-center py-0.5">
        <div className="w-0.5 h-4 bg-[#b8943f]/40" />
        <div
          className="w-0 h-0"
          style={{ borderLeft: "5px solid transparent", borderRight: "5px solid transparent", borderTop: "7px solid #b8943f99" }}
        />
      </div>
    )
  }
  return (
    <div className="flex items-center px-1">
      <div className="h-0.5 w-6 bg-[#b8943f]/40" />
      <div
        className="w-0 h-0"
        style={{ borderTop: "5px solid transparent", borderBottom: "5px solid transparent", borderLeft: "7px solid #b8943f99" }}
      />
    </div>
  )
}

// ── Flow wrappers ─────────────────────────────────────────────────────────────

function HFlow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-0">
      {children}
    </div>
  )
}

function VFlow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-0">
      {children}
    </div>
  )
}

// ── Section card wrapper ──────────────────────────────────────────────────────

interface SectionCardProps {
  icon: React.ElementType
  title: string
  subtitle: string
  children: React.ReactNode
  iconColor?: string
}

function SectionCard({ icon: Icon, title, subtitle, children, iconColor = "text-[#b8943f]" }: SectionCardProps) {
  return (
    <div className="bg-white border border-[#ede9e2] rounded-2xl shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[#ede9e2] bg-[#f6f3ee] flex items-center gap-3">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center bg-white border border-[#ede9e2] ${iconColor}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-[#1a1814]">{title}</h2>
          <p className="text-[10px] text-[#1a1814]/50 font-medium tracking-wide uppercase">{subtitle}</p>
        </div>
      </div>
      <div className="p-5 overflow-x-auto">
        {children}
      </div>
    </div>
  )
}

// ── Double-entry callout ──────────────────────────────────────────────────────

function DoubleEntryCallout() {
  return (
    <div className="bg-[#1a1814] text-white rounded-2xl px-6 py-5 flex flex-col sm:flex-row gap-4 items-start sm:items-center">
      <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-[#b8943f] flex items-center justify-center text-white font-serif font-bold text-lg">
        =
      </div>
      <div className="flex-1">
        <p className="font-bold text-[#ffd966] text-sm mb-1">The Double-Entry Rule</p>
        <p className="text-white/80 text-xs leading-relaxed">
          Every transaction affects <span className="text-[#ffd966] font-semibold">at least two accounts</span>.
          Total debits must always equal total credits. This keeps the accounting equation balanced:{" "}
          <span className="font-mono text-[#ffd966]">Assets = Liabilities + Equity</span>.
        </p>
      </div>
      <div className="bg-[#ffd966]/10 border border-[#ffd966]/30 rounded-xl px-4 py-3 text-center flex-shrink-0">
        <p className="text-[#ffd966] font-mono text-xs font-bold">∑ Debit</p>
        <p className="text-white/40 text-lg font-light leading-none my-0.5">=</p>
        <p className="text-[#ffd966] font-mono text-xs font-bold">∑ Credit</p>
      </div>
    </div>
  )
}

// ── Cycle diagrams ────────────────────────────────────────────────────────────

function SalesCycleFlow() {
  return (
    <div className="space-y-4 min-w-[560px]">
      {/* Row 1 */}
      <HFlow>
        <StepBox
          title="Customer"
          impact="Initiate sale"
          accent="blue"
        />
        <Arrow />
        <StepBox
          title="Invoice Created"
          gl="Dr A/R · Cr Revenue"
          impact="Revenue recognised"
          accent="gold"
        />
        <Arrow />
        <StepBox
          title="Payment Received"
          gl="Dr Bank · Cr A/R"
          impact="Cash settled"
          accent="green"
        />
        <Arrow />
        <StepBox
          title="Invoice Marked Paid"
          impact="A/R cleared to zero"
          accent="teal"
        />
      </HFlow>

      {/* GL detail strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
        <div className="bg-[#faf6ec] border border-[#b8943f]/30 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#b8943f] mb-2">Step 2 — Invoice GL Entry</p>
          <div className="space-y-1 font-mono text-xs text-[#1a1814]">
            <div className="flex justify-between">
              <span className="text-[#7a5c1e]">Dr Accounts Receivable</span>
              <span className="text-[#1a1814]/60">+amount</span>
            </div>
            <div className="flex justify-between pl-4">
              <span className="text-green-700">Cr Revenue</span>
              <span className="text-[#1a1814]/60">+amount</span>
            </div>
          </div>
        </div>
        <div className="bg-green-50 border border-green-300/50 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-green-700 mb-2">Step 3 — Payment GL Entry</p>
          <div className="space-y-1 font-mono text-xs text-[#1a1814]">
            <div className="flex justify-between">
              <span className="text-[#7a5c1e]">Dr Bank / Cash</span>
              <span className="text-[#1a1814]/60">+amount</span>
            </div>
            <div className="flex justify-between pl-4">
              <span className="text-green-700">Cr Accounts Receivable</span>
              <span className="text-[#1a1814]/60">-amount</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function PurchaseCycleFlow() {
  return (
    <div className="space-y-4 min-w-[560px]">
      {/* Row 1 */}
      <HFlow>
        <StepBox
          title="Vendor"
          impact="Initiate purchase"
          accent="purple"
        />
        <Arrow />
        <StepBox
          title="Bill Created"
          gl="Dr Expense / Inventory · Cr A/P"
          impact="Payable recorded"
          accent="orange"
        />
        <Arrow />
        <StepBox
          title="Bill Payment"
          gl="Dr A/P · Cr Bank"
          impact="Cash paid out"
          accent="gold"
        />
        <Arrow />
        <StepBox
          title="Bill Marked Paid"
          impact="A/P cleared to zero"
          accent="teal"
        />
      </HFlow>

      {/* GL detail strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
        <div className="bg-orange-50 border border-orange-300/50 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-orange-700 mb-2">Step 2 — Bill GL Entry</p>
          <div className="space-y-1 font-mono text-xs text-[#1a1814]">
            <div className="flex justify-between">
              <span className="text-[#7a5c1e]">Dr Expense / Inventory</span>
              <span className="text-[#1a1814]/60">+amount</span>
            </div>
            <div className="flex justify-between pl-4">
              <span className="text-orange-700">Cr Accounts Payable</span>
              <span className="text-[#1a1814]/60">+amount</span>
            </div>
          </div>
        </div>
        <div className="bg-[#faf6ec] border border-[#b8943f]/30 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#b8943f] mb-2">Step 3 — Payment GL Entry</p>
          <div className="space-y-1 font-mono text-xs text-[#1a1814]">
            <div className="flex justify-between">
              <span className="text-[#7a5c1e]">Dr Accounts Payable</span>
              <span className="text-[#1a1814]/60">-amount</span>
            </div>
            <div className="flex justify-between pl-4">
              <span className="text-orange-700">Cr Bank / Cash</span>
              <span className="text-[#1a1814]/60">-amount</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ManualJournalFlow() {
  return (
    <div className="min-w-[480px]">
      <HFlow>
        <StepBox
          title="Entry Form"
          impact="Date, description, ref"
          accent="blue"
        />
        <Arrow />
        <StepBox
          title="Debit / Credit Lines"
          gl="Account + amount each line"
          impact="Add all affected accounts"
          accent="gold"
        />
        <Arrow />
        <StepBox
          title="Validate Dr = Cr"
          impact="System enforces balance"
          accent="green"
        />
        <Arrow />
        <StepBox
          title="Post to GL"
          impact="Entries saved to ledger"
          accent="teal"
        />
        <Arrow />
        <StepBox
          title="Reflected in Reports"
          gl="Trial Balance · P&L · Balance Sheet"
          impact="Real-time update"
          accent="purple"
        />
      </HFlow>
      <p className="mt-4 text-xs text-[#1a1814]/55 leading-relaxed">
        Manual journal entries are used for adjustments, accruals, depreciation, corrections, and any transaction
        that does not originate from an invoice or bill. They post immediately to the General Ledger.
      </p>
    </div>
  )
}

function FinancialStatementFlow() {
  return (
    <div className="space-y-4 min-w-[520px]">
      {/* Source */}
      <div className="flex justify-center">
        <StepBox
          title="All GL Entries"
          gl="Every Dr & Cr line in the system"
          impact="Single source of truth"
          accent="gold"
        />
      </div>
      <div className="flex justify-center">
        <Arrow vertical />
      </div>
      <div className="flex justify-center">
        <StepBox
          title="Trial Balance"
          gl="∑ Dr = ∑ Cr per account"
          impact="Aggregated account balances"
          accent="blue"
        />
      </div>
      <div className="flex justify-center">
        <Arrow vertical />
      </div>

      {/* Three output statements */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-green-50 border-2 border-green-300 rounded-xl p-4">
          <p className="text-xs font-bold text-green-800 mb-2">Income Statement (P&L)</p>
          <div className="font-mono text-[10px] text-green-700 space-y-0.5">
            <p>Revenue accounts</p>
            <p className="pl-2">- Expense accounts</p>
            <p className="border-t border-green-200 mt-1 pt-1 font-bold">= Net Profit / Loss</p>
          </div>
        </div>
        <div className="bg-blue-50 border-2 border-blue-300 rounded-xl p-4">
          <p className="text-xs font-bold text-blue-800 mb-2">Balance Sheet</p>
          <div className="font-mono text-[10px] text-blue-700 space-y-0.5">
            <p>Assets</p>
            <p className="pl-2">= Liabilities</p>
            <p className="pl-2">+ Equity</p>
            <p className="pl-2">+ Retained Earnings</p>
          </div>
        </div>
        <div className="bg-purple-50 border-2 border-purple-300 rounded-xl p-4">
          <p className="text-xs font-bold text-purple-800 mb-2">Cash Flow Statement</p>
          <div className="font-mono text-[10px] text-purple-700 space-y-0.5">
            <p>Operating CF</p>
            <p>+ Investing CF</p>
            <p>+ Financing CF</p>
            <p className="border-t border-purple-200 mt-1 pt-1 font-bold">= Net Cash Change</p>
          </div>
        </div>
      </div>
      <p className="mt-4 text-xs text-[#1a1814]/55 leading-relaxed">
        Trial Balance, the P&amp;L and the Balance Sheet are <b>hierarchical</b>: accounts roll up under
        their parent groups with subtotals, and you can expand/collapse any group and click a leaf line to
        drill into its ledger and on to the underlying voucher. Turn on <b>Compare</b> on the P&amp;L or
        Balance Sheet for a prior-period column. Every posted transaction carries a <b>voucher type</b>
        (Sales/Purchase/Receipt/Payment/Journal/Credit-Note/Debit-Note) feeding the Cash &amp; Bank Book.
      </p>
      <p className="mt-2 text-xs text-[#1a1814]/55 leading-relaxed">
        Two variants on the sales cycle: a <b>deferred-revenue</b> product posts <span className="font-mono">Dr A/R · Cr Deferred Revenue (2300)</span>
        and creates a recognition schedule that releases revenue over time; and a <b>posted invoice can be edited</b> (the
        original entries are reversed and re-posted) unless it is paid, in a locked period, or — for deferred invoices —
        already partly recognised.
      </p>
    </div>
  )
}

function InventoryFlow() {
  return (
    <div className="space-y-4 min-w-[500px]">
      {/* Purchase side */}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-orange-600 mb-2">Purchase (Stock In)</p>
        <HFlow>
          <StepBox
            title="Bill with Stock Product"
            impact="Product type = stock"
            accent="orange"
          />
          <Arrow />
          <StepBox
            title="Bill Saved / Posted"
            gl="Dr Inventory · Cr A/P"
            impact="Payable created"
            accent="gold"
          />
          <Arrow />
          <div className="bg-orange-100 border-2 border-orange-400 rounded-xl px-4 py-3">
            <p className="text-xs font-bold text-orange-800">stock_qty</p>
            <p className="font-mono text-sm text-orange-700 mt-0.5">+= qty</p>
            <p className="text-[10px] text-orange-600 mt-0.5">inventory increases</p>
          </div>
        </HFlow>
      </div>

      {/* Divider */}
      <div className="border-t border-dashed border-[#ede9e2]" />

      {/* Sales side */}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-green-600 mb-2">Sale (Stock Out)</p>
        <HFlow>
          <StepBox
            title="Invoice with Stock Product"
            impact="Product type = stock"
            accent="green"
          />
          <Arrow />
          <StepBox
            title="Invoice Saved / Posted"
            gl="Dr A/R · Cr Revenue"
            impact="Receivable created"
            accent="gold"
          />
          <Arrow />
          <div className="bg-green-100 border-2 border-green-400 rounded-xl px-4 py-3">
            <p className="text-xs font-bold text-green-800">stock_qty</p>
            <p className="font-mono text-sm text-green-700 mt-0.5">-= qty</p>
            <p className="text-[10px] text-green-600 mt-0.5">inventory decreases</p>
          </div>
        </HFlow>
      </div>

      {/* Warning callout */}
      <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 text-xs text-amber-800">
        <span className="font-bold">Low-stock alert:</span> When{" "}
        <span className="font-mono">stock_qty &lt;= reorder_level</span>, the dashboard flags the product.
        Service-type products skip inventory tracking entirely.
      </div>
    </div>
  )
}

function PaymentAllocationFlow() {
  return (
    <div className="space-y-4 min-w-[560px]">
      <HFlow>
        <StepBox title="One Payment" gl="amount = 1000" impact="cash received" accent="green" />
        <Arrow />
        <StepBox title="Allocations[]" impact="Split across invoices" accent="blue" />
        <Arrow />
        <div className="flex flex-col gap-2">
          <StepBox title="Invoice A" impact="300 of 800 → partial" accent="orange" small />
          <StepBox title="Invoice B" impact="500 of 500 → paid"    accent="teal"   small />
          <StepBox title="Invoice C" impact="200 of 1000 → partial" accent="orange" small />
        </div>
      </HFlow>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
        <div className="bg-[#faf6ec] border border-[#b8943f]/30 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#b8943f] mb-2">GL — single JV for the payment</p>
          <div className="space-y-1 font-mono text-xs text-[#1a1814]">
            <div className="flex justify-between">
              <span className="text-[#7a5c1e]">Dr Cash / Bank</span>
              <span className="text-[#1a1814]/60">+1,000</span>
            </div>
            <div className="flex justify-between pl-4">
              <span className="text-green-700">Cr Accounts Receivable</span>
              <span className="text-[#1a1814]/60">−1,000</span>
            </div>
          </div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-blue-700 mb-2">Derived status (per invoice)</p>
          <p className="text-xs text-blue-800 leading-relaxed">
            <span className="font-mono">allocated / total</span> {`<`} 1 → <strong>partial</strong>
            <br/>
            <span className="font-mono">allocated / total</span> ≥ 1 → <strong>paid</strong>
          </p>
        </div>
      </div>

      <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 text-xs text-amber-800">
        <span className="font-bold">Constraint:</span> sum(allocations) ≤ payment.amount.
        The dashboard and aging report use <strong>outstanding</strong> = total − sum(allocations) for each invoice.
      </div>
    </div>
  )
}

function CurrencyFlow() {
  return (
    <div className="space-y-4 min-w-[560px]">
      <HFlow>
        <StepBox title="Tenant base = USD" impact="reporting currency" accent="blue" />
        <Arrow />
        <StepBox title="Invoice in EUR" gl="subtotal = 1,000 EUR" impact="document currency stays EUR" accent="purple" />
        <Arrow />
        <StepBox title="FX lookup" gl="EUR → USD or 1/(USD → EUR)" impact="rate snapshot at issue date" accent="gold" />
        <Arrow />
        <StepBox title="JV posts in USD" gl="Dr AR 1,100 / Cr Rev 1,100" impact="reports stay consistent" accent="green" />
      </HFlow>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
        <div className="bg-purple-50 border border-purple-200 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-purple-700 mb-2">Document fields</p>
          <div className="font-mono text-[11px] text-purple-800 space-y-0.5">
            <p>currency      = &quot;EUR&quot;</p>
            <p>exchange_rate = 1.10</p>
            <p>subtotal      = 1,000 (EUR)</p>
            <p>total         = 1,000 (EUR)</p>
          </div>
        </div>
        <div className="bg-[#faf6ec] border border-[#b8943f]/30 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#b8943f] mb-2">GL (in base USD)</p>
          <div className="space-y-1 font-mono text-xs">
            <div className="flex justify-between text-[#7a5c1e]">
              <span>Dr Accounts Receivable</span><span>+1,100.00</span>
            </div>
            <div className="flex justify-between pl-4 text-green-700">
              <span>Cr Revenue</span><span>−1,100.00</span>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-xs text-blue-800">
        <span className="font-bold">Inverse fallback:</span> if only USD→EUR=0.91 is in the catalog,
        EUR→USD resolves automatically as 1/0.91 ≈ 1.10. You don&apos;t have to enter both directions.
      </div>
    </div>
  )
}

function PeriodCloseFlow() {
  return (
    <div className="space-y-4 min-w-[560px]">
      <HFlow>
        <StepBox title="Period open" impact="JVs post freely" accent="blue" />
        <Arrow />
        <StepBox title="Preview" gl="net income → Retained Earnings" impact="GET /periods/{id}/close-preview" accent="gold" />
        <Arrow />
        <StepBox title="Soft Close" impact="monthly/quarterly — lock + snapshot, P&L NOT zeroed" accent="teal" />
        <StepBox title="Year-End Close" gl="Rev/Exp → Retained Earnings" impact="annual — posts closing JV + lock" accent="purple" />
      </HFlow>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
        <div className="bg-teal-50 border border-teal-200 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-teal-700 mb-2">Soft Close (monthly / quarterly)</p>
          <p className="text-xs text-teal-800 leading-relaxed">
            Locks the period and snapshots balances. <strong>P&amp;L is not zeroed</strong>, so within-year
            income statements stay cumulative. Balance-sheet accounts carry forward live from the GL —
            no opening-balance journal.
          </p>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-xl px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-purple-700 mb-2">Year-End Close JV (example)</p>
          <div className="space-y-1 font-mono text-xs text-purple-800">
            <div className="flex justify-between"><span>Dr Sales Revenue</span><span>10,000</span></div>
            <div className="flex justify-between pl-4"><span>Cr Cost of Goods Sold</span><span>4,000</span></div>
            <div className="flex justify-between pl-4"><span>Cr General Expenses</span><span>1,000</span></div>
            <div className="flex justify-between pl-4"><span>Cr Retained Earnings</span><span>5,000</span></div>
          </div>
        </div>
      </div>

      <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 text-xs text-amber-800">
        <span className="font-bold">Reopen:</span> POST /periods/{`{id}`}/reopen unlocks and drops the snapshot.
        A year-end reopen also reverses the closing JV so Retained Earnings is restored.
      </div>
    </div>
  )
}

function ReversalFlow() {
  return (
    <div className="space-y-4 min-w-[560px]">
      <HFlow>
        <StepBox title="POST /transactions/{id}/reverse" impact="mirror JV created" accent="orange" />
        <Arrow />
        <StepBox title="Detect source doc" impact="Invoice · Bill · Payment · BillPayment" accent="blue" />
        <Arrow />
        <StepBox title="Unwind derived state" impact="see breakdown" accent="purple" />
        <Arrow />
        <StepBox title="Original linked" gl="is_reversed = true · reversed_by_id" accent="teal" />
      </HFlow>

      <div className="rounded-xl overflow-hidden border border-[#ede9e2] mt-2">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">If source is…</th>
              <th className="px-4 py-2.5 text-left">…the reverse handler also</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2] text-[11px]">
            <tr><td className="px-4 py-2 font-mono">PaymentReceived</td><td className="px-4 py-2 text-[#1a1814]/75">deletes its PaymentAllocations · recomputes each invoice&apos;s status</td></tr>
            <tr><td className="px-4 py-2 font-mono">BillPayment</td><td className="px-4 py-2 text-[#1a1814]/75">same on the AP side</td></tr>
            <tr><td className="px-4 py-2 font-mono">Invoice</td><td className="px-4 py-2 text-[#1a1814]/75">restores stock via reverse_consumption · auto-reverses the COGS sub-JV · sets invoice.status=&quot;void&quot;</td></tr>
            <tr><td className="px-4 py-2 font-mono">Bill</td><td className="px-4 py-2 text-[#1a1814]/75">drops the InventoryLayer · recomputes avg_cost · sets bill.status=&quot;void&quot;</td></tr>
            <tr><td className="px-4 py-2 font-mono">manual JV</td><td className="px-4 py-2 text-[#1a1814]/75">just mirrors the entries — no derived state</td></tr>
          </tbody>
        </table>
      </div>

      <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 text-xs text-amber-800">
        <span className="font-bold">No deletes:</span> the original is never removed. Double-reversal is rejected with 400.
      </div>
    </div>
  )
}

function DrillDownFlow() {
  return (
    <div className="space-y-4">
      <p className="text-xs text-[#1a1814]/65 leading-relaxed">
        Every code, JV number, document number, customer, vendor, and product rendered in the app
        is a clickable link to its source record. The shared <code className="font-mono text-[10px] bg-[#f6f3ee] border border-[#ede9e2] rounded px-1.5 py-0.5">&lt;DocLink /&gt;</code> resolver
        wires the cyclic graph below — there are no dead-end rows. This is what
        <b> ISA 230 §A6</b> calls <i>&quot;reperformability of the audit trail&quot;</i>.
      </p>

      <VFlow>
        <HFlow>
          <StepBox title="Trial Balance" accent="gold" impact="click code" />
          <StepBox title="/coa" accent="gold" impact="click code or name" small />
        </HFlow>
        <Arrow vertical />
        <StepBox title="Account Ledger (/ledger?account=…)" accent="blue" impact="running balance per JV" />
        <Arrow vertical />
        <StepBox title="JV Detail (/journal/{id})" accent="purple" impact="source_docs[] · reversed_by_id" />
        <Arrow vertical />
        <HFlow>
          <StepBox title="/invoices/{id}" accent="green" small />
          <StepBox title="/bills/{id}" accent="green" small />
          <StepBox title="/payments-received/{id}" accent="green" small />
          <StepBox title="/grn/{id}" accent="green" small />
        </HFlow>
        <Arrow vertical />
        <HFlow>
          <StepBox title="/customers/{id}/ledger" accent="teal" impact="AR sub-ledger (Dr − Cr)" />
          <StepBox title="/vendors/{id}/ledger" accent="teal" impact="AP sub-ledger (Cr − Dr)" />
          <StepBox title="/products/{id}/stock-card" accent="teal" impact="StockMovement-driven qty + value" />
        </HFlow>
      </VFlow>

      <div className="bg-[#faf6ec] border border-[#b8943f]/30 rounded-xl px-4 py-3 text-xs text-[#1a1814]/75 leading-relaxed">
        <b className="text-[#7a5c1e]">Best practice alignment.</b> Sub-ledgers fulfil
        <b> IAS 1.78(b)</b> &amp; <b>IFRS 7.7</b> (receivable / payable disclosure),
        the stock card fulfils <b>IAS 2.36(d)/(g)</b> (carrying amount + movements), and the cyclic drill-down satisfies
        <b> ISA 315.A82</b> (internal-control traceability). Corrections never delete — reverse the
        originating JV (<code className="font-mono text-[10px] bg-white border border-[#ede9e2] rounded px-1 py-0.5">POST /api/transactions/&#123;id&#125;/reverse</code>) and post the
        corrected entry. This is what <b>IAS 8.42</b> calls for.
      </div>
    </div>
  )
}

function ProductionOrderFlow() {
  return (
    <div className="space-y-4">
      <p className="text-xs text-[#1a1814]/65 leading-relaxed">
        Manufacturing tenants only. Each transition posts its own JV — easy to audit, easy to
        reverse one stage without disturbing the others. Customer-supplied components never
        touch your asset accounts; they live in memo accounts 1210 / 2150.
      </p>

      <VFlow>
        <StepBox
          title="GRN — Goods Receipt"
          accent="teal"
          impact="Customer drops off raw material at GODOWN. Optional declared_value posts memo JE."
          gl="Dr 1210 / Cr 2150  (memo)"
        />
        <StepBox
          title="Create Production Order"
          accent="gold"
          impact="State = DRAFT. References BoM + customer + rate plan + output_qty."
        />
        <StepBox
          title="START → consume components"
          accent="orange"
          impact="own_stock → WIP; customer_supplied → CUSTODIAL_ISSUE (no GL)."
          gl="Dr 1201 WIP / Cr 1200 Raw Material"
        />
        <StepBox
          title="COMPLETE → capitalise output"
          accent="blue"
          impact="WIP cost transfers to Finished Goods inventory at unit cost."
          gl="Dr 1202 FG / Cr 1201 WIP"
        />
        <StepBox
          title="DELIVER → ship to customer"
          accent="purple"
          impact="FG out at cost. Custodial memo balance released for fully-drained GRNs."
          gl="Dr 5010 COGS / Cr 1202 FG  +  Dr 2150 / Cr 1210"
        />
        <StepBox
          title="BILL → invoice via rate plan"
          accent="green"
          impact="per_unit_rate × qty + materials + overhead% + margin%. Creates Invoice row."
          gl="Dr 1100 AR / Cr 4010 Service Revenue (Value-Add)"
        />
      </VFlow>

      <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-xs text-blue-900 leading-relaxed">
        <span className="font-bold">Rate plan formula:</span> total = ((per_unit × qty + materials)
        × (1 + overhead%/100)) × (1 + margin%/100). Each component renders as its own line on the
        invoice so the customer sees exactly what they&apos;re paying for.
      </div>
    </div>
  )
}

function TelecomFranchiseFlow() {
  return (
    <div className="space-y-4">
      <p className="text-xs text-[#1a1814]/65 leading-relaxed">
        Telecom-franchise tenants only. Cash flows into a prepaid <b>Tracker</b> wallet, converts to
        spendable <b>load float</b> with a 3% uplift, then moves down a MSR → RSO → Retail chain.
        Each step posts its own balanced JV. The Tracker&apos;s deposit and load balances always
        reconcile to GL accounts 1210 and 1211.
      </p>

      <VFlow>
        <StepBox
          title="Tracker deposit"
          accent="teal"
          impact="Pre-fund the operator wallet with cash."
          gl="Dr 1210 Tracker Deposit / Cr 1010 Bank"
        />
        <StepBox
          title="Load order (3% uplift)"
          accent="gold"
          impact="Deposit converts to load float; operator credits 3% extra face value, booked as commission revenue at disbursement."
          gl="Dr 1211 (cash×1.03) / Cr 1210 (cash) / Cr 4020 (3%)"
        />
        <StepBox
          title="MSR → RSO → Retail"
          accent="orange"
          impact="Distribute float down the channel; each hop creates a receivable."
          gl="Dr 1212 / Cr 1211   then   Dr 1213 / Cr 1212"
        />
        <StepBox
          title="RSO daily collection"
          accent="blue"
          impact="RSO banks cash covering load + stock sold; any gap routes to overage (4900) or shortage (5070)."
          gl="Dr 1010 Bank / Cr 1212 (load) / Cr 1120 (stock) ± variance"
        />
        <StepBox
          title="SIM activation → commission"
          accent="purple"
          impact="Activate SIMs, then accrue operator commission as a receivable; cleared at statement settlement."
          gl="Dr 1110 Commission Rec. / Cr 4020 Revenue"
        />
        <StepBox
          title="FCA target / postpaid / franchise"
          accent="green"
          impact="Monthly FCA target pays 4060 (or penalty 5090); postpaid bill→collect→remit; franchise fee amortises to 5030, royalty to 5040."
          gl="Cr 4060 · Dr 2110/Cr Bank+4040 · Dr 5030/Cr 1301"
        />
      </VFlow>

      <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-xs text-blue-900 leading-relaxed">
        <span className="font-bold">FCA events are counted, not journalised</span> — only the monthly
        target settlement (commission or penalty) hits the GL. Mobile-money float moves <i>opposite</i>
        to cash: a customer deposit reduces float (Dr Cash / Cr 2100), a withdrawal increases it.
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

// ── New-module flows (Sprint 7–12 improvement roadmap) ───────────────────────

function CreditNoteFlow() {
  return (
    <div className="min-w-[480px]">
      <HFlow>
        <StepBox title="Issue Credit Note" impact="Return / adjustment / rebate" accent="gold" />
        <Arrow />
        <StepBox title="Link Invoice (opt.)" impact="CN-NNNN number assigned" accent="blue" />
        <Arrow />
        <StepBox title="Post Reversing JV" gl="Dr 4000 Revenue / Cr 1100 AR" impact="Reduces revenue + receivable" accent="green" />
        <Arrow />
        <StepBox title="AR Sub-Ledger" impact="Customer balance drops" accent="teal" />
      </HFlow>
      <p className="mt-4 text-xs text-[#1a1814]/55 leading-relaxed">
        Credit notes preserve the audit trail (ISA 240) — posted invoices are never edited; adjustments
        flow through a separate CN- document that posts the exact reverse entry.
      </p>
    </div>
  )
}

function FixedAssetFlow() {
  return (
    <div className="min-w-[480px]">
      <HFlow>
        <StepBox title="Register Asset" impact="Cost, salvage, useful life" accent="blue" />
        <Arrow />
        <StepBox title="Choose Method" impact="Straight-line / reducing-balance" accent="gold" />
        <Arrow />
        <StepBox title="Run Depreciation" gl="Dr 5050 Depr Exp / Cr 1090 Accum Depr" impact="Per period (IAS 16)" accent="green" />
        <Arrow />
        <StepBox title="Book Value Updates" impact="Stops at salvage value" accent="purple" />
      </HFlow>
    </div>
  )
}

function PurchaseOrderConvertFlow() {
  return (
    <div className="min-w-[480px]">
      <HFlow>
        <StepBox title="Raise PO" impact="PO-NNNN, vendor + lines" accent="gold" />
        <Arrow />
        <StepBox title="Approve" impact="Admin+ authorises" accent="blue" />
        <Arrow />
        <StepBox title="Goods Arrive" impact="Convert to Bill" accent="orange" />
        <Arrow />
        <StepBox title="Bill Posted" gl="Dr Expense / Cr 2000 AP" impact="BILL-NNNN linked to PO" accent="green" />
      </HFlow>
      <p className="mt-4 text-xs text-[#1a1814]/55 leading-relaxed">
        A lightweight 3-way-match control (IAS 2.11): the PO records intent, approval authorises spend,
        and conversion creates the payable only when goods are received.
      </p>
    </div>
  )
}

function DeferredRevenueFlow() {
  return (
    <div className="min-w-[480px]">
      <HFlow>
        <StepBox title="Invoice Deferred Item" gl="Dr 1100 AR / Cr 2300 Deferred Rev" impact="Cash up front, revenue held" accent="gold" />
        <Arrow />
        <StepBox title="Recognition Schedule" impact="Spread over N months" accent="blue" />
        <Arrow />
        <StepBox title="Run Recognition" gl="Dr 2300 Deferred Rev / Cr 4020 Revenue" impact="Per period (IFRS 15.31)" accent="green" />
        <Arrow />
        <StepBox title="Schedule Completes" impact="Fully recognised" accent="purple" />
      </HFlow>
    </div>
  )
}

function PurchaseReturnFlow() {
  return (
    <div className="min-w-[480px]">
      <HFlow>
        <StepBox title="Return goods" impact="Select vendor + original bill" accent="gold" />
        <Arrow />
        <StepBox title="Debit Note (DN-)" impact="Returned qty per line" accent="blue" />
        <Arrow />
        <StepBox title="Reduce stock" gl="at original layer cost" impact="Product.stock_qty falls" accent="orange" />
        <Arrow />
        <StepBox title="Post GL" gl="Dr 2000 AP / Cr 1200 Inv (+ Cr 1250 GST)" impact="Payable + inventory fall" accent="green" />
      </HFlow>
    </div>
  )
}

function CustomerAdvanceFlow() {
  return (
    <div className="min-w-[480px]">
      <HFlow>
        <StepBox title="Receive advance" gl="Dr Bank / Cr 2310 Customer Advances" impact="Prepayment (liability)" accent="gold" />
        <Arrow />
        <StepBox title="Invoice later" impact="Normal AR invoice" accent="blue" />
        <Arrow />
        <StepBox title="Apply advance" gl="Dr 2310 / Cr 1100 AR" impact="Invoice settled" accent="green" />
      </HFlow>
    </div>
  )
}

function VendorAdvanceFlow() {
  return (
    <div className="min-w-[480px]">
      <HFlow>
        <StepBox title="Pay advance" gl="Dr 1260 Advances to Vendors / Cr Bank" impact="Prepayment (asset)" accent="gold" />
        <Arrow />
        <StepBox title="Bill later" impact="Normal AP bill" accent="blue" />
        <Arrow />
        <StepBox title="Apply advance" gl="Dr 2000 AP / Cr 1260" impact="Bill settled" accent="green" />
      </HFlow>
    </div>
  )
}

function DashboardCustomizationFlow() {
  return (
    <div className="space-y-4 min-w-[480px]">
      <HFlow>
        <StepBox title="Dashboard" impact="Any screen size" accent="blue" />
        <Arrow />
        <StepBox title="Click Customize" impact="Edit mode activates" accent="gold" />
        <Arrow />
        <StepBox title="Drag / Resize widgets" impact="Reorder or resize any card" accent="purple" />
        <Arrow />
        <StepBox title="Add widget (optional)" impact="Pick from widget menu" accent="orange" />
        <Arrow />
        <StepBox title="Done" impact="Layout auto-saved" accent="green" />
      </HFlow>

      <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-xs text-blue-800 leading-relaxed">
        <span className="font-bold">Responsive breakpoints:</span> Desktop, tablet, and phone layouts are
        independent. Resize the browser window to the target width and click{" "}
        <span className="font-mono">Customize</span> — changes are saved for that breakpoint only.
        Switch between breakpoints to adjust each view separately.
      </div>
    </div>
  )
}

export default function WorkflowPage() {
  const { t } = useTranslation()

  const handlePrint = () => window.print()
  const [businessModel, setBusinessModel] = useState<BusinessModel | null>(null)

  // Fetch the tenant's business model so only the relevant cycles are shown.
  useEffect(() => {
    apiFetch<{ tenant?: { business_model?: BusinessModel } }>("/api/auth/me")
      .then(d => setBusinessModel(d.tenant?.business_model ?? "simple"))
      .catch(() => setBusinessModel("simple"))
  }, [])

  const isInventory = businessModel != null && INVENTORY_MODELS.includes(businessModel)
  const isManufacturing = businessModel === "manufacturing"
  const isTelecom = businessModel === "telecom_franchise"
  const isServices = businessModel === "services"

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-[#1a1814]/50 print:hidden">
        <Link href="/dashboard" className="hover:text-[#b8943f] transition-colors">Dashboard</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-[#1a1814]/80 font-medium">Transaction Workflow</span>
      </nav>

      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">
            Transaction Routing Workflow
          </h1>
          <p className="text-xs text-[#1a1814]/50 mt-0.5 font-medium tracking-wide uppercase">
            Double-entry accounting cycle reference
          </p>
        </div>
        <button
          onClick={handlePrint}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-[#ede9e2] rounded-xl text-sm text-[#1a1814]/70 hover:border-[#b8943f]/50 hover:text-[#b8943f] transition-all print:hidden shadow-sm self-start"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      {/* Double-Entry callout */}
      <DoubleEntryCallout />

      {/* 1 — Sales Cycle */}
      <SectionCard
        icon={GitBranch}
        title="Sales Cycle"
        subtitle="Accounts Receivable flow"
        iconColor="text-green-600"
      >
        <SalesCycleFlow />
      </SectionCard>

      {/* 2 — Purchase Cycle */}
      <SectionCard
        icon={RefreshCw}
        title="Purchase Cycle"
        subtitle="Accounts Payable flow"
        iconColor="text-orange-600"
      >
        <PurchaseCycleFlow />
      </SectionCard>

      {/* 3 — Manual Journal Entry */}
      <SectionCard
        icon={BookOpen}
        title="Manual Journal Entry"
        subtitle="Direct GL posting"
        iconColor="text-blue-600"
      >
        <ManualJournalFlow />
      </SectionCard>

      {/* 4 — Financial Statement Flow */}
      <SectionCard
        icon={BarChart3}
        title="Financial Statement Flow"
        subtitle="From GL to financial reports"
        iconColor="text-purple-600"
      >
        <FinancialStatementFlow />
      </SectionCard>

      {/* 5 — Inventory Flow (inventory-tracking models only) */}
      {isInventory && (
        <SectionCard
          icon={Package}
          title="Inventory Flow"
          subtitle="Weighted-average or FIFO cost (IAS 2)"
          iconColor="text-teal-600"
        >
          <InventoryFlow />
        </SectionCard>
      )}

      {/* 6 — Payment Allocations */}
      <SectionCard
        icon={CheckCircle}
        title="Payment Allocations"
        subtitle="One payment, many invoices, partial OK"
        iconColor="text-green-600"
      >
        <PaymentAllocationFlow />
      </SectionCard>

      {/* 7 — Multi-Currency */}
      <SectionCard
        icon={Globe}
        title="Multi-Currency Invoicing"
        subtitle="Document in EUR, GL in base currency"
        iconColor="text-blue-600"
      >
        <CurrencyFlow />
      </SectionCard>

      {/* 8 — Period Close */}
      <SectionCard
        icon={Calendar}
        title="Period-End Close"
        subtitle="Closing JV + materialised balances"
        iconColor="text-purple-600"
      >
        <PeriodCloseFlow />
      </SectionCard>

      {/* 9 — Reversal */}
      <SectionCard
        icon={RotateCcw}
        title="Reversal Mechanics"
        subtitle="Mirror JV + unwind of derived state"
        iconColor="text-orange-600"
      >
        <ReversalFlow />
      </SectionCard>

      {/* 10 — Drill-Down & Audit Trail */}
      <SectionCard
        icon={Link2}
        title="Drill-Down & Audit Trail"
        subtitle="Cyclic link graph from Trial Balance to source documents (ISA 230 / 315)"
        iconColor="text-teal-600"
      >
        <DrillDownFlow />
      </SectionCard>

      {/* 11 — Production Order Lifecycle (V2) — manufacturing only */}
      {isManufacturing && (
        <SectionCard
          icon={Factory}
          title="Production Order Lifecycle (V2)"
          subtitle="GRN → start → complete → deliver → bill"
          iconColor="text-pink-600"
        >
          <ProductionOrderFlow />
        </SectionCard>
      )}

      {/* 12 — Telecom Franchise Lifecycle (V3) — telecom only */}
      {isTelecom && (
        <SectionCard
          icon={Radio}
          title="Telecom Franchise Lifecycle (V3)"
          subtitle="Tracker deposit → load (3% uplift) → MSR→RSO→Retail → collect → activate → settle"
          iconColor="text-teal-600"
        >
          <TelecomFranchiseFlow />
        </SectionCard>
      )}

      {/* 13 — Credit Note flow (all models) */}
      <SectionCard
        icon={RefreshCw}
        title="Credit Note Flow"
        subtitle="Reverse a sale without editing the invoice (ISA 240)"
        iconColor="text-green-600"
      >
        <CreditNoteFlow />
      </SectionCard>

      {/* 14 — Fixed Asset Depreciation (all models) */}
      <SectionCard
        icon={Calendar}
        title="Fixed Asset Depreciation"
        subtitle="Systematic depreciation over useful life (IAS 16)"
        iconColor="text-purple-600"
      >
        <FixedAssetFlow />
      </SectionCard>

      {/* 15 — Purchase Order → Bill (inventory models) */}
      {isInventory && (
        <SectionCard
          icon={CheckCircle}
          title="Purchase Order → Bill"
          subtitle="Pre-approval and 3-way match (IAS 2.11)"
          iconColor="text-orange-600"
        >
          <PurchaseOrderConvertFlow />
        </SectionCard>
      )}

      {/* 16 — Deferred Revenue (services only) */}
      {isServices && (
        <SectionCard
          icon={Calendar}
          title="Deferred Revenue Recognition"
          subtitle="Recognise revenue as obligations are satisfied (IFRS 15)"
          iconColor="text-blue-600"
        >
          <DeferredRevenueFlow />
        </SectionCard>
      )}

      {/* 17 — Purchase Return (inventory models) */}
      {isInventory && (
        <SectionCard
          icon={Undo2}
          title="Purchase Return (Debit Note)"
          subtitle="Return goods to a vendor at original cost (IAS 2.11)"
          iconColor="text-orange-600"
        >
          <PurchaseReturnFlow />
        </SectionCard>
      )}

      {/* 18 — Customer Advance (all models) */}
      <SectionCard
        icon={Wallet}
        title="Customer Advance"
        subtitle="Prepayment received, applied to an invoice later"
        iconColor="text-green-600"
      >
        <CustomerAdvanceFlow />
      </SectionCard>

      {/* 19 — Vendor Advance (all models) */}
      <SectionCard
        icon={Wallet}
        title="Vendor Advance"
        subtitle="Prepayment paid, applied to a bill later"
        iconColor="text-orange-600"
      >
        <VendorAdvanceFlow />
      </SectionCard>

      {/* 20 — Dashboard Customization */}
      <SectionCard
        icon={LayoutDashboard}
        title="Dashboard Customization"
        subtitle="Drag, resize, and save your widget layout per breakpoint"
        iconColor="text-blue-600"
      >
        <DashboardCustomizationFlow />
      </SectionCard>

      {/* Footer note */}
      <div className="bg-[#f6f3ee] border border-[#ede9e2] rounded-xl px-5 py-4 text-xs text-[#1a1814]/60 leading-relaxed print:hidden">
        <span className="font-semibold text-[#b8943f]">Note:</span> All flows are processed automatically when you create invoices,
        bills, or payments. Manual journal entries give you direct access to the General Ledger for adjustments,
        accruals, and corrections. See the{" "}
        <Link href="/guide" className="text-[#b8943f] underline underline-offset-2 hover:text-[#7a5c1e]">User Guide</Link>
        {" "}for step-by-step instructions.
      </div>
    </div>
  )
}
