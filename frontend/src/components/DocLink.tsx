"use client"

import Link from "next/link"

export type DocKind =
  | "jv"
  | "invoice"
  | "bill"
  | "payment_received"
  | "bill_payment"
  | "grn"
  | "production_order"
  | "customer"
  | "vendor"
  | "account"
  | "product"
  | "credit_note"
  | "debit_note"
  | "fixed_asset"

interface DocLinkProps {
  type: DocKind
  id: number | string
  label?: string
  className?: string
  title?: string
  children?: React.ReactNode
}

/** Resolve a (kind, id) → href in one place. New routes / aliases should
 *  be added here, never to the call sites. */
function hrefFor(type: DocKind, id: number | string): string {
  switch (type) {
    case "jv":               return `/journal/${id}`
    case "invoice":          return `/invoices/${id}`
    case "bill":             return `/bills/${id}`
    case "payment_received": return `/payments-received/${id}/print`
    case "bill_payment":     return `/bill-payments/${id}/print`
    case "grn":              return `/manufacturing/grn/${id}/print`
    case "production_order": return `/manufacturing/production-orders/${id}`
    case "customer":         return `/customers/${id}`
    case "vendor":           return `/vendors/${id}`
    case "account":          return `/ledger?account=${encodeURIComponent(String(id))}`
    case "product":          return `/products/${id}/stock-card`
    case "credit_note":      return `/credit-notes/${id}`
    case "debit_note":       return `/debit-notes/${id}`
    case "fixed_asset":      return `/assets/${id}`
  }
}

/**
 * Inline brand-coloured link used throughout reports/lists to make every
 * code / name / ID clickable. Style is intentionally subtle — looks like
 * normal text on screen but underlines on hover.
 */
export default function DocLink({ type, id, label, className = "", title, children }: DocLinkProps) {
  return (
    <Link
      href={hrefFor(type, id)}
      title={title ?? `Open ${type.replace("_", " ")}`}
      className={`text-[var(--text-primary)] hover:text-[var(--primary)] hover:underline underline-offset-2 transition-colors ${className}`}
    >
      {children ?? label ?? id}
    </Link>
  )
}
