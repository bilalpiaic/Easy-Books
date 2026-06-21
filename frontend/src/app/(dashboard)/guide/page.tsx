"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"
import {
  ChevronRight, BookOpen, LogIn, BarChart3, FileSignature,
  Receipt, Package, PenLine, TrendingUp, Upload,
  AlertTriangle, CheckCircle, Info,
  Globe, Shield, Lock, Repeat, Landmark, Percent, Calendar, Users,
  Factory, Link2, Radio, Keyboard, ListChecks, LayoutDashboard,
} from "lucide-react"

// ── Tab definition ────────────────────────────────────────────────────────────

// Business models — used to tailor which guide sections each tenant sees.
type BusinessModel = "simple" | "services" | "trader" | "manufacturing" | "telecom_franchise"

interface Tab {
  id: string
  label: string
  icon: React.ElementType
  shortLabel: string
  /** If set, the tab only shows for these business models. Omitted = universal. */
  forModels?: BusinessModel[]
}

// Inventory-tracking models (stock, procurement, COGS apply)
const INVENTORY_MODELS: BusinessModel[] = ["trader", "manufacturing", "telecom_franchise"]

const TABS: Tab[] = [
  { id: "getting-started",  label: "Getting Started",        icon: LogIn,           shortLabel: "Start"    },
  { id: "dashboard",        label: "Dashboard Customization", icon: LayoutDashboard, shortLabel: "Dash"     },
  { id: "coa",              label: "Chart of Accounts",      icon: BarChart3,       shortLabel: "COA"      },
  { id: "invoicing",        label: "Invoicing",              icon: FileSignature,   shortLabel: "Invoices" },
  { id: "billing",          label: "Billing",                icon: Receipt,         shortLabel: "Bills"    },
  { id: "credit-notes",     label: "Credit Notes / Sales Returns", icon: Receipt,   shortLabel: "Credits"  },
  { id: "debit-notes",      label: "Purchase Returns",       icon: Receipt,         shortLabel: "Returns",  forModels: INVENTORY_MODELS },
  { id: "advances",         label: "Advances",               icon: TrendingUp,      shortLabel: "Advances" },
  { id: "products",         label: "Products & Inventory",   icon: Package,         shortLabel: "Products", forModels: INVENTORY_MODELS },
  { id: "purchase-orders",  label: "Purchase Orders",        icon: ListChecks,      shortLabel: "PO",       forModels: INVENTORY_MODELS },
  { id: "payments",         label: "Payments & Allocations", icon: CheckCircle,     shortLabel: "Pay"      },
  { id: "journal",          label: "Journal Entries",        icon: PenLine,         shortLabel: "Journal"  },
  { id: "analytic",         label: "Cost Centers",           icon: BarChart3,       shortLabel: "Analytic" },
  { id: "fixed-assets",     label: "Fixed Assets",           icon: Landmark,        shortLabel: "Assets"   },
  { id: "deferred-revenue", label: "Deferred Revenue",       icon: Calendar,        shortLabel: "Deferred", forModels: ["services"] },
  { id: "tax-codes",        label: "Tax Codes",              icon: Percent,         shortLabel: "Tax"      },
  { id: "currency",         label: "Multi-Currency",         icon: Globe,           shortLabel: "FX"       },
  { id: "budgets",          label: "Budgets",                icon: TrendingUp,      shortLabel: "Budget"   },
  { id: "recurring",        label: "Recurring Entries",      icon: Repeat,          shortLabel: "Recur"    },
  { id: "bank-imports",     label: "Bank Imports",           icon: Landmark,        shortLabel: "Bank"     },
  { id: "period-close",     label: "Period Close",           icon: Calendar,        shortLabel: "Close"    },
  { id: "roles",            label: "Roles & Access",         icon: Users,           shortLabel: "Roles"    },
  { id: "security",         label: "Security & CSRF",        icon: Shield,          shortLabel: "Sec"      },
  { id: "reports",          label: "Financial Reports",      icon: TrendingUp,      shortLabel: "Reports"  },
  { id: "sub-ledgers",      label: "Sub-Ledgers & Drill-Down", icon: Link2,         shortLabel: "Drill"    },
  { id: "csv",              label: "CSV Import",             icon: Upload,          shortLabel: "CSV"      },
  { id: "manufacturing",    label: "Manufacturing (V2)",     icon: Factory,         shortLabel: "Mfg",      forModels: ["manufacturing"] },
  { id: "telecom",          label: "Telecom Franchise (V3)",  icon: Radio,          shortLabel: "Telecom",  forModels: ["telecom_franchise"] },
  { id: "bulk-statements",  label: "Bulk Actions & Statements", icon: ListChecks,   shortLabel: "Bulk"     },
  { id: "tips-shortcuts",   label: "Tips & Shortcuts",        icon: Keyboard,       shortLabel: "Tips"     },
]

// ── Callout components ────────────────────────────────────────────────────────

function MistakeCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-3.5 flex gap-3 mt-4">
      <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
      <div>
        <p className="text-xs font-bold text-amber-800 mb-1 uppercase tracking-wide">Common Mistakes</p>
        <div className="text-xs text-amber-700 leading-relaxed space-y-1">{children}</div>
      </div>
    </div>
  )
}

function TipCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3.5 flex gap-3 mt-4">
      <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
      <div className="text-xs text-blue-700 leading-relaxed">{children}</div>
    </div>
  )
}

function StepList({ steps }: { steps: string[] }) {
  return (
    <ol className="space-y-2 mt-3">
      {steps.map((step, i) => (
        <li key={i} className="flex gap-3 text-sm text-[#1a1814]/80 leading-relaxed">
          <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[#b8943f] text-white text-[10px] font-bold flex items-center justify-center mt-0.5">
            {i + 1}
          </span>
          <span>{step}</span>
        </li>
      ))}
    </ol>
  )
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-bold uppercase tracking-widest text-[#b8943f] mt-5 mb-2 first:mt-0">
      {children}
    </h3>
  )
}

function CodeBadge({ children }: { children: React.ReactNode }) {
  return (
    <code className="font-mono text-[11px] bg-[#f6f3ee] border border-[#ede9e2] rounded px-1.5 py-0.5 text-[#1a1814]">
      {children}
    </code>
  )
}

// ── Tab content panels ────────────────────────────────────────────────────────

function GettingStartedPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Easy-Books is a double-entry accounting application. It records every transaction as
        two balanced journal entries — debits and credits — so your books always stay in balance.
        This guide walks you through the first steps to get up and running.
      </p>

      <SectionHeading>Sign Up — pick your business model</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        The signup page is a 2-step wizard. Step 1 asks for your <b>business model</b>; this
        controls which Chart of Accounts you start with and which UI sections are enabled.
      </p>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Model</th>
              <th className="px-4 py-2.5 text-left">Best for</th>
              <th className="px-4 py-2.5 text-left">Adds to base CoA</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["simple",        "Solo / micro-business",         "—"],
              ["services",      "Consulting, agencies",          "Consulting & recurring revenue, deferred revenue, subcontractor costs"],
              ["trader",        "Buy-and-resell goods",          "Finished Goods, COGS, Freight In, Storage, Inventory Adj."],
              ["manufacturing", "Value-addition on customer goods", "Raw Material / WIP / FG, memo pair 1210/2150, Direct Labour, Overhead, Service Revenue (Value-Add)"],
              ["telecom_franchise", "Mobile-operator franchise", "56-account franchise CoA: Tracker Deposit 1210, Load Float 1211, RSO/Retail receivables, MM float, SIM/device inventory, commission & FCA revenue, royalty & fee amortisation"],
            ].map(([model, use, extras]) => (
              <tr key={model} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-mono font-semibold text-[#b8943f]">{model}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{use}</td>
                <td className="px-4 py-2.5 text-[10px] text-[#1a1814]/60">{extras}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TipCallout>
        You can change the business model later via <CodeBadge>Settings → PATCH /api/settings/business-model</CodeBadge>;
        switching only <b>adds</b> any missing CoA accounts. It never deletes existing ones.
      </TipCallout>

      <SectionHeading>Login</SectionHeading>
      <StepList steps={[
        "Step 2 of signup is your email + password (≥ 8 chars) + full name + company name.",
        "On submit the system creates your tenant, seeds the CoA + stock locations + sequence counters, and logs you in as owner.",
        "Your session token is stored in localStorage AND set as an HttpOnly cookie. Both work side-by-side.",
      ]} />

      <SectionHeading>Company Setup</SectionHeading>
      <StepList steps={[
        "Go to Settings from the left sidebar.",
        "Confirm your company name, base currency, and fiscal year start date.",
        "Upload a company logo — drag-and-drop or click the logo zone. It appears on all printed documents.",
        "Fill in your address, phone, and website — these appear on printed invoices per IAS 1.49.",
        "Set up Payment Terms (Net 30, Net 15, etc.) so due dates calculate automatically on new invoices.",
        "If you picked manufacturing, you'll already have MAIN, GODOWN, and WIP stock locations seeded.",
      ]} />

      <SectionHeading>Onboarding Checklist</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        New tenants see a Setup Checklist card on the Dashboard. Complete each step to dismiss it:
      </p>
      <ul className="text-xs text-[#1a1814]/70 leading-relaxed space-y-1 mt-2 list-disc pl-5">
        <li><b>Logo uploaded</b> — Settings → Company Profile → logo zone</li>
        <li><b>Payment terms set</b> — Settings → Payment Terms → add at least one</li>
        <li><b>First invoice created</b> — Invoices → New Invoice</li>
        <li><b>Bank account added</b> — Banking → Bank Accounts → New Account</li>
        <li><b>Team member invited</b> — Settings → Team → Invite User</li>
      </ul>

      <SectionHeading>Your First Transaction</SectionHeading>
      <StepList steps={[
        "Add a few accounts beyond the seeded ones if needed (Chart of Accounts).",
        "Create at least one Customer (Receivable section) or Vendor (Payable section).",
        "Create an Invoice for a sale, or a Bill for a purchase.",
        "Manufacturing tenants: see the Manufacturing tab for the BoM → GRN → PO → bill flow.",
        "Use New Entry (Ledger section) for a direct journal entry whenever you need an adjustment.",
        "Check the Dashboard for KPIs and recent activity.",
      ]} />

      <TipCallout>
        <strong>Pro tip:</strong> The Workflow page (
        <Link href="/workflow" className="underline underline-offset-2 text-blue-600 hover:text-blue-800">
          Dashboard → Workflow
        </Link>
        ) is a visual reference of every accounting cycle — including the V2 production-order
        lifecycle. Print-friendly for handing to your bookkeeper.
      </TipCallout>

      <MistakeCallout>
        <p>Picking <CodeBadge>simple</CodeBadge> when you actually trade or manufacture — you can switch later, but starting with the right model gives you the right accounts up front.</p>
        <p>Skipping company setup — your logo and company name will be missing from all printed documents.</p>
        <p>Using the same account for both income and expense — always use separate account codes.</p>
      </MistakeCallout>
    </div>
  )
}

function CoaPanel() {
  const { t } = useTranslation()
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        The Chart of Accounts (COA) is the master list of every account used in your books.
        Each account belongs to one of five types, which determines how it behaves in reports
        and whether debits or credits increase its balance.
      </p>

      <SectionHeading>Account Types</SectionHeading>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Type</th>
              <th className="px-4 py-2.5 text-left">Normal Balance</th>
              <th className="px-4 py-2.5 text-left">Debit effect</th>
              <th className="px-4 py-2.5 text-left">Credit effect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["Asset",     "Debit",  "Increases ↑", "Decreases ↓"],
              ["Liability", "Credit", "Decreases ↓", "Increases ↑"],
              ["Equity",    "Credit", "Decreases ↓", "Increases ↑"],
              ["Revenue",   "Credit", "Decreases ↓", "Increases ↑"],
              ["Expense",   "Debit",  "Increases ↑", "Decreases ↓"],
            ].map(([type, normal, dr, cr]) => (
              <tr key={type} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-semibold text-[#1a1814]">{type}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/60">{normal}</td>
                <td className={`px-4 py-2.5 ${dr.includes("↑") ? "text-green-700" : "text-red-600"}`}>{dr}</td>
                <td className={`px-4 py-2.5 ${cr.includes("↑") ? "text-green-700" : "text-red-600"}`}>{cr}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>Account Codes</SectionHeading>
      <StepList steps={[
        "Use a numeric prefix to organise accounts: 1000s = Assets, 2000s = Liabilities, 3000s = Equity, 4000s = Revenue, 5000s+ = Expenses.",
        "Navigate to Chart of Accounts in the sidebar.",
        "Click Add Account, enter the code, name, and select the type.",
        "Sub-accounts can be created by using a parent account — e.g. 1010 Cash under 1000 Current Assets.",
        "Accounts cannot be deleted once they have transactions — deactivate them instead.",
      ]} />

      <SectionHeading>Per-Business-Model Templates</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Your CoA is seeded from a <b>common backbone</b> (13 accounts every tenant has) plus a
        <b> model-specific layer</b>. Switching business model later only <em>adds</em> missing
        accounts — it never deletes existing ones.
      </p>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Codes</th>
              <th className="px-4 py-2.5 text-left">Layer</th>
              <th className="px-4 py-2.5 text-left">{t('col.account', 'Account')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["1000–1100", "common",        "Cash, Bank, AR"],
              ["1200",      "trader / mfg",  "Finished Goods (trader) · Raw Material (mfg)"],
              ["1201",      "manufacturing", "Work-in-Progress"],
              ["1202",      "manufacturing", "Finished Goods"],
              ["1210",      "manufacturing", "Customer Goods on Hand (MEMO — off balance sheet)"],
              ["1250",      "trader / mfg",  "GST Receivable (Input)"],
              ["2000",      "common",        "Accounts Payable"],
              ["2150",      "manufacturing", "Customer Goods Liability (MEMO — pairs with 1210)"],
              ["2200",      "common",        "GST Payable (Output)"],
              ["2300",      "services",      "Deferred Revenue"],
              ["4000",      "common",        "Sales Revenue"],
              ["4010",      "services / mfg","Consulting Revenue (svc) · Service Revenue Value-Add (mfg)"],
              ["4020",      "services",      "Recurring Service Revenue"],
              ["5010",      "trader / mfg",  "Cost of Goods Sold"],
              ["5100–5210", "manufacturing", "Direct Labour, Subcontractor, Overhead, Indirect Materials"],
              ["1110",      "telecom",       "Commission Receivable"],
              ["1210 / 1211","telecom",      "Tracker Deposit · Load Float Asset (MSR)"],
              ["1212 / 1213","telecom",      "RSO · Retail Load Receivable"],
              ["1214",      "telecom",       "Mobile Money Float Asset"],
              ["4020 / 4060","telecom",      "Load Uplift Commission (3%) · FCA Target Commission"],
              ["5030 / 5040","telecom",      "Franchise Fee Amortisation · Royalty Expense"],
            ].map(([code, layer, name], i) => (
              <tr key={i} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-mono font-semibold text-[#b8943f]">{code}</td>
                <td className="px-4 py-2.5 text-[10px] text-[#1a1814]/55">{layer}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/80">{name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>Memo (Custodial) Accounts</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Accounts with <CodeBadge>is_memo=true</CodeBadge> are shown in a <b>separate
        Custodial section</b> of the Balance Sheet — they do not inflate your formal A=L+E
        totals. They are used to record items you hold in custody but do not own (e.g. a
        customer&apos;s raw material in your godown).
      </p>
      <ul className="text-xs text-[#1a1814]/70 leading-relaxed space-y-1 mt-2 list-disc pl-5">
        <li><CodeBadge>1210</CodeBadge> Customer Goods on Hand — debit balance, mirrors the qty/value of customer-owned material we hold.</li>
        <li><CodeBadge>2150</CodeBadge> Customer Goods Liability — credit balance, our obligation to return it.</li>
        <li>Posted by <CodeBadge>POST /api/grn</CodeBadge> when a non-zero <CodeBadge>declared_value</CodeBadge> is supplied.</li>
        <li>Released automatically on <CodeBadge>POST /api/production-orders/&#123;id&#125;/deliver</CodeBadge> when every layer of the source GRN is drained.</li>
      </ul>

      <SectionHeading>Best Practices</SectionHeading>
      <StepList steps={[
        "Keep code gaps between accounts (1000, 1010, 1020) so you can insert new accounts later.",
        "Use descriptive names: 'Trade Receivables' is clearer than 'AR'.",
        "Create a dedicated bank account code for each physical bank account.",
        "Separate Cost of Goods Sold (COGS) from operating expenses for accurate gross margin.",
        "Manufacturing tenants: keep 1210/2150 with is_memo=true — never untick that flag, or those balances will pollute your real balance sheet.",
      ]} />

      <MistakeCallout>
        <p>Using a single &apos;Sundry&apos; account for everything — this makes reports meaningless.</p>
        <p>Forgetting to create a bank account in COA before creating bank transactions.</p>
        <p>Mixing asset and expense accounts — e.g. posting equipment purchases to an expense account.</p>
        <p>Manually editing 1210 / 2150 from the COA UI — let the GRN / PO endpoints manage those balances.</p>
      </MistakeCallout>
    </div>
  )
}

function InvoicingPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Invoices record sales to customers. When you save an invoice, Easy-Books automatically
        posts <CodeBadge>Dr Accounts Receivable / Cr Revenue</CodeBadge> to the General Ledger,
        and reduces inventory for stock products.
      </p>

      <SectionHeading>Create an Invoice</SectionHeading>
      <StepList steps={[
        "Go to Invoices in the sidebar, then click New Invoice (or press N).",
        "Select a customer (or create one inline). Set the invoice date.",
        "Choose a Payment Term (Net 30, etc.) — the due date fills in automatically. You can still override it manually.",
        "Add line items: choose a product or type a description, enter quantity and unit price.",
        "Add a customer-facing Note (printed on invoice) or an internal memo (staff-only).",
        "Click Save. GL entries post immediately and the invoice is marked sent.",
      ]} />

      <SectionHeading>Editing an Invoice (draft or posted)</SectionHeading>
      <StepList steps={[
        "Click Edit in the toolbar to reopen the create modal pre-filled — this works for draft AND posted invoices.",
        "Change any field — lines, prices, dates, notes.",
        "Save. For a posted invoice the original GL entries are reversed and new ones re-posted automatically.",
        "Editing is blocked once a payment is allocated or the invoice's date falls in a locked period (use Reverse instead). If overselling protection is on, an edit that would drive stock negative is rejected.",
      ]} />

      <SectionHeading>Deferred-Revenue Products</SectionHeading>
      <StepList steps={[
        "On the product form, tick 'Deferred revenue' and set a recognition period (months) — for subscriptions/support/retainers.",
        "When you invoice that product, its amount posts to Deferred Revenue (2300) instead of Sales Revenue, and a recognition schedule is created.",
        "Open the Deferred Revenue screen to see schedules and run recognition — each run releases one period's revenue (Dr Deferred Revenue / Cr Revenue).",
        "Editing a deferred invoice rebuilds its schedule, but is blocked once any period has been recognised (void & reissue instead).",
      ]} />

      <SectionHeading>Receive a Payment</SectionHeading>
      <StepList steps={[
        "Open the invoice and click Receive Payment.",
        "Select the bank account the money was deposited into.",
        "Enter the payment date and amount (partial payments are supported).",
        "Save. The system posts Dr Bank / Cr Accounts Receivable.",
        "When the full amount is paid, the invoice is marked Paid automatically.",
      ]} />

      <SectionHeading>AR Aging</SectionHeading>
      <StepList steps={[
        "Navigate to Invoices and look at the status column — overdue invoices are highlighted.",
        "The Dashboard shows a count of overdue invoices for a quick overview.",
        "Use the date filter on the Invoices list to see invoices by period.",
        "Export to CSV for detailed aging analysis in a spreadsheet.",
      ]} />

      <TipCallout>
        Partial payments are supported. You can receive multiple payments against a single invoice.
        The outstanding balance updates in real time and the invoice remains open until fully paid.
      </TipCallout>

      <MistakeCallout>
        <p>Not setting a due date — the system cannot flag overdue invoices without one.</p>
        <p>Receiving payment against the wrong bank account — always verify the account before saving.</p>
        <p>Deleting a paid invoice — this orphans the payment record. Void it instead if needed.</p>
      </MistakeCallout>
    </div>
  )
}

function BillingPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Bills record purchases from vendors. Saving a bill posts{" "}
        <CodeBadge>Dr Expense or Inventory / Cr Accounts Payable</CodeBadge> and increases
        stock quantities for inventory products.
      </p>

      <SectionHeading>Create a Bill</SectionHeading>
      <StepList steps={[
        "Go to Bills in the sidebar, then click New Bill.",
        "Select a vendor (or create one inline). Enter the bill date and due date.",
        "Add line items: choose products or services, quantities, and unit costs.",
        "Add tax if the vendor charged VAT or sales tax.",
        "Click Save. The bill is recorded as a payable and GL is updated.",
      ]} />

      <SectionHeading>AP Tracking</SectionHeading>
      <StepList steps={[
        "The Bills list shows all open and paid bills with their outstanding amounts.",
        "The Dashboard AP Outstanding metric shows total unpaid bills.",
        "Filter by vendor or date range to review AP aging.",
        "Export to CSV for a detailed payables report.",
      ]} />

      <SectionHeading>Pay a Bill</SectionHeading>
      <StepList steps={[
        "Open the bill and click Make Payment.",
        "Select the bank account the payment was made from.",
        "Enter the payment date and amount (partial payments are supported).",
        "Save. The system posts Dr Accounts Payable / Cr Bank.",
        "The bill status changes to Paid once the full amount is settled.",
      ]} />

      <MistakeCallout>
        <p>Posting a bill to an expense account when the item is actually an asset (e.g. equipment) — use the correct asset account.</p>
        <p>Not entering a due date — you lose the ability to track upcoming payment obligations.</p>
        <p>Paying a bill twice by accident — always check the bill status before processing a payment.</p>
      </MistakeCallout>
    </div>
  )
}

function ProductsPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Products can be <strong>stock items</strong> (physical goods with inventory tracking) or{" "}
        <strong>services</strong> (no inventory tracking). Stock items automatically adjust
        quantity on hand when used in bills or invoices.
      </p>

      <SectionHeading>Stock vs Service Products</SectionHeading>
      <div className="grid sm:grid-cols-2 gap-3 mt-2">
        <div className="border-2 border-orange-300 bg-orange-50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Package className="w-4 h-4 text-orange-600" />
            <p className="text-xs font-bold text-orange-800">Stock Product</p>
          </div>
          <ul className="text-xs text-orange-700 space-y-1">
            <li>• Tracks quantity on hand</li>
            <li>• Bill → stock_qty increases</li>
            <li>• Invoice → stock_qty decreases</li>
            <li>• Triggers low-stock alerts</li>
            <li>• Has reorder level setting</li>
          </ul>
        </div>
        <div className="border-2 border-blue-300 bg-blue-50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-4 h-4 text-blue-600" />
            <p className="text-xs font-bold text-blue-800">Service Product</p>
          </div>
          <ul className="text-xs text-blue-700 space-y-1">
            <li>• No quantity tracking</li>
            <li>• Can be used on invoices and bills</li>
            <li>• No inventory GL posting</li>
            <li>• No reorder level needed</li>
            <li>• Ideal for labour, consulting, SaaS</li>
          </ul>
        </div>
      </div>

      <SectionHeading>Multi-Location Inventory (V2.2)</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Stock layers are keyed by <CodeBadge>(product, location)</CodeBadge> — the same product
        can live in multiple stores at different costs. Every tenant gets a <CodeBadge>MAIN</CodeBadge>
        store seeded at signup. Manufacturing tenants additionally get <CodeBadge>GODOWN</CodeBadge>
        (customer-custodial) and <CodeBadge>WIP</CodeBadge> (work-in-progress) out of the box.
      </p>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Type</th>
              <th className="px-4 py-2.5 text-left">Purpose</th>
              <th className="px-4 py-2.5 text-left">Ownership</th>
              <th className="px-4 py-2.5 text-left">Hits GL?</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["own",                "Manufacturer-owned stock (raw mat, FG, etc.)", "Yours",   "Yes — at WAvg cost"],
              ["customer_custodial", "Godown holding customer-supplied material",     "Customer", "Only the memo pair 1210/2150"],
              ["wip",                "Work-in-progress holding bucket",               "Yours",   "Yes — Dr 1201 WIP at start"],
            ].map(([type, purpose, owner, gl]) => (
              <tr key={type} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-mono font-semibold text-[#b8943f]">{type}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{purpose}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/60">{owner}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/60">{gl}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>Lot Tracking + Stock-Movement Log</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Every receipt / issue / completion / shipment writes one immutable row to
        <CodeBadge>StockMovement</CodeBadge>. The log is the source of truth; layers are a
        materialised projection over it.
      </p>
      <ul className="text-xs text-[#1a1814]/70 leading-relaxed space-y-1 mt-2 list-disc pl-5">
        <li><b>Direction values:</b> RECEIPT, CUSTODIAL_RECEIPT, ISSUE, CUSTODIAL_ISSUE, COMPLETION, CUSTODIAL_COMPLETION, DELIVERY, SHIPMENT, ADJUSTMENT.</li>
        <li><b>posted_to_gl:</b> false for purely custodial movements (customer goods); true for own-stock movements that have a journal entry attached.</li>
        <li><b>Lot number</b> flows from receipt → consumption to the linked movement and layer, so you can trace a finished output back to a specific raw lot.</li>
        <li><b>Read the log</b> at <CodeBadge>GET /api/stock-locations/movements</CodeBadge> with filters <CodeBadge>direction</CodeBadge>, <CodeBadge>product_id</CodeBadge>, <CodeBadge>location_id</CodeBadge>.</li>
      </ul>

      <SectionHeading>Reorder Levels</SectionHeading>
      <StepList steps={[
        "Open a stock product and set the Reorder Level field.",
        "When stock_qty falls at or below the reorder level, the item appears on the Dashboard under Low Stock.",
        "This is a visual alert only — no automatic purchase order is created.",
        "Use the Products list to view current stock levels across all items.",
        "For per-location stock visibility, use GET /api/stock-locations/{id}/stock.",
      ]} />

      <SectionHeading>CSV Import</SectionHeading>
      <StepList steps={[
        "On the Products page, click the CSV Import button.",
        "Download the sample CSV template to see the required columns.",
        "Required columns: name, product_type (stock/service), default_rate.",
        "Optional: description, reorder_level, opening_stock.",
        "Upload your CSV and review the preview before confirming the import.",
      ]} />

      <MistakeCallout>
        <p>Using service type for physical goods — stock levels will not be tracked.</p>
        <p>Setting a reorder level of 0 — all stock items will permanently show as low-stock.</p>
        <p>Importing products without a type column — the import will fail.</p>
        <p>Trying to consume from a customer_custodial location for an own-stock BoM line — the consume call will refuse; that location is reserved for customer-owned layers.</p>
      </MistakeCallout>
    </div>
  )
}

function JournalPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Manual journal entries give you direct access to the General Ledger. Use them for
        adjusting entries, accruals, depreciation, opening balances, and any correction that
        cannot be handled through invoices or bills.
      </p>

      <SectionHeading>Debit & Credit Rules</SectionHeading>
      <div className="bg-[#1a1814] rounded-xl p-4 mt-2">
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <p className="text-[#ffd966] font-bold mb-2 uppercase tracking-wide">Debit increases</p>
            <ul className="text-white/70 space-y-1">
              <li>• Assets (Cash, A/R, Inventory)</li>
              <li>• Expenses (Rent, Salaries)</li>
              <li>• Drawings / Dividends paid</li>
            </ul>
          </div>
          <div>
            <p className="text-[#ffd966] font-bold mb-2 uppercase tracking-wide">Credit increases</p>
            <ul className="text-white/70 space-y-1">
              <li>• Liabilities (A/P, Loans)</li>
              <li>• Equity (Capital, Retained Earnings)</li>
              <li>• Revenue (Sales, Service Income)</li>
            </ul>
          </div>
        </div>
      </div>

      <SectionHeading>Create a Manual Journal Entry</SectionHeading>
      <StepList steps={[
        "Go to New Entry from the sidebar.",
        "Enter the entry date, JV reference number, and a description.",
        "Add at least two lines. Each line needs: account, description, and either a debit or credit amount.",
        "The system shows a running Dr/Cr balance at the bottom. It must equal zero before you can save.",
        "Click Post Entry. The voucher is saved and all accounts are updated in real time.",
      ]} />

      <SectionHeading>Reversal Entries</SectionHeading>
      <StepList steps={[
        "Use POST /api/transactions/{id}/reverse — it posts a mirror JV automatically and links it via reversed_by_id.",
        "Reversal unwinds derived state: PaymentAllocations drop and invoice/bill statuses recompute; invoice stock-line consumption is restored; bill stock-line purchase peels back the inventory layer and recomputes avg_cost.",
        "A reversed transaction cannot be reversed again (request returns 400).",
        "Production-order stages currently DO NOT auto-reverse — to undo a started/completed PO you must call reverse on each underlying transaction in reverse order. Roadmap item.",
        "Check the Journal list to verify both the original and reversal entries appear correctly.",
      ]} />

      <TipCallout>
        <strong>Opening balances:</strong> Enter opening balances as a single journal entry on the first day of
        your fiscal year. Debit all asset accounts, credit all liability and equity accounts.
        The entry must balance (Dr = Cr) before the system accepts it.
      </TipCallout>

      <MistakeCallout>
        <p>Saving an unbalanced entry — the system prevents this, but always double-check your totals.</p>
        <p>Posting adjustments to the wrong period — always set the correct entry date, not today&apos;s date.</p>
        <p>Describing entries as just &quot;adjustment&quot; — use meaningful descriptions for auditability.</p>
      </MistakeCallout>
    </div>
  )
}

function ReportsPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        All financial reports are generated in real time from posted GL entries. Select a date range
        and the system aggregates all transactions in that period. Reports can be printed or exported to CSV.
      </p>

      <SectionHeading>Trial Balance</SectionHeading>
      <StepList steps={[
        "Go to Trial Balance from the sidebar.",
        "Select your reporting period using the date range picker.",
        "The report shows total debits and credits for every account, grouped under their parent accounts with rolled-up subtotals.",
        "The grand total row must show equal debits and credits — if not, there is a data entry error.",
        "Export to CSV for external reconciliation.",
      ]} />

      <SectionHeading>Hierarchical Statements & Drill-Down</SectionHeading>
      <StepList steps={[
        "Trial Balance, Balance Sheet, and P&L display as an expandable tree that mirrors your Chart of Accounts.",
        "Each group/parent row shows a subtotal rolled up from its children; click the ▸/▾ chevron to expand or collapse any group.",
        "Click a leaf-account line to drill straight into its ledger — and from a ledger row into the underlying voucher.",
        "On the Balance Sheet and P&L, turn on Compare to show a prior period side-by-side.",
      ]} />

      <SectionHeading>Income Statement (P&L)</SectionHeading>
      <StepList steps={[
        "Go to Income Statement from the Reports section.",
        "Set the date range for your reporting period (e.g. a fiscal year or quarter).",
        "The report shows: Revenue → Gross Profit → Operating Expenses → Net Profit/Loss.",
        "Compare across periods by changing the date range.",
      ]} />

      <SectionHeading>Balance Sheet</SectionHeading>
      <StepList steps={[
        "Go to Balance Sheet. Select the 'as of' date (usually year-end or month-end).",
        "The report shows Assets = Liabilities + Equity.",
        "Retained earnings include the current period net profit automatically.",
        "If the balance sheet does not balance, check for unposted or incorrectly coded entries.",
      ]} />

      <SectionHeading>Cash Flow Statement</SectionHeading>
      <StepList steps={[
        "Go to Cash Flow. Select your reporting period.",
        "Operating, Investing, and Financing activities are shown separately.",
        "The closing cash balance should agree to your bank account balance.",
        "Use this report to understand actual cash movements vs accrual-basis profit.",
      ]} />

      <SectionHeading>Tax Reports</SectionHeading>
      <StepList steps={[
        "Go to Tax Reports to see a summary of all tax collected and paid.",
        "The report breaks down input tax (on purchases) vs output tax (on sales).",
        "Net tax payable/receivable is calculated automatically.",
        "Use the CSV export for preparing your tax return.",
      ]} />

      <SectionHeading>Manufacturing Reports (V2.5)</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Available only to manufacturing tenants. Reachable from the Production Floor
        dashboard (<CodeBadge>/manufacturing</CodeBadge>) and via API.
      </p>
      <ul className="text-xs text-[#1a1814]/70 leading-relaxed space-y-1 mt-2 list-disc pl-5">
        <li><CodeBadge>GET /api/manufacturing/dashboard</CodeBadge> — pipeline counts by state + total WIP cost + total FG cost + custodial qty on hand.</li>
        <li><CodeBadge>GET /api/manufacturing/wip-aging</CodeBadge> — open POs (state=started) bucketed by days since start (<i>0-7d / 8-14d / 15-30d / 30d+</i>).</li>
        <li><CodeBadge>GET /api/manufacturing/production-summary</CodeBadge> — POs grouped by state with count + output_qty + cost. Accepts optional <CodeBadge>start</CodeBadge> + <CodeBadge>end</CodeBadge> date filters.</li>
        <li><CodeBadge>GET /api/manufacturing/customer-custody</CodeBadge> — per-(customer, product) summary of goods we hold custodially + unreleased declared value.</li>
      </ul>

      <SectionHeading>Memo Accounts on the Balance Sheet</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Accounts with <CodeBadge>is_memo=true</CodeBadge> (1210 / 2150) appear in a
        <b> separate Custodial section</b> at the bottom of the Balance Sheet — they don&apos;t
        affect the formal A=L+E totals. The qty and value they track is the customer&apos;s,
        not yours.
      </p>

      <MistakeCallout>
        <p>Running a P&amp;L without setting the correct date range — you may miss transactions or include wrong periods.</p>
        <p>Ignoring a non-balancing Balance Sheet — this always indicates a data problem that needs fixing.</p>
        <p>Relying on profit figures that include unpaid invoices — check Cash Flow for actual liquidity.</p>
        <p>Comparing custodial qty against your inventory totals — they&apos;re separate; custodial is the customer&apos;s, your inventory is yours.</p>
      </MistakeCallout>
    </div>
  )
}

function PaymentsPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        A single payment can settle multiple invoices (or bills) with partial amounts.
        The invoice <code className="font-mono text-[11px]">status</code> is derived from the
        total allocated against it — <strong>partial</strong> when some is paid,{" "}
        <strong>paid</strong> when fully covered. The dashboard and aging report both use
        the <em>outstanding</em> balance, never the gross.
      </p>

      <SectionHeading>Multi-Invoice Allocation Modal</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        The New Payment modal shows a table of all open invoices for the selected customer (or bills for a vendor). Each row shows Invoice#, Due Date, Total, Outstanding, and an editable <b>Amount to Apply</b> column.
      </p>
      <StepList steps={[
        "Go to Payments Received (or Bill Payments) and click New Payment.",
        "Select the customer/vendor. The allocation table populates with their open invoices/bills.",
        "Enter the gross payment amount at the top.",
        "In the allocation table, tick the invoices to settle and enter an amount for each.",
        "A running 'Total Applied vs Payment Amount' counter turns red if you over- or under-allocate.",
        "Save — GL posts, allocation rows are written, and each invoice status updates independently.",
      ]} />

      <SectionHeading>What the GL Looks Like</SectionHeading>
      <div className="bg-[#faf6ec] border border-[#ede9e2] rounded-xl p-3 font-mono text-[11px] text-[#1a1814]/85 leading-relaxed mt-2">
        Dr  1000 Cash in Hand       400.00<br/>
        &nbsp;&nbsp;&nbsp;&nbsp;Cr  1100 Accounts Receivable        400.00<br/>
        <span className="text-[#7a5c1e]">+ PaymentAllocation {`{`}invoice_id=INV-0042, amount=400.00{`}`}</span><br/>
        <span className="text-[#7a5c1e]">+ Invoice.status = &quot;partial&quot;  (400 paid of 1000 total)</span>
      </div>

      <TipCallout>
        <strong>Reversal:</strong> reversing the payment&apos;s JV (Transactions → Reverse)
        deletes the allocations and recomputes each invoice&apos;s status — no orphaned state.
      </TipCallout>

      <MistakeCallout>
        <p>Allocating more than the payment amount — the API will reject with 400.</p>
        <p>Forgetting to set an allocation — the payment posts but no invoice marks as paid.</p>
      </MistakeCallout>
    </div>
  )
}

function TaxCodesPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Tax codes decouple the rate from the document. Instead of hard-coding 17% on every
        invoice, you maintain a per-tenant catalog. When a tenant&apos;s standard rate changes,
        you edit the catalog; historical documents keep the rate they were issued with.
      </p>

      <SectionHeading>Creating a Tax Code</SectionHeading>
      <StepList steps={[
        "Go to Settings → Tax Codes.",
        "Enter a short code (e.g. GST17), a name (Standard GST 17%), and the rate (17).",
        "Choose type: output (sales tax — a liability) or input (purchase tax — receivable).",
        "Select the GL account where the tax leg posts (typically 2200 for output, 1250 for input).",
      ]} />

      <SectionHeading>Constraints</SectionHeading>
      <StepList steps={[
        "Code is unique per tenant — you cannot have two GST17 codes.",
        "Rate must be ≥ 0 (CHECK enforced at the database).",
        "Type must be either output or input — no other values accepted.",
      ]} />

      <MistakeCallout>
        <p>Using the same GL account for output and input GST — the tax summary will not net correctly.</p>
        <p>Editing a tax code rate retroactively expecting old invoices to change — they keep their snapshot.</p>
      </MistakeCallout>
    </div>
  )
}

function CurrencyPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Every tenant has a <strong>base currency</strong> — that&apos;s what your reports are in.
        Individual invoices and bills can be issued in a different currency; the system snapshots
        the exchange rate at issue time and posts the GL in base currency. Document totals on
        the invoice itself stay in the document currency.
      </p>

      <SectionHeading>Setting the Base Currency</SectionHeading>
      <StepList steps={[
        "Go to Settings → Company.",
        "Set base_currency to your reporting currency (e.g. USD, PKR, EUR).",
        "This is what the trial balance, P&L, balance sheet, and dashboard will show.",
      ]} />

      <SectionHeading>Maintaining Exchange Rates</SectionHeading>
      <StepList steps={[
        "Go to Settings → Exchange Rates.",
        "Add a rate entry: date, from_currency, to_currency, rate.",
        "You only need to enter rates when they CHANGE — lookups walk back to the most recent prior date.",
        "Lookups also resolve the inverse automatically: if you enter USD→EUR=0.91 and post an EUR invoice, the system uses 1/0.91 = ~1.10 to convert to USD.",
      ]} />

      <SectionHeading>Posting a Foreign-Currency Invoice</SectionHeading>
      <StepList steps={[
        "Create an invoice as usual.",
        "Set currency to the document currency (e.g. EUR).",
        "Leave exchange_rate blank to let the server resolve from the catalog, OR set it explicitly to override.",
        "The invoice document shows EUR amounts; the GL posts USD (or whatever your base is).",
      ]} />

      <div className="bg-[#faf6ec] border border-[#ede9e2] rounded-xl p-3 font-mono text-[11px] text-[#1a1814]/85 leading-relaxed mt-3">
        EUR invoice: subtotal=1000, exchange_rate=1.10, total=1000 (EUR)<br/>
        GL post (in base USD):<br/>
        Dr  1100 AR        1,100.00<br/>
        &nbsp;&nbsp;Cr  4000 Revenue   1,100.00
      </div>

      <MistakeCallout>
        <p>Forgetting to enter an exchange rate for a new currency — the invoice will return 400 with a clear message.</p>
        <p>Setting tenant base currency to a foreign code halfway through the year — your historical reports will look strange because old JVs posted in the old base.</p>
      </MistakeCallout>
    </div>
  )
}

function RecurringPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Recurring templates capture a journal-entry skeleton and a schedule. The{" "}
        <code className="font-mono text-[11px]">run-due</code> worker endpoint materialises
        a Transaction for every template whose next-run date has arrived and advances the
        schedule.
      </p>

      <SectionHeading>Creating a Template</SectionHeading>
      <StepList steps={[
        "Go to Accounting → Recurring in the sidebar (or press N on that page).",
        "Click Create Recurring.",
        "Name it (e.g. Monthly office rent) and choose frequency: daily, weekly, monthly, quarterly, or yearly.",
        "Set next run date — the first date it should fire.",
        "Add GL line items in the entries table — both debit and credit totals must match.",
        "Save. The template appears in the list as active.",
      ]} />

      <SectionHeading>Running Due Templates</SectionHeading>
      <StepList steps={[
        "Open Recurring → Run Due (or POST /api/recurring/run-due).",
        "Every template whose next_run is on or before today posts a Transaction with today’s date in the JV description.",
        "After firing, last_run = previous next_run, and next_run advances by the frequency.",
        "Running twice on the same day is idempotent — the second call finds no due templates.",
      ]} />

      <TipCallout>
        <strong>Day-of-month clamping:</strong> a monthly template scheduled for the 31st
        falls back to the last day of the target month (Feb 28/29). No template ever
        skips a month because its day-of-month doesn&apos;t exist.
      </TipCallout>

      <MistakeCallout>
        <p>Forgetting to set is_active=true on production templates — they will never fire.</p>
        <p>Editing a template after it has fired — past JVs keep the old amounts; only future cycles use the new ones.</p>
      </MistakeCallout>
    </div>
  )
}

function BankImportsPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Bank statement import lets you reconcile your books against the bank&apos;s record.
        Upload a CSV from your bank, the system parses each line and tries to match it to
        an existing journal entry. Anything that doesn&apos;t auto-match is left for manual review.
      </p>

      <SectionHeading>CSV Format</SectionHeading>
      <div className="bg-[#faf6ec] border border-[#ede9e2] rounded-xl p-3 font-mono text-[11px] text-[#1a1814]/85 leading-relaxed mt-2">
        date,description,debit,credit,balance<br/>
        2026-05-02,Customer payment Alice,0,500,1500<br/>
        2026-05-03,Stripe payout,0,1000,2500<br/>
        2026-05-04,Office rent,200,0,2300
      </div>
      <p className="text-xs text-[#1a1814]/55 mt-2 leading-relaxed">
        <strong>debit</strong> = money leaving the account (e.g. paying a vendor).{" "}
        <strong>credit</strong> = money arriving (e.g. customer payment). Either column can be blank.
      </p>

      <SectionHeading>Importing</SectionHeading>
      <StepList steps={[
        "Go to Banking → Imports → New Import.",
        "Choose the bank account this statement belongs to.",
        "Upload the CSV. Server computes a SHA-256 hash — re-uploading the exact same file returns 409 to prevent duplicate lines.",
        "After upload, each line becomes a StatementLine row, unmatched.",
      ]} />

      <SectionHeading>Auto-Match</SectionHeading>
      <StepList steps={[
        "Click Auto-Match on the import page.",
        "For each unmatched line, the system finds Transactions whose JV total equals the line amount within a ±3-day window.",
        "If exactly one candidate matches, the line is linked. Multiple candidates leave the line unmatched for review.",
        "Lines auto-matched in OTHER imports don't prevent matching here (each import is scored independently).",
      ]} />

      <MistakeCallout>
        <p>Uploading a non-UTF-8 CSV — the server returns 400. Save as UTF-8 in Excel or Sheets.</p>
        <p>Expecting auto-match to handle bank fees or multi-line splits — set those manually via the line PATCH endpoint.</p>
      </MistakeCallout>
    </div>
  )
}

function PeriodClosePanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        The <strong>Period Close</strong> page (Reports → Period Close) closes accounting periods at the
        cadence you need. Create a period with the <strong>Monthly</strong>, <strong>Quarterly</strong>,
        or <strong>Fiscal-Year</strong> presets, then choose how to close it. Closing snapshots per-account
        balances into <code className="font-mono text-[11px]">AccountBalance</code> rows so trial-balance
        reads against the closed period stay fast.
      </p>

      <SectionHeading>Two close modes (IAS 1)</SectionHeading>
      <StepList steps={[
        "Soft Close (monthly / quarterly): locks the period and snapshots balances, but does NOT zero P&L. Within-year income statements stay cumulative and comparable. Use for management period-ends.",
        "Year-End Close: posts the closing JV — Dr Revenue / Cr Expense / Cr-or-Dr Retained Earnings (net income → 3100) — then locks. Use only at fiscal year-end.",
        "Preview first: the page shows the net income that will roll into Retained Earnings before you commit.",
      ]} />

      <SectionHeading>Carry-forward</SectionHeading>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Balance-sheet (permanent) accounts <strong>carry forward automatically</strong> — Easy-Books computes
        every balance live from the all-time ledger, so the next period opens at the prior closing balance.
        No opening-balance journal is posted.
      </p>

      <SectionHeading>Reopening</SectionHeading>
      <StepList steps={[
        "Reopen unlocks the period and deletes its AccountBalance snapshot; reads aggregate live again.",
        "A year-end reopen also reverses the closing JV so Retained Earnings is restored.",
      ]} />

      <TipCallout>
        <strong>Backdating into a closed period?</strong> The central posting service refuses with 400 —
        the period-lock check runs before any DB write, for both soft and year-end closes.
      </TipCallout>

      <MistakeCallout>
        <p>Running a Year-End Close monthly — that zeroes P&L every month and breaks within-year comparatives. Use Soft Close for sub-annual periods.</p>
        <p>Closing before month-end adjustments are posted — you&apos;d have to reopen to fix it.</p>
      </MistakeCallout>
    </div>
  )
}

function RolesPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Easy-Books uses role-based access control. Every user has one of four roles. The first
        user of a tenant is automatically the <strong>owner</strong>; the owner can invite or
        promote other users.
      </p>

      <SectionHeading>Role Matrix</SectionHeading>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Role</th>
              <th className="px-4 py-2.5 text-left">Read reports</th>
              <th className="px-4 py-2.5 text-left">Post JVs / docs</th>
              <th className="px-4 py-2.5 text-left">Close period</th>
              <th className="px-4 py-2.5 text-left">Delete accounts</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["viewer",     "✔", "—", "—", "—"],
              ["accountant", "✔", "✔", "—", "—"],
              ["admin",      "✔", "✔", "✔", "✔"],
              ["owner",      "✔", "✔", "✔", "✔"],
            ].map(([role, r, w, c, d]) => (
              <tr key={role} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-semibold text-[#1a1814] font-mono">{role}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{r}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{w}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{c}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{d}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>Behaviour</SectionHeading>
      <StepList steps={[
        "A viewer trying to POST/PUT/PATCH/DELETE anything → 403 with a clear message.",
        "Accountants can do day-to-day work — invoices, bills, payments, manual JVs — but cannot close periods or delete accounts.",
        "Period close, account delete, and managing users require admin or owner.",
        "Roles are stored in the JWT; a role change applies on the user's next request/login.",
      ]} />

      <SectionHeading>Managing your team</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Admins and owners get a <CodeBadge>Team</CodeBadge> page (under <b>System</b> in the sidebar) to run a
        multi-user organisation. Two ways to onboard a colleague:
      </p>
      <StepList steps={[
        "Create account — add their email, name and role; the page shows a one-time temporary password to relay. They're forced to set a new password at first login.",
        "Send invite — generate a tokenized link (valid 7 days) and share it; the recipient sets their own name and password at /accept-invite.",
        "Assign roles inline, reset a password, or activate/deactivate a member. Deactivating locks them out instantly — even a still-valid session stops working.",
      ]} />

      <SectionHeading>Your profile</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Every user has a <CodeBadge>My Profile</CodeBadge> page to edit their name &amp; phone, change their
        password, upload an avatar, and review their role, organisation, join date and last login.
      </p>

      <MistakeCallout>
        <p>Promoting too many users to admin — you lose the audit-of-actions benefit of restricted access.</p>
        <p>You can&apos;t change your own role or deactivate yourself — ask another admin/owner.</p>
        <p>The last active owner is protected: you can&apos;t demote or deactivate the only owner, so a tenant is never locked out of its admin surface.</p>
      </MistakeCallout>
    </div>
  )
}

function SecurityPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Easy-Books layers several protections so the wrong request can&apos;t do damage. Most are
        invisible if you use the app normally; this panel explains them so integrators know what
        to expect.
      </p>

      <SectionHeading>Authentication</SectionHeading>
      <StepList steps={[
        "Login (OAuth2 password form) returns a JWT bearer token AND sets an HttpOnly access cookie.",
        "Browser SPA uses the cookie automatically (credentials: 'include').",
        "SDKs / mobile / curl can use the bearer token directly via the Authorization header.",
        "Both paths coexist — backend tries Bearer first, then cookie.",
      ]} />

      <SectionHeading>CSRF Protection</SectionHeading>
      <StepList steps={[
        "When you log in, a second non-HttpOnly cookie eb_csrf is set (and the same value is returned in the login response).",
        "Any mutating POST/PUT/PATCH/DELETE authenticated by cookie MUST echo eb_csrf as the X-CSRF-Token header.",
        "Missing or mismatched header → 403.",
        "Bearer-header callers are exempt — the auth header itself proves intent.",
      ]} />

      <SectionHeading>Login Throttle</SectionHeading>
      <StepList steps={[
        "10 attempts per IP per 60-second rolling window.",
        "11th attempt → 429 (Too Many Requests).",
        "State lives in the database, so multiple uvicorn workers share the same counter.",
      ]} />

      <SectionHeading>Idempotency Keys</SectionHeading>
      <StepList steps={[
        "Send any mutating request with an Idempotency-Key header.",
        "If the same key has been seen for this tenant before, the cached response body is returned with Idempotency-Replay: true.",
        "Use this on flaky networks to make POSTs safely retryable.",
      ]} />

      <TipCallout>
        <strong>Why two cookies?</strong> The HttpOnly access cookie keeps the JWT out of
        JavaScript&apos;s reach. The non-HttpOnly CSRF cookie is readable by JavaScript so the SPA
        can echo it back as a header — a header an attacker on another origin cannot set.
      </TipCallout>

      <MistakeCallout>
        <p>Forgetting credentials: &apos;include&apos; on browser fetches — the access cookie won&apos;t be sent and you&apos;ll get 401.</p>
        <p>Sending the CSRF token in the body instead of the X-CSRF-Token header — the middleware only reads the header.</p>
      </MistakeCallout>
    </div>
  )
}

function CsvImportPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Easy-Books supports CSV import for bulk-loading master data and transactions.
        Each entity type has its own required column set. Always download the sample template
        from the import dialog before preparing your file.
      </p>

      <SectionHeading>Supported Entities</SectionHeading>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Entity</th>
              <th className="px-4 py-2.5 text-left">Where to import</th>
              <th className="px-4 py-2.5 text-left">Required fields</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["Transactions", "Journal page",      "date, description, account_code, debit, credit"],
              ["Accounts",     "Chart of Accounts", "code, name, type · optional: parent_code, is_group, is_memo"],
              ["Products",     "Products page",     "name, product_type, default_rate · optional: category_name, is_deferred"],
              ["Customers",    "Customers page",    "name · optional: email, phone, opening_balance"],
              ["Vendors",      "Vendors page",      "name · optional: email, phone, opening_balance"],
            ].map(([entity, where, fields]) => (
              <tr key={entity} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-semibold text-[#1a1814]">{entity}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/60">{where}</td>
                <td className="px-4 py-2.5 font-mono text-[10px] text-[#b8943f]">{fields}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>How to Import</SectionHeading>
      <StepList steps={[
        "Navigate to the relevant page (e.g. Products).",
        "Click the CSV Import button in the top-right action area.",
        "Download the sample template CSV to see the exact column headers and format.",
        "Fill in your data, keeping the header row exactly as shown.",
        "Upload your file. The system shows a row count and any validation errors.",
        "Fix any flagged errors and re-upload. Confirmed rows are imported immediately.",
      ]} />

      <SectionHeading>Common Errors</SectionHeading>
      <div className="space-y-2 mt-2">
        {[
          { code: "Missing column",         fix: "Check that all required column headers are present, using exact spelling and case." },
          { code: "Duplicate code/email",   fix: "Each account code and customer/vendor email must be unique. Remove duplicates from your CSV." },
          { code: "Invalid type value",     fix: "For Products, type must be exactly 'stock' or 'service' (lowercase)." },
          { code: "Non-numeric price",      fix: "default_rate must be a plain number (e.g. 1500.00) — no currency symbols or commas." },
          { code: "Empty required field",   fix: "Every required field must have a value. Blank cells in required columns cause row-level failures." },
        ].map(({ code, fix }) => (
          <div key={code} className="flex gap-3 items-start">
            <CodeBadge>{code}</CodeBadge>
            <p className="text-xs text-[#1a1814]/70 leading-relaxed mt-0.5">{fix}</p>
          </div>
        ))}
      </div>

      <MistakeCallout>
        <p>Editing the template header row — even a single typo in a column name will cause the entire import to fail.</p>
        <p>Using Excel and saving as .xlsx instead of .csv — the importer only accepts comma-separated text files.</p>
        <p>Including a currency symbol in numeric fields — strip all formatting, use plain numbers only.</p>
      </MistakeCallout>
    </div>
  )
}

function SubLedgersPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        The General Ledger answers <i>&quot;what is the balance of account X?&quot;</i>. Sub-ledgers answer
        <i> &quot;which customer / vendor / product caused that balance, and which document booked it?&quot;</i>.
        Easy-Books wires three sub-ledgers and a cyclic drill-down link graph on top of the GL —
        click any account code, JV number, invoice/bill number, customer, vendor or product
        anywhere in the app and you land on its source record.
      </p>

      <SectionHeading>The three sub-ledgers</SectionHeading>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Sub-ledger</th>
              <th className="px-4 py-2.5 text-left">Endpoint</th>
              <th className="px-4 py-2.5 text-left">Page</th>
              <th className="px-4 py-2.5 text-left">Running balance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            <tr className="hover:bg-[#faf8f4]">
              <td className="px-4 py-2.5 font-semibold">Customer AR (debit-normal)</td>
              <td className="px-4 py-2.5 font-mono text-[10px] text-[#1a1814]/70"><CodeBadge>GET /api/customers/&#123;id&#125;/ledger</CodeBadge></td>
              <td className="px-4 py-2.5 font-mono text-[10px] text-[#b8943f]"><Link href="/customers" className="underline">/customers/[id]/ledger</Link></td>
              <td className="px-4 py-2.5">Σ Dr − Σ Cr (positive = owes you)</td>
            </tr>
            <tr className="hover:bg-[#faf8f4]">
              <td className="px-4 py-2.5 font-semibold">Vendor AP (credit-normal)</td>
              <td className="px-4 py-2.5 font-mono text-[10px] text-[#1a1814]/70"><CodeBadge>GET /api/vendors/&#123;id&#125;/ledger</CodeBadge></td>
              <td className="px-4 py-2.5 font-mono text-[10px] text-[#b8943f]"><Link href="/vendors" className="underline">/vendors/[id]/ledger</Link></td>
              <td className="px-4 py-2.5">Σ Cr − Σ Dr (positive = you owe)</td>
            </tr>
            <tr className="hover:bg-[#faf8f4]">
              <td className="px-4 py-2.5 font-semibold">Product stock card</td>
              <td className="px-4 py-2.5 font-mono text-[10px] text-[#1a1814]/70"><CodeBadge>GET /api/products/&#123;id&#125;/stock-card</CodeBadge></td>
              <td className="px-4 py-2.5 font-mono text-[10px] text-[#b8943f]"><Link href="/products" className="underline">/products/[id]/stock-card</Link></td>
              <td className="px-4 py-2.5">Σ qty_in − Σ qty_out + value @ WAvg</td>
            </tr>
          </tbody>
        </table>
      </div>

      <SectionHeading>The cyclic drill-down graph</SectionHeading>
      <pre className="mt-2 bg-[#faf6ec] border border-[#ede9e2] rounded-xl p-3 text-[11px] leading-relaxed text-[#1a1814]/80 overflow-x-auto">
{`Trial Balance ──▶ click code ──▶ Account Ledger
                                       │
                                       │ click JV no.
                                       ▼
                                  JV Detail (/journal/{id})
                                       │
                                source_docs[]   reversed_by_id
                                       │              │
                                       ▼              ▼
                  /invoices/{id}, /bills/{id}, /grn/{id}, ...
                                       │
                                       │ click party
                                       ▼
                       /customers/{id}/ledger
                       /vendors/{id}/ledger
                                       │
                                       └── click any JV ─▶ back to JV Detail
                                       └── click product ─▶ /products/{id}/stock-card`}
      </pre>

      <SectionHeading>Source-document resolution on any JV</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        <CodeBadge>GET /api/transactions/&#123;id&#125;</CodeBadge> now returns a
        <CodeBadge>source_docs[]</CodeBadge> array — the API reverse-resolves which Invoice / Bill
        / Payment / GRN posted this JV, plus <CodeBadge>is_reversed</CodeBadge> and
        <CodeBadge>reversed_by_id</CodeBadge>. The JV detail page renders these as one-click links
        — there is no orphan JV in the system.
      </p>

      <SectionHeading>Best practice — accounting standards alignment</SectionHeading>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Need</th>
              <th className="px-4 py-2.5 text-left">Standard</th>
              <th className="px-4 py-2.5 text-left">How Easy-Books satisfies it</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["Audit reperformability",        "ISA 230 §A6",      "source_docs[] + reversed_by_id"],
              ["Internal control traceability", "ISA 315.A82",      "Cyclic link graph — every node has in & out links"],
              ["Consistency of presentation",   "IAS 1.45",         "Single <DocLink> resolver = single URL convention"],
              ["Receivable / payable disclosure","IFRS 7.7 / IAS 1.78(b)","Customer & vendor sub-ledgers with full period activity"],
              ["Inventory carrying amount + movement","IAS 2.36(d)/(g)","Stock card driven by StockMovement event log"],
              ["Change history",                "ISA 240 / SOC 2 CC7.3","AuditLog row per mutation"],
            ].map(([need, std, how]) => (
              <tr key={need} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-semibold text-[#1a1814]">{need}</td>
                <td className="px-4 py-2.5 font-mono text-[10px] text-[#b8943f]">{std}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{how}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <TipCallout>
        <b>Drill-down is the audit trail.</b> If an external auditor asks <i>&quot;why is AR ₹5.4 L?&quot;</i>,
        open Trial Balance → click <code>1100 Accounts Receivable</code> → see every JV → click any
        JV → click <code>source_docs[0]</code> → see the originating invoice with lines, customer,
        and tax. No spreadsheet, no separate report, no copy-paste — reperformability is built in.
      </TipCallout>

      <MistakeCallout>
        <p>Treating <CodeBadge>Product.stock_qty</CodeBadge> as the source of truth — it&apos;s a projection. The <CodeBadge>StockMovement</CodeBadge> event log is canonical; the stock card derives from it.</p>
        <p>Editing a sub-ledger directly — you can&apos;t. Sub-ledgers are read-only views. To change a balance, reverse the originating JV (<CodeBadge>POST /api/transactions/&#123;id&#125;/reverse</CodeBadge>) and post a corrected one. This is what <b>IAS 8.42</b> calls for.</p>
        <p>Skipping the source-doc click on JV detail — every JV that <i>can</i> be traced should be traced before posting a correction. Reversing a JV that was already used to allocate a payment cascades — read §5.7 of WORKFLOW.md.</p>
      </MistakeCallout>
    </div>
  )
}

function ManufacturingPanel() {
  const { t } = useTranslation()
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        The manufacturing track is enabled when you pick <CodeBadge>manufacturing</CodeBadge> as
        your business model at signup. It adds custodial intake of customer-supplied material,
        Bills of Material, value-addition rate plans, and a full production-order lifecycle —
        all wired to the same double-entry GL.
      </p>

      <SectionHeading>The 5-step lifecycle</SectionHeading>
      <StepList steps={[
        "GRN (Goods Receipt) — record customer-supplied material into the GODOWN. Optional declared_value posts a memo JE (Dr 1210 / Cr 2150).",
        "Bills of Material — define the recipe per output product. Each component is own_stock (your raw material) or customer_supplied (consumed from a GODOWN lot).",
        "Rate Plan — set your per-unit value-add charge with optional materials passthrough, overhead %, and margin %. Assign one active plan per customer.",
        "Production Order — created in DRAFT. POST /api/production-orders with bom_id, customer_id, output_qty. Auto-resolves the customer's active rate plan.",
        "Walk it through: start → complete → deliver → bill. Each transition is its own JV — easy to audit and reverse independently.",
      ]} />

      <SectionHeading>Journal entries by stage</SectionHeading>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Stage</th>
              <th className="px-4 py-2.5 text-left">{t('col.debit', 'Debit')}</th>
              <th className="px-4 py-2.5 text-left">{t('col.credit', 'Credit')}</th>
              <th className="px-4 py-2.5 text-left">Movement</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["GRN (with declared value)", "1210 Customer Goods on Hand", "2150 Customer Goods Liab.", "CUSTODIAL_RECEIPT"],
              ["start (own_stock)",         "1201 WIP",                    "1200 Raw Material",         "ISSUE"],
              ["start (customer_supplied)", "—",                           "—",                         "CUSTODIAL_ISSUE"],
              ["complete",                  "1202 Finished Goods",         "1201 WIP",                  "COMPLETION"],
              ["deliver (FG)",              "5010 COGS",                   "1202 Finished Goods",       "DELIVERY"],
              ["deliver (memo release)",    "2150 Customer Goods Liab.",   "1210 Customer Goods on Hand","—"],
              ["bill",                      "1100 AR",                     "4010 Service Revenue",      "—"],
            ].map(([stage, dr, cr, mv]) => (
              <tr key={stage} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-semibold text-[#1a1814]">{stage}</td>
                <td className="px-4 py-2.5 font-mono text-[10px] text-[#1a1814]/70">{dr}</td>
                <td className="px-4 py-2.5 font-mono text-[10px] text-[#1a1814]/70">{cr}</td>
                <td className="px-4 py-2.5 font-mono text-[10px] text-[#b8943f]">{mv}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>Rate plan formula</SectionHeading>
      <pre className="mt-2 bg-[#faf6ec] border border-[#ede9e2] rounded-xl p-3 text-[11px] leading-relaxed text-[#1a1814]/80 overflow-x-auto">
{`base       = per_unit_rate × output_qty
if includes_materials_at_cost:
  base    += own_material_cost           (your consumables, at WAvg)
overhead   = base × overhead_pct / 100
subtotal   = base + overhead
margin     = subtotal × margin_pct / 100
total      = subtotal + margin            (excl. GST)`}
      </pre>

      <TipCallout>
        <b>Customer goods never touch your asset accounts.</b> They live in a custodial
        InventoryLayer (owner_customer_id set, unit_cost=0) and — if you supplied a declared
        value — in the memo pair 1210/2150 (excluded from formal A=L+E totals). Memo balance
        releases only when <i>every</i> layer of a GRN has been drained.
      </TipCallout>

      <MistakeCallout>
        <p>Skipping stages — every transition has a required predecessor (e.g. you can&apos;t bill until delivered). Use the one-click button on the Production Orders page.</p>
        <p>Editing a BoM in-place — that breaks reconstructability. Post a <i>new version</i> instead (the prior version auto-deactivates).</p>
        <p>Reassigning a rate plan to a customer expecting both to stay active — the old assignment auto-deactivates. History is preserved at <CodeBadge>/api/rate-plans/customer/&#123;id&#125;</CodeBadge>.</p>
      </MistakeCallout>

      <SectionHeading>Manufacturing reports</SectionHeading>
      <ul className="text-xs text-[#1a1814]/70 leading-relaxed space-y-1.5 mt-2 list-disc pl-5">
        <li><b>Dashboard</b> — pipeline counts by state, total WIP/FG cost, custodial qty on hand.</li>
        <li><b>WIP aging</b> — open POs (state=started) bucketed by days since start.</li>
        <li><b>Production summary</b> — POs grouped by state with output_qty and cost totals.</li>
        <li><b>Customer custody</b> — per-(customer, product) on-hand qty + unreleased declared value.</li>
      </ul>
    </div>
  )
}

function TelecomFranchisePanel() {
  const { t } = useTranslation()
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        The telecom-franchise track is enabled when you pick <CodeBadge>telecom_franchise</CodeBadge> as
        your business model at signup. It models a mobile-operator franchise end-to-end: a prepaid
        <b> Tracker</b> wallet, load distribution down a <b>MSR → RSO → Retail</b> chain, SIM
        activations, monthly <b>FCA</b> targets, a mobile-money agency, postpaid billing,
        commission reconciliation, and franchise-fee amortisation — all on the same double-entry GL.
      </p>

      <SectionHeading>The daily operating loop</SectionHeading>
      <StepList steps={[
        "Fund the Tracker — deposit cash with the operator (Dr 1210 / Cr Bank), then place a load order. The operator credits 3% more face value than the cash you spend; the uplift books as commission revenue at disbursement.",
        "Procure stock — a tracker stock-debit pulls SIM/IMSI inventory (Dr 1200 / Cr 1210) and auto-creates a SIM batch.",
        "Distribute load — push float MSR → RSO (Dr 1212 / Cr 1211), then RSO → Retail (Dr 1213 / Cr 1212). Each hop is a receivable.",
        "Collect daily — each RSO banks cash covering load + stock sold; any gap posts to overage/shortage so balances reconcile.",
        "Sell & activate — counter sales post sale + COGS; activations log the customer and accrue the operator commission as a receivable (1110).",
        "Hit FCA targets — first-call activations are counted toward a monthly target; hitting it pays a commission (4060), missing it can trigger a penalty (5090).",
        "Reconcile — settle the operator's commission statement against 1110; run mobile-money and postpaid; amortise the franchise fee and pay royalty.",
      ]} />

      <SectionHeading>Key journal entries</SectionHeading>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Operation</th>
              <th className="px-4 py-2.5 text-left">{t('col.debit', 'Debit')}</th>
              <th className="px-4 py-2.5 text-left">{t('col.credit', 'Credit')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["Tracker deposit",        "1210 Tracker Deposit",     "1010 Bank"],
              ["Load order (3% uplift)", "1211 Load Float ×1.03",    "1210 (cash) + 4020 (3%)"],
              ["SIM stock debit",        "1200 SIM Inventory",       "1210 Tracker Deposit"],
              ["MSR → RSO transfer",     "1212 RSO Load Rec.",       "1211 Load Float"],
              ["RSO → Retail transfer",  "1213 Retail Load Rec.",    "1212 RSO Load Rec."],
              ["RSO daily collection",   "1010 Bank",                "1212 + 1120 (± variance)"],
              ["Commission accrual",     "1110 Commission Rec.",     "4020 / 4010 Revenue"],
              ["FCA target commission",  "1210 Tracker / Bank",      "4060 FCA Target Commission"],
              ["MM customer deposit",    "1000 Cash",                "2100 MM Float Liability"],
              ["Postpaid bill",          "1130 Postpaid Cust Rec.",  "2110 Collections Payable"],
              ["Postpaid remittance",    "2110 Collections Payable", "Bank (net) + 4040 (commission)"],
              ["Fee amortisation",       "5030 Fee Amortisation",    "1301 Accum. Amortisation"],
            ].map(([op, dr, cr]) => (
              <tr key={op} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-semibold text-[#1a1814]">{op}</td>
                <td className="px-4 py-2.5 font-mono text-[10px] text-[#1a1814]/70">{dr}</td>
                <td className="px-4 py-2.5 font-mono text-[10px] text-[#1a1814]/70">{cr}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>The 3% load uplift</SectionHeading>
      <pre className="mt-2 bg-[#faf6ec] border border-[#ede9e2] rounded-xl p-3 text-[11px] leading-relaxed text-[#1a1814]/80 overflow-x-auto">
{`Dr 1211 Load Float Asset      cash × 1.03
   Cr 1210 Tracker Deposit        cash
   Cr 4020 Load Uplift Commission cash × 0.03`}
      </pre>

      <TipCallout>
        <b>Two balances always reconcile to the GL:</b> the Tracker account&apos;s
        <CodeBadge>deposit_balance</CodeBadge> equals account 1210, and its
        <CodeBadge>load_balance</CodeBadge> equals account 1211. The Tracker Statement report shows
        both the denormalised figure and the live GL figure side by side.
      </TipCallout>

      <MistakeCallout>
        <p>Treating FCA events as journal entries — they are <i>counted</i>, not posted. Only the monthly target commission/penalty hits the GL.</p>
        <p>Forgetting mobile-money float moves <i>opposite</i> to cash: a customer deposit reduces your float, a withdrawal increases it.</p>
        <p>Recording a load order larger than the available Tracker deposit — the posting is rejected until you top up the wallet.</p>
      </MistakeCallout>

      <SectionHeading>Telecom reports</SectionHeading>
      <ul className="text-xs text-[#1a1814]/70 leading-relaxed space-y-1.5 mt-2 list-disc pl-5">
        <li><b>Dashboard</b> — tracker & load positions, commission receivable, RSO, MM float, SIM utilisation, FCA month progress.</li>
        <li><b>RSO ledger</b> — per-RSO load in/out, cash collected, open balance.</li>
        <li><b>Float statement</b> — mobile-money system balance vs GL 1214.</li>
        <li><b>Commission aging, SIM utilisation, postpaid book, revenue-by-stream, FCA target, tracker statement</b>.</li>
      </ul>
    </div>
  )
}

function BulkStatementsPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Bulk actions let you update many records at once. Customer and vendor statements give
        counterparties a period summary of their account standing, ready to print or email.
      </p>

      <SectionHeading>Bulk Actions on List Pages</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Every list page (Invoices, Bills, Customers, Vendors, Products) has a checkbox column.
        Select rows and a floating <b>Bulk Action Bar</b> appears at the bottom of the screen.
      </p>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Page</th>
              <th className="px-4 py-2.5 text-left">Available actions</th>
              <th className="px-4 py-2.5 text-left">Guard</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["Invoices", "Mark as Sent, Void, Delete", "Delete only for draft; Void sets status=void without GL reversal"],
              ["Bills", "Mark as Received, Void, Delete", "Same guards as invoices"],
              ["Customers", "Delete", "No outstanding balance"],
              ["Vendors", "Delete", "No outstanding balance"],
              ["Products", "Delete", "Zero stock qty"],
            ].map(([page, actions, guard]) => (
              <tr key={page} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-semibold text-[#1a1814]">{page}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{actions}</td>
                <td className="px-4 py-2.5 text-[10px] text-[#1a1814]/55">{guard}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>Customer Statement</SectionHeading>
      <StepList steps={[
        "Open a customer's ledger page (Customers → [name] → View Ledger).",
        "Click Print Statement in the toolbar.",
        "Set the date range (defaults to current year).",
        "The statement shows: opening balance, invoices billed in period, payments received, closing balance.",
        "Click Print to send to the browser print dialog (save as PDF from there).",
      ]} />

      <SectionHeading>Vendor Statement</SectionHeading>
      <StepList steps={[
        "Open a vendor's ledger page (Vendors → [name] → View Ledger).",
        "Click Print Statement in the toolbar.",
        "Set the date range.",
        "The statement shows: opening balance, bills received in period, payments made, closing balance.",
        "Closing balance > 0 means you still owe the vendor.",
      ]} />

      <TipCallout>
        Statements are point-in-time snapshots — the date range only filters which documents
        appear in the body. The opening balance is computed from all activity <em>before</em> the
        from-date, so the numbers always reconcile with the ledger.
      </TipCallout>

      <MistakeCallout>
        <p>Bulk-voiding an invoice that was already paid — the GL entries stay; only the status changes. Use Reverse on the payment first if you need to fully unwind.</p>
        <p>Bulk-deleting draft invoices that are part of a recurring template — the template still fires next cycle and creates new ones.</p>
      </MistakeCallout>
    </div>
  )
}

function TipsShortcutsPanel() {
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        Quick tips to work faster in Easy-Books — keyboard shortcuts, list-page features,
        and document-number customisation.
      </p>

      <SectionHeading>Keyboard Shortcuts</SectionHeading>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Key</th>
              <th className="px-4 py-2.5 text-left">Action</th>
              <th className="px-4 py-2.5 text-left">Works on</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["N", "Open New / Create modal", "Invoices, Bills, Customers, Vendors, Products, Journal, Bank Accounts"],
              ["Esc", "Close the currently open modal", "All modals"],
            ].map(([key, action, where]) => (
              <tr key={key} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5"><code className="font-mono text-[11px] bg-[#f6f3ee] border border-[#ede9e2] rounded px-1.5 py-0.5">{key}</code></td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{action}</td>
                <td className="px-4 py-2.5 text-[10px] text-[#1a1814]/55">{where}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TipCallout>
        The <code className="font-mono text-[11px]">N</code> shortcut is suppressed when focus is inside a text input, textarea, or select — so you can type without triggering it.
      </TipCallout>

      <SectionHeading>Document Number Format</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Go to <b>Settings → Document Numbers</b> to customise the invoice and bill number format.
        Supported tokens:
      </p>
      <div className="mt-2 rounded-xl overflow-hidden border border-[#ede9e2]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f6f3ee] text-[10px] font-bold uppercase tracking-wider text-[#1a1814]/60">
              <th className="px-4 py-2.5 text-left">Token</th>
              <th className="px-4 py-2.5 text-left">Meaning</th>
              <th className="px-4 py-2.5 text-left">Example</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#ede9e2]">
            {[
              ["{prefix}",         "The prefix you set (INV, BILL, etc.)", "INV"],
              ["{seq:04d}",        "4-digit zero-padded sequence number",  "0042"],
              ["{YYYY}",           "4-digit year",                         "2026"],
              ["{MM}",             "2-digit month",                        "05"],
            ].map(([token, meaning, example]) => (
              <tr key={token} className="hover:bg-[#faf8f4]">
                <td className="px-4 py-2.5 font-mono text-[#b8943f]">{token}</td>
                <td className="px-4 py-2.5 text-[#1a1814]/70">{meaning}</td>
                <td className="px-4 py-2.5 font-mono text-[#1a1814]/55">{example}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-[#1a1814]/65 mt-2">
        Example format: <code className="font-mono text-[11px] bg-[#f6f3ee] border border-[#ede9e2] rounded px-1.5 py-0.5">INV-{"{YYYY}"}-{"{seq:04d}"}</code> → <b>INV-2026-0001</b>
      </p>

      <SectionHeading>Sorting & Filtering Lists</SectionHeading>
      <StepList steps={[
        "Click any column header with an arrow icon to sort ascending or descending.",
        "Use the filter bar above the list to combine status, date range, and search filters.",
        "Filters and sort are applied together — e.g. all overdue invoices sorted by amount.",
        "Low-stock products: Dashboard → Low Stock tile links directly to Products filtered by low_stock=true.",
      ]} />

      <SectionHeading>Breadcrumb Navigation</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Every detail page (invoice, bill, customer ledger, etc.) shows a breadcrumb nav at the top:
      </p>
      <div className="bg-[#faf6ec] border border-[#ede9e2] rounded-xl p-3 font-mono text-[11px] text-[#1a1814]/85 mt-2">
        Invoices › INV-2026-0042
      </div>
      <p className="text-xs text-[#1a1814]/55 mt-1.5">
        Clicking the parent segment always goes to the list page — even if you navigated directly via a URL.
      </p>

      <SectionHeading>Notes & Internal Memos</SectionHeading>
      <StepList steps={[
        "When creating or editing an invoice or bill, expand the Notes section at the bottom of the form.",
        "Customer Note — printed on the document; visible to the customer.",
        "Internal Memo — shown only to users with accountant role or higher; never printed.",
        "Both fields are optional and can be edited on draft documents.",
      ]} />

      <MistakeCallout>
        <p>Using the internal memo for customer-facing information — it is hidden on the print layout.</p>
        <p>Resetting document number sequences manually — the sequence counter is per-tenant and auto-increments; editing it directly can cause duplicate numbers.</p>
      </MistakeCallout>
    </div>
  )
}

// ── Returns & Advances panels (Sprint 13) ────────────────────────────────────

function DebitNotesPanel() {
  return (
    <div className="space-y-3 text-sm text-[#1a1814]/80 leading-relaxed">
      <SectionHeading>Purchase Returns (Debit Notes)</SectionHeading>
      <p>
        When you return goods to a vendor, a Debit Note reverses the purchase: it reduces what you owe
        the vendor and removes the stock at its original cost (<strong>IAS 2.11</strong>).
      </p>
      <StepList steps={[
        "Go to Debit Notes (Payable section) → New Debit Note",
        "Select the vendor, then the original bill the goods came from",
        "Enter the returned quantity per line (and any GST to reverse)",
        "Post — a DN-NNNN is created and the GL posts automatically",
      ]} />
      <SectionHeading>GL Posting</SectionHeading>
      <p>
        Dr <CodeBadge>2000 Accounts Payable</CodeBadge> / Cr <CodeBadge>1200 Inventory</CodeBadge>
        (at the original layer cost) + Cr <CodeBadge>1250 GST Input</CodeBadge>. Stock quantity drops
        by the returned amount.
      </p>
      <TipCallout>
        The return draws from the original bill&apos;s inventory layer, so it must still hold enough
        un-sold quantity — otherwise the post is rejected with a clear message.
      </TipCallout>
    </div>
  )
}

function AdvancesPanel() {
  return (
    <div className="space-y-3 text-sm text-[#1a1814]/80 leading-relaxed">
      <SectionHeading>Customer & Vendor Advances</SectionHeading>
      <p>
        Advances are prepayments — cash that moves before an invoice or bill exists. Record the advance,
        then apply it against a document later; the application settles the invoice/bill through the
        normal payment-allocation flow.
      </p>
      <SectionHeading>From Customers (prepayment received)</SectionHeading>
      <StepList steps={[
        "Advances → From Customers → Record Customer Advance (Dr Bank / Cr 2310 Customer Advances)",
        "Later, click Apply to invoice — Dr 2310 / Cr Accounts Receivable settles the invoice",
      ]} />
      <SectionHeading>To Vendors (prepayment paid)</SectionHeading>
      <StepList steps={[
        "Advances → To Vendors → Record Vendor Advance (Dr 1260 Advances to Vendors / Cr Bank)",
        "Later, click Apply to bill — Dr Accounts Payable / Cr 1260 settles the bill",
      ]} />
      <TipCallout>
        Each advance tracks its remaining balance, so you can apply it across several documents until
        it is fully used.
      </TipCallout>
    </div>
  )
}

// ── New-module panels (Sprint 7–12 improvement roadmap) ──────────────────────

function CreditNotesPanel() {
  return (
    <div className="space-y-3 text-sm text-[#1a1814]/80 leading-relaxed">
      <SectionHeading>What Credit Notes Do</SectionHeading>
      <p>
        A credit note reduces what a customer owes you — for returns, price adjustments, or rebates.
        Instead of editing a posted invoice (which would break your audit trail), you issue a credit
        note that posts its own reversing entry. This satisfies <strong>ISA 240</strong> document integrity.
      </p>
      <StepList steps={[
        "Go to Credit Notes → New Credit Note (in the Receivable section)",
        "Select the customer, and optionally link the original invoice",
        "Enter the reason (e.g. 'Return — defective goods') and line items",
        "Issue — a CN-NNNN number is assigned and the GL posts automatically",
      ]} />
      <SectionHeading>GL Posting</SectionHeading>
      <p>
        Dr <CodeBadge>4000 Sales Revenue</CodeBadge> / Cr <CodeBadge>1100 Accounts Receivable</CodeBadge> —
        the exact reverse of an invoice, reducing both revenue and the receivable balance.
      </p>
      <TipCallout>
        Credit notes use a separate <CodeBadge>CN-</CodeBadge> number sequence so they never clash with
        invoice numbers and stay easy to spot in the AR sub-ledger.
      </TipCallout>
    </div>
  )
}

function PurchaseOrdersPanel() {
  return (
    <div className="space-y-3 text-sm text-[#1a1814]/80 leading-relaxed">
      <SectionHeading>Purchase Order Workflow</SectionHeading>
      <p>
        Purchase orders add a pre-approval step before money is committed. Raise a PO, get it approved,
        then convert it to a bill once goods arrive — a lightweight 3-way-match control (<strong>IAS 2.11</strong>).
      </p>
      <StepList steps={[
        "Go to Purchase Orders → New Purchase Order",
        "Select the vendor and add line items (product, qty, rate)",
        "Save as draft, then Approve (admin+) once authorised",
        "When goods arrive, click Convert to Bill — a BILL-NNNN is created and the GL posts Dr Expense / Cr Accounts Payable",
      ]} />
      <TipCallout>
        Purchase orders are shown for Trader, Manufacturing, and Telecom Franchise models — the ones that
        routinely procure stock or devices.
      </TipCallout>
    </div>
  )
}

function AnalyticPanel() {
  return (
    <div className="space-y-3 text-sm text-[#1a1814]/80 leading-relaxed">
      <SectionHeading>Cost Centers, Projects & Departments</SectionHeading>
      <p>
        Analytic accounts are an optional second dimension you can tag onto journal lines, invoice lines,
        and bill lines — letting you report profitability by department, project, or region without
        cluttering your Chart of Accounts (<strong>IAS 1</strong> management commentary).
      </p>
      <StepList steps={[
        "Go to Analytic Accounts and create dimensions (e.g. 'North Region', 'Project Alpha')",
        "When posting a journal entry or invoice, tag the relevant line with an analytic account",
        "Open Reports → Analytic P&L and pick a dimension to see revenue and expenses for just that segment",
      ]} />
      <TipCallout>
        Analytic tagging is always optional — existing workflows are unaffected if you never use it.
      </TipCallout>
    </div>
  )
}

function FixedAssetsPanel() {
  return (
    <div className="space-y-3 text-sm text-[#1a1814]/80 leading-relaxed">
      <SectionHeading>Fixed Asset Register & Depreciation</SectionHeading>
      <p>
        Track long-lived assets (laptops, vehicles, machinery) and depreciate them systematically over
        their useful life per <strong>IAS 16</strong>. Easy-Books supports straight-line and reducing-balance methods.
      </p>
      <StepList steps={[
        "Go to Fixed Assets → New Asset",
        "Enter cost, salvage value, useful life (months), and depreciation method",
        "Pick the asset, accumulated-depreciation (1090), and depreciation-expense (5050) GL accounts",
        "Each period, click Run Depreciation — it posts Dr 5050 Depreciation Expense / Cr 1090 Accumulated Depreciation",
      ]} />
      <TipCallout>
        Book value is recalculated after every run and depreciation stops automatically once the asset
        reaches its salvage value.
      </TipCallout>
    </div>
  )
}

function DeferredRevenuePanel() {
  return (
    <div className="space-y-3 text-sm text-[#1a1814]/80 leading-relaxed">
      <SectionHeading>Deferred Revenue Recognition (IFRS 15)</SectionHeading>
      <p>
        When you invoice a customer for a service delivered over time (e.g. an annual support contract),
        the cash arrives up front but the revenue must be recognised as you satisfy the obligation.
        Deferred revenue schedules automate this (<strong>IFRS 15.31</strong>).
      </p>
      <StepList steps={[
        "Flag a product as deferred (with a recognition period in months)",
        "Invoicing that product posts to Deferred Revenue (2300) instead of Revenue",
        "Each period, run recognition — it moves a slice from Dr 2300 Deferred Revenue / Cr Revenue",
        "View active schedules and their recognised-to-date balances under Deferred Revenue",
      ]} />
      <TipCallout>
        This section applies to the Services model, where subscription and retainer billing is common.
      </TipCallout>
    </div>
  )
}

function BudgetsPanel() {
  return (
    <div className="space-y-3 text-sm text-[#1a1814]/80 leading-relaxed">
      <SectionHeading>Budgets & Variance Analysis</SectionHeading>
      <p>
        Set a monthly budget per account and compare it against actual GL activity to spot overspend
        early — standard management-accounting practice under <strong>IAS 1</strong>.
      </p>
      <StepList steps={[
        "Go to Budgets and enter monthly amounts per expense (or revenue) account for the fiscal year",
        "Open Budget vs Actual to see budget, actual, variance, and variance % side by side",
        "Variances are colour-coded — over-budget in red, under-budget in green",
      ]} />
      <TipCallout>
        Multi-currency reports and the comparative-period columns on the P&L and Balance Sheet pair well
        with budgeting for a full management-review pack.
      </TipCallout>
    </div>
  )
}

function DashboardCustomizationPanel() {
  const { t } = useTranslation()
  return (
    <div>
      <p className="text-sm text-[#1a1814]/70 leading-relaxed">
        The dashboard is fully customizable per user. Your layout is saved to your account —
        other users see their own arrangement.
      </p>

      <SectionHeading>Entering customize mode</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Click the customize icon (pencil/grid icon) in the dashboard toolbar to enter customize
        mode. The editing bar appears at the top showing which layout you&apos;re editing
        (<b>Desktop layout</b>, <b>Tablet layout</b>, or <b>Phone layout</b>).
      </p>

      <SectionHeading>Rearranging widgets</SectionHeading>
      <StepList steps={[
        "Drag any widget by its header/body to move it to a new position in the grid.",
        "Drag the resize handle (bottom-right corner) to make it taller or wider.",
        "Click × on a widget to remove it from the grid.",
      ]} />

      <SectionHeading>Per-breakpoint layouts</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Each screen size has its own saved arrangement:
      </p>
      <ul className="text-xs text-[#1a1814]/70 leading-relaxed space-y-1 mt-2 list-disc pl-5">
        <li><b>Desktop</b> (≥1024 px) — 4-column grid</li>
        <li><b>Tablet</b> (640–1023 px) — 2-column grid</li>
        <li><b>Phone</b> (&lt;640 px) — 1-column grid</li>
      </ul>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-2">
        Resize your browser to switch breakpoints. The toolbar label updates to show which
        layout you&apos;re editing. Desktop edits don&apos;t affect your phone layout until you
        edit it directly.
      </p>

      <SectionHeading>Adding widgets and shortcuts</SectionHeading>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-1">
        Click <b>+ Add widget</b> in the toolbar to open the Add panel:
      </p>
      <ul className="text-xs text-[#1a1814]/70 leading-relaxed space-y-1 mt-2 list-disc pl-5">
        <li><b>Widgets tab</b> — Bank Balances, Top Products, Inventory Summary — self-fetching data widgets</li>
        <li><b>Shortcuts tab</b> — pin any navigation page as a quick-access tile (e.g., Invoices, Bills, Products, Bank Accounts)</li>
      </ul>
      <p className="text-xs text-[#1a1814]/65 leading-relaxed mt-2">
        Shortcut tiles show live metric badges where available (e.g., overdue count, total outstanding).
      </p>

      <SectionHeading>Saving and resetting</SectionHeading>
      <ul className="text-xs text-[#1a1814]/70 leading-relaxed space-y-1 mt-2 list-disc pl-5">
        <li><b>Done</b> — saves your layout and exits customize mode</li>
        <li><b>{t('common.cancel', 'Cancel')}</b> — discards unsaved changes</li>
        <li><b>Reset all</b> — removes all customizations and returns to the default grid for all screen sizes</li>
      </ul>

      <TipCallout>
        Your dashboard layout is saved per-user. Team members each have their own arrangement
        and can customize independently.
      </TipCallout>

      <MistakeCallout>
        <p><b>Reset all</b> clears ALL breakpoint layouts — desktop, tablet, and phone. There is no undo once saved.</p>
      </MistakeCallout>
    </div>
  )
}

// ── Panel map ─────────────────────────────────────────────────────────────────

const PANEL_MAP: Record<string, React.ReactNode> = {
  "getting-started": <GettingStartedPanel />,
  "dashboard":       <DashboardCustomizationPanel />,
  "coa":             <CoaPanel />,
  "invoicing":       <InvoicingPanel />,
  "billing":         <BillingPanel />,
  "credit-notes":    <CreditNotesPanel />,
  "debit-notes":     <DebitNotesPanel />,
  "advances":        <AdvancesPanel />,
  "products":        <ProductsPanel />,
  "purchase-orders": <PurchaseOrdersPanel />,
  "payments":        <PaymentsPanel />,
  "journal":         <JournalPanel />,
  "analytic":        <AnalyticPanel />,
  "fixed-assets":    <FixedAssetsPanel />,
  "deferred-revenue": <DeferredRevenuePanel />,
  "tax-codes":       <TaxCodesPanel />,
  "currency":        <CurrencyPanel />,
  "budgets":         <BudgetsPanel />,
  "recurring":       <RecurringPanel />,
  "bank-imports":    <BankImportsPanel />,
  "period-close":    <PeriodClosePanel />,
  "roles":           <RolesPanel />,
  "security":        <SecurityPanel />,
  "reports":         <ReportsPanel />,
  "sub-ledgers":     <SubLedgersPanel />,
  "csv":             <CsvImportPanel />,
  "manufacturing":   <ManufacturingPanel />,
  "telecom":         <TelecomFranchisePanel />,
  "bulk-statements": <BulkStatementsPanel />,
  "tips-shortcuts":  <TipsShortcutsPanel />,
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function GuidePage() {

  const [activeTab, setActiveTab] = useState<string>("getting-started")
  const [businessModel, setBusinessModel] = useState<BusinessModel | null>(null)

  // Fetch the tenant's business model so the guide only shows relevant sections.
  useEffect(() => {
    apiFetch<{ tenant?: { business_model?: BusinessModel } }>("/api/auth/me")
      .then(d => setBusinessModel(d.tenant?.business_model ?? "simple"))
      .catch(() => setBusinessModel("simple"))
  }, [])

  // Until we know the model, show universal tabs only (avoids a flash of
  // model-specific content that then disappears).
  const visibleTabs = TABS.filter(
    t => !t.forModels || (businessModel != null && t.forModels.includes(businessModel))
  )

  // If the active tab gets filtered out (model resolved after mount), fall back.
  useEffect(() => {
    if (businessModel && !visibleTabs.some(t => t.id === activeTab)) {
      setActiveTab("getting-started")
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [businessModel])

  const activeTabDef = visibleTabs.find(t => t.id === activeTab) ?? visibleTabs[0]
  const ActiveIcon = activeTabDef.icon

  return (
    <div className="space-y-5">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-[#1a1814]/50">
        <Link href="/dashboard" className="hover:text-[#b8943f] transition-colors">Dashboard</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-[#1a1814]/80 font-medium">User Guide</span>
      </nav>

      {/* Page header */}
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#1a1814] flex items-center justify-center flex-shrink-0">
          <BookOpen className="w-5 h-5 text-[#ffd966]" />
        </div>
        <div>
          <h1 className="text-xl sm:text-2xl font-serif font-semibold text-[#1a1814]">User Guide</h1>
          <p className="text-xs text-[#1a1814]/50 mt-0.5 font-medium tracking-wide uppercase">
            Comprehensive reference for Easy-Books
          </p>
        </div>
      </div>

      {/* Tab strip — horizontal scroll on mobile */}
      <div className="bg-white border border-[#ede9e2] rounded-2xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto border-b border-[#ede9e2]">
          <div className="flex min-w-max">
            {visibleTabs.map(tab => {
              const Icon = tab.icon
              const isActive = tab.id === activeTab
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={[
                    "flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-all whitespace-nowrap",
                    isActive
                      ? "border-[#b8943f] text-[#b8943f] bg-[#faf6ec]"
                      : "border-transparent text-[#1a1814]/55 hover:text-[#1a1814] hover:bg-[#f6f3ee]",
                  ].join(" ")}
                >
                  <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                  <span className="hidden sm:inline">{tab.label}</span>
                  <span className="sm:hidden">{tab.shortLabel}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Active tab header */}
        <div className="px-5 pt-4 pb-1 flex items-center gap-2 border-b border-[#ede9e2] bg-[#f6f3ee]">
          <ActiveIcon className="w-4 h-4 text-[#b8943f]" />
          <h2 className="text-sm font-bold text-[#1a1814]">{activeTabDef.label}</h2>
        </div>

        {/* Panel content */}
        <div className="p-5">
          {PANEL_MAP[activeTabDef.id]}
        </div>
      </div>

      {/* Footer nav */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        {/* Previous / Next tab navigation */}
        {(() => {
          const idx = visibleTabs.findIndex(t => t.id === activeTabDef.id)
          const prev = idx > 0 ? visibleTabs[idx - 1] : null
          const next = idx < visibleTabs.length - 1 ? visibleTabs[idx + 1] : null
          return (
            <>
              <div>
                {prev && (
                  <button
                    onClick={() => setActiveTab(prev.id)}
                    className="flex items-center gap-1.5 text-xs text-[#1a1814]/55 hover:text-[#b8943f] transition-colors"
                  >
                    <ChevronRight className="w-3.5 h-3.5 rotate-180" />
                    {prev.label}
                  </button>
                )}
              </div>
              <div>
                {next && (
                  <button
                    onClick={() => setActiveTab(next.id)}
                    className="flex items-center gap-1.5 text-xs text-[#1a1814]/55 hover:text-[#b8943f] transition-colors"
                  >
                    {next.label}
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </>
          )
        })()}
      </div>

      {/* Also see */}
      <div className="bg-[#f6f3ee] border border-[#ede9e2] rounded-xl px-5 py-4 text-xs text-[#1a1814]/60 leading-relaxed">
        <span className="font-semibold text-[#b8943f]">Also see:</span>{" "}
        <Link href="/workflow" className="text-[#b8943f] underline underline-offset-2 hover:text-[#7a5c1e]">
          Transaction Workflow
        </Link>
        {" "}for a visual flowchart of how each transaction type maps to GL entries.
      </div>
    </div>
  )
}
