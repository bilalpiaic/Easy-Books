# Batch C1 — Decimal Precision + Voucher-Type Account Hints

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tenant-level `decimal_places` setting (2 or 4) that propagates to all amount displays; add voucher-type-aware account hints in the New Entry form.

**Architecture:** `decimal_places` is a string KV setting (same pattern as `ui_density`). Frontend: fix `fmtCurrency` to actually show decimal places (currently rounds to integer), add `useDp()` hook for raw `.toFixed` sites, replace all `.toFixed(2)` with `.toFixed(dp)`. Voucher hints: add `VOUCHER_ACCOUNT_HINTS` map to `voucherTypes.ts`, split account list into hinted/other in `entry/page.tsx`. No schema migration needed. No backend amount logic changes — display only.

**Tech Stack:** FastAPI / Python (settings router, KV settings table), Next.js 16 / React 19 / TypeScript. Tests with pytest + FastAPI TestClient. Run backend tests: `cd backend && uv run pytest`. Build frontend: `cd frontend && npm run build`.

---

## File map

| Action | File | What changes |
|--------|------|--------------|
| Modify | `backend/routers/settings.py` | Add `decimal_places` to `SettingsUpdate`; add validation |
| Create | `backend/tests/test_settings_decimal.py` | 2 tests: persist + reject-invalid |
| Modify | `frontend/src/context/SettingsContext.tsx` | Add `decimal_places` to interface/defaults; fix `fmtCurrency`; update `useFmt`; add `useDp` |
| Modify | `frontend/src/app/(dashboard)/settings/page.tsx` | Add Decimal Places select after Currency |
| Modify | `frontend/src/lib/voucherTypes.ts` | Add `AccountType` + `VOUCHER_ACCOUNT_HINTS` |
| Modify | `frontend/src/app/(dashboard)/entry/page.tsx` | Account hint split (desktop + mobile); replace `.toFixed(2)` with `dp` |
| Modify | `frontend/src/app/(dashboard)/recurring/page.tsx` | Replace 4× `.toFixed(2)` with `useDp` |
| Modify | `frontend/src/components/payments/PaymentReceivedForm.tsx` | Replace 1× `.toFixed(2)` with `useDp` |
| Modify | `frontend/src/components/payments/BillPaymentForm.tsx` | Replace 1× `.toFixed(2)` with `useDp` |

---

## Task 1: Backend — `decimal_places` setting (TDD)

**Files:**
- Create: `backend/tests/test_settings_decimal.py`
- Modify: `backend/routers/settings.py`

### Context

Settings are stored as KV rows in the `Settings` table (one row per key per tenant). `SettingsUpdate` is a Pydantic model with `Optional[str]` fields. The `update_settings` endpoint iterates `model_dump()` and upserts each non-None value. `ui_density` (in the same file) is the reference implementation for validated string settings. The test fixture pattern follows `backend/tests/test_settings_density.py`.

- [ ] **Step 1: Write two failing tests**

```python
# backend/tests/test_settings_decimal.py
"""decimal_places setting round-trips and rejects invalid values."""


def test_decimal_places_persists(client, admin_headers):
    h = admin_headers
    r = client.patch("/api/settings", headers=h, json={"decimal_places": "4"})
    assert r.status_code == 200
    got = client.get("/api/settings", headers=h).json()
    assert got["decimal_places"] == "4"


def test_decimal_places_rejects_invalid(client, admin_headers):
    r = client.patch("/api/settings", headers=admin_headers, json={"decimal_places": "3"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_settings_decimal.py -v
```

Expected: `test_decimal_places_persists` FAILS (field not accepted), `test_decimal_places_rejects_invalid` FAILS (no validation → 200 instead of 400).

- [ ] **Step 3: Add `decimal_places` to `SettingsUpdate` and add validation**

In `backend/routers/settings.py`, add to `SettingsUpdate` after `ui_density`:
```python
    # Amount display precision ("2" or "4")
    decimal_places: Optional[str] = None
```

In `update_settings`, add the validation block after the `ui_density` block (around line 84):
```python
    if "decimal_places" in updates:
        dp = updates["decimal_places"]
        if dp not in ("2", "4"):
            raise HTTPException(400, "decimal_places must be '2' or '4'")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd backend && uv run pytest tests/test_settings_decimal.py -v
```

Expected: both PASS.

- [ ] **Step 5: Run full suite — no regressions**

```bash
cd backend && uv run pytest -v 2>&1 | tail -10
```

Expected: 383 passed (381 previous + 2 new).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/settings.py backend/tests/test_settings_decimal.py
git commit -m "feat(settings): add decimal_places setting (2 or 4)"
```

---

## Task 2: Frontend — `SettingsContext.tsx` updates

**Files:**
- Modify: `frontend/src/context/SettingsContext.tsx`

### Context

`AppSettings` is an interface with string fields. All settings come back as strings from the KV API. `fmtCurrency(n, currency)` currently calls `Math.round()` — it shows zero decimal places (this is a bug that `decimal_places` fixes). `useFmt()` wraps `fmtCurrency` with the tenant's currency. After this task, `useFmt()` will automatically show the correct decimal places in all ~25 call sites without touching those files.

- [ ] **Step 1: Add `decimal_places` to `AppSettings` interface and defaults**

In `frontend/src/context/SettingsContext.tsx`:

In the `AppSettings` interface, add after `ui_density: string`:
```ts
  // Amount display precision
  decimal_places: string
```

In the `defaults` object, add after `ui_density: "comfortable"`:
```ts
  decimal_places: "2",
```

- [ ] **Step 2: Fix `fmtCurrency` to use decimal places**

Replace the existing `fmtCurrency` function (lines 107–111):
```ts
export function fmtCurrency(n: number, currency: string, dp: number = 2): string {
  const formatted = (n || 0).toLocaleString("en-PK", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  })
  return `${currency} ${formatted}`
}
```

- [ ] **Step 3: Update `useFmt` to pass decimal places**

Replace the existing `useFmt` function (lines 114–117):
```ts
export function useFmt() {
  const { settings } = useSettings()
  const dp = parseInt(settings.decimal_places || "2")
  return (n: number) => fmtCurrency(n, settings.currency || "PKR", dp)
}
```

- [ ] **Step 4: Add `useDp` hook**

Add immediately after `useFmt`:
```ts
/** Returns the tenant's configured decimal places as a number (2 or 4). */
export function useDp(): number {
  const { settings } = useSettings()
  return parseInt(settings.decimal_places || "2")
}
```

- [ ] **Step 5: Build to verify no TypeScript errors**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: build succeeds (no new errors).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/context/SettingsContext.tsx
git commit -m "feat(settings): decimal_places — fix fmtCurrency decimals, add useDp hook"
```

---

## Task 3: Frontend — Settings page UI

**Files:**
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx`

### Context

The settings form uses a `form` state object (type mirrors `AppSettings`) and `handleChange(key, value)` to update it. The Currency `<select>` lives at around line 247–259 inside the Accounting Preferences card. The Decimal Places selector goes immediately after it, inside the same `<div className="grid ...">` grid cell. The `form` object already picks up `decimal_places` from `AppSettings` since the page loads settings into form state.

- [ ] **Step 1: Verify the form state initialises `decimal_places`**

Check the top of `settings/page.tsx` for how the form state is initialised from `AppSettings`. It should already include `decimal_places: "2"` because it spreads from `defaults`. No change needed unless the form is explicitly typed differently.

- [ ] **Step 2: Add Decimal Places select after Currency**

Find the Currency `<select>` block (around line 246–259). Immediately after its closing `</div>`, add:

```tsx
            <div>
              <label className="block text-sm font-semibold text-black/85 mb-2">Decimal Places</label>
              <select
                value={form.decimal_places ?? "2"}
                onChange={e => handleChange('decimal_places', e.target.value)}
                className="w-full px-4 py-2 border border-[#ede9e2] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#b8943f] text-black"
              >
                <option value="2">2 — Standard (1,500.00)</option>
                <option value="4">4 — Extended (1,500.0000)</option>
              </select>
            </div>
```

- [ ] **Step 3: Build to verify no TypeScript errors**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)/settings/page.tsx"
git commit -m "feat(settings): add decimal places selector to settings page"
```

---

## Task 4: Frontend — `voucherTypes.ts` account hints

**Files:**
- Modify: `frontend/src/lib/voucherTypes.ts`

### Context

`VOUCHER_TYPES` (12 types) and `VOUCHER_TYPE_COLORS` already live in this file. Adding `VOUCHER_ACCOUNT_HINTS` here keeps all voucher-type metadata in one place. The `AccountType` type mirrors the `Account.type` string values returned by `GET /api/accounts`.

- [ ] **Step 1: Add `AccountType` and `VOUCHER_ACCOUNT_HINTS`**

Append to `frontend/src/lib/voucherTypes.ts` (after the existing exports):

```ts
export type AccountType = "Asset" | "Liability" | "Equity" | "Revenue" | "Expense"

/** Account types to surface first in the entry-form dropdown for each voucher type.
 *  Empty array = JV (no hint — show all accounts flat). */
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
  JV: [],
}
```

- [ ] **Step 2: Build to verify no TypeScript errors**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/voucherTypes.ts
git commit -m "feat(entry): add VOUCHER_ACCOUNT_HINTS to voucherTypes"
```

---

## Task 5: Frontend — Entry form: account hints + `useDp`

**Files:**
- Modify: `frontend/src/app/(dashboard)/entry/page.tsx`

### Context

The entry form has two account selectors — one in the **desktop table** (around line 183–193) and one in the **mobile card** (around line 254–263). Both render `{accounts.map(a => <option>)}`. They must both be updated identically.

Three `.toFixed(2)` sites exist:
- Line 313: `totalDebit.toFixed(2)`
- Line 317: `totalCredit.toFixed(2)`
- Line 322: `difference.toFixed(2)`

Imports currently include: `import { VOUCHER_TYPES } from "@/lib/voucherTypes"`. Add `VOUCHER_ACCOUNT_HINTS, AccountType` to this import. Add `useDp` to the SettingsContext import.

- [ ] **Step 1: Update imports**

Change the `voucherTypes` import from:
```ts
import { VOUCHER_TYPES } from "@/lib/voucherTypes"
```
To:
```ts
import { VOUCHER_TYPES, VOUCHER_ACCOUNT_HINTS, AccountType } from "@/lib/voucherTypes"
```

Add `useDp` to the SettingsContext import. Find the existing SettingsContext import (likely `import { useFmt, useSettings } from "@/context/SettingsContext"`) and add `useDp`:
```ts
import { useFmt, useSettings, useDp } from "@/context/SettingsContext"
```

If `useSettings` or `useFmt` is not already imported, adjust accordingly.

- [ ] **Step 2: Add `dp` and account hint variables inside the component**

Inside the component body (near where `accounts` state is declared), add:

```ts
const dp = useDp()

const hintTypes = VOUCHER_ACCOUNT_HINTS[voucherType] ?? []
const hintedAccounts = hintTypes.length > 0
  ? accounts.filter(a => hintTypes.includes(a.type as AccountType))
  : []
const otherAccounts = hintTypes.length > 0
  ? accounts.filter(a => !hintTypes.includes(a.type as AccountType))
  : accounts
```

- [ ] **Step 3: Replace desktop table account selector**

Find the desktop table `<select>` for account_id (around line 183). Replace the inner content:

From:
```tsx
<option value="">Select Account</option>
{accounts.map(a => (
  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
))}
```

To:
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

- [ ] **Step 4: Replace mobile card account selector**

Find the mobile card `<select>` for account_id (around line 254). Apply the same replacement as Step 3.

- [ ] **Step 5: Replace `.toFixed(2)` with `.toFixed(dp)`**

Find and replace all three occurrences:
- `totalDebit.toFixed(2)` → `totalDebit.toFixed(dp)`
- `totalCredit.toFixed(2)` → `totalCredit.toFixed(dp)`
- `difference.toFixed(2)` → `difference.toFixed(dp)`

- [ ] **Step 6: Build to verify no TypeScript errors**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
git add "frontend/src/app/(dashboard)/entry/page.tsx"
git commit -m "feat(entry): voucher-type account hints + decimal_places for totals"
```

---

## Task 6: Frontend — recurring and payment forms `useDp`

**Files:**
- Modify: `frontend/src/app/(dashboard)/recurring/page.tsx`
- Modify: `frontend/src/components/payments/PaymentReceivedForm.tsx`
- Modify: `frontend/src/components/payments/BillPaymentForm.tsx`

### Context

**`recurring/page.tsx`** has 4 `.toFixed(2)` sites:
- Line 89: error message `Debits (${totalDebit.toFixed(2)}) must equal Credits (${totalCredit.toFixed(2)})`
- Line 360: `{totalDebit.toFixed(2)}`
- Line 363: `{totalCredit.toFixed(2)}`

**`PaymentReceivedForm.tsx`** has 1 site:
- Line 145: `String(suggested.toFixed(2))`

**`BillPaymentForm.tsx`** has 1 site:
- Line 138: `String(suggested.toFixed(2))`

All three files need `useDp` imported from `@/context/SettingsContext` and called at component top-level.

- [ ] **Step 1: Update `recurring/page.tsx`**

Add `useDp` to its SettingsContext import. Call `const dp = useDp()` inside the component. Replace all 4 `.toFixed(2)` with `.toFixed(dp)`.

The import line to find:
```ts
import { useFmt, useSettings } from "@/context/SettingsContext"
```
Change to:
```ts
import { useFmt, useSettings, useDp } from "@/context/SettingsContext"
```

Inside the main component function (near other hooks at the top), add:
```ts
const dp = useDp()
```

Then replace:
- `totalDebit.toFixed(2)` → `totalDebit.toFixed(dp)` (all occurrences)
- `totalCredit.toFixed(2)` → `totalCredit.toFixed(dp)` (all occurrences)

- [ ] **Step 2: Update `PaymentReceivedForm.tsx`**

Find its SettingsContext import:
```ts
import { useFmt } from '@/context/SettingsContext'
```
Change to:
```ts
import { useFmt, useDp } from '@/context/SettingsContext'
```

Inside the component function (near other hooks), add:
```ts
const dp = useDp()
```

Replace:
```ts
setAlloc(inv.id, 'amount', String(suggested.toFixed(2)))
```
With:
```ts
setAlloc(inv.id, 'amount', String(suggested.toFixed(dp)))
```

- [ ] **Step 3: Update `BillPaymentForm.tsx`**

Find its SettingsContext import:
```ts
import { useFmt } from '@/context/SettingsContext'
```
Change to:
```ts
import { useFmt, useDp } from '@/context/SettingsContext'
```

Inside the component function (near other hooks), add:
```ts
const dp = useDp()
```

Replace:
```ts
setAlloc(bill.id, 'amount', String(suggested.toFixed(2)))
```
With:
```ts
setAlloc(bill.id, 'amount', String(suggested.toFixed(dp)))
```

- [ ] **Step 4: Build to verify no TypeScript errors**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 5: Run the full backend suite — no regressions**

```bash
cd backend && uv run pytest -v 2>&1 | tail -10
```

Expected: 383 passed.

- [ ] **Step 6: Commit**

```bash
git add \
  "frontend/src/app/(dashboard)/recurring/page.tsx" \
  frontend/src/components/payments/PaymentReceivedForm.tsx \
  frontend/src/components/payments/BillPaymentForm.tsx
git commit -m "feat(forms): use decimal_places setting for amount display in recurring + payment forms"
```

---

## Final verification

- [ ] Run the full backend suite:

```bash
cd backend && uv run pytest 2>&1 | tail -5
```

Expected: 383 passed.

- [ ] Run the frontend build:

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: no new errors.

- [ ] Close GitHub issues #63 and #64 with comments citing delivery.
