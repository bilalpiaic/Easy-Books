import {
  LayoutDashboard, LayoutGrid, PlusCircle, ClipboardList, BookOpen, TableProperties,
  Scale, FileText, PieChart, TrendingUp, FileSignature, Users,
  ArrowDownLeft, Receipt, Truck, ArrowUpRight, Landmark, CheckCheck,
  Percent, Settings, Package, GitBranch, HelpCircle,
  Factory, ListChecks, Tags, PackagePlus, Warehouse, ShoppingCart,
  Radio, Wallet, Network, Smartphone, Target, Banknote, ReceiptText,
  ScrollText, Tablet, UserCircle, UsersRound, RefreshCw,
  Building2, Undo2, CalendarCheck, Clock, Table2, Upload, Layers, Play, BarChart2,
  ShieldCheck, Briefcase, UserCog, Settings2, CalendarDays, FileCheck, AppWindow,
  Stethoscope, FileHeart, Activity, BedDouble, FlaskConical, Syringe, UserRound,
} from "lucide-react"

export type NavItem = {
  label: string
  href: string
  icon: React.ElementType
  section: string
  /** Module ID — item is hidden when this module is not installed. */
  forModule?: "inventory" | "production" | "hrm" | "telecom" | "pra" | "healthcare"
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
  { label: "Overview",         href: "/receivable",        icon: LayoutGrid,       section: "Receivable" },
  { label: "Invoices",         href: "/invoices",          icon: FileSignature,    section: "Receivable" },
  { label: "Commissions",      href: "/commissions",        icon: Percent,          section: "Receivable" },
  { label: "Promo Discounts", href: "/promo-discounts",    icon: Tags,             section: "Receivable" },
  { label: "Credit Notes",     href: "/credit-notes",      icon: Receipt,          section: "Receivable" },
  { label: "Customers",        href: "/customers",         icon: Users,            section: "Receivable" },
  { label: "Payments Received",href: "/payments-received", icon: ArrowDownLeft,    section: "Receivable" },
  { label: "Advances Received",href: "/advances",          icon: Wallet,           section: "Receivable" },
  { label: "Overview",         href: "/payable",           icon: LayoutGrid,       section: "Payable" },
  { label: "Bills",            href: "/bills",             icon: Receipt,          section: "Payable" },
  { label: "Debit Notes",      href: "/debit-notes",       icon: Undo2,            section: "Payable" },
  { label: "Vendors",          href: "/vendors",           icon: Truck,            section: "Payable" },
  { label: "Bill Payments",    href: "/bill-payments",     icon: ArrowUpRight,     section: "Payable" },
  { label: "Overview",         href: "/inventory",         icon: LayoutGrid,       section: "Inventory",      forModule: "inventory" },
  { label: "Products",          href: "/products",            icon: Package,          section: "Inventory",      forModule: "inventory" },
  { label: "Product Categories",href: "/products/categories", icon: Tags,             section: "Inventory",      forModule: "inventory" },
  { label: "Product Ledger",    href: "/products/ledger",    icon: BookOpen,         section: "Inventory",      forModule: "inventory" },
  { label: "Inventory Report",  href: "/inventory/performance", icon: PieChart,      section: "Inventory",      forModule: "inventory" },
  { label: "Production Floor", href: "/manufacturing",     icon: Factory,          section: "Manufacturing",    forModule: "production" },
  { label: "Bills of Material",href: "/manufacturing/boms",icon: ListChecks,       section: "Manufacturing",    forModule: "production" },
  { label: "Rate Plans",       href: "/manufacturing/rate-plans", icon: Tags,      section: "Manufacturing",    forModule: "production" },
  { label: "Purchase Orders",  href: "/manufacturing/purchase-orders", icon: ShoppingCart, section: "Manufacturing", forModule: "production" },
  { label: "Stock Locations",  href: "/manufacturing/stock-locations", icon: Warehouse, section: "Manufacturing", forModule: "production" },
  { label: "Goods Receipt",    href: "/manufacturing/grn", icon: PackagePlus,      section: "Manufacturing",    forModule: "production" },
  { label: "Production Orders",href: "/manufacturing/production-orders", icon: Warehouse, section: "Manufacturing", forModule: "production" },
  { label: "Mfg Reports",     href: "/manufacturing/reports",           icon: BarChart2, section: "Manufacturing", forModule: "production" },
  { label: "Telecom Overview", href: "/telecom",                icon: Radio,       section: "Telecom",          forModule: "telecom" },
  { label: "Tracker & Load",   href: "/telecom/tracker",        icon: Wallet,      section: "Telecom",          forModule: "telecom" },
  { label: "RSO Channel",      href: "/telecom/rso",            icon: Network,     section: "Telecom",          forModule: "telecom" },
  { label: "SIM & Activations",href: "/telecom/sim",            icon: Smartphone,  section: "Telecom",          forModule: "telecom" },
  { label: "FCA & Targets",    href: "/telecom/fca",            icon: Target,      section: "Telecom",          forModule: "telecom" },
  { label: "Mobile Money",     href: "/telecom/mobile-money",   icon: Banknote,    section: "Telecom",          forModule: "telecom" },
  { label: "Postpaid Billing", href: "/telecom/postpaid",       icon: ReceiptText, section: "Telecom",          forModule: "telecom" },
  { label: "Commissions",      href: "/telecom/commissions",    icon: Percent,     section: "Telecom",          forModule: "telecom" },
  { label: "Franchise Admin",  href: "/telecom/franchise",      icon: ScrollText,  section: "Telecom",          forModule: "telecom" },
  { label: "Devices (IMEI)",   href: "/telecom/devices",        icon: Tablet,      section: "Telecom",          forModule: "telecom" },
  { label: "Overview",         href: "/banking",           icon: LayoutGrid,       section: "Banking" },
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
  { label: "My Profile",       href: "/profile",           icon: UserCircle,       section: "System" },
  { label: "CSV Import",        href: "/imports",           icon: Upload,           section: "System" },
  { label: "Payment Terms",    href: "/payment-terms",     icon: Clock,            section: "System", adminOnly: true },
  { label: "Team",             href: "/team",              icon: UsersRound,       section: "System", adminOnly: true },
  { label: "Permissions",      href: "/settings/permissions", icon: ShieldCheck,   section: "System", adminOnly: true },
  { label: "Audit Log",        href: "/audit",             icon: ScrollText,       section: "System", adminOnly: true },
  { label: "Workflow",         href: "/workflow",          icon: GitBranch,        section: "System" },
  { label: "User Guide",       href: "/guide",             icon: HelpCircle,       section: "System" },
  { label: "Settings",         href: "/settings",          icon: Settings,         section: "System" },
  { label: "Apps",             href: "/apps",              icon: AppWindow,        section: "System",    adminOnly: true },
  { label: "PRA Logs",         href: "/pra-logs",          icon: FileCheck,        section: "System",    forModule: "pra" },
  // Payroll
  { label: "Overview",         href: "/hrm",               icon: LayoutGrid,       section: "Payroll",   forModule: "hrm" },
  { label: "Payroll Runs",     href: "/payroll",           icon: Briefcase,        section: "Payroll",   forModule: "hrm" },
  { label: "Employees",        href: "/employees",         icon: UserCog,          section: "Payroll",   forModule: "hrm" },
  { label: "Attendance",       href: "/attendance",        icon: CalendarDays,     section: "Payroll",   forModule: "hrm" },
  { label: "Salary Components",href: "/payroll/components",icon: Settings2,        section: "Payroll",   forModule: "hrm" },
  // Healthcare
  { label: "HC Overview",       href: "/healthcare",              icon: Stethoscope,  section: "Healthcare", forModule: "healthcare" },
  { label: "Patients",          href: "/healthcare/patients",     icon: FileHeart,    section: "Healthcare", forModule: "healthcare" },
  { label: "Doctors",           href: "/healthcare/doctors",      icon: UserRound,    section: "Healthcare", forModule: "healthcare" },
  { label: "OPD",               href: "/healthcare/opd",          icon: Activity,     section: "Healthcare", forModule: "healthcare" },
  { label: "IPD / Inpatient",   href: "/healthcare/ipd",          icon: BedDouble,    section: "Healthcare", forModule: "healthcare" },
  { label: "Laboratory",        href: "/healthcare/lab",          icon: FlaskConical, section: "Healthcare", forModule: "healthcare" },
  { label: "Lab Tests",         href: "/healthcare/lab/tests",    icon: FlaskConical, section: "Healthcare", forModule: "healthcare" },
  { label: "Procedures",        href: "/healthcare/procedures",   icon: Syringe,      section: "Healthcare", forModule: "healthcare" },
  { label: "HC Store",          href: "/healthcare/store",        icon: Warehouse,    section: "Healthcare", forModule: "healthcare" },
  { label: "HC Reports",        href: "/healthcare/reports",      icon: BarChart2,    section: "Healthcare", forModule: "healthcare" },
]

export const ALL_SECTIONS = ["Overview","Ledger","Receivable","Payable","Inventory","Manufacturing","Telecom","Healthcare","Banking","Reports","Payroll","System"]

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
