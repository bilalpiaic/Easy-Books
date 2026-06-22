# PRA Sales Invoice Portal — Design Spec

_Date: 2026-06-22 · Status: Approved · Author: Claude Code_

---

## Overview

Transform the PRA e-Invoice tenant experience from a full accounting app (with PRA bolted on) into a focused **Sales Invoice Portal** for accountants operating under Punjab Revenue Authority (PRA) compliance obligations.

**Target user:** Accountant — creates and manages invoices, monitors PRA submission status, handles walk-in retail sales.

**Activation:** Role-based. Non-admin users on a PRA-enabled tenant (`pra_enabled = "true"`) enter portal mode automatically. Admin users retain the full accounting UI.

**Approach:** Feature-flag (Approach C) — a single `usePRAPortal()` hook gates all simplifications. No new routes, no duplicate codebases, zero impact on non-PRA tenants.

---

## 1. `usePRAPortal()` Hook

**File:** `frontend/src/hooks/usePRAPortal.ts` _(new)_

```ts
import { getCurrentUser } from "@/lib/auth"

export function usePRAPortal(): { isPortal: boolean } {
  const { settings } = useSettings()    // already global context
  const user = getCurrentUser()         // decodes JWT from localStorage
  const role = user?.role ?? "viewer"
  return {
    isPortal: settings.pra_enabled === "true" && role !== "admin" && role !== "owner"
  }
}
```

- Returns `isPortal: true` only when `pra_enabled === "true"` AND the current user is not an admin/owner.
- All portal-mode conditionals in the app read from this single hook.
- No DB change, no new setting key.

---

## 2. Sidebar Simplification

**File:** `frontend/src/components/Sidebar.tsx`

When `isPortal = true`, the sidebar renders only:

| Section | Items |
|---------|-------|
| **Invoicing** | Invoices · Customers · Products · Credit Notes |
| **Reports** | Sales Report · Customer Statement · PRA Submission Logs |
| **Settings** | Settings (always visible) |

All other sections (Payable, Inventory, Banking, Payroll, GL/Journal, CoA, HRM) are hidden.

The logo/home link navigates to `/invoices` instead of `/dashboard`. The 3-state collapsible/pinned behaviour is unchanged.

Admin users on PRA tenants: `isPortal = false` → full sidebar, no change.

---

## 3. Dashboard → Invoice Queue

**Files:** `frontend/src/app/(dashboard)/page.tsx`, `frontend/src/app/(dashboard)/invoices/page.tsx`

**Redirect:** In the main dashboard page (`/dashboard`), add a `useEffect` that redirects to `/invoices` when `isPortal = true`. The invoice list page becomes the effective home screen.

**KPI Strip** (portal mode only, above the invoice table):

```
┌──────────────────────────────────────────────────────────────┐
│  Today's Sales         PRA Submitted    Failed    Pending    │
│  PKR 1,24,500 (23)         21 ✓           1 ✗      1 ⏳     │
│                                             [Fix Failed →]   │
└──────────────────────────────────────────────────────────────┘
```

- Data: client-side filter of existing `/api/invoices` response by `issue_date === today`. No new endpoint.
- "Fix Failed →" deep-links to the failed invoice detail page.

**PRA Status column** added to the invoice list table (portal mode only):
- `✓ FIN-xxxxxxxx` (green) for submitted
- `⏳ Pending` (amber) for pending
- `✗ Failed` (red) for failed
- Hidden in non-portal mode to avoid cluttering the standard invoice list.

---

## 4. Invoice Form Enhancements

**File:** `frontend/src/components/invoices/InvoiceForm.tsx`

### 4a. Inline Buyer CNIC / NTN

Below the customer picker, two optional fields:

| Field | Label | Format | Behaviour |
|-------|-------|--------|-----------|
| `buyer_ntn` | Buyer NTN | `1234567-8` (7+1 digit) | Auto-populated from `customer.ntn` on customer select; editable for walk-ins |
| `buyer_cnic` | Buyer CNIC | `3520212345678` (13 digit) | Auto-populated from `customer.cnic` on customer select; editable for walk-ins |

Values are submitted with the invoice payload and stored on `Invoice.buyer_ntn` / `Invoice.buyer_cnic` (new columns, see §6).

### 4b. Payment Mode Position (portal mode)

When `isPortal = true`, the Payment Mode dropdown renders immediately below the date field — second field the accountant sets. In non-portal mode, it remains in its current position (after notes/memo).

### 4c. No other form changes

All other InvoiceForm fields (customer, date, lines, tax, terms, notes) remain unchanged.

---

## 5. Print Templates

### 5a. Enhanced A4 Invoice (existing)

**File:** `frontend/src/app/(dashboard)/invoices/[id]/print/page.tsx`

Additions to the existing print layout:
- **FIN block** — prominent bordered badge below invoice number: `Fiscal Invoice No: PRA-XXXXXXXX` (14px, bold); replaces the current tiny mono FIN text.
- **Buyer identification row** — NTN / CNIC printed below customer name/address when present.
- **Per-line PCT code + Tax %** — two new columns in the line items table; visible only in `@media print` (`print:table-cell`), hidden on-screen.

### 5b. Thermal Receipt (new)

**File:** `frontend/src/app/(dashboard)/invoices/[id]/receipt/page.tsx` _(new)_

- `@page { size: 80mm auto; margin: 4mm; }` — standard POS thermal width.
- Header: company name, POS ID.
- Invoice number, date + time.
- Line items: name, qty × rate, tax%, amount.
- Totals: subtotal / GST / **Total**.
- Payment mode.
- **FIN** in large monospace text.
- **QR code** — SVG inline, encodes the FIN string; generated client-side via `qrcode` npm package (zero server dependency).
- "Print Receipt" button on the invoice detail page (`invoices/[id]/page.tsx`), portal mode only, alongside existing "Print Invoice".

---

## 6. Backend Compliance Fixes

### 6a. Alembic Migration `0027_pra_buyer_fields`

Two new nullable columns on `Invoice`:
```python
buyer_ntn:  Optional[str] = Field(default=None)  # walk-in NTN override
buyer_cnic: Optional[str] = Field(default=None)  # walk-in CNIC override
```

SQLite-safe (nullable ADD COLUMN, no FK constraint). Guard with `bind.dialect.has_table("invoice")`.

### 6b. Payload Builder — buyer identity priority chain

**File:** `backend/services/pra.py` → `build_pra_payload()`

```python
BuyerPNTN = invoice.buyer_ntn or (customer.ntn if customer else None) or ""
BuyerCNIC = invoice.buyer_cnic or (customer.cnic if customer else None) or ""
```

### 6c. DateTime with actual time

**File:** `backend/services/pra.py` → `build_pra_payload()`

```python
# Before:
"DateTime": f"{invoice.issue_date} 00:00:00",
# After:
"DateTime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
```

### 6d. Credit Note PRA submission — deferred

`CreditNote` is a separate model (not an `Invoice` subtype) with its own `invoice_id` back-reference. Wiring PRA `InvoiceType=3` for credit notes requires a distinct PRA submission path for `CreditNote` records — out of scope for this sprint. Deferred to a future PRA compliance sprint alongside Debit Note (InvoiceType=2) support.

---

## 7. Files Touched Summary

| File | Change |
|------|--------|
| `frontend/src/hooks/usePRAPortal.ts` | **New** — portal gate hook |
| `frontend/src/components/Sidebar.tsx` | Filter nav items when `isPortal` |
| `frontend/src/app/(dashboard)/page.tsx` | Redirect to `/invoices` when `isPortal` |
| `frontend/src/app/(dashboard)/invoices/page.tsx` | KPI strip + PRA status column |
| `frontend/src/components/invoices/InvoiceForm.tsx` | Buyer CNIC/NTN fields + payment mode position |
| `frontend/src/app/(dashboard)/invoices/[id]/print/page.tsx` | FIN badge + buyer ID + PCT/tax columns |
| `frontend/src/app/(dashboard)/invoices/[id]/receipt/page.tsx` | **New** — 80mm thermal receipt |
| `frontend/src/app/(dashboard)/invoices/[id]/page.tsx` | "Print Receipt" button (portal only) |
| `backend/models.py` | `Invoice.buyer_ntn`, `Invoice.buyer_cnic` |
| `backend/services/pra.py` | DateTime fix, buyer priority chain, InvoiceType CN wiring |
| `backend/routers/invoices.py` | Accept `buyer_ntn`, `buyer_cnic` on create/edit |
| `backend/alembic/versions/0027_pra_buyer_fields.py` | **New** — migration |

---

## 8. Out of Scope

- QR code printing on A4 invoice (thermal receipt only)
- FurtherTax configuration (stays 0 — no current PRA tenant uses it)
- Credit Note / Debit Note PRA wiring (InvoiceType 2/3) — deferred; requires separate submission path for CreditNote model
- New backend API endpoints (all KPI data from existing `/api/invoices`)
- Multi-language support for portal mode (deferred)
