"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
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
  LogOut
} from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, section: "Overview" },
  { label: "New Entry", href: "/entry", icon: PlusCircle, section: "Transactions" },
  { label: "General Journal", href: "/journal", icon: ClipboardList, section: "Transactions" },
  { label: "General Ledger", href: "/ledger", icon: BookOpen, section: "Transactions" },
  { label: "Chart of Accounts", href: "/coa", icon: TableProperties, section: "Reports" },
  { label: "Trial Balance", href: "/trial-balance", icon: Scale, section: "Reports" },
  { label: "P&L Statement", href: "/pl", icon: FileText, section: "Reports" },
  { label: "Balance Sheet", href: "/balance", icon: PieChart, section: "Reports" },
  { label: "Cash Flow", href: "/cashflow", icon: TrendingUp, section: "Reports" },
]

export default function Sidebar() {
  const pathname = usePathname()

  const sections = ["Overview", "Transactions", "Reports"]

  return (
    <div className="w-64 bg-[#1a1814] text-white flex flex-col h-screen border-r border-white/5">
      <div className="p-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold">
            M
          </div>
          <div className="font-serif text-lg">Malik Ent.</div>
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
            M
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">Malik Sahib</p>
            <p className="text-[10px] text-white/40">Owner</p>
          </div>
          <button className="p-1.5 text-white/30 hover:text-white/70">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
