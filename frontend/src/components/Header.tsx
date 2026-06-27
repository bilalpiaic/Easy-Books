"use client"

import { useEffect, useRef, useState } from "react"
import { Menu, Home, Sun, Moon, Monitor, Globe } from "lucide-react"
import Link from "next/link"
import { getCurrentUser } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"
import { useTheme, type ThemeMode } from "@/context/ThemeContext"
import { useLocale } from "@/context/LocaleContext"
import { LANGUAGES } from "@/i18n/config"

interface HeaderProps {
  onOpenMenu: () => void
}

const THEME_CYCLE: ThemeMode[] = ["light", "dark", "system"]
const THEME_ICON = { light: Sun, dark: Moon, system: Monitor } as const

export default function Header({ onOpenMenu }: HeaderProps) {
  const { settings }            = useSettings()
  const { theme, setTheme }     = useTheme()
  const { language, setLanguage } = useLocale()
  const [userName, setUserName]   = useState("User")
  const [userInitial, setInitial] = useState("U")
  const [langOpen, setLangOpen]   = useState(false)
  const langRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const user = getCurrentUser()
    if (user) {
      setUserName(user.full_name)
      setInitial(user.full_name.charAt(0).toUpperCase())
    }
  }, [])

  // Close language dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (langRef.current && !langRef.current.contains(e.target as Node)) {
        setLangOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const cycleTheme = () => {
    const next = THEME_CYCLE[(THEME_CYCLE.indexOf(theme) + 1) % THEME_CYCLE.length]
    setTheme(next)
  }

  const ThemeIcon = THEME_ICON[theme]
  const themeLabel = { light: "Light mode", dark: "Dark mode", system: "System theme" }[theme]
  const currentLangMeta = LANGUAGES.find(l => l.code === language) ?? LANGUAGES[0]

  return (
    <header className="h-12 bg-[var(--text-primary)] flex items-center px-3 sm:px-4 gap-3 border-b border-white/5 shrink-0 z-20">
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
      <div className="w-7 h-7 bg-[var(--primary)] rounded-lg flex items-center justify-center font-bold text-black font-bold text-sm flex-shrink-0">
        {settings.company_name.charAt(0)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-white text-sm font-semibold truncate leading-tight">{settings.company_name}</p>
        <p className="text-[9px] text-white/40 font-bold tracking-widest uppercase hidden sm:block">{settings.business_tagline}</p>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        {/* Theme toggle — cycles Light → Dark → System */}
        <button
          onClick={cycleTheme}
          title={themeLabel}
          aria-label={`Switch theme (current: ${themeLabel})`}
          className="w-8 h-8 inline-flex items-center justify-center rounded-lg text-white/60 hover:text-[#ffd966] hover:bg-white/5 transition"
        >
          <ThemeIcon className="w-4 h-4" />
        </button>

        {/* Language switcher */}
        <div ref={langRef} className="relative">
          <button
            onClick={() => setLangOpen(p => !p)}
            title={`Language: ${currentLangMeta.label}`}
            aria-label="Switch language"
            className="w-8 h-8 inline-flex items-center justify-center rounded-lg text-white/60 hover:text-[#ffd966] hover:bg-white/5 transition"
          >
            <Globe className="w-4 h-4" />
          </button>
          {langOpen && (
            <div className="absolute right-0 top-10 z-50 bg-[#2a2521] border border-white/10 rounded-lg shadow-2xl py-1 min-w-[140px]">
              {LANGUAGES.map(lang => (
                <button
                  key={lang.code}
                  onClick={() => { setLanguage(lang.code); setLangOpen(false) }}
                  className={`w-full text-left flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
                    language === lang.code
                      ? "text-[#ffd966] bg-[var(--primary)]/10"
                      : "text-white/70 hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span className="text-base leading-none">{lang.code === "en" ? "🇬🇧" : lang.code === "ur" ? "🇵🇰" : "🇨🇳"}</span>
                  <span className="flex-1">{lang.nativeLabel}</span>
                  {language === lang.code && <span className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]" />}
                </button>
              ))}
            </div>
          )}
        </div>

        <div
          className="w-8 h-8 rounded-full bg-[var(--primary)] flex items-center justify-center text-black font-bold text-xs"
          title={userName}
        >
          {userInitial}
        </div>
      </div>
    </header>
  )
}
