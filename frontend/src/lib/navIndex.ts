/**
 * Static full-text search index for navigation, forms, and reports.
 * Built at module-load time — every lookup is synchronous (~0 ms).
 *
 * Three layers:
 *  1. All sidebar nav items from NAV (section pages)
 *  2. Quick-action "New …" forms
 *  3. Report & utility pages with keyword aliases
 */
import { NAV } from "@/lib/nav"

export interface NavResult {
  id:       string
  type:     "nav" | "action" | "report"
  label:    string
  sub:      string   // shown as secondary text
  href:     string
  keywords: string[] // extra match terms (not displayed)
}

// ── 1. Sidebar pages ──────────────────────────────────────────────────────────

const NAV_ITEMS: NavResult[] = NAV.map(item => ({
  id:       `nav:${item.href}`,
  type:     "nav" as const,
  label:    item.label,
  sub:      item.section,
  href:     item.href,
  keywords: [item.label.toLowerCase(), item.section.toLowerCase()],
}))

// ── 2. Quick-action "New …" forms ────────────────────────────────────────────

const ACTIONS: NavResult[] = [
  {
    id: "qa:invoice-new", type: "action", label: "New Invoice",
    sub: "Create a sales invoice", href: "/invoices/new",
    keywords: ["create invoice", "add invoice", "sale", "billing", "new sale"],
  },
  {
    id: "qa:bill-new", type: "action", label: "New Bill",
    sub: "Record a vendor bill", href: "/bills/new",
    keywords: ["create bill", "add bill", "purchase", "vendor invoice", "supplier"],
  },
  {
    id: "qa:customer-new", type: "action", label: "New Customer",
    sub: "Add a customer", href: "/customers/new",
    keywords: ["create customer", "add customer", "client", "buyer"],
  },
  {
    id: "qa:vendor-new", type: "action", label: "New Vendor",
    sub: "Add a vendor / supplier", href: "/vendors/new",
    keywords: ["create vendor", "add vendor", "supplier", "add supplier"],
  },
  {
    id: "qa:payment-received-new", type: "action", label: "New Payment Received",
    sub: "Record customer payment", href: "/payments-received/new",
    keywords: ["receive payment", "customer payment", "collection", "cash receipt"],
  },
  {
    id: "qa:bill-payment-new", type: "action", label: "New Bill Payment",
    sub: "Pay a vendor bill", href: "/bill-payments/new",
    keywords: ["pay bill", "vendor payment", "payment made", "cash payment"],
  },
  {
    id: "qa:journal-new", type: "action", label: "New Journal Entry",
    sub: "Manual debit / credit entry", href: "/entry",
    keywords: ["journal", "jv", "voucher", "debit credit", "manual entry", "new entry"],
  },
  {
    id: "qa:product-new", type: "action", label: "New Product",
    sub: "Add a product or service", href: "/products/new",
    keywords: ["create product", "add item", "inventory item", "stock item", "service"],
  },
  {
    id: "qa:employee-new", type: "action", label: "New Employee",
    sub: "Add an employee record", href: "/employees/new",
    keywords: ["create employee", "add staff", "hire", "new hire"],
  },
  {
    id: "qa:payroll-new", type: "action", label: "New Payroll Run",
    sub: "Process payroll for a period", href: "/payroll/new",
    keywords: ["run payroll", "pay salaries", "payroll period", "salary run"],
  },
  {
    id: "qa:po-new", type: "action", label: "New Purchase Order",
    sub: "Create a purchase order", href: "/manufacturing/purchase-orders/new",
    keywords: ["create po", "purchase order", "order to supplier"],
  },
  {
    id: "qa:grn-new", type: "action", label: "New Goods Receipt",
    sub: "Receive stock from a PO", href: "/manufacturing/grn/new",
    keywords: ["receive goods", "grn", "stock receipt", "goods in"],
  },
  {
    id: "qa:bom-new", type: "action", label: "New Bill of Materials",
    sub: "Define a production recipe", href: "/manufacturing/boms/new",
    keywords: ["bom", "recipe", "manufacturing", "components"],
  },
  {
    id: "qa:production-new", type: "action", label: "New Production Order",
    sub: "Start a manufacturing run", href: "/manufacturing/production-orders/new",
    keywords: ["production order", "work order", "manufacture", "produce"],
  },
]

// ── 3. Reports & utilities with keywords ──────────────────────────────────────

const REPORTS: NavResult[] = [
  {
    id: "rpt:trial-balance", type: "report", label: "Trial Balance",
    sub: "Accounts debit/credit summary", href: "/trial-balance",
    keywords: ["tb", "trial balance", "closing balance", "debit credit totals"],
  },
  {
    id: "rpt:pl", type: "report", label: "Income Statement",
    sub: "Profit & Loss report", href: "/pl",
    keywords: ["p&l", "profit loss", "income statement", "pnl", "revenue expenses"],
  },
  {
    id: "rpt:balance-sheet", type: "report", label: "Balance Sheet",
    sub: "Assets, liabilities & equity", href: "/balance",
    keywords: ["bs", "balance sheet", "assets liabilities", "financial position"],
  },
  {
    id: "rpt:cash-flow", type: "report", label: "Cash Flow Statement",
    sub: "Cash in & out by activity", href: "/cashflow",
    keywords: ["cash flow", "funds flow", "liquidity", "cash statement"],
  },
  {
    id: "rpt:gl", type: "report", label: "General Ledger",
    sub: "Full account transaction history", href: "/ledger",
    keywords: ["gl", "general ledger", "ledger report", "transaction history"],
  },
  {
    id: "rpt:tax", type: "report", label: "Tax Reports",
    sub: "GST / VAT summary", href: "/tax",
    keywords: ["tax", "gst", "vat", "tax report", "tax summary", "sales tax"],
  },
  {
    id: "rpt:aging-ar", type: "report", label: "AR Aging Report",
    sub: "Outstanding customer invoices by age", href: "/aging/receivable",
    keywords: ["aging", "ar aging", "overdue", "receivable aging", "outstanding customers"],
  },
  {
    id: "rpt:aging-ap", type: "report", label: "AP Aging Report",
    sub: "Outstanding vendor bills by age", href: "/aging/payable",
    keywords: ["ap aging", "overdue bills", "payable aging", "outstanding vendors"],
  },
  {
    id: "rpt:budget", type: "report", label: "Budget vs Actual",
    sub: "Compare budget to actual spend", href: "/budgets",
    keywords: ["budget", "variance", "budget report", "actual vs budget"],
  },
  {
    id: "rpt:customer-perf", type: "report", label: "Customer Performance",
    sub: "Revenue by customer", href: "/customer-performance",
    keywords: ["customer analysis", "top customers", "revenue by customer", "customer report"],
  },
  {
    id: "rpt:product-ledger", type: "report", label: "Product Ledger",
    sub: "Stock movement history", href: "/products/ledger",
    keywords: ["stock ledger", "inventory movements", "product history", "stock history"],
  },
  {
    id: "rpt:inv-perf", type: "report", label: "Inventory Performance",
    sub: "Stock levels & valuation", href: "/inventory/performance",
    keywords: ["inventory report", "stock report", "stock value", "on hand"],
  },
  {
    id: "rpt:report-builder", type: "report", label: "Report Builder",
    sub: "Build custom reports from any table", href: "/reports/builder",
    keywords: ["custom report", "ad hoc", "report builder", "query", "dynamic report"],
  },
  {
    id: "rpt:deferred", type: "report", label: "Deferred Revenue",
    sub: "IFRS-15 recognition schedule", href: "/deferred-revenue",
    keywords: ["deferred", "revenue recognition", "ifrs", "subscription revenue"],
  },
  {
    id: "rpt:assets", type: "report", label: "Fixed Assets",
    sub: "Asset register & depreciation", href: "/assets",
    keywords: ["fixed assets", "depreciation", "asset register", "capex"],
  },
  {
    id: "rpt:cashbook", type: "report", label: "Cash Book",
    sub: "All cash transactions", href: "/cash-book",
    keywords: ["cash book", "petty cash", "cash transactions", "cash ledger"],
  },
  {
    id: "rpt:bankbook", type: "report", label: "Bank Book",
    sub: "All bank transactions", href: "/bank-book",
    keywords: ["bank book", "bank statement", "bank ledger", "bank transactions"],
  },
  {
    id: "rpt:coa", type: "report", label: "Chart of Accounts",
    sub: "Account hierarchy", href: "/coa",
    keywords: ["coa", "chart of accounts", "accounts list", "account codes"],
  },
  {
    id: "rpt:audit", type: "report", label: "Audit Log",
    sub: "System activity history", href: "/audit",
    keywords: ["audit", "activity log", "history", "who changed", "audit trail"],
  },
  {
    id: "rpt:reconciliation", type: "report", label: "Bank Reconciliation",
    sub: "Match bank statement to ledger", href: "/reconciliations",
    keywords: ["reconcile", "bank reconciliation", "match transactions", "bank match"],
  },
  {
    id: "rpt:period-close", type: "report", label: "Period Close",
    sub: "Lock an accounting period", href: "/period-close",
    keywords: ["period close", "close month", "lock period", "fiscal period"],
  },
  // Settings / system pages
  {
    id: "sys:settings", type: "nav", label: "Settings",
    sub: "Company, accounting & preferences", href: "/settings",
    keywords: ["settings", "preferences", "configuration", "setup", "company settings"],
  },
  {
    id: "sys:settings-updates", type: "nav", label: "Check for Updates",
    sub: "System update settings", href: "/settings?tab=updates",
    keywords: ["update", "version", "upgrade", "patch", "updates tab"],
  },
  {
    id: "sys:settings-accounting", type: "nav", label: "Accounting Settings",
    sub: "Currency, fiscal year, prefixes", href: "/settings?tab=accounting",
    keywords: ["currency", "fiscal year", "invoice prefix", "accounting settings"],
  },
  {
    id: "sys:team", type: "nav", label: "Team / Users",
    sub: "Manage team members and roles", href: "/team",
    keywords: ["team", "users", "roles", "staff", "members", "access"],
  },
  {
    id: "sys:permissions", type: "nav", label: "Permissions",
    sub: "Granular access control matrix", href: "/settings/permissions",
    keywords: ["permissions", "access control", "roles", "rights", "user rights"],
  },
  {
    id: "sys:imports", type: "nav", label: "CSV Import",
    sub: "Import data from spreadsheet", href: "/imports",
    keywords: ["import", "csv", "spreadsheet", "upload data", "bulk import"],
  },
  {
    id: "sys:addons", type: "nav", label: "Add-ons / Modules",
    sub: "Install or remove modules", href: "/apps",
    keywords: ["addons", "modules", "apps", "install module", "extensions"],
  },
]

// ── Full combined index ───────────────────────────────────────────────────────

const ALL: NavResult[] = [...NAV_ITEMS, ...ACTIONS, ...REPORTS]

// ── Search function ───────────────────────────────────────────────────────────

export function searchNav(q: string, limit = 8): NavResult[] {
  if (!q) return []
  const lower = q.toLowerCase()
  const scored: Array<{ r: NavResult; score: number }> = []

  for (const r of ALL) {
    const labelLower = r.label.toLowerCase()
    const subLower   = r.sub.toLowerCase()

    // Exact label start → highest priority
    if (labelLower.startsWith(lower)) {
      scored.push({ r, score: 3 })
    } else if (labelLower.includes(lower)) {
      scored.push({ r, score: 2 })
    } else if (subLower.includes(lower)) {
      scored.push({ r, score: 1 })
    } else if (r.keywords.some(k => k.includes(lower))) {
      scored.push({ r, score: 0 })
    }
  }

  return scored
    .sort((a, b) => b.score - a.score || a.r.label.localeCompare(b.r.label))
    .slice(0, limit)
    .map(x => x.r)
}

// ── Prefix map for typed search (e.g. "inv:" → only invoices group) ──────────

export const SEARCH_PREFIXES: Record<string, string> = {
  inv:      "invoices",
  invoice:  "invoices",
  bill:     "bills",
  bills:    "bills",
  cust:     "customers",
  customer: "customers",
  vend:     "vendors",
  vendor:   "vendors",
  acc:      "accounts",
  account:  "accounts",
  prod:     "products",
  product:  "products",
  emp:      "employees",
  employee: "employees",
  tx:       "transactions",
  jv:       "transactions",
  nav:      "__nav__",
  tab:      "__tabs__",
  report:   "__reports__",
  rpt:      "__reports__",
  action:   "__actions__",
  new:      "__actions__",
}

export { type NavResult as SearchNavResult }
