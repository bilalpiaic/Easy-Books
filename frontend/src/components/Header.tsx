"use client"

import { useEffect, useState } from "react"
import { Menu, Home } from "lucide-react"
import Link from "next/link"
import { getCurrentUser } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"

interface HeaderProps {
  onOpenMenu: () => void
}

export default function Header({ onOpenMenu }: HeaderProps) {
  const { settings } = useSettings()
  const [userName, setUserName] = useState("User")
  const [userInitial, setInitial] = useState("U")

  useEffect(() => {
    const user = getCurrentUser()
    if (user) {
      setUserName(user.full_name)
      setInitial(user.full_name.charAt(0).toUpperCase())
    }
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
      <Link
        href="/dashboard"
        aria-label="Home"
        title="Dashboard"
        className="w-9 h-9 inline-flex items-center justify-center rounded-lg text-white/70 hover:text-[#ffd966] hover:bg-white/5 transition"
      >
        <Home className="w-5 h-5" />
      </Link>
      <div className="w-7 h-7 bg-[#b8943f] rounded-lg flex items-center justify-center font-serif text-black font-bold text-sm flex-shrink-0">
        {settings.company_name.charAt(0)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-serif text-white text-sm font-semibold truncate leading-tight">{settings.company_name}</p>
        <p className="text-[9px] text-white/40 font-bold tracking-widest uppercase hidden sm:block">{settings.business_tagline}</p>
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
