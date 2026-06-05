# Design: UI Density System (Feature 6)

**Date:** 2026-06-04
**Status:** Approved (direction chosen by product owner)

## Overview

Spacing across screens is inconsistent and over-generous: 20+ pages hand-roll
`<table>` markup with inline `px-6 py-4` cells and there is no shared table
primitive, so there's no single lever for density. Print is already well-tuned
(`globals.css:166-177`). This feature introduces a **density system** — CSS
density tokens + semantic classes — applied app-wide so tables, forms, cards and
print all derive spacing from one source, with a **Comfortable/Compact toggle**
in Settings (persisted per-tenant).

Goal phrasing from the owner: data should display **right-sized — neither
squeezed nor expanded** — across all views, reports, forms, and print.

### Locked decisions
| Decision | Choice |
|----------|--------|
| Density behavior | Tuned default **+** Comfortable/Compact toggle in Settings (per-tenant) |
| Implementation | Density CSS variables + semantic classes (`.ui-table`/`.ui-th`/`.ui-td`, form/card spacing); sweep the ~20 table files + forms to use them and drop inline `px-6 py-4` |
| Sequencing | **Foundation first** — built before Features 1–5 so their new/edited UI inherits correct spacing |

## Architecture

**Density tokens (CSS variables in `globals.css`).** A `:root` comfortable
default and a `[data-density="compact"]` override, set on `<html>`:

```css
:root {
  --ui-cell-px: 1rem;      --ui-cell-py: 0.55rem;
  --ui-head-py: 0.55rem;   --ui-section-gap: 1.25rem;
  --ui-card-pad: 1.25rem;  --ui-control-py: 0.55rem;  --ui-control-px: 0.9rem;
}
[data-density="compact"] {
  --ui-cell-px: 0.7rem;    --ui-cell-py: 0.32rem;
  --ui-head-py: 0.38rem;   --ui-section-gap: 0.85rem;
  --ui-card-pad: 0.9rem;   --ui-control-py: 0.4rem;   --ui-control-px: 0.7rem;
}
```

(The comfortable default is already tighter than today's `px-6 py-4` =
1.5rem/1rem — that is the "expanded" feel being removed.)

**Semantic classes (one source of truth, screen + print):**
```css
.ui-table { width: 100%; }
.ui-th { padding: var(--ui-head-py) var(--ui-cell-px); }
.ui-td { padding: var(--ui-cell-py) var(--ui-cell-px); }
.ui-card { padding: var(--ui-card-pad); }
.ui-field { padding: var(--ui-control-py) var(--ui-control-px); }
.ui-section { gap: var(--ui-section-gap); }
```
The existing `@media print` block is refactored to read the same `--ui-*`
variables (kept at their print-pt equivalents) so print and screen never drift.

**Toggle plumbing.** New setting key `ui_density` (`comfortable` | `compact`)
added to backend `SettingsUpdate` and the frontend `AppSettings`/`SettingsContext`.
A tiny client effect sets `document.documentElement.dataset.density` from the
setting on load and on change. A Settings UI control flips it.

**"Neither squeezed nor expanded".** Wide tables keep the existing
`min-w-[...]` + horizontal-scroll behavior (`globals.css:38-55`) so dense tables
never crush columns; the tuned default prevents over-expansion. No per-table
auto-magic — predictable and consistent.

## Migration scope (the sweep)
- ~20 table pages: replace inline `px-6 py-4` header/body cell classes with
  `ui-th`/`ui-td` (keep alignment/typography utilities like `text-right`,
  `font-mono`). Files found via `grep -rln "px-6 py-4" frontend/src`.
- Modal/forms: replace inline control padding (`px-4 py-3`) with `ui-field`.
- Cards: optional, where the `p-4`/`p-6` density looks off.

## Testing
- Backend: `ui_density` accepted/persisted by settings PATCH; rejects invalid value.
- Frontend: build/lint clean; manual + print check at both densities (a wide
  report like Trial Balance/GL, a form modal, an invoice print).
- No double-spacing regressions; horizontal scroll still works on narrow widths.

## Revised build order
**6 (density) → 1 → 2 → 3 → 4 → 5.** Foundation first; Features 1–5 then use the
`ui-*` classes for any new/edited tables and forms.
