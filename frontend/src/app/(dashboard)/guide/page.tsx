"use client"

import { useState } from "react"
import Link from "next/link"
import {
  ChevronRight, BookOpen, LogIn, BarChart3, FileSignature,
  Receipt, Package, PenLine, TrendingUp, Upload,
  AlertTriangle, CheckCircle, Info,
} from "lucide-react"

// ── Tab definition ────────────────────────────────────────────────────────────

interface Tab {
  id: string
  label: string
  icon: React.ElementType
  shortLabel: string
}

const TABS: Tab[] = [
  { id: "getting-started",  label: "Getting Started",        icon: LogIn,          shortLabel: "Start"    },
  { id: "coa",              label: "Chart of Accounts",      icon: BarChart3,       shortLabel: "COA"      },
  { id: "invoicing",        label: "Invoicing",              icon: FileSignature,   shortLabel: "Invoices" },
  { id: "billing",          label: "Billing",                icon: Receipt,         shortLabel: "Bills"    },
  { id: "products",         label: "Products & Inventory",   icon: Package,         shortLabel: "Products" },
  { id: "journal",          label: "Journal Entries",        icon: PenLine,         shortLabel: "Journal"  },
  { id: "reports",          label: "Financial Reports",      icon: TrendingUp,      shortLabel: "Reports"  },
  { id: "csv",              label: "CSV Import",             icon: Upload,          shortLabel: "CSV"      },
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

      <SectionHeading>Login</SectionHeading>
      <StepList steps={[
        "Navigate to the app URL and you will be redirected to the Login page.",
        "Enter your username and password, then click Sign In.",
        "On first login you will be prompted to configure your company settings.",
        "Your session token is stored securely in localStorage and refreshed automatically.",
      ]} />

      <SectionHeading>Company Setup</SectionHeading>
      <StepList steps={[
        "Go to Settings from the left sidebar.",
        "Enter your company name, address, currency, and fiscal year start date.",
        "Upload a company logo (optional) — it appears on printed invoices and reports.",
        "Save settings. These details appear on all exported documents.",
      ]} />

      <SectionHeading>Your First Transaction</SectionHeading>
      <StepList steps={[
        "Before creating transactions, set up your Chart of Accounts (see the COA tab).",
        "Create at least one Customer (Receivable section) or Vendor (Payable section).",
        "Create an Invoice for a sale, or a Bill for a purchase.",
        "Alternatively, use New Entry (Ledger section) for a direct journal entry.",
        "Check the Dashboard to see your running totals and recent activity.",
      ]} />

      <TipCallout>
        <strong>Pro tip:</strong> Use the Workflow reference page (
        <Link href="/workflow" className="underline underline-offset-2 text-blue-600 hover:text-blue-800">
          Dashboard → Workflow
        </Link>
        ) to visualise exactly which GL accounts are affected by each transaction type.
      </TipCallout>

      <MistakeCallout>
        <p>Skipping company setup — your logo and company name will be missing from all printed documents.</p>
        <p>Creating transactions before setting up a Chart of Accounts — the system needs accounts to post to.</p>
        <p>Using the same account for both income and expense — always use separate account codes.</p>
      </MistakeCallout>
    </div>
  )
}

function CoaPanel() {
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

      <SectionHeading>Best Practices</SectionHeading>
      <StepList steps={[
        "Keep code gaps between accounts (1000, 1010, 1020) so you can insert new accounts later.",
        "Use descriptive names: 'Trade Receivables' is clearer than 'AR'.",
        "Create a dedicated bank account code for each physical bank account.",
        "Separate Cost of Goods Sold (COGS) from operating expenses for accurate gross margin.",
      ]} />

      <MistakeCallout>
        <p>Using a single 'Sundry' account for everything — this makes reports meaningless.</p>
        <p>Forgetting to create a bank account in COA before creating bank transactions.</p>
        <p>Mixing asset and expense accounts — e.g. posting equipment purchases to an expense account.</p>
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
        "Go to Invoices in the sidebar, then click New Invoice.",
        "Select a customer (or create one inline). Set the invoice date and due date.",
        "Add line items: choose a product or type a description, enter quantity and unit price.",
        "Apply tax rates if applicable — the system calculates tax automatically.",
        "Click Save. The invoice moves to 'Unpaid' status and GL entries are posted.",
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

      <SectionHeading>Reorder Levels</SectionHeading>
      <StepList steps={[
        "Open a stock product and set the Reorder Level field.",
        "When stock_qty falls at or below the reorder level, the item appears on the Dashboard under Low Stock.",
        "This is a visual alert only — no automatic purchase order is created.",
        "Use the Products list to view current stock levels across all items.",
      ]} />

      <SectionHeading>CSV Import</SectionHeading>
      <StepList steps={[
        "On the Products page, click the CSV Import button.",
        "Download the sample CSV template to see the required columns.",
        "Required columns: name, type (stock/service), unit_price.",
        "Optional: description, reorder_level, opening_stock.",
        "Upload your CSV and review the preview before confirming the import.",
      ]} />

      <MistakeCallout>
        <p>Using service type for physical goods — stock levels will not be tracked.</p>
        <p>Setting a reorder level of 0 — all stock items will permanently show as low-stock.</p>
        <p>Importing products without a type column — the import will fail.</p>
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
        "To reverse a posted entry, create a new journal entry with the exact opposite debits and credits.",
        "Reference the original JV number in the description (e.g. 'Reversal of JV-0042').",
        "There is no automatic reversal button — reversals are always explicit new entries.",
        "Check the Journal list to verify both the original and reversal entries appear correctly.",
      ]} />

      <TipCallout>
        <strong>Opening balances:</strong> Enter opening balances as a single journal entry on the first day of
        your fiscal year. Debit all asset accounts, credit all liability and equity accounts.
        The entry must balance (Dr = Cr) before the system accepts it.
      </TipCallout>

      <MistakeCallout>
        <p>Saving an unbalanced entry — the system prevents this, but always double-check your totals.</p>
        <p>Posting adjustments to the wrong period — always set the correct entry date, not today's date.</p>
        <p>Describing entries as just "adjustment" — use meaningful descriptions for auditability.</p>
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
        "The report shows total debits and credits for every account.",
        "The grand total row must show equal debits and credits — if not, there is a data entry error.",
        "Export to CSV for external reconciliation.",
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

      <MistakeCallout>
        <p>Running a P&L without setting the correct date range — you may miss transactions or include wrong periods.</p>
        <p>Ignoring a non-balancing Balance Sheet — this always indicates a data problem that needs fixing.</p>
        <p>Relying on profit figures that include unpaid invoices — check Cash Flow for actual liquidity.</p>
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
              ["Products",    "Products page",         "name, type, unit_price"],
              ["Customers",   "Customers page",        "name, email"],
              ["Vendors",     "Vendors page",          "name, email"],
              ["Accounts",    "Chart of Accounts",     "code, name, type"],
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
          { code: "Non-numeric price",      fix: "unit_price must be a plain number (e.g. 1500.00) — no currency symbols or commas." },
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

// ── Panel map ─────────────────────────────────────────────────────────────────

const PANEL_MAP: Record<string, React.ReactNode> = {
  "getting-started": <GettingStartedPanel />,
  "coa":             <CoaPanel />,
  "invoicing":       <InvoicingPanel />,
  "billing":         <BillingPanel />,
  "products":        <ProductsPanel />,
  "journal":         <JournalPanel />,
  "reports":         <ReportsPanel />,
  "csv":             <CsvImportPanel />,
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function GuidePage() {
  const [activeTab, setActiveTab] = useState<string>("getting-started")

  const activeTabDef = TABS.find(t => t.id === activeTab)!
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
            {TABS.map(tab => {
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
          {PANEL_MAP[activeTab]}
        </div>
      </div>

      {/* Footer nav */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        {/* Previous / Next tab navigation */}
        {(() => {
          const idx = TABS.findIndex(t => t.id === activeTab)
          const prev = idx > 0 ? TABS[idx - 1] : null
          const next = idx < TABS.length - 1 ? TABS[idx + 1] : null
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
