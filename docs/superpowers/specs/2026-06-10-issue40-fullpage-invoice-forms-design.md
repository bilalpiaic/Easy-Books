# #40 — Full-page data-entry forms (Pilot: Invoices)

_Design — 2026-06-10 · against `main` @ v2.5.0_

## Problem

Create/edit forms for transaction and master-data records are rendered as
**modals embedded inside their list pages**. For invoices, the entire form
(state, dropdown loading, validation, posted-edit guard, submit) lives inline in
`frontend/src/app/(dashboard)/invoices/page.tsx` (~750 lines, modal at lines
542–730). This couples three concerns — list rendering, data fetching, and the
full create/edit form — in one file, and gives data entry a cramped modal
surface.

Issue #40 (= #52 §5) calls for **full-page** create/edit forms instead of
modals, across the named set: invoices, bills, payments-received,
bill-payments, products, customers, vendors. (JV entry is already full-page.)

## Scope of this spec

**Invoices only** — the reference pattern. Once approved and merged, the same
shape is mechanically replicated to the other six named forms in follow-up
batches (each its own plan). This spec does **not** cover those.

Out of scope: the other 13 modal pages; any API/backend change; redesign of the
form's fields or the `LineItemsTable`.

## Architecture

Five units, four well-defined boundaries.

### 1. `components/invoices/InvoiceForm.tsx` (new — the extracted unit)

Self-contained create/edit form. **Knows nothing about routing or the list.**

- **Props**
  - `mode: 'create' | 'edit'`
  - `invoice?: Invoice` — initial data, required when `mode === 'edit'`
  - `onSaved: (id: number) => void` — called with the saved invoice id
  - `onCancel: () => void`
- **Owns** (lifted verbatim from the current modal):
  - form field state + line-item state
  - dropdown data loading (today's `loadModalData`: customers, products,
    accounts) on mount
  - client-side validation + the `formError` banner
  - the posted-edit **block-if-paid** confirmation flow (`confirmPostedEdit`)
  - submit: `POST /api/invoices` (create) or `PUT /api/invoices/{id}` (edit),
    then `onSaved(id)`
- **Depends on:** `apiFetch`, `useSettings`, `LineItemsTable`,
  `lib/voucherTypes` (existing imports).

### 2. `app/(dashboard)/invoices/new/page.tsx` (new route)

Thin page shell: page header ("New Invoice") + back-to-list link, rendering:

```tsx
<InvoiceForm
  mode="create"
  onSaved={(id) => router.push(`/invoices/${id}`)}
  onCancel={() => router.push('/invoices')}
/>
```

### 3. `app/(dashboard)/invoices/[id]/edit/page.tsx` (new route)

Fetches the invoice by id (`GET /api/invoices/{id}`), shows a skeleton while
loading, then renders `<InvoiceForm mode="edit" invoice={data} ... />` with the
same `onSaved`/`onCancel` as create. A missing invoice (404) → toast + redirect
to `/invoices`.

### 4. `app/(dashboard)/invoices/page.tsx` (list — slimmed)

- Delete the modal (lines ~542–730), the form state, `loadModalData`, and
  `handleSave`.
- "New Invoice" button → `router.push('/invoices/new')`.
- Row "Edit" action → `router.push('/invoices/${id}/edit')`.
- Remains a pure list (fetch + table + filters + pagination). Expected to shrink
  ~200 lines.

### 5. `app/(dashboard)/invoices/[id]/page.tsx` (detail — augmented)

Add an "Edit" button → `/invoices/[id]/edit`.

## Data flow

- **Create:** `/invoices/new` mounts `InvoiceForm` → loads dropdowns → user
  submits → POST → `onSaved(id)` → `router.push('/invoices/{id}')` (detail).
- **Edit:** `/invoices/[id]/edit` fetches invoice → seeds `InvoiceForm` →
  user submits → PUT → `onSaved(id)` → detail.
- **Cancel** (either mode): `onCancel` → back to list.

## Error handling & edge cases

- **Posted-edit guard:** the existing block-if-paid confirmation moves into
  `InvoiceForm` unchanged — editing a paid/posted invoice still blocks.
- **Edit route load failure / unknown id:** skeleton during fetch; on 404 or
  error, redirect to `/invoices` with a toast.
- **Submit error:** the existing `formError` banner inside `InvoiceForm`
  (no behavior change).

## Testing & verification

Pure frontend (no API change), so verification is build + manual smoke:

1. `npm run build` — clean.
2. `npm run lint` — clean.
3. Manual click-through:
   - Create a draft invoice → lands on its detail page.
   - Edit that draft → change a line → save → detail reflects it.
   - Attempt to edit a paid/posted invoice → block-if-paid confirmation fires.
   - Cancel from both `new` and `edit` → returns to list.

## Replication note (future batches, not this spec)

The same five-unit shape (`components/<entity>/<Entity>Form.tsx` +
`<entity>/new` + `<entity>/[id]/edit` + slimmed list + detail "Edit" button)
applies to bills, payments-received, bill-payments, products, customers, and
vendors. Each is a separate plan once this pilot lands.
