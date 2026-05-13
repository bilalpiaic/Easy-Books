"use client"

import { useEffect, useState } from "react"
import { Menu } from "lucide-react"
import { getAuthHeader } from "@/lib/auth"

export default function Header() {
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

  return (
    <header className="h-14 bg-[#1a1814] flex items-center px-6 gap-4 border-bottom border-white/5 shrink-0 z-20">
      <button className="md:hidden text-white/70 p-1">
        <Menu className="w-5 h-5" />
      </button>
      <div className="flex-1 min-w-0">
        <h1 className="font-serif text-white text-base truncate">{orgName}</h1>
        <p className="text-[10px] text-white/40 tracking-wider">FINANCIAL MANAGEMENT SYSTEM</p>
      </div>
      <div className="hidden sm:flex items-center gap-4">
        <div className="px-3 py-1 bg-white/5 border border-white/10 rounded-full text-[10px] text-white/50">
          Current Session
        </div>
        <div className="px-2 py-0.5 bg-[#b8943f]/20 text-[#d4af60] rounded-full text-[9px] font-bold tracking-wider">
          ADMIN
        </div>
      </div>
    </header>
  )
}
