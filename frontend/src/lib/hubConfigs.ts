// frontend/src/lib/hubConfigs.ts
import {
  FileSignature, PlusCircle, ArrowDownLeft, Users, Clock,
  Receipt, Percent, Tags, TrendingUp, FileText, ArrowUpRight,
  Truck, Undo2, CalendarCheck, ShoppingCart, Package,
  BookOpen, PieChart, Landmark, Upload, CheckCheck, Wallet,
} from "lucide-react"
import { apiFetch } from "@/lib/api"
import type { HubConfig, HubRawData } from "@/components/hub/HubPage"

const sum = (...vals: number[]) => vals.reduce((a, b) => a + (b || 0), 0)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const meanDays = (items: any[]): number => {
  const overdue = items.filter(i => (i.days_past ?? 0) > 0).map(i => i.days_past as number)
  return overdue.length ? Math.round(overdue.reduce((a, b) => a + b, 0) / overdue.length) : 0
}

export const RECEIVABLE_CONFIG: HubConfig = {
  section: "Receivable",
  title: "Accounts Receivable",
  icon: FileSignature,
  fetch: () =>
    Promise.all([
      apiFetch<Record<string, number> & { items?: { days_past: number }[] }>("/api/invoices/aging"),
      apiFetch<{ total: number }>("/api/invoices?limit=1"),
    ]) as Promise<HubRawData>,
  kpis: [
    {
      label: "Total AR",
      format: "currency",
      value: ([aging]) => sum(aging.current, aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90),
    },
    {
      label: "Overdue",
      format: "currency",
      value: ([aging]) => sum(aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90),
      tone: ([aging]) =>
        sum(aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90) > 0 ? "danger" : "normal",
    },
    {
      label: "Open Invoices",
      value: ([, inv]) => inv.total ?? 0,
    },
    {
      label: "Avg Days Overdue",
      value: ([aging]) => {
        const d = meanDays(aging.items ?? [])
        return d > 0 ? `${d}d` : "0d"
      },
      tone: ([aging]) => {
        const d = meanDays(aging.items ?? [])
        return d > 30 ? "danger" : d > 0 ? "warning" : "normal"
      },
    },
  ],
  band: "aging",
  bandData: ([aging]) => ({
    current: aging.current    || 0,
    d1_30:   aging["1_30"]   || 0,
    d31_60:  aging["31_60"]  || 0,
    d60plus: sum(aging["61_90"] || 0, aging.over_90 || 0),
  }),
  actions: [
    { label: "New Invoice",     href: "/invoices/new",         icon: PlusCircle,   primary: true },
    { label: "Payments",        href: "/payments-received",    icon: ArrowDownLeft              },
    { label: "Customers",       href: "/customers",            icon: Users                      },
    { label: "AR Aging",        href: "/aging/receivable",     icon: Clock                      },
    { label: "Credit Notes",    href: "/credit-notes",         icon: Receipt                    },
    { label: "Commissions",     href: "/commissions",          icon: Percent                    },
    { label: "Promo Discounts", href: "/promo-discounts",      icon: Tags                       },
    { label: "Performance",     href: "/customer-performance", icon: TrendingUp                 },
  ],
}

export const PAYABLE_CONFIG: HubConfig = {
  section: "Payable",
  title: "Accounts Payable",
  icon: FileText,
  fetch: () =>
    Promise.all([
      apiFetch<Record<string, number> & { items?: { days_past: number }[] }>("/api/bills/aging"),
      apiFetch<{ total: number }>("/api/bills?limit=1"),
    ]) as Promise<HubRawData>,
  kpis: [
    {
      label: "Total AP",
      format: "currency",
      value: ([aging]) => sum(aging.current, aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90),
    },
    {
      label: "Overdue",
      format: "currency",
      value: ([aging]) => sum(aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90),
      tone: ([aging]) =>
        sum(aging["1_30"], aging["31_60"], aging["61_90"], aging.over_90) > 0 ? "danger" : "normal",
    },
    {
      label: "Open Bills",
      value: ([, bills]) => bills.total ?? 0,
    },
    {
      label: "Avg Days Overdue",
      value: ([aging]) => {
        const d = meanDays(aging.items ?? [])
        return d > 0 ? `${d}d` : "0d"
      },
      tone: ([aging]) => {
        const d = meanDays(aging.items ?? [])
        return d > 30 ? "danger" : d > 0 ? "warning" : "normal"
      },
    },
  ],
  band: "aging",
  bandData: ([aging]) => ({
    current: aging.current    || 0,
    d1_30:   aging["1_30"]   || 0,
    d31_60:  aging["31_60"]  || 0,
    d60plus: sum(aging["61_90"] || 0, aging.over_90 || 0),
  }),
  actions: [
    { label: "New Bill",        href: "/bills/new",                     icon: PlusCircle,   primary: true },
    { label: "Bill Payments",   href: "/bill-payments",                 icon: ArrowUpRight               },
    { label: "Vendors",         href: "/vendors",                       icon: Truck                      },
    { label: "AP Aging",        href: "/aging/payable",                 icon: Clock                      },
    { label: "Debit Notes",     href: "/debit-notes",                   icon: Undo2                      },
    { label: "Bills",           href: "/bills",                         icon: FileText                   },
    { label: "Payment Terms",   href: "/payment-terms",                 icon: CalendarCheck              },
    { label: "Purchase Orders", href: "/manufacturing/purchase-orders", icon: ShoppingCart               },
  ],
}

export const INVENTORY_CONFIG: HubConfig = {
  section: "Inventory",
  title: "Inventory",
  icon: Package,
  fetch: () =>
    apiFetch<{ items: Record<string, unknown>[] }>("/api/reports/inventory-performance").then(r => [r]),
  kpis: [
    {
      label: "Products",
      value: ([data]) => (data.items ?? []).length,
    },
    {
      label: "Stock Value",
      format: "currency",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([data]) => (data.items ?? []).reduce((a: number, i: any) => a + (i.stock_value || 0), 0),
    },
    {
      label: "Low Stock",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([data]) => (data.items ?? []).filter((i: any) => i.low_stock && i.on_hand > 0).length,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      tone: ([data]) =>
        (data.items ?? []).filter((i: any) => i.low_stock && i.on_hand > 0).length > 0
          ? "warning"
          : "normal",
    },
    {
      label: "Out of Stock",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      value: ([data]) => (data.items ?? []).filter((i: any) => i.on_hand <= 0).length,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      tone: ([data]) =>
        (data.items ?? []).filter((i: any) => i.on_hand <= 0).length > 0 ? "danger" : "normal",
    },
  ],
  band: "low-stock",
  bandData: ([data]) => ({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    items: [...(data.items ?? [])]
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .filter((i: any) => i.low_stock || i.on_hand <= 0)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .sort((a: any, b: any) => {
        if (a.on_hand <= 0 && b.on_hand > 0) return -1
        if (b.on_hand <= 0 && a.on_hand > 0) return 1
        const ra = a.on_hand / (a.reorder_level || 1)
        const rb = b.on_hand / (b.reorder_level || 1)
        return ra - rb
      })
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .map((i: any) => ({ name: i.name, on_hand: i.on_hand, reorder_level: i.reorder_level ?? 0 })),
  }),
  actions: [
    { label: "New Product",      href: "/products/new",          icon: PlusCircle, primary: true },
    { label: "Product Ledger",   href: "/products/ledger",       icon: BookOpen                 },
    { label: "Categories",       href: "/products/categories",   icon: Tags                     },
    { label: "Inventory Report", href: "/inventory/performance", icon: PieChart                 },
  ],
}

export const BANKING_CONFIG: HubConfig = {
  section: "Banking",
  title: "Banking",
  icon: Landmark,
  fetch: () =>
    Promise.all([
      apiFetch<{ id: number; name: string; balance?: number }[]>("/api/bank-accounts"),
      apiFetch<{ status: string }[]>("/api/bank-imports"),
    ]) as Promise<HubRawData>,
  kpis: [
    {
      label: "Total Funds",
      format: "currency",
      value: ([accounts]) =>
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (accounts as any[]).reduce((a: number, acc: any) => a + (acc.balance || 0), 0),
    },
    {
      label: "Accounts",
      value: ([accounts]) => (accounts as unknown[]).length,
    },
    {
      label: "Pending Imports",
      value: ([, imports]) =>
        (imports as { status: string }[]).filter(i => i.status === "parsed").length,
      tone: ([, imports]) =>
        (imports as { status: string }[]).filter(i => i.status === "parsed").length > 0
          ? "warning"
          : "normal",
    },
    {
      label: "Unreconciled",
      value: ([, imports]) =>
        (imports as { status: string }[]).filter(i => i.status === "matched").length,
      tone: ([, imports]) =>
        (imports as { status: string }[]).filter(i => i.status === "matched").length > 0
          ? "warning"
          : "normal",
    },
  ],
  band: "account-list",
  bandData: ([accounts]) => ({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    accounts: (accounts as any[]).map((a: any) => ({
      id: a.id,
      name: a.name,
      balance: a.balance || 0,
    })),
  }),
  actions: [
    { label: "Import CSV",      href: "/bank-imports",    icon: Upload,      primary: true },
    { label: "Bank Accounts",   href: "/bank-accounts",   icon: Landmark                  },
    { label: "Reconciliations", href: "/reconciliations", icon: CheckCheck                },
    { label: "Cash Book",       href: "/cash-book",       icon: Wallet                    },
    { label: "Bank Book",       href: "/bank-book",       icon: BookOpen                  },
    { label: "Exchange Rates",  href: "/exchange-rates",  icon: TrendingUp                },
  ],
}
