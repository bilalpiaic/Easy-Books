"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  LayoutDashboard, PlusCircle, ClipboardList, BookOpen, TableProperties,
  Scale, FileText, PieChart, TrendingUp, LogOut, FileSignature, Users,
  ArrowDownLeft, Receipt, Truck, ArrowUpRight, Landmark, CheckCheck,
  Percent, Settings, X, Package, ChevronRight, GitBranch, HelpCircle,
  Factory, ListChecks, Tags, PackagePlus, Warehouse,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getCurrentUser, removeAuthToken } from "@/lib/auth"
import { apiFetch } from "@/lib/api"
import BottomNav from "./BottomNav"

type NavItem = {
  label: string
  href: string
  icon: React.ElementType
  section: string
  /** When set, item is only shown if the tenant's business_model matches. */
  forModel?: "manufacturing"
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
  { label: "Bank Accounts",    href: "/bank-accounts",     icon: Landmark,         section: "Banking" },
  { label: "Reconciliations",  href: "/reconciliations",   icon: CheckCheck,       section: "Banking" },
  { label: "Trial Balance",    href: "/trial-balance",     icon: Scale,            section: "Reports" },
  { label: "Income Statement", href: "/pl",                icon: TrendingUp,       section: "Reports" },
  { label: "Balance Sheet",    href: "/balance",           icon: PieChart,         section: "Reports" },
  { label: "Cash Flow",        href: "/cashflow",          icon: FileText,         section: "Reports" },
  { label: "Tax Reports",      href: "/tax",               icon: Percent,          section: "Reports" },
  { label: "Workflow",          href: "/workflow",          icon: GitBranch,        section: "System" },
  { label: "User Guide",        href: "/guide",             icon: HelpCircle,       section: "System" },
  { label: "Settings",          href: "/settings",          icon: Settings,         section: "System" },
]

const ALL_SECTIONS = ["Overview","Ledger","Receivable","Payable","Manufacturing","Banking","Reports","System"]

const SECTION_COLORS: Record<string, string> = {
  Overview:      "text-[#ffd966]",
  Ledger:        "text-blue-400",
  Receivable:    "text-green-400",
  Payable:       "text-orange-400",
  Manufacturing: "text-pink-400",
  Banking:       "text-purple-400",
  Reports:       "text-cyan-400",
  System:        "text-white/40",
}

type Me = { tenant?: { business_model?: string } }

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [orgName, setOrgName]     = useState("Easy-Books")
  const [drawerOpen, setDrawer]   = useState(false)
  const [userName, setUserName]   = useState("User")
  const [userInitial, setInitial] = useState("U")
  const [businessModel, setBusinessModel] = useState<string>("simple")

  useEffect(() => {
    const user = getCurrentUser()
    if (user) { setUserName(user.full_name); setInitial(user.full_name.charAt(0).toUpperCase()) }
    apiFetch<Record<string,string>>("/api/settings")
      .then(d => { if (d?.company_name) setOrgName(d.company_name) })
      .catch(() => {})
    apiFetch<Me>("/api/auth/me")
      .then(d => { if (d?.tenant?.business_model) setBusinessModel(d.tenant.business_model) })
      .catch(() => {})
  }, [])

  // Filter NAV by business_model + filter sections to those that have items.
  const visibleNav = NAV.filter(i => !i.forModel || i.forModel === businessModel)
  const SECTIONS = ALL_SECTIONS.filter(s => visibleNav.some(i => i.section === s))

  const logout = () => {
    if (!window.confirm("Log out?")) return
    removeAuthToken(); router.push("/login")
  }

  const go = (href: string) => { router.push(href); setDrawer(false) }

  return (
    <>
      {/* ── Desktop icon rail ── */}
      <aside className="hidden md:flex flex-col items-center w-[60px] bg-[#1a1814] border-r border-white/5 py-3 gap-1 shrink-0 z-30">
        <button
          onClick={() => router.push("/dashboard")}
          className="w-10 h-10 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-base mb-2 hover:bg-[#d4af60] transition-colors"
          title={orgName}
        >
          {orgName.charAt(0)}
        </button>

        <nav className="flex-1 flex flex-col gap-0.5 items-center overflow-y-auto scrollbar-hide w-full px-1">
          {visibleNav.map(item => {
            const active = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.label}
                className={cn(
                  "w-full flex items-center justify-center h-9 rounded-lg transition-all duration-150 relative group",
                  active
                    ? "bg-[#b8943f]/20 text-[#ffd966]"
                    : "text-white/40 hover:text-white/80 hover:bg-white/5"
                )}
              >
                <item.icon className="w-4 h-4" />
                {active && <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-[#b8943f] rounded-r-full" />}
                <span className="absolute left-full ml-2 px-2 py-1 bg-[#1a1814] border border-white/10 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 shadow-xl transition-opacity">
                  {item.label}
                </span>
              </Link>
            )
          })}
        </nav>

        <div className="flex flex-col gap-1 items-center pb-1 w-full px-1">
          <div className="w-8 h-8 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-xs" title={userName}>
            {userInitial}
          </div>
          <button onClick={logout} title="Log out"
            className="w-full flex items-center justify-center h-9 rounded-lg text-white/40 hover:text-red-400 hover:bg-white/5 transition-all">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* ── Desktop expanded panel (xl+) ── */}
      <aside className="hidden xl:flex flex-col w-56 bg-[#1a1814] border-r border-white/5 shrink-0 z-30">
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-white/5">
          <div className="w-8 h-8 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold flex-shrink-0">
            {orgName.charAt(0)}
          </div>
          <span className="font-serif text-white text-sm truncate font-medium" title={orgName}>{orgName}</span>
        </div>

        <nav className="flex-1 overflow-y-auto py-2 scrollbar-hide">
          {SECTIONS.map(section => (
            <div key={section} className="mb-1">
              <div className={cn("px-4 pt-3 pb-1 text-[9px] font-bold uppercase tracking-[0.15em]", SECTION_COLORS[section])}>
                {section}
              </div>
              {visibleNav.filter(i => i.section === section).map(item => {
                const active = pathname === item.href
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2.5 px-4 py-2 text-[13px] font-medium transition-all duration-150 relative",
                      active
                        ? "bg-[#b8943f]/15 text-[#ffd966] border-l-2 border-[#b8943f]"
                        : "text-white/55 hover:text-white hover:bg-white/5 border-l-2 border-transparent"
                    )}
                  >
                    <item.icon className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>

        <div className="px-4 py-3 border-t border-white/5 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-xs flex-shrink-0">
              {userInitial}
            </div>
            <span className="text-white/60 text-xs truncate">{userName}</span>
          </div>
          <button onClick={logout} className="text-white/30 hover:text-red-400 transition-colors p-1">
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </aside>

      {/* ── Mobile: bottom nav ── */}
      <BottomNav onMore={() => setDrawer(true)} />

      {/* ── Mobile: full drawer ── */}
      {drawerOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setDrawer(false)} />
          <div className="relative w-72 bg-[#1a1814] h-full flex flex-col shadow-2xl overflow-y-auto">
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold">
                  {orgName.charAt(0)}
                </div>
                <span className="font-serif text-white font-bold truncate">{orgName}</span>
              </div>
              <button onClick={() => setDrawer(false)} className="text-white/50 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <nav className="flex-1 py-2">
              {SECTIONS.map(section => (
                <div key={section} className="mb-1">
                  <div className={cn("px-5 pt-3 pb-1 text-[9px] font-bold uppercase tracking-[0.15em]", SECTION_COLORS[section])}>
                    {section}
                  </div>
                  {visibleNav.filter(i => i.section === section).map(item => {
                    const active = pathname === item.href
                    return (
                      <button
                        key={item.href}
                        onClick={() => go(item.href)}
                        className={cn(
                          "w-full flex items-center gap-3 px-5 py-2.5 text-sm font-medium transition-all border-l-2",
                          active
                            ? "bg-[#b8943f]/20 text-[#ffd966] border-[#b8943f]"
                            : "text-white/65 hover:text-white hover:bg-white/5 border-transparent"
                        )}
                      >
                        <item.icon className="w-4 h-4 flex-shrink-0" />
                        <span>{item.label}</span>
                        {active && <ChevronRight className="w-3.5 h-3.5 ml-auto opacity-60" />}
                      </button>
                    )
                  })}
                </div>
              ))}
            </nav>

            <div className="px-5 py-4 border-t border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-sm">
                  {userInitial}
                </div>
                <div>
                  <p className="text-white text-sm font-medium">{userName}</p>
                  <p className="text-white/40 text-[10px]">Admin</p>
                </div>
              </div>
              <button onClick={logout} className="text-white/40 hover:text-red-400 p-1.5">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
