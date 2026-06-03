# User-Level Dynamic Reporting Framework — Design

**Date:** 2026-06-03
**Status:** Draft for review
**Scope:** A generic, user-configurable report builder (Odoo / QuickBooks / Oracle-APEX / Bookkeeper style) over curated single-source datasets — column chooser, click-to-filter, grouping + totals, saved reports, and export. Multi-tenant safe by construction.

> **Related (not in scope):** "Audit Log as a System-menu page with hyperlinking" was the user's item 1 — it is **already implemented** in open **PR #38** (`feature/audit-log-page`: `/audit` System page, `DocLink` hyperlinked entities, Timeline/By User/By Type views, CSV export). It only needs merging and is excluded from this spec.

---

## Locked decisions (from brainstorming)

1. **Paradigm:** generic **report builder over curated data sources** (not an interactive layer on existing reports, not an ad-hoc SQL/join designer).
2. **Data model:** **single source per report + curated related fields.** No user-defined joins. A data source may expose pre-joined fields (e.g. `Invoice → customer.region`) via join paths declared in the registry. (Designed so cross-source joins *could* be added later without a rewrite, but explicitly out of scope for v1.)
3. **v1 capabilities — all four bundles:**
   - **Interactive grid core:** column chooser (pick + reorder), click-to-filter (field + operator + value, **AND-combined**), sorting, date-range/period presets.
   - **Grouping & totals:** group by field(s) with collapsible subtotals + aggregate footers (sum/avg/count/min/max) on numeric/money columns.
   - **Saved reports:** save a config under a name; reopen; **private** (owner) or **shared** (whole tenant); edit/delete **owner-only**.
   - **Export & print:** server-side CSV + XLSX export and a Print/PDF layout using existing `PrintHeader` branding.
4. **Architecture:** Approach 1 — declarative data-source registry + SQLModel query builder. The registry is the security boundary.

## Out of scope for v1 (later phases)
- User-defined cross-source joins.
- OR / nested filter logic (v1 is AND-only).
- Email scheduling / delivery of reports.
- Charts/visualisations on builder output.
- Frontend component unit tests (no jest harness in repo; covered by type-check + build + manual).

---

## Architecture overview

```
Frontend  /reports/builder  ─POST /run──►  routers/report_builder.py
  <ReportGrid> (metadata-driven)            │ thin; read-only; no commit
  ColumnChooser / FilterBar / GroupBy       ▼
  SavedReportsMenu / ExportMenu      services/report_engine.py
        ▲   ▲                               │ registry-resolve → tenant-inject → select()
        │   └─GET /sources──────────────────┤ DB-side filter/group/aggregate + paginate
        │     (registry metadata)           ▼
        └─────/reports CRUD──►  ReportDefinition table   services/report_sources/ (REGISTRY)
```

Pure-logic in `services/` (engine + registry); thin FastAPI routers; one new table; one new frontend page with small, independently-testable components.

---

## Section 1 — Data-source registry (`backend/services/report_sources/`)

The registry is **declarative Python (never user input)** and is the security boundary: user configs reference only stable string **keys**, which the server resolves to real SQLModel columns. An unknown key is a `400`, never a query.

```python
@dataclass(frozen=True)
class FieldDef:
    key: str                      # stable id used by API/UI, e.g. "customer_name"
    label: str                    # human label
    type: FieldType               # TEXT | NUMBER | MONEY | DATE | ENUM | BOOL
    column: InstrumentedAttribute # the real SQLModel column (resolved server-side)
    join: JoinPath | None = None  # curated join, e.g. Invoice.customer_id -> Customer.id
    enum_values: list[str] | None = None  # drives dropdown filter for ENUM
    aggregatable: bool = False    # eligible for SUM/AVG/etc footers
    groupable: bool = True

@dataclass(frozen=True)
class JoinPath:
    local: InstrumentedAttribute  # e.g. Invoice.customer_id
    target: type[SQLModel]        # e.g. Customer
    target_key: InstrumentedAttribute  # e.g. Customer.id

@dataclass(frozen=True)
class ReportSource:
    key: str                      # "invoices"
    label: str                    # "Invoices"
    model: type[SQLModel]         # Invoice
    fields: dict[str, FieldDef]   # whitelist — the ONLY queryable columns
    default_columns: list[str]    # initial grid columns
    date_field: str | None        # field that period/date-range presets filter on
    required_role: str = "viewer"

    def field(self, key: str) -> FieldDef: ...  # KeyError -> HTTP 400 at the router
```

**`tenant_id` is never a registry field** — it is force-injected by the engine on every query.

**v1 data sources** (each is one `ReportSource`; more are added later by appending entries, no engine change):
- **Invoices** (`Invoice`, date_field `issue_date`) — incl. curated `customer_region` via join.
- **Bills** (`Bill`, `bill_date`).
- **Journal Entry lines** (`JournalEntry` joined to `Transaction`/`Account`, date via `Transaction.date`) — the GL workhorse.
- **Payments received** (`PaymentReceived`) and **Payments made** (`BillPayment`).
- **Products / Inventory** (`Product`, `StockMovement`).
- **Customers** (`Customer`), **Vendors** (`Vendor`).

`type` drives both allowed operators and the UI widget:
| type | operators | widget |
|---|---|---|
| TEXT | contains, equals, starts_with, in | text box |
| NUMBER / MONEY | equals, gt, gte, lt, lte, between | number / range |
| DATE | before, after, between, period-preset | date picker |
| ENUM | in, equals | dropdown (from `enum_values`) |
| BOOL | equals | toggle |

---

## Section 2 — Storage: `ReportDefinition` + shared `ReportConfig`

One new table (existing conventions: `tenant_id`, indexed). A saved report = name + the same config blob the run endpoint accepts ad-hoc.

```python
class ReportDefinition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    source_key: str                              # must exist in REGISTRY
    config: str = Field(sa_column=Column(JSON))  # ReportConfig blob (below)
    visibility: str = Field(default="private")   # "private" | "shared"
    owner_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

**`ReportConfig`** (Pydantic) — validated against the registry on every run *and* save, so invalid configs can neither run nor persist:
```jsonc
{
  "columns": ["number","customer_name","issue_date","total"],   // registry keys, display order
  "filters": [
    {"field":"status","op":"in","value":["sent","partial"]},
    {"field":"currency","op":"equals","value":"EUR"},
    {"field":"total","op":"gte","value":1000}
  ],                                                              // AND-combined (v1)
  "sort":      [{"field":"issue_date","dir":"desc"}],
  "group_by":  ["customer_name"],
  "aggregates":[{"field":"total","fn":"sum"}],
  "date_range":{"preset":"this_quarter"}                          // or {"start":"…","end":"…"}
}
```

**Migration:** `0020-style` guarded create_table with `if not bind.dialect.has_table(bind, "reportdefinition")`, `down_revision` = current head (**`aa01prodcat`** — verify with `alembic heads`), per the repo's SQLite-safe pattern (CLAUDE.md). No FK lines on ALTER.

**Endpoints** (`routers/report_builder.py`, all `/api/report-builder`):
| Method | Path | Purpose |
|---|---|---|
| GET | `/sources` | registry metadata (sources + fields/types/ops/enums) — drives UI |
| POST | `/run` | run ad-hoc `ReportConfig` against `source_key`; paginated |
| GET | `/reports` | list saved (mine + shared in tenant) |
| POST | `/reports` | save new |
| PATCH | `/reports/{id}` | update (owner-only) |
| DELETE | `/reports/{id}` | delete (owner-only) |
| POST | `/export?format=csv\|xlsx` | re-run config through engine, stream file (row-cap enforced) |

---

## Section 3 — Query engine (`backend/services/report_engine.py`)

Read-only `select()` builder. The router calls it and never commits.

```python
def run_report(session, *, tenant_id, source_key, config, page, page_size) -> ReportResult:
    source = REGISTRY.get(source_key) or raise_400("unknown source")
    select_fields = [source.field(k) for k in config.columns]      # KeyError -> 400
    needed_joins  = {f.join for f in (select_fields + filter_fields + group_fields) if f.join}

    q = select(*[f.column.label(f.key) for f in select_fields]).select_from(source.model)
    for j in needed_joins:                                          # curated joins only
        q = q.join(j.target, j.local == j.target_key)
    q = q.where(source.model.tenant_id == tenant_id)                # ALWAYS injected

    for flt in config.filters:                                      # AND
        f = source.field(flt.field)
        q = q.where(build_predicate(f, flt.op, coerce(f.type, flt.value)))
    if config.date_range and source.date_field:
        q = apply_date_range(q, source.field(source.date_field), config.date_range)

    if config.group_by:
        gcols = [source.field(k).column for k in config.group_by]
        aggs  = [agg_expr(source.field(a.field), a.fn) for a in config.aggregates]
        q = select(*gcols, *aggs).where(...).group_by(*gcols)

    q = q.order_by(*[direction(source.field(s.field), s.dir) for s in config.sort])
    total   = session.scalar(select(func.count()).select_from(q.subquery()))
    rows    = session.exec(q.offset(page*page_size).limit(page_size)).mappings().all()
    footers = grand_totals(session, source, config) if config.aggregates else None
    return ReportResult(rows, footers, total, column_meta(select_fields))
```

**Five guarantees:**
1. **Tenant isolation unconditional** — `where(model.tenant_id == tenant_id)` appended by the engine, never by config; applies even when another user runs a `shared` report (scoped to *their* tenant).
2. **Every identifier registry-resolved** — `source.field(key)` raises → `400`; no string reaches SQL → injection structurally impossible.
3. **Operators type-checked** — `build_predicate` rejects mismatches (e.g. `contains` on MONEY → `400`); values coerced per type (Decimal money, ISO-date validation, enum membership).
4. **Joins curated** — only registry `JoinPath`s, added only when a referenced field needs one.
5. **Read-only** — no writes, no commit; zero GL/data risk.

**Response shape:**
```jsonc
{
  "columns":[{"key":"total","label":"Total","type":"money","aggregatable":true}, …],
  "rows":[{"number":"INV-001","customer_name":"Acme","total":"1200.00"}, …],
  "group_by":["customer_name"],
  "footers":{"total":"48230.00"},          // when aggregates set
  "page":0,"page_size":100,"total_count":412
}
```
Money serialised as **string** (repo money convention). Filtering/grouping/aggregation run **in the DB**; results paginated (default 100); a hard cap (10k rows) guards exports.

---

## Section 4 — Frontend (`/reports/builder`)

New route under the **Reports** sidebar section, with saved reports listed beneath. One reusable metadata-driven `<ReportGrid>` — **no per-source frontend code**.

**Layout:**
```
Source:[ Invoices ▾ ]  Period:[ This Quarter ▾ ]  [Saved ▾]
[+Columns] [+Filter] [Group by ▾]        [Save] [Export ▾] [⎙]
Filters: ( status in sent,partial ✕ ) ( currency = EUR ✕ )
─────────────────────────────────────────────────────────
Invoice#▲│Customer│Issue Date│Status│        Total
▸ Acme (3)                              12,400.00     ← group + subtotal
   INV-001│Acme   │2026-04-02│sent  │    1,200.00 ▾   ← click cell → "Filter by this"
▸ Globex (2)                             9,800.00
─────────────────────────────────────────────────────────
TOTAL                                   48,230.00      ← footer
                       ◀ Page 1/5 ▶   100/page
```

**Components (each independently testable):**
| Component | Responsibility | Driven by |
|---|---|---|
| `ReportBuilderPage` | holds working `ReportConfig` state; calls `/run` on any change | — |
| `SourcePicker` | choose source | `/sources` |
| `ColumnChooser` | checkbox + drag-reorder of fields | field metadata |
| `FilterBar` + `FilterEditor` | add/remove filters; operator + value widget by field `type` | field `type` |
| `GroupByPicker` | pick groupable field(s) | `groupable` fields |
| `<ReportGrid>` | render columns/rows/group headers/subtotals/footers; sortable headers reuse **`SortableHeader.tsx`**; click cell → "Filter by this value" | `/run` response |
| `SavedReportsMenu` | load/save/save-as/delete; private↔shared toggle | `/reports` |
| `ExportMenu` | CSV / XLSX / Print | `/export` |

**Data flow:** mount → `GET /sources` → pick source → `POST /run` with `default_columns` → render. Every edit mutates config → re-`POST /run`. **Save** sends the same config to `/reports`. Fetch via `apiFetch`; money via `useFmt`/`useSettings`; styling matches existing report pages (cream `#f6f3ee` / gold `#b8943f`). Builder is a client component; check `node_modules/next/dist/docs/` + `frontend/AGENTS.md` for App-Router specifics first (Next 16 constraint).

**Export server-side** — `/export` re-runs the same config through the engine so row-cap + tenant filter live in one place; Print uses `PrintHeader`.

---

## Section 5 — Testing strategy

Backend: pytest with the `client` fixture + `_auth(client)` helper + `TestClient` (repo convention). Frontend: type-check + build (repo's frontend gate; no jest harness).

1. **Engine units** (`tests/test_report_engine.py`): predicate per type; value coercion (money→Decimal, ISO date, enum membership); join added only when needed.
2. **Safety** (`tests/test_report_builder_safety.py`) — *most important*: `unknown_source_400`, `unknown_field_400`, `op_type_mismatch_400`, `tenant_isolation_run`, `shared_report_scoped_to_runner_tenant`, `arbitrary_string_not_reachable`.
3. **Run integration** (`tests/test_report_builder_run.py`): each operator end-to-end; date_range presets + explicit; sort; pagination (`total_count` + slicing); default columns; grouping subtotals + aggregate footers vs hand-computed figures.
4. **Saved CRUD** (`tests/test_report_builder_reports.py`): save→list→load round-trip; PATCH/DELETE; invalid config → 400; visibility (private hidden from others, shared visible in tenant, edit/delete owner-only → 403 otherwise); migration smoke from empty DB.
5. **Export** (`tests/test_report_builder_export.py`): CSV header+rows match run; XLSX valid workbook; row-cap enforced.
6. **Frontend gate:** `npm run lint` + `tsc --noEmit` + `npm run build` clean.

**Definition of done:** full `uv run pytest` green (existing + new); frontend builds clean; all four v1 bundles work against seeded demo data.

---

## File structure summary

**Backend**
- Create: `backend/services/report_sources/__init__.py` (registry + dataclasses + REGISTRY)
- Create: `backend/services/report_engine.py` (query builder)
- Modify: `backend/models.py` (`ReportDefinition`)
- Create: `backend/alembic/versions/<rev>_report_definition.py` (guarded; revision id assigned at impl time via `alembic revision`; `down_revision = aa01prodcat` — confirm with `alembic heads`)
- Create: `backend/routers/report_builder.py` (`/sources`, `/run`, `/reports` CRUD, `/export`)
- Modify: `backend/main.py` (register router)
- Create: tests `test_report_engine.py`, `test_report_builder_safety.py`, `test_report_builder_run.py`, `test_report_builder_reports.py`, `test_report_builder_export.py`

**Frontend**
- Create: `frontend/src/app/(dashboard)/reports/builder/page.tsx` + components `ReportGrid`, `ColumnChooser`, `FilterBar`, `GroupByPicker`, `SavedReportsMenu`, `ExportMenu` (under `src/components/report-builder/`)
- Modify: `frontend/src/components/Sidebar.tsx` (Reports → Report Builder + saved reports)
- Reuse: `SortableHeader.tsx`, `apiFetch`, `useFmt`, `useSettings`, `PrintHeader`

**Docs**
- Modify: `CLAUDE.md` (router table + reports note), `README.md`, `USER_GUIDE.md`, `WORKFLOW.md` (new report-builder entry)
