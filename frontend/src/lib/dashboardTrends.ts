import { apiFetch } from "@/lib/api"

// One payload backs all trend widgets — every series is aligned to `months`.
export interface AgingBuckets {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
}
export interface TrendsData {
  months: string[]
  ar_ap_trend: { months: string[]; ar: number[]; ap: number[] }
  cashflow: { inflow: number[]; outflow: number[]; net: number[] }
  cash_balance: number[]
  sales_purchases: { sales: number[]; purchases: number[] }
  collections: number[]
  expense_trend: { accounts: string[]; series: number[][] }
  revenue_breakdown: { account: string; amount: number }[]
  top_vendors: { name: string; total: number }[]
  invoice_status: { status: string; count: number; amount: number }[]
  ap_aging: AgingBuckets
}

const TTL_MS = 60_000
let cache: { at: number; promise: Promise<TrendsData> } | null = null

/** Shared cached fetch so ten widgets mounting at once issue one request. */
export function fetchDashboardTrends(): Promise<TrendsData> {
  if (cache && Date.now() - cache.at < TTL_MS) return cache.promise
  const promise = apiFetch<TrendsData>("/api/reports/dashboard/trends?months=12")
  cache = { at: Date.now(), promise }
  promise.catch(() => { cache = null })
  return promise
}

// ── Day Book ─────────────────────────────────────────────────────────────────
export interface DayBookDocSummary { count: number; total: number }
export interface DayBookData {
  date: string
  vouchers: { type: string; count: number; total: number }[]
  voucher_totals: { count: number; total: number }
  documents: {
    invoices: DayBookDocSummary
    bills: DayBookDocSummary
    payments_received: DayBookDocSummary
    payments_made: DayBookDocSummary
  }
  activity: { category: string; count: number }[]
}

export function fetchDayBook(date: string): Promise<DayBookData> {
  return apiFetch<DayBookData>(`/api/reports/dashboard/day-book?date=${date}`)
}

/** "YYYY-MM" → short month label for chart axes. */
export function monthLabel(m: string): string {
  const [y, mo] = m.split("-")
  return new Date(+y, +mo - 1).toLocaleString("default", { month: "short" })
}
