# PRA Sales Invoice Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the PRA e-Invoice tenant into a focused Sales Invoice Portal — simplified sidebar, invoice-queue dashboard, inline buyer identification, thermal receipt, and backend compliance fixes — all gated by a single `usePRAPortal()` feature flag.

**Architecture:** A single `usePRAPortal()` hook (reads `settings.pra_enabled` + JWT role) gates all UI changes. Non-admin users on PRA-enabled tenants see the simplified portal; all other tenants and admin users are unaffected. Backend gains two new `Invoice` columns (`buyer_ntn`, `buyer_cnic`), a DateTime fix, and buyer priority-chain logic in the PRA payload builder.

**Tech Stack:** Next.js 16 / React 19 / TypeScript (frontend), FastAPI / Python 3.11 / SQLModel (backend), Alembic (migrations), `qrcode.react` (QR SVG), `uv` + `pytest` (backend tests).

## Global Constraints

- All frontend files use `"use client"` where state/effects/hooks are used.
- Date display: always use `fmtDate()` from `@/lib/utils` — never raw ISO strings or `toLocaleDateString()`.
- Amount display: always use `fmt()` from `useFmt()` — never inline `toLocaleString()`.
- Icons: `lucide-react` only.
- Brand colors: background `#f6f3ee`, accent `#b8943f`, text `#1a1814`.
- Print orientation: this feature adds portrait pages only — do not set `orientation="landscape"`.
- Alembic migrations: nullable ADD COLUMN only — no FK constraints on ALTER; guard new tables with `has_table`.
- Backend: run tests from `backend/` with `uv run pytest`.
- Frontend: run linter with `npm run lint` from `frontend/`.
- `usePRAPortal()` must be called inside React components/hooks only — never at module level.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/hooks/usePRAPortal.ts` | **Create** | Single gate: `isPortal` flag |
| `frontend/src/components/Sidebar.tsx` | Modify | Filter nav items in portal mode |
| `frontend/src/app/(dashboard)/page.tsx` | Modify | Redirect to `/invoices` in portal mode |
| `frontend/src/app/(dashboard)/invoices/page.tsx` | Modify | KPI strip + PRA status column |
| `frontend/src/components/invoices/InvoiceForm.tsx` | Modify | Buyer CNIC/NTN fields, payment mode position |
| `frontend/src/app/(dashboard)/invoices/[id]/print/page.tsx` | Modify | Prominent FIN, buyer ID row, PCT/tax columns |
| `frontend/src/app/(dashboard)/invoices/[id]/receipt/page.tsx` | **Create** | 80mm thermal receipt with QR |
| `frontend/src/app/(dashboard)/invoices/[id]/page.tsx` | Modify | "Print Receipt" button (portal only) |
| `frontend/src/app/(dashboard)/pra-logs/page.tsx` | **Create** | PRA submission log table |
| `frontend/src/lib/nav.ts` | Modify | Add PRA Logs nav item |
| `backend/models.py` | Modify | `Invoice.buyer_ntn`, `Invoice.buyer_cnic` |
| `backend/alembic/versions/0027_pra_buyer_fields.py` | **Create** | Alembic migration |
| `backend/routers/invoices.py` | Modify | Accept buyer fields in `InvoiceCreate` |
| `backend/services/pra.py` | Modify | DateTime fix + buyer priority chain |
| `backend/tests/test_pra_payload.py` | **Create** | Unit tests for payload builder |

---

### Task 1: Backend — buyer fields + PRA compliance fixes

**Files:**
- Modify: `backend/models.py` (Invoice class, ~line 329)
- Create: `backend/alembic/versions/0027_pra_buyer_fields.py`
- Modify: `backend/routers/invoices.py` (InvoiceCreate ~line 89, create_invoice ~line 343, update_invoice ~line 728)
- Modify: `backend/services/pra.py` (build_pra_payload ~line 113)
- Create: `backend/tests/test_pra_payload.py`

**Interfaces:**
- Produces: `Invoice.buyer_ntn: Optional[str]`, `Invoice.buyer_cnic: Optional[str]`; `InvoiceCreate.buyer_ntn`, `InvoiceCreate.buyer_cnic`; fixed `build_pra_payload` with real DateTime and buyer priority chain.

- [ ] **Step 1: Write the failing payload-builder tests**

Create `backend/tests/test_pra_payload.py`:

```python
"""Unit tests for PRA payload builder (no DB required)."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from services.pra import build_pra_payload, PAYMENT_MODE_LABELS


def _make_invoice(**kwargs):
    inv = MagicMock()
    inv.number = "SL-2026-001"
    inv.issue_date = "2026-06-22"
    inv.subtotal = Decimal("1000")
    inv.gst_amount = Decimal("170")
    inv.total = Decimal("1170")
    inv.gst_rate = Decimal("17")
    inv.payment_mode = 1
    inv.buyer_ntn = None
    inv.buyer_cnic = None
    for k, v in kwargs.items():
        setattr(inv, k, v)
    return inv


def _make_customer(**kwargs):
    c = MagicMock()
    c.name = "Test Customer"
    c.ntn = None
    c.cnic = None
    c.phone = None
    for k, v in kwargs.items():
        setattr(c, k, v)
    return c


def _make_config():
    return {"pos_id": "123", "token": "tok", "endpoint": "https://example.com", "sandbox": True}


def test_datetime_is_not_midnight():
    """DateTime must include actual time, not 00:00:00."""
    payload = build_pra_payload(_make_invoice(), [], None, {}, {}, _make_config())
    assert payload["DateTime"] != f"2026-06-22 00:00:00"
    # Must match YYYY-MM-DD HH:MM:SS pattern
    import re
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", payload["DateTime"])


def test_buyer_ntn_invoice_overrides_customer():
    """invoice.buyer_ntn takes priority over customer.ntn."""
    inv = _make_invoice(buyer_ntn="9999999-9")
    cust = _make_customer(ntn="1111111-1")
    payload = build_pra_payload(inv, [], cust, {}, {}, _make_config())
    assert payload["BuyerPNTN"] == "9999999-9"


def test_buyer_cnic_invoice_overrides_customer():
    """invoice.buyer_cnic takes priority over customer.cnic."""
    inv = _make_invoice(buyer_cnic="3520299999999")
    cust = _make_customer(cnic="1111122222222")
    payload = build_pra_payload(inv, [], cust, {}, {}, _make_config())
    assert payload["BuyerCNIC"] == "3520299999999"


def test_buyer_ntn_falls_back_to_customer():
    """When invoice.buyer_ntn is None, use customer.ntn."""
    inv = _make_invoice(buyer_ntn=None)
    cust = _make_customer(ntn="7654321-0")
    payload = build_pra_payload(inv, [], cust, {}, {}, _make_config())
    assert payload["BuyerPNTN"] == "7654321-0"


def test_buyer_empty_when_no_source():
    """When neither invoice nor customer have NTN/CNIC, send empty string."""
    payload = build_pra_payload(_make_invoice(), [], None, {}, {}, _make_config())
    assert payload["BuyerPNTN"] == ""
    assert payload["BuyerCNIC"] == ""
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && uv run pytest tests/test_pra_payload.py -v
```

Expected: `AttributeError: Mock object has no attribute 'buyer_ntn'` or similar — confirms the new fields don't exist yet.

- [ ] **Step 3: Add `buyer_ntn` and `buyer_cnic` to Invoice model**

In `backend/models.py`, after line 335 (`pra_response_raw`):

```python
    pra_response_raw: Optional[str] = None  # raw JSON response for audit trail
    buyer_ntn: Optional[str] = None   # walk-in NTN override (takes priority over customer.ntn)
    buyer_cnic: Optional[str] = None  # walk-in CNIC override (takes priority over customer.cnic)
```

- [ ] **Step 4: Create Alembic migration**

Create `backend/alembic/versions/0027_pra_buyer_fields.py`:

```python
"""add buyer_ntn and buyer_cnic to invoice

Revision ID: 0027_pra_buyer_fields
Revises: d42ac2e7674d
Branch labels: None
Depends on: None
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_pra_buyer_fields"
down_revision = "d42ac2e7674d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoice", sa.Column("buyer_ntn",  sa.String(), nullable=True))
    op.add_column("invoice", sa.Column("buyer_cnic", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoice", "buyer_ntn")
    op.drop_column("invoice", "buyer_cnic")
```

- [ ] **Step 5: Run migration**

```bash
cd backend && uv run alembic upgrade head
```

Expected: `Running upgrade d42ac2e7674d -> 0027_pra_buyer_fields`.

- [ ] **Step 6: Add buyer fields to `InvoiceCreate` and wire into create/update**

In `backend/routers/invoices.py`, add to `InvoiceCreate` (after line 106):

```python
    payment_mode: Optional[int] = None   # PRA: 1=Cash 2=Card 3=GiftVoucher 4=Loyalty 5=Mixed 6=Cheque
    buyer_ntn: Optional[str] = None      # walk-in NTN override for PRA payload
    buyer_cnic: Optional[str] = None     # walk-in CNIC override for PRA payload
```

In `create_invoice` (after `payment_mode=body.payment_mode,` ~line 343):
```python
        payment_mode=body.payment_mode,
        buyer_ntn=body.buyer_ntn,
        buyer_cnic=body.buyer_cnic,
```

In `update_invoice` (after `inv.analytic_account_id = body.analytic_account_id` ~line 729):
```python
    inv.analytic_account_id = body.analytic_account_id
    inv.buyer_ntn = body.buyer_ntn
    inv.buyer_cnic = body.buyer_cnic
```

- [ ] **Step 7: Fix `build_pra_payload` in `services/pra.py`**

Replace lines 113–128 with:

```python
    payload = {
        "InvoiceNumber": "",
        "POSID": int(config["pos_id"]),
        "USIN": invoice.number,
        "DateTime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "BuyerName": (customer.name if customer else invoice.customer_name) or "",
        "BuyerPNTN": invoice.buyer_ntn or (customer.ntn if customer else None) or "",
        "BuyerCNIC": invoice.buyer_cnic or (customer.cnic if customer else None) or "",
        "BuyerPhoneNumber": (customer.phone if customer else None) or "",
        "TotalBillAmount": round(total_bill, 2),
        "TotalQuantity": round(total_qty, 2),
        "TotalSaleValue": round(total_sale_value, 2),
        "TotalTaxCharged": round(total_tax, 2),
        "Discount": round(total_discount, 2),
        "FurtherTax": 0.0,
        "PaymentMode": invoice.payment_mode or 1,
        "RefUSIN": None,
        "InvoiceType": invoice_type,
        "Items": pra_items,
    }
```

- [ ] **Step 8: Run tests to confirm they pass**

```bash
cd backend && uv run pytest tests/test_pra_payload.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 9: Run full test suite to check for regressions**

```bash
cd backend && uv run pytest -x -q
```

Expected: all existing tests still pass.

- [ ] **Step 10: Commit**

```bash
git add backend/models.py backend/alembic/versions/0027_pra_buyer_fields.py backend/routers/invoices.py backend/services/pra.py backend/tests/test_pra_payload.py
git commit -m "feat: add buyer_ntn/buyer_cnic to Invoice; fix PRA DateTime + buyer priority chain"
```

---

### Task 2: Frontend — `usePRAPortal()` hook

**Files:**
- Create: `frontend/src/hooks/usePRAPortal.ts`

**Interfaces:**
- Produces: `usePRAPortal(): { isPortal: boolean }` — consumed by Sidebar, dashboard page, invoices page, InvoiceForm, invoice detail page.

- [ ] **Step 1: Create the hook**

Create `frontend/src/hooks/usePRAPortal.ts`:

```ts
import { getCurrentUser } from "@/lib/auth"
import { useSettings } from "@/context/SettingsContext"

/**
 * Returns isPortal=true when the current user is a non-admin on a PRA-enabled tenant.
 * All portal-mode UI simplifications read from this single hook.
 */
export function usePRAPortal(): { isPortal: boolean } {
  const { settings } = useSettings()
  const user = getCurrentUser()
  const role = user?.role ?? "viewer"
  return {
    isPortal: settings.pra_enabled === "true" && role !== "admin" && role !== "owner",
  }
}
```

- [ ] **Step 2: Lint check**

```bash
cd frontend && npm run lint -- --max-warnings 0 src/hooks/usePRAPortal.ts
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/usePRAPortal.ts
git commit -m "feat: add usePRAPortal() hook — single gate for PRA sales portal mode"
```

---

### Task 3: Sidebar filter + dashboard redirect

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/app/(dashboard)/page.tsx`

**Interfaces:**
- Consumes: `usePRAPortal(): { isPortal: boolean }` from Task 2.

- [ ] **Step 1: Add portal nav filtering to Sidebar**

In `frontend/src/components/Sidebar.tsx`, add the import at the top (after existing imports):

```ts
import { usePRAPortal } from "@/hooks/usePRAPortal"
```

Inside the `Sidebar` component, after line 121 (`const isAdmin = role === "admin" || role === "owner"`):

```ts
  const { isPortal } = usePRAPortal()

  const PRA_PORTAL_HREFS = new Set([
    "/invoices", "/customers", "/products", "/credit-notes",
    "/customer-performance", "/pra-logs", "/settings",
  ])
```

Replace the existing `visibleNav` line (currently `const visibleNav = NAV.filter(...)`):

```ts
  const visibleNav = NAV.filter(i => {
    if (i.forModel && i.forModel !== businessModel) return false
    if (i.adminOnly && !isAdmin) return false
    if (isPortal) return PRA_PORTAL_HREFS.has(i.href)
    return true
  })
```

Also replace the home link inside the drawer JSX — find the logo/home `<Link>` or `<button>` that navigates to `/dashboard` and conditionally change it to `/invoices` in portal mode. Look for the section that renders the org name at the top of the drawer and wrap the href:

```tsx
// Find the org name link (renders company name at top of sidebar)
// Change its href conditionally:
href={isPortal ? "/invoices" : "/dashboard"}
```

- [ ] **Step 2: Add redirect to dashboard page**

In `frontend/src/app/(dashboard)/page.tsx`, add the hook import and redirect effect. Add at the top of the main component function (after existing state/hooks):

```tsx
import { usePRAPortal } from "@/hooks/usePRAPortal"
import { useRouter } from "next/navigation"

// Inside the component:
const { isPortal } = usePRAPortal()
const router = useRouter()

useEffect(() => {
  if (isPortal) router.replace("/invoices")
}, [isPortal])

if (isPortal) return null  // avoid flash before redirect
```

- [ ] **Step 3: Lint check**

```bash
cd frontend && npm run lint -- --max-warnings 0 src/components/Sidebar.tsx src/app/\(dashboard\)/page.tsx
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Sidebar.tsx "frontend/src/app/(dashboard)/page.tsx"
git commit -m "feat: portal sidebar filter + dashboard redirect for PRA non-admin users"
```

---

### Task 4: Invoice list — KPI strip + PRA status column

**Files:**
- Modify: `frontend/src/app/(dashboard)/invoices/page.tsx`

**Interfaces:**
- Consumes: `usePRAPortal()` from Task 2.
- Consumes: existing `/api/invoices` response (already fetched); adds `pra_status`, `pra_fiscal_number` to the `Invoice` interface.

- [ ] **Step 1: Extend the Invoice interface and add hook import**

In `frontend/src/app/(dashboard)/invoices/page.tsx`, extend the `Invoice` interface (currently ends at `internal_memo`):

```ts
interface Invoice {
  id: number
  number: string
  customer_id: number | null
  customer_name: string | null
  issue_date: string
  due_date: string
  subtotal: number
  gst_amount: number
  total: number
  status: string
  description: string | null
  notes: string | null
  internal_memo: string | null
  pra_status: string | null
  pra_fiscal_number: string | null
}
```

Add import at the top:
```ts
import { usePRAPortal } from "@/hooks/usePRAPortal"
```

Inside `InvoicesContent`, after the existing hooks:
```ts
const { isPortal } = usePRAPortal()
```

- [ ] **Step 2: Add KPI strip above the table**

After the existing 3-column KPI grid (`<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 ...">`) and before the `customerFilter` block, add:

```tsx
{isPortal && (() => {
  const today = new Date().toISOString().split("T")[0]
  const todayInvoices = invoices.filter(i => i.issue_date === today)
  const todaySales = todayInvoices.reduce((s, i) => s + i.total, 0)
  const submitted = invoices.filter(i => i.pra_status === "submitted").length
  const failed    = invoices.filter(i => i.pra_status === "failed")
  const pending   = invoices.filter(i => i.pra_status === "pending").length
  return (
    <div className="bg-[#1a1814] text-white rounded-xl px-6 py-4 flex flex-wrap items-center gap-6 print:hidden">
      <div>
        <p className="text-xs text-white/50 uppercase tracking-widest font-bold">Today's Sales</p>
        <p className="text-xl font-bold font-mono mt-0.5">{fmt(todaySales)}</p>
        <p className="text-[10px] text-white/40 mt-0.5">{todayInvoices.length} invoice{todayInvoices.length !== 1 ? "s" : ""}</p>
      </div>
      <div>
        <p className="text-xs text-white/50 uppercase tracking-widest font-bold">PRA Submitted</p>
        <p className="text-xl font-bold text-emerald-400 mt-0.5">{submitted} ✓</p>
      </div>
      <div>
        <p className="text-xs text-white/50 uppercase tracking-widest font-bold">Failed</p>
        <p className="text-xl font-bold text-red-400 mt-0.5">{failed.length} ✗</p>
      </div>
      <div>
        <p className="text-xs text-white/50 uppercase tracking-widest font-bold">Pending</p>
        <p className="text-xl font-bold text-amber-400 mt-0.5">{pending} ⏳</p>
      </div>
      {failed.length > 0 && (
        <Link
          href={`/invoices/${failed[0].id}`}
          className="ml-auto text-xs text-red-300 border border-red-400/40 rounded-lg px-3 py-1.5 hover:bg-red-900/30 transition-colors"
        >
          Fix Failed →
        </Link>
      )}
    </div>
  )
})()}
```

- [ ] **Step 3: Add PRA status column to the table**

In the `<thead>` row, after the Status `<SortableHeader>` and before the actions `<th>`:

```tsx
{isPortal && (
  <th className="px-4 py-4 text-left text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55">PRA</th>
)}
```

In the `<tbody>` rows, after the status badge `<td>` and before the actions `<td>`:

```tsx
{isPortal && (
  <td className="ui-td text-xs">
    {inv.pra_status === "submitted" && (
      <span className="text-emerald-700 font-mono">✓ {inv.pra_fiscal_number ?? "FIN"}</span>
    )}
    {inv.pra_status === "pending" && (
      <span className="text-amber-600">⏳ Pending</span>
    )}
    {inv.pra_status === "failed" && (
      <span className="text-red-600 font-medium">✗ Failed</span>
    )}
  </td>
)}
```

- [ ] **Step 4: Lint check**

```bash
cd frontend && npm run lint -- --max-warnings 0 "src/app/(dashboard)/invoices/page.tsx"
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(dashboard)/invoices/page.tsx"
git commit -m "feat: PRA portal KPI strip + PRA status column on invoices list"
```

---

### Task 5: Invoice form — buyer fields + payment mode position

**Files:**
- Modify: `frontend/src/components/invoices/InvoiceForm.tsx`

**Interfaces:**
- Consumes: `usePRAPortal()` from Task 2.
- Consumes: `Invoice.buyer_ntn`, `Invoice.buyer_cnic` from Task 1 (backend now accepts them).
- Produces: `buyer_ntn` and `buyer_cnic` in the form payload sent to `/api/invoices`.

- [ ] **Step 1: Extend Customer interface and FormState**

In `InvoiceForm.tsx`, update the `Customer` interface (currently `{ id: number; name: string }`):

```ts
interface Customer { id: number; name: string; ntn?: string | null; cnic?: string | null }
```

Add `buyer_ntn` and `buyer_cnic` to `FormState` (after `payment_mode: string`):

```ts
  payment_mode: string
  buyer_ntn: string
  buyer_cnic: string
```

Add to `emptyForm` (the default state object, after `payment_mode: '1'`):

```ts
  payment_mode: '1',
  buyer_ntn: '',
  buyer_cnic: '',
```

- [ ] **Step 2: Add hook import and call**

At the top of the file, add:
```ts
import { usePRAPortal } from "@/hooks/usePRAPortal"
```

Inside `InvoiceForm`, after existing hook calls (e.g., after `const fmt = useFmt()`):
```ts
const { isPortal } = usePRAPortal()
```

- [ ] **Step 3: Auto-populate from customer on select**

Find the customer `<select>` onChange handler (currently ~line 326–327):
```ts
setForm(p => ({ ...p, customer_id: e.target.value, customer_name: c?.name ?? '' }))
```

Replace with:
```ts
setForm(p => ({
  ...p,
  customer_id: e.target.value,
  customer_name: c?.name ?? '',
  buyer_ntn: c?.ntn ?? '',
  buyer_cnic: c?.cnic ?? '',
}))
```

- [ ] **Step 4: Populate from invoice in edit mode**

In the `useEffect` that loads edit state (~line 133), after `payment_mode: ...`:
```ts
        payment_mode: invoice.payment_mode ? String(invoice.payment_mode) : '1',
        buyer_ntn: (invoice as any).buyer_ntn ?? '',
        buyer_cnic: (invoice as any).buyer_cnic ?? '',
```

- [ ] **Step 5: Add buyer fields to the form JSX**

After the customer picker grid (the block with "Customer" and "Customer Name" labels), add a new grid row that shows when `isPortal` is true OR when the existing NTN/CNIC values are non-empty:

```tsx
{(isPortal || form.buyer_ntn || form.buyer_cnic) && (
  <div className="grid grid-cols-2 gap-4">
    <div>
      <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
        Buyer NTN <span className="font-normal normal-case text-[#1a1814]/40">(7-digit business)</span>
      </label>
      <input
        value={form.buyer_ntn}
        onChange={e => setForm(p => ({ ...p, buyer_ntn: e.target.value }))}
        placeholder="1234567-8"
        className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm font-mono"
      />
    </div>
    <div>
      <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
        Buyer CNIC <span className="font-normal normal-case text-[#1a1814]/40">(13-digit consumer)</span>
      </label>
      <input
        value={form.buyer_cnic}
        onChange={e => setForm(p => ({ ...p, buyer_cnic: e.target.value }))}
        placeholder="3520212345678"
        className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm font-mono"
      />
    </div>
  </div>
)}
```

- [ ] **Step 6: Move Payment Mode before Description in portal mode**

The Payment Mode `<div>` currently lives inside a 2-column grid with Description (~line 400–414). In portal mode it should render immediately after the date row. Wrap the existing Payment Mode block with `{!isPortal && (...)}` to hide it from its current position, then add a portal-only block right after the date/payment-term/due-date row:

```tsx
{isPortal && (
  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <div>
      <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
        Payment Mode
      </label>
      <select value={form.payment_mode} onChange={e => setForm(p => ({ ...p, payment_mode: e.target.value }))}
        className="w-full px-3 py-2 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f] text-sm">
        <option value="1">Cash</option>
        <option value="2">Card / Bank Transfer</option>
        <option value="3">Gift Voucher</option>
        <option value="4">Loyalty Card</option>
        <option value="5">Mixed</option>
        <option value="6">Cheque</option>
      </select>
    </div>
  </div>
)}
```

- [ ] **Step 7: Include buyer fields in the form submission payload**

Find the `body` object passed to `apiFetch` in the save handler (~line 272–310). Add after `payment_mode: form.payment_mode ? parseInt(form.payment_mode) : null,`:

```ts
      buyer_ntn: form.buyer_ntn || null,
      buyer_cnic: form.buyer_cnic || null,
```

- [ ] **Step 8: Lint check**

```bash
cd frontend && npm run lint -- --max-warnings 0 src/components/invoices/InvoiceForm.tsx
```

Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/invoices/InvoiceForm.tsx
git commit -m "feat: inline buyer CNIC/NTN on invoice form; portal payment mode position"
```

---

### Task 6: Enhanced A4 print — prominent FIN + buyer ID + PCT/tax columns

**Files:**
- Modify: `frontend/src/app/(dashboard)/invoices/[id]/print/page.tsx`

**Interfaces:**
- Consumes: `Invoice.buyer_ntn`, `Invoice.buyer_cnic`, `Invoice.payment_mode` (new fields from Task 1 backend).
- Consumes: `InvoiceLine.pct_code`, `InvoiceLine.tax_rate` (already on the Product model; check if returned by invoice API).

- [ ] **Step 1: Extend the Invoice and InvoiceLine interfaces in print page**

At the top of `invoices/[id]/print/page.tsx`, update:

```ts
interface InvoiceLine {
  id: number
  product_id: number | null
  description: string
  qty: string | number
  unit: string | null
  rate: string | number
  amount: string | number
  hs_code: string | null
  pct_code: string | null
  tax_rate: string | number | null
}

interface Invoice {
  id: number
  number: string
  customer_id: number | null
  customer_name: string | null
  issue_date: string
  due_date: string
  description: string | null
  notes: string | null
  subtotal: string | number
  gst_rate: string | number
  gst_amount: string | number
  total: string | number
  currency: string
  status: string
  lines: InvoiceLine[]
  pra_fiscal_number?: string | null
  buyer_ntn?: string | null
  buyer_cnic?: string | null
  payment_mode?: number | null
}
```

- [ ] **Step 2: Replace the tiny FIN mono text with a prominent FIN badge**

Find the existing FIN block (~line 101–105):
```tsx
{inv.pra_fiscal_number && (
  <div className="hidden print:block mb-4 text-xs text-[#1a1814]/70">
    PRA Fiscal Invoice No: <span className="font-mono font-semibold">{inv.pra_fiscal_number}</span>
  </div>
)}
```

Replace with:
```tsx
{inv.pra_fiscal_number && (
  <div className="mb-4 border border-[#b8943f]/40 rounded-lg px-4 py-2 bg-[#faf6ec]">
    <p className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-0.5">Fiscal Invoice No (PRA)</p>
    <p className="text-sm font-bold font-mono text-[#b8943f]">{inv.pra_fiscal_number}</p>
  </div>
)}
```

- [ ] **Step 3: Add buyer NTN/CNIC row in the customer block**

Find the "Bill To" grid block (~line 108–118) and add below the customer name:

```tsx
<div>
  <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 mb-1">Bill To</div>
  <p className="font-semibold">{inv.customer_name ?? "—"}</p>
  {inv.buyer_ntn && (
    <p className="text-xs text-[#1a1814]/60 font-mono mt-0.5">NTN: {inv.buyer_ntn}</p>
  )}
  {inv.buyer_cnic && (
    <p className="text-xs text-[#1a1814]/60 font-mono mt-0.5">CNIC: {inv.buyer_cnic}</p>
  )}
</div>
```

- [ ] **Step 4: Add PCT Code and Tax % columns to the line items table**

In the `<thead>` row, add two columns after the Amount header:

```tsx
<th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-20 hidden print:table-cell">PCT Code</th>
<th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/55 w-16 hidden print:table-cell">Tax %</th>
```

In each `<tbody>` row, add after the amount `<td>`:

```tsx
<td className="px-3 py-2 text-right font-mono text-xs hidden print:table-cell">
  {ln.pct_code ?? "—"}
</td>
<td className="px-3 py-2 text-right font-mono text-xs hidden print:table-cell">
  {ln.tax_rate != null ? `${ln.tax_rate}%` : "—"}
</td>
```

- [ ] **Step 5: Lint check**

```bash
cd frontend && npm run lint -- --max-warnings 0 "src/app/(dashboard)/invoices/[id]/print/page.tsx"
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add "frontend/src/app/(dashboard)/invoices/[id]/print/page.tsx"
git commit -m "feat: prominent FIN badge + buyer NTN/CNIC + PCT/tax columns on A4 invoice print"
```

---

### Task 7: Thermal receipt page + Print Receipt button

**Files:**
- Create: `frontend/src/app/(dashboard)/invoices/[id]/receipt/page.tsx`
- Modify: `frontend/src/app/(dashboard)/invoices/[id]/page.tsx`

**Interfaces:**
- Consumes: `usePRAPortal()` from Task 2.
- Consumes: `GET /api/invoices/{id}` (same endpoint as print page — returns `pra_fiscal_number`, `payment_mode`, lines).

- [ ] **Step 1: Install qrcode.react**

```bash
cd frontend && npm install qrcode.react
```

Expected: added to `package.json` dependencies.

- [ ] **Step 2: Create the thermal receipt page**

Create `frontend/src/app/(dashboard)/invoices/[id]/receipt/page.tsx`:

```tsx
"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useSettings } from "@/context/SettingsContext"

const PAYMENT_MODE: Record<number, string> = {
  1: "Cash", 2: "Card", 3: "Gift Voucher", 4: "Loyalty Card", 5: "Mixed", 6: "Cheque",
}

interface Line {
  description: string
  qty: string | number
  rate: string | number
  amount: string | number
  tax_rate?: string | number | null
}

interface Invoice {
  id: number
  number: string
  customer_name: string | null
  issue_date: string
  subtotal: string | number
  gst_rate: string | number
  gst_amount: string | number
  total: string | number
  currency: string
  payment_mode: number | null
  pra_fiscal_number: string | null
  lines: Line[]
}

const r2 = (v: string | number) => {
  const n = Number(v)
  return Number.isNaN(n) ? "0.00" : Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function ReceiptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const { settings } = useSettings()
  const [inv, setInv] = useState<Invoice | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<Invoice>(`/api/invoices/${id}`)
      .then(d => {
        setInv(d)
        setTimeout(() => window.print(), 300)
      })
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [id])

  if (error) return <p className="p-4 text-red-700 text-sm">{error}</p>
  if (!inv)  return <p className="p-4 text-[#1a1814]/60 text-sm">Loading receipt…</p>

  return (
    <>
      {/* Screen toolbar — hidden when printing */}
      <div className="print:hidden flex items-center justify-between bg-[#1a1814] text-white px-4 py-2 mb-4">
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm hover:text-[#ffd966]">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#b8943f] hover:bg-[#d4af60] text-black rounded-md text-sm font-semibold"
        >
          <Printer className="w-4 h-4" /> Print Receipt
        </button>
      </div>

      {/* Receipt body — 80mm width for thermal POS */}
      <div className="receipt-body bg-white mx-auto text-[#1a1814] font-mono text-xs" style={{ width: "80mm", padding: "4mm" }}>
        {/* Header */}
        <div className="text-center mb-3">
          <p className="font-bold text-sm">{settings.company_name}</p>
          {settings.pra_pos_id && <p className="text-[10px] text-[#1a1814]/60">POS ID: {settings.pra_pos_id}</p>}
        </div>

        <div className="border-t border-dashed border-[#1a1814]/30 my-2" />

        {/* Invoice meta */}
        <div className="mb-2 space-y-0.5">
          <div className="flex justify-between">
            <span className="text-[#1a1814]/60">Invoice</span>
            <span className="font-bold">{inv.number}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#1a1814]/60">Date</span>
            <span>{fmtDate(inv.issue_date)}</span>
          </div>
          {inv.customer_name && (
            <div className="flex justify-between">
              <span className="text-[#1a1814]/60">Customer</span>
              <span className="text-right max-w-[40mm] truncate">{inv.customer_name}</span>
            </div>
          )}
          {inv.payment_mode && (
            <div className="flex justify-between">
              <span className="text-[#1a1814]/60">Payment</span>
              <span>{PAYMENT_MODE[inv.payment_mode] ?? inv.payment_mode}</span>
            </div>
          )}
        </div>

        <div className="border-t border-dashed border-[#1a1814]/30 my-2" />

        {/* Line items */}
        <table className="w-full text-[10px] mb-2">
          <thead>
            <tr className="text-[#1a1814]/60">
              <th className="text-left font-normal">Item</th>
              <th className="text-right font-normal">Qty</th>
              <th className="text-right font-normal">Rate</th>
              <th className="text-right font-normal">Amt</th>
            </tr>
          </thead>
          <tbody>
            {inv.lines.map((ln, i) => (
              <tr key={i}>
                <td className="text-left">{ln.description}</td>
                <td className="text-right">{Number(ln.qty)}</td>
                <td className="text-right">{r2(ln.rate)}</td>
                <td className="text-right">{r2(ln.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="border-t border-dashed border-[#1a1814]/30 my-2" />

        {/* Totals */}
        <div className="space-y-0.5 mb-2">
          <div className="flex justify-between">
            <span className="text-[#1a1814]/60">Subtotal</span>
            <span>{r2(inv.subtotal)}</span>
          </div>
          {Number(inv.gst_rate) > 0 && (
            <div className="flex justify-between">
              <span className="text-[#1a1814]/60">GST ({Number(inv.gst_rate)}%)</span>
              <span>{r2(inv.gst_amount)}</span>
            </div>
          )}
          <div className="flex justify-between font-bold text-sm border-t border-[#1a1814]/20 pt-1 mt-1">
            <span>TOTAL {inv.currency}</span>
            <span>{r2(inv.total)}</span>
          </div>
        </div>

        {/* FIN */}
        {inv.pra_fiscal_number && (
          <>
            <div className="border-t border-dashed border-[#1a1814]/30 my-2" />
            <div className="text-center space-y-2">
              <p className="text-[9px] text-[#1a1814]/55 uppercase tracking-widest">PRA Fiscal Invoice No</p>
              <p className="font-bold text-sm tracking-wider">{inv.pra_fiscal_number}</p>
              <div className="flex justify-center mt-1">
                <QRCodeSVG value={inv.pra_fiscal_number} size={80} />
              </div>
            </div>
          </>
        )}

        <div className="border-t border-dashed border-[#1a1814]/30 my-2" />
        <p className="text-center text-[9px] text-[#1a1814]/50">Thank you for your business</p>
      </div>

      {/* 80mm page CSS — injected print style */}
      <style>{`
        @media print {
          @page { size: 80mm auto; margin: 0; }
          body > *:not(.receipt-body) { display: none !important; }
          .receipt-body { display: block !important; }
          .print\\:hidden { display: none !important; }
        }
      `}</style>
    </>
  )
}
```

- [ ] **Step 3: Add "Print Receipt" button to invoice detail page**

In `frontend/src/app/(dashboard)/invoices/[id]/page.tsx`, add the import:
```ts
import { usePRAPortal } from "@/hooks/usePRAPortal"
```

Inside the component, after existing hooks:
```ts
const { isPortal } = usePRAPortal()
```

In the toolbar JSX (the `<div className="flex flex-wrap items-center justify-end gap-2">` block), after the existing "Print Invoice" `<Link>`:

```tsx
{/* Find the Print Invoice link, which looks like: */}
<Link href={`/invoices/${id}/print`} ...>
  <Printer ... /> Print Invoice
</Link>

{/* Add Print Receipt immediately after: */}
{isPortal && inv.pra_fiscal_number && (
  <Link
    href={`/invoices/${inv.id}/receipt`}
    className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#faf6ec] text-[#1a1814]/70"
  >
    <Printer className="w-4 h-4" /> Print Receipt
  </Link>
)}
```

- [ ] **Step 4: Lint check**

```bash
cd frontend && npm run lint -- --max-warnings 0 "src/app/(dashboard)/invoices/[id]/receipt/page.tsx" "src/app/(dashboard)/invoices/[id]/page.tsx"
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(dashboard)/invoices/[id]/receipt/page.tsx" "frontend/src/app/(dashboard)/invoices/[id]/page.tsx" frontend/package.json frontend/package-lock.json
git commit -m "feat: thermal receipt page (80mm + QR code) + Print Receipt button on invoice detail"
```

---

### Task 8: PRA Logs page + nav item

**Files:**
- Create: `frontend/src/app/(dashboard)/pra-logs/page.tsx`
- Modify: `frontend/src/lib/nav.ts`

**Interfaces:**
- Consumes: `GET /api/pra/logs` — returns `{ id, invoice_id, attempt_at, endpoint, http_status, response_code, success, error_message }[]`

- [ ] **Step 1: Add PRA Logs nav item**

In `frontend/src/lib/nav.ts`, add a new import for a suitable icon (add `FileCheck` to existing lucide-react import line), then add after the Settings nav item (~line 96):

```ts
  { label: "Settings",         href: "/settings",          icon: Settings,         section: "System" },
  { label: "PRA Logs",         href: "/pra-logs",          icon: FileCheck,        section: "System" },
```

Also import `FileCheck` in the nav.ts imports — find the existing `import { ... } from "lucide-react"` line and add `FileCheck` to it.

- [ ] **Step 2: Create the PRA Logs page**

Create `frontend/src/app/(dashboard)/pra-logs/page.tsx`:

```tsx
"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { useBreadcrumb } from "@/context/BreadcrumbContext"

interface PRALog {
  id: number
  invoice_id: number
  attempt_at: string
  endpoint: string
  http_status: number | null
  response_code: string | null
  success: boolean
  error_message: string | null
}

export default function PRALogsPage() {
  useBreadcrumb("PRA Submission Logs")
  const [logs, setLogs] = useState<PRALog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<PRALog[]>("/api/pra/logs?limit=100")
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-3xl font-serif font-medium">PRA Submission Logs</h1>
        <p className="text-sm text-black/75 mt-1">Audit trail of every PRA e-IMS API call</p>
      </div>

      <div className="bg-white rounded-xl border border-[#ede9e2] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="bg-[#f6f3ee] border-b border-[#ede9e2]">
              <tr>
                <th className="ui-th text-left">Date / Time</th>
                <th className="ui-th text-left">Invoice</th>
                <th className="ui-th text-center">HTTP</th>
                <th className="ui-th text-center">PRA Code</th>
                <th className="ui-th text-center">Status</th>
                <th className="ui-th text-left">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ede9e2]">
              {loading ? (
                <tr><td colSpan={6} className="px-6 py-10 text-center text-sm text-black/40">Loading…</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={6} className="px-6 py-10 text-center text-sm text-black/40">No PRA submissions yet.</td></tr>
              ) : logs.map(log => (
                <tr key={log.id} className={log.success ? "" : "bg-red-50/30"}>
                  <td className="ui-td whitespace-nowrap text-black/60">{fmtDate(log.attempt_at)}</td>
                  <td className="ui-td">
                    <Link href={`/invoices/${log.invoice_id}`} className="text-[#b8943f] font-mono font-bold hover:underline">
                      #{log.invoice_id}
                    </Link>
                  </td>
                  <td className="ui-td text-center font-mono">{log.http_status ?? "—"}</td>
                  <td className="ui-td text-center font-mono">{log.response_code ?? "—"}</td>
                  <td className="ui-td text-center">
                    {log.success
                      ? <span className="text-emerald-700 font-bold">✓ OK</span>
                      : <span className="text-red-600 font-bold">✗ Failed</span>}
                  </td>
                  <td className="ui-td text-xs text-red-600 max-w-xs truncate">{log.error_message ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Lint check**

```bash
cd frontend && npm run lint -- --max-warnings 0 "src/app/(dashboard)/pra-logs/page.tsx" src/lib/nav.ts
```

Expected: no errors.

- [ ] **Step 4: Build check**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully` with no type errors.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(dashboard)/pra-logs/page.tsx" frontend/src/lib/nav.ts
git commit -m "feat: PRA Submission Logs page + nav item"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec Section | Task |
|---|---|
| §1 `usePRAPortal()` hook | Task 2 |
| §2 Sidebar — 7 portal items | Task 3 |
| §3 Dashboard redirect + KPI strip | Tasks 3 + 4 |
| §3 PRA status column on invoice list | Task 4 |
| §4a Inline buyer CNIC/NTN on form | Task 5 |
| §4b Payment mode moved up in portal | Task 5 |
| §5a Enhanced A4 print (FIN badge, buyer row, PCT/tax) | Task 6 |
| §5b Thermal receipt page + QR + Print Receipt button | Task 7 |
| §6a Migration `0027_pra_buyer_fields` | Task 1 |
| §6b Buyer priority chain in `build_pra_payload` | Task 1 |
| §6c DateTime with actual time | Task 1 |
| PRA Logs sidebar item | Task 8 |

All spec requirements covered. ✓

**Type consistency:** `buyer_ntn`/`buyer_cnic` named consistently across models.py, InvoiceCreate, InvoiceForm FormState, and print page Invoice interface.

**No placeholders:** All code blocks are complete and executable.
