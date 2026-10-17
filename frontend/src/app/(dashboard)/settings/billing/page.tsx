"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"

type Usage = {
  users: number
  documents_this_month: number
  storage_mb: number
  plan: string
  plan_limits: { max_users: number; max_documents: number; storage_quota_mb: number }
  included_modules?: string[]
  include_labels?: string[]
  extra_addons?: string[]
  extra_addon_labels?: string[]
  settlement?: "saas" | "standalone"
  is_suspended: boolean
  subscription_status: string | null
}

type PlanCard = {
  id?: string
  price: number
  max_users: number
  max_documents: number
  summary?: string
  includes?: string[]
  include_labels?: string[]
  label?: string
}

type AddonSku = {
  id: string
  label: string
  kind: "industry" | "localization"
  price: number
  included_from: string
  category: string
}

type Catalog = {
  settlement: "saas" | "standalone"
  plans: Record<string, PlanCard>
  addons: AddonSku[]
}

type LicenseStatus = {
  install_id?: string | null
  licensed?: boolean
  standalone?: boolean
  plan?: string | null
  addons?: string[]
}

const PLAN_ORDER = ["starter", "pro", "enterprise"] as const

export default function BillingPage() {
  const [usage, setUsage] = useState<Usage | null>(null)
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [license, setLicense] = useState<LicenseStatus | null>(null)
  const [msg, setMsg] = useState("")
  const [err, setErr] = useState("")

  const load = () => {
    apiFetch<Usage>("/api/billing/usage").then(setUsage).catch(() => {})
    apiFetch<Catalog>("/api/billing/catalog")
      .then(setCatalog)
      .catch(() => {
        apiFetch<Record<string, PlanCard>>("/api/billing/plans")
          .then((plans) => setCatalog({ settlement: "saas", plans, addons: [] }))
          .catch(() => {})
      })
    apiFetch<LicenseStatus>("/api/license/status").then(setLicense).catch(() => {})
  }
  useEffect(load, [])

  const standalone = (usage?.settlement || catalog?.settlement) === "standalone"
  const plans = catalog?.plans || {}

  const upgrade = async (plan: string) => {
    setMsg("")
    setErr("")
    try {
      const r = await apiFetch<{
        checkout_url?: string
        message?: string
        plan?: string
        detail?: string
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
    } catch (e: unknown) {
      setErr(String((e as Error).message ?? e))
    }
  }

  const industry = (catalog?.addons || []).filter((a) => a.kind === "industry")
  const localization = (catalog?.addons || []).filter((a) => a.kind === "localization")

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <h1 className="font-serif text-2xl text-[var(--text-primary)]">Billing & plan</h1>
      {usage && (
        <div className="rounded-xl border border-[var(--border)] p-4 space-y-3 bg-[var(--surface)]">
          <p className="text-sm">
            Current plan: <strong className="capitalize">{usage.plan}</strong>
            {usage.subscription_status ? ` · ${usage.subscription_status}` : ""}
            {usage.is_suspended ? " · SUSPENDED" : ""}
            {standalone ? " · standalone license" : ""}
          </p>
          <Meter label="Users" used={usage.users} max={usage.plan_limits.max_users} />
          <Meter label="Documents this month" used={usage.documents_this_month} max={usage.plan_limits.max_documents} />
          <Meter label="Storage (MB)" used={usage.storage_mb} max={usage.plan_limits.storage_quota_mb} />
          {!!usage.include_labels?.length && (
            <p className="text-xs text-[var(--text-muted)]">
              Included add-ons: {usage.include_labels.join(" · ")}
            </p>
          )}
          {!!usage.extra_addon_labels?.length && (
            <p className="text-xs text-[var(--text-primary)]">
              Extra entitled add-ons: {usage.extra_addon_labels.join(" · ")}
            </p>
          )}
        </div>
      )}
      {standalone && (
        <div className="rounded-xl border border-[var(--border)] p-4 bg-[var(--surface)] space-y-2 text-sm">
          <p className="font-medium">Standalone settlement</p>
          <p className="text-[var(--text-muted)]">
            This copy is licensed on the premises. The plan and extra add-ons
            are encoded in the signed install license after invoice settlement —
            they are not changed from these cards. Send Easy-Books your Install ID
            to upgrade or add a vertical.
          </p>
          {license?.install_id && (
            <p className="text-xs">
              Install ID: <code className="break-all">{license.install_id}</code>
            </p>
          )}
          {license?.licensed && license.plan && (
            <p className="text-xs">
              Licensed plan: <strong className="capitalize">{license.plan}</strong>
              {license.addons?.length ? ` · extra add-ons: ${license.addons.join(", ")}` : ""}
            </p>
          )}
          <Link href="/settings" className="text-xs text-[var(--primary)] underline">
            Open Install license →
          </Link>
        </div>
      )}
      {msg && <p className="text-sm text-emerald-700">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}
      <div className="grid gap-3 sm:grid-cols-3">
        {PLAN_ORDER.map((p) => {
          const card = plans[p]
          const current = usage?.plan === p
          return (
            <div
              key={p}
              className={`rounded-xl border p-4 text-left space-y-2 ${
                current ? "border-[#b8943f] bg-[#b8943f]/5" : "border-[var(--border)]"
              }`}
            >
              <div className="font-medium capitalize">{card?.label || p}</div>
              <div className="text-sm text-[var(--text-muted)]">
                ${card?.price ?? "—"}/mo
              </div>
              <div className="text-xs text-[var(--text-muted)]">
                {card?.summary}
              </div>
              <div className="text-xs text-[var(--text-muted)]">
                {card?.max_users} users · {card?.max_documents} docs
              </div>
              {!!card?.include_labels?.length && p !== "enterprise" && (
                <ul className="text-[11px] text-[var(--text-muted)] list-disc pl-4 space-y-0.5 max-h-36 overflow-auto">
                  {card.include_labels.map((label) => (
                    <li key={label}>{label}</li>
                  ))}
                </ul>
              )}
              {p === "enterprise" && (
                <p className="text-[11px] text-[var(--text-muted)]">
                  Every first-party module, including mill / hospital / telecom verticals.
                </p>
              )}
              <button
                type="button"
                onClick={() => upgrade(p)}
                disabled={current || standalone}
                title={standalone ? "Plan is set by the install license" : undefined}
                className="mt-1 w-full rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:border-[#b8943f] disabled:opacity-40"
              >
                {current ? "Current plan" : standalone ? "Licensed separately" : `Choose ${p}`}
              </button>
            </div>
          )
        })}
      </div>

      {!!industry.length && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Industry add-ons</h2>
          <p className="text-xs text-[var(--text-muted)]">
            ${industry[0]?.price}/mo each on Starter or Pro. Included in Enterprise.
            Standalone: name the vertical on the license after invoice.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {industry.map((sku) => (
              <div key={sku.id} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm flex justify-between gap-2">
                <span>{sku.label}</span>
                <span className="text-xs text-[var(--text-muted)]">${sku.price}/mo</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {!!localization.length && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Country packs</h2>
          <p className="text-xs text-[var(--text-muted)]">
            ${localization[0]?.price}/mo each on Starter. Included from Pro.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {localization.map((sku) => (
              <div key={sku.id} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm flex justify-between gap-2">
                <span>{sku.label}</span>
                <span className="text-xs text-[var(--text-muted)]">${sku.price}/mo · from {sku.included_from}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <p className="text-xs text-[var(--text-muted)]">
        {standalone
          ? "Cloud Stripe Checkout is disabled on standalone copies. Field staff encode plan + add-ons in the EB1 license token."
          : "Live Stripe Checkout needs STRIPE_SECRET_KEY plus STRIPE_PRICE_STARTER / STRIPE_PRICE_PRO / STRIPE_PRICE_ENTERPRISE. Without a secret key, SaaS upgrades apply offline. Add-on SKUs are invoiced and entitled by Easy-Books (they are not self-serve Stripe products yet)."}
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
