# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Easy-Books** is a SaaS double-entry bookkeeping application for SMEs. It is a **monorepo with two parallel implementations**:

- **Modern Stack (Primary):** `frontend/` (Next.js 16 / React 19 / TypeScript) + `backend/` (FastAPI / Python 3.11+)
- **Legacy Stack (Reference only):** `server.js` (Express) + `public/` (Vanilla JS)

Focus development on the modern stack unless explicitly working on the legacy reference implementation.

---

## Commands

### Backend (FastAPI)

```bash
cd backend
uv sync                                         # install dependencies
python main.py                                  # dev server → http://localhost:8000
uv run pytest                                   # run all tests
uv run pytest -v                                # verbose
uv run pytest tests/test_auth.py               # single file
uv run pytest -k test_name                     # single test by name
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev        # dev server → http://localhost:3000
npm run build
npm start          # production
npm run lint       # ESLint
```

### Legacy Stack

```bash
npm install && node server.js    # runs on root package.json
```

---

## Architecture

### Backend (`backend/`)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI bootstrap — middleware wiring and router mounts (~80 lines) |
| `models.py` | SQLModel table + schema definitions (includes `ProductCategory` for the 2-level product taxonomy). `ConsolidationMember` / `ConsolidationRun` / `ConsolidationElimination` — IFRS 10 group worksheet on the holding tenant (#255; API `routers/consolidation.py`, engine `services/consolidation.py`; eliminations never post to member GLs). **Intercompany (#261):** `Invoice`/`Bill` carry `is_intercompany`, `ic_counterparty_tenant_id`, and `ic_mirror_*_id`; service `services/intercompany.py` + API `routers/intercompany.py` (counterparties + paginated recon); CoA leaves `1180` Due from Affiliates / `2180` Due to Affiliates. `LeaseContract` / `LeaseScheduleLine` — IFRS 16 RoU + lease liability (#256; API `routers/leases.py`, engine `services/leases.py`; GL via `posting.py`; settings gate `leases_enabled`). `Account` has `parent_id` + `is_group` (multi-level CoA; posting to active leaves only). `Product` has `is_deferred` + `recognition_months` (deferred revenue). `DeferredRevenueSchedule` tracks IFRS-15 recognition per invoice. `UserPermission` — sparse override table keyed by `(tenant_id, user_id, resource_key)` with `access_level` (`none/view/edit`) and `my_data_only` flag; module-gated via `settings.user_rights_enabled`. `CommissionPlan` + `CommissionLedger` — rate/target plans per user; compute → approve → post GL entry flow. `PromoRule` — product/min-qty/discount-pct rules; `InvoiceLine.discount_pct` + `promo_rule_id` apply the discount (`amount = qty × rate × (1 − discount_pct/100)`). `Employee` + 5 HRM tables (`SalaryComponent`, `EmployeeSalaryStructure`, `PayrollRun`, `PayrollLine`, `PayrollLineDetail`) — full payroll cycle; `AttendanceRecord` — manual/biometric time-in/out with hours_worked, status (present|absent|half_day|leave|holiday|off), source field ready for ZKTeco device integration. **Purchase chain (#137 P1):** `PurchaseDemand` (PD-YYYY-seq, quantity-only, `created_by_id`/`approved_by_id` distinct) + `PurchaseDemandLine`; `VendorQuotation` (VQ-YYYY-seq, per-demand-line rate) + `VendorQuotationLine`; `ComparativeStatement` (CS-YYYY-seq, one per demand via unique constraint, `selected_quotation_id` + `justification`); `PurchaseOrder` gained `demand_id` + `comparative_id` FKs; `GateInward` (GI-YYYY-seq, memo gate entry vs PO, status open/billed/cancelled, append-only once billed) + `GateInwardLine` (per-PO-line qty caps) (#137 P2); `GateOutward` (GO-YYYY-seq, dispatch exit — memo for invoice/debit_note sources, draft→approve with GL posting for scrap) + `GateOutwardLine` (#137 P2b). `StoreIssue` (SI-YYYY-seq, departmental/cost-center consumption — posts Dr user-picked Expense account (analytic-tagged) / Cr Inventory immediately on create, no draft/approve gate) + `StoreIssueLine` (#137 P3). |
| `models_telecom.py` | 23 `tc_*` tables for the Telecom Franchise business model |
| `models_healthcare.py` | 19 `hc_*` tables for the Healthcare / Hospital business model: `HcPatient` (MR-YYYYNNNN + auto-linked Customer), `HcDoctor`, `HcWard`, `HcBed` (status: available/occupied/maintenance), `HcProcedureCatalog`, `HcOpdToken`, `HcOpdVisit`, `HcPrescription`, `HcPrescriptionItem`, `HcAdmission` (ADM-YYYYNNNN, deposit + discharge invoice), `HcAdmissionCharge` (accumulate until discharge — no individual GL post), `HcLabTest`, `HcLabOrder` (LO-YYYYNNNN), `HcLabOrderItem` (result per test), `HcSampleCollection`, `HcProcedureOrder`, `HcStoreIssue`, `HcStoreIssueItem`, `HcProcedureConsumable` |
| `models_weaving.py` | 10 `wv_*` tables for the Weaving unit-control module (#140): masters (`WvFabricQuality`, `WvLoom`, `WvYarnType`, `WvShift`, `WvOperator`) + `WvContract` (embedded rate/costing) + `WvYarnInward` / `WvSizing` / `WvProduction` / `WvDispatch`. **v1 is memo/ops only — no GL posting.** Yarn weights stored in Kg; Lbs/Bags and Rate/Lb derived via `services/weaving_calc.py`. |
| `models.py` (`UserDashboardLayout`) | Per-user dashboard layout KV — `(tenant_id, user_id)` → opaque `layout` JSON; schema-agnostic (v3 sparse breakpoint overrides). `GET/PUT /api/dashboard/layout`. |
| `db.py` | Engine creation, startup seeding (default tenant + CoA + admin user + 7 demo tenants). **The default Chart of Accounts is hierarchical** — a shared group skeleton (`_COA_GROUPS`: `1`/`11`/`12`/`2`/`21`/`3`/`4`/`41`/`49`/`5`/`51`/`52`/`59`) + leaf accounts carrying `parent_code`; `_coa_for()` yields 6-tuples `(code,name,type,is_memo,parent_code,is_group)`; `seed_data` inserts in two passes (create all → wire `parent_id`). Posting is restricted to active leaf accounts. The three `_coa_for` consumers (`seed_data`, `seed_demo._ensure_coa`, settings model-switch) all do this two-pass wiring. **`MODULE_REGISTRY`** — dict of all 10 installable modules (base/inventory/production/hrm/telecom/pra/healthcare/ai_assistant/purchase_store/weaving) with label, description, category, icon, deps, always, tier fields; **`MODULES_BY_MODEL`** — maps business_model → default module list (new module IDs, not legacy strings). The manufacturing demo also enables `weaving` for unit-control discoverability. |
| `auth.py` | JWT encoding/decoding, bcrypt password hashing |
| `routers/` | 40+ domain routers (accounts, invoices, bills, payments, users, telecom, healthcare, reports, credit_notes, debit_notes, advances, assets, budgets, purchase_orders, analytic_accounts, deferred_revenue, commissions, promo_rules, permissions, …) |
| `routers/admin.py` | Demo-data management: seed all 7 demo tenants on demand / purge them (admin+). Backs the **Settings → Sample / Demo Data** card. |
| `routers/healthcare.py` | Patients (`GET/POST /patients`, `GET/PUT /patients/{id}`, `/patients/{id}/visits|admissions|lab-orders`), Doctors, Wards/Beds (`PUT /beds/{id}` status machine), OPD tokens + visits (bill on record: `Dr 1100 / Cr 4100`), Prescriptions, IPD admissions (`POST /admissions/{id}/charges`, `POST /admissions/{id}/discharge` — consolidated invoice + deposit settlement), Lab tests catalogue, Lab orders (`POST /lab/orders/{id}/collect`, result entry, deliver), Procedure catalogue + orders, Store issues (`/store/issues`), Pharmacy dispense queue (`/store/pharmacy/dispense`). |
| `routers/healthcare_reports.py` | 7 endpoints under `/api/healthcare/reports/`: `dashboard` (KPIs), `opd-summary`, `doctor-collections`, `lab-summary`, `ipd-census`, `revenue-by-type` (GL accounts 4100–4121), `patient-statement/{id}`. |
| `routers/product_categories.py` | `ProductCategory` CRUD — 2-level taxonomy (parent category → sub-category). Delete blocked while sub-categories or products exist. |
| `routers/commissions.py` | `CommissionPlan` CRUD + `GET /api/commissions/staff` (users eligible for commissions) + `GET /api/commissions/ledger` + `POST /compute` (period commission calculation) + `POST /ledger/{id}/approve` + `POST /ledger/{id}/post` (creates `Dr Commission Expense / Cr Commissions Payable` GL entry). |
| `routers/promo_rules.py` | `PromoRule` CRUD + `POST /api/promo-rules/check` — given a list of invoice lines returns applicable discount suggestions; "Apply Promos" button on InvoiceForm applies them. |
| `routers/permissions.py` | Granular access control — `GET /api/permissions/me` (current user's rights), `GET /api/permissions/resources` (74-resource registry), `GET /api/permissions/users/{id}`, `PUT /api/permissions/users/{id}` (admin matrix update), `PATCH /api/permissions/users/{id}/my-data-only`. |
| `routers/ai_chat.py` | AI Financial Assistant (#112 L1, multi-provider #117) — `POST /api/ai/chat` is an **async** SSE endpoint (`text/event-stream`) running a **4-stage agentic pipeline** per turn (2026-07-17; Reviewer added 2026-07-19, PRs #185–#188): **Triage** (`_run_triage`, a non-streaming, cheap-tier classification call — `max_tokens=30`, `temperature=0`, no tools — that picks one specialist agent key from `services/ai_agents.AGENTS`, filtered to the tenant's installed modules; any failure, malformed response, or unparseable text falls back to `"general"`, never aborting the request) → **Specialist** (`run_tool_loop()`, the tool-calling agent loop — max 6 steps, extracted as a shared generator so both the routed specialist and the `general` fallback call it identically — parameterized by that agent's own narrow tool subset + system-prompt fragment; its own text is accumulated but never streamed to the client, `yield_tokens=False`, only its `tool_start`/`tool_end` progress streams live) → **Reviewer** (`_run_reviewer`, a non-streaming, cheap-tier, no-tools **silent fact-check** — `max_tokens=1500`, `temperature=0` — that verifies every figure/name/date in the specialist's analysis against the raw tool-result JSON and returns a corrected analysis, which replaces the specialist text fed to drafting; **skipped entirely when the turn ran no tools** (nothing to verify), and any exception or empty output falls back to the unreviewed specialist text — it can never abort the stream. The pipeline's four LLM calls are distinguished by unique `(stream, max_tokens)` signatures — triage 30 / reviewer 1500 / specialist 2048 / drafting 4096 — which the test fakes rely on: **keep these numbers unique forever**) → **Drafting** (`_run_drafting`, a streaming, cheap-tier, no-tools completion that rewrites the specialist's raw findings — plus its raw tool-call results, for exact figures — into polished Markdown with GFM tables/headings; `max_tokens=4096`; only this stage's `token` events reach the client and become the persisted reply; falls back to the specialist's raw text verbatim if drafting itself produces nothing). The cheap/fast per-provider model used by Triage, Reviewer, and Drafting (`services/ai_providers.CHEAP_TIER` + `resolve_cheap_tier()` — `claude-haiku-4-5`/`gpt-4o-mini`/`gemini-flash-latest`; no entry for ollama, which has no tiering concept and reuses the user's own selected model for all 4 stages) is resolved per call with a `ValueError`-safe fallback to the user's own model if the mapping ever goes stale. **The agent roster is 11 keys** (2026-07-19): 5 always-available base agents (`receivables`, `payables`, `financial_reports`, `sales`, `general`) plus 6 module-gated agents (`inventory`/`payroll`/`healthcare`/`telecom`/`purchasing`/`manufacturing`) offered to triage only when their `AgentDef.required_module` is installed — see `services/ai_agents.py`. The specialist's tool subset is additionally re-filtered by installed modules at runtime (`ai_tools.filter_by_modules`, defense in depth). The routed agent key is persisted on `AiChatMessage.agent` (nullable, not yet surfaced via any API response). All ~50 read-only tools live in `services/ai_tools.py`'s `TOOL_REGISTRY` (2026-07-19 refactor — provider schemas, progress labels, and dispatch all derive from it; adding a tool is one registry entry, not a 4-place hand-edit) and call existing report functions directly (tenant filters reused, never re-implemented). Providers: anthropic/openai/gemini/ollama via LiteLLM, each with its own model list; cloud API keys resolve tenant-first from the Settings KV (`ai_api_key_<provider>`) with `ANTHROPIC_API_KEY` env var as a dev/demo fallback for the anthropic provider only (see `services/ai_providers.py`). Ollama (self-hosted, no cloud key) is translated at the `litellm.acompletion` call site only — internal/display/persisted form stays `ollama/<tag>` (matches every other provider's own-name-as-prefix convention), swapped to `ollama_chat/<tag>` + `api_base=<tenant's server URL>` right before the call so OpenAI-style tool-calling + streaming works against the tenant's own server. Chat sessions are server-side and per-user-private (`AiChatSession`/`AiChatMessage`, filtered by `tenant_id` + `user_id`); `GET/POST /sessions`, `PATCH/DELETE /sessions/{id}`, `GET /sessions/{id}/messages`. Streamed events: `stage` (`{label}` — pipeline-progress text shown through the same UI slot as `tool_start`/`tool_end`, e.g. "Routing your question…" / "`<Agent label>` is looking into this…" / "Reviewing figures…" / "Drafting your report…"), `token` (text delta — drafting stage only, see above), `tool_start`/`tool_end` (tool-call progress labels, specialist stage), `done` (`session_id`+`message_id`, persists the assistant reply), `error` (mid-stream failure — headers already sent, so provider errors can't become HTTP status codes once streaming starts; carries the provider's actual error text truncated to 300 chars, and the full exception is also printed server-side as `[ai_chat] ...` — a 2026-07-14 fix, previously only `type(exc).__name__` reached the client with nothing logged, making every mid-stream failure undiagnosable). Pre-stream gates (plain HTTP): `ai_assistant` module not installed → 403, message > 4,000 chars → 400, no provider configured → 503, unknown/misconfigured model → 400, sliding-hour rate limit (`ai_rate_limit_per_hour` setting, default 20/hour, per-process in-memory) → 429 — the rate limit is one decrement per user turn regardless of the pipeline's 4 internal LLM calls, since the check runs once pre-stream, before any of them happen. History trimmed to last 20 turns (a short 2-turn tail of it is also fed to Triage, for topic-continuation routing). `GET /models` returns configured providers + default model for the chat UI's dropdown; `GET /key-status` (admin-only) returns masked (`••••1234`) key tails per provider, never raw values — excludes ollama (no secret key to mask). |
| `routers/purchase_demands.py` | Purchase Demand CRUD (#137 P1) — quantity-only requisitions, no rates; `PATCH /{id}/approve` blocks self-approval (`created_by_id == approver.id` → 400); `/cancel`, `/close`; gated by `purchase.demand` permission + `my_data_only` via `apply_own_filter`. |
| `routers/quotations.py` | Vendor Quotations against an approved demand (#137 P1) — `POST/PUT /api/quotations` validate each line's `demand_line_id` belongs to the demand and the vendor belongs to the tenant; writes freeze (400) once the demand's comparative is `approved`/`converted`; gated by `purchase.comparative` permission. |
| `routers/comparatives.py` | Comparative Statement — quotation matrix, vendor selection, lowest-or-justify approval (#137 P1) — one CS per demand (unique constraint); `PATCH /{id}/approve` blocks self-approval, requires a selected quotation, requires `justification` when there are fewer than two quotations or the selection isn't the lowest total, and rejects approval if the selected quotation doesn't price every demand line; `POST /{id}/convert-to-po` creates the `PurchaseOrder` (`demand_id`/`comparative_id` set) from the winning quotation's lines. |
| `routers/gate_inward.py` | Gate Inward vs approved PO (#137 P2) — per-line qty ≤ PO remaining; coverage flips PO approved↔received; cancel-with-reason only while PO unbilled; gated by `purchase.gate`. `GET /pos` + `GET /pos/{po_id}` are gate-scoped, price-free PO views (no `rate`/`amount`/`total`) so a `purchase.gate`-only user can drive the whole GI flow without `purchase_orders` rights; the GI serializer carries each line's PO description/unit directly so the detail page needs no PO fetch either. |
| `routers/purchase_reports.py` | Gate register (vehicle/challan search, `{total, items}` paginated) + 3-way match (PO vs Σ GI vs Bill, positional line match, variance flags; paginated per-PO, `q` searches PO#/vendor, `EXISTS` filters to POs with a bill or non-cancelled GI). Vendor Performance (delivery lead time, quotation rate trend, short-receipt-rate proxy for rejection rate — not yet paginated). |
| `routers/gate_outward.py` | Dispatch exit — memo for invoice/debit_note (create = approved, reconciliation only); scrap is draft→approve, GL posts only at approval via `consume_stock(..., source_doc_type="gate_outward")`. Gated by `store.gate_outward`. |
| `routers/store_issues.py` | Store Issue — departmental consumption; posts GL + relieves stock atomically on create via `consume_stock(..., source_doc_type="store_issue")`; debit account must be Expense-type. Gated by `store.issue`. |
| `routers/store_reports.py` | Gate-outward register + dispatch reconciliation (posted invoices/debit-notes with no matching gate exit flagged — a SQL `UNION ALL` of invoices + debit notes so search/ordering/paging span both doc types) + Issue Register, all `{total, items}` paginated with `ilike` search pushed into SQL (#150/#154). Stock Tie-out (product-level, not per-location — consume_stock has no location_id; when `end` is supplied the variance columns return null since live stock can't reconcile a truncated window; not paginated — one row per stock product). |
| `routers/payroll.py` | Employee CRUD + salary structure replace; `SalaryComponent` catalog CRUD; `PayrollRun` lifecycle (draft→approve→post GL→void); auto-computes lines from salary structures; GL posting `Dr Salary Expense / Cr Salaries Payable`; PR-YYYY-seq voucher numbering; payslip endpoint. Permissions: `employees`, `payroll`, `payroll.components`. |
| `routers/attendance.py` | `AttendanceRecord` CRUD; bulk upsert; monthly summary (`GET /api/attendance/summary`); biometric import (`POST /api/attendance/import/biometric` — matches by employee_code, stores raw_data, sets source=biometric); hours auto-computed from time_in/time_out; delete blocked for biometric records. |
| `routers/customers.py` | Customer CRUD + `GET /api/customers/{id}/statement?from_date=&to_date=` — opening balance (pre-period payments), period invoices with per-line outstanding, period payments, closing balance. |
| `routers/vendors.py` | Vendor CRUD + `GET /api/vendors/{id}/statement?from_date=&to_date=` — AP mirror of customer statement (bills + bill-payments). |
| `routers/reports.py` | Contains the General Ledger endpoint (`/api/reports/ledger`) which returns **Opening Balance** and **Closing Balance** per account when `start`/`end` query params are supplied. Opening = net balance of all JEs before `start`; Closing = `opening + Σdebits − Σcredits` in period (sign follows account-type convention). New endpoints: `/api/reports/product-ledger` (each movement carries its resolved store `location`), `/api/reports/inventory-performance`, `/api/reports/customer-performance`, and `/api/reports/product-coa` (Main→Sub→Item closing-stock valuation tree grouped by product category, with rolled-up subtotals + an Uncategorized bucket; backs the **Tree** view toggle on the Products page). **Hierarchical statements (v2.5):** single-period `/trial-balance` → `{tree, totals}`, `/balance-sheet` → `{assets, liabilities, equity, totals}` (RE-CUR synthetic equity line), `/income-statement` → `{revenue, expenses, totals}` + `net_profit` — nested trees rolled up via `services/account_tree.py`; comparison mode (`compare_end`/`compare_start`) stays flat `{current, comparison}`. |
| `routers/report_builder.py` | Dynamic report builder — `/api/report-builder/sources` (list whitelisted data sources), `/api/report-builder/run` (execute a `ReportConfig`), `/api/report-builder/reports` CRUD (save/load/delete named reports), `/api/report-builder/export` (CSV/XLSX download, formula-injection-safe). All queries are tenant-scoped and column references are resolved exclusively through the whitelist in `services/report_sources/`. |
| `services/report_sources/__init__.py` | Declarative data-source **registry** (the security boundary): 9 whitelisted sources (`invoices`, `bills`, `journal_lines`, `payments_received`, `payments_made`, `products`, `stock_movements`, `customers`, `vendors`), each listing exact SQLAlchemy columns users may query. Unknown field keys → HTTP 400, never a query. |
| `services/report_engine.py` | Pure query builder — `ReportConfig` Pydantic schema + `run_report()`: resolves field keys through the registry, injects `tenant_id` unconditionally, builds a tenant-safe `select()` with filters, group-by, aggregates, and pagination. |
| `services/account_tree.py` | **Hierarchical roll-up engine** — `build_account_tree(accounts, values_by_account_id, field_names, *, prune_zero=True)`: builds the parent→child account tree, parent value = own + Σ descendant leaves, prunes zero subtrees. Backs the hierarchical Trial Balance / Balance Sheet / P&L. Generic over field set (`["debit","credit"]` or `["balance"]`/`["amount"]`). |
| `services/deferred.py` | **Deferred-revenue origination (#47)** — `plan_deferral`, `resolve_deferred_account`, `create_schedules`, `has_any_recognition`, `reverse_schedules`. Called by both `create_invoice` and `update_invoice` so create/edit can't diverge: `product.is_deferred` lines credit Deferred Revenue (2300) + originate a `DeferredRevenueSchedule`; edit blocks-if-recognized else reverses+rebuilds. |
| `services/permissions.py` | `perm_dep(resource_key, level)` factory — returns a FastAPI dependency injected into 35+ routers; resolves the effective right for `(tenant_id, user_id, resource_key)` by merging RBAC role defaults with `UserPermission` sparse overrides; `apply_own_filter(query, model, user)` adds `created_by_id == user.id` filter when `my_data_only=True`; `PERMISSION_RESOURCES` is the 74-resource registry used by the admin matrix. **A registered resource is not self-enforcing** — it only takes effect where a route actually carries `dependencies=[perm_dep(key, level)]`; a 2026-07 audit found 22 registered resources (12 `report.*`, `customer_ledger`/`vendor_ledger`, 8 `telecom.*`, plus the since-removed `team`) with zero enforcement anywhere in the backend. Fixed: `reports.py`/`aging.py` now gate all 12 report resources, `customers.py`/`vendors.py` layer `customer_ledger`/`vendor_ledger` on top of the coarser `customers`/`vendors` gate on the `/statement` routes, `telecom.py` replaced its single router-wide `telecom.tracker` check with 9 independently-scoped per-route resources (view for GET, edit for POST — the router-wide version had also left every POST endpoint checking only view-level), and the dead `team` entry was deleted (team management is hardcoded `AdminUserDep` in `users.py`, permission-proof by design). Whenever a new resource key is added to the registry, grep for `perm_dep("<key>"` to confirm a route actually references it — an entry with no call site is indistinguishable from a real gate in the admin UI. |
| `services/ai_providers.py` | Multi-provider LLM registry for the AI Financial Assistant (#117) — single source of truth for `PROVIDERS` (anthropic/openai/gemini/ollama: label, `settings_key`, `env_fallback`, `models`), `resolve_api_key()` (tenant Settings KV wins, env fallback for anthropic only; returns `None` for ollama — no cloud key), `configured_providers()` (the `/api/ai/models` payload — cloud providers need a resolvable key, ollama needs at least one tenant-tagged model), `validate_model()` (parses `provider/model` strings, returns `(litellm_model, api_key, api_base)` — `api_base` is non-`None` only for ollama — raises `ValueError` on unknown/unconfigured), `mask_key()` (`••••1234` — never returns raw key material). **Ollama is a self-hosted provider, not a cloud one**: `PROVIDERS["ollama"]["models"]` is deliberately empty (no fixed catalog) — `ollama_models()`/`ollama_base_url()` resolve the tenant-specific `ai_ollama_models` (comma-separated tags, Settings → AI's tag-input UI) / `ai_ollama_base_url` (defaults `http://localhost:11434`) KV settings instead; neither is a secret, so neither is in `AI_SECRET_SETTINGS_KEYS` and both round-trip through plain `GET`/`PATCH /api/settings` (unlike the cloud provider keys, which are write-only). `AI_SECRET_SETTINGS_KEYS` is consumed by `routers/settings.py`'s `GET /api/settings` to redact `ai_api_key_*` before the response leaves the server. **`CHEAP_TIER` + `resolve_cheap_tier()`** (2026-07-17, agentic pipeline): a fixed cheap/fast model per provider used by `ai_chat.py`'s Triage, Reviewer, and Drafting stages — `validate_model()` only checks the model ID is in that provider's own static list, not any tenant-selected allowlist, so the hardcoded mapping works the moment the tenant has *any* key for that provider, with zero requirement they've ever picked it in Settings; `resolve_cheap_tier` catches `ValueError` (e.g. the mapped ID gets removed from a provider's list later) and falls back to the exact `(model, key, base)` triple passed in, so a stale mapping degrades to "no cost savings this turn," never a hard failure. |
| `services/ai_agents.py` | Specialist-agent registry for `ai_chat.py`'s Triage stage (2026-07-17, full roster 2026-07-19) — mirrors `services/report_sources`'s frozen-dataclass-registry pattern. `AgentDef` (`key`, `label`, `trigger_hint` — fed to the triage classification prompt — `system_prompt_fragment`, `tools: tuple[str,...]` — subset of `ai_tools.TOOL_REGISTRY` names, `required_module: str \| None`). **`AGENTS` has 11 entries**: 5 base (`receivables`, `payables`, `financial_reports` — incl. balance sheet/tax/budget/net-worth tools + `run_custom_report`, `sales` — customer performance/statements, `general` — original 7 tools + `run_custom_report` fallback) and 6 module-gated (`inventory`, `payroll` (hrm), `healthcare`, `telecom`, `purchasing` (purchase_store), `manufacturing` (production)). `available_agents(installed_modules)` filters by `required_module` — a tenant only sees agents for its installed modules. **Invariants (test- + import-time-enforced):** every `AgentDef.tools` name must exist in `TOOL_REGISTRY` (import-time assert — a typo fails app boot), no agent key may be a substring of another (triage's fallback matcher is bidirectional-substring), and a module-gated agent may only reference base tools or tools of its own module. |
| `services/ai_tools.py` | **Declarative tool registry for the AI assistant** (2026-07-19, PRs #185–#188) — frozen `ToolDef` dataclass (`name`, `description`, `input_schema` (Anthropic JSON-Schema shape), `label` (progress text), `executor: (session, user, tool_input) -> result`, `required_module: str \| None`) in `TOOL_REGISTRY` (~50 entries). `ai_chat.py` derives everything from it: `openai_tools(names)`/`anthropic_tools(names)` (provider schema shapes), `tool_labels()`, `execute_tool(name, input, session, user) -> (json_text, is_error)` (dispatch — unknown names and executor exceptions become recoverable error payloads, never HTTP failures; results >`MAX_TOOL_RESULT_CHARS`=15k are truncated with a `truncated: true` wrapper), `filter_by_modules(names, enabled)` (drops tools whose module isn't installed). Executors wrap existing report functions directly — **watch the arg order**: hrm (`hrm_summary`, `attendance.get_summary`) and all `healthcare_reports` functions take `(user, session, ...)`, everything else `(session, user, ...)`. `find_customer`/`find_vendor`/`find_product`/`find_employee`/`find_patient`/`find_rso` are tenant-scoped `ilike` name→id lookups (10-match cap) that ID-requiring tools point to in their error messages. `list_report_sources` + `run_custom_report` expose `services/report_engine.run_report` (tenant-injected, field-whitelisted) as a generic ad-hoc query tool — source keys gated by module via `_REPORT_SOURCE_MODULES`, 50-row cap. `_json_safe` (moved here from ai_chat) converts Decimal→float and date/datetime→ISO. **Adding a tool = one `ToolDef` entry + granting it to an agent in `ai_agents.py`; module tools must also be added to the smoke test in `tests/test_ai_tools_modules.py` (a guard test fails otherwise).** |
| `services/` | Pure-logic modules — `posting.py` is the only GL writer; also `account_tree.py`, `deferred.py`, `depreciation.py`, `pdf.py`, `email.py`, `permissions.py`, `ai_providers.py`, `ai_agents.py`, `ai_tools.py` |
| `scripts/seed_demo.py` | Idempotent rich mock-data seeder (50+ per entity type). Exercises current features: data spans **two fiscal years**, transactions carry **voucher types** (SL/PU/CR/CP/CN/DN), the services tenant demonstrates **deferred-revenue origination with partial recognition**, and each tenant has **multiple users** (owner/accountant/clerk) with varied Audit-Log attribution. `_seed_purchase_store_chain` (manufacturing tenant only) exercises the full #137 P1/P2/P2b chain end-to-end: demands across every status, comparatives at lowest-wins/justify-required/pending-approval, POs at partial/full/short-received and billed/unbilled, a Gate Inward cancel-and-re-enter, and Gate Outward across all three source types including an approved scrap entry with real GL postings, plus **60 Store Issues** (manufacturing only, one page over the Issue Register's 50/page default — #150/#154) — every Purchases/Store screen and report has data on first login, and the Issue Register actually has a second page to click through. `_seed_notification_settings` turns on `email_notifications` for every demo tenant so `services/overdue.py`'s reminder scan runs its full per-customer grouping logic against the seeded overdue invoices rather than skipping every tenant outright (safe — `send_email()` no-ops without `SMTP_HOST`). **Gap-fill batch (2026-07-19):** every tenant also gets promo rules (bulk %/giveaway/category/invoice-value), commission plans + a 3-month `CommissionLedger` (draft→approved→posted with GL entry; ~half the posted invoices get `assigned_to_id` and periods anchor on the tenant's latest payment month so compute maths is non-zero), accounting periods (the only *locked* one is FY(year−3), which predates the 640-day data window so re-runs never trip posting.py's locked-period guard), two bank reconciliations (closed + open ~70% matched) and one imported bank statement (~60% matched) built from real GL activity on the main bank account; the PRA tenant gets a `PRASubmissionLog` trail (20 successes + 2 failed-then-retried). Still deliberately unseeded: `UserPermission` overrides (inert while `user_rights_enabled` is off), `AiChatSession` (per-user-private), `UserDashboardLayout`/`ApiKey`/auth-infra tables. |
| `scripts/autoseed_demo.py` | First-run demo loader: skips if any user already exists (brand-new empty DB only); no-ops when `SEED_DEMO=false` |

**Database:** SQLite (`backend/database.db`) in dev; PostgreSQL via `DATABASE_URL` in production. Dev still bootstraps via `SQLModel.metadata.create_all()`, but **Alembic migrations are now the source of truth** for schema changes (`backend/alembic/versions/`, revisions through `0029_purchase_demand_comparative`). New columns/tables: add to `models.py`, then `uv run alembic revision --autogenerate -m "..."` and `uv run alembic upgrade head`. **SQLite caveat:** Alembic can't `ADD CONSTRAINT` via ALTER — generated migrations adding FKs need the FK line removed and an existence guard added (see migrations 0016/0017 for the pattern). New tables get a `bind.dialect.has_table(...)` guard so they coexist with `create_all()`.

**Seeding:** On startup, `db.py` creates:
- A default `Tenant`, seeds a Chart of Accounts, and optionally creates an admin user from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` env vars
- Seven pre-seeded demo tenants (one per business model, incl. PRA retail + hospital) with placeholder users for immediate testing
- Delete `backend/database.db` to reset to seeded state

**Script installers run `alembic upgrade head` on every launch** (`install-and-run.*` and `run_packaged.py`) so updating to a newer version migrates the existing database forward in place — new columns/tables are added, existing data preserved.

**Installers auto-rebuild the frontend** when the current `git rev-parse HEAD` differs from the hash recorded in `frontend/.next/.built-commit`. This means any code update (via `update.sh`/`update.bat` or a plain re-run after a `git pull`) will recompile the UI — a stale build can never hide new features. Pass `--rebuild` (sh) / `-Rebuild` (ps1) to force a rebuild regardless.

**Update scripts:** `update.sh` (macOS/Linux), `update.bat` / `update.ps1` (Windows) — `git pull` then re-run `install-and-run.*`. Data directory (`~/.easy-books` / `%USERPROFILE%\.easy-books`) is never touched.

**Demo Tenants:**

| Context | Behaviour |
|---------|-----------|
| Dev / cloud (`dev.sh`) | Auto-created on first run; auto-populated with 50+ records per tenant each time `dev.sh` runs |
| Standalone *script* installers (`install-and-run.*`) | **Auto-load** the 7 fully-populated demo companies on first install (`SEED_DEMO=true` default, ~20–30 s one-time). Set `SEED_DEMO=false` for a clean install with no demo data. Mechanism: after `alembic upgrade head`, the installer runs `scripts.autoseed_demo` (guarded — any user already present → skip; also skips when `SEED_DEMO=false`). Updating an existing install is **migrate-only** — no demo data is added. |
| Desktop (Electron) | **Also auto-loads** the 7 demo companies on first install (`SEED_DEMO=true` default; `run_packaged.py` runs the guarded auto-seed before serving; the Electron shell shows a "Starting up… first-time setup may take ~30 seconds" splash during the one-time seed). Set `SEED_DEMO=false` for a clean desktop install. Updating an existing install is **migrate-only** — no demo data is added. |

Demo data is also loadable/removable at any time via **Settings → Sample / Demo Data** regardless of install type.

All seven demo tenants use password `demo1234`:

| Email | Model |
|-------|-------|
| `demo.simple@easy-books.app` | Simple |
| `demo.services@easy-books.app` | Services |
| `demo.trader@easy-books.app` | Trader |
| `demo.manufacturing@easy-books.app` | Manufacturing |
| `demo.telecom@easy-books.app` | Telecom Franchise |
| `demo.pra@easy-books.app` | PRA e-Invoice (Pakistani retail, PKR, PRA sandbox enabled) |
| `demo.hospital@easy-books.app` | Healthcare / Hospital (OPD/IPD/Lab/Procedures, 50 patients, 5 doctors, 4 wards) |

To run the rich mock-data seeder manually:
```bash
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
```

**API conventions:**
- All endpoints prefixed with `/api`
- DB dependency: `SessionDep = Annotated[Session, Depends(get_session)]`
- Auth enforcement: `CurrentUserDep = Annotated[User, Depends(get_current_user)]`
- Swagger UI available at `http://localhost:8000/docs` during dev

### Frontend (`frontend/`)

**Routing:** Next.js App Router. The `(dashboard)` route group wraps all authenticated pages. `DashboardLayout` checks `isAuthenticated()` and redirects to `/login` if needed.

**API layer:** `src/lib/api.ts` — `apiFetch(path, options)` auto-injects the `Authorization: Bearer` header from `localStorage` key `access_token`.

**Module System:** `ModuleContext` (`src/context/ModuleContext.tsx`) fetches `/api/modules` on app init and provides `installedModules: Set<string>`, `install(id, { seedSample? })`, `uninstall()`, `refresh()` via `useModules()`. Always contains `"base"` before fetch resolves (prevents sidebar flicker). **Add-ons-first UX:** public signup/login always starts with Base Accounting only; industry packs live on `/apps` (`addonPacks.ts` recommended packs + per-module cards). `OnboardingGuard` is a no-op; `/onboarding` and `/demo` redirect to `/apps?welcome=1` and `/login?demo=1` respectively. Optional `?seed_sample=true` on install seeds idempotent sample rows (`services/module_sample_data.py`). PRA home: `usePRAPortal` + `eb.home_dashboard` preference; widgets/quick-actions carry `requiredModule`. Nav items carry `forModule?: string` — Sidebar hides items whose module is not installed. `ALL_SECTIONS` in `nav.ts` controls sidebar section order; System section is last (after Payroll). Apps page at `/apps` (System → Apps, admin/owner only) is the module store. **`apps/page.tsx`'s `CATEGORY_ORDER` array is an allowlist, not just a sort order** — any module whose backend `MODULE_REGISTRY` category (`db.py`) isn't in that array is silently dropped from the page entirely (still counted in the "N of M installed" header, still installable via a raw API call, but no card and no Install button anywhere in the UI). `ai_assistant`'s `"Intelligence"` category was missing here from the module's introduction until 2026-07-14 — the only symptom was "the AI Assistant isn't reflected anywhere in the frontend," since every other AI Chat surface (FAB, nav link, `/agent` page) correctly gates on `installedModules.has("ai_assistant")` and a module that can never be installed through the UI never lights any of them up. When adding a new module category to `MODULE_REGISTRY`, add it to `CATEGORY_ORDER` in the same change, and add its `icon` string to `ICON_MAP` in the same file (also silently falls back to a generic icon, not a crash, if missed).

**Settings System:** `SettingsContext` (`src/context/SettingsContext.tsx`) fetches `/api/settings` on app init and provides settings app-wide via `useSettings()` hook. Settings include:
- `company_name` — displayed in header and reports
- `business_tagline` — shown below company name (e.g., "Easy-Books · Double-Entry Accounting")
- `currency`, `fiscal_year_start`, `financial_statement_date` — accounting preferences
- `week_start_day` — first day of the week (`monday` default) used by the report period presets ("This Week", "Last Week", etc.); set on Settings alongside `fiscal_year_start`, which drives the fiscal-year/quarter presets
- `invoice_prefix`, `bill_prefix` — document numbering
- `tax_id`, `email_notifications` — compliance and notifications
- `overdue_reminder_interval_days` (default `7`) — only takes effect when `email_notifications="true"`; throttles `services/overdue.py`'s daily aging-reminder email per tenant (one email per customer listing all their overdue invoices). The overdue status sweep itself (`Invoice.status → "overdue"`) and the reminder send both run from a background asyncio task wired into `main.py`'s FastAPI lifespan — fires once on boot, then every `OVERDUE_SWEEP_INTERVAL_HOURS` (env var, default 24); set `OVERDUE_SWEEP_ENABLED=false` to disable entirely (e.g. in tests, though the scheduler never runs under `TestClient` since no test invokes it as a context manager).
- `block_negative_stock` — when `true`, `consume_stock(block_negative=True)` raises HTTP 400 if a sale would drive `stock_qty` below 0 (default `false`; purchases are never blocked). `consume_stock` also accepts an optional `source_doc_type` override (default `"invoice"`) so non-sale consumers — Gate Outward's scrap approval — tag their own `StockMovement` rows correctly instead of being mislabeled as invoices.
- `require_purchase_chain` — when not `"false"` (default on), `POST /api/purchase-orders` rejects a bare PO once `purchase_store` is installed, unless it carries a `comparative_id` referencing an approved/converted `ComparativeStatement`; toggle only visible on the Settings page when `purchase_store` is installed
- `require_gate_inward` — when not `"false"` (default on), `convert-to-bill` requires full GI coverage once `purchase_store` is installed
- `leases_enabled` — when not `"false"` (default on), IFRS 16 leases UI/API at `/leases` is available (#256)

**Report period presets (#141):** `components/DateRangePicker.tsx` renders a QuickBooks-style preset dropdown (26 presets — Today/This Week/Last Month/Fiscal Quarter/…) ahead of the From/To inputs, keeping its original prop contract so all consumers get presets for free. Preset resolution lives in `lib/datePresets.ts` (`resolvePreset(id, { today?, fiscalStartMonth, weekStartDay? })` — pure, vitest-covered; `matchPreset` does the reverse mapping so a URL-restored range re-selects its preset); fiscal presets follow `fiscal_year_start`, week presets follow `week_start_day`. Picking a preset fills and disables From/To; "Custom" re-enables them. Report pages with hand-rolled date inputs were swept to use the shared component — new report filters should use `DateRangePicker`, not raw `<input type="date">` pairs.

**Company Branding:** Users customize their branding via `/dashboard/settings`:
- Company name appears in `Header` + `PrintHeader`
- Business tagline appears below company name in header and all printed documents
- All settings are persisted per-tenant via `/api/settings` PATCH endpoint

**Inventory nav section:** the sidebar exposes a dedicated **Inventory** group containing routes for Products (`/products` — has a **List / Tree** view toggle; Tree shows the Main→Sub→Item closing-stock valuation via `/api/reports/product-coa`), Product Categories (`/products/categories`), Product Ledger (`/products/ledger` — has a Location column and accepts `?product=<id>` to pre-select), and Inventory Performance (`/inventory/performance` — product names link into the ledger).

**Payroll nav section:** the sidebar exposes a dedicated **Payroll** group containing routes for Payroll Runs (`/payroll` — hub with KPI cards + recent runs table), Employees (`/employees` — searchable list with active/all filter), Attendance (`/attendance` — monthly grid view), and Salary Components (`/payroll/components` — inline-edit catalog). New employee (`/employees/new`), employee edit with Salary Structure tab (`/employees/[id]/edit`), run detail with approve/post/void actions (`/payroll/[id]`), and printable payslips (`/payroll/[id]/payslip/[eid]`).

**Purchases + Store nav sections (v3.3–v3.5, `purchase_store` module):** a dedicated **Purchases** group (`lib/nav.ts`) contains Demands (`/purchases/demands` — list/detail/new/edit, quotation entry at `/purchases/demands/[id]/quotations/new`), Comparatives (`/purchases/comparatives` — list/detail matrix builder with convert-to-PO), Gate Inward (`/purchases/gate-inward` — list/new/detail, `?po=<id>` pre-select), and the Gate Register + 3-Way Match reports. Purchase Orders and Goods Receipt are **dual-homed**: they carry `forModule: "purchase_store"` to also appear under Purchases, and the pre-existing Manufacturing-section copies gained `notForModule: "purchase_store"` so they hide once the module is installed (avoids listing the same route twice). A separate top-level **Store** group (added in v3.5 alongside Gate Outward — the first genuinely new top-level nav section since the module system shipped) contains Gate Outward (`/store/gate-outward`) plus its register and Dispatch Reconciliation reports; adding it required 7 distinct edits across `NAV`, `ALL_SECTIONS`, `TopNavSection.forModule`, `TOP_NAV`, `SECTION_PREFIXES`, `SUB_NAV`, and `getSectionHref` — a useful checklist when adding the next top-level section. `navVisible(item, installed)` in `nav.ts` is the single predicate consumers should use instead of ad-hoc `forModule` checks. **Any new nav item must land in both the sidebar `NAV` registry and the live `SUB_NAV`/`TOP_NAV` registries** — Gate Inward's initial PR only updated `NAV`, leaving it invisible in the actually-rendered top nav until a follow-up fix.

`/purchases` is now a hub page (`HubConfig` pattern, 4 KPIs + low-stock band + 6 action tiles) — the Purchases section header link changed from `/payable` to `/purchases` accordingly. The live registry for that link is `TopNav.tsx`'s `SECTION_OVERVIEW.purchases.href`, not `getSectionHref` in `nav.ts` — `getSectionHref` was also updated to match but its `purchases` entry is dead code, unread by any consumer; a reminder that this file's "stale doc trap" warning applies to source registries too, not just CLAUDE.md.

Store Issue lives under the **Store** nav section (`/store/issues`), not Purchases — it's the store-side consumption leg, same placement logic as Gate Outward.

**Section Hub Pages:** each major sidebar section has a command-centre hub page:
- `/receivable` — AR aging summary + top overdue customers (`AgingBand`)
- `/payable` — AP aging summary + top overdue vendors (`AgingBand`)
- `/inventory` — low-stock alerts + on-hand value (`LowStockBand`)
- `/banking` — live bank-account balances from the GL (`AccountListBand`)
- Generic renderer: `components/hub/HubPage.tsx` driven by `lib/hubConfigs.ts` (`HubConfig` objects with `title`, `bands[]`). Sidebar section headers navigate to the hub via `TITLE_MAP` in `(dashboard)/layout.tsx`.

**Collapsible sidebar (`components/Sidebar.tsx`):**
- 3-state behaviour: **collapsed** (icon strip) / **open** (labels) / **pinned** (always open) stored in `localStorage` key `eb.sidebar.pinned` (`"1"` / `"0"`) and `eb.sidebar.open`.
- Hover over the collapsed strip opens a floating panel with full nav labels; leaving closes it.
- Auto-pins on wide screens (`window.innerWidth >= 1280`).
- Backdrop `div` starts at `top-12` (below the header) to avoid covering it; `z-index` layering: header `z-50`, sidebar `z-40`, backdrop `z-30`.

**Auto-hide SubNav (`components/SubNav.tsx`):**
- Secondary section sidebar (left of main content); shows sub-items for the active TopNav section.
- **Collapsed (icon-only):** 52 px wide — shows only icon + `title` tooltip; expands on hover via CSS `width` transition (200 ms ease).
- **Expanded:** 200 px wide — shows icon + label; triggered by mouse hover or pin.
- **Pin/unpin:** chevron button at the bottom toggles `eb.subnav.pinned` in `localStorage`; pinned sidebar stays expanded regardless of hover.
- Width transition done via inline `style={{ width: expanded ? 200 : 52, transition: "width 200ms ease-in-out" }}` (not Tailwind width classes — those don't transition).
- Returns `null` when no sub-items exist for the active section (dashboard, report builder, etc.).

**3-mode voucher form (`app/(dashboard)/journal/new/page.tsx`):**
- Mode selector at top: **Journal** (JV) / **Payment** (CP cash, BP bank) / **Receipt** (CR cash, BR bank).
- Payment mode: GL picker pre-filters to Cash/Bank accounts for the instrument side; payee field shown.
- Receipt mode: mirror of Payment with reversed Dr/Cr orientation.
- JV prefix auto-sets per mode (CP-YYYY-seq, BP-YYYY-seq, CR-YYYY-seq, BR-YYYY-seq, JV-YYYY-seq).
- Distinct print templates: PV (Payment Voucher) for CP/BP, RV (Receipt Voucher) for CR/BR, standard JV template for JV.

**Print system:**
- **`PrintHeader` (`components/PrintHeader.tsx`):** accepts `orientation?: "portrait" | "landscape"`. When `"landscape"`, a `useEffect` dynamically injects `<style data-print-landscape>@media print { @page { size: A4 landscape; margin: 12mm 15mm; } }</style>` and removes it on unmount. Portrait is the default via `globals.css` (`@page { size: A4 portrait; }`). **Do NOT use CSS classes to control `@page` size** — they have no effect in standard CSS.
- **Orientation rules:** landscape for wide tables (aging, performance reports, product ledger, journal list, invoices/bills list, customer/vendor ledgers); portrait for all other pages (GL, cash/bank book, statements, trial balance, balance sheet, P&L, cash flow, voucher prints, CoA).
- **Date formatting (always use these — never `toLocaleDateString()` or raw ISO strings):**
  - `fmtDate(str: string)` in `src/lib/utils.ts` — converts ISO `"YYYY-MM-DD"` or datetime string → `"dd-mm-yy"`. Splits on `"T"` first to handle datetimes.
  - `fmtDateJs(date: Date)` — converts a JS `Date` object → `"dd-mm-yy"`.
- **Print hygiene classes:**
  - `print:hidden` — hides filter controls, pagination, sort handles, toolbar buttons, action columns, checkbox columns.
  - `@media print { td span, th span { ... } }` in `globals.css` flattens any badge pills to plain text.
- **Column alignment in report tables:** add `whitespace-nowrap` to Date and JV#/Doc# `<td>` cells; do NOT add `max-w-xs` to description cells (let the table manage remaining width naturally).
- **Voucher type badges:** do NOT add inline type badges (`<span>` pills) next to JV numbers in any report table. The JV number prefix already encodes the type (CP = Cash Payment, SL = Sales, BR = Bank Receipt, etc.).
- **Amount formatting:** negative amounts display as `(1,234.56)` via the `fmt()` helper from `useFmt()`; currency code appears once in the column header, not in each cell.

**Freeze panes (report tables):**
- `.table-freeze` on the div directly wrapping a `<table>` gives it a bounded scroll viewport (`max-height: var(--table-freeze-h, calc(100dvh - 240px))`) so the sticky `<thead>` (and sticky `<tfoot>` totals row) actually engage — a plain `overflow-x-auto` wrapper never scrolls vertically, so sticky headers were a no-op inside it. Add `.freeze-col` on the same wrapper to also pin the first column. Rules live in `globals.css` (FREEZE PANES block) and are all reset under `@media print`; any new sticky rule must be added to that print reset too.
- Applied on: aging AR/AP, customer/inventory performance, GL ledger, product ledger, report-builder grid, healthcare + manufacturing reports, customer/vendor statements, telecom tracker, Purchases/Store (demands/comparatives/gate-inward/gate-outward + their registers/3-way-match/dispatch-reconciliation reports), Trial Balance, Budget vs Actual (both tabs), Fixed Assets, Audit Log, Period Close, Attendance Report, PRA Submission Logs (#127 second follow-up pass). Div-based report pages (cash-book, bank-book, cashflow, tax reports, deferred-revenue, report-builder's own summary view) have no `<table>` and are not covered. Income Statement (`/pl`) and Balance Sheet (`/balance`) single-period tree tables gained real `<thead>` column headers (Account / Amount·Balance) + `.table-freeze` in 2026-07-14's leftover batch — the former known gap is closed; their comparison-mode flex layouts remain header-less by design.

**Report pagination (#150/#154):** the five Purchases/Store registers (Gate Register, 3-Way Match, Gate Outward Register, Dispatch Reconciliation, Issue Register) return `{total, items}` instead of a bare array — `skip`/`limit` and an `ilike`-backed `q` search param are pushed into SQL rather than filtered in Python. Frontend pages consume this via the shared `components/Pagination.tsx` (50/page; renders nothing when `totalPages <= 1`) and reset to page 1 on any filter change. New report list endpoints with unbounded row counts should follow this shape, not the older bare-array + client-side-filter pattern still used by Vendor Performance and Stock Tie-out.

**Dashboard KPI cards:** use the shared `components/dashboard/KpiCard.tsx` for any dashboard stat tile — props: `title`, `value` (null → shimmer), optional `icon` (layout switches: icon top-left/title bottom-left/value bottom-right vs. title top-left/value bottom-right), `tone` (`green|red|amber|emerald|blue|neutral` colored-tile variants), `href` (renders a Link), `sub`, `badge`, `iconClass`, `valueClass`. Do not hand-roll per-card markup or hardcode hex colors — neutral tone uses CSS theme variables for dark-mode compatibility.

**Universal Search (`components/GlobalSearch.tsx` + `lib/navIndex.ts` + `routers/search.py`):**
- `GlobalSearch` — `Ctrl+K` / `⌘K` command palette rendered via `createPortal` at `document.body`; also opened by TopNav search button (dispatches `window.CustomEvent("search:open")`). Three-tier search: (1) open tabs via `useTabs()` — 0 ms; (2) static nav index — 0 ms; (3) API via `GET /api/search` — 150 ms debounce. Keyboard: ↑↓ navigate, ↵ open, Esc close. Recent searches stored in `localStorage` (`eb.recent-searches`, max 5). Results show status badges (draft=amber, posted=blue, paid=green) and amount pills.
- `lib/navIndex.ts` — three-layer static index: all sidebar nav pages (from `NAV`), 14 quick-action "New…" forms, 22 report/utility pages with keyword aliases. `searchNav(q, limit)` returns scored results (label-start=3, label-contains=2, sub=1, keyword=0). `SEARCH_PREFIXES` maps `inv:` → `"invoices"`, `tab:` → `"__tabs__"`, `rpt:` → `"__reports__"`, etc.
- `routers/search.py` — `GET /api/search?q=&limit=&types=` — searches 8 entity types, all tenant-scoped. `types` param (comma-separated) filters to specific entities (used by prefix routing). Expanded columns: Invoice (description, notes, status, issue_date), Employee (designation, cnic, bank_name), Transaction (reference, notes, date, voucher_type), Product (unit, product_type), Customer (address, ntn, cnic). Returns `{..., date?, amount?, status?}` per row for rich UI display. Import: `from sqlalchemy import or_` (NOT from sqlmodel); `from .common import SessionDep` (NOT from db).

**AI Chat (multi-provider, #117):** `components/ai/ChatCore.tsx` is the shared chat-thread component (message list, composer, model dropdown, tool-progress indicators, mid-stream error banner) used by both surfaces: the Sparkles FAB (`components/AIChat.tsx` + `AIChatButton.tsx`, `createPortal` popup panel rendered in `(dashboard)/layout.tsx`, hidden unless the `ai_assistant` module is installed via `useModules()`) and the full-page `/agent` route (`app/(dashboard)/agent/page.tsx` — two-column layout with a session sidebar: new/rename/delete chats, resumes the most recent session on load, 403-from-`/api/ai/models` renders an "install the module" empty state instead of erroring). Both surfaces persist chat history server-side per-user (no more session-only history) and stream replies token-by-token. `lib/aiStream.ts` (`streamChat()`) is a raw-`fetch` SSE reader (not EventSource, since it needs to POST a body + auth header) that parses the backend's `stage`/`token`/`tool_start`/`tool_end`/`done`/`error` frames and guards against a connection reset after a terminal frame double-firing the error handler. **Assistant replies render as Markdown** (2026-07-17, `components/ai/ChatMarkdown.tsx` — `react-markdown` + `remark-gfm`; no markdown renderer existed in this frontend before) with `table`/`thead`/`th`/`td`/`h2`/`h3`/`strong` overrides styled against the app's own theme vars instead of browser defaults — both the finished-message bubble and the live-streaming bubble go through it; user messages stay raw `whitespace-pre-wrap` text. The new `stage` frame (backend's Triage/Specialist/Reviewer/Drafting pipeline-progress labels, e.g. "Routing your question…" / "Reviewing figures…") reuses the *same* single `toolLabel` state `tool_start`/`tool_end` already drove — no new UI, just an extra label source; the first real `token` also clears it, so a "Drafting your report…" label disappears the instant the final answer starts streaming, without a separate stage-end frame. The `done` frame carries a `reply` field (the backend's authoritative final text) that `ChatCore`'s `onDone` handler commits in preference to its own locally-accumulated `streamingRef` buffer — a 2026-07-14 fix: when a model finishes a turn having only ever emitted `tool_calls` with zero content deltas, `ai_chat.py` falls back to a fixed "I wasn't able to..." string for the persisted message, but that text was never streamed as `token` events, so the old code (which trusted only the accumulated token buffer) committed a blank assistant bubble even though a real reply existed in the DB. Provider/model keys are configured per-tenant on **Settings → AI** (`app/(dashboard)/settings/page.tsx`, Advanced tab, admin/owner only): one card per cloud provider (anthropic/openai/gemini) with a masked key-status badge (from `GET /api/ai/key-status`, admin-only), write-only key input, default-model picker, and the `ai_rate_limit_per_hour` field. Ollama gets its own card below the cloud providers — a server-URL text input (`ai_ollama_base_url`) plus a tag-input (Enter or `,` to add, × chip to remove) for locally-pulled model names (`ai_ollama_models`, comma-joined in storage); both are plain settings (not secrets) so, unlike the cloud keys, they round-trip and pre-fill on reload. The Default Model `<select>` appends `Ollama (Local) — <tag>` options once at least one is tagged. Backend counterpart: `routers/ai_chat.py` + `services/ai_providers.py`. Anthropic default model is `claude-sonnet-5` (2026-07-14) — Sonnet 5 runs adaptive thinking ON when the `thinking` param is omitted (a silent behavioral change from `claude-sonnet-4-6`, which ran thinking-off by default), and thinking output would otherwise share the reply's fixed `max_tokens=2048` budget, so `ai_chat.py`'s `litellm.acompletion` call explicitly sends `thinking: {"type": "disabled"}` gated to `litellm_model.startswith("anthropic/")` only (openai/gemini reject the unknown kwarg). `ChatCore` takes an optional `onFirstMessageSent` callback, fired once per session right after its first turn completes — the backend auto-titles a session from its first message, so `/agent`'s sidebar wires this to a session-list refetch (without it the sidebar stayed on "New chat" forever, since nothing else re-fetches after send). The composer `<textarea>` auto-grows up to `max-h-24` via a `scrollHeight`-driven resize effect on the `input` value — `rows={1}` alone never grows past one line even with the right Tailwind classes present. The FAB popup panel is drag-anywhere + minimizable via the shared `hooks/useDraggablePanel.ts` (below).

**Draggable/minimizable floating panels:** `hooks/useDraggablePanel.ts` is a shared hook (`{ panelRef, pos, minimized, dragging, startDrag, toggleMinimized }`) backing every floating widget panel — currently the AI Assistant FAB popup (`components/AIChat.tsx`) and the global Calculator (`components/Calculator.tsx`). Position/minimized state is a per-browser UI preference in `localStorage` (keyed `<storageKey>.pos` / `<storageKey>.minimized`, e.g. `eb.aichat.*` / `eb.calculator.*`) — not tenant data, so it's never sent to the backend. `pos` stays `null` until the user drags at least once; consumers render their own default CSS corner while `null` and switch to inline `style={{ left, top }}` once a drag has happened. `startDrag` is meant to be wired to `onPointerDown` on whatever element is the drag handle (a header bar) and bails out early if the pointer-down landed on a `<button>` inside it, so header action buttons (close/minimize/new) still get their own click. Dragging is clamped to the viewport on every move and re-clamped on window resize. Minimizing hides the panel body via a `hidden` class rather than unmounting it, so an in-flight AI stream or the current calculator entry isn't lost. **Calculator** (`components/Calculator.tsx` + `CalculatorButton.tsx`, globally available — no module gate, unlike the AI Assistant FAB) is a standard 4-function calculator (+ − × ÷, %, ±, C, backspace) with a 12-digit display cap (`formatResult()` falls back to `toExponential` for results too large/small to fit). Its FAB is intentionally stacked **above** `AIChatButton` on the same right edge (`bottom-36 right-4 md:bottom-24 md:right-20`), not bottom-left — bottom-left collides with Next.js's own dev-mode route-indicator badge in local development (dev builds only, but real: a `force`-clicked Playwright test landed on the Next.js overlay instead of the button before this was moved).

**In-app auto-update system:**
- `components/UpdateAvailablePopup.tsx` — bottom-sheet/card shown when `update_available`; "Update Now" / "Later" (session dismiss via `sessionStorage eb.update-later-session`) / "Skip version" (SHA-keyed persist via `localStorage eb.update-skip`)
- `components/UpdateProgressScreen.tsx` — fullscreen portal overlay during update; animated SVG ring + Zap icon; 4-phase progress indicator (Pull → Compile → Bundle → Start); progress bar `Math.min((elapsed/120)*100, 90)%`; calls `POST /api/system/update` → polls `/version.json` every 5 s; on commit hash change sets `localStorage eb.just-updated`, fetches changelog from `GET /api/system/update/changelog?since=<sha>`, reloads after 4.5 s; success/error states
- `(dashboard)/layout.tsx` — auto-checks `/api/system/update/status` on every mount for admin/owner via `useEffect`; shows popup unless dismissed; reads `localStorage eb.just-updated` on mount to display post-update congratulations toast (8 s auto-dismiss)
- `backend/routers/system_update.py` — `GET /api/system/update/status` polls GitHub Commits API (not Releases); `POST /api/system/update` runs git pull + migrate + rebuild in background; `GET /api/system/update/changelog?since=<sha>&limit=8` returns recent git log entries
- `desktop/` + `UpdateModal.tsx` — **Settings → Check for Updates** modal for Electron (uses `electron-updater` IPC bridge) and script installs (shows CLI commands); "Commit" row shows live `git rev-parse HEAD` from API (not stale build-time env var)

**react-grid-layout (dashboard grid):** Import from `react-grid-layout/legacy` (v2 API, self-typed). Do NOT add `@types/react-grid-layout` — v2 ships its own types. v1 is unusable under React 19 (`findDOMNode` removed). `Layout` = array, `LayoutItem` = single item.

**Dashboard layout store:** Schema v3 `{version:3, layouts:{lg:GridItem[], sm?:GridItem[], xs?:GridItem[]}}` — `lg` is canonical; `sm`/`xs` are sparse overrides created only on first drag/resize at that width. `BP_COLS={lg:4,sm:2,xs:1}` exported from `hooks/useDashboardLayout.ts`. Migration chain in `resolveLayout` handles v1/v2/v3/garbage. `onDragStop`/`onResizeStop` alone call `markCustomized` — `onLayoutChange` updates but never creates overrides.

**UI conventions:**
- Icons: `lucide-react` only
- Styling: Tailwind CSS v4 with `tailwind-merge`
- Brand colors: Background `#f6f3ee` (cream), Accent `#b8943f` (gold), Text `#1a1814` (charcoal)
- Fonts: DM Sans (UI), DM Serif Display (headings)

### Multi-Tenancy

Every data model includes `tenant_id`. Unique constraints (account codes, JV numbers) are tenant-scoped, not global. The JWT payload carries both `sub` (email) and `tenant_id` — never query accounting data without filtering by `tenant_id`.

### Double-Entry Bookkeeping Invariant

`sum(debit) == sum(credit)` must hold for every posted transaction. This is validated in `POST /api/transactions` before any DB write. `JournalEntry` rows store separate `debit` and `credit` float fields; exactly one must be > 0 per line.

---

## Environment Variables

**Backend** (`backend/.env`):
```
DATABASE_URL=              # PostgreSQL (production); omit to use SQLite
JWT_SECRET_KEY=            # openssl rand -hex 32
FRONTEND_ORIGIN=http://localhost:3000
SEED_ADMIN_EMAIL=
SEED_ADMIN_PASSWORD=
SEED_COMPANY_NAME=
ANTHROPIC_API_KEY=         # AI Financial Assistant (#117): dev/demo fallback for the anthropic provider ONLY, used when a tenant has no key of its own in Settings → AI. Per-tenant keys (any of anthropic/openai/gemini) set via the UI take priority; endpoint returns 503 only when no provider is configured at all (neither this env var nor any tenant key).
OVERDUE_SWEEP_ENABLED=     # default true; set "false" to disable the background overdue-invoice sweep + reminder scheduler (services/overdue.py, wired in main.py's lifespan)
OVERDUE_SWEEP_INTERVAL_HOURS=  # default 24; how often the scheduler tick runs (it also fires once immediately on boot)
```

**Frontend** (`frontend/.env.local`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Important Constraints

- **Next.js 16 breaking changes** — APIs and file conventions differ from earlier versions. Before writing frontend code, check `node_modules/next/dist/docs/` and heed `frontend/AGENTS.md`.
- **Tenant isolation** — always filter by `tenant_id`; missing this silently leaks cross-tenant data.
- **Debit/credit balance** — validate totals before any transaction commit.
- **JWT payload** — must include both `sub` and `tenant_id`; auth middleware depends on both fields.
- **Migrations via Alembic** — for schema changes run `uv run alembic revision --autogenerate` then `uv run alembic upgrade head`. `create_all()` still runs in dev for zero-setup boot, so new-table migrations must guard with `bind.dialect.has_table(...)`. SQLite cannot `ADD CONSTRAINT`, so strip auto-generated FK lines on ALTER (app-level tenant checks enforce integrity).
- **WSL2 npm issue** — `dev.sh` resolves the Linux node binary automatically; never invoke Windows `npm` inside WSL2 paths.
- **Date display** — always use `fmtDate()` / `fmtDateJs()` from `src/lib/utils.ts`; never use `toLocaleDateString()` or render raw ISO strings in the UI. Output format is `dd-mm-yy`.
- **Print orientation** — set `orientation="landscape"` on `<PrintHeader>` only for wide multi-column tables; leave it unset (portrait) for everything else. The prop works via dynamic `<style>` injection in `useEffect` — CSS classes cannot control `@page` size.
- **No voucher-type badges in tables** — the JV number prefix (CP / SL / BR / JV etc.) already identifies the type. Adding a separate badge span is redundant and was intentionally removed.

---

## Adding Common Features

**New report:**
1. Add FastAPI endpoint in the appropriate `backend/routers/` file (or `routers/reports.py`) using `select()` with tenant filter.
2. Create `frontend/src/app/(dashboard)/[report-name]/page.tsx`.
3. Use `apiFetch` for data; `react-chartjs-2` for visualizations.

**New transaction type:**
1. Validate `sum(debit) == sum(credit)` in the endpoint.
2. Generate a unique `jv_number` per tenant.
3. Insert one `Transaction` + N `JournalEntry` rows atomically.

**New account type:**
1. Update `Account.type` documentation/enum.
2. Add seeding defaults in `db.py` if needed.
3. Update any report aggregation logic that groups by account type.

**Customize company branding/settings:**
1. Add new setting key to `AppSettings` interface in `frontend/src/context/SettingsContext.tsx`
2. Add default value to `defaults` object in same file
3. Add field to `SettingsUpdate` model in `backend/routers/settings.py`
4. Add UI input field to `frontend/src/app/(dashboard)/settings/page.tsx`
5. Display setting value where needed (Header, PrintHeader, etc.) using `useSettings()` hook
6. Settings are auto-persisted via `/api/settings` PATCH endpoint — no additional backend logic needed

**New printable report page:**
1. Add `<PrintHeader title="..." subtitle={fmtDate(date)} orientation="landscape" />` at the top of the page (set `orientation` only if the table is wider than ~6 columns).
2. Import `fmtDate` from `@/lib/utils` and apply to every date cell — never render raw ISO strings.
3. Wrap all toolbar / filter / pagination UI in `print:hidden` or the `<div className="print:hidden">` pattern.
4. In report tables: add `whitespace-nowrap` to Date and JV#/Doc# `<td>` cells; let Description cells have no `max-w-*` so they absorb remaining width.
5. Do not add amount currency symbols per-cell; put the currency code in the `<th>` header once.
6. Use the `fmt()` helper from `useFmt()` for all amounts — it handles parenthesis-negative and decimal places automatically.

**New section hub page:**
1. Add a `HubConfig` entry in `frontend/src/lib/hubConfigs.ts` with `{ id, title, bands[] }`.
2. Each band is one of `AgingBand`, `LowStockBand`, `AccountListBand` from `components/hub/`.
3. Create `frontend/src/app/(dashboard)/[section]/page.tsx` rendering `<HubPage config={myConfig} />`.
4. Add an entry to `TITLE_MAP` in `frontend/src/app/(dashboard)/layout.tsx` so the breadcrumb and page title resolve.
5. Make the sidebar section header `<Link href="/[section]">` so clicking it navigates to the hub.
