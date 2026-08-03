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
  ClipboardCheck, DoorOpen, PackageMinus, Sparkles, Scissors, Calculator, Droplets,
  AlertTriangle, KeyRound, FileSpreadsheet, GitCompareArrows, Globe,
} from "lucide-react"

export type NavItem = {
  label: string
  href: string
  icon: React.ElementType
  section: string
  /** Module ID — item is hidden when this module is not installed. */
  forModule?: "inventory" | "production" | "hrm" | "telecom" | "pra" | "uae_vat" | "sa_zatca" | "in_gst" | "eu_peppol" | "healthcare" | "purchase_store" | "ai_assistant" | "weaving"
  /** Module ID — item is hidden when this module IS installed (dual-home entries). */
  notForModule?: "purchase_store"
  /** Only shown to admin+ (admin or owner). */
  adminOnly?: boolean
}

/** Single visibility predicate — use everywhere instead of ad-hoc forModule checks. */
export function navVisible(item: NavItem, installed: Set<string>): boolean {
  if (item.forModule && !installed.has(item.forModule)) return false
  if (item.notForModule && installed.has(item.notForModule)) return false
  return true
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
  { label: "AR Aging",         href: "/aging/receivable",  icon: Clock,            section: "Receivable" },
  { label: "Overview",         href: "/payable",           icon: LayoutGrid,       section: "Payable" },
  { label: "Bills",            href: "/bills",             icon: Receipt,          section: "Payable" },
  { label: "Debit Notes",      href: "/debit-notes",       icon: Undo2,            section: "Payable" },
  { label: "Vendors",          href: "/vendors",           icon: Truck,            section: "Payable" },
  { label: "Bill Payments",    href: "/bill-payments",     icon: ArrowUpRight,     section: "Payable" },
  { label: "AP Aging",         href: "/aging/payable",     icon: Clock,            section: "Payable" },
  { label: "Demands",          href: "/purchases/demands",     icon: ClipboardCheck, section: "Purchases", forModule: "purchase_store" },
  { label: "Comparatives",     href: "/purchases/comparatives", icon: Scale,        section: "Purchases", forModule: "purchase_store" },
  { label: "Gate Inward",      href: "/purchases/gate-inward", icon: DoorOpen,     section: "Purchases", forModule: "purchase_store" },
  { label: "Gate Register",    href: "/purchases/gate-register", icon: ScrollText, section: "Purchases", forModule: "purchase_store" },
  { label: "3-Way Match",      href: "/purchases/three-way-match", icon: CheckCheck, section: "Purchases", forModule: "purchase_store" },
  { label: "Vendor Performance", href: "/purchases/vendor-performance", icon: TrendingUp, section: "Purchases", forModule: "purchase_store" },
  { label: "Purchase Orders",  href: "/manufacturing/purchase-orders", icon: ShoppingCart, section: "Purchases", forModule: "purchase_store" },
  { label: "Goods Receipt",    href: "/manufacturing/grn", icon: PackagePlus,      section: "Purchases", forModule: "purchase_store" },
  { label: "Gate Outward",     href: "/store/gate-outward",              icon: DoorOpen,   section: "Store", forModule: "purchase_store" },
  { label: "Outward Register", href: "/store/gate-outward-register",     icon: ScrollText, section: "Store", forModule: "purchase_store" },
  { label: "Dispatch Recon",   href: "/store/dispatch-reconciliation",   icon: CheckCheck, section: "Store", forModule: "purchase_store" },
  { label: "Store Issues",     href: "/store/issues",                    icon: PackageMinus, section: "Store", forModule: "purchase_store" },
  { label: "Issue Register",   href: "/store/issue-register",            icon: ScrollText,   section: "Store", forModule: "purchase_store" },
  { label: "Stock Tie-Out",    href: "/store/stock-tie-out",             icon: CheckCheck,   section: "Store", forModule: "purchase_store" },
  { label: "Overview",         href: "/inventory",         icon: LayoutGrid,       section: "Inventory",      forModule: "inventory" },
  { label: "Products",          href: "/products",            icon: Package,          section: "Inventory",      forModule: "inventory" },
  { label: "Product Categories",href: "/products/categories", icon: Tags,             section: "Inventory",      forModule: "inventory" },
  { label: "Product Ledger",    href: "/products/ledger",    icon: BookOpen,         section: "Inventory",      forModule: "inventory" },
  { label: "Inventory Report",  href: "/inventory/performance", icon: PieChart,      section: "Inventory",      forModule: "inventory" },
  { label: "Valuation",         href: "/inventory/valuation",   icon: Scale,         section: "Inventory",      forModule: "inventory" },
  { label: "Production Floor", href: "/manufacturing",     icon: Factory,          section: "Manufacturing",    forModule: "production" },
  { label: "Bills of Material",href: "/manufacturing/boms",icon: ListChecks,       section: "Manufacturing",    forModule: "production" },
  { label: "Rate Plans",       href: "/manufacturing/rate-plans", icon: Tags,      section: "Manufacturing",    forModule: "production" },
  { label: "Purchase Orders",  href: "/manufacturing/purchase-orders", icon: ShoppingCart, section: "Manufacturing", forModule: "production", notForModule: "purchase_store" },
  { label: "Stock Locations",  href: "/manufacturing/stock-locations", icon: Warehouse, section: "Manufacturing", forModule: "production" },
  { label: "Goods Receipt",    href: "/manufacturing/grn", icon: PackagePlus,      section: "Manufacturing",    forModule: "production", notForModule: "purchase_store" },
  { label: "Production Orders",href: "/manufacturing/production-orders", icon: Warehouse, section: "Manufacturing", forModule: "production" },
  { label: "Scrap Reasons",    href: "/manufacturing/scrap-reasons",     icon: AlertTriangle, section: "Manufacturing", forModule: "production" },
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
  { label: "Bank Rules",       href: "/bank-imports/rules", icon: Tags,            section: "Banking" },
  { label: "Cash Book",        href: "/cash-book",         icon: Wallet,           section: "Banking" },
  { label: "Bank Book",        href: "/bank-book",         icon: BookOpen,         section: "Banking" },
  { label: "Reconciliations",  href: "/reconciliations",   icon: CheckCheck,       section: "Banking" },
  { label: "Trial Balance",    href: "/trial-balance",     icon: Scale,            section: "Reports" },
  { label: "Income Statement", href: "/pl",                icon: TrendingUp,       section: "Reports" },
  { label: "Dimensional P&L",  href: "/reports/dimensional-pl", icon: Layers,      section: "Reports" },
  { label: "Balance Sheet",    href: "/balance",           icon: PieChart,         section: "Reports" },
  { label: "Consolidation",    href: "/consolidation",     icon: Network,          section: "Reports" },
  { label: "IC Reconciliation", href: "/intercompany/recon", icon: GitCompareArrows, section: "Reports" },
  { label: "Cash Flow",        href: "/cashflow",          icon: FileText,         section: "Reports" },
  { label: "Tax Reports",      href: "/tax",               icon: Percent,          section: "Reports" },
  { label: "Withholding Tax",  href: "/reports/wht",       icon: Percent,          section: "Reports" },
  { label: "CIT Worksheet",    href: "/reports/cit-worksheet", icon: FileSpreadsheet, section: "Reports" },
  { label: "GSTR Report",      href: "/india-gst/gstr",    icon: FileSpreadsheet,  section: "India GST", forModule: "in_gst" },
  { label: "India GST Home",   href: "/india-gst",         icon: LayoutDashboard,  section: "India GST", forModule: "in_gst" },
  { label: "Tax Return",       href: "/tax-return",        icon: Percent,          section: "Reports" },
  { label: "Tax Codes",        href: "/tax-codes",         icon: Percent,          section: "Reports" },
  { label: "Budget vs Actual", href: "/budgets",           icon: TrendingUp,       section: "Reports" },
  { label: "Fixed Assets",     href: "/assets",            icon: Building2,        section: "Reports" },
  { label: "Asset Rollforward", href: "/assets/rollforward", icon: Table2,         section: "Reports" },
  { label: "Leases",           href: "/leases",            icon: KeyRound,         section: "Reports" },
  { label: "Period Close",     href: "/period-close",      icon: CalendarCheck,    section: "Reports" },
  { label: "Deferred Revenue", href: "/deferred-revenue",  icon: Play,             section: "Reports" },
  { label: "Contract Balances", href: "/contract-balances", icon: FileSpreadsheet,  section: "Reports" },
  { label: "Customer Performance", href: "/customer-performance", icon: TrendingUp, section: "Reports" },
  { label: "Report Builder",       href: "/reports/builder",      icon: Table2,     section: "Reports" },
  { label: "My Profile",       href: "/profile",           icon: UserCircle,       section: "System" },
  { label: "CSV Import",        href: "/imports",           icon: Upload,           section: "System" },
  { label: "Payment Terms",    href: "/payment-terms",     icon: Clock,            section: "System", adminOnly: true },
  { label: "Team",             href: "/team",              icon: UsersRound,       section: "System", adminOnly: true },
  { label: "Practice clients", href: "/practice",          icon: Building2,        section: "System" },
  { label: "Permissions",      href: "/settings/permissions", icon: ShieldCheck,   section: "System", adminOnly: true },
  { label: "Audit Log",        href: "/audit",             icon: ScrollText,       section: "System", adminOnly: true },
  { label: "Approvals",        href: "/approvals",         icon: CheckCheck,       section: "System" },
  { label: "Approval Workflows", href: "/approvals/workflows", icon: GitBranch,   section: "System", adminOnly: true },
  { label: "Workflow",         href: "/workflow",          icon: GitBranch,        section: "System" },
  { label: "User Guide",       href: "/guide",             icon: HelpCircle,       section: "System" },
  { label: "AI Assistant",     href: "/agent",             icon: Sparkles,         section: "System",    forModule: "ai_assistant" },
  { label: "Settings",         href: "/settings",          icon: Settings,         section: "System" },
  { label: "Add-ons",          href: "/apps",              icon: AppWindow,        section: "System",    adminOnly: true },
  { label: "PRA Dashboard",    href: "/pra-dashboard",     icon: LayoutDashboard,  section: "PRA",       forModule: "pra" },
  { label: "PRA Logs",         href: "/pra-logs",          icon: FileCheck,        section: "PRA",       forModule: "pra" },
  { label: "UAE Dashboard",    href: "/uae",               icon: LayoutDashboard,  section: "UAE",       forModule: "uae_vat" },
  { label: "UAE e-Invoice Logs", href: "/uae/logs",        icon: Landmark,         section: "UAE",       forModule: "uae_vat" },
  { label: "ZATCA Dashboard",  href: "/zatca",             icon: LayoutDashboard,  section: "ZATCA",     forModule: "sa_zatca" },
  { label: "ZATCA Logs",       href: "/zatca/logs",        icon: Landmark,         section: "ZATCA",     forModule: "sa_zatca" },
  { label: "Peppol Dashboard", href: "/peppol",            icon: LayoutDashboard,  section: "Peppol",    forModule: "eu_peppol" },
  { label: "Peppol Logs",      href: "/peppol/logs",       icon: Globe,            section: "Peppol",    forModule: "eu_peppol" },
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
  { label: "Dialysis",          href: "/healthcare/dialysis",     icon: Droplets,     section: "Healthcare", forModule: "healthcare" },
  { label: "HC Store",          href: "/healthcare/store",        icon: Warehouse,    section: "Healthcare", forModule: "healthcare" },
  { label: "HC Reports",        href: "/healthcare/reports",      icon: BarChart2,    section: "Healthcare", forModule: "healthcare" },
  // Weaving
  { label: "Weaving Overview",  href: "/weaving",                 icon: Scissors,      section: "Weaving", forModule: "weaving" },
  { label: "Weaving Setup",     href: "/weaving/setup",           icon: Settings2,     section: "Weaving", forModule: "weaving" },
  { label: "Contracts",         href: "/weaving/contracts",       icon: FileSignature, section: "Weaving", forModule: "weaving" },
  { label: "Yarn Inward",       href: "/weaving/yarn-inward",     icon: PackagePlus,   section: "Weaving", forModule: "weaving" },
  { label: "Sizing",            href: "/weaving/sizing",          icon: Layers,        section: "Weaving", forModule: "weaving" },
  { label: "Production",        href: "/weaving/production",      icon: Factory,       section: "Weaving", forModule: "weaving" },
  { label: "Dispatch",          href: "/weaving/dispatch",        icon: Truck,         section: "Weaving", forModule: "weaving" },
  { label: "Weaving Calc",      href: "/weaving/calculators/weaving", icon: Calculator, section: "Weaving", forModule: "weaving" },
  { label: "Sizing Calc",       href: "/weaving/calculators/sizing",  icon: Calculator, section: "Weaving", forModule: "weaving" },
  { label: "Daily Ops",         href: "/weaving/reports/daily",   icon: Activity,      section: "Weaving", forModule: "weaving" },
  { label: "Contract Control",  href: "/weaving/reports/contract-control", icon: ClipboardList, section: "Weaving", forModule: "weaving" },
  { label: "Customer KPI",      href: "/weaving/reports/customer-kpi", icon: PieChart, section: "Weaving", forModule: "weaving" },
  { label: "Weaving Dashboard", href: "/weaving/dashboard",       icon: LayoutDashboard, section: "Weaving", forModule: "weaving" },
]

export const ALL_SECTIONS = ["Overview","Ledger","Receivable","Payable","Purchases","Store","Inventory","Manufacturing","Telecom","Healthcare","Weaving","Banking","Reports","Payroll","PRA","UAE","ZATCA","Peppol","India GST","System"]

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

// ─── QB-style Top Navigation ─────────────────────────────────────────────────

export type TopNavSection = {
  key: string
  label: string
  /** Shorter label for the crowded top-nav strip; full `label` used in menus. */
  shortLabel?: string
  /** If present, only visible when this module is installed */
  forModule?: "inventory" | "production" | "hrm" | "telecom" | "pra" | "uae_vat" | "sa_zatca" | "in_gst" | "eu_peppol" | "healthcare" | "purchase_store" | "ai_assistant" | "weaving"
}

/** Core sections always shown + module-gated sections shown inline */
export const TOP_NAV: TopNavSection[] = [
  { key: "dashboard",     label: "Dashboard"     },
  { key: "banking",       label: "Banking"       },
  { key: "sales",         label: "Sales"         },
  { key: "purchases",     label: "Purchases"     },
  { key: "accounting",    label: "Accounting"    },
  { key: "reports",       label: "Reports"       },
  { key: "system",        label: "System"        },
  // module-gated — appear inline when installed
  { key: "store",         label: "Store",         forModule: "purchase_store" },
  { key: "inventory",     label: "Inventory",     forModule: "inventory"   },
  { key: "payroll",       label: "Payroll",       forModule: "hrm"         },
  { key: "healthcare",    label: "Healthcare",    forModule: "healthcare"  },
  { key: "weaving",       label: "Weaving",       forModule: "weaving"     },
  { key: "manufacturing", label: "Manufacturing", forModule: "production"  },
  { key: "telecom",       label: "Telecom",       forModule: "telecom"     },
  { key: "pra",           label: "PRA e-Invoice", shortLabel: "PRA", forModule: "pra" },
  { key: "uae",           label: "UAE VAT",       shortLabel: "UAE", forModule: "uae_vat" },
  { key: "zatca",         label: "ZATCA",         shortLabel: "ZATCA", forModule: "sa_zatca" },
  { key: "peppol",        label: "Peppol",        shortLabel: "Peppol", forModule: "eu_peppol" },
  { key: "india_gst",     label: "India GST",     shortLabel: "GST", forModule: "in_gst" },
]

/**
 * Mobile More-drawer section order (user preference):
 * Dashboard → core books → ops → optional industry/localization → System last.
 */
export const MOBILE_MORE_SECTION_ORDER: string[] = [
  "dashboard",
  "accounting",
  "reports",
  "banking",
  "sales",
  "purchases",
  "store",
  "manufacturing",
  "inventory",
  "payroll",
  // optional / module-gated packs
  "healthcare",
  "telecom",
  "weaving",
  "pra",
  "uae",
  "zatca",
  "peppol",
  "india_gst",
  "system",
]

/** TOP_NAV sorted for the sm/md More drawer (unknown keys append at end). */
export function mobileMoreSections(): TopNavSection[] {
  const rank = new Map(MOBILE_MORE_SECTION_ORDER.map((k, i) => [k, i]))
  return [...TOP_NAV].sort((a, b) => {
    const ra = rank.get(a.key) ?? 999
    const rb = rank.get(b.key) ?? 999
    return ra - rb
  })
}

/** Pathname-prefix → top-nav section key mapping */
const SECTION_PREFIXES: Record<string, string[]> = {
  dashboard:     ["/dashboard"],
  banking:       ["/banking", "/bank-accounts", "/bank-book", "/cash-book", "/reconciliations", "/bank-imports", "/exchange-rates"],
  sales:         ["/receivable", "/invoices", "/customers", "/payments-received", "/credit-notes", "/advances", "/commissions", "/promo-discounts", "/aging/receivable"],
  purchases:     ["/payable", "/bills", "/vendors", "/bill-payments", "/debit-notes", "/aging/payable", "/purchases"],
  store:         ["/store"],
  accounting:    ["/entry", "/journal", "/recurring", "/ledger", "/coa", "/analytic-accounts", "/period-close", "/deferred-revenue", "/contract-balances", "/assets", "/leases", "/intercompany"],
  reports:       ["/trial-balance", "/pl", "/reports/dimensional-pl", "/balance", "/consolidation", "/intercompany", "/cashflow", "/tax", "/reports/wht", "/reports/cit-worksheet", "/tax-return", "/budgets", "/customer-performance"],
  inventory:     ["/inventory", "/products"],
  payroll:       ["/hrm", "/payroll", "/employees", "/attendance"],
  healthcare:    ["/healthcare"],
  weaving:       ["/weaving"],
  manufacturing: ["/manufacturing"],
  telecom:       ["/telecom"],
  pra:           ["/pra-dashboard", "/pra-logs"],
  uae:           ["/uae"],
  zatca:         ["/zatca"],
  peppol:        ["/peppol"],
  india_gst:     ["/india-gst"],
  system:        ["/settings", "/team", "/practice", "/profile", "/imports", "/guide", "/apps", "/payment-terms", "/tax-codes", "/audit", "/approvals", "/workflow", "/agent"],
}

/** Routes homed under /manufacturing that move to the Purchases section when purchase_store is installed */
const PURCHASE_DUAL_HOMED = ["/manufacturing/purchase-orders", "/manufacturing/grn"]

/** Returns the top-nav section key for the current pathname */
export function getActiveSection(pathname: string, installed?: Set<string>): string {
  if (
    installed?.has("purchase_store") &&
    PURCHASE_DUAL_HOMED.some(p => pathname === p || pathname.startsWith(p + "/"))
  ) {
    return "purchases"
  }
  for (const [section, prefixes] of Object.entries(SECTION_PREFIXES)) {
    if (prefixes.some(p => pathname === p || pathname.startsWith(p + "/"))) {
      return section
    }
  }
  return "dashboard"
}

/** Default landing href when a top-nav section is clicked — points to the hub/overview page */
export function getSectionHref(key: string): string {
  const map: Record<string, string> = {
    dashboard:     "/dashboard",
    banking:       "/banking",
    sales:         "/receivable",
    purchases:     "/purchases",
    store:         "/store/gate-outward",
    accounting:    "/entry",
    reports:       "/trial-balance",
    inventory:     "/inventory",
    payroll:       "/hrm",
    healthcare:    "/healthcare",
    weaving:       "/weaving",
    manufacturing: "/manufacturing",
    telecom:       "/telecom",
    pra:           "/pra-dashboard",
    uae:           "/uae",
    zatca:         "/zatca",
    peppol:        "/peppol",
    india_gst:     "/india-gst",
    system:        "/settings",
  }
  return map[key] ?? "/dashboard"
}

/** Sub-navigation items grouped by top-nav section key */
export const SUB_NAV: Record<string, NavItem[]> = {
  dashboard: [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, section: "dashboard" },
  ],
  banking: [
    { label: "Bank Accounts",   href: "/bank-accounts",   icon: Landmark,   section: "banking" },
    { label: "Bank Book",       href: "/bank-book",       icon: BookOpen,   section: "banking" },
    { label: "Cash Book",       href: "/cash-book",       icon: Wallet,     section: "banking" },
    { label: "Reconciliations", href: "/reconciliations", icon: CheckCheck, section: "banking" },
    { label: "Bank Imports",    href: "/bank-imports",    icon: Upload,     section: "banking" },
    { label: "Bank Rules",      href: "/bank-imports/rules", icon: Tags,  section: "banking" },
    { label: "Exchange Rates",  href: "/exchange-rates",  icon: TrendingUp, section: "banking" },
  ],
  sales: [
    { label: "Customers",         href: "/customers",         icon: Users,         section: "sales" },
    { label: "Invoices",          href: "/invoices",          icon: FileSignature, section: "sales" },
    { label: "Payments Received", href: "/payments-received", icon: ArrowDownLeft, section: "sales" },
    { label: "Credit Notes",      href: "/credit-notes",      icon: Receipt,       section: "sales" },
    { label: "Advances",          href: "/advances",          icon: Wallet,        section: "sales" },
    { label: "Commissions",       href: "/commissions",       icon: Percent,       section: "sales" },
    { label: "Promo Discounts",   href: "/promo-discounts",   icon: Tags,          section: "sales" },
    { label: "AR Aging",          href: "/aging/receivable",  icon: Clock,         section: "sales" },
  ],
  purchases: [
    { label: "Vendors",       href: "/vendors",       icon: Truck,        section: "purchases" },
    { label: "Bills",         href: "/bills",         icon: Receipt,      section: "purchases" },
    { label: "Bill Payments", href: "/bill-payments", icon: ArrowUpRight, section: "purchases" },
    { label: "Debit Notes",   href: "/debit-notes",   icon: Undo2,        section: "purchases" },
    { label: "AP Aging",      href: "/aging/payable", icon: Clock,        section: "purchases" },
    { label: "Demands",         href: "/purchases/demands",             icon: ClipboardCheck, section: "purchases", forModule: "purchase_store" },
    { label: "Comparatives",    href: "/purchases/comparatives",        icon: Scale,          section: "purchases", forModule: "purchase_store" },
    { label: "Gate Inward",     href: "/purchases/gate-inward",         icon: DoorOpen,       section: "purchases", forModule: "purchase_store" },
    { label: "Gate Register",   href: "/purchases/gate-register",       icon: ScrollText,     section: "purchases", forModule: "purchase_store" },
    { label: "3-Way Match",     href: "/purchases/three-way-match",     icon: CheckCheck,     section: "purchases", forModule: "purchase_store" },
    { label: "Vendor Performance", href: "/purchases/vendor-performance", icon: TrendingUp,   section: "purchases", forModule: "purchase_store" },
    { label: "Purchase Orders", href: "/manufacturing/purchase-orders", icon: ShoppingCart,   section: "purchases", forModule: "purchase_store" },
    { label: "Goods Receipt",   href: "/manufacturing/grn",             icon: PackagePlus,    section: "purchases", forModule: "purchase_store" },
  ],
  store: [
    { label: "Gate Outward",     href: "/store/gate-outward",            icon: DoorOpen,   section: "store", forModule: "purchase_store" },
    { label: "Outward Register", href: "/store/gate-outward-register",   icon: ScrollText, section: "store", forModule: "purchase_store" },
    { label: "Dispatch Recon",   href: "/store/dispatch-reconciliation", icon: CheckCheck, section: "store", forModule: "purchase_store" },
    { label: "Store Issues",     href: "/store/issues",                  icon: PackageMinus, section: "store", forModule: "purchase_store" },
    { label: "Issue Register",   href: "/store/issue-register",          icon: ScrollText, section: "store", forModule: "purchase_store" },
    { label: "Stock Tie-Out",    href: "/store/stock-tie-out",           icon: CheckCheck, section: "store", forModule: "purchase_store" },
  ],
  accounting: [
    { label: "New Entry",         href: "/entry",             icon: PlusCircle,      section: "accounting" },
    { label: "Journal",           href: "/journal",           icon: ClipboardList,   section: "accounting" },
    { label: "Recurring",         href: "/recurring",         icon: RefreshCw,       section: "accounting" },
    { label: "General Ledger",    href: "/ledger",            icon: BookOpen,        section: "accounting" },
    { label: "Chart of Accounts", href: "/coa",               icon: TableProperties, section: "accounting" },
    { label: "Analytic Accounts", href: "/analytic-accounts", icon: Layers,          section: "accounting" },
    { label: "Period Close",      href: "/period-close",      icon: CalendarCheck,   section: "accounting" },
    { label: "Deferred Revenue",  href: "/deferred-revenue",  icon: Play,            section: "accounting" },
    { label: "Contract Balances", href: "/contract-balances", icon: FileSpreadsheet, section: "accounting" },
    { label: "Fixed Assets",      href: "/assets",            icon: Building2,       section: "accounting" },
    { label: "Asset Rollforward", href: "/assets/rollforward", icon: Table2,         section: "accounting" },
    { label: "Leases",            href: "/leases",            icon: KeyRound,        section: "accounting" },
    { label: "IC Reconciliation", href: "/intercompany/recon", icon: GitCompareArrows, section: "accounting" },
  ],
  reports: [
    // Financial Statements
    { label: "Trial Balance",    href: "/trial-balance",        icon: Scale,      section: "reports" },
    { label: "Income Statement", href: "/pl",                   icon: TrendingUp, section: "reports" },
    { label: "Dimensional P&L",  href: "/reports/dimensional-pl", icon: Layers,   section: "reports" },
    { label: "Balance Sheet",    href: "/balance",              icon: PieChart,   section: "reports" },
    { label: "Consolidation",    href: "/consolidation",        icon: Network,    section: "reports" },
    { label: "IC Reconciliation", href: "/intercompany/recon",  icon: GitCompareArrows, section: "reports" },
    { label: "Cash Flow",        href: "/cashflow",             icon: FileText,   section: "reports" },
    // Management Reports
    { label: "Tax Reports",      href: "/tax",                  icon: Percent,    section: "reports" },
    { label: "Withholding Tax",  href: "/reports/wht",          icon: Percent,    section: "reports" },
    { label: "CIT Worksheet",    href: "/reports/cit-worksheet", icon: FileSpreadsheet, section: "reports" },
    { label: "GSTR Report",      href: "/india-gst/gstr",       icon: FileSpreadsheet, section: "reports", forModule: "in_gst" },
    { label: "Tax Return",       href: "/tax-return",           icon: Percent,    section: "reports" },
    { label: "Budget vs Actual", href: "/budgets",              icon: TrendingUp, section: "reports" },
    { label: "Customer Perf.",   href: "/customer-performance", icon: TrendingUp, section: "reports" },
  ],
  inventory: [
    { label: "Products",           href: "/products",              icon: Package,  section: "inventory", forModule: "inventory" },
    { label: "Product Categories", href: "/products/categories",   icon: Tags,     section: "inventory", forModule: "inventory" },
    { label: "Product Ledger",     href: "/products/ledger",       icon: BookOpen, section: "inventory", forModule: "inventory" },
    { label: "Inventory Report",   href: "/inventory/performance", icon: PieChart, section: "inventory", forModule: "inventory" },
    { label: "Valuation",          href: "/inventory/valuation",   icon: Scale,    section: "inventory", forModule: "inventory" },
  ],
  payroll: [
    { label: "Overview",          href: "/hrm",                icon: LayoutGrid,   section: "payroll", forModule: "hrm" },
    { label: "Payroll Runs",      href: "/payroll",            icon: Briefcase,    section: "payroll", forModule: "hrm" },
    { label: "Employees",         href: "/employees",          icon: UserCog,      section: "payroll", forModule: "hrm" },
    { label: "Attendance",        href: "/attendance",         icon: CalendarDays, section: "payroll", forModule: "hrm" },
    { label: "Salary Components", href: "/payroll/components", icon: Settings2,    section: "payroll", forModule: "hrm" },
  ],
  healthcare: [
    { label: "Overview",       href: "/healthcare",            icon: Stethoscope,  section: "healthcare", forModule: "healthcare" },
    { label: "Patients",       href: "/healthcare/patients",   icon: FileHeart,    section: "healthcare", forModule: "healthcare" },
    { label: "Doctors",        href: "/healthcare/doctors",    icon: UserRound,    section: "healthcare", forModule: "healthcare" },
    { label: "OPD",            href: "/healthcare/opd",        icon: Activity,     section: "healthcare", forModule: "healthcare" },
    { label: "IPD / Inpatient",href: "/healthcare/ipd",        icon: BedDouble,    section: "healthcare", forModule: "healthcare" },
    { label: "Laboratory",     href: "/healthcare/lab",        icon: FlaskConical, section: "healthcare", forModule: "healthcare" },
    { label: "Lab Tests",      href: "/healthcare/lab/tests",  icon: FlaskConical, section: "healthcare", forModule: "healthcare" },
    { label: "Procedures",     href: "/healthcare/procedures", icon: Syringe,      section: "healthcare", forModule: "healthcare" },
    { label: "Dialysis",       href: "/healthcare/dialysis",   icon: Droplets,     section: "healthcare", forModule: "healthcare" },
    { label: "HC Store",       href: "/healthcare/store",      icon: Warehouse,    section: "healthcare", forModule: "healthcare" },
    { label: "HC Reports",     href: "/healthcare/reports",    icon: BarChart2,    section: "healthcare", forModule: "healthcare" },
  ],
  weaving: [
    { label: "Overview",         href: "/weaving",              icon: Scissors,       section: "weaving", forModule: "weaving" },
    { label: "Setup",            href: "/weaving/setup",        icon: Settings2,      section: "weaving", forModule: "weaving" },
    { label: "Contracts",        href: "/weaving/contracts",    icon: FileSignature,  section: "weaving", forModule: "weaving" },
    { label: "Yarn Inward",      href: "/weaving/yarn-inward",  icon: PackagePlus,    section: "weaving", forModule: "weaving" },
    { label: "Sizing",           href: "/weaving/sizing",       icon: Layers,         section: "weaving", forModule: "weaving" },
    { label: "Production",       href: "/weaving/production",   icon: Factory,        section: "weaving", forModule: "weaving" },
    { label: "Dispatch",         href: "/weaving/dispatch",     icon: Truck,          section: "weaving", forModule: "weaving" },
    { label: "Weaving Calc",     href: "/weaving/calculators/weaving", icon: Calculator, section: "weaving", forModule: "weaving" },
    { label: "Sizing Calc",      href: "/weaving/calculators/sizing",  icon: Calculator, section: "weaving", forModule: "weaving" },
    { label: "Daily Ops",        href: "/weaving/reports/daily", icon: Activity,      section: "weaving", forModule: "weaving" },
    { label: "Contract Control", href: "/weaving/reports/contract-control", icon: ClipboardList, section: "weaving", forModule: "weaving" },
    { label: "Customer KPI",     href: "/weaving/reports/customer-kpi", icon: PieChart, section: "weaving", forModule: "weaving" },
    { label: "Dashboard",        href: "/weaving/dashboard",    icon: LayoutDashboard, section: "weaving", forModule: "weaving" },
  ],
  manufacturing: [
    { label: "Production Floor",  href: "/manufacturing",                   icon: Factory,      section: "manufacturing", forModule: "production" },
    { label: "Bills of Material", href: "/manufacturing/boms",              icon: ListChecks,   section: "manufacturing", forModule: "production" },
    { label: "Rate Plans",        href: "/manufacturing/rate-plans",        icon: Tags,         section: "manufacturing", forModule: "production" },
    { label: "Purchase Orders",   href: "/manufacturing/purchase-orders",   icon: ShoppingCart, section: "manufacturing", forModule: "production", notForModule: "purchase_store" },
    { label: "Stock Locations",   href: "/manufacturing/stock-locations",   icon: Warehouse,    section: "manufacturing", forModule: "production" },
    { label: "Goods Receipt",     href: "/manufacturing/grn",               icon: PackagePlus,  section: "manufacturing", forModule: "production", notForModule: "purchase_store" },
    { label: "Production Orders", href: "/manufacturing/production-orders", icon: Warehouse,    section: "manufacturing", forModule: "production" },
    { label: "Scrap Reasons",     href: "/manufacturing/scrap-reasons",     icon: AlertTriangle, section: "manufacturing", forModule: "production" },
    { label: "Mfg Reports",       href: "/manufacturing/reports",           icon: BarChart2,    section: "manufacturing", forModule: "production" },
  ],
  telecom: [
    { label: "Overview",          href: "/telecom",              icon: Radio,       section: "telecom", forModule: "telecom" },
    { label: "Tracker & Load",    href: "/telecom/tracker",      icon: Wallet,      section: "telecom", forModule: "telecom" },
    { label: "RSO Channel",       href: "/telecom/rso",          icon: Network,     section: "telecom", forModule: "telecom" },
    { label: "SIM & Activations", href: "/telecom/sim",          icon: Smartphone,  section: "telecom", forModule: "telecom" },
    { label: "FCA & Targets",     href: "/telecom/fca",          icon: Target,      section: "telecom", forModule: "telecom" },
    { label: "Mobile Money",      href: "/telecom/mobile-money", icon: Banknote,    section: "telecom", forModule: "telecom" },
    { label: "Postpaid Billing",  href: "/telecom/postpaid",     icon: ReceiptText, section: "telecom", forModule: "telecom" },
    { label: "Commissions",       href: "/telecom/commissions",  icon: Percent,     section: "telecom", forModule: "telecom" },
    { label: "Franchise Admin",   href: "/telecom/franchise",    icon: ScrollText,  section: "telecom", forModule: "telecom" },
    { label: "Devices (IMEI)",    href: "/telecom/devices",      icon: Tablet,      section: "telecom", forModule: "telecom" },
  ],
  pra: [
    { label: "PRA Dashboard", href: "/pra-dashboard", icon: LayoutDashboard, section: "pra", forModule: "pra" },
    { label: "PRA Logs",      href: "/pra-logs",      icon: FileCheck,       section: "pra", forModule: "pra" },
  ],
  uae: [
    { label: "UAE Dashboard", href: "/uae",      icon: LayoutDashboard, section: "uae", forModule: "uae_vat" },
    { label: "UAE Logs",      href: "/uae/logs", icon: Landmark,        section: "uae", forModule: "uae_vat" },
  ],
  zatca: [
    { label: "ZATCA Dashboard", href: "/zatca",      icon: LayoutDashboard, section: "zatca", forModule: "sa_zatca" },
    { label: "ZATCA Logs",      href: "/zatca/logs", icon: Landmark,        section: "zatca", forModule: "sa_zatca" },
  ],
  peppol: [
    { label: "Peppol Dashboard", href: "/peppol",      icon: LayoutDashboard, section: "peppol", forModule: "eu_peppol" },
    { label: "Peppol Logs",      href: "/peppol/logs", icon: Globe,           section: "peppol", forModule: "eu_peppol" },
  ],
  india_gst: [
    { label: "GST Dashboard", href: "/india-gst",      icon: LayoutDashboard, section: "india_gst", forModule: "in_gst" },
    { label: "GSTR Report",   href: "/india-gst/gstr", icon: FileSpreadsheet, section: "india_gst", forModule: "in_gst" },
  ],
  system: [
    { label: "Settings",      href: "/settings",             icon: Settings,    section: "system" },
    { label: "Team",          href: "/team",                 icon: UsersRound,  section: "system", adminOnly: true },
    { label: "Practice clients", href: "/practice",          icon: Building2,   section: "system" },
    { label: "Permissions",   href: "/settings/permissions", icon: ShieldCheck, section: "system", adminOnly: true },
    { label: "My Profile",    href: "/profile",              icon: UserCircle,  section: "system" },
    { label: "CSV Import",    href: "/imports",              icon: Upload,      section: "system" },
    { label: "Payment Terms", href: "/payment-terms",        icon: Clock,       section: "system", adminOnly: true },
    { label: "Tax Codes",     href: "/tax-codes",            icon: Percent,     section: "system", adminOnly: true },
    { label: "Approvals",     href: "/approvals",            icon: CheckCheck,  section: "system" },
    { label: "Approval Workflows", href: "/approvals/workflows", icon: GitBranch, section: "system", adminOnly: true },
    { label: "Audit Log",     href: "/audit",                icon: ScrollText,  section: "system", adminOnly: true },
    { label: "Workflow",      href: "/workflow",             icon: GitBranch,   section: "system" },
    { label: "User Guide",    href: "/guide",                icon: HelpCircle,  section: "system" },
    { label: "AI Assistant",  href: "/agent",                icon: Sparkles,    section: "system", forModule: "ai_assistant" },
  ],
}
