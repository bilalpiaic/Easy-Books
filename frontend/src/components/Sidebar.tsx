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
  ChevronRight
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getAuthHeader, removeAuthToken } from "@/lib/auth"

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

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [orgName, setOrgName] = useState("Easy-Books")
  const [isExpanded, setIsExpanded] = useState(true)
  
  useEffect(() => {
    fetch("http://localhost:8000/api/settings", {
      headers: getAuthHeader()
    })
    .then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    })
    .then(data => {
      if (data?.org_name) setOrgName(data.org_name)
    })
    .catch(err => console.error("Failed to fetch settings:", err))
  }, [])

  const handleLogout = () => {
    removeAuthToken()
    router.push("/login")
  }

  return (
    <>
      {/* Icon Bar (always visible on left edge) */}
      <div className="hidden md:flex flex-col items-center justify-between w-20 bg-[#1a1814] border-r border-white/5 py-4 gap-2">
        {/* Logo Icon */}
        <div className="w-12 h-12 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-lg hover:shadow-lg hover:shadow-[#b8943f]/30 transition-all cursor-pointer"
          title={orgName}
          onClick={() => router.push("/dashboard")}
        >
          {orgName.charAt(0)}
        </div>

        {/* Nav Icons */}
        <nav className="flex-1 flex flex-col gap-2 items-center overflow-y-auto scrollbar-hide">
          {navItems.map(item => (
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

        {/* User Icon */}
        <div className="w-12 h-12 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-sm hover:shadow-lg hover:shadow-[#b8943f]/30 transition-all" title="User">
          U
        </div>

        {/* Logout & Toggle */}
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

      {/* Expandable Sidebar (hidden on mobile) */}
      <div 
        className={cn(
          "hidden md:flex flex-col bg-[#1a1814] border-r border-white/5 transition-all duration-300 overflow-hidden",
          isExpanded ? "w-64" : "w-0"
        )}
      >
        {/* Header */}
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

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4">
          {[
            "Overview", 
            "General Ledger", 
            "Accounts Receivable", 
            "Accounts Payable", 
            "Banking", 
            "Financial Statements", 
            "Configuration"
          ].map(section => (
            <div key={section} className="mb-6">
              <div className="px-6 mb-2 text-[10px] font-bold uppercase tracking-widest text-white/30">
                {section}
              </div>
              {navItems.filter(item => item.section === section).map(item => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-6 py-2.5 text-sm transition-colors",
                    pathname === item.href 
                      ? "bg-[#b8943f]/10 text-[#d4af60]" 
                      : "text-white/60 hover:text-white/90 hover:bg-white/5"
                  )}
                >
                  <item.icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.label}</span>
                </Link>
              ))}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-white/5 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-xs flex-shrink-0">
              U
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">Logged User</p>
              <p className="text-[10px] text-white/40">Admin</p>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Navigation Icons (bottom for mobile) */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-[#1a1814] border-t border-white/5 flex items-center justify-around p-2">
        {navItems.slice(0, 5).map(item => (
          <Link
            key={item.href}
            href={item.href}
            title={item.label}
            className={cn(
              "flex-1 flex items-center justify-center py-3 transition-all",
              pathname === item.href 
                ? "text-[#d4af60]" 
                : "text-white/50 hover:text-white/90"
            )}
          >
            <item.icon className="w-5 h-5" />
          </Link>
        ))}
      </div>
    </>
  )
}
