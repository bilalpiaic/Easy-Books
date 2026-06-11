# Design — #52 §6 Standard Navigation Controls

**Date:** 2026-06-11
**Issue:** #52 §6 (COA/Dashboard/UX bundle — navigation controls slice)
**Effort:** M

## Goal

Provide consistent navigation controls — a **back** affordance, a **Dashboard home**, the **record's list ("section home")**, and a **breadcrumb trail** — on every sub-page (detail / new / edit), replacing today's hand-rolled, inconsistent per-page breadcrumbs. Designed so future Next/Prev-record, Favorites, and Recently-Visited can hang off the same component.

## Locked decisions

1. **Placement: sub-pages only.** Top-level list pages keep their existing large `h1` header and get **no** bar (avoids a redundant `Dashboard › Invoices` above an `Invoices` title). The bar appears only on pages *deeper* than a sidebar destination.
2. **Back/up: both.** A `←` arrow runs browser history-back (`router.back()`); every breadcrumb segment is also a clickable structural link. The crumbs are the deterministic fallback when history is empty (deep-link).
3. **Leaf label: a `useBreadcrumb()` context hook.** Pages optionally set a precise leaf (`INV-001`, `New`, `Edit INV-001`); with zero wiring a sub-page still shows `Dashboard › List`.
4. **Trail shape: `⌂ Dashboard › {List} › {Leaf}`.** No abstract section-name crumb ("Receivable") — it is not a navigable route; the **list crumb is the section home**.
5. **Home is guaranteed on *every* page/form.** Because the breadcrumb bar is sub-pages-only, the always-visible Home control lives in the global `Header` (the dark top bar mounted on every dashboard route). So top-level lists and the dashboard — which intentionally have no breadcrumb bar — still always expose Home. On sub-pages the breadcrumb additionally starts with its own `⌂ Dashboard` crumb (conventional, in-content); the two are complementary, not contradictory.

## Architecture

### Unit 1 — `lib/nav.ts` (new; extraction from `Sidebar.tsx`)
Move the single source of truth out of the Sidebar so two consumers can share it:
- `export type NavItem` (label, href, icon, section, forModel?, adminOnly?)
- `export const NAV: NavItem[]` (the existing array, verbatim)
- `export const ALL_SECTIONS: string[]` (verbatim)
- `export function resolveBreadcrumb(pathname: string): { list?: { label: string; href: string }; isSubPage: boolean }`

`Sidebar.tsx` imports `NavItem`, `NAV`, `ALL_SECTIONS` from `lib/nav.ts` instead of declaring them. `SECTION_COLORS` (presentational) stays in `Sidebar.tsx`. No behavioral change to the sidebar.

**`resolveBreadcrumb` rules (pure function):**
- Consider every `NAV` item whose `href` is a prefix of `pathname` (`pathname === href` OR `pathname.startsWith(href + "/")`).
- The matched **list** = the longest such `href` (most specific). E.g. `/products/categories/5` matches both `/products` and `/products/categories`; pick `/products/categories`.
- `isSubPage = true` **iff** `pathname !== matchedHref` (the path is deeper than the destination). `pathname` exactly equal to a NAV href → `isSubPage = false` (top-level; no bar).
- If no NAV item is a prefix (orphan route), `isSubPage = false`, `list = undefined` — render nothing (safe default).

### Unit 2 — `BreadcrumbProvider` + `useBreadcrumb()` (new; `context/BreadcrumbContext.tsx`)
- `BreadcrumbProvider` holds `leaf: string | null` state and exposes `setLeaf`.
- `useBreadcrumb(leaf?: string)`: when called with a value, an effect sets it on mount and clears it on unmount (so a stale leaf never bleeds into the next page). When called with no value, returns the current leaf (read access — not needed by pages, but keeps the hook symmetric).
- Mounted in `app/(dashboard)/layout.tsx`, wrapping `<NavBar/>` and `{children}` (inside the existing `<SettingsProvider>`).

### Unit 3 — `<NavBar/>` (new; `components/NavBar.tsx`)
- `'use client'`. Reads `usePathname()` + `useBreadcrumb()` leaf.
- Computes `{ list, isSubPage } = resolveBreadcrumb(pathname)`. If `!isSubPage` → `return null`.
- Renders one slim row in the cream content area, above the page body:
  - `←` button → `router.back()` (icon `ArrowLeft`).
  - `⌂` + "Dashboard" → `Link href="/dashboard"` (icon `Home`).
  - `›` `{list.label}` → `Link href={list.href}` (when `list` present).
  - `›` `{leaf}` → plain text (no link) when a leaf is set.
- Style mirrors the existing ad-hoc breadcrumbs: `text-sm`, muted `text-black/60`, `ChevronRight` separators, gold hover (`hover:text-[#b8943f]`), `print:hidden`.

### Mounting (in `layout.tsx`)
```
<SettingsProvider>
  <BreadcrumbProvider>
    <div className="flex h-screen …">
      <Sidebar … />
      <div className="flex-1 flex flex-col min-w-0">
        <Header … />
        <main …>
          <NavBar />
          {children}
        </main>
      </div>
      <BottomNav … />
    </div>
  </BreadcrumbProvider>
</SettingsProvider>
```
The `NavBar` self-decides visibility, so no page needs to opt in for the baseline trail.

### Unit 4 — Persistent Home button in `Header.tsx`
Add an always-visible `⌂` Home control to the global `Header` (the dark top bar in `layout.tsx`, present on every dashboard page/form). Placed immediately right of the existing menu (hamburger) button: a `Home`-icon button → `Link href="/dashboard"`, styled like the menu button (`text-white/70 hover:text-[#ffd966] hover:bg-white/5`), with `aria-label="Home"` and `title="Dashboard"`. This is the universal Home guarantee (locked decision 5); it is independent of the breadcrumb bar's visibility.

### Unit 5 — Bounded page cleanup
Remove the now-redundant hand-rolled breadcrumb `<nav>…</nav>` and add a `useBreadcrumb(leaf)` call in the **6 detail sub-pages** that currently roll their own:
`invoices/[id]`, `bills/[id]`, `bill-payments/[id]`, `credit-notes/[id]`, `journal/[id]`, `assets/[id]`.

Add a `useBreadcrumb` leaf (no manual breadcrumb existed) to the **#40 sub-pages**:
- `*/new` pages → `useBreadcrumb('New …')` (e.g. `'New Invoice'`, `'Add Customer'`).
- `*/[id]/edit` pages → `useBreadcrumb(...)` called **unconditionally** with a value that updates as the entity loads, e.g. `useBreadcrumb(entity ? 'Edit ' + entity.number : 'Edit')`. The hook's effect re-runs when the leaf string changes, so the crumb sharpens from `Edit` → `Edit INV-001` without violating hook-ordering rules.

**Out of scope (untouched):** top-level pages that happen to have breadcrumbs but are sidebar destinations (`coa`, `ledger`, `workflow`, `reports/builder`) — the NavBar returns `null` there, so their existing markup is harmless and stays. Print routes (`*/print`) — separate layout, not under `(dashboard)`.

## Data flow

`pathname` (Next router) ─┐
                          ├─► `resolveBreadcrumb()` ─► `{ list, isSubPage }`
`leaf` (BreadcrumbContext)┘                                     │
                                                                ▼
                                                  `<NavBar/>` renders trail
Pages push their leaf via `useBreadcrumb(leaf)` → context → NavBar re-renders.

## Error / edge handling
- **Deep-link with empty history:** `router.back()` may do nothing or exit; the breadcrumb links are the deterministic recovery path. Acceptable.
- **Stale leaf:** the hook clears `leaf` on unmount, so navigating from `/invoices/1` to a leaf-less sub-page won't show `1`.
- **Orphan / unmapped routes:** `resolveBreadcrumb` returns `isSubPage:false` → NavBar renders nothing (no crash, no wrong crumb).
- **Nested known routes** (`/products/categories`): longest-prefix match picks the most specific list.

## Testing / verification
- `resolveBreadcrumb` is a **pure function** kept isolated in `lib/nav.ts` — logic verifiable by inspection and, if a runner is later added, unit-testable (cases: exact NAV href → not sub-page; one level deeper → sub-page with that list; nested known route → longest prefix; orphan → none).
- Frontend has **no unit-test runner**; gate is `cd frontend && npm run build` (green, all routes compile) + `npm run lint` (changed files clean).
- Manual spot-checks: `/invoices/123` shows `← ⌂ Dashboard › Invoices › INV-…`; `/invoices` (list) shows no bar; `/invoices/new` shows `… › Invoices › New Invoice`; `/dashboard` shows no bar. **Header Home button is visible on every page** — `/dashboard`, top-level lists, and sub-pages alike.

## Future hooks (not built now — YAGNI)
The `<NavBar/>` row is the anchor for later additions named in §6: Next/Prev-record arrows (need an ordered-id source per list), Favorites (a per-user pinned-routes store), Recently-Visited (a small client-side ring buffer). None are implemented here; the component just leaves room.
