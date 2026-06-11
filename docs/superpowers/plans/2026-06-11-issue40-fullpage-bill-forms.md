# Plan — #40 Full-page Bill Forms (replication of invoice pilot)

**Branch:** `feature/issue40-fullpage-bill-forms`
**Pattern source:** merged invoice pilot (`components/invoices/InvoiceForm.tsx`, `invoices/new`, `invoices/[id]/edit`).

Mechanical replication of the approved invoice full-page-form architecture to bills. Same 5 units. Field-shape deltas: customer→vendor, issue_date→bill_date, AR(Asset)→AP(Liability), revenue→expense, `priceKind="sale"`+`warnOversell`→`priceKind="purchase"` (no oversell warning), no vendor-balance lookup (bills modal never had one — faithful extraction).

## Units
1. **`components/bills/BillForm.tsx`** (new) — extract the bills modal body into a routing-agnostic component. Props `{ mode, bill?, onSaved, onCancel }`; export `BillFull`. Owns form state, dropdown loading (vendors/accounts/products/payment-terms/tax-codes), totals, posted-edit guard (`mode==='edit' && bill.status!=='draft'`), submit (POST→`onSaved(created.id)`, PUT→`onSaved(bill.id)`). Cancel resets `confirmPostedEdit`. Container `max-w-3xl mx-auto`.
2. **`bills/new/page.tsx`** (new) — back-link + `<BillForm mode="create" onSaved={id=>push(/bills/${id})} onCancel={push(/bills)} />`.
3. **`bills/[id]/edit/page.tsx`** (new) — async `use(params)`, fetch `/api/bills/${id}` into `BillFull`, on fail `router.replace('/bills')`, render `<BillForm mode="edit" bill={bill} ... />`.
4. **`bills/page.tsx`** (slim) — drop modal + all form state/logic; `openCreate=()=>router.push('/bills/new')`; row Edit → `router.push(/bills/${b.id}/edit)`; collapse `Suspense`/`BillsInner` split (no more `useSearchParams`). Retain load/sort/filter/paginate/cards/aging/bulk/status/CSV/kbd.
5. **`bills/[id]/page.tsx`** (1 line) — Edit link `/bills?edit=${id}` → `/bills/${id}/edit`.

## Verify
`cd frontend && npm run build && npm run lint` — changed files lint-clean; only the 5 bills files differ from main.
