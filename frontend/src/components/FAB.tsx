"use client"

import Link from "next/link"
import { Plus } from "lucide-react"
import { usePathname } from "next/navigation"
import { getActiveSection } from "@/lib/nav"

const FAB_MAP: Record<string, { href: string; label: string }> = {
  sales:      { href: "/invoices/new",  label: "New Invoice"  },
  purchases:  { href: "/bills/new",     label: "New Bill"     },
  accounting: { href: "/journal/new",   label: "New Journal"  },
  inventory:  { href: "/products/new",  label: "New Product"  },
  payroll:    { href: "/employees/new", label: "New Employee" },
  banking:    { href: "/journal/new",   label: "New Entry"    },
}

export default function FAB() {
  const section = getActiveSection(usePathname())
  const action  = FAB_MAP[section]
  if (!action) return null

  return (
    <Link
      href={action.href}
      aria-label={action.label}
      className="md:hidden fixed bottom-20 right-4 z-50 flex items-center justify-center w-14 h-14 rounded-full bg-[var(--primary)] text-white shadow-lg hover:bg-[var(--primary-dark)] transition-colors"
    >
      <Plus className="w-6 h-6" />
    </Link>
  )
}
