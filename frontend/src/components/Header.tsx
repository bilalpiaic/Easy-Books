"use client"

import { Menu } from "lucide-react"

export default function Header() {
  return (
    <header className="h-14 bg-[#1a1814] flex items-center px-6 gap-4 border-bottom border-white/5 shrink-0 z-20">
      <button className="md:hidden text-white/70 p-1">
        <Menu className="w-5 h-5" />
      </button>
      <div className="flex-1 min-w-0">
        <h1 className="font-serif text-white text-base truncate">Malik Enterprises</h1>
        <p className="text-[10px] text-white/40 tracking-wider">FINANCIAL MANAGEMENT SYSTEM</p>
      </div>
      <div className="hidden sm:flex items-center gap-4">
        <div className="px-3 py-1 bg-white/5 border border-white/10 rounded-full text-[10px] text-white/50">
          Mar 2025 – Feb 2026
        </div>
        <div className="px-2 py-0.5 bg-[#b8943f]/20 text-[#d4af60] rounded-full text-[9px] font-bold tracking-wider">
          OWNER
        </div>
      </div>
    </header>
  )
}
