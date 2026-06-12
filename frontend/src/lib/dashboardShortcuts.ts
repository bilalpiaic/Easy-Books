import { NAV, type NavItem } from "@/lib/nav"

const SHORTCUT_PREFIX = "shortcut:"

export const isShortcutId = (id: string) => id.startsWith(SHORTCUT_PREFIX)
export const shortcutHref = (id: string) => id.slice(SHORTCUT_PREFIX.length)
export const shortcutId = (href: string) => `${SHORTCUT_PREFIX}${href}`

/** Same visibility rule the sidebar uses (lib/nav consumers). */
function available(item: NavItem, model: string | undefined, role: string): boolean {
  const isAdmin = role === "admin" || role === "owner"
  return (!item.forModel || item.forModel === model) && (!item.adminOnly || isAdmin)
}

/** NAV items the user may add as shortcut tiles (excludes the Dashboard itself),
 *  filtered to the user's business model + role. */
export function shortcutCatalog(model: string | undefined, role: string): NavItem[] {
  return NAV.filter(i => i.href !== "/dashboard" && available(i, model, role))
}

/** Resolve a shortcut id to its NAV item, or null if it's no longer available
 *  to this user (e.g. their business model changed and the route is gone). */
export function resolveShortcut(id: string, model: string | undefined, role: string): NavItem | null {
  if (!isShortcutId(id)) return null
  const item = NAV.find(i => i.href === shortcutHref(id))
  return item && available(item, model, role) ? item : null
}
