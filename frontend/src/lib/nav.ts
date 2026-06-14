import {
  LayoutDashboard, PlusCircle, ClipboardList, BookOpen, TableProperties,
  Scale, FileText, PieChart, TrendingUp, FileSignature, Users,
  ArrowDownLeft, Receipt, Truck, ArrowUpRight, Landmark, CheckCheck,
  Percent, Settings, Package, GitBranch, HelpCircle,
  Factory, ListChecks, Tags, PackagePlus, Warehouse, ShoppingCart,
  Radio, Wallet, Network, Smartphone, Target, Banknote, ReceiptText,
  ScrollText, Tablet, UserCircle, UsersRound, RefreshCw,
  Building2, Undo2, CalendarCheck, Clock, Table2, Upload, Layers, Play, BarChart2,
  ShieldCheck,
} from "lucide-react"

export type NavItem = {
  label: string
  href: string
  icon: React.ElementType
  section: string
  forModel?: "manufacturing" | "telecom_franchise"
  /** Only shown to admin+ (admin or owner). */
  adminOnly?: boolean
}

export const NAV: NavItem[] = [
  { label: "Dashboard",        href: "/dashboard",         icon: LayoutDashboard,  section: "Overview" },
  { label: "New Entry",        href: "/entry",             icon: PlusCircle,       section: "Ledger" },
  { label: "Journal",          href: "/journal",           icon: ClipboardList,    section: "Ledger" },
  { label: "Recurring",        href: "/recurring",         icon: RefreshCw,        section: "Ledger" },
  { label: "General Ledger",   href: "/ledger",            icon: BookOpen,         section: "Ledger" },
  { label: "Chart of Accounts",href: "/coa",               icon: TableProperties,  section: "Ledger" },
  { label: "Analytic Accounts",href: "/analytic-accounts", icon: Layers,           section: "Ledger" },
  { label: "Invoices",         href: "/invoices",          icon: FileSignature,    section: "Receivable" },
  { label: "Commissions",      href: "/commissions",        icon: Percent,          section: "Receivable" },
  { label: "Promo Discounts", href: "/promo-discounts",    icon: Tags,             section: "Receivable" },
  { label: "Credit Notes",     href: "/credit-notes",      icon: Receipt,          section: "Receivable" },
  { label: "Customers",        href: "/customers",         icon: Users,            section: "Receivable" },
  { label: "Payments Received",href: "/payments-received", icon: ArrowDownLeft,    section: "Receivable" },
  { label: "Advances Received",href: "/advances",          icon: Wallet,           section: "Receivable" },
  { label: "Bills",            href: "/bills",             icon: Receipt,          section: "Payable" },
  { label: "Debit Notes",      href: "/debit-notes",       icon: Undo2,            section: "Payable" },
  { label: "Vendors",          href: "/vendors",           icon: Truck,            section: "Payable" },
  { label: "Bill Payments",    href: "/bill-payments",     icon: ArrowUpRight,     section: "Payable" },
  { label: "Products",          href: "/products",            icon: Package,          section: "Inventory" },
  { label: "Product Categories",href: "/products/categories", icon: Tags,             section: "Inventory" },
  { label: "Product Ledger",    href: "/products/ledger",    icon: BookOpen,         section: "Inventory" },
  { label: "Inventory Report",  href: "/inventory/performance", icon: PieChart,      section: "Inventory" },
  { label: "Production Floor", href: "/manufacturing",     icon: Factory,          section: "Manufacturing", forModel: "manufacturing" },
  { label: "Bills of Material",href: "/manufacturing/boms",icon: ListChecks,       section: "Manufacturing", forModel: "manufacturing" },
  { label: "Rate Plans",       href: "/manufacturing/rate-plans", icon: Tags,      section: "Manufacturing", forModel: "manufacturing" },
  { label: "Purchase Orders",  href: "/manufacturing/purchase-orders", icon: ShoppingCart, section: "Manufacturing", forModel: "manufacturing" },
  { label: "Stock Locations",  href: "/manufacturing/stock-locations", icon: Warehouse, section: "Manufacturing", forModel: "manufacturing" },
  { label: "Goods Receipt",    href: "/manufacturing/grn", icon: PackagePlus,      section: "Manufacturing", forModel: "manufacturing" },
  { label: "Production Orders",href: "/manufacturing/production-orders", icon: Warehouse, section: "Manufacturing", forModel: "manufacturing" },
  { label: "Mfg Reports",     href: "/manufacturing/reports",           icon: BarChart2, section: "Manufacturing", forModel: "manufacturing" },
  { label: "Telecom Overview", href: "/telecom",                icon: Radio,       section: "Telecom", forModel: "telecom_franchise" },
  { label: "Tracker & Load",   href: "/telecom/tracker",        icon: Wallet,      section: "Telecom", forModel: "telecom_franchise" },
  { label: "RSO Channel",      href: "/telecom/rso",            icon: Network,     section: "Telecom", forModel: "telecom_franchise" },
  { label: "SIM & Activations",href: "/telecom/sim",            icon: Smartphone,  section: "Telecom", forModel: "telecom_franchise" },
  { label: "FCA & Targets",    href: "/telecom/fca",            icon: Target,      section: "Telecom", forModel: "telecom_franchise" },
  { label: "Mobile Money",     href: "/telecom/mobile-money",   icon: Banknote,    section: "Telecom", forModel: "telecom_franchise" },
  { label: "Postpaid Billing", href: "/telecom/postpaid",       icon: ReceiptText, section: "Telecom", forModel: "telecom_franchise" },
  { label: "Commissions",      href: "/telecom/commissions",    icon: Percent,     section: "Telecom", forModel: "telecom_franchise" },
  { label: "Franchise Admin",  href: "/telecom/franchise",      icon: ScrollText,  section: "Telecom", forModel: "telecom_franchise" },
  { label: "Devices (IMEI)",   href: "/telecom/devices",        icon: Tablet,      section: "Telecom", forModel: "telecom_franchise" },
  { label: "Bank Accounts",    href: "/bank-accounts",     icon: Landmark,         section: "Banking" },
  { label: "Exchange Rates",   href: "/exchange-rates",    icon: TrendingUp,       section: "Banking" },
  { label: "Bank Imports",     href: "/bank-imports",      icon: Upload,           section: "Banking" },
  { label: "Cash Book",        href: "/cash-book",         icon: Wallet,           section: "Banking" },
  { label: "Bank Book",        href: "/bank-book",         icon: BookOpen,         section: "Banking" },
  { label: "Reconciliations",  href: "/reconciliations",   icon: CheckCheck,       section: "Banking" },
  { label: "Trial Balance",    href: "/trial-balance",     icon: Scale,            section: "Reports" },
  { label: "Income Statement", href: "/pl",                icon: TrendingUp,       section: "Reports" },
  { label: "Balance Sheet",    href: "/balance",           icon: PieChart,         section: "Reports" },
  { label: "Cash Flow",        href: "/cashflow",          icon: FileText,         section: "Reports" },
  { label: "Tax Reports",      href: "/tax",               icon: Percent,          section: "Reports" },
  { label: "Tax Codes",        href: "/tax-codes",         icon: Percent,          section: "Reports" },
  { label: "Budget vs Actual", href: "/budgets",           icon: TrendingUp,       section: "Reports" },
  { label: "Fixed Assets",     href: "/assets",            icon: Building2,        section: "Reports" },
  { label: "Period Close",     href: "/period-close",      icon: CalendarCheck,    section: "Reports" },
  { label: "Deferred Revenue", href: "/deferred-revenue",  icon: Play,             section: "Reports" },
  { label: "AR Aging",         href: "/aging/receivable",  icon: Clock,            section: "Reports" },
  { label: "AP Aging",         href: "/aging/payable",     icon: Clock,            section: "Reports" },
  { label: "Customer Performance", href: "/customer-performance", icon: TrendingUp,   section: "Reports" },
  { label: "Report Builder",      href: "/reports/builder",      icon: Table2,         section: "Reports" },
  { label: "CSV Import",        href: "/imports",           icon: Upload,           section: "System" },
  { label: "Payment Terms",    href: "/payment-terms",     icon: Clock,            section: "System", adminOnly: true },
  { label: "My Profile",       href: "/profile",           icon: UserCircle,       section: "System" },
  { label: "Team",             href: "/team",              icon: UsersRound,       section: "System", adminOnly: true },
  { label: "Permissions",      href: "/settings/permissions", icon: ShieldCheck,   section: "System", adminOnly: true },
  { label: "Audit Log",        href: "/audit",             icon: ScrollText,       section: "System", adminOnly: true },
  { label: "Workflow",         href: "/workflow",          icon: GitBranch,        section: "System" },
  { label: "User Guide",       href: "/guide",             icon: HelpCircle,       section: "System" },
  { label: "Settings",         href: "/settings",          icon: Settings,         section: "System" },
]

export const ALL_SECTIONS = ["Overview","Ledger","Receivable","Payable","Inventory","Manufacturing","Telecom","Banking","Reports","System"]

/**
 * Resolve a pathname to its breadcrumb context using the sidebar map.
 * - `list` = the NAV item whose href is the LONGEST prefix of pathname.
 * - `isSubPage` is true only when pathname is DEEPER than that href
 *   (i.e. a detail / new / edit route), so top-level destinations get no bar.
 */
export function resolveBreadcrumb(pathname: string): {
  list?: { label: string; href: string }
  isSubPage: boolean
} {
  let best: NavItem | undefined
  for (const item of NAV) {
    if (pathname === item.href || pathname.startsWith(item.href + "/")) {
      if (!best || item.href.length > best.href.length) best = item
    }
  }
  if (!best) return { isSubPage: false }
  const isSubPage = pathname !== best.href
  return { list: { label: best.label, href: best.href }, isSubPage }
}
