"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { apiFetch } from "@/lib/api"

export interface AppSettings {
  company_name: string
  tax_id: string
  fiscal_year_start: string
  week_start_day: string
  currency: string
  email_notifications: string
  // Days between automated overdue-invoice reminder emails (services/overdue.py)
  overdue_reminder_interval_days: string
  // In-app Alerts bell for staff ops alerts
  in_app_alerts: string
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
  // Purchases & Store
  require_purchase_chain: string
  require_gate_inward: string
  // UI density
  ui_density: string
  // Amount display precision
  decimal_places: string
  // Business model
  business_model: string
  // Inventory cost method
  cost_method: string
  // User Rights Module
  user_rights_enabled: string
  // Appearance
  app_theme: string
  color_theme: string
  app_language: string
  // PRA e-Invoice (Punjab Revenue Authority) — Pakistan tax compliance
  pra_enabled: string
  pra_ntn: string
  pra_pos_id: string
  pra_api_token: string
  pra_sandbox_mode: string
}

const defaults: AppSettings = {
  company_name: "My Company",
  tax_id: "",
  fiscal_year_start: "January",
  week_start_day: "Monday",
  currency: "PKR",
  email_notifications: "true",
  overdue_reminder_interval_days: "7",
  in_app_alerts: "true",
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
  require_purchase_chain: "true",
  require_gate_inward: "true",
  ui_density: "comfortable",
  decimal_places: "2",
  business_model: "simple",
  cost_method: "wavg",
  user_rights_enabled: "false",
  app_theme: "light",
  color_theme: "gold",
  app_language: "en",
  pra_enabled: "false",
  pra_ntn: "",
  pra_pos_id: "",
  pra_api_token: "",
  pra_sandbox_mode: "true",
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

  useEffect(() => {
    document.documentElement.dataset.density =
      settings.ui_density === "compact" ? "compact" : "comfortable"
  }, [settings.ui_density])

  return (
    <SettingsContext.Provider value={{ settings, reload }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  return useContext(SettingsContext)
}

/** Full currency display — use only for standalone amounts, NOT table cells. */
export function fmtCurrency(n: number, currency: string, dp: number = 2): string {
  const val = n || 0
  const abs = Math.abs(val)
  const formatted = abs.toLocaleString("en-PK", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  })
  return val < 0 ? `${currency} (${formatted})` : `${currency} ${formatted}`
}

/** Number-only formatter (no currency prefix) — for table cell values. */
export function fmtNum(n: number, dp: number = 2): string {
  const val = n || 0
  const abs = Math.abs(val)
  const formatted = abs.toLocaleString("en-PK", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  })
  return val < 0 ? `(${formatted})` : formatted
}

/** Hook that returns a number-only formatter for table cells. */
export function useFmt() {
  const { settings } = useSettings()
  const dp = parseInt(settings.decimal_places || "2")
  return (n: number) => fmtNum(n, dp)
}

/** Compact number formatter for KPI tiles: 1,234,567 → 1.23M, 12,345 → 12.3K. */
export function fmtCompact(n: number): string {
  const val = n || 0
  const abs = Math.abs(val)
  let result: string
  if (abs >= 1_000_000_000) {
    result = (abs / 1_000_000_000).toFixed(2).replace(/\.?0+$/, "") + "B"
  } else if (abs >= 1_000_000) {
    result = (abs / 1_000_000).toFixed(2).replace(/\.?0+$/, "") + "M"
  } else if (abs >= 10_000) {
    result = (abs / 1_000).toFixed(1).replace(/\.0$/, "") + "K"
  } else {
    result = Math.round(abs).toLocaleString("en-PK")
  }
  return val < 0 ? `(${result})` : result
}

/** Hook returning the compact formatter — for dashboard KPI tiles. */
export function useFmtCompact() {
  return fmtCompact
}

/** Returns the tenant's active currency code (e.g. "PKR"). */
export function useCurrency(): string {
  const { settings } = useSettings()
  return settings.currency || "PKR"
}

/** Returns the tenant's configured decimal places as a number (2 or 4). */
export function useDp(): number {
  const { settings } = useSettings()
  return parseInt(settings.decimal_places || "2")
}
