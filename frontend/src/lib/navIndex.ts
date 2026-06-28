/**
 * Static search index built from nav.ts at module-load time.
 * Querying this is synchronous (~0 ms) — results appear before the API responds.
 */
import { NAV } from "@/lib/nav"

export interface NavResult {
  id: string
  type: "nav"
  label: string
  sub: string   // section name
  href: string
}

const INDEX: NavResult[] = NAV.map(item => ({
  id:    `nav:${item.href}`,
  type:  "nav" as const,
  label: item.label,
  sub:   item.section,
  href:  item.href,
}))

export function searchNav(q: string): NavResult[] {
  if (!q) return []
  const lower = q.toLowerCase()
  return INDEX.filter(
    item =>
      item.label.toLowerCase().includes(lower) ||
      item.sub.toLowerCase().includes(lower)
  ).slice(0, 8)
}
