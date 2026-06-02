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
  business_tagline: string
  // Company profile
  logo_url: string
  address_line1: string
  address_line2: string
  city: string
  country: string
  phone: string
  website: string
  // Default GL accounts (account codes)
  default_ar_account: string
  default_ap_account: string
  default_revenue_account: string
  default_cogs_account: string
  // Document number formats
  invoice_number_format: string
  bill_number_format: string
  // Onboarding
  onboarding_steps: string
  onboarding_dismissed: string
  // Inventory
  block_negative_stock: string
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
  business_tagline: "Easy-Books · Double-Entry Accounting",
  logo_url: "",
  address_line1: "",
  address_line2: "",
  city: "",
  country: "",
  phone: "",
  website: "",
  default_ar_account: "1100",
  default_ap_account: "2000",
  default_revenue_account: "4000",
  default_cogs_account: "5010",
  invoice_number_format: "",
  bill_number_format: "",
  onboarding_steps: "",
  onboarding_dismissed: "",
  block_negative_stock: "false",
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

/** Hook that returns a formatter using the tenant's base currency. */
export function useFmt() {
  const { settings } = useSettings()
  return (n: number) => fmtCurrency(n, settings.currency || "PKR")
}
