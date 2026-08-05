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
import KpiCard from "@/components/dashboard/KpiCard"
import NetWorthTrendWidget from "@/components/dashboard/widgets/NetWorthTrendWidget"
import CashFlowTrendWidget from "@/components/dashboard/widgets/trends/CashFlowTrendWidget"
import CashBalanceTrendWidget from "@/components/dashboard/widgets/trends/CashBalanceTrendWidget"
import SalesPurchasesWidget from "@/components/dashboard/widgets/trends/SalesPurchasesWidget"
import CollectionsTrendWidget from "@/components/dashboard/widgets/trends/CollectionsTrendWidget"
import ProfitMarginWidget from "@/components/dashboard/widgets/trends/ProfitMarginWidget"
import RevenueBreakdownWidget from "@/components/dashboard/widgets/trends/RevenueBreakdownWidget"
import TopVendorsWidget from "@/components/dashboard/widgets/trends/TopVendorsWidget"
import InvoiceStatusWidget from "@/components/dashboard/widgets/trends/InvoiceStatusWidget"
import ApAgingWidget from "@/components/dashboard/widgets/trends/ApAgingWidget"
import ExpenseTrendWidget from "@/components/dashboard/widgets/trends/ExpenseTrendWidget"
import ArApTrendWidget from "@/components/dashboard/widgets/trends/ArApTrendWidget"
import DayBookWidget from "@/components/dashboard/widgets/trends/DayBookWidget"
import { apiFetch } from "@/lib/api"
import type { AppSettings } from "@/context/SettingsContext"
import {
  TrendingUp, TrendingDown, Hash, Wallet, ArrowDownLeft, ArrowUpRight, Clock,
  Package, AlertTriangle, FileSignature, Receipt, Banknote, CalendarClock,
  CalendarDays, Users, Briefcase, Truck, Landmark, Scale, HelpCircle,
  Factory, ClipboardCheck, DoorOpen, Radio, Activity, ShoppingCart, CircleDot, Layers,
} from "lucide-react"
import {
  OpsPrimaryKpis, OpsAlerts, OpsPipelineWidget,
  SpinningSummaryWidget, WeavingSummaryWidget, ProductionWipWidget,
  HealthcareCensusWidget, TelecomTrackerWidget, PurchasesPipelineWidget,
  TextileProcessingWidget,
} from "@/components/dashboard/widgets/OpsWidgets"
import {
  OpsProcessChart, OpsTrendChart, OpsStatusTable, OpsMixChart,
} from "@/components/dashboard/widgets/OpsCharts"
import type { OperationsSummary } from "@/lib/operationsSummary"
import { DEFAULT_FINANCIAL_QUICK_ACTIONS } from "@/lib/dashboardHome"
import type { DashboardView } from "@/lib/dashboardHome"

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
  /** Active home view — financial or operations. */
  view: DashboardView
  /** Aggregated ops KPIs (loaded when view === operations). */
  opsSummary: OperationsSummary | null
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
  /** When set, widget is only available if this module is installed. */
  requiredModule?: string
  /** Which home dashboard this widget belongs to. Defaults to financial. */
  home?: DashboardView | "both"
  render: (ctx: WidgetContext) => React.ReactNode
}

export function ChartSkeleton() {
  return <div className="h-full w-full shimmer rounded-lg" />
}


const ONBOARDING_STEPS = [
  { key: "company_profile", label: "Upload company logo",     href: "/settings?tab=company" },
  { key: "first_customer",  label: "Add your first customer", href: "/customers" },
  { key: "payment_terms",   label: "Set up payment terms",    href: "/settings?tab=accounting" },
  { key: "first_invoice",   label: "Create your first invoice", href: "/invoices" },
  { key: "first_bill",      label: "Record your first bill",  href: "/bills" },
]

export interface QuickActionDef {
  id: string
  label: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  requiredModule?: string
}

export const ALL_QUICK_ACTIONS: QuickActionDef[] = [
  { id: "new_invoice",   label: "New Invoice",       href: "/invoices",          icon: FileSignature, color: "text-green-600" },
  { id: "new_bill",      label: "New Bill",          href: "/bills",             icon: Receipt,       color: "text-orange-600" },
  { id: "new_entry",     label: "New Entry",         href: "/entry",             icon: Hash,          color: "text-blue-600" },
  { id: "attendance",    label: "Attendance",        href: "/attendance",        icon: CalendarDays,  color: "text-indigo-600", requiredModule: "hrm" },
  { id: "new_payroll",   label: "New Payroll Run",   href: "/payroll/new",       icon: Briefcase,     color: "text-violet-600", requiredModule: "hrm" },
  { id: "employees",     label: "Employees",         href: "/employees",         icon: Users,         color: "text-cyan-600", requiredModule: "hrm" },
  { id: "products",      label: "Products",          href: "/products",          icon: Package,       color: "text-purple-600", requiredModule: "inventory" },
  { id: "customers",     label: "Customers",         href: "/customers",         icon: ArrowDownLeft, color: "text-emerald-600" },
  { id: "vendors",       label: "Vendors",           href: "/vendors",           icon: Truck,         color: "text-amber-700" },
  { id: "bank",          label: "Banking",           href: "/banking",           icon: Landmark,      color: "text-slate-600" },
  { id: "trial_balance", label: "Trial Balance",     href: "/trial-balance",     icon: Scale,         color: "text-rose-600" },
  { id: "workflow",      label: "Workflow Guide",    href: "/workflow",          icon: TrendingUp,    color: "text-[#b8943f]" },
  { id: "guide",         label: "User Guide",        href: "/guide",             icon: HelpCircle,    color: "text-[#1a1814]" },
  // Operations / purpose quick actions
  { id: "new_demand",      label: "New Demand",          href: "/purchases/demands/new",              icon: ClipboardCheck, color: "text-amber-700", requiredModule: "purchase_store" },
  { id: "new_po",          label: "Purchase Orders",     href: "/manufacturing/purchase-orders",      icon: ShoppingCart,   color: "text-orange-600", requiredModule: "purchase_store" },
  { id: "gate_inward",     label: "Gate Inward",         href: "/purchases/gate-inward",              icon: DoorOpen,       color: "text-teal-700",  requiredModule: "purchase_store" },
  { id: "new_production",  label: "Production Orders",   href: "/manufacturing/production-orders",    icon: Factory,        color: "text-blue-700",  requiredModule: "production" },
  { id: "new_spin_lot",    label: "Spin Lots",           href: "/spinning/lots",                      icon: CircleDot,      color: "text-indigo-700", requiredModule: "spinning" },
  { id: "new_grey_lot",    label: "Grey Lots",           href: "/processing/lots",                    icon: Layers,         color: "text-teal-700",   requiredModule: "textile_processing" },
  { id: "new_opd",         label: "OPD",                 href: "/healthcare/opd",                     icon: Activity,       color: "text-rose-600",  requiredModule: "healthcare" },
  { id: "telecom_tracker", label: "Tracker & Load",      href: "/telecom/tracker",                    icon: Radio,          color: "text-cyan-700",  requiredModule: "telecom" },
]

export const DEFAULT_QUICK_ACTION_IDS = DEFAULT_FINANCIAL_QUICK_ACTIONS

export const WIDGET_REGISTRY: WidgetDef[] = [
  {
    id: "quick_actions",
    title: "Quick Actions",
    defaultVisible: true,
    defaultSize: { w: 4, h: 1 }, minSize: { w: 2, h: 1 },
    home: "both",
    render: (ctx) => (
      <QuickActionsWidget quickActions={ctx.quickActions} updateQuickActions={ctx.updateQuickActions} />
    ),
  },
  {
    id: "onboarding",
    title: "Setup Checklist",
    defaultVisible: true,
    defaultSize: { w: 4, h: 2 }, minSize: { w: 4, h: 1 }, pinned: true,
    home: "financial",
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
          <KpiCard title={ctx.t('dashboard.revenue', 'Revenue')}       value={s ? fmt(s.total_revenue) : null}          icon={TrendingUp}   tone="green"   sub={margin ? `${margin}% ${ctx.t('common.margin', 'margin')}` : undefined} />
          <KpiCard title={ctx.t('dashboard.expenses', 'Expenses')}     value={s ? fmt(s.total_expense) : null}          icon={TrendingDown} tone="red" />
          <KpiCard title={ctx.t('dashboard.netProfit', 'Net Profit')}  value={s ? fmt(netProfit) : null}                icon={Wallet}       tone={netProfit < 0 ? "red" : "amber"} sub={netProfit < 0 ? ctx.t('common.netLoss', 'Net loss') : ctx.t('common.netGain', 'Net gain')} />
          <KpiCard title={ctx.t('dashboard.cashAndBank', 'Cash & Bank')} value={s ? fmt(s.cash_balance ?? 0) : null}    icon={Banknote}     tone="emerald" sub={ctx.t('common.availableBalance', 'available balance')} />
          <KpiCard title={ctx.t('common.vouchers', 'Vouchers')}        value={s ? s.transaction_count.toString() : null} icon={Hash}        tone="blue"    sub={ctx.t('common.posted_count', 'posted')} />
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
          <KpiCard title={ctx.t('dashboard.outstandingAr', 'AR Outstanding')}  value={s ? fmt(s.ar_outstanding) : null}         icon={ArrowDownLeft} iconClass="text-green-700"  href="/invoices"                badge={s?.overdue_invoices ? { count: s.overdue_invoices, label: "overdue", className: "bg-red-100 text-red-700" } : undefined} />
          <KpiCard title={ctx.t('dashboard.outstandingAp', 'AP Outstanding')}  value={s ? fmt(s.ap_outstanding) : null}         icon={ArrowUpRight}  iconClass="text-orange-700" href="/bills"                   badge={s?.unpaid_bills ? { count: s.unpaid_bills, label: "unpaid", className: "bg-orange-100 text-orange-700" } : undefined} />
          <KpiCard title={ctx.t('dashboard.openInvoices', 'Overdue Invoices')} value={s ? s.overdue_invoices.toString() : null} icon={Clock}         iconClass="text-red-600"    href="/invoices"                valueClass={s && s.overdue_invoices > 0 ? "text-red-600 font-bold" : undefined} />
          <KpiCard title={ctx.t('dashboard.lowStock', 'Low Stock Items')}      value={s ? s.low_stock_items.toString() : null}  icon={Package}       iconClass="text-purple-600" href="/products?low_stock=true" valueClass={s && s.low_stock_items > 0 ? "text-amber-600 font-bold" : undefined} />
          <KpiCard title={ctx.t('dashboard.apDueWeek', 'AP Due This Week')}    value={s ? fmt(s.ap_due_week ?? 0) : null}       icon={CalendarClock} iconClass="text-rose-600"   href="/bills"                   valueClass={s && (s.ap_due_week ?? 0) > 0 ? "text-rose-600 font-bold" : undefined} />
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
    home: "financial",
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
    id: "net_worth_trend",
    title: "Net Worth",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <NetWorthTrendWidget />,
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
    // h:4 keeps 10 horizontal bars legible (was 5 rows at h:3)
    defaultSize: { w: 2, h: 4 }, minSize: { w: 2, h: 2 },
    render: (ctx) => {
      const { charts, fmt } = ctx
      const { customerBarData, baseChartOpts } = ctx.chartConfigs
      return (
        <div className="bg-white rounded-xl border border-[#ede9e2] p-4 shadow-sm h-full flex flex-col">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-3">Top Customers by Revenue</p>
          <div className="flex-1 min-h-0">
            {charts ? (
              charts.top_customers.length > 0
                ? <Bar data={customerBarData as ChartJsData<"bar">} options={{
                    ...baseChartOpts, indexAxis: "y",
                    // horizontal bar: y is the category axis (names), x is money —
                    // baseChartOpts' money-formatting y callback would render tick
                    // indices ("0".."9") instead of customer names here
                    scales: {
                      x: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 10 }, callback: (v: unknown) => fmt(Number(v)) } },
                      y: { grid: { display: false }, ticks: { font: { size: 10 } } },
                    },
                  } as ChartOptions<"bar">} />
                : <div className="h-full flex items-center justify-center text-sm text-[#1a1814]/40">No invoice data</div>
            ) : <ChartSkeleton />}
          </div>
        </div>
      )
    },
  },
  // ── Trend & graph widgets (one shared /dashboard/trends fetch) ────────────
  {
    id: "cashflow_trend", title: "Cash Flow", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <CashFlowTrendWidget />,
  },
  {
    id: "cash_balance_trend", title: "Cash Balance Trend", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <CashBalanceTrendWidget />,
  },
  {
    id: "sales_purchases", title: "Sales vs Purchases", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <SalesPurchasesWidget />,
  },
  {
    id: "collections_trend", title: "Collections", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <CollectionsTrendWidget />,
  },
  {
    id: "profit_margin_trend", title: "Profit Margin", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: (ctx) => <ProfitMarginWidget charts={ctx.charts} />,
  },
  {
    id: "revenue_breakdown", title: "Revenue Breakdown", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <RevenueBreakdownWidget />,
  },
  {
    id: "invoice_status", title: "Invoice Pipeline", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <InvoiceStatusWidget />,
  },
  {
    id: "ap_aging", title: "AP Aging", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <ApAgingWidget />,
  },
  {
    id: "top_vendors", title: "Top Vendors", defaultVisible: true,
    defaultSize: { w: 2, h: 4 }, minSize: { w: 2, h: 2 },
    render: () => <TopVendorsWidget />,
  },
  {
    id: "expense_trend", title: "Expense Trend", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <ExpenseTrendWidget />,
  },
  {
    id: "ar_ap_trend", title: "AR vs AP Trend", defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    render: () => <ArApTrendWidget />,
  },
  {
    id: "day_book", title: "Day Book", defaultVisible: true,
    defaultSize: { w: 2, h: 4 }, minSize: { w: 2, h: 2 },
    render: () => <DayBookWidget />,
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
    requiredModule: "inventory",
    render: () => <TopProductsWidget />,
  },
  {
    id: "inventory_summary", title: "Inventory Summary", defaultVisible: true, defaultOnGrid: false,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    requiredModule: "inventory",
    render: () => <InventorySummaryWidget />,
  },
  {
    id: "hrm_summary", title: "HRM & Payroll", defaultVisible: true,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    requiredModule: "hrm",
    home: "both",
    render: () => <HRMSummaryWidget />,
  },

  // ── Operations / purpose home widgets ─────────────────────────────────────
  {
    id: "ops_primary_kpis",
    title: "Operations KPIs",
    defaultVisible: true,
    defaultSize: { w: 4, h: 1 }, minSize: { w: 2, h: 1 },
    home: "operations",
    render: (ctx) => <OpsPrimaryKpis ctx={ctx} />,
  },
  {
    id: "ops_alerts",
    title: "Operations Alerts",
    defaultVisible: true,
    defaultSize: { w: 4, h: 1 }, minSize: { w: 4, h: 1 },
    home: "operations",
    conditional: true,
    render: (ctx) => <OpsAlerts ctx={ctx} />,
  },
  {
    id: "ops_pipeline",
    title: "Operations Pipeline",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    home: "operations",
    render: (ctx) => <OpsPipelineWidget ctx={ctx} />,
  },
  {
    id: "spinning_summary",
    title: "Spinning Summary",
    defaultVisible: true,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    home: "operations",
    requiredModule: "spinning",
    conditional: true,
    render: (ctx) => <SpinningSummaryWidget ctx={ctx} />,
  },
  {
    id: "weaving_summary",
    title: "Weaving Summary",
    defaultVisible: true,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    home: "operations",
    requiredModule: "weaving",
    conditional: true,
    render: (ctx) => <WeavingSummaryWidget ctx={ctx} />,
  },
  {
    id: "production_wip",
    title: "Production WIP",
    defaultVisible: true,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    home: "operations",
    requiredModule: "production",
    conditional: true,
    render: (ctx) => <ProductionWipWidget ctx={ctx} />,
  },
  {
    id: "healthcare_census",
    title: "Healthcare Census",
    defaultVisible: true,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    home: "operations",
    requiredModule: "healthcare",
    conditional: true,
    render: (ctx) => <HealthcareCensusWidget ctx={ctx} />,
  },
  {
    id: "telecom_tracker",
    title: "Telecom Tracker",
    defaultVisible: true,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    home: "operations",
    requiredModule: "telecom",
    conditional: true,
    render: (ctx) => <TelecomTrackerWidget ctx={ctx} />,
  },
  {
    id: "purchases_pipeline",
    title: "Purchases Pipeline",
    defaultVisible: true,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    home: "operations",
    requiredModule: "purchase_store",
    conditional: true,
    render: (ctx) => <PurchasesPipelineWidget ctx={ctx} />,
  },
  {
    id: "textile_processing_summary",
    title: "Textile Processing",
    defaultVisible: true,
    defaultSize: { w: 2, h: 2 }, minSize: { w: 2, h: 2 },
    home: "operations",
    requiredModule: "textile_processing",
    conditional: true,
    render: (ctx) => <TextileProcessingWidget ctx={ctx} />,
  },
  // Process-visibility charts / tables (adapt to whichever purpose modules are installed)
  {
    id: "ops_process_chart",
    title: "Process Visibility",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    home: "operations",
    render: (ctx) => <OpsProcessChart ctx={ctx} />,
  },
  {
    id: "ops_trend_chart",
    title: "Operations Trend",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    home: "operations",
    render: (ctx) => <OpsTrendChart ctx={ctx} />,
  },
  {
    id: "ops_status_table",
    title: "Status Board",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    home: "operations",
    render: (ctx) => <OpsStatusTable ctx={ctx} />,
  },
  {
    id: "ops_mix_chart",
    title: "Composition Mix",
    defaultVisible: true,
    defaultSize: { w: 2, h: 3 }, minSize: { w: 2, h: 2 },
    home: "operations",
    render: (ctx) => <OpsMixChart ctx={ctx} />,
  },
]
