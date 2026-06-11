# #52 §6 Standard Navigation Controls — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a consistent breadcrumb/back bar on every sub-page and an always-visible Home button on every page, driven by the existing sidebar route map.

**Architecture:** Extract the sidebar `NAV` array into a shared `lib/nav.ts` with a pure `resolveBreadcrumb()`. A `BreadcrumbProvider`/`useBreadcrumb()` context carries an optional leaf label. A self-deciding `<NavBar/>` (mounted once in the dashboard layout) renders `← ⌂ Dashboard › List › Leaf` only on sub-pages. A Home button is added to the global `Header`. Six hand-rolled detail-page breadcrumbs are replaced by the hook.

**Tech Stack:** Next.js 16 App Router (client components), React 19, TypeScript, Tailwind v4, lucide-react.

**Spec:** `docs/superpowers/specs/2026-06-11-issue52-6-nav-controls-design.md`

**Verification note:** The frontend has **no unit-test runner** (`npm test` is absent). The per-task gate is `cd frontend && npm run build` (compiles, all routes green) + `npm run lint` (changed files clean). `resolveBreadcrumb` is a pure function; each task documents expected input→output pairs to reason through. Run all commands from `frontend/`.

---

## File structure

| File | Responsibility | Task |
|------|----------------|------|
| `src/lib/nav.ts` | **New.** Single source of truth: `NavItem`, `NAV`, `ALL_SECTIONS`, pure `resolveBreadcrumb()` | 1 |
| `src/components/Sidebar.tsx` | **Modify.** Import `NavItem`/`NAV`/`ALL_SECTIONS` from `lib/nav` instead of declaring them | 1 |
| `src/context/BreadcrumbContext.tsx` | **New.** `BreadcrumbProvider` + `useBreadcrumb()` leaf context | 2 |
| `src/components/NavBar.tsx` | **New.** Self-deciding breadcrumb/back bar | 3 |
| `src/app/(dashboard)/layout.tsx` | **Modify.** Mount provider + `<NavBar/>` | 4 |
| `src/components/Header.tsx` | **Modify.** Add always-on Home button | 5 |
| 6 detail pages + #40 new/edit pages | **Modify.** Replace manual breadcrumbs / add leaf | 6 |

---

## Task 1: Extract NAV into `lib/nav.ts` + `resolveBreadcrumb`

**Files:**
- Create: `src/lib/nav.ts`
- Modify: `src/components/Sidebar.tsx` (lines 20–28 `NavItem`, 30–86 `NAV`, 88 `ALL_SECTIONS`)

- [ ] **Step 1: Create `src/lib/nav.ts`** — move the `NavItem` type, `NAV` array, and `ALL_SECTIONS` **verbatim** out of `Sidebar.tsx` (currently `Sidebar.tsx:20-28`, `:30-86`, `:88`), keep their lucide icon imports, and add the resolver.

```ts
import {
  LayoutDashboard, PlusCircle, ClipboardList, BookOpen, TableProperties,
  Scale, FileText, PieChart, TrendingUp, FileSignature, Users,
  ArrowDownLeft, Receipt, Truck, ArrowUpRight, Landmark, CheckCheck,
  Percent, Settings, Package, GitBranch, HelpCircle,
  Factory, ListChecks, Tags, PackagePlus, Warehouse,
  Radio, Wallet, Network, Smartphone, Target, Banknote, ReceiptText,
  ScrollText, Tablet, UserCircle, UsersRound, RefreshCw,
  Building2, CalendarCheck, Clock, Table2,
} from "lucide-react"

export type NavItem = {
  label: string
  href: string
  icon: React.ElementType
  section: string
  forModel?: "manufacturing" | "telecom_franchise"
  /** Only shown to admin+ (admin or owner). */
  adminOnly?: boolean
}

export const NAV: NavItem[] = [
  // ⬇️ PASTE the existing 56-entry array verbatim from Sidebar.tsx:31-85
]

export const ALL_SECTIONS = ["Overview","Ledger","Receivable","Payable","Inventory","Manufacturing","Telecom","Banking","Reports","System"]

/**
 * Resolve a pathname to its breadcrumb context using the sidebar map.
 * - `list` = the NAV item whose href is the LONGEST prefix of pathname.
 * - `isSubPage` is true only when pathname is DEEPER than that href
 *   (i.e. a detail / new / edit route), so top-level destinations get no bar.
 */
export function resolveBreadcrumb(pathname: string): {
  list?: { label: string; href: string }
  isSubPage: boolean
} {
  let best: NavItem | undefined
  for (const item of NAV) {
    if (pathname === item.href || pathname.startsWith(item.href + "/")) {
      if (!best || item.href.length > best.href.length) best = item
    }
  }
  if (!best) return { isSubPage: false }
  const isSubPage = pathname !== best.href
  return { list: { label: best.label, href: best.href }, isSubPage }
}
```

- [ ] **Step 2: Rewire `Sidebar.tsx`** — delete the local `NavItem` type (`:20-28`), the `NAV` array (`:30-86`), and the `ALL_SECTIONS` const (`:88`); import them instead. Add to the top of `Sidebar.tsx`:

```ts
import { NAV, ALL_SECTIONS, type NavItem } from "@/lib/nav"
```

Then prune any now-unused icon imports from `Sidebar.tsx`'s lucide import block (icons only referenced by `NAV` move to `lib/nav.ts`; icons still used in the Sidebar JSX — `X`, `ChevronRight`, `Pin`, `PinOff`, `LogOut`, `DollarSign`/`Tag`/`ShoppingCart`/`Undo2` if unused — stay only if referenced). Keep `cn`, auth, and `apiFetch` imports.

- [ ] **Step 3: Verify build + lint**

Run: `npm run build && npm run lint`
Expected: build green; **no** "unused import" or "cannot find name NAV/NavItem/ALL_SECTIONS" errors. Lint clean on `Sidebar.tsx` and `lib/nav.ts`.

Reason through `resolveBreadcrumb`:
- `"/invoices"` → `{ list:{label:"Invoices",href:"/invoices"}, isSubPage:false }`
- `"/invoices/123"` → `{ list:{label:"Invoices",href:"/invoices"}, isSubPage:true }`
- `"/products/categories"` → `{ list:{label:"Product Categories",href:"/products/categories"}, isSubPage:false }` (longest prefix beats `/products`)
- `"/products/categories/5"` → same list, `isSubPage:true`
- `"/dashboard"` → `{ list:{label:"Dashboard",href:"/dashboard"}, isSubPage:false }`
- `"/unknown-orphan"` → `{ isSubPage:false }`

- [ ] **Step 4: Commit**

```bash
git add src/lib/nav.ts src/components/Sidebar.tsx
git commit -m "refactor(nav): extract NAV + resolveBreadcrumb into lib/nav.ts (#52 §6)"
```

---

## Task 2: Breadcrumb context (`useBreadcrumb`)

**Files:**
- Create: `src/context/BreadcrumbContext.tsx`

- [ ] **Step 1: Create the context**

```tsx
'use client'

import { createContext, useContext, useEffect, useState } from 'react'

interface BreadcrumbCtx {
  leaf: string | null
  setLeaf: (v: string | null) => void
}

const Ctx = createContext<BreadcrumbCtx>({ leaf: null, setLeaf: () => {} })

export function BreadcrumbProvider({ children }: { children: React.ReactNode }) {
  const [leaf, setLeaf] = useState<string | null>(null)
  return <Ctx.Provider value={{ leaf, setLeaf }}>{children}</Ctx.Provider>
}

/**
 * Pages call useBreadcrumb('Some Label') to set the trailing breadcrumb
 * segment. Pass nothing to read the current leaf. The leaf is cleared on
 * unmount so it never bleeds into the next page.
 *
 * Call it UNCONDITIONALLY (React hook rules). For data that loads async,
 * pass a value that updates: useBreadcrumb(entity ? 'Edit ' + entity.number : 'Edit').
 */
export function useBreadcrumb(leaf?: string): string | null {
  const ctx = useContext(Ctx)
  useEffect(() => {
    if (leaf === undefined) return
    ctx.setLeaf(leaf)
    return () => ctx.setLeaf(null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leaf])
  return ctx.leaf
}
```

- [ ] **Step 2: Verify build + lint**

Run: `npm run build && npm run lint`
Expected: build green; lint clean on `BreadcrumbContext.tsx`.

- [ ] **Step 3: Commit**

```bash
git add src/context/BreadcrumbContext.tsx
git commit -m "feat(nav): BreadcrumbProvider + useBreadcrumb leaf context (#52 §6)"
```

---

## Task 3: `<NavBar/>` component

**Files:**
- Create: `src/components/NavBar.tsx`

- [ ] **Step 1: Create the component**

```tsx
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
    <nav className="flex items-center gap-2 text-sm text-black/60 mb-4 print:hidden" aria-label="Breadcrumb">
      <button
        onClick={() => router.back()}
        aria-label="Back"
        title="Back"
        className="inline-flex items-center justify-center w-7 h-7 rounded-lg border border-[#ede9e2] text-[#1a1814]/55 hover:text-[#b8943f] hover:bg-[#faf6ec] transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
      </button>
      <Link href="/dashboard" aria-label="Dashboard home" title="Dashboard" className="inline-flex items-center hover:text-[#b8943f] transition-colors">
        <Home className="w-4 h-4" />
      </Link>
      {crumbs.map((c, i) => (
        <Fragment key={i}>
          <ChevronRight className="w-3 h-3 shrink-0 text-black/30" />
          {c.href ? (
            <Link href={c.href} className="hover:text-[#b8943f] transition-colors truncate max-w-[40vw]">{c.label}</Link>
          ) : (
            <span className="text-black/60 truncate max-w-[40vw]">{c.label}</span>
          )}
        </Fragment>
      ))}
    </nav>
  )
}
```

Note: the leading `Home` icon link and the first `Dashboard` crumb both point to `/dashboard` — the icon is the persistent affordance, the word is the trail start (matches the approved mockup `[←] ⌂ Dashboard › Invoices › INV-001`).

- [ ] **Step 2: Verify build + lint**

Run: `npm run build && npm run lint`
Expected: build green; lint clean on `NavBar.tsx`.

- [ ] **Step 3: Commit**

```bash
git add src/components/NavBar.tsx
git commit -m "feat(nav): self-deciding NavBar breadcrumb/back bar (#52 §6)"
```

---

## Task 4: Mount provider + NavBar in the dashboard layout

**Files:**
- Modify: `src/app/(dashboard)/layout.tsx` (imports near top; render tree `:108-129`)

- [ ] **Step 1: Add imports** to `layout.tsx`:

```tsx
import NavBar from "@/components/NavBar"
import { BreadcrumbProvider } from "@/context/BreadcrumbContext"
```

- [ ] **Step 2: Wrap the tree and mount NavBar.** Replace the `return ( <SettingsProvider> … </SettingsProvider> )` body (`layout.tsx:108-129`) with:

```tsx
  return (
    <SettingsProvider>
      <BreadcrumbProvider>
        <div className="flex h-screen overflow-hidden bg-[#f6f3ee]">
          <Sidebar
            open={open}
            onClose={onClose}
            pinned={pinned}
            onTogglePinned={onTogglePinned}
          />
          <div className="flex-1 flex flex-col min-w-0">
            <Header onOpenMenu={onOpen} />
            <main className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 pb-20 md:pb-6 w-full">
              <NavBar />
              {children}
            </main>
          </div>
          <BottomNav onMore={onOpen} />
        </div>
      </BreadcrumbProvider>
    </SettingsProvider>
  )
```

- [ ] **Step 3: Verify build + lint, then manual spot-check**

Run: `npm run build && npm run lint`
Expected: build green; lint clean.
Manual (if dev server handy, optional): `/invoices/123` shows the bar `← ⌂ Dashboard › Invoices`; `/invoices` shows no bar; `/dashboard` shows no bar. (Leaf labels arrive in Task 6.)

- [ ] **Step 4: Commit**

```bash
git add "src/app/(dashboard)/layout.tsx"
git commit -m "feat(nav): mount BreadcrumbProvider + NavBar in dashboard layout (#52 §6)"
```

---

## Task 5: Always-on Home button in the Header

**Files:**
- Modify: `src/components/Header.tsx` (imports `:4`; JSX after the menu button `:27-33`)

- [ ] **Step 1: Add `Home` + `Link` imports.** Change `Header.tsx:4` from `import { Menu } from "lucide-react"` to:

```tsx
import { Menu, Home } from "lucide-react"
import Link from "next/link"
```

- [ ] **Step 2: Add the Home button** immediately after the menu (hamburger) `</button>` (after `Header.tsx:33`):

```tsx
      <Link
        href="/dashboard"
        aria-label="Home"
        title="Dashboard"
        className="w-9 h-9 inline-flex items-center justify-center rounded-lg text-white/70 hover:text-[#ffd966] hover:bg-white/5 transition"
      >
        <Home className="w-5 h-5" />
      </Link>
```

- [ ] **Step 3: Verify build + lint, manual spot-check**

Run: `npm run build && npm run lint`
Expected: build green; lint clean.
Manual (optional): the Home (⌂) button appears in the dark top bar on **every** page — `/dashboard`, `/invoices` (list), `/invoices/123` (sub-page).

- [ ] **Step 4: Commit**

```bash
git add src/components/Header.tsx
git commit -m "feat(nav): always-on Home button in Header (#52 §6)"
```

---

## Task 6: Page wiring — replace manual breadcrumbs, add leaf labels

Two kinds of edits. Do them file-by-file; commit once at the end of the task.

### 6a — Replace hand-rolled breadcrumbs in the 6 detail pages

For **each** of: `invoices/[id]`, `bills/[id]`, `bill-payments/[id]`, `credit-notes/[id]`, `journal/[id]`, `assets/[id]` (all under `src/app/(dashboard)/.../[id]/page.tsx`):

- [ ] **Step 1: Add the hook import** (top of the file, with the other imports):

```tsx
import { useBreadcrumb } from '@/context/BreadcrumbContext'
```

- [ ] **Step 2: Locate the manual breadcrumb.** Grep the file for its breadcrumb `<nav>` — it is the block containing `ChevronRight` and a `<Link href="/{list}">` followed by `<span className="text-black/60">{number}</span>`. Example in `bills/[id]/page.tsx`:

```tsx
      <nav className="...flex items-center gap-2 text-sm...">
        <Link href="/bills" className="hover:text-black/70 transition-colors">Bills</Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-black/60">{bill.number}</span>
      </nav>
```

Delete that whole `<nav>…</nav>` block (the global NavBar now renders it).

- [ ] **Step 3: Set the leaf** via the hook, called unconditionally in the component body (after the entity state is declared). Use the entity's display field; guard for the loading state. Examples:
  - `invoices/[id]`: `useBreadcrumb(invoice ? invoice.number : undefined)`
  - `bills/[id]`: `useBreadcrumb(bill ? bill.number : undefined)`
  - `bill-payments/[id]`: `useBreadcrumb(payment ? (payment.reference ?? \`Payment #${payment.id}\`) : undefined)`
  - `credit-notes/[id]`: `useBreadcrumb(note ? note.number : undefined)`
  - `journal/[id]`: `useBreadcrumb(entry ? (entry.jv_number ?? \`JV #${entry.id}\`) : undefined)`
  - `assets/[id]`: `useBreadcrumb(asset ? asset.name : undefined)`

  (Use the actual state-variable name already present in each file. Passing `undefined` while loading leaves the trail at `Dashboard › List` until data arrives.)

- [ ] **Step 4: Prune now-unused imports.** If `ChevronRight` (or the breadcrumb's `Link`) is no longer referenced after deleting the `<nav>`, remove it from that file's imports to keep lint clean.

### 6b — Add leaf labels to the #40 new/edit pages

- [ ] **Step 5: `/new` pages** — add `useBreadcrumb('New …')` in each (`'use client'` already present). Files + leaf:
  - `invoices/new` → `useBreadcrumb('New Invoice')`
  - `bills/new` → `useBreadcrumb('New Bill')`
  - `payments-received/new` → `useBreadcrumb('Record Payment')`
  - `bill-payments/new` → `useBreadcrumb('Pay Bill')`
  - `products/new` → `useBreadcrumb('Add Product')`
  - `customers/new` → `useBreadcrumb('Add Customer')`
  - `vendors/new` → `useBreadcrumb('Add Vendor')`

  Add `import { useBreadcrumb } from '@/context/BreadcrumbContext'` and call it once in the page component body.

- [ ] **Step 6: `/[id]/edit` pages** — add the hook with a value that sharpens as the entity loads. Files + leaf:
  - `invoices/[id]/edit` → `useBreadcrumb(invoice ? \`Edit ${invoice.number}\` : 'Edit')`
  - `bills/[id]/edit` → `useBreadcrumb(bill ? \`Edit ${bill.number}\` : 'Edit')`
  - `products/[id]/edit` → `useBreadcrumb(product ? \`Edit ${product.name}\` : 'Edit')`
  - `customers/[id]/edit` → `useBreadcrumb(customer ? \`Edit ${customer.name}\` : 'Edit')`
  - `vendors/[id]/edit` → `useBreadcrumb(vendor ? \`Edit ${vendor.name}\` : 'Edit')`

  (`/[id]/edit` resolves `list` to e.g. `/invoices` via longest-prefix, so the trail reads `Dashboard › Invoices › Edit INV-001`.)

- [ ] **Step 7: Verify build + lint**

Run: `npm run build && npm run lint`
Expected: build green; **0 new lint errors** in the touched files (pre-existing warnings inherited from earlier work are acceptable; do not introduce new ones). Confirm no `ChevronRight`/`Link` "unused" warnings remain in the 6 detail pages.

- [ ] **Step 8: Commit**

```bash
git add "src/app/(dashboard)"
git commit -m "feat(nav): replace manual breadcrumbs with useBreadcrumb; add leaf labels (#52 §6)"
```

---

## Self-review (completed at write time)

- **Spec coverage:** Unit 1 (`lib/nav.ts`/`resolveBreadcrumb`) → Task 1; Unit 2 (`BreadcrumbProvider`/`useBreadcrumb`) → Task 2; Unit 3 (`NavBar`) → Task 3 + mount Task 4; Unit 4 (Header Home, locked decision 5) → Task 5; Unit 5 (page cleanup) → Task 6. Locked decisions 1–4 (sub-pages-only, both back+crumbs, leaf hook, `Dashboard › List › Leaf`) realized in Tasks 3/4/6. Edge cases (orphan, nested known route, empty-history back, stale leaf via unmount-clear) covered in `resolveBreadcrumb` (Task 1) + the hook (Task 2).
- **Type consistency:** `resolveBreadcrumb` returns `{ list?: {label,href}, isSubPage }` — consumed identically in `NavBar` (Task 3). `useBreadcrumb(leaf?)` signature consistent across Tasks 2/6. `NavItem`/`NAV`/`ALL_SECTIONS` exported in Task 1, imported in Sidebar (Task 1).
- **No placeholders:** all new files given in full; the one verbatim move (the 56-entry `NAV` array) is an explicit cut-paste from cited `Sidebar.tsx` lines, not a re-description.
