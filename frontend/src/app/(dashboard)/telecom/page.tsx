"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Signal, Wallet, Users, ArrowRightLeft, Banknote, Smartphone, Target } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"

interface Dashboard {
  tracker_deposit_balance: string
  load_float_balance: string
  rso_load_outstanding: string
  retail_load_outstanding: string
  rso_stock_receivable: string
  commission_receivable: string
  current_kpi: {
    target_month: string
    target_fca_count: number
    actual_fca_count: number
    incentive_earned: string
    penalty_applied: string
    status: string
  } | null
}

interface KPICardProps {
  label: string
  value: string
  sub?: string
  tone?: "default" | "warning" | "success"
  icon: React.ElementType
}

function KPICard({ label, value, sub, tone = "default", icon: Icon }: KPICardProps) {
  const toneClass =
    tone === "warning" ? "border-amber-200 bg-amber-50"
    : tone === "success" ? "border-emerald-200 bg-emerald-50"
    : "border-[#b8943f]/20 bg-white"
  return (
    <div className={`rounded-xl border p-4 flex gap-3 items-start ${toneClass}`}>
      <div className="mt-0.5 shrink-0">
        <Icon className="w-5 h-5 text-[#b8943f]" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-[#1a1814]/50 uppercase tracking-wide truncate">{label}</p>
        <p className="text-xl font-semibold text-[#1a1814] font-mono mt-0.5">{value}</p>
        {sub && <p className="text-xs text-[#1a1814]/50 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

interface QuickLinkProps { href: string; icon: React.ElementType; label: string }
function QuickLink({ href, icon: Icon, label }: QuickLinkProps) {
  return (
    <Link href={href}
      className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-[#b8943f]/20
                 bg-white text-sm text-[#1a1814] hover:bg-[#f6f3ee] hover:border-[#b8943f]/40 transition-colors">
      <Icon className="w-4 h-4 text-[#b8943f]" />
      {label}
    </Link>
  )
}

function fmt(v: string | undefined) {
  if (!v) return "PKR 0"
  const n = parseFloat(v)
  return "PKR " + n.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function TelecomDashboardPage() {
  const [data, setData]   = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Dashboard>("/api/telecom/dashboard")
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load dashboard"))
  }, [])

  const kpi = data?.current_kpi
  const fcaProgress = kpi
    ? Math.min(100, Math.round((kpi.actual_fca_count / Math.max(1, kpi.target_fca_count)) * 100))
    : 0

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <Signal className="w-7 h-7 text-[#b8943f]" />
        <div>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Telecom Franchise</h1>
          <p className="text-sm text-[#1a1814]/60">Tracker balances, load float, RSO channel, and FCA KPIs.</p>
        </div>
      </header>

      <HelpCallout title="How the telecom franchise works" tone="tip">
        <ol className="list-decimal pl-4 space-y-1">
          <li><b>Deposit funds</b> into the Tracker wallet (Advance to Operator).</li>
          <li><b>Order load</b> — Tracker debits 100%, MSR SIM receives 103% (3% is commission income).</li>
          <li><b>Distribute load</b> to RSO agents → RSO distributes to retail outlets.</li>
          <li><b>Collect daily</b> — RSO deposits cash covering load + SIM stock settlements.</li>
          <li><b>FCA events</b> count toward the monthly operator target; commission is posted at month-end.</li>
        </ol>
      </HelpCallout>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-900 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Balance KPI cards */}
      <section>
        <h2 className="text-xs font-semibold text-[#1a1814]/40 uppercase tracking-widest mb-3">Balances</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <KPICard label="Tracker Deposit"   value={fmt(data?.tracker_deposit_balance)} icon={Wallet} />
          <KPICard label="Load Float (MSR)"  value={fmt(data?.load_float_balance)}      icon={Signal} />
          <KPICard label="RSO Load Owed"     value={fmt(data?.rso_load_outstanding)}    icon={Users}
            tone={parseFloat(data?.rso_load_outstanding || "0") > 0 ? "warning" : "default"} />
          <KPICard label="Retail Load Owed"  value={fmt(data?.retail_load_outstanding)} icon={ArrowRightLeft} />
          <KPICard label="RSO Stock Owed"    value={fmt(data?.rso_stock_receivable)}    icon={Smartphone} />
          <KPICard label="Commission Rec."   value={fmt(data?.commission_receivable)}   icon={Banknote} />
        </div>
      </section>

      {/* FCA KPI section */}
      {kpi && (
        <section>
          <h2 className="text-xs font-semibold text-[#1a1814]/40 uppercase tracking-widest mb-3">
            FCA Target — {kpi.target_month}
          </h2>
          <div className="rounded-xl border border-[#b8943f]/20 bg-white p-5 space-y-3">
            <div className="flex justify-between items-baseline">
              <span className="text-sm text-[#1a1814]/60">Progress</span>
              <span className="font-mono text-lg font-semibold text-[#1a1814]">
                {kpi.actual_fca_count} / {kpi.target_fca_count} FCAs
              </span>
            </div>
            <div className="w-full bg-[#f6f3ee] rounded-full h-3 overflow-hidden">
              <div
                className={`h-3 rounded-full transition-all ${fcaProgress >= 100 ? "bg-emerald-500" : "bg-[#b8943f]"}`}
                style={{ width: `${fcaProgress}%` }}
              />
            </div>
            <div className="flex gap-6 text-sm">
              <div>
                <span className="text-[#1a1814]/50">Achievement </span>
                <span className="font-semibold text-[#1a1814]">{fcaProgress}%</span>
              </div>
              {parseFloat(kpi.incentive_earned) > 0 && (
                <div className="text-emerald-700">
                  <span>Commission earned </span>
                  <span className="font-semibold">{fmt(kpi.incentive_earned)}</span>
                </div>
              )}
              {parseFloat(kpi.penalty_applied) > 0 && (
                <div className="text-red-700">
                  <span>Penalty </span>
                  <span className="font-semibold">{fmt(kpi.penalty_applied)}</span>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Quick links */}
      <section>
        <h2 className="text-xs font-semibold text-[#1a1814]/40 uppercase tracking-widest mb-3">Quick Access</h2>
        <div className="flex flex-wrap gap-2">
          <QuickLink href="/telecom/tracker"         icon={Wallet}        label="Tracker & Load" />
          <QuickLink href="/telecom/rso/agents"      icon={Users}         label="RSO Agents" />
          <QuickLink href="/telecom/rso/transfers"   icon={ArrowRightLeft} label="Load Transfers" />
          <QuickLink href="/telecom/rso/collections" icon={Banknote}      label="Daily Collections" />
          <QuickLink href="/telecom/sim/batches"     icon={Smartphone}    label="SIM Batches" />
          <QuickLink href="/telecom/fca"             icon={Target}        label="FCA & KPI Targets" />
        </div>
      </section>
    </div>
  )
}
