/** Canonical voucher-type catalog — mirrors backend services/vouchers.py VOUCHER_TYPES */
export const VOUCHER_TYPES: Record<string, string> = {
  JV: "Journal Voucher",
  CP: "Cash Payment",
  CR: "Cash Receipt",
  BP: "Bank Payment",
  BR: "Bank Receipt",
  SL: "Sales Invoice",
  SR: "Sales Return",
  PR: "Purchase Invoice",
  PV: "Purchase Return",
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
  SR: "bg-pink-100 text-pink-700",
  PR: "bg-purple-100 text-purple-700",
  PV: "bg-pink-100 text-pink-700",
  CO: "bg-cyan-100 text-cyan-700",
  DN: "bg-amber-100 text-amber-700",
  CN: "bg-amber-100 text-amber-700",
}

export function voucherTypeBadgeClass(type: string): string {
  return VOUCHER_TYPE_COLORS[type] ?? "bg-gray-100 text-gray-600"
}
