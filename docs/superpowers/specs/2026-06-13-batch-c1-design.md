# Batch C1 — Decimal Precision (#64) + Voucher-Type Account Hints (#63)

**Date:** 2026-06-13
**Status:** Approved
**Issues:** #64 (Decimal Value), #63 (Filter Account Dropdown in New Entry)

---

## Problem

### #64 — Decimal Precision
Amounts are displayed with inconsistent precision:
- `fmtCurrency` (used in dashboards, reports, tables via `useFmt`) rounds to the nearest integer — zero decimal places.
- Raw `.toFixed(2)` calls in entry/recurring/payment forms hard-code two decimal places.

Users need a tenant-level setting to choose 2 or 4 decimal places across all amount displays.

### #63 — Voucher-Type Account Hints
The New Entry form (`/entry`) shows all postable accounts in every row's `<select>` regardless of voucher type. When a user selects CP (Cash Payment), they should see cash/bank accounts first; for SL (Sale), revenue and asset accounts first — reducing mis-posting errors.

---

## Design

### Backward compatibility

- `decimal_places` defaults to `"2"` — all existing displays are unchanged until the user changes the setting.
- Account hint filtering is soft (suggested types appear first; all accounts remain reachable below a divider). No hard blocking. Selected accounts are never cleared on voucher-type change.

---

## Section 1 — #64: Configurable Decimal Places

### 1.1 Backend — `routers/settings.py`

Add `decimal_places: Optional[str] = None` to `SettingsUpdate`. Add validation:
```python
if "decimal_places" in updates:
    if updates["decimal_places"] not in ("2", "4"):
        raise HTTPException(400, "decimal_places must be '2' or '4'")
```
The value is stored as a string in the `Settings` KV table (same pattern as `ui_density`). No migration needed — KV rows are created on first write.

### 1.2 Frontend — `SettingsContext.tsx`

**`AppSettings` interface:** add `decimal_places: string`  
**`defaults`:** `decimal_places: "2"`

**Fix `fmtCurrency`** — currently rounds to integer (shows no decimal places). Replace with:
```ts
export function fmtCurrency(n: number, currency: string, dp: number = 2): string {
  const formatted = (n || 0).toLocaleString("en-PK", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  })
  return `${currency} ${formatted}`
}
```

**Update `useFmt`** to read `decimal_places` and pass it to `fmtCurrency`:
```ts
export function useFmt() {
  const { settings } = useSettings()
  const dp = parseInt(settings.decimal_places || "2")
  return (n: number) => fmtCurrency(n, settings.currency || "PKR", dp)
}
```

**Add `useDp` hook** for plain number formatting (`.toFixed` replacement):
```ts
export function useDp(): number {
  const { settings } = useSettings()
  return parseInt(settings.decimal_places || "2")
}
```

### 1.3 Frontend — `.toFixed(2)` call sites

Replace all `.toFixed(2)` with `.toFixed(dp)` where `dp = useDp()`. Affected files:
- `frontend/src/app/(dashboard)/entry/page.tsx` (3 sites)
- `frontend/src/app/(dashboard)/recurring/page.tsx` (4 sites)
- `frontend/src/components/payments/PaymentReceivedForm.tsx` (1 site)
- `frontend/src/components/payments/BillPaymentForm.tsx` (1 site)

### 1.4 Frontend — Settings page

Add a "Decimal Places" select immediately after the Currency select in the Accounting Preferences card:
```tsx
<div>
  <label className="block text-sm font-semibold text-black/85 mb-2">Decimal Places</label>
  <select
    value={form.decimal_places}
    onChange={e => handleChange('decimal_places', e.target.value)}
    className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black"
  >
    <option value="2">2 — Standard (1,500.00)</option>
    <option value="4">4 — Extended (1,500.0000)</option>
  </select>
</div>
```

---

## Section 2 — #63: Voucher-Type Account Hints

### 2.1 `frontend/src/lib/voucherTypes.ts`

Add `VOUCHER_ACCOUNT_HINTS` constant (alongside existing `VOUCHER_TYPES`):
```ts
export type AccountType = "Asset" | "Liability" | "Equity" | "Revenue" | "Expense"

export const VOUCHER_ACCOUNT_HINTS: Record<string, AccountType[]> = {
  CP: ["Asset"],
  CR: ["Asset"],
  BP: ["Asset"],
  BR: ["Asset"],
  CO: ["Asset"],
  SL: ["Asset", "Revenue"],
  SR: ["Asset", "Revenue"],
  CN: ["Asset", "Revenue"],
  PR: ["Asset", "Expense", "Liability"],
  PV: ["Asset", "Expense", "Liability"],
  DN: ["Asset", "Expense", "Liability"],
  JV: [],  // empty = show all without divider
}
```

### 2.2 `frontend/src/app/(dashboard)/entry/page.tsx`

Import `VOUCHER_ACCOUNT_HINTS` from `@/lib/voucherTypes`.

Compute split inside the component (derived from existing `accounts` and `voucherType`):
```ts
const hintTypes = VOUCHER_ACCOUNT_HINTS[voucherType] ?? []
const hintedAccounts = hintTypes.length > 0
  ? accounts.filter(a => hintTypes.includes(a.type as AccountType))
  : []
const otherAccounts = hintTypes.length > 0
  ? accounts.filter(a => !hintTypes.includes(a.type as AccountType))
  : accounts
```

In both the desktop table and mobile card account `<select>` elements, replace the flat `accounts.map(...)` with:
```tsx
<option value="">Select Account</option>
{hintedAccounts.map(a => (
  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
))}
{hintedAccounts.length > 0 && otherAccounts.length > 0 && (
  <option disabled>── All accounts ──</option>
)}
{otherAccounts.map(a => (
  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
))}
```

No changes to account pre-selection or clearing on voucher-type change.

---

## Tests

### Backend (new file `backend/tests/test_settings_decimal.py`)
1. `test_decimal_places_persists` — PATCH `{"decimal_places": "4"}`, GET settings, assert value is `"4"`
2. `test_decimal_places_rejects_invalid` — PATCH `{"decimal_places": "3"}`, assert HTTP 400

### Frontend
No new test files. The build (`npm run build`) is the smoke check.

---

## What is NOT changing
- Backend amount storage — Decimal precision is unchanged; this is display-only.
- Any amount computation logic — only display/formatting changes.
- Hard enforcement on account selection — soft hints only, all accounts remain selectable.
- Customers, vendors, products pages that use `fmt()` — those already call `useFmt()` and will pick up the new decimal places automatically.
