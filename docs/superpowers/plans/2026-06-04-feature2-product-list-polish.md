# Feature 2: Product List Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the `/products` list view, add a Category column, rename "Default Rate" → "Selling Price", and add a read-only "Cost Price" column showing live `avg_cost`.

**Architecture:** Frontend-only. `GET /api/products` already returns raw `Product` rows (so `avg_cost` and `category_id` are already in the JSON). We extend the `Product` TS interface, reuse the existing flat-category map for labels, and add two columns.

**Tech Stack:** Next.js 16 / React 19 / TypeScript.

---

### Task 1: Surface `avg_cost` and category label on the product row

**Files:**
- Modify: `frontend/src/app/(dashboard)/products/page.tsx`

- [ ] **Step 1: Read Next.js 16 guidance**

Run: `ls frontend/node_modules/next/dist/docs/` and heed `frontend/AGENTS.md`. (No new APIs needed; this is a table edit.)

- [ ] **Step 2: Extend the `Product` interface**

In `products/page.tsx` add `avg_cost: number` to the `Product` interface (after `default_rate`, line ~23). `category_id` is already present.

- [ ] **Step 3: Add a category-label resolver**

The flat category map is already built at lines ~243-249 as `allCatsFlat` ( `{ id, label }` ). Add a lookup helper just after it:

```tsx
const catLabel = (id: number | null) =>
  id == null ? '—' : (allCatsFlat.find(c => c.id === id)?.label ?? '—')
```

- [ ] **Step 4: Update the list header row**

In the `<thead>` (lines ~364-371): add a Category header after "Name", and rename "Default Rate" → "Selling Price", and add a "Cost Price" header after it:

```tsx
<th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Category</th>
```
(insert after the Name `<th>`)

Change the Default Rate header text to `Selling Price`. Immediately after it add:

```tsx
<th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-widest text-black/60">Cost Price</th>
```

- [ ] **Step 5: Update the body cells (and colSpan counts)**

In each product `<tr>` (lines ~389-427): after the Name cell add:

```tsx
<td className="px-6 py-4 text-black/60 text-xs">{catLabel(p.category_id)}</td>
```

After the (renamed) Selling Price cell (the `fmt(p.default_rate)` cell, line ~414) add a Cost Price cell:

```tsx
<td className="px-6 py-4 text-right font-mono text-black/70">
  {p.product_type === 'stock' ? fmt(p.avg_cost) : <span className="text-black/30">—</span>}
</td>
```

Update the two `colSpan` values (currently `9`) in the loading skeleton (line ~376) and empty-state row (line ~379) to `11` (two columns added).

- [ ] **Step 6: Rename the form label**

In the Add/Edit modal, change the "Default Rate" label (line ~517) text to `Selling Price`. The field key stays `default_rate`.

- [ ] **Step 7: Add Cost Price to CSV export (optional consistency)**

In the `downloadCSV` mapper (lines ~280-283), rename `Rate: p.default_rate` to `'Selling Price': p.default_rate` and add `'Cost Price': p.avg_cost, Category: catLabel(p.category_id)`.

- [ ] **Step 8: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors (watch for unused-var or colSpan mismatch warnings).

- [ ] **Step 9: Manual smoke check**

Open `/products`: stock items show a Category, a Selling Price, and a Cost Price (avg cost); service items show `—` for Cost Price. The Add/Edit form label reads "Selling Price".

- [ ] **Step 10: Commit**

```bash
git add "frontend/src/app/(dashboard)/products/page.tsx"
git commit -m "feat(products): add Category + Cost Price columns, rename Default Rate to Selling Price"
```

---

## Self-Review Notes
- Spec Feature 2 fully covered: Category column (Step 5), rename (Steps 4 & 6), Cost Price = live `avg_cost`, read-only, `—` for services (Step 5).
- No backend change needed — `GET /api/products` returns raw `Product` objects, so `avg_cost`/`category_id` already serialize.
- colSpan updates (Step 5) are the easy-to-miss bug; called out explicitly.
