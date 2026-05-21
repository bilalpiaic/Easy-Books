"use client"

import { useEffect, useState } from "react"
import { Menu } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { getCurrentUser } from "@/lib/auth"

interface HeaderProps {
  onOpenMenu: () => void
}

export default function Header({ onOpenMenu }: HeaderProps) {
  const [orgName, setOrgName]   = useState("Easy-Books")
  const [userName, setUserName] = useState("User")
  const [userInitial, setInitial] = useState("U")

  useEffect(() => {
    const user = getCurrentUser()
    if (user) {
      setUserName(user.full_name)
      setInitial(user.full_name.charAt(0).toUpperCase())
    }
    apiFetch<Record<string, string>>("/api/settings")
      .then(d => { if (d?.company_name) setOrgName(d.company_name) })
      .catch(() => {})
  }, [])

  return (
    <header className="h-12 bg-[#1a1814] flex items-center px-3 sm:px-4 gap-3 border-b border-white/5 shrink-0 z-20">
      <button
        onClick={onOpenMenu}
        aria-label="Open menu"
        className="w-9 h-9 inline-flex items-center justify-center rounded-lg text-white/70 hover:text-[#ffd966] hover:bg-white/5 transition"
      >
        <Menu className="w-5 h-5" />
      </button>
      <div className="w-7 h-7 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-sm flex-shrink-0">
        {orgName.charAt(0)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-serif text-white text-sm font-semibold truncate leading-tight">{orgName}</p>
        <p className="text-[9px] text-white/40 font-bold tracking-widest uppercase hidden sm:block">Easy-Books · Double-Entry Accounting</p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <div
          className="w-8 h-8 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-xs"
          title={userName}
        >
          {userInitial}
        </div>
      </div>
    </header>
  )
}
