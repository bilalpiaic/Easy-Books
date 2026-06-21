import React from "react"
import type { TFunction } from "i18next"
import Link from "next/link"
import { Bar, Doughnut, Line } from "react-chartjs-2"
import type { ChartOptions, ChartData as ChartJsData } from "chart.js"
import RecentTransactions from "@/components/RecentTransactions"
import BankBalancesWidget from "@/components/dashboard/widgets/BankBalancesWidget"
import TopProductsWidget from "@/components/dashboard/widgets/TopProductsWidget"
import InventorySummaryWidget from "@/components/dashboard/widgets/InventorySummaryWidget"
import HRMSummaryWidget from "@/components/dashboard/widgets/HRMSummaryWidget"
import QuickActionsWidget from "@/components/dashboard/widgets/QuickActionsWidget"
import { apiFetch } from "@/lib/api"
import type { AppSettings } from "@/context/SettingsContext"
import {
  TrendingUp, TrendingDown, Hash, Wallet, ArrowDownLeft, ArrowUpRight, Clock,
  Package, AlertTriangle, FileSignature, Receipt, Banknote, CalendarClock,
  CalendarDays, Users, Briefcase, Truck, Landmark, Scale, HelpCircle,
} from "lucide-react"

// ── Shared data shapes (moved here from page.tsx; page now imports them) ──────
export interface ArAging {
  current: number; "1_30": number; "31_60": number; "61_90": number; over_90: number
}
export interface DashboardSummary {
  total_revenue: number; total_expense: number; transaction_count: number
  ar_outstanding: number; ap_outstanding: number; overdue_invoices: number
  unpaid_bills: number; low_stock_items: number; cash_balance: number
  ar_aging: ArAging | null; ap_due_week: number
}
export interface DashboardData { summary: DashboardSummary }
export interface ChartData {
  monthly: { month: string; revenue: number; expenses: number; profit: number }[]
  expense_breakdown: { account: string; amount: number }[]
  top_customers: { name: string; total: number }[]
}

// chart.js configs + options computed once in page.tsx and passed down
export interface DashboardChartConfigs {
  barData: { labels: string[]; datasets: object[] }
  lineData: { labels: string[]; datasets: object[] }
  doughnutData: { labels: string[]; datasets: object[] }
  customerBarData: { labels: string[]; datasets: object[] }
  agingBarData: { labels: string[]; datasets: { data: number[]; backgroundColor: string[]; borderRadius: number }[] }
  baseChartOpts: ChartOptions<"bar">
  lineOpts: ChartOptions<"line">
  doughnutOpts: ChartOptions<"doughnut">
}

export interface WidgetContext {
  data: DashboardData | null
  charts: ChartData | null
  s: DashboardSummary | undefined
  netProfit: number
  margin: string | null
  fmt: (n: number) => string
  agingLabels: string[]
  agingValues: number[] | null
  chartConfigs: DashboardChartConfigs
  settings: AppSettings
  reloadSettings: () => void
  checklistDismissed: boolean
  setChecklistDismissed: (v: boolean) => void
  t: TFunction
  quickActions: string[]
  updateQuickActions: (ids: string[]) => Promise<void>
}

export interface WidgetSize { w: number; h: number }
export interface WidgetDef {
  id: string
  title: string
  defaultVisible: boolean        // retained from Phase 1; unused by the grid but harmless
  defaultSize: WidgetSize        // cells on the 4-col desktop grid
  minSize: WidgetSize
  pinned?: boolean               // rendered in the fixed notices strip, NOT a grid item
  conditional?: boolean          // render() may return null (e.g. ar_aging when no data)
  defaultOnGrid?: boolean        // default true; false = not on the default dashboard, add via panel
  render: (ctx: WidgetContext) => React.ReactNode
}

export function ChartSkeleton() {
  return <div className="h-full w-full shimmer rounded-lg" />
}

interface PrimaryKpiProps {
  label: string; value: string | null; icon: React.ElementType
  bg: string; border: string; text: string; sub?: string; compact?: boolean
}
export function PrimaryKpi({ label, value, icon: Icon, bg, border, text, sub, compact }: PrimaryKpiProps) {
  return (
    <div className={`${bg} ${border} border rounded-xl p-3 card-lift`}>
      <div className="flex items-start justify-between gap-1.5">
        <div className="min-w-0 flex-1">
          <p className={`text-[9px] font-bold uppercase tracking-[0.12em] ${text} opacity-70`}>{label}</p>
          {value === null ? <div className="shimmer h-5 w-20 rounded mt-1.5" /> : <p className={`${compact ? "text-base" : "text-sm sm:text-base"} font-bold ${text} mt-1 leading-none truncate`}>{value}</p>}
          {sub && <p className={`text-[9px] ${text} opacity-55 mt-0.5 font-medium`}>{sub}</p>}
        </div>
        <Icon className={`w-4 h-4 ${text} opacity-25 flex-shrink-0 mt-0.5`} />
      </div>
    </div>
  )
}

interface SecondaryKpiProps {
  label: string; value: string | null; icon: React.ElementType; color: string
  href: string; badge?: { count: number; label: string; color: string }; valueClass?: string
}
export function SecondaryKpi({ label, value, icon: Icon, color, href, badge, valueClass }: SecondaryKpiProps) {
  return (
    <Link href={href} className="bg-white border border-[#ede9e2] rounded-xl p-2.5 flex flex-col gap-1 hover:border-[#b8943f]/40 hover:shadow-sm transition-all group">
      <div className="flex items-center gap-1.5">
        <Icon className={`w-3 h-3 ${color}`} />
        <span className="text-[9px] font-bold uppercase tracking-[0.10em] text-[#1a1814]/50">{label}</span>
      </div>
      {value === null ? <div className="shimmer h-4 w-14 rounded" /> : <p className={`text-sm font-bold text-[#1a1814] leading-none ${valueClass ?? ""}`}>{value}</p>}
      {badge && <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full self-start ${badge.color}`}>{badge.count} {badge.label}</span>}
    </Link>
  )
}

const ONBOARDING_STEPS = [
  { key: "company_profile", label: "Upload company logo",     href: "/settings#company" },
  { key: "first_customer",  label: "Add your first customer", href: "/customers" },
  { key: "payment_terms",   label: "Set up payment terms",    href: "/settings#payment-terms" },
  { key: "first_invoice",   label: "Create your first invoice", href: "/invoices" },
  { key: "first_bill",      label: "Record your first bill",  href: "/bills" },
]

export interface QuickActionDef {
  id: string
  label: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  color: string
}

export const ALL_QUICK_ACTIONS: QuickActionDef[] = [
  { id: "new_invoice",   label: "New Invoice",       href: "/invoices",          icon: FileSignature, color: "text-green-600" },
  { id: "new_bill",      label: "New Bill",          href: "/bills",             icon: Receipt,       color: "text-orange-600" },
  { id: "new_entry",     label: "New Entry",         href: "/entry",             icon: Hash,          color: "text-blue-600" },
  { id: "attendance",    label: "Attendance",        href: "/attendance",        icon: CalendarDays,  color: "text-indigo-600" },
  { id: "new_payroll",   label: "New Payroll Run",   href: "/payroll/new",       icon: Briefcase,     color: "text-violet-600" },
  { id: "employees",     label: "Employees",         href: "/employees",         icon: Users,         color: "text-cyan-600" },
  { id: "products",      label: "Products",          href: "/products",          icon: Package,       color: "text-purple-600" },
  { id: "customers",     label: "Customers",         href: "/customers",         icon: ArrowDownLeft, color: "text-emerald-600" },
  { id: "vendors",       label: "Vendors",           href: "/vendors",           icon: Truck,         color: "text-amber-700" },
  { id: "bank",          label: "Banking",           href: "/banking",           icon: Landmark,      color: "text-slate-600" },
  { id: "trial_balance", label: "Trial Balance",     href: "/trial-balance",     icon: Scale,         color: "text-rose-600" },
  { id: "workflow",      label: "Workflow Guide",    href: "/workflow",          icon: TrendingUp,    color: "text-[#b8943f]" },
  { id: "guide",         label: "User Guide",        href: "/guide",             icon: HelpCircle,    color: "text-[#1a1814]" },
]

export const DEFAULT_QUICK_ACTION_IDS = [
  "new_invoice", "new_bill", "new_entry", "attendance", "products", "workflow", "guide",
]

export const WIDGET_REGISTRY: WidgetDef[] = [
  {
    id: "quick_actions",
    title: "Quick Actions",
    defaultVisible: true,
    defaultSize: { w: 4, h: 1 }, minSize: { w: 2, h: 1 },
    render: (ctx) => (
      <QuickActionsWidget quickActions={ctx.quickActions} updateQuickActions={ctx.updateQuickActions} />
    ),
  },
  {
    id: "onboarding",
    title: "Setup Checklist",
    defaultVisible: true,
    defaultSize: { w: 4, h: 2 }, minSize: { w: 4, h: 1 }, pinned: true,
    conditional: true,
    render: (ctx) => {
      const { settings, checklistDismissed, setChecklistDismissed, reloadSettings } = ctx
      if (checklistDismissed || settings.onboarding_dismissed === "true") return null
      let steps: Record<string, boolean> = {}
      try { steps = JSON.parse(settings.onboarding_steps || "{}") } catch { return null }
      const total = ONBOARDING_STEPS.length
      const done = ONBOARDING_STEPS.filter(s => steps[s.key]).length
      if (done === total) return null
      return (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-3">
                <FileSignature className="w-4 h-4 text-amber-600" />
                <h3 className="text-sm font-bold text-amber-900">{ctx.t('common.setupChecklist', 'Setup Checklist')} — {done} of {total} complete</h3>
                <div className="flex-1 bg-amber-200 rounded-full h-1.5 max-w-[120px]">
                  <div className="bg-amber-500 h-1.5 rounded-full transition-all" style={{ width: `${done / total * 100}%` }} />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {ONBOARDING_STEPS.map(step => (
                  <Link key={step.key} href={step.href}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      steps[step.key]
                        ? "bg-amber-100 text-amber-700 line-through opacity-60"
                        : "bg-white border border-amber-200 text-amber-800 hover:bg-amber-100"
                    }`}
                  >
                    <span className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-bold ${steps[step.key] ? "bg-green-500 text-white" : "bg-amber-200 text-amber-700"}`}>
                      {steps[step.key] ? "✓" : "○"}
                    </span>
                    {step.label}
                  </Link>
                ))}
              </div>
            </div>
            <button
              onClick={async () => {
                setChecklistDismissed(true)
                await apiFetch("/api/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ onboarding_dismissed: "true" }) })
                reloadSettings()
              }}
              className="text-amber-400 hover:text-amber-700 transition-colors flex-shrink-0"
              title="Dismiss checklist"
            >
              ✕
            </button>
          </div>
        </div>
      )
    },
  },
  {
    id: "primary_kpis",
    title: "Key Figures",
    defaultVisible: true,
    defaultSize: { w: 4, h: 1 }, minSize: { w: 2, h: 1 },
    render: (ctx) => {
      const { s, fmt, netProfit, margin } = ctx
      return (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <PrimaryKpi label={ctx.t('dashboard.revenue', 'Revenue')}    value={s ? fmt(s.total_revenue) : null}           icon={TrendingUp}  bg="bg-green-50"   border="border-green-200"   text="text-green-800"   sub={margin ? `${margin}% ${ctx.t('common.margin', 'margin')}` : undefined} />
          <PrimaryKpi label={ctx.t('dashboard.expenses', 'Expenses')}   value={s ? fmt(s.total_expense) : null}           icon={TrendingDown} bg="bg-red-50"     border="border-red-200"     text="text-red-800" />
          <PrimaryKpi label={ctx.t('dashboard.netProfit', 'Net Profit')} value={s ? fmt(netProfit) : null}                 icon={Wallet}      bg={netProfit < 0 ? "bg-red-50" : "bg-amber-50"} border={netProfit < 0 ? "border-red-200" : "border-amber-200"} text={netProfit < 0 ? "text-red-800" : "text-amber-800"} sub={netProfit < 0 ? ctx.t('common.netLoss', 'Net loss') : ctx.t('common.netGain', 'Net gain')} />
          <PrimaryKpi label={ctx.t('dashboard.cashAndBank', 'Cash & Bank')} value={s ? fmt(s.cash_balance ?? 0) : null}     icon={Banknote}    bg="bg-emerald-50" border="border-emerald-200"   text="text-emerald-800" sub={ctx.t('common.availableBalance', 'available balance')} />
          <PrimaryKpi label={ctx.t('common.vouchers', 'Vouchers')}   value={s ? s.transaction_count.toString() : null}    icon={Hash}        bg="bg-blue-50"    border="border-blue-200"     text="text-blue-800"    sub={ctx.t('common.posted_count', 'posted')} compact />
        </div>
      )
    },
  },
  {
    id: "secondary_kpis",
    title: "Receivables / Payables",
    defaultVisible: true,
    defaultSize: { w: 4, h: 1 }, minSize: { w: 2, h: 1 },
    render: (ctx) => {
      const { s, fmt } = ctx
      return (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <SecondaryKpi label={ctx.t('dashboard.outstandingAr', 'AR Outstanding')}   value={s ? fmt(s.ar_outstanding) : null}       icon={ArrowDownLeft}  color="text-green-700"  href="/invoices"                badge={s?.overdue_invoices ? { count: s.overdue_invoices, label: "overdue", color: "bg-red-100 text-red-700" } : undefined} />
          <SecondaryKpi label={ctx.t('dashboard.outstandingAp', 'AP Outstanding')}   value={s ? fmt(s.ap_outstanding) : null}       icon={ArrowUpRight}   color="text-orange-700" href="/bills"                   badge={s?.unpaid_bills ? { count: s.unpaid_bills, label: "unpaid", color: "bg-orange-100 text-orange-700" } : undefined} />
          <SecondaryKpi label={ctx.t('dashboard.openInvoices', 'Overdue Invoices')} value={s ? s.overdue_invoices.toString() : null}   icon={Clock}          color="text-red-600"    href="/invoices"                valueClass={s && s.overdue_invoices > 0 ? "text-red-600 font-bold" : undefined} />
          <SecondaryKpi label={ctx.t('dashboard.lowStock', 'Low Stock Items')}  value={s ? s.low_stock_items.toString() : null}    icon={Package}        color="text-purple-600" href="/products?low_stock=true" valueClass={s && s.low_stock_items > 0 ? "text-amber-600 font-bold" : undefined} />
          <SecondaryKpi label={ctx.t('dashboard.apDueWeek', 'AP Due This Week')} value={s ? fmt(s.ap_due_week ?? 0) : null}     icon={CalendarClock}  color="text-rose-600"   href="/bills"                   valueClass={s && (s.ap_due_week ?? 0) > 0 ? "text-rose-600 font-bold" : undefined} />
        </div>
      )
    },
  },
  {
    id: "ar_aging",
    title: "AR Aging",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    conditional: true,
    render: (ctx) => {
      const { s, fmt, agingLabels, agingValues } = ctx
      const { agingBarData } = ctx.chartConfigs
      return s?.ar_aging ? (
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm h-full flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">{ctx.t('page.arAging', 'AR Aging')} (Receivables)</p>
              <p className="text-[10px] text-[#1a1814]/40 mt-0.5">{ctx.t('dashboard.arAgingSubtitle', 'Outstanding invoice amounts by age bucket')}</p>
            </div>
            <Link href="/invoices" className="text-[11px] text-[#b8943f] font-semibold hover:text-[#8a6d2e]">{ctx.t('page.invoices', 'Invoices')} →</Link>
          </div>
          <div className="flex-1 min-h-0">
            <Bar data={agingBarData as ChartJsData<"bar">} options={{
              responsive: true, maintainAspectRatio: false,
              plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmt(ctx.parsed.y as number) } } },
              scales: {
                x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: v => fmt(v as number) } },
              },
            } as ChartOptions<"bar">} />
          </div>
          <div className="flex items-center gap-4 mt-2 flex-wrap">
            {agingLabels.map((label, i) => (
              <span key={label} className="flex items-center gap-1 text-[10px] text-[#1a1814]/55">
                <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ backgroundColor: agingBarData.datasets[0].backgroundColor[i] }} />
                {label}: <span className="font-semibold text-[#1a1814]/75">{fmt(agingValues?.[i] ?? 0)}</span>
              </span>
            ))}
          </div>
        </div>
      ) : null
    },
  },
  {
    id: "alerts",
    title: "Action Alerts",
    defaultVisible: true,
    defaultSize: { w: 4, h: 1 }, minSize: { w: 4, h: 1 }, pinned: true,
    conditional: true,
    render: (ctx) => {
      const { s } = ctx
      return (s && (s.overdue_invoices > 0 || s.low_stock_items > 0)) ? (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex flex-wrap gap-3 items-center">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span className="text-sm font-medium text-amber-800">Action required:</span>
          {s.overdue_invoices > 0 && <Link href="/invoices" className="text-sm text-amber-700 underline underline-offset-2 hover:text-amber-900">{s.overdue_invoices} overdue invoice{s.overdue_invoices > 1 ? "s" : ""}</Link>}
          {s.overdue_invoices > 0 && s.low_stock_items > 0 && <span className="text-amber-400">·</span>}
          {s.low_stock_items > 0 && <Link href="/products?low_stock=true" className="text-sm text-amber-700 underline underline-offset-2 hover:text-amber-900">{s.low_stock_items} low-stock product{s.low_stock_items > 1 ? "s" : ""}</Link>}
        </div>
      ) : null
    },
  },
  {
    id: "monthly_rev_exp",
    title: "Monthly Revenue vs Expenses",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: (ctx) => {
      const { charts } = ctx
      const { barData, baseChartOpts } = ctx.chartConfigs
      return (
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm h-full flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">Monthly Revenue vs Expenses</p>
            <div className="flex items-center gap-3 text-[10px] font-medium text-[#1a1814]/50">
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-green-500 inline-block" />Revenue</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-red-500 inline-block" />Expenses</span>
            </div>
          </div>
          <div className="flex-1 min-h-0">
            {charts ? <Bar data={barData as ChartJsData<"bar">} options={baseChartOpts} /> : <ChartSkeleton />}
          </div>
        </div>
      )
    },
  },
  {
    id: "net_profit_trend",
    title: "Net Profit Trend",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: (ctx) => {
      const { charts } = ctx
      const { lineData, lineOpts } = ctx.chartConfigs
      return (
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm h-full flex flex-col">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-3">Net Profit Trend</p>
          <div className="flex-1 min-h-0">
            {charts ? <Line data={lineData as ChartJsData<"line">} options={lineOpts} /> : <ChartSkeleton />}
          </div>
        </div>
      )
    },
  },
  {
    id: "expense_breakdown",
    title: "Expense Breakdown",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: (ctx) => {
      const { charts } = ctx
      const { doughnutData, doughnutOpts } = ctx.chartConfigs
      return (
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm h-full flex flex-col">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-3">Expense Breakdown (YTD)</p>
          <div className="flex-1 min-h-0">
            {charts ? (
              charts.expense_breakdown.length > 0
                ? <Doughnut data={doughnutData as ChartJsData<"doughnut">} options={doughnutOpts} />
                : <div className="h-full flex items-center justify-center text-sm text-[#1a1814]/40">No expense data</div>
            ) : <ChartSkeleton />}
          </div>
        </div>
      )
    },
  },
  {
    id: "top_customers",
    title: "Top Customers",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: (ctx) => {
      const { charts } = ctx
      const { customerBarData, baseChartOpts } = ctx.chartConfigs
      return (
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm h-full flex flex-col">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-3">Top Customers by Revenue</p>
          <div className="flex-1 min-h-0">
            {charts ? (
              charts.top_customers.length > 0
                ? <Bar data={customerBarData as ChartJsData<"bar">} options={{ ...baseChartOpts, indexAxis: "y" } as ChartOptions<"bar">} />
                : <div className="h-full flex items-center justify-center text-sm text-[#1a1814]/40">No invoice data</div>
            ) : <ChartSkeleton />}
          </div>
        </div>
      )
    },
  },
  {
    id: "recent_transactions",
    title: "Recent Transactions",
    defaultVisible: true,
    defaultSize: { w: 4, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <RecentTransactions />,
  },
  {
    id: "bank_balances", title: "Bank Balances", defaultVisible: true, defaultOnGrid: false,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <BankBalancesWidget />,
  },
  {
    id: "top_products", title: "Top Products", defaultVisible: true, defaultOnGrid: false,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <TopProductsWidget />,
  },
  {
    id: "inventory_summary", title: "Inventory Summary", defaultVisible: true, defaultOnGrid: false,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    render: () => <InventorySummaryWidget />,
  },
  {
    id: "hrm_summary", title: "HRM & Payroll", defaultVisible: true,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    render: () => <HRMSummaryWidget />,
  },
]
