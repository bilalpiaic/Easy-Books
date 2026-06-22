import { NAV, type NavItem } from "@/lib/nav"

const SHORTCUT_PREFIX = "shortcut:"

export const isShortcutId = (id: string) => id.startsWith(SHORTCUT_PREFIX)
export const shortcutHref = (id: string) => id.slice(SHORTCUT_PREFIX.length)
export const shortcutId = (href: string) => `${SHORTCUT_PREFIX}${href}`

/** Same visibility rule the sidebar uses (lib/nav consumers). */
function available(item: NavItem, installedModules: Set<string>, role: string): boolean {
  const isAdmin = role === "admin" || role === "owner"
  return (!item.forModule || installedModules.has(item.forModule)) && (!item.adminOnly || isAdmin)
}

/** NAV items the user may add as shortcut tiles (excludes the Dashboard itself),
 *  filtered to installed modules + role. */
export function shortcutCatalog(installedModules: Set<string>, role: string): NavItem[] {
  return NAV.filter(i => i.href !== "/dashboard" && available(i, installedModules, role))
}

/** Resolve a shortcut id to its NAV item, or null if it's no longer available
 *  to this user (e.g. a module was uninstalled and the route is gone). */
export function resolveShortcut(id: string, installedModules: Set<string>, role: string): NavItem | null {
  if (!isShortcutId(id)) return null
  const item = NAV.find(i => i.href === shortcutHref(id))
  return item && available(item, installedModules, role) ? item : null
}
