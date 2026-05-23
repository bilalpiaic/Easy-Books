"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  LayoutDashboard, PlusCircle, ClipboardList, BookOpen, TableProperties,
  Scale, FileText, PieChart, TrendingUp, LogOut, FileSignature, Users,
  ArrowDownLeft, Receipt, Truck, ArrowUpRight, Landmark, CheckCheck,
  Percent, Settings, X, Package, ChevronRight, GitBranch, HelpCircle,
  Factory, ListChecks, Tags, PackagePlus, Warehouse, Pin, PinOff,
  Signal, Wallet, ArrowRightLeft, Banknote, Smartphone, Target,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getCurrentUser, removeAuthToken } from "@/lib/auth"
import { apiFetch } from "@/lib/api"

type NavItem = {
  label: string
  href: string
  icon: React.ElementType
  section: string
  forModel?: "manufacturing" | "telecom_franchise"
}

const NAV: NavItem[] = [
  { label: "Dashboard",        href: "/dashboard",         icon: LayoutDashboard,  section: "Overview" },
  { label: "New Entry",        href: "/entry",             icon: PlusCircle,       section: "Ledger" },
  { label: "Journal",          href: "/journal",           icon: ClipboardList,    section: "Ledger" },
  { label: "General Ledger",   href: "/ledger",            icon: BookOpen,         section: "Ledger" },
  { label: "Chart of Accounts",href: "/coa",               icon: TableProperties,  section: "Ledger" },
  { label: "Invoices",         href: "/invoices",          icon: FileSignature,    section: "Receivable" },
  { label: "Customers",        href: "/customers",         icon: Users,            section: "Receivable" },
  { label: "Payments Received",href: "/payments-received", icon: ArrowDownLeft,    section: "Receivable" },
  { label: "Bills",            href: "/bills",             icon: Receipt,          section: "Payable" },
  { label: "Vendors",          href: "/vendors",           icon: Truck,            section: "Payable" },
  { label: "Bill Payments",    href: "/bill-payments",     icon: ArrowUpRight,     section: "Payable" },
  { label: "Products",         href: "/products",          icon: Package,          section: "Payable" },
  { label: "Production Floor", href: "/manufacturing",     icon: Factory,          section: "Manufacturing", forModel: "manufacturing" },
  { label: "Bills of Material",href: "/manufacturing/boms",icon: ListChecks,       section: "Manufacturing", forModel: "manufacturing" },
  { label: "Rate Plans",       href: "/manufacturing/rate-plans", icon: Tags,      section: "Manufacturing", forModel: "manufacturing" },
  { label: "Goods Receipt",    href: "/manufacturing/grn", icon: PackagePlus,      section: "Manufacturing", forModel: "manufacturing" },
  { label: "Production Orders",href: "/manufacturing/production-orders", icon: Warehouse, section: "Manufacturing", forModel: "manufacturing" },
  { label: "Telecom Dashboard",href: "/telecom",                    icon: Signal,          section: "Telecom", forModel: "telecom_franchise" },
  { label: "Tracker & Load",   href: "/telecom/tracker",            icon: Wallet,          section: "Telecom", forModel: "telecom_franchise" },
  { label: "RSO Agents",       href: "/telecom/rso/agents",         icon: Users,           section: "Telecom", forModel: "telecom_franchise" },
  { label: "Load Transfers",   href: "/telecom/rso/transfers",      icon: ArrowRightLeft,  section: "Telecom", forModel: "telecom_franchise" },
  { label: "Daily Collections",href: "/telecom/rso/collections",    icon: Banknote,        section: "Telecom", forModel: "telecom_franchise" },
  { label: "SIM Batches",      href: "/telecom/sim/batches",        icon: Smartphone,      section: "Telecom", forModel: "telecom_franchise" },
  { label: "SIM Sales",        href: "/telecom/sim/sales",          icon: Package,         section: "Telecom", forModel: "telecom_franchise" },
  { label: "FCA & KPI Targets",href: "/telecom/fca",                icon: Target,          section: "Telecom", forModel: "telecom_franchise" },
  { label: "Bank Accounts",    href: "/bank-accounts",     icon: Landmark,         section: "Banking" },
  { label: "Reconciliations",  href: "/reconciliations",   icon: CheckCheck,       section: "Banking" },
  { label: "Trial Balance",    href: "/trial-balance",     icon: Scale,            section: "Reports" },
  { label: "Income Statement", href: "/pl",                icon: TrendingUp,       section: "Reports" },
  { label: "Balance Sheet",    href: "/balance",           icon: PieChart,         section: "Reports" },
  { label: "Cash Flow",        href: "/cashflow",          icon: FileText,         section: "Reports" },
  { label: "Tax Reports",      href: "/tax",               icon: Percent,          section: "Reports" },
  { label: "Workflow",         href: "/workflow",          icon: GitBranch,        section: "System" },
  { label: "User Guide",       href: "/guide",             icon: HelpCircle,       section: "System" },
  { label: "Settings",         href: "/settings",          icon: Settings,         section: "System" },
]

const ALL_SECTIONS = ["Overview","Ledger","Receivable","Payable","Manufacturing","Telecom","Banking","Reports","System"]

const SECTION_COLORS: Record<string, string> = {
  Overview:      "text-[#ffd966]",
  Ledger:        "text-blue-400",
  Receivable:    "text-green-400",
  Payable:       "text-orange-400",
  Manufacturing: "text-pink-400",
  Telecom:       "text-emerald-400",
  Banking:       "text-purple-400",
  Reports:       "text-cyan-400",
  System:        "text-white/40",
}

type Me = { tenant?: { business_model?: string } }

interface SidebarProps {
  /** Drawer is shown when true; closed when false. Caller controls. */
  open: boolean
  onClose: () => void
  /** When true (md+ only), the sidebar takes part in layout flow instead
   *  of overlaying. Mobile always overlays regardless. */
  pinned: boolean
  onTogglePinned: () => void
}

export default function Sidebar({ open, onClose, pinned, onTogglePinned }: SidebarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const [orgName, setOrgName]     = useState("Easy-Books")
  const [userName, setUserName]   = useState("User")
  const [userInitial, setInitial] = useState("U")
  const [businessModel, setBusinessModel] = useState<string>("simple")

  useEffect(() => {
    const user = getCurrentUser()
    if (user) {
      setUserName(user.full_name)
      setInitial(user.full_name.charAt(0).toUpperCase())
    }
    apiFetch<Record<string,string>>("/api/settings")
      .then(d => { if (d?.company_name) setOrgName(d.company_name) })
      .catch(() => {})
    apiFetch<Me>("/api/auth/me")
      .then(d => { if (d?.tenant?.business_model) setBusinessModel(d.tenant.business_model) })
      .catch(() => {})
  }, [])

  const visibleNav = NAV.filter(i => !i.forModel || i.forModel === businessModel)
  const SECTIONS = ALL_SECTIONS.filter(s => visibleNav.some(i => i.section === s))

  const logout = () => {
    if (!window.confirm("Log out?")) return
    removeAuthToken(); router.push("/login")
  }

  const go = (href: string) => {
    router.push(href)
    // On mobile / unpinned mode, close the drawer after navigation so the
    // user can see the page. Pinned-mode keeps it open as a static panel.
    if (!pinned) onClose()
  }

  // ── A single drawer component used at every size ──────────────────────────
  // - When closed: a thin gold "open menu" tab is shown on the left edge so
  //   the user can always re-open without going via the header hamburger.
  // - When open + pinned (md+): the drawer sits in the document flow at 260px
  //   wide, content sits next to it.
  // - When open + unpinned: the drawer overlays content with a backdrop.

  const drawerWidth = "w-[260px]"

  return (
    <>
      {/* Static placeholder so flex/layout reserves the sidebar width when
          pinned. The actual drawer below is fixed-positioned. */}
      {pinned && open && (
        <div className={`hidden md:block ${drawerWidth} shrink-0`} aria-hidden />
      )}

      {/* Backdrop — only when overlaying (mobile OR unpinned) */}
      {open && (
        <button
          aria-label="Close menu"
          onClick={onClose}
          className={cn(
            "fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity",
            pinned && "md:hidden"
          )}
        />
      )}

      {/* The drawer itself */}
      <aside
        className={cn(
          "fixed top-0 left-0 h-full bg-[#1a1814] border-r border-white/5 z-50 flex flex-col shadow-2xl",
          drawerWidth,
          "transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "-translate-x-full"
        )}
        aria-hidden={!open}
      >
        {/* Header row inside drawer */}
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-white/10 shrink-0">
          <button
            onClick={() => { router.push("/dashboard"); if (!pinned) onClose() }}
            className="w-8 h-8 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-sm hover:bg-[#d4af60] transition-colors"
            title={orgName}
          >
            {orgName.charAt(0)}
          </button>
          <span className="flex-1 font-serif text-white text-sm truncate font-semibold" title={orgName}>
            {orgName}
          </span>
          {/* Pin toggle — only meaningful on md+ */}
          <button
            onClick={onTogglePinned}
            title={pinned ? "Unpin sidebar" : "Pin sidebar open"}
            className="hidden md:inline-flex w-7 h-7 items-center justify-center rounded-md text-white/40 hover:text-[#ffd966] hover:bg-white/5 transition"
          >
            {pinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={onClose}
            title="Close menu"
            className="w-7 h-7 inline-flex items-center justify-center rounded-md text-white/40 hover:text-white hover:bg-white/5 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2 scrollbar-hide">
          {SECTIONS.map(section => (
            <div key={section} className="mb-1">
              <div className={cn("px-4 pt-3 pb-1 text-[9px] font-bold uppercase tracking-[0.15em]", SECTION_COLORS[section])}>
                {section}
              </div>
              {visibleNav.filter(i => i.section === section).map(item => {
                const active = pathname === item.href
                return (
                  <button
                    key={item.href}
                    onClick={() => go(item.href)}
                    className={cn(
                      "w-full text-left flex items-center gap-2.5 px-4 py-2 text-[13px] font-medium transition-all border-l-2",
                      active
                        ? "bg-[#b8943f]/15 text-[#ffd966] border-[#b8943f]"
                        : "text-white/60 hover:text-white hover:bg-white/5 border-transparent"
                    )}
                  >
                    <item.icon className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="truncate flex-1">{item.label}</span>
                    {active && <ChevronRight className="w-3.5 h-3.5 opacity-60 flex-shrink-0" />}
                  </button>
                )
              })}
            </div>
          ))}
        </nav>

        {/* Footer: user + logout */}
        <div className="px-4 py-3 border-t border-white/10 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-xs flex-shrink-0">
              {userInitial}
            </div>
            <div className="min-w-0">
              <p className="text-white text-xs font-medium truncate">{userName}</p>
              <p className="text-white/40 text-[10px]">Admin</p>
            </div>
          </div>
          <button
            onClick={logout}
            title="Log out"
            className="w-7 h-7 inline-flex items-center justify-center rounded-md text-white/40 hover:text-red-400 hover:bg-white/5 transition"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </aside>
    </>
  )
}
