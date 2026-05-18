"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { getCurrentUser } from "@/lib/auth"

export default function Header() {
  const [orgName, setOrgName] = useState("Easy-Books")
  const [userName, setUserName] = useState("User")

  useEffect(() => {
    const user = getCurrentUser()
    if (user) setUserName(user.full_name)

    apiFetch<Record<string, string>>("/api/settings")
      .then((data) => {
        if (data?.company_name) setOrgName(data.company_name)
      })
      .catch(() => {})
  }, [])

  return (
    <header className="hidden sm:flex h-14 bg-[#1a1814] items-center px-6 gap-4 border-bottom border-white/5 shrink-0 z-20">
      <div className="flex-1 min-w-0">
        <h1 className="font-serif text-white text-base truncate font-medium">{orgName}</h1>
        <p className="text-[10px] text-white/60 tracking-wider font-medium">FINANCIAL MANAGEMENT SYSTEM</p>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-xs text-white/60 font-medium truncate max-w-[160px]">{userName}</span>
        <div className="px-3 py-1 bg-[#b8943f]/25 text-[#ffd966] rounded-full text-[9px] font-bold tracking-wider border border-[#b8943f]/40">
          ADMIN
        </div>
      </div>
    </header>
  )
}
