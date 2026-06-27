// frontend/src/components/hub/HubPage.tsx
"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { useFmt } from "@/context/SettingsContext"
import AgingBand, { type AgingBandProps } from "./AgingBand"
import LowStockBand, { type LowStockBandProps } from "./LowStockBand"
import AccountListBand, { type AccountListBandProps } from "./AccountListBand"
import PayrollBand, { type PayrollBandProps } from "./PayrollBand"
import { useTranslation } from "react-i18next"

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type HubRawData = any[]

export interface KpiDef {
  label: string
  value: (raw: HubRawData) => string | number
  tone?: (raw: HubRawData) => "normal" | "warning" | "danger"
  /** "currency" = pass the number through fmt(); "text" = use value string as-is */
  format?: "currency" | "text"
}

export interface ActionDef {
  label: string
  href: string
  icon: LucideIcon
  primary?: boolean
}

export type BandType = "aging" | "low-stock" | "account-list" | "payroll-runs"

export interface HubConfig {
  section: string
  title: string
  icon: LucideIcon
  kpis: KpiDef[]             // exactly 4
  band: BandType
  bandData: (raw: HubRawData) => unknown   // cast at render site
  actions: ActionDef[]       // 4–8 tiles; first should be primary
  fetch: () => Promise<HubRawData>
}

const TONE: Record<string, string> = {
  normal:  "text-[var(--text-primary)]",
  warning: "text-amber-600",
  danger:  "text-red-600",
}

export default function HubPage({ config }: { config: HubConfig }) {
  const { t } = useTranslation()

  const router = useRouter()
  const fmt = useFmt()
  const [raw, setRaw] = useState<HubRawData | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    config.fetch().then(setRaw).catch(() => setError(true))
  }, [config])

  const loading = !raw && !error

  const displayKpi = (kpi: KpiDef, val: string | number): string =>
    kpi.format === "currency" && typeof val === "number" ? fmt(val) : String(val)

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--primary)] mb-0.5">
            {config.section}
          </div>
          <h1 className="text-3xl font-bold text-[var(--text-primary)]">{config.title}</h1>
        </div>
        <config.icon className="w-10 h-10 text-[var(--primary)]/40 mt-1" />
      </div>

      {/* Error banner — action grid still renders below */}
      {error && (
        <div className="mb-4 rounded-xl bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-800">
          Could not load summary — data may be stale.
        </div>
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        {config.kpis.map((kpi, i) => {
          const val = raw ? kpi.value(raw) : null
          const tone = raw && kpi.tone ? kpi.tone(raw) : "normal"
          return (
            <div
              key={i}
              className="bg-white rounded-2xl p-4 shadow-sm shadow-black/5 border border-[var(--text-primary)]/5"
            >
              <div
                className={cn(
                  "text-lg font-bold font-mono truncate",
                  loading ? "text-[var(--text-primary)]/10 animate-pulse" : TONE[tone]
                )}
              >
                {loading ? "—" : val !== null ? displayKpi(kpi, val) : "—"}
              </div>
              <div className="text-[9px] font-bold uppercase tracking-[0.1em] text-[var(--text-primary)]/40 mt-1">
                {kpi.label}
              </div>
            </div>
          )
        })}
      </div>

      {/* Data band */}
      <div className="mb-4">
        {loading && <div className="bg-white rounded-xl h-20 animate-pulse" />}
        {!loading && raw && config.band === "aging" && (
          <AgingBand {...(config.bandData(raw) as AgingBandProps)} />
        )}
        {!loading && raw && config.band === "low-stock" && (
          <LowStockBand {...(config.bandData(raw) as LowStockBandProps)} />
        )}
        {!loading && raw && config.band === "account-list" && (
          <AccountListBand {...(config.bandData(raw) as AccountListBandProps)} />
        )}
        {!loading && raw && config.band === "payroll-runs" && (
          <PayrollBand {...(config.bandData(raw) as PayrollBandProps)} />
        )}
      </div>

      {/* Action grid */}
      <div className="grid grid-cols-4 gap-3">
        {config.actions.map((action, i) => (
          <button
            key={i}
            onClick={() => router.push(action.href)}
            className={cn(
              "flex flex-col items-center gap-2 rounded-2xl p-4 text-center transition-all",
              "hover:scale-[1.02] shadow-sm shadow-black/5 border",
              action.primary
                ? "bg-[var(--text-primary)] text-white border-transparent hover:bg-[var(--primary)]"
                : "bg-white text-[var(--text-primary)] border-[var(--text-primary)]/5 hover:bg-[var(--bg-page)]"
            )}
          >
            <action.icon
              className={cn("w-5 h-5", action.primary ? "text-white" : "text-[var(--primary)]")}
            />
            <span
              className={cn(
                "text-[10px] font-medium leading-tight",
                action.primary ? "text-white" : "text-[var(--text-primary)]/70"
              )}
            >
              {action.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
