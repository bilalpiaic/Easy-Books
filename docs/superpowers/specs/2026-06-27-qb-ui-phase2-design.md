# Easy-Books — QB Online UI Redesign: Phase 2 Design

**Date:** 2026-06-27
**Status:** Approved — ready for implementation planning
**Scope:** Core pages token migration + shared StatusBadge primitive
**Parent spec:** `docs/superpowers/specs/2026-06-27-qb-ui-redesign.md`

---

## 1. Summary

Phase 1 delivered the QB shell (TopNav, SubNav, BottomNav, CSS token system). Phase 2 migrates the 7 highest-traffic page groups from hardcoded gold/cream hex values to the QB CSS custom-property tokens established in Phase 1. No logic, API, routing, or structural layout changes — this is a pure styling migration plus one new shared primitive (`StatusBadge`).

**Approach:** Hybrid — build 1 shared component + 4 CSS utility classes first, then migrate each page group as an independent task with its own build verification and commit.

---

## 2. Problem Statement

Every Phase 2 page still uses hardcoded old-brand colors:

| Old value | Count | Replacement |
|---|---|---|
| `border-[#ede9e2]` | ~35 | `border-[var(--border)]` |
| `bg-[#f6f3ee]` / `hover:bg-[#f6f3ee]` | ~28 | `bg-[var(--bg-page)]` |
| `bg-[#b8943f]` (primary buttons) | ~18 | `bg-[var(--primary)]` |
| `hover:bg-[#a07c35]` | ~12 | `hover:bg-[var(--primary-dark)]` |
| `text-[#b8943f]` | ~14 | `text-[var(--primary)]` |
| `text-[#1a1814]` | ~10 | `text-[var(--text-primary)]` |
| `text-black/75` / `text-black/60` | ~22 | `text-[var(--text-muted)]` |
| `font-serif font-medium` on h1 | ~7 | `text-2xl font-bold text-[var(--text-primary)]` |
| `statusColors` inline dict | 2+ pages | `<StatusBadge status={x} />` |
| `"#b8943f"` in chart palette | 1 | `"#2CA01C"` |

Total: ~129 occurrences across 6 measured files; estimated ~150–170 across full Phase 2 scope.

---

## 3. Shared Primitives (Task 1)

### 3a. `StatusBadge.tsx`

**File:** `frontend/src/components/StatusBadge.tsx`

A single component replacing the copy-pasted `statusColors` dict that currently exists independently in invoices, bills, journal, and other pages.

```
Props: { status: string; className?: string }

Status → badge token mapping (from QB redesign spec §5):
  paid | posted | active | delivered | completed → badge-green-bg / --success
  sent | due | partial | pending | draft-sent  → badge-yellow-bg / #D97706
  overdue | void | rejected                    → badge-red-bg / --danger
  draft | inactive | cancelled                 → badge-gray-bg / --text-muted
  processing | info                            → badge-blue-bg / --text-link
  approved                                     → badge-purple-bg / #7C3AED
  (unknown)                                    → badge-gray-bg / --text-muted
```

Visual style: `px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wide`

### 3b. CSS Utility Classes

**File:** `frontend/src/app/globals.css` (append to bottom)

Four utility classes that encode the QB table/card pattern. Pages use these short names instead of repeating 40-character class strings:

```css
.ui-th   { /* table header cell: QB gray bg, 11px bold uppercase muted */ }
.ui-td   { /* table data cell: border-b border-light, 13px */ }
.ui-tr   { /* table row hover: hover:bg-[var(--bg-row-hover)] */ }
.qb-card { /* white card: bg-card, border, rounded-lg, shadow-sm */ }
```

**Note:** Existing pages are not required to adopt `.ui-th` etc. immediately — they may keep inline Tailwind classes as long as colors use CSS tokens. The utilities are available for use and will be used in new or heavily-edited pages.

---

## 4. Token Replacement Map (definitive)

All Phase 2 files must use this mapping exclusively. No hardcoded hex values may remain after each task.

| Find | Replace with |
|---|---|
| `#ede9e2` | `var(--border)` |
| `#f6f3ee` | `var(--bg-page)` |
| `#faf6ec` | `var(--bg-page)` |
| `#b8943f` | `var(--primary)` |
| `#a07c35` | `var(--primary-dark)` |
| `#1a1814` (non-nav) | `var(--text-primary)` |
| `text-black/75` | `text-[var(--text-muted)]` |
| `text-black/60` | `text-[var(--text-muted)]` |
| `text-black/30` | `text-[var(--border)]` |
| `font-serif font-medium` | `font-bold` (h1 is already `text-2xl` or similar) |
| `statusColors[x]` span | `<StatusBadge status={x} />` |
| `"#b8943f"` in JS arrays | `"#2CA01C"` |
| `bg-[#ffd966]/10` (selected row tint) | `bg-[var(--primary-light)]` |

---

## 5. Page Groups

### Task 2 — Dashboard (`dashboard/page.tsx`)

- Replace `"#b8943f"` → `"#2CA01C"` in `DOUGHNUT_COLORS` array
- Update KPI widget card styles: `border-[#ede9e2]` → `border-[var(--border)]`
- Update period selector button active state: `bg-[#b8943f]` → `bg-[var(--primary)]`
- Update any inline `text-[#b8943f]` metric values → `text-[var(--primary)]`
- **Do not** change `DashboardGrid`, `WIDGET_REGISTRY`, or layout — structure is correct

### Task 3 — Invoices (`invoices/page.tsx`, `invoices/new/page.tsx`, `invoices/[id]/page.tsx`)

- `invoices/page.tsx`: full token replacement + remove `statusColors` dict + add `import StatusBadge` + replace badge spans
- `invoices/new/page.tsx`: button and form input token replacement (keep existing 2-col layout)
- `invoices/[id]/page.tsx` (view): status badge, action button, card border tokens

### Task 4 — Bills (`bills/page.tsx`, `bills/new/page.tsx`, `bills/[id]/page.tsx`)

Same pattern as Task 3. Bills list also has its own `statusColors` dict to replace.

### Task 5 — Customers (`customers/page.tsx`, `customers/[id]/page.tsx`)

- List page: header, filter, table token replacement
- Detail page: customer info card, tab nav active color, statement table tokens

### Task 6 — Vendors (`vendors/page.tsx`, `vendors/[id]/page.tsx`)

Same pattern as Task 5 (AP mirror of AR).

### Task 7 — Journal (`journal/page.tsx`, `entry/page.tsx`)

- Journal list: voucher-type filter tabs, table header/row tokens, action button
- Journal entry form (`entry/page.tsx`): mode selector button active state, line-item table, save button

### Task 8 — Reports Hub (`trial-balance/page.tsx`, `pl/page.tsx`, `balance/page.tsx`)

- All three: page header token replacement, export button, filter bar
- These pages use `PrintHeader` (already token-aware via CSS vars) — no print changes needed
- Report table rows: `border-[#ede9e2]` → `border-[var(--border-light)]`, amount text color updates

---

## 6. Constraints

- **Zero logic changes.** Every API call, state variable, handler, and conditional remains untouched. Only `className` strings and one JS color array change.
- **Zero backend changes.**
- **`npm run build` must pass** after every task before committing.
- **`StatusBadge` must handle unknown statuses gracefully** (fall through to gray badge — no crash).
- **Print output unaffected.** Token-based colors already resolve correctly in print context via CSS vars. No `print:` classes need updating.
- **PRA portal block** (`invoices/page.tsx` dark PRA banner) keeps its `bg-[#1a1814]` intentionally — it is not a brand token, it is a high-contrast UI element with a specific purpose.
- **Selected-row gold tint** (`bg-[#ffd966]/10`) → `bg-[var(--primary-light)]` which is `#E8F5E4` (light green). Acceptable visual change.

---

## 7. Files Changed

| File | Change |
|---|---|
| `frontend/src/components/StatusBadge.tsx` | **Create** — new shared badge component |
| `frontend/src/app/globals.css` | Append 4 utility classes |
| `frontend/src/app/(dashboard)/dashboard/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/invoices/page.tsx` | Token migration + StatusBadge |
| `frontend/src/app/(dashboard)/invoices/new/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/invoices/[id]/page.tsx` | Token migration + StatusBadge |
| `frontend/src/app/(dashboard)/bills/page.tsx` | Token migration + StatusBadge |
| `frontend/src/app/(dashboard)/bills/new/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/bills/[id]/page.tsx` | Token migration + StatusBadge |
| `frontend/src/app/(dashboard)/customers/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/customers/[id]/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/vendors/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/vendors/[id]/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/journal/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/entry/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/trial-balance/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/pl/page.tsx` | Token migration |
| `frontend/src/app/(dashboard)/balance/page.tsx` | Token migration |

**Unchanged:** All backend files, all other frontend pages, `PrintHeader`, routing, auth, API layer.

---

## 8. Task Order & Commit Strategy

| Task | Files | Commit message |
|---|---|---|
| T1 | `StatusBadge.tsx` + `globals.css` | `feat(ui): add StatusBadge component and QB table utility classes` |
| T2 | `dashboard/page.tsx` | `feat(ui): migrate Dashboard page to QB token system` |
| T3 | `invoices/*` | `feat(ui): migrate Invoices pages to QB token system` |
| T4 | `bills/*` | `feat(ui): migrate Bills pages to QB token system` |
| T5 | `customers/*` | `feat(ui): migrate Customers pages to QB token system` |
| T6 | `vendors/*` | `feat(ui): migrate Vendors pages to QB token system` |
| T7 | `journal/page.tsx` + `entry/page.tsx` | `feat(ui): migrate Journal pages to QB token system` |
| T8 | `trial-balance` + `pl` + `balance` | `feat(ui): migrate Reports hub pages to QB token system` |
| T9 | none | Verification: `npm run build && npm run lint` (no commit) |

Build check after each task before committing. If build fails, fix before moving on.

---

## 9. Success Criteria

- [ ] `StatusBadge` renders correct QB badge colors for all known statuses
- [ ] Zero occurrences of `#ede9e2`, `#b8943f`, `#a07c35`, `#f6f3ee`, `font-serif font-medium` in any Phase 2 file
- [ ] `npm run build` passes with zero TypeScript errors after T9
- [ ] `npm run lint` passes after T9
- [ ] Print output visually unchanged (spot-check invoices print view)
- [ ] No JS console errors on Dashboard, Invoices list, Bills list, Customers list
