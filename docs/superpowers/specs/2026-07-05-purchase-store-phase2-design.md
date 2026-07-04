# Purchase/Store Module — Phase 2: Gate Inward (#137)

**Date:** 2026-07-05
**Status:** Approved design
**Prior art:** Phase 1 (PR #139, merge `a3db65b`) — Demand (PD) → Vendor Quotation (VQ) → Comparative Statement (CS) → PO. Spec: `2026-07-03-purchase-demand-comparative-design.md`.

## Scope

Phase 2 adds the **Gate Inward (GI)** control document between PO approval and
billing, two audit reports (Gate Register, 3-Way Match), and lands the three
Phase-1 carry-ins (uninstall guards, tenant-filter hardening, module copy).

**Key architectural finding that shaped this design:** issue #137 assumed a
purchase GRN exists ("GRN (exists, link to GI)"). It does not — the existing
`GoodsReceiptNote` is *customer-custodial* receiving for manufacturing.
Purchased stock enters inventory at **bill posting**
(`services/inventory.py::receive_stock`, `source_doc_type="bill"`).

**Decision (locked): Gate Inward → Bill model.** GI is a memo gate-register
document referencing the PO; billing requires GI coverage. Stock continues to
arrive at bill posting — no accounting change, no GRNI accrual account. The
3-way match is PO vs GI vs Bill. A true purchase-GRN with GRNI accrual remains
possible later without conflicting with this design.

Other locked decisions:
- **GI carries lines** (per PO line qty), pre-filled from the PO — enables
  per-item billed-qty caps and a per-item 3-way match.
- **New `require_gate_inward` setting**, default on, independent of
  `require_purchase_chain`.
- Phase-1 control invariants continue to apply (approver ≠ creator etc. are
  unchanged; GI has no approval step — its control is append-only + caps).

## Data model (Alembic migration 0030, `has_table` guard)

### `GateInward`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `tenant_id` | FK tenant, indexed | |
| `number` | str, indexed | `GI-YYYY-seq` via `SequenceCounter`; unique per tenant |
| `po_id` | FK purchaseorder, required | GI is always against a PO |
| `gate_date` | str (ISO date) | |
| `time_in` | str, optional | HH:MM |
| `vehicle_no` | str, optional | |
| `challan_no` | str, optional | challan / bilty number |
| `remarks` | str, optional | |
| `status` | str | `open` → `billed`; `cancelled` |
| `cancel_reason` | str, optional | required on cancel |
| `created_by_id` | FK user | recorder (gate/security user) |
| `created_at` | datetime | |

CheckConstraint: `status IN ('open','billed','cancelled')`.
Memo document — **no GL posting, no stock movement**.

### `GateInwardLine`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `gate_inward_id` | FK gateinward, cascade delete | |
| `po_line_id` | FK purchaseorderline | which PO line this receipt covers |
| `product_id` | FK product, optional | denormalized from the PO line |
| `qty_received` | Money | CheckConstraint qty_received > 0 |

## Rules & state machine

1. **Create** — PO must belong to the tenant and be `approved` or `received`
   (not `draft`/`billed`/`cancelled`). Every `po_line_id` must belong to that
   PO. Multiple GIs per PO are allowed (partial deliveries).
2. **Qty cap** — per PO line: Σ `qty_received` across non-cancelled GI lines
   ≤ PO line `qty`. Violation → 400 (the gate cannot wave in more than was
   ordered).
3. **PO `received` status** — after each GI create/cancel, recompute coverage:
   if every PO line is fully covered, PO status ← `received`; if coverage
   drops below full (a GI was cancelled), status reverts to `approved`.
   (The `received` value already exists in `ck_po_status` — previously unused.)
4. **Billing gate** — `POST /purchase-orders/{id}/convert-to-bill` blocks with
   400 when the module is installed, `require_gate_inward` is not `"false"`,
   and any PO line is not fully covered by non-cancelled GI lines. Setting
   off → conversion behaves as today.
5. **On conversion** — all the PO's `open` GIs flip to `billed`.
6. **Append-only** — a GI is never edited after creation (no PUT). It can be
   **cancelled** (with a required reason, audit-logged) only while its PO is
   unbilled. Once the PO is billed, its GIs are immutable. No hard delete,
   ever.

## Enforcement setting

`require_gate_inward` — same convention as `require_purchase_chain`:
stored in `Settings`, treated as on unless literally `"false"`, exposed in
the Settings page only when `purchase_store` is installed, positioned next
to the existing chain toggle.

## Permissions

New resource `purchase.gate` in `PERMISSION_RESOURCES` (category Purchases).
`routers/gate_inward.py` guarded by `perm_dep("purchase.gate", ...)`;
`apply_own_filter` honored on the list endpoint (`my_data_only` ⇒ a gate user
sees only entries they recorded). Reports require `purchase.gate` view (gate
register) and `purchase.comparative` view (3-way match).

## API surface

`routers/gate_inward.py` (mounted `/api/gate-inwards`):
- `GET /` — list; filters `po_id`, `status`, pagination; own-filter applied
- `GET /{id}` — detail with lines + PO/vendor context
- `POST /` — create (rules 1–3)
- `PATCH /{id}/cancel` — body `{reason}` (rule 6)

`routers/purchase_reports.py` (mounted `/api/purchase-reports`):
- `GET /gate-register?start=&end=&q=` — GI register; `q` matches vehicle or
  challan; returns per-entry rows incl. PO#, vendor, line summary, recorder
- `GET /three-way-match?start=&end=` — one row per PO line for POs with any
  GI or bill: PO qty/rate/amount, Σ GI qty, bill qty/amount, qty & amount
  variances, `flag` boolean when any variance ≠ 0

`routers/purchase_orders.py` changes: billing gate (rule 4), GI status flip
(rule 5), GI coverage summary included in `GET /{id}` response.

## Frontend

Pages (full-page routes, #40 pattern; all `forModule: "purchase_store"`):
- `/purchases/gate-inward` — list
- `/purchases/gate-inward/new?po=<id>` — form: PO picker (approved/received
  POs), lines pre-filled with remaining (uncovered) qty per line, vehicle /
  challan / time-in fields
- `/purchases/gate-inward/[id]` — detail + portrait print
- `/purchases/gate-register` — report, landscape print, `.table-freeze`
- `/purchases/three-way-match` — report, landscape print, `.table-freeze`,
  variance rows highlighted (badge-free in print)

Existing-page changes:
- PO detail: GI coverage indicator + "Record Gate Inward" button; the
  convert-to-bill button disabled with tooltip while coverage is incomplete
  and enforcement is on.
- Settings: `require_gate_inward` toggle.

**Nav checklist (hard requirement — regression from 2026-07-05):** every new
route must be added to BOTH `NAV` (sidebar registry) and `SUB_NAV` +
`SECTION_PREFIXES` (live TopNav) in `frontend/src/lib/nav.ts`.

## Phase-1 carry-ins (in scope)

1. **Uninstall guards** — generic `MODULE_UNINSTALL_GUARDS: dict[str, Callable
   [[Session, int], dict[str, int]]]` in `routers/modules.py`; uninstall
   endpoint consults it and returns 400 listing blocking document counts.
   `purchase_store` guard counts demands, quotations, comparatives, GIs.
2. **Tenant-filter hardening** — explicit `tenant_id` predicates on
   quotations `_validate_and_write_lines` and comparatives `_quote_totals` +
   approve-completeness subqueries (transitively safe today; make it local).
3. **Module copy** — `MODULE_REGISTRY["purchase_store"].description` updated:
   gate inward shipped, store issues still upcoming.

## Testing

`tests/test_gate_inward.py` (+ small additions to existing files):
- Lifecycle: create GI (partial) → second GI (complete) → PO flips `received`
- Over-receipt: line qty beyond PO remaining → 400
- Billing gate: blocked at partial coverage; allowed at full; allowed at
  partial when setting off; GIs flip `billed` on conversion
- Cancel: requires reason; restores coverage headroom; PO reverts to
  `approved` when coverage drops; cancel after billing → 400
- Tenant isolation: GI against another tenant's PO → 404; foreign po_line → 400
- Permissions: no `purchase.gate` edit right → 403
- Uninstall guard: blocked with documents, allowed after purge
- 3-way match: variance rows computed correctly (qty and amount)

## Out of scope (later phases)

- Store Issue + GL posting + `/purchases` hub page (Phase 3)
- Vendor performance analysis, demo-seeder chain data, README/BLUEPRINT/
  WORKFLOW docs overhaul (Phase 4)
- True purchase-GRN with GRNI accrual (not planned; compatible if ever needed)
