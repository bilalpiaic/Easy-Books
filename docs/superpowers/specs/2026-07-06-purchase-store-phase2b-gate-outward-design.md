# Purchase/Store Module — Phase 2b: Gate Outward (#137)

**Date:** 2026-07-06
**Status:** Approved design
**Prior art:** Phase 2 (merged `864fbcd`) — Gate Inward: `GateInward`/`GateInwardLine` models, `services/gate.py` coverage math, billing gate, gate-register + 3-way-match reports. Spec: `2026-07-05-purchase-store-phase2-design.md`.

## Scope

Phase 2b adds **Gate Outward (GO)** — the dispatch-side mirror of Gate Inward —
covering three things leaving the premises: sales invoice dispatch, purchase
returns (debit notes), and scrap disposal.

## Key architectural finding that shaped this design

Gate Inward could enforce a hard block because it sits *before* the
accounting event (PO approval happens before goods move; billing happens
after). On the outward side, **stock already leaves the books at invoice
creation** (`consume_stock` runs inside `create_invoice`, before the invoice
is even saved as `draft`) — there is no later checkpoint analogous to
PO→billing to hang a block on, and reworking when invoices post is out of
scope for this phase.

**Decision (locked): reconciliation, not enforcement, for invoice/debit-note
exits.** Gate Outward records the physical exit as a memo and a report flags
mismatches; it never blocks invoice or debit-note creation or status
changes.

**Scrap is the one exception.** It has no existing document, model, or GL
treatment anywhere in the codebase — its own Gate Outward entry IS the
originating transaction, so it must consume stock and post GL itself.

## Data model (new Alembic migration, `has_table` guard)

### `GateOutward`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `tenant_id` | FK tenant, indexed | |
| `number` | str, indexed | `GO-YYYY-seq` via `SequenceCounter`; unique per tenant |
| `source_doc_type` | str | `invoice` \| `debit_note` \| `scrap` |
| `source_doc_id` | int, optional | FK resolved by type; null only for `scrap` |
| `gate_date` | str (ISO date) | |
| `time_out` | str, optional | HH:MM |
| `vehicle_no` | str, optional | |
| `challan_no` | str, optional | |
| `remarks` | str, optional | |
| `status` | str | `draft` \| `approved` \| `cancelled` |
| `created_by_id` | FK user | |
| `approved_by_id` | FK user, optional | scrap only |
| `approved_at` | datetime, optional | scrap only |
| `cancel_reason` | str, optional | |
| `created_at` | datetime | |

CheckConstraint: `status IN ('draft','approved','cancelled')`;
`source_doc_type IN ('invoice','debit_note','scrap')`.

### `GateOutwardLine`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `gate_outward_id` | FK, cascade delete | |
| `product_id` | FK product | |
| `qty` | Money | CheckConstraint qty > 0 |
| `unit_cost` | Money, default 0 | scrap only — inventory cost relieved per unit |
| `unit_value` | Money, default 0 | scrap only — salvage/sale price per unit |

`unit_cost`/`unit_value` are always present on the row (simpler than a
polymorphic line table) but are only meaningful — and only populated by the
UI — when the parent's `source_doc_type == "scrap"`.

## Rules & state machine

### Invoice / debit_note exits (memo, no GL)
1. **Create** — `status="approved"` immediately (no draft step; nothing to
   approve). Validates the source document belongs to the tenant and is not
   `draft`/`void`/`cancelled`. Multiple GO entries per source document are
   allowed (a shipment can go out in batches) — no qty cap, since this is
   reconciliation not control.
2. **Cancel** — allowed anytime, requires a reason, audit-logged. No GL/stock
   effect either way (nothing to reverse).

### Scrap exits (the transaction itself)
1. **Create** — `status="draft"`. No source document. No GL, no stock
   consumed yet. Freely editable/cancellable while draft (delete the
   mistake, no reversal needed).
2. **Approve** (`PATCH /{id}/approve`, `AdminUserDep`) — blocks
   self-approval (`created_by_id == approver.id` → 400, same rule as
   Demand/Comparative). On success:
   - For each line, call `consume_stock` (source_doc_type="gate_outward") to
     relieve inventory at the product's actual moving-average cost; sum the
     returned relief into `total_cost`.
   - `total_value = Σ(qty × unit_value)`.
   - If `total_value > 0`: post JV — `Dr 1000 Cash in Hand`
     (`get_or_create_account`, Asset — the default CoA's existing cash leaf,
     `backend/db.py` `_coa_for`) / `Cr 4902 Scrap Sales`
     (`get_or_create_account`, Revenue).
   - Always (qty > 0 lines exist): post a **separate** JV — `Dr 5901 Scrap
     Disposal Expense` (`get_or_create_account`, Expense) / `Cr Inventory`
     for `total_cost` — mirrors the existing invoice pattern of two separate
     JVs (Revenue then COGS) rather than one combined entry.
   - `status="approved"`, `approved_by_id`, `approved_at` set.
3. **Cancel** — allowed only while `status == "draft"`. Once `approved`,
   immutable: no cancel, no edit. Matches this codebase's own convention
   (`CreditNote`'s docstring: ISA 240, "issued instead of editing a posted
   invoice") — a mistake found after approval needs a correcting entry
   design, explicitly out of scope for this phase.

## Permissions

New resource `store.gate_outward`, category **Store** (new category,
distinct from `purchase.gate`'s "Purchasing" — Gate Outward spans Sales,
Purchases, and Inventory, and is staffed by security/store personnel, not a
purchasing role). `routers/gate_outward.py` guarded by
`perm_dep("store.gate_outward", ...)`; `apply_own_filter` on the list
endpoint. The approve endpoint requires `AdminUserDep` in addition (matches
Demand/Comparative's segregation-of-duties pattern).

## API surface

`routers/gate_outward.py` (mounted `/api/gate-outwards`):
- `GET /` — list; filters `source_doc_type`, `status`, `source_doc_id`;
  own-filter applied
- `GET /{id}` — detail with lines + resolved source-document context
  (invoice/debit-note number + party name; nothing extra for scrap)
- `POST /` — create (rules above)
- `PATCH /{id}/approve` — scrap only; 400 for invoice/debit_note types
  ("nothing to approve")
- `PATCH /{id}/cancel` — body `{reason}`

`routers/store_reports.py` (mounted `/api/store-reports`; new file — kept
separate from `purchase_reports.py` since Gate Outward is not
purchase-specific):
- `GET /gate-outward-register?start=&end=&q=&source_doc_type=` — all GO
  entries in range; `q` matches vehicle or challan; rows carry a resolved
  "reference" column (invoice #, debit-note #, or "Scrap")
- `GET /dispatch-reconciliation?start=&end=` — one row per posted
  Invoice/DebitNote in range: document #, party, date, `has_gate_exit`
  (bool), and the GO # if one exists. Flags documents with no matching gate
  exit yet. (No quantity variance column — invoices don't carry a separate
  dispatch quantity to compare against, unlike PO vs GI vs Bill.)

## Shared-helper carry-in

`_gate_required`/`_chain_required` in `purchase_orders.py` are near-identical
setting-gate checks; Phase 2's final review flagged the duplication as a
Minor to fold in when next touched. Gate Outward introduces no new
setting-gate of its own (it's reconciliation-only, not enforcement — there is
nothing to toggle on/off), so there's no third near-copy to add. The
duplication fix itself is deferred to whichever phase next needs a new
setting-gate helper; not part of this phase's scope.

## Frontend

New **Store** nav section (`forModule: "purchase_store"`, added to both
`NAV` and `SUB_NAV`/`SECTION_PREFIXES` per the standing checklist — this
section will also host Phase 3's Store Issue):
- `/store/gate-outward` — list (GO#, date, type, reference, status)
- `/store/gate-outward/new` — form: source-type picker (Invoice / Debit Note
  / Scrap) →
  - Invoice/Debit Note: dropdown of posted documents, lines pre-filled
    (read-only qty/product from the source document)
  - Scrap: bare line editor — product picker, qty, unit_cost (defaults from
    product avg_cost, editable), unit_value (defaults 0)
- `/store/gate-outward/[id]` — detail + portrait print; scrap drafts show an
  "Approve" button (admin/owner only, disabled with tooltip if
  `created_by_id === currentUser.id`); non-draft/scrap-cancelled show a
  Cancel action with inline reason input (mirrors Gate Inward's detail page)
- `/store/gate-outward-register` — landscape report, `.table-freeze`,
  date+search filters, type filter
- `/store/dispatch-reconciliation` — landscape report, `.table-freeze`,
  flagged rows (`has_gate_exit === false`) highlighted

## Testing

`tests/test_gate_outward.py`:
- Invoice-sourced GO: create → approved immediately, no GL/stock change;
  cancel anytime with reason; rejects draft/void invoices; rejects foreign
  tenant's invoice
- Debit-note-sourced GO: same shape as invoice
- Scrap GO lifecycle: create as draft (no GL, no stock change) → approve
  (self-approval blocked) → GL posted (revenue JV only when
  `total_value > 0`; expense/inventory JV always; balanced debits=credits)
  → stock actually relieved (`Product.stock_qty` decreases,
  `Product.avg_cost` unaffected by a sale-below-cost scrap) → status
  `approved`
- Scrap cancel: allowed while draft; rejected once approved
- Permission: `store.gate_outward` view-only user blocked from
  create/approve/cancel; `AdminUserDep` enforced on approve specifically
  (a non-admin write-role user with edit-level `store.gate_outward` can
  create/cancel but not approve)
- Tenant isolation on every query
- Reports: register filters (type, search, date range); reconciliation
  correctly flags a posted invoice with no GO entry, and correctly clears
  once one exists

## Out of scope (later work)

- Blocking invoice "sent" status without a gate exit (considered, rejected
  for this phase — touches the shared invoice status-transition endpoint,
  higher blast radius than reconciliation)
- Correcting an approved scrap entry (reversal/adjustment document design)
- `_gate_required`/`_chain_required` dedup (no new instance added here;
  still pending from Phase 2)
- Phase 3 (Store Issue + GL posting + hub page) and Phase 4 (vendor
  performance, seeder, docs) from the original issue #137 phasing remain
  separately scoped
