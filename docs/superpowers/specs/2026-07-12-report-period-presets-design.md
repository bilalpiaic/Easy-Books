# Report Period Presets (QuickBooks-style) — Design

**Issue:** #141 · **Date:** 2026-07-12 · **Status:** Approved (rollout scope + design confirmed in session)

## Goal

Replace the crude 30d/90d/Month/Year quick buttons on the shared date-range filter with the full QuickBooks Enterprise preset list (26 entries), fiscal-year-aware, and roll the shared component out to **every** report screen that filters by a from/to date range — no report re-implements its own range filter.

## Non-Goals

- The "Days per Aging Period" field on A/R–A/P aging (explicitly out of scope in the issue).
- Single-date "as of" filters (e.g. Balance Sheet's as-of date) — presets describe *ranges*.
- Document entry forms (invoice/bill/PO/GI/payroll dates) — not filters.
- Persisting the chosen preset per user/report (YAGNI; revisit if requested).

## Architecture

Three layers, one new file each way:

```
src/lib/datePresets.ts        pure resolver (no React, no I/O)  ← vitest unit tests
components/DateRangePicker.tsx UI rewrite, SAME prop contract   ← consumers unchanged
~15 hand-rolled report pages   converted to <DateRangePicker>   ← audited page-by-page
```

### 1. `src/lib/datePresets.ts` (new)

```ts
export type PresetId =
  | "all" | "today"
  | "this_week" | "this_week_to_date"
  | "this_month" | "this_month_to_date"
  | "this_fiscal_quarter" | "this_fiscal_quarter_to_date"
  | "this_fiscal_year" | "this_fiscal_year_to_last_month" | "this_fiscal_year_to_date"
  | "yesterday"
  | "last_week" | "last_week_to_date"
  | "last_month" | "last_month_to_date"
  | "last_fiscal_quarter" | "last_fiscal_quarter_to_date"
  | "last_fiscal_year" | "last_fiscal_year_to_date"
  | "next_week" | "next_4_weeks" | "next_month"
  | "next_fiscal_quarter" | "next_fiscal_year"
  | "custom";

export const PRESETS: { id: PresetId; label: string }[]; // QB order, exactly as issue lists

export interface PresetOpts { today?: Date; fiscalStartMonth: number /* 1-12 */ }

// Returns ISO "YYYY-MM-DD" bounds. "all" → { start: "", end: "" } (unbounded —
// consumers already treat empty as no filter). "custom" → null (caller keeps
// manual values).
export function resolvePreset(id: PresetId, opts: PresetOpts): { start: string; end: string } | null;

// Reverse lookup: which non-custom preset (if any) produces exactly this range
// today? Used to initialize the dropdown on pages that arrive with explicit
// dates (deep links, saved state). First match in PRESETS order wins.
export function matchPreset(start: string, end: string, opts: PresetOpts): PresetId | null;

// "January" → 1 … "December" → 12; unknown/empty → 1.
export function fiscalStartMonthFromSetting(value: string | undefined): number;
```

**Date semantics** (T = today, all local time, no external date lib — small internal helpers with day-clamped month arithmetic, e.g. Mar 31 − 1 month → Feb 28/29):

| Preset | Range |
|---|---|
| All | unbounded (`""`/`""`) |
| Today / Yesterday | [T, T] / [T−1d, T−1d] |
| This Week | [Mon(T), Mon(T)+6] — **weeks start Monday** |
| This Week-to-date | [Mon(T), T] |
| This Month / -to-date | [1st, last] / [1st, T] |
| This Fiscal Quarter / -to-date | current FQ full / [FQ start, T] |
| This Fiscal Year / -to-date | current FY full / [FY start, T] |
| This Fiscal Year-to-Last Month | [FY start, end of previous calendar month], end clamped to ≥ FY start |
| Last Week / -to-date | [Mon(T)−7, Mon(T)−1] / [Mon(T)−7, T−7d] |
| Last Month / -to-date | previous month full / [1st of prev month, T−1 month (day-clamped)] |
| Last Fiscal Quarter / -to-date | previous FQ full / [prev FQ start, T−3 months (day-clamped)] |
| Last Fiscal Year / -to-date | previous FY full / [prev FY start, T−1 year (day-clamped)] |
| Next Week | [Mon(T)+7, Mon(T)+13] |
| Next 4 Weeks | [T, T+27d] |
| Next Month / Next Fiscal Quarter / Next Fiscal Year | the following full period |
| Custom | `null` — manual From/To |

Uniform "-to-date on a past period" rule: period start → today shifted back by one period length (week −7d; month −1mo; quarter −3mo; year −1yr), day-clamped, never past the period's end.

**Fiscal math:** FY containing T starts on the 1st of `fiscalStartMonth` in year `y` such that that date ≤ T < same date next year. Fiscal quarters are the four consecutive 3-month blocks from FY start. `fiscal_year_start = "January"` (the default) makes fiscal == calendar, so tenants who never touched the setting see calendar behavior.

### 2. `components/DateRangePicker.tsx` (rewrite in place)

Prop contract **unchanged** — `{ start, end, onStartChange, onEndChange, label? }` — so all 14 current consumers upgrade with zero edits. New optional prop: `hideAll?: boolean` for reports that require a bounded period.

UI (per issue, mirroring QB's Customize Report → Dates row):
- Native `<select>` labeled by the existing uppercase label chip (default label stays "Period"; pages may pass "Dates"), listing `PRESETS` in order (minus All when `hideAll`).
- Selecting a non-custom preset calls `onStartChange`/`onEndChange` with the resolved bounds and renders From/To as **disabled** inputs.
- Selecting **Custom** enables From/To for manual entry (current behavior).
- A muted inline label shows the resolved range as `dd-mm-yy – dd-mm-yy` via `fmtDateJs` ("All dates" for All), satisfying the issue's "Today only"-style hint.
- Dropdown state initializes via `matchPreset(start, end)`; no match → Custom. It re-syncs the same way if the parent changes `start`/`end` externally (deep-link effects).
- `useSettings()` supplies `fiscal_year_start`; the old 30d/90d/Month/Year buttons are deleted.
- Styling: existing input/border/focus token classes; component stays inside consumers' `print:hidden` toolbars.

### 3. Rollout sweep

Convert every report page that hand-rolls a from/to **range** filter to `<DateRangePicker>`. Candidates found by audit (`type="date"` without DateRangePicker, filtered to range-filter reports — final list confirmed page-by-page in the plan): customer/vendor statements, attendance report, audit log, deferred revenue, commissions, analytic account detail, healthcare reports/OPD/IPD/lab lists, purchases gate-register / three-way-match / vendor-performance, store issue-register / gate-outward-register / dispatch-reconciliation / stock-tie-out, telecom, promo-discounts, credit/debit-notes list filters, advances, reconciliations. Pages whose date inputs turn out to be single-date or form fields on audit (e.g. exchange rates) are excluded, not force-fitted. Pages keep their own state variables and fetch logic — only the input UI is replaced. Document forms and as-of filters are untouched.

### 4. Saved filters / migration

Report-builder saved reports store literal filter values, not preset ids — nothing breaks; they surface as Custom. Deep-linked ranges resolve through `matchPreset`. No data migration.

## Testing

- **vitest** added to `frontend` devDependencies with `npm run test` script (pure Node environment, no jsdom): `src/lib/__tests__/datePresets.test.ts` covering every preset id, Monday week starts, fiscal offsets (January + July FY), month-end clamping (Jan 31 / Mar 31 / leap Feb), FY boundary edges (T in first month of FY for to-last-month), matchPreset round-trip of all presets, and the All/Custom sentinels.
- Component/page verification: `npm run build` + manual drive of Trial Balance, GL, a statement page, and one store register.

## Error handling

- Unknown `fiscal_year_start` string → month 1 (January) fallback, no throw.
- `resolvePreset` never returns inverted ranges (clamps documented above).
- Pages that require dates keep their existing guards; `hideAll` prevents All where unbounded queries would be pathological.

## Risks

- The 14 existing consumers silently change UX (buttons → dropdown) — intended, but the plan's verify step must click through a sample.
- Some hand-rolled pages bind extra behavior to their date inputs (e.g. refetch-on-change); conversion must preserve each page's fetch triggering.
