# Purchase Demand + Comparative Statement — Phase 1 Design (#137)

**Date:** 2026-07-03
**Issue:** #137 (Purchase/Store module) — Phase 1 of 4
**Status:** Approved design, pending implementation plan

## Goal

Add the front half of the procure-to-pay chain — **Purchase Demand → Vendor Quotations → Comparative Statement → PO** — as the first slice of the installable `purchase_store` module. Phase 1 delivers real internal control (segregation of duties, lowest-or-justify, chain enforcement), not just record-keeping. All Phase 1 documents are memo documents: **zero GL impact**.

Later phases (not this spec): Gate Inward + GRN linkage (2), Store Issue + GL (3), vendor analysis + seeder (4).

## Locked decisions

| Decision | Choice |
|---|---|
| Chain enforcement | Setting `require_purchase_chain` (default **on** when module installed): PO creation requires an approved CS. Toggleable per tenant in Settings. |
| Approval model | Single-step `draft → approved`; **approver ≠ creator enforced** (400 on self-approve); `approved_by_id` + `approved_at` recorded. |
| CS → PO | `POST /api/comparatives/{id}/convert-to-po` creates an **editable draft PO** pre-filled from the winning quotation (mirrors PO `convert-to-bill` idiom). |
| Department attribution | Optional `analytic_account_id` FK on the demand (reuses AnalyticAccount, #79). |
| Module packaging | `purchase_store` registered in Phase 1; new **Purchases** nav section absorbs existing PO + GRN pages when installed (dual-home via new `notForModule` nav flag). |

## Data model

All tables tenant-scoped with `tenant_id` FK + index; voucher numbers unique per tenant via `next_number()`; `Money`/`money_col()` for amounts; status guarded by `CheckConstraint` (mirroring `PurchaseOrder`).

### PurchaseDemand (`PD-YYYY-seq`)

| Field | Type | Notes |
|---|---|---|
| `number` | str | `PD-YYYY-seq`, unique per tenant |
| `demand_date` | str | ISO date |
| `required_by` | str? | ISO date |
| `analytic_account_id` | int? FK | requesting department / cost center |
| `purpose` | str? | why it's needed |
| `notes` | str? | |
| `status` | str | `draft \| approved \| converted \| closed \| cancelled` |
| `created_by_id` | int FK user | requester |
| `approved_by_id` / `approved_at` | int? / datetime? | set on approve |

**PurchaseDemandLine:** `demand_id` (CASCADE), `product_id?`, `description`, `qty`, `unit?`.
**No rate fields** — demands are quantity documents; requesters never set prices (control).

### VendorQuotation (`VQ-YYYY-seq`)

`demand_id` FK, `vendor_id` FK (**required**, validated against tenant), `quote_date`, `valid_until?`, `delivery_terms?`, `payment_terms?`, `notes?`, `created_at`.

**VendorQuotationLine:** `quotation_id` (CASCADE), `demand_line_id` FK (ties each rate to a demand line), `rate`, `qty` (defaults from demand line), `amount = qty × rate`.

Quotation total = Σ line amounts (computed, used by the lowest-or-justify rule).

### ComparativeStatement (`CS-YYYY-seq`)

One per demand (`UniqueConstraint(tenant_id, demand_id)`). Fields: `demand_id`, `cs_date`, `selected_quotation_id?`, `justification?`, `status` (`draft | approved | converted | cancelled`), `created_by_id`, `approved_by_id`, `approved_at`, `po_id?` (set on convert).

### PurchaseOrder changes

Two nullable columns: `demand_id`, `comparative_id`. Alembic migration; FK lines stripped for SQLite ALTER per repo convention; new tables get `bind.dialect.has_table(...)` guards.

## Workflow rules

1. **Demand approve** — `PATCH /api/purchase-demands/{id}/approve` (admin+): only from `draft`; rejects `user.id == created_by_id` with 400 "A demand cannot be approved by its creator"; audit-logged.
2. **Quotations** — only attachable to an **approved** demand; CRUD blocked once the demand's CS is approved.
3. **CS approve** — requires `selected_quotation_id` set and ≥1 quotation on the demand. **Lowest-or-justify:** if quotation count < 2 **or** selected quotation total is not the lowest, `justification` is mandatory (400 without it). Approver ≠ creator, same as demands.
4. **Convert** — `POST /api/comparatives/{id}/convert-to-po` (CS must be `approved`): creates **draft** PO with vendor + lines from the winning quotation (description/qty/unit from demand lines, rates from quotation lines), sets `po.demand_id`/`po.comparative_id`, CS → `converted`, demand → `converted`. PO then follows its normal approve/bill lifecycle.
5. **Chain enforcement** — in `create_po`: if `purchase_store` installed for the tenant **and** setting `require_purchase_chain` is on **and** `comparative_id` is absent → 400 "This tenant requires purchases to go through Demand → Comparative approval". Setting stored in the Settings KV (backend `SettingsUpdate` + `SettingsContext` + a toggle on the Settings page), default `true`.
6. **Cancel/close** — demands cancellable while `draft|approved` (not after convert); `closed` reserved for demands fulfilled without conversion.

## Permissions & module registration

- `PERMISSION_RESOURCES` += `purchase.demand`, `purchase.comparative` (quotations ride on `purchase.comparative`). Routers wired with `perm_dep()`; `apply_own_filter` honors `my_data_only` on demand listing.
- `MODULE_REGISTRY` += `purchase_store`: label "Purchases & Store", category **Operations**, icon `ShoppingCart`, deps `["inventory"]`, `always: False`, tier `free`, `nav_sections: ["Purchases"]`. `MODULES_BY_MODEL`: appended for `manufacturing`.
- Uninstall blocked while any PD/VQ/CS documents exist (mirrors existing dependency checks).

## Backend surface

New routers (mounted in `main.py`):

| Router | Endpoints |
|---|---|
| `routers/purchase_demands.py` | `GET /api/purchase-demands` (filters: status, department), `GET/{id}`, `POST`, `PUT/{id}` (draft only), `PATCH/{id}/approve`, `PATCH/{id}/cancel`, `PATCH/{id}/close` |
| `routers/quotations.py` | `GET /api/quotations?demand_id=`, `GET/{id}`, `POST`, `PUT/{id}`, `DELETE/{id}` (all blocked once CS approved) |
| `routers/comparatives.py` | `GET /api/comparatives`, `GET/{id}` (returns demand lines × quotations matrix), `POST`, `PUT/{id}` (draft only), `PATCH/{id}/approve`, `POST/{id}/convert-to-po` |

All follow existing conventions: `SessionDep`, `perm_dep`, `next_number()`, `log_audit`, tenant filter on every query.

## Frontend

New **Purchases** section in `nav.ts` (`forModule: "purchase_store"`):

| Page | Route | Notes |
|---|---|---|
| Demands list | `/purchases/demands` | status filter chips, `.table-freeze` |
| New/Edit demand | `/purchases/demands/new`, `/purchases/demands/[id]/edit` | full-page form (#40 pattern); product picker (free-text allowed), analytic-account picker |
| Demand detail | `/purchases/demands/[id]` | lines, quotations received, CS status, action buttons |
| Quotation entry | `/purchases/demands/[id]/quotations/new` | per-vendor rates against demand lines |
| Comparatives list | `/purchases/comparatives` | |
| Comparative builder | `/purchases/comparatives/[id]` | **matrix: demand lines × vendors**, lowest rate per line highlighted, totals row, winner selection, justification field shown when required |

- **Nav extension:** add `notForModule?: string` to nav items (hide when that module IS installed) — the inverse of `forModule`. Existing PO + GRN entries get `notForModule: "purchase_store"` in their current sections plus duplicates in Purchases with `forModule: "purchase_store"`.
- Print templates for PD and CS: portrait, `PrintHeader`, `fmtDate`, no type badges.
- Settings page: "Require purchase chain (Demand → Comparative → PO)" toggle, visible when module installed.

## Testing

`backend/tests/test_purchase_flow.py`:

- Full lifecycle: create demand → approve (different user) → 2 quotations → CS select lowest → approve → convert → draft PO with correct vendor/lines/rates/links.
- Self-approval rejected on demand and CS (400).
- Lowest-or-justify: selecting the higher quote without justification → 400; with justification → ok; single-quote CS without justification → 400.
- Chain enforcement: bare `POST /api/purchase-orders` 400s when module installed + setting on; succeeds when setting off or module not installed.
- Quotation edit blocked after CS approval; demand edit blocked after approval.
- Tenant isolation on all list/get endpoints; permission matrix (`purchase.demand` = none blocks listing).

## Out of scope (later phases)

Gate Inward, Store Issue, GL postings, 3-way match and other reports, hub page, vendor performance, demo seeder. Docs delta (README/BLUEPRINT/WORKFLOW/CLAUDE.md) ships with the Phase 1 PR but is written at the end.
