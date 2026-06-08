# Recent Transactions Enhancement (#41) — Design

_Date: 2026-06-08 · Branch: `feature/issue41-recent-transactions` · Base: `main` @ v2.5.0_

## Problem

The dashboard's **Recent Transactions** widget is minimal — it lists only `jv_number`,
`date`, and `description` (from the `/api/reports/dashboard` `recent` field). Now that
voucher series (#44) ships a `voucher_type` on every transaction and `/api/reports/journal`
returns rich entry-level rows, the widget should surface the full picture (voucher type,
account, amount) with user-selectable columns, a voucher-type filter, sort, and quick
search — so users can scan and jump into recent activity without leaving the dashboard.

## Scope (decided)

- **In:** replace the dashboard Recent-Transactions widget with a richer table backed by
  `/api/reports/journal`; user-selectable columns (persisted), voucher-type filter,
  sort-by-date, quick search, click-to-open.
- **Out / decided against:** a **Party** column (no clean party field at the
  journal-entry level — narration carries it); **any backend change** (the existing
  endpoint already returns everything needed); server-side filtering (client-side over a
  recent window instead).

## Decisions (locked during brainstorming)

1. **Frontend-only** — reuse `GET /api/reports/journal` as-is; no backend work.
2. **Drop Party** — rely on the narration/description, which already names the party.
3. **localStorage persistence** (per-browser), keyed per tenant — no settings/backend.
4. **Client-side filter/sort/search** over a recent window (fetch ~100 rows once).
5. **Extract a `RecentTransactions` component** rather than bloat `dashboard/page.tsx`.

## §1 · Data source (no backend change)

On mount the widget calls `GET /api/reports/journal?limit=100` (via `apiFetch`). Response
`items` are entry-level rows, each: `transaction_id`, `jv_number`, `voucher_type`,
`legacy_jv_number`, `date`, `description`, `account_name`, `debit`, `credit`,
`is_reversed`. All interactions operate on this loaded set. The widget no longer reads the
`/dashboard` `recent` field (that field can remain in the dashboard payload, just unused
by this widget).

## §2 · Component & columns

New component `frontend/src/components/RecentTransactions.tsx` (client component), rendered
by `dashboard/page.tsx` in place of the current inline widget. It owns its own fetch +
state.

**Columns** (default order): **Date · Voucher No · Voucher Type · Account · Narration ·
Amount**.
- *Amount* renders the entry's non-zero side (debit or credit) with a small **Dr/Cr**
  badge.
- *Voucher Type* renders the type code (SL/PU/CR/CP/JV/CN/DN…) styled as a badge.
- Reversed rows (`is_reversed`) get a subtle visual marker (muted + a "reversed" tag).

**User-selectable columns:** a column-config dropdown (checkbox per column) toggles
visibility. The visible-column set persists in `localStorage` under a stable key —
`eb.recentTx.cols` (namespaced by tenant id if it's readily available from the existing
auth context/token decode; otherwise the plain key, since localStorage is already
per-browser). On load, restore the saved set; default to all columns if none saved. Date
and Amount are always shown (can't be hidden) so a row is never empty.

## §3 · Filter / sort / search (client-side)

Over the loaded rows:
- **Voucher-type filter:** a dropdown populated from `lib/voucherTypes.ts` (plus "All");
  filters rows by `voucher_type`.
- **Sort by date:** a toggle (newest ↔ oldest); rows arrive newest-first, so this flips
  the order.
- **Quick search:** a debounced text input; case-insensitive substring match across
  `jv_number`, `account_name`, and `description`.
- Loading and empty states preserved ("No transactions for this period." / a spinner).

## §4 · Click-to-open

A row click navigates to the existing journal view using the current pattern
`/journal?jv=<jv_number>` (consistent with today's widget link and the "View all →" link,
which both already point at `/journal`).

## §5 · Testing & verification

The frontend has no unit-test harness (backend is verified via pytest, frontend via
lint + manual). Verification for #41:
- **`npm run lint`** — no new errors in `RecentTransactions.tsx` or `dashboard/page.tsx`.
- **Manual smoke** (if app run): widget loads recent rows; column toggles work and persist
  across reload; voucher-type filter, date sort, and search behave; a row opens the
  correct voucher in `/journal`.
- No backend change → backend test suite unaffected.

## Success criteria

The dashboard Recent-Transactions widget shows Date / Voucher No / Voucher Type / Account /
Narration / Amount; users can hide/show columns (persisted across reloads), filter by
voucher type, sort by date, and quick-search, and clicking a row opens its voucher. No
backend change; lint clean.
