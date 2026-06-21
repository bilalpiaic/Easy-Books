"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { I18nextProvider } from "react-i18next"
import { apiFetch } from "@/lib/api"
import i18n, { type Language, LANGUAGES } from "@/i18n/config"

interface LocaleCtxValue {
  language:    Language
  setLanguage: (lang: Language) => void
}

const LocaleCtx = createContext<LocaleCtxValue>({
  language: "en",
  setLanguage: () => {},
})

export function useLocale() { return useContext(LocaleCtx) }

function applyToDOM(lang: Language) {
  const meta = LANGUAGES.find(l => l.code === lang) ?? LANGUAGES[0]
  document.documentElement.lang = lang
  document.documentElement.dir  = meta.dir
  i18n.changeLanguage(lang)
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en")

  useEffect(() => {
    const saved = (localStorage.getItem("eb.lang") ?? "en") as Language
    setLanguageState(saved)
    applyToDOM(saved)
  }, [])

  const setLanguage = (lang: Language) => {
    setLanguageState(lang)
    localStorage.setItem("eb.lang", lang)
    applyToDOM(lang)
    apiFetch("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ app_language: lang }),
    }).catch(() => {})
  }

  return (
    <LocaleCtx.Provider value={{ language, setLanguage }}>
      {/* I18nextProvider explicitly wires our i18n instance to all
          useTranslation() hooks below, ensuring re-renders on changeLanguage */}
      <I18nextProvider i18n={i18n}>
        {children}
      </I18nextProvider>
    </LocaleCtx.Provider>
  )
}
