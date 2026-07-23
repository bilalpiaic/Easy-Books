"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

type Usage = {
  users: number
  documents_this_month: number
  storage_mb: number
  plan: string
  plan_limits: { max_users: number; max_documents: number; storage_quota_mb: number }
  is_suspended: boolean
  subscription_status: string | null
}

export default function BillingPage() {
  const [usage, setUsage] = useState<Usage | null>(null)
  const [plans, setPlans] = useState<Record<string, { price: number; max_users: number; max_documents: number }>>({})
  const [msg, setMsg] = useState("")

  const load = () => {
    apiFetch<Usage>("/api/billing/usage").then(setUsage).catch(() => {})
    apiFetch<Record<string, { price: number; max_users: number; max_documents: number }>>(
      "/api/billing/plans",
    ).then(setPlans).catch(() => {})
  }
  useEffect(load, [])

  const upgrade = async (plan: string) => {
    setMsg("")
    const r = await apiFetch<{
      checkout_url?: string
      message?: string
      plan?: string
    }>("/api/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ plan }),
    })
    if (r.checkout_url) {
      window.location.href = r.checkout_url
      return
    }
    setMsg(r.message || `Plan set to ${r.plan}`)
    load()
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <h1 className="font-serif text-2xl text-[var(--text-primary)]">Billing & plan</h1>
      {usage && (
        <div className="rounded-xl border border-[var(--border)] p-4 space-y-3 bg-[var(--surface)]">
          <p className="text-sm">
            Current plan: <strong className="capitalize">{usage.plan}</strong>
            {usage.subscription_status ? ` · ${usage.subscription_status}` : ""}
            {usage.is_suspended ? " · SUSPENDED" : ""}
          </p>
          <Meter label="Users" used={usage.users} max={usage.plan_limits.max_users} />
          <Meter label="Documents this month" used={usage.documents_this_month} max={usage.plan_limits.max_documents} />
          <Meter label="Storage (MB)" used={usage.storage_mb} max={usage.plan_limits.storage_quota_mb} />
        </div>
      )}
      {msg && <p className="text-sm text-emerald-700">{msg}</p>}
      <div className="grid gap-3 sm:grid-cols-3">
        {["starter", "pro", "enterprise"].map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => upgrade(p)}
            className="rounded-xl border border-[var(--border)] p-4 text-left hover:border-[#b8943f]"
          >
            <div className="font-medium capitalize">{p}</div>
            <div className="text-sm text-[var(--text-muted)]">
              ${plans[p]?.price ?? "—"}/mo
            </div>
            <div className="text-xs mt-2 text-[var(--text-muted)]">
              {plans[p]?.max_users} users · {plans[p]?.max_documents} docs
            </div>
          </button>
        ))}
      </div>
      <p className="text-xs text-[var(--text-muted)]">
        Live Stripe Checkout needs <code>STRIPE_SECRET_KEY</code> plus{" "}
        <code>STRIPE_PRICE_STARTER</code> / <code>STRIPE_PRICE_PRO</code> /{" "}
        <code>STRIPE_PRICE_ENTERPRISE</code>. Without a secret key, upgrades apply offline.
      </p>
    </div>
  )
}

function Meter({ label, used, max }: { label: string; used: number; max: number }) {
  const pct = max ? Math.min(100, Math.round((used / max) * 100)) : 0
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span>{label}</span>
        <span>{used} / {max}</span>
      </div>
      <div className="h-2 rounded-full bg-[var(--border)] overflow-hidden">
        <div className="h-full bg-[#b8943f]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
