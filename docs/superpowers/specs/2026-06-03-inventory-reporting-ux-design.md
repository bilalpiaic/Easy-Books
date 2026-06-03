# Inventory-Reporting UX Enhancements — Design

**Date:** 2026-06-03
**Branch:** `feature/inventory-reporting-ux`
**Status:** Approved (design)

## Summary

Three enhancements to the inventory reporting surface, all driven by user request:

1. **Cross-navigation hyperlinks** between Inventory Performance and Product Ledger.
2. **Location column** in the Product Ledger (which store each movement hit).
3. **"Product COA"** — a new Products-section page presenting products as a
   **Main → Sub → Item** tree (parent category → sub-category → product) with
   **Qty / Avg Rate / Value** and rolled-up subtotals, modeled on the Chart of
   Accounts page but for products.

## F1 — Cross-navigation hyperlinks

- **Inventory Performance** (`inventory/performance/page.tsx`): product name → link to
  `/products/ledger?product=<id>`.
- **Product Ledger** (`products/ledger/page.tsx`): read `product` from the URL via
  `useSearchParams()` on mount and pre-select it. **Next.js 16:** `useSearchParams()`
  must sit inside a `<Suspense>` boundary — split into a thin page wrapper rendering
  `<Suspense><LedgerInner/></Suspense>`.
- **Product COA** items also link into the ledger.

## F2 — Location column in Product Ledger

- **Backend** `GET /api/reports/product-ledger`: add `location` (store name) to each item.
  Resolve per movement — IN directions (`_IN_DIRECTIONS`) use `to_location_id`, OUT use
  `from_location_id` — against a `{location_id: name}` map built once per request from
  `StockLocation` (no N+1). Empty string when unresolved.
- **Frontend:** add a **Location** column to the ledger table. The existing
  store/location filter dropdown is unchanged.

## F3 — Product COA

- **Backend** new report `GET /api/reports/product-coa`:
  ```json
  { "groups": [ { "name": "Goods", "qty": 0, "value": 0,
        "subs": [ { "name": "Imported", "qty": 0, "value": 0,
            "items": [ { "id": 1, "code": "SKU-1", "name": "Widget",
                         "qty": 10, "avg_rate": 5, "value": 50 } ] } ] } ],
    "grand": { "qty": 0, "value": 0 } }
  ```
  - **Main** = parent `ProductCategory`; **Sub** = sub-category; **Item** = product.
  - `qty` = `Product.stock_qty`, `avg_rate` = `Product.avg_cost`, `value` = qty × avg_cost.
  - Products with no category → **"Uncategorized"** Main group; products whose category is
    a parent (no sub) → a `"—"` sub bucket.
  - Subtotals roll Item → Sub → Main → grand. Tenant-filtered.
- **Frontend** `products/coa/page.tsx`: indented tree table — Main row (bold, subtotal),
  Sub row (subtotal), Item rows with Qty / Avg Rate / Value; grand-total footer; print +
  CSV buttons consistent with the other reports. Item names link to the ledger (F1).
- **Sidebar** (`Sidebar.tsx`): add **"Product COA"** to the Inventory group, next to
  Product Categories.

## Testing

- Backend `tests/test_product_coa.py`: tree shape, subtotal rollups, uncategorized bucket,
  valuation math, tenant isolation.
- Extend `tests/test_reports_new.py` (or product-ledger test) to assert each ledger item
  carries a `location` field.
- Frontend: `npm run lint && npm run build` clean (incl. the Suspense boundary).

## Out of scope

- Per-location quantity *valuation* in Product COA (location appears in the ledger only).
- Editing categories/accounts from the Product COA page (read-only report).
