/** Canonical voucher-type catalog — mirrors backend services/vouchers.py VOUCHER_TYPES */
export const VOUCHER_TYPES: Record<string, string> = {
  JV: "Journal Voucher",
  CP: "Cash Payment",
  CR: "Cash Receipt",
  BP: "Bank Payment",
  BR: "Bank Receipt",
  SL: "Sales Invoice",
  PR: "Purchase Invoice",
  CO: "Contra",
  DN: "Debit Note",
  CN: "Credit Note",
}

/** Tailwind colour classes for each voucher type badge. */
export const VOUCHER_TYPE_COLORS: Record<string, string> = {
  JV: "bg-gray-100 text-gray-700",
  CP: "bg-orange-100 text-orange-700",
  CR: "bg-green-100 text-green-700",
  BP: "bg-orange-100 text-orange-700",
  BR: "bg-green-100 text-green-700",
  SL: "bg-blue-100 text-blue-700",
  PR: "bg-purple-100 text-purple-700",
  CO: "bg-cyan-100 text-cyan-700",
  DN: "bg-amber-100 text-amber-700",
  CN: "bg-amber-100 text-amber-700",
}

export function voucherTypeBadgeClass(type: string): string {
  return VOUCHER_TYPE_COLORS[type] ?? "bg-gray-100 text-gray-600"
}

export type AccountType = "Asset" | "Liability" | "Equity" | "Revenue" | "Expense"

/**
 * Extended account category for per-side filtering.
 * Standard account types plus sub-categories for cash and bank accounts
 * (both are "Asset" type but need to be distinguished for payment vouchers).
 */
export type AccountCategory =
  | AccountType
  | "cash"     // Asset whose name/code suggests cash-in-hand
  | "bank"     // Asset whose name/code suggests a bank account
  | "cashbank" // Either cash or bank (used for Contra vouchers)

/** Per-side account-type filter for each voucher type. */
export interface SideFilter {
  debit: AccountCategory[]
  credit: AccountCategory[]
}

/**
 * Smart account-head filtering rules (Issue #77 Part 1).
 * Voucher types not listed here (JV, SL, PR, DN, CN, CO) have no
 * restriction and show the full COA on both sides.
 */
export const VOUCHER_SIDE_FILTERS: Record<string, SideFilter> = {
  CP: {
    debit:  ["Expense", "Liability", "Asset"],
    credit: ["cash"],
  },
  BP: {
    debit:  ["Expense", "Liability", "Asset"],
    credit: ["bank"],
  },
  CR: {
    debit:  ["cash"],
    credit: ["Revenue", "Asset", "Equity"],
  },
  BR: {
    debit:  ["bank"],
    credit: ["Revenue", "Asset", "Equity"],
  },
  CV: {
    debit:  ["cashbank"],
    credit: ["cashbank"],
  },
}

/** Minimal account shape needed for filtering — matches the API response. */
export interface FilterableAccount {
  id: number
  code: string
  name: string
  type?: string
}

function isCash(a: FilterableAccount): boolean {
  return (
    a.type === "Asset" &&
    (a.name.toLowerCase().includes("cash") || a.code.startsWith("100"))
  )
}

function isBank(a: FilterableAccount): boolean {
  return (
    a.type === "Asset" &&
    (a.name.toLowerCase().includes("bank") || a.code.startsWith("101"))
  )
}

function matchesCategory(a: FilterableAccount, cat: AccountCategory): boolean {
  switch (cat) {
    case "cash":     return isCash(a)
    case "bank":     return isBank(a)
    case "cashbank": return isCash(a) || isBank(a)
    default:         return a.type === cat
  }
}

const EMPTY_HINTS: Record<string, string> = {
  cash:     "No Cash in Hand account found — add one in Chart of Accounts",
  bank:     "No Bank account found — add one in Chart of Accounts",
  cashbank: "No Cash or Bank account found — add one in Chart of Accounts",
}

/**
 * Filter accounts for one side (debit/credit) of a payment/receipt voucher.
 *
 * Pass `excludeIds` to remove accounts already used on the opposite side
 * (Contra vouchers must not debit and credit the same account).
 *
 * Returns the filtered list and an optional `emptyReason` string to display
 * when no matching accounts exist in the tenant's COA.
 */
export function filterAccountsForSide<T extends FilterableAccount>(
  accounts: T[],
  voucherType: string,
  side: "debit" | "credit",
  excludeIds?: ReadonlySet<number>,
): { accounts: T[]; emptyReason?: string } {
  const filter = VOUCHER_SIDE_FILTERS[voucherType]
  if (!filter) return { accounts }   // JV + non-payment types → no restriction

  const categories = filter[side]
  const filtered = accounts.filter(
    a =>
      (!excludeIds || !excludeIds.has(a.id)) &&
      categories.some(cat => matchesCategory(a, cat)),
  )

  if (filtered.length === 0) {
    const primary = categories[0]
    const reason =
      EMPTY_HINTS[primary] ??
      `No ${categories.join(" / ")} account found — add one in Chart of Accounts`
    return { accounts: [], emptyReason: reason }
  }

  return { accounts: filtered }
}

/** @deprecated Use VOUCHER_SIDE_FILTERS + filterAccountsForSide instead. */
export const VOUCHER_ACCOUNT_HINTS: Record<string, AccountType[]> = {
  CP: ["Asset"],
  CR: ["Asset"],
  BP: ["Asset"],
  BR: ["Asset"],
  CO: ["Asset"],
  SL: ["Asset", "Revenue"],
  CN: ["Asset", "Revenue"],
  PR: ["Asset", "Expense", "Liability"],
  DN: ["Asset", "Expense", "Liability"],
  JV: [],
}
