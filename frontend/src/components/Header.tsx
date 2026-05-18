"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { getCurrentUser } from "@/lib/auth"

export default function Header() {
  const [orgName, setOrgName] = useState("Easy-Books")
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
    <header className="h-14 bg-[#1a1814] flex items-center px-4 sm:px-6 gap-3 border-b border-white/5 shrink-0 z-20 md:hidden">
      {/* Mobile: logo + org name on left, user avatar on right */}
      <div className="w-7 h-7 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-sm flex-shrink-0">
        {orgName.charAt(0)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-serif text-white text-sm font-semibold truncate leading-tight">{orgName}</p>
        <p className="text-[9px] text-white/40 font-bold tracking-widest uppercase">Easy-Books</p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="px-2 py-0.5 bg-[#b8943f]/20 text-[#ffd966] rounded-full text-[8px] font-bold tracking-wider border border-[#b8943f]/30 hidden xs:block">
          ADMIN
        </div>
        <div className="w-7 h-7 rounded-full bg-[#b8943f] flex items-center justify-center text-black font-bold text-xs" title={userName}>
          {userInitial}
        </div>
      </div>
    </header>
  )
}
