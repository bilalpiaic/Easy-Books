'use client'

import { Fragment } from 'react'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { ArrowLeft, Home, ChevronRight } from 'lucide-react'
import { resolveBreadcrumb } from '@/lib/nav'
import { useBreadcrumb } from '@/context/BreadcrumbContext'

export default function NavBar() {
  const router = useRouter()
  const pathname = usePathname()
  const leaf = useBreadcrumb()
  const { list, isSubPage } = resolveBreadcrumb(pathname)

  // Sub-pages only: top-level destinations and orphans render nothing.
  if (!isSubPage) return null

  // Build the trail: Dashboard › List › Leaf (each but the leaf is a link).
  const crumbs: { label: string; href?: string }[] = [
    { label: 'Dashboard', href: '/dashboard' },
  ]
  if (list && list.href !== '/dashboard') crumbs.push({ label: list.label, href: list.href })
  if (leaf) crumbs.push({ label: leaf })

  return (
    <nav
      className="flex items-center gap-1.5 sm:gap-2 text-sm text-[var(--text-muted)] mb-3 sm:mb-4 min-w-0 overflow-hidden print:hidden"
      aria-label="Breadcrumb"
    >
      <button
        onClick={() => router.back()}
        aria-label="Back"
        title="Back"
        className="inline-flex items-center justify-center w-7 h-7 shrink-0 rounded-lg border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--primary)] hover:bg-[var(--primary-light)] transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
      </button>
      <Link href="/dashboard" aria-label="Dashboard home" title="Dashboard" className="inline-flex items-center shrink-0 hover:text-[var(--primary)] transition-colors">
        <Home className="w-4 h-4" />
      </Link>
      {crumbs.map((c, i) => {
        const isLast = i === crumbs.length - 1
        // On SM, hide middle crumbs when the trail is long (keep Dashboard via Home + leaf)
        const hideOnSm = crumbs.length > 2 && i > 0 && !isLast
        return (
          <Fragment key={i}>
            <ChevronRight className={`w-3 h-3 shrink-0 text-[var(--border)] ${hideOnSm ? "hidden sm:inline" : ""}`} />
            {c.href ? (
              <Link
                href={c.href}
                className={`hover:text-[var(--primary)] transition-colors truncate min-w-0 max-w-[28vw] sm:max-w-[40vw] ${hideOnSm ? "hidden sm:inline" : ""}`}
              >
                {c.label}
              </Link>
            ) : (
              <span className="text-[var(--text-muted)] truncate min-w-0 max-w-[40vw] sm:max-w-[50vw]">{c.label}</span>
            )}
          </Fragment>
        )
      })}
    </nav>
  )
}
