"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { apiFetch } from "@/lib/api"

export interface AppSettings {
  company_name: string
  tax_id: string
  fiscal_year_start: string
  currency: string
  email_notifications: string
  invoice_prefix: string
  bill_prefix: string
  financial_statement_date: string
}

const defaults: AppSettings = {
  company_name: "My Company",
  tax_id: "",
  fiscal_year_start: "January",
  currency: "PKR",
  email_notifications: "true",
  invoice_prefix: "INV",
  bill_prefix: "BILL",
  financial_statement_date: "month_end",
}

interface SettingsContextValue {
  settings: AppSettings
  reload: () => void
}

const SettingsContext = createContext<SettingsContextValue>({
  settings: defaults,
  reload: () => {},
})

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(defaults)

  const reload = () => {
    apiFetch<Record<string, string>>("/api/settings")
      .then(data => setSettings({ ...defaults, ...data }))
      .catch(() => {})
  }

  useEffect(reload, [])

  return (
    <SettingsContext.Provider value={{ settings, reload }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  return useContext(SettingsContext)
}

export function fmtCurrency(n: number, currency: string): string {
  const rounded = Math.round(n || 0)
  const formatted = rounded.toLocaleString("en-PK")
  return `${currency} ${formatted}`
}
