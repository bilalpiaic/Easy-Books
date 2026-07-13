"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  Radio, Wallet, Network, Smartphone, Target, Banknote,
  ReceiptText, Percent, ScrollText, Coins, TrendingUp,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import DateRangePicker from "@/components/DateRangePicker"
import { Tile, Section, PageHeader, ErrorBanner, money } from "@/components/telecom/primitives"
import { useTranslation } from "react-i18next"

interface Dashboard {
  as_of: string
  tracker: {
    deposit_balance: string; load_float: string
    rso_load_receivable: string; retail_load_receivable: string
  }
  commissions: { receivable: string }
  rso: { agent_count: number; stock_receivable: string }
  mobile_money: { float_asset: string; float_liability: string }
  sim: { inventory_cost: string; total_received: number; total_activated: number; available: number }
  fca: { month: string; actual: number; target: string | null; achievement_pct: string | null }
}

interface RevenueStream { code: string; name: string; amount: string }
interface RevenueResp { items: RevenueStream[]; total_revenue: string }

interface StockRow {
  rso_id: number; name: string; territory: string | null
  stock_issuance: string; load_issued: string; hlr_issued: string
  sim_issued_qty: number; other_stock: string; bank_deposits: string
  closing_hlr_load_dep: string; fca_hits: number | null; closing_sim_fca: number | null
}
interface StockTotals {
  stock_issuance: string; load_issued: string; hlr_issued: string
  sim_issued_qty: number; other_stock: string; bank_deposits: string
  closing_hlr_load_dep: string; fca_hits: number; closing_sim_fca: number
}
interface StockResp { items: StockRow[]; totals: StockTotals; period: { start: string | null; end: string | null } }

export default function TelecomDashboardPage() {
  const { t } = useTranslation()

  const [data, setData] = useState<Dashboard | null>(null)
  const [rev, setRev] = useState<RevenueResp | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stock, setStock] = useState<StockResp | null>(null)
  const [siStart, setSiStart] = useState("")
  const [siEnd, setSiEnd] = useState("")

  useEffect(() => {
    const qs = new URLSearchParams()
    if (siStart) qs.set("start", siStart)
    if (siEnd) qs.set("end", siEnd)
    apiFetch<StockResp>(`/api/telecom/reports/stock-issuance${qs.toString() ? `?${qs}` : ""}`)
      .then(setStock)
      .catch(() => {})
  }, [siStart, siEnd])

  useEffect(() => {
    apiFetch<Dashboard>("/api/telecom/reports/dashboard")
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
    apiFetch<RevenueResp>("/api/telecom/reports/revenue-by-stream")
      .then(setRev)
      .catch(() => {})
  }, [])

  const fca = data?.fca
  const pct = fca?.achievement_pct ? Number(fca.achievement_pct) : null

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Radio}
        title="Telecom Franchise"
        subtitle="Daily operations across Tracker, RSO channel, SIM, mobile money and targets."
      />

      <HelpCallout title="How the franchise money flows" tone="tip">
        <ol className="list-decimal pl-4 space-y-1">
          <li><b>Top up the Tracker</b> — deposit cash with the operator (Dr Tracker Deposit / Cr Bank).</li>
          <li><b>Place a load order</b> — convert deposit to load float; you earn a 3% uplift commission at disbursement.</li>
          <li><b>Distribute load</b> down the chain: MSR → RSO → Retail outlets.</li>
          <li><b>Collect daily</b> from each RSO — load portion + stock portion ± variance.</li>
          <li><b>Hit FCA targets</b> — first-call activations are counted toward a monthly target that pays a commission.</li>
        </ol>
        <p className="mt-2 text-[11px] opacity-80">
          Every posting keeps <code>sum(debit) == sum(credit)</code>. The tiles below read straight from the GL.
        </p>
      </HelpCallout>

      <ErrorBanner error={error} />

      <Section title="Tracker & Load float">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Tile icon={Wallet} label="Tracker deposit" value={money(data?.tracker.deposit_balance)} hint="Acct 1210" href="/ledger?account=1210" />
          <Tile icon={Coins} label="Load float (MSR)" value={money(data?.tracker.load_float)} hint="Acct 1211" href="/ledger?account=1211" />
          <Tile icon={Network} label="RSO load receivable" value={money(data?.tracker.rso_load_receivable)} hint="Acct 1212" href="/ledger?account=1212" />
          <Tile icon={Network} label="Retail load receivable" value={money(data?.tracker.retail_load_receivable)} hint="Acct 1213" href="/ledger?account=1213" />
        </div>
      </Section>

      <Section title="Channel & receivables">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Tile icon={Percent} label="Commission receivable" value={money(data?.commissions.receivable)} hint="Acct 1110" href="/ledger?account=1110" />
          <Tile icon={Network} label="RSO agents" value={data ? String(data.rso.agent_count) : "—"} hint={`Stock rec. ${money(data?.rso.stock_receivable)}`} />
          <Tile icon={Banknote} label="Mobile money float" value={money(data?.mobile_money.float_asset)} hint={`Liability ${money(data?.mobile_money.float_liability)}`} />
          <Tile icon={Smartphone} label="SIMs available" value={data ? String(data.sim.available) : "—"} hint={`${data?.sim.total_activated ?? 0} / ${data?.sim.total_received ?? 0} activated`} />
        </div>
      </Section>

      <Section title={`FCA target — ${fca?.month ?? "this month"}`}>
        <div className="bg-white border border-[var(--border)] rounded-2xl px-4 py-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-[var(--text-primary)]/60">First-call activations</span>
            <span className="font-bold font-bold text-[var(--text-primary)]">
              {fca?.actual ?? 0}{fca?.target ? ` / ${fca.target}` : ""}
            </span>
          </div>
          <div className="mt-2 h-2.5 rounded-full bg-[var(--border)] overflow-hidden">
            <div
              className="h-full bg-[var(--primary)] transition-all"
              style={{ width: pct !== null ? `${Math.min(pct, 100)}%` : "0%" }}
            />
          </div>
          <div className="mt-1.5 text-xs text-[var(--text-primary)]/55">
            {pct !== null ? `${pct}% of monthly target` : "No target set for this month — add one under FCA & Targets."}
          </div>
        </div>
      </Section>

      <Section title="Revenue by stream">
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              {(rev?.items ?? []).filter(s => Number(s.amount) !== 0).map(s => (
                <tr key={s.code} className="border-t border-[var(--border)] first:border-t-0">
                  <td className="px-4 py-2 font-mono text-xs text-[var(--text-primary)]/60">{s.code}</td>
                  <td className="px-4 py-2">{s.name}</td>
                  <td className="px-4 py-2 text-right font-medium">{money(s.amount)}</td>
                </tr>
              ))}
              {rev && rev.items.every(s => Number(s.amount) === 0) && (
                <tr><td className="px-4 py-6 text-center text-[var(--text-primary)]/50" colSpan={3}>No revenue posted yet.</td></tr>
              )}
            </tbody>
            {rev && (
              <tfoot>
                <tr className="border-t-2 border-[var(--primary)]/30 bg-[var(--bg-page)] font-bold">
                  <td className="px-4 py-2" colSpan={2}>Total revenue</td>
                  <td className="px-4 py-2 text-right flex items-center justify-end gap-1">
                    <TrendingUp className="w-3.5 h-3.5 text-[var(--primary)]" />{money(rev.total_revenue)}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </Section>

      <Section title="Stock & Issuance (per RSO)">
        <div className="flex flex-wrap items-end gap-3 mb-3">
          <DateRangePicker start={siStart} end={siEnd} onStartChange={setSiStart} onEndChange={setSiEnd} />
          {(siStart || siEnd) && (
            <button onClick={() => { setSiStart(""); setSiEnd("") }}
              className="text-xs text-[var(--primary)] hover:underline">Clear</button>
          )}
        </div>
        <div className="bg-white border border-[var(--border)] rounded-2xl overflow-x-auto">
          <table className="w-full text-sm min-w-[920px]">
            <thead className="bg-[var(--bg-page)] text-[10px] uppercase tracking-widest text-[var(--text-primary)]/60">
              <tr>
                <th className="px-3 py-2 text-left">RSO</th>
                <th className="px-3 py-2 text-right">Stock Iss.</th>
                <th className="px-3 py-2 text-right">Load Iss.</th>
                <th className="px-3 py-2 text-right">HLR Iss.</th>
                <th className="px-3 py-2 text-right">Other Stock</th>
                <th className="px-3 py-2 text-right">SIM Iss.</th>
                <th className="px-3 py-2 text-right">Bank Dep.</th>
                <th className="px-3 py-2 text-right">FCA Hits</th>
                <th className="px-3 py-2 text-right">Closing (SIM−FCA)</th>
                <th className="px-3 py-2 text-right">Closing (HLR+Load−Dep)</th>
              </tr>
            </thead>
            <tbody>
              {(stock?.items ?? []).map(r => (
                <tr key={r.rso_id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2">{r.name}{r.territory ? ` · ${r.territory}` : ""}</td>
                  <td className="px-3 py-2 text-right">{money(r.stock_issuance)}</td>
                  <td className="px-3 py-2 text-right">{money(r.load_issued)}</td>
                  <td className="px-3 py-2 text-right">{money(r.hlr_issued)}</td>
                  <td className="px-3 py-2 text-right">{money(r.other_stock)}</td>
                  <td className="px-3 py-2 text-right">{r.sim_issued_qty}</td>
                  <td className="px-3 py-2 text-right">{money(r.bank_deposits)}</td>
                  <td className="px-3 py-2 text-right text-[var(--text-primary)]/35">—</td>
                  <td className="px-3 py-2 text-right text-[var(--text-primary)]/35">—</td>
                  <td className="px-3 py-2 text-right">{money(r.closing_hlr_load_dep)}</td>
                </tr>
              ))}
              {stock && stock.items.length === 0 && (
                <tr><td className="px-4 py-6 text-center text-[var(--text-primary)]/50" colSpan={10}>No RSO activity for this period.</td></tr>
              )}
            </tbody>
            {stock && stock.items.length > 0 && (
              <tfoot>
                <tr className="border-t-2 border-[var(--primary)]/30 bg-[var(--bg-page)] font-bold">
                  <td className="px-3 py-2">TOTAL</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.stock_issuance)}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.load_issued)}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.hlr_issued)}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.other_stock)}</td>
                  <td className="px-3 py-2 text-right">{stock.totals.sim_issued_qty}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.bank_deposits)}</td>
                  <td className="px-3 py-2 text-right">{stock.totals.fca_hits}</td>
                  <td className="px-3 py-2 text-right">{stock.totals.closing_sim_fca}</td>
                  <td className="px-3 py-2 text-right">{money(stock.totals.closing_hlr_load_dep)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </Section>

      <Section title="Jump to">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <QuickLink href="/telecom/tracker"      icon={Wallet}      title="Tracker & Load"   subtitle="Deposits, load orders, stock" />
          <QuickLink href="/telecom/rso"          icon={Network}     title="RSO Channel"      subtitle="Transfers & daily collections" />
          <QuickLink href="/telecom/sim"          icon={Smartphone}  title="SIM & Activations" subtitle="Batches, activations, sales" />
          <QuickLink href="/telecom/fca"          icon={Target}      title="FCA & Targets"    subtitle="Events, target commission" />
          <QuickLink href="/telecom/mobile-money" icon={Banknote}    title="Mobile Money"     subtitle="Float, deposits, withdrawals" />
          <QuickLink href="/telecom/postpaid"     icon={ReceiptText} title="Postpaid Billing" subtitle="Bills, collection, remittance" />
          <QuickLink href="/telecom/commissions"  icon={Percent}     title="Commissions"      subtitle="Statements & reconciliation" />
          <QuickLink href="/telecom/franchise"    icon={ScrollText}  title="Franchise Admin"  subtitle="Fee amortisation & royalty" />
        </div>
      </Section>
    </div>
  )
}

function QuickLink({ href, icon: Icon, title, subtitle }: {
  href: string; icon: React.ElementType; title: string; subtitle: string
}) {
  return (
    <Link href={href} className="bg-white border border-[var(--border)] rounded-xl px-4 py-3 hover:border-[var(--primary)]/60 transition-colors block">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-[var(--primary)]" />
        <div className="text-sm font-semibold text-[var(--text-primary)]">{title}</div>
      </div>
      <p className="text-xs text-[var(--text-primary)]/60 mt-1.5">{subtitle}</p>
    </Link>
  )
}
