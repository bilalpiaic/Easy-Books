"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  LayoutDashboard,
  PlusCircle,
  ClipboardList,
  BookOpen,
  TableProperties,
  Scale,
  FileText,
  PieChart,
  TrendingUp,
  LogOut,
  FileSignature,
  Users,
  ArrowDownLeft,
  Receipt,
  Truck,
  ArrowUpRight,
  Landmark,
  CheckCheck,
  Percent,
  Settings,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getCurrentUser, removeAuthToken } from "@/lib/auth"
import { apiFetch } from "@/lib/api"

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, section: "Overview" },

  { label: "New Journal Entry", href: "/entry", icon: PlusCircle, section: "General Ledger" },
  { label: "General Journal", href: "/journal", icon: ClipboardList, section: "General Ledger" },
  { label: "General Ledger", href: "/ledger", icon: BookOpen, section: "General Ledger" },
  { label: "Chart of Accounts", href: "/coa", icon: TableProperties, section: "General Ledger" },

  { label: "Invoices", href: "/invoices", icon: FileSignature, section: "Accounts Receivable" },
  { label: "Customers", href: "/customers", icon: Users, section: "Accounts Receivable" },
  { label: "Payments Received", href: "/payments-received", icon: ArrowDownLeft, section: "Accounts Receivable" },

  { label: "Bills", href: "/bills", icon: Receipt, section: "Accounts Payable" },
  { label: "Vendors", href: "/vendors", icon: Truck, section: "Accounts Payable" },
  { label: "Bill Payments", href: "/bill-payments", icon: ArrowUpRight, section: "Accounts Payable" },

  { label: "Bank Accounts", href: "/bank-accounts", icon: Landmark, section: "Banking" },
  { label: "Reconciliations", href: "/reconciliations", icon: CheckCheck, section: "Banking" },

  { label: "Trial Balance", href: "/trial-balance", icon: Scale, section: "Financial Statements" },
  { label: "Income Statement", href: "/pl", icon: TrendingUp, section: "Financial Statements" },
  { label: "Balance Sheet", href: "/balance", icon: PieChart, section: "Financial Statements" },
  { label: "Cash Flow", href: "/cashflow", icon: FileText, section: "Financial Statements" },
  { label: "Tax Reports", href: "/tax", icon: Percent, section: "Financial Statements" },

  { label: "Settings", href: "/settings", icon: Settings, section: "Configuration" },
]

const sections = [
  "Overview",
  "General Ledger",
  "Accounts Receivable",
  "Accounts Payable",
  "Banking",
  "Financial Statements",
  "Configuration",
]

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [orgName, setOrgName] = useState("Easy-Books")
  const [isExpanded, setIsExpanded] = useState(true)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [userName, setUserName] = useState("User")
  const [userInitial, setUserInitial] = useState("U")

  useEffect(() => {
    const user = getCurrentUser()
    if (user) {
      setUserName(user.full_name)
      setUserInitial(user.full_name.charAt(0).toUpperCase())
    }

    apiFetch<Record<string, string>>("/api/settings")
      .then((data) => {
        if (data?.org_name) setOrgName(data.org_name)
      })
      .catch(() => {})
  }, [])

  const handleLogout = () => {
    if (!window.confirm("Are you sure you want to log out?")) return
    removeAuthToken()
    router.push("/login")
  }

  const handleNavigation = (href: string) => {
    router.push(href)
    setIsMobileMenuOpen(false)
  }

  return (
    <>
      {/* Icon Bar (always visible on left edge, desktop only) */}
      <div className="hidden md:flex flex-col items-center justify-between w-20 bg-[#1a1814] border-r border-white/5 py-4 gap-2">
        <div
          className="w-12 h-12 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-lg hover:shadow-lg hover:shadow-[#b8943f]/30 transition-all cursor-pointer"
          title={orgName}
          onClick={() => router.push("/dashboard")}
        >
          {orgName.charAt(0)}
        </div>

        <nav className="flex-1 flex flex-col gap-2 items-center overflow-y-auto scrollbar-hide">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              title={item.label}
              className={cn(
                "w-12 h-12 flex items-center justify-center rounded-lg transition-all duration-200",
                pathname === item.href
                  ? "bg-[#b8943f] text-black shadow-lg shadow-[#b8943f]/30"
                  : "text-white/50 hover:text-white/90 hover:bg-white/5"
              )}
            >
              <item.icon className="w-5 h-5" />
            </Link>
          ))}
        </nav>

        <div
          className="w-12 h-12 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-sm hover:shadow-lg hover:shadow-[#b8943f]/30 transition-all"
          title={userName}
        >
          {userInitial}
        </div>

        <div className="flex flex-col gap-2 items-center">
          <button
            onClick={handleLogout}
            className="w-12 h-12 flex items-center justify-center rounded-lg text-white/50 hover:text-white/90 hover:bg-white/5 transition-all duration-200"
            title="Logout"
          >
            <LogOut className="w-5 h-5" />
          </button>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-12 h-12 flex items-center justify-center rounded-lg text-white/50 hover:text-white/90 hover:bg-white/5 transition-all duration-200"
            title={isExpanded ? "Collapse" : "Expand"}
          >
            {isExpanded ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Expandable Sidebar (desktop only) */}
      <div
        className={cn(
          "hidden md:flex flex-col bg-[#1a1814] border-r border-white/5 transition-all duration-300 overflow-hidden",
          isExpanded ? "w-64" : "w-0"
        )}
      >
        <div className="p-6 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold flex-shrink-0">
              {orgName.charAt(0)}
            </div>
            <div className="font-serif text-lg text-white truncate" title={orgName}>
              {orgName}
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-4">
          {sections.map((section) => (
            <div key={section} className="mb-6">
              <div className="px-6 mb-2 text-[10px] font-bold uppercase tracking-widest text-white/50">
                {section}
              </div>
              {navItems
                .filter((item) => item.section === section)
                .map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 px-6 py-2.5 text-sm transition-all duration-200 font-medium",
                      pathname === item.href
                        ? "bg-[#b8943f]/15 text-[#ffd966] border-l-2 border-[#d4af60]"
                        : "text-white/75 hover:text-white hover:bg-white/5"
                    )}
                  >
                    <item.icon className="w-4 h-4 flex-shrink-0" />
                    <span>{item.label}</span>
                  </Link>
                ))}
            </div>
          ))}
        </nav>

        <div className="p-4 border-t border-white/5 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-xs flex-shrink-0">
              {userInitial}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{userName}</p>
              <p className="text-[10px] text-white/40">Admin</p>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Menu Toggle */}
      <button
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        className="md:hidden fixed top-4 left-4 z-50 w-12 h-12 bg-[#b8943f] hover:bg-[#d4af60] rounded-lg flex items-center justify-center text-black shadow-lg shadow-[#b8943f]/40 transition-all duration-300 hover:shadow-xl hover:shadow-[#b8943f]/60"
        title={isMobileMenuOpen ? "Close Menu" : "Open Menu"}
      >
        {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Mobile Drawer */}
      {isMobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-80 bg-[#1a1814] border-r border-white/10 shadow-2xl flex flex-col animate-in slide-in-from-left-80 duration-300">
            <div className="p-6 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold">
                  {orgName.charAt(0)}
                </div>
                <div className="font-serif text-lg text-white font-bold">{orgName}</div>
              </div>
            </div>

            <nav className="flex-1 overflow-y-auto py-4">
              {sections.map((section) => (
                <div key={section} className="mb-4">
                  <div className="px-6 mb-3 text-xs font-bold uppercase tracking-widest text-white/60">
                    {section}
                  </div>
                  {navItems
                    .filter((item) => item.section === section)
                    .map((item) => (
                      <button
                        key={item.href}
                        onClick={() => handleNavigation(item.href)}
                        className={cn(
                          "w-full flex items-center gap-3 px-6 py-3 text-sm transition-all duration-200 font-medium",
                          pathname === item.href
                            ? "bg-[#b8943f]/20 text-[#ffd966] border-l-2 border-[#d4af60] shadow-sm"
                            : "text-white/75 hover:text-white hover:bg-white/10"
                        )}
                      >
                        <item.icon className="w-5 h-5 flex-shrink-0" />
                        <span className="font-medium">{item.label}</span>
                      </button>
                    ))}
                </div>
              ))}
            </nav>

            <div className="p-4 border-t border-white/10 flex-shrink-0 space-y-2">
              <div className="flex items-center gap-3 px-2">
                <div className="w-10 h-10 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-sm flex-shrink-0">
                  {userInitial}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{userName}</p>
                  <p className="text-xs text-white/40">Admin</p>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-white/75 hover:text-white hover:bg-[#b8943f]/10 rounded-lg transition-all duration-200 font-medium"
              >
                <LogOut className="w-5 h-5" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
