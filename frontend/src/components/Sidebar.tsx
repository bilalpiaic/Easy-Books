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
  Settings
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

  const sections = [
    "Overview", 
    "General Ledger", 
    "Accounts Receivable", 
    "Accounts Payable", 
    "Banking", 
    "Financial Statements", 
    "Configuration"
  ]

  return (
    <div className="w-64 bg-[#1a1814] text-white flex flex-col h-screen border-r border-white/5">
      <div className="p-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold">
            {orgName.charAt(0)}
          </div>
          <div className="font-serif text-lg truncate" title={orgName}>{orgName}</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-4">
        {sections.map(section => (
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
                <item.icon className="w-4 h-4" />
                {item.label}
              </Link>
            ))}
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-xs">
            U
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">Logged User</p>
            <p className="text-[10px] text-white/40">Admin</p>
          </div>
          <button 
            onClick={handleLogout}
            className="p-1.5 text-white/30 hover:text-white/70"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
