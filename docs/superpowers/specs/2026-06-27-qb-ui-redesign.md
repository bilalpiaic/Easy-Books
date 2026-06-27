# Easy-Books — QuickBooks Online 2024 UI Redesign

**Date:** 2026-06-27  
**Status:** Approved — ready for implementation planning  
**Scope:** Full frontend redesign (shell + design system + all pages + mobile)  
**Target style:** Intuit QuickBooks Online 2024  

---

## 1. Summary

Replace the current dark-sidebar / gold-cream UI with a QuickBooks Online 2024 style: dark top navbar, white left sub-nav panel per section, white card content on light-gray page background, and green (#2CA01C) as the primary color. The redesign covers the full application shell, all 70+ pages, and mobile responsive behavior. Delivered in four sequential phases.

---

## 2. Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Target style | QB Online 2024 | Top navbar + sub-panel; most modern SaaS accounting look |
| Scope | Full redesign | Shell + design system + every page + mobile |
| Brand palette | QB green (#2CA01C) | Drop gold/cream; full QB green palette |
| Font | Keep DM Sans | Close enough to QB's Avenir; no font swap needed |
| Left sub-nav | Per-section panel (not collapsible accordion) | Matches QB Online; simpler state management |
| Module-gated items | "More ▾" overflow in top nav | Only show installed modules; prevents nav overflow |
| Mobile nav | Bottom tab bar (5 items) + FAB | QB mobile pattern; replaces current BottomNav |
| Table→mobile | Card list layout below 768px | Tables unreadable on small screens |

---

## 3. Color Token System

Replace all current brand tokens in `frontend/src/app/globals.css`:

```css
:root {
  /* Navigation */
  --nav-bg:          #393A3D;   /* top navbar background */
  --nav-text:        #FFFFFF;
  --nav-hover:       rgba(255,255,255,0.10);
  --nav-active:      rgba(255,255,255,0.18);

  /* Primary (QB green) */
  --primary:         #2CA01C;
  --primary-dark:    #1A7510;   /* hover/pressed */
  --primary-light:   #E8F5E4;   /* active sub-nav bg, success tint */

  /* Page chrome */
  --bg-page:         #F4F6F8;   /* page background */
  --bg-card:         #FFFFFF;   /* cards, sub-nav panel */
  --bg-row-hover:    #F7F9FA;   /* table row hover */

  /* Text */
  --text-primary:    #1C2B36;
  --text-muted:      #6C737A;
  --text-link:       #0077C5;

  /* Borders */
  --border:          #D8DDE3;
  --border-light:    #EEF0F3;

  /* Semantic */
  --success:         #2CA01C;
  --warning:         #F59E0B;
  --danger:          #D32F2F;
  --info:            #0077C5;

  /* Status badge backgrounds */
  --badge-green-bg:  #E8F5E4;
  --badge-yellow-bg: #FEF3C7;
  --badge-red-bg:    #FEE2E2;
  --badge-gray-bg:   #F0F2F5;
  --badge-blue-bg:   #EEF4FF;
  --badge-purple-bg: #F3F0FF;
}
```

---

## 4. Typography Scale

Font family: **DM Sans** (already installed — no change).

| Level | Size | Weight | Use |
|---|---|---|---|
| Page title | 24px / 1.5rem | 700 | `<h1>` on every page |
| Section heading | 18px / 1.125rem | 600 | Card titles, section headers |
| Card title | 15px / 0.9375rem | 600 | Widget headings |
| Body | 13px / 0.8125rem | 400 | Table rows, form fields, paragraphs |
| Meta / muted | 12px / 0.75rem | 400 | Dates, subtitles, secondary labels |
| Table header | 11px / 0.6875rem | 700 | `<th>` — UPPERCASE |
| Badge | 11px / 0.6875rem | 700 | Status badges — UPPERCASE |

---

## 5. Component Library

### Buttons

```
Primary:    bg-[--primary]    text-white    hover:bg-[--primary-dark]   rounded-md px-4 py-2 text-sm font-semibold
Secondary:  bg-white          text-[--text-primary]  border border-[--border]  hover:bg-[--bg-page]  rounded-md px-4 py-2 text-sm
Danger:     bg-[--danger]     text-white    hover:bg-red-800             rounded-md px-4 py-2 text-sm font-semibold
Link:       bg-transparent    text-[--text-link]  underline               text-sm
```

### Cards

```
bg-[--bg-card] border border-[--border] rounded-lg shadow-sm
```

### Form inputs

```
Default:  border border-[--border]   rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-[--primary]/20 focus:border-[--primary]
Error:    border border-[--danger]   rounded-md px-3 py-2 text-sm
Label:    text-xs font-semibold text-[--text-primary] mb-1
```

### Tables

```
Header row:  bg-[--bg-page]  text-[11px] font-bold text-[--text-muted] uppercase tracking-wide
Data row:    bg-white  border-b border-[--border-light]  hover:bg-[--bg-row-hover]
Amount cols: text-right font-semibold
Negative:    text-[--danger]  formatted as (1,234.56) via fmt()
```

### Status badges (unified across all pages)

| Status | Background | Text color |
|---|---|---|
| Paid, Posted, Active, Delivered | `--badge-green-bg` | `--success` |
| Due, Partial, Pending, Draft-sent | `--badge-yellow-bg` | `#D97706` |
| Overdue, Void, Rejected | `--badge-red-bg` | `--danger` |
| Draft, Inactive, Cancelled | `--badge-gray-bg` | `--text-muted` |
| Sent, Info, Processing | `--badge-blue-bg` | `--text-link` |
| Approved, Completed | `--badge-purple-bg` | `#7C3AED` |

---

## 6. Shell Architecture

### Top Navbar (`components/TopNav.tsx`) — replaces `Header.tsx`

- Height: 52px, `background: var(--nav-bg)`
- **Left:** Logo mark (24px green square "EB") + company name
- **Center:** Primary nav items — rendered from `TOP_NAV` config, module-gated
- **Right:** Search box (140px), Settings icon, User avatar
- Active item: `background: var(--nav-active)`, full white text
- Hover: `background: var(--nav-hover)`

### Top Nav Sections & Sub-nav mapping

| Top nav item | Always shown | Sub-nav pages |
|---|---|---|
| Dashboard | ✅ | Dashboard, Profit & Loss, Balance Sheet, Cash Flow |
| Banking | ✅ | Bank Accounts, Bank Book, Reconciliation, Bank Imports, Exchange Rates |
| Sales | ✅ | Customers, Invoices, Receipts, Credit Notes, AR Aging, Statements |
| Purchases | ✅ | Vendors, Bills, Payments Made, Debit Notes, AP Aging |
| Accounting | ✅ | Journal, Chart of Accounts, Trial Balance, GL Ledger, Period Close |
| Reports | ✅ | Standard Reports, Report Builder, Customer Performance, Inventory Performance |
| More ▾ | module-gated | Inventory, Payroll, Healthcare, Manufacturing, Telecom, PRA |
| ⚙ Settings | ✅ (icon only) | Settings, Team, Apps, Profile, Audit Log |

### Left Sub-nav Panel (`components/SubNav.tsx`) — replaces `Sidebar.tsx`

- Width: 200px, `background: var(--bg-card)`, `border-right: 1px solid var(--border)`
- Active item: `background: var(--primary-light)`, `border-left: 3px solid var(--primary)`
- Section labels: 10px uppercase muted, non-clickable
- No collapse/expand; always visible on desktop
- Hidden on mobile (replaced by bottom tab bar)

### Layout wrapper (`app/(dashboard)/layout.tsx`)

```
[TopNav 52px fixed]
[SubNav 200px] | [Content area flex-1, padding 24px, bg-[--bg-page]]
```

---

## 7. Page Templates

### 7a. Dashboard

Widgets (top → bottom):

1. **KPI row** — 4 cards: Revenue MTD, Expenses MTD, Net Profit, Cash Balance. Each card: label, large value, delta vs last month (green ↑ / red ↑).
2. **AR + AP summary row** — 2 cards side by side. Each: Overdue / Due Soon / Paid MTD sub-panels with amounts + count.
3. **Recent Transactions table** — last 20 entries across all transaction types. Columns: Date, Doc#, Description/Party, Amount, Status badge. "See all →" link to journal.

Period selector (This Month / This Quarter / This Year / Custom) in page header controls all widgets.

### 7b. List Page Template (applies to 15+ pages)

Structure (top → bottom):

1. **Page header row** — `<h1>` title + subtitle (count + total outstanding) + action buttons right-aligned (Export, Import, **＋ New [Entity]**)
2. **Filter bar** — Status pill tabs (horizontally scrollable) + search input + entity dropdown + date range picker
3. **Data table** — white card, gray header row, hover rows, status badges, last col = "View" or "Edit" link
4. **Pagination** — "Showing 1–25 of N" left, Prev / Next right

Applies to: Invoices, Bills, Credit Notes, Debit Notes, Customers, Vendors, Products, Journal, Bank Transactions, Employees, Payroll Runs, Attendance, PO list, Lab Orders, OPD Tokens, IPD Admissions.

### 7c. Form Page Template (applies to all transaction entry pages)

Structure:

1. **Breadcrumb** — `Section › List › New/Edit Entity`
2. **Page header row** — title + action buttons (Save Draft, Preview, **Save & Send**)
3. **White card form body:**
   - **Header fields** — 2-column grid: entity selector (typeahead), auto-generated doc#, date, due date, terms, reference
   - `<hr>` divider
   - **Line items table** — inline-editable: Item/Description, Qty, Rate, Amount, ✕ delete. "＋ Add line item" below.
   - `<hr>` divider
   - **Footer row** — 2 cols: Notes textarea (left) + Subtotal / Tax / **Total** summary (right)
4. **Sticky bottom action bar** — dark bg, Save Draft + primary action button. Always visible while scrolling.

Applies to: New/Edit Invoice, Bill, Credit Note, Debit Note, Journal Entry, Purchase Order, Payment form.

### 7d. Report Page Template

1. **Page header** — title + period selector + Export button
2. **`<PrintHeader>` component** — unchanged behavior, updated colors
3. **Report table** — white card, same table style as list pages
4. **Print:** existing `print:hidden` / `orientation` system preserved

---

## 8. Mobile Layout (< 768px)

### Bottom Tab Bar (`components/BottomNav.tsx`) — updated

5 fixed tabs: **Home · Sales · Purchases · Reports · More**

- Height: 58px + safe-area-inset-bottom
- Active tab: green icon + label
- "More" opens full-screen nav drawer with all sections

### Mobile-specific behaviors

- **Tables → card list:** each row becomes a card with party name (bold), doc# + date (muted), amount (right), status badge
- **Status filter pills:** horizontal scroll row above card list
- **FAB (＋):** fixed bottom-right, 44px green circle, primary action for current section
- **Sub-nav panel:** hidden; section switching via top hamburger → slide-in drawer
- **Forms:** single column, full-width inputs, sticky save bar retained
- **KPI grid:** 2×2 (not 4-across)

### Breakpoints

| Breakpoint | Layout |
|---|---|
| ≥ 1024px | Top navbar + left sub-nav panel + multi-column grids |
| 768–1023px | Top navbar collapses to hamburger; sub-nav = slide-in drawer; 2×2 KPI; table hides low-priority columns; single-column forms |
| < 768px | Bottom tab bar; tables → cards; FAB; 2×2 KPI |

---

## 9. Phased Delivery Plan

### Phase 1 — Foundation (design system + shell)
**Goal:** Every page instantly looks QB-style from day 1 of this phase.

- Replace CSS tokens in `globals.css`
- Build `TopNav.tsx` (replaces `Header.tsx`)
- Build `SubNav.tsx` (replaces `Sidebar.tsx`)
- Update `app/(dashboard)/layout.tsx` to use TopNav + SubNav
- Update `lib/nav.ts` — `TOP_NAV` and `SUB_NAV` config maps
- Update `BottomNav.tsx` — 5-item QB mobile bottom bar

Deliverable: All pages render with new chrome. Individual page content still uses old card/table styles until Phase 2–3.

### Phase 2 — Core pages
**Goal:** Highest-traffic pages fully QB-styled.

Pages: Dashboard, Invoices (list + form), Bills (list + form), Customers (list + detail), Vendors (list + detail), Journal (list + form), Reports hub.

Work per page:
- Apply `qb-page-header` pattern (title + subtitle + action buttons)
- Apply filter bar + pill tabs
- Apply table token classes (`ui-th`, `ui-td` updated to QB tokens)
- Apply form 2-column grid + sticky action bar
- Dashboard: new KPI cards + AR/AP summary widgets + recent transactions

### Phase 3 — Secondary pages
**Goal:** Complete coverage of all remaining pages.

Groups:
- **Accounting:** COA, Trial Balance, Balance Sheet, P&L, Cash Flow, GL Ledger, Period Close
- **Banking:** Bank Accounts, Bank Book, Reconciliation, Bank Imports
- **Sales tail:** Credit Notes, AR Aging, Customer Statements, Advances, Recurring
- **Purchases tail:** Debit Notes, AP Aging, Vendor Statements, Purchase Orders, Debit Notes
- **Inventory:** Products, Categories, Product Ledger, Performance
- **Payroll:** Employees, Payroll Runs, Attendance, Components, Payslips
- **Healthcare:** Patients, Doctors, OPD, IPD, Lab, Reports
- **Manufacturing, Telecom, PRA:** existing page styling updated

### Phase 4 — Mobile + polish
**Goal:** Ship-ready quality.

- Responsive table→card conversion (Tailwind responsive variants)
- FAB component for mobile
- "More" drawer for mobile nav
- Print style audit (ensure `--primary` green replaces gold in print headers)
- Dark mode audit (update `globals.css` dark theme tokens)
- Cross-browser / cross-device QA pass

---

## 10. Files Changed

### New files
- `frontend/src/components/TopNav.tsx`
- `frontend/src/components/SubNav.tsx`

### Modified files
- `frontend/src/app/globals.css` — token replacement
- `frontend/src/app/(dashboard)/layout.tsx` — use TopNav + SubNav
- `frontend/src/lib/nav.ts` — TOP_NAV + SUB_NAV config
- `frontend/src/components/BottomNav.tsx` — 5-item QB style
- `frontend/src/components/Header.tsx` — retired (replaced by TopNav)
- `frontend/src/components/Sidebar.tsx` — retired (replaced by SubNav)
- All 70+ page files — apply page template patterns (Phases 2–3)

### Unchanged
- All backend files — zero backend changes required
- `PrintHeader.tsx` — behavior preserved, colors auto-update via tokens
- `apiFetch`, auth, routing logic — untouched
- Module system (`ModuleContext`, `OnboardingGuard`) — logic unchanged, nav wiring updated

---

## 11. Success Criteria

- [ ] All pages render with QB green palette — no gold/cream remaining
- [ ] Top navbar present on all authenticated pages
- [ ] Left sub-nav shows correct items for active section
- [ ] Module-gated items hidden when module not installed
- [ ] Bottom tab bar works on < 768px viewports
- [ ] Tables convert to card list on mobile
- [ ] `npm run build` passes with zero TypeScript errors
- [ ] Print output unaffected (landscape/portrait rules preserved)
- [ ] Dark mode tokens updated (no gold/cream in dark theme)
- [ ] 335 pages verified (0 JS console errors)
