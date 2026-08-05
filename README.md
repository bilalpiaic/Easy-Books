# Easy-Books

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Easy-Books** is a multi-tenant double-entry bookkeeping SaaS for SMEs. Everyone starts on **Base Accounting**; industry capabilities (Inventory, Manufacturing, Telecom Franchise, PRA e-Invoice, Healthcare, Weaving, Yarn Spinning, AI Assistant, …) are **Add-ons** installed after login from System → Add-ons. IAS/IFRS-aligned accounting with an enforced ∑Dr = ∑Cr invariant and live reports from the General Ledger.

Stack: FastAPI + SQLModel (backend) · Next.js 16 + React 19 + Tailwind v4 (frontend) · SQLite for dev/local, PostgreSQL for production.

---

## Feature highlights

**Accounting core**
- **Multi-level Chart of Accounts** — group/parent accounts with child leaves (the default CoA every tenant gets is hierarchical); posting is restricted to active leaf accounts, and parent balances roll up automatically
- Double-entry GL with `services/posting.py` as the single, invariant-enforcing write path
- **Voucher series** — typed vouchers (Sales / Purchase / Receipt / Payment / Journal / Credit-Note / Debit-Note) with per-type numbering, plus Cash Book & Bank Book views
- Decimal money throughout (`NUMERIC(18,4)`, banker's rounding) — no floating-point drift
- Weighted-Average inventory costing (IAS 2); optional FIFO per tenant
- Tax codes catalog with per-line GL posting (output vs input VAT/GST)
- Multi-currency documents with exchange-rate catalog and FX revaluation (IAS 21)
- Payment allocations: one payment settles multiple invoices/bills with partial amounts
- Payment terms (Due on Receipt, Net 15/30/60) with auto-calculated due dates
- Period close — posts closing JV (Revenue/Expense → Retained Earnings), locks the period, materialises `AccountBalance` cache; `/reopen` unlocks
- Recurring journal entries (daily/weekly/monthly/quarterly/yearly) with a run-due endpoint
- Overdue auto-flag on invoice/bill fetch; reversal unwinds allocations and COGS sub-JVs

**AR / AP**
- Invoicing and bills with draft editing **and posted-document editing** (reverse-and-repost; blocked once paid; honours the negative-stock guard on edit), bulk actions (mark-sent, void, delete)
- Sales Returns via Credit Notes (restocks inventory, reverses COGS — IAS 2 / ISA 240)
- Purchase Returns via Debit Notes (returns stock at original cost — IAS 2.11)
- Customer & vendor advances; apply against invoices/bills through the allocation flow
- Customer and vendor statements (printable, any date range)
- Per-document notes (customer-facing) and internal memo (staff-only)

**Inventory & stock**
- 2-level product categories (parent → sub-category) seeded per business model; assign on product form, filter in list
- **On hand: N** shown on invoice/bill line items; optional **Block overselling** setting prevents negative stock on sales (`block_negative_stock`, default off — purchases are never blocked)
- Per-product stock card with running qty and value; drill-down from every GL line
- Stock reserved/available tracking on sales; COGS sub-JV posted at shipment
- Dedicated **Inventory** sidebar section: Products, Product Categories, Product Ledger, Inventory Performance

**Banking**
- Bank account balances derived live from the GL
- CSV statement import with SHA-256 de-duplication and auto-match to existing JVs
- Per-period bank reconciliation with line matching and lock-on-close

**Reports (all live from the GL)**
- Trial Balance, General Ledger (with **Opening / Closing Balance** on date-filtered views), Income Statement, Balance Sheet, Cash Flow (indirect)
- **Hierarchical statements** — Trial Balance, Balance Sheet and P&L roll up over the multi-level CoA with parent subtotals, expand/collapse, and click-through drill-down from a leaf line into its ledger and on to the voucher (`services/account_tree.py`)
- Comparative-period P&L and Balance Sheet (IAS 1.38)
- **AR Aging** & **AP Aging** — dedicated pages (`/aging/receivable`, `/aging/payable`) with Current/1–30/31–60/61–90/90+ buckets and drill-down to the customer/vendor ledger; bucket summary cards are **clickable filters** — click a bucket to filter the detail table, click again or *Show all* to reset
- **Product Ledger** (`/products/ledger`) — stock movements + running qty per product, single-store or consolidated
- **Inventory Performance** (`/inventory/performance`) — on-hand qty, on-hand value, low-stock flag, last movement, units sold + COGS
- **Customer Performance** (`/customer-performance`) — revenue, invoice count, outstanding AR, avg days-to-pay, ranked
- Customer/Vendor sub-ledgers, Stock Card
- Tax Summary (GST output/input), Analytic P&L (cost-centre dimension)
- Budget vs Actual with monthly per-account variance
- **Report Builder** — user-configurable reports (column chooser, click-to-filter, grouping/totals, saved views, CSV/XLSX export), backed by a whitelisted data-source registry + tenant-safe report engine on the backend
- **Freeze panes (v3.1)** — table reports scroll inside a bounded viewport with a sticky header row and sticky totals row (`.table-freeze`); wide reports also lock the first column (`.freeze-col`) — Excel-style scrolling on aging, ledgers, performance and industry reports

**Dashboard (v2.5+ / dual-home v4)**
- **Two homes per tenant** — **Financial** (P&amp;L / cash / AR-AP) and **Operations** (purpose-built industry KPIs), toggled on `/dashboard` and preferred via Settings → Advanced → Home dashboard (`eb.home_dashboard`)
- Per-user drag-to-arrange, resize, show/hide widgets — **each home saved independently** via `/api/dashboard/layout` (schema v4 dual-slice JSON; v1–v3 migrate under Financial)
- Responsive 2D grid (react-grid-layout) — 4-col desktop / 2-col tablet / 1-col phone; per-breakpoint layouts per home
- **Operations widgets** — ops KPIs / pipeline / alerts plus Spinning, Weaving, Production WIP, Healthcare census, Telecom tracker, Purchases pipeline, Textile Processing tiles (module-gated); aggregate API `GET /api/dashboard/operations-summary`
- **Shortcut tiles** — pin any nav page as a dashboard tile with live metric badge (count / total); Quick Actions differ per home
- **Data widgets** — opt-in Bank Balances, Top Products, Inventory Summary; Top Customers and Top Products show the **top 10** entries
- **Net Worth Trend (v3.1)** — combo chart widget: Assets as upward bars, Liabilities as downward bars around a zero axis, Net Worth as an overlaid line; 3M/6M/1Y/All range selector
- **Unified KPI cards (v3.1)** — shared `KpiCard` component (tone variants, icon/no-icon layouts, dark-mode-safe theme variables)
- **Staff Rights** — `dashboard.financial` / `dashboard.operations` resources in the User Rights matrix
- **Cash-flow tie-out** — reconciling row on the Cash Flow statement shows ✓ (balanced) or amber delta per IAS 7

**Navigation & UX (v2.7)**
- **Section Hub Pages** — `/receivable`, `/payable`, `/inventory`, `/banking` each open a command-centre view: aging summary band, low-stock alert band, or live bank-balance list; sidebar section headers navigate there directly
- **Collapsible sidebar** — 3-state behaviour (collapsed / open / pinned); hover expands with tooltip nav; auto-pins on wide screens; state persisted in `localStorage`
- **3-mode voucher form** — New Entry supports Journal, Payment (CP/BP), and Receipt (CR/BR) modes; mode-specific GL pickers pre-filter Cash/Bank accounts; voucher prefix auto-applies per mode (CP-0001 / BP-0001 / CR-0001 etc.)

**Universal Search & Navigation (v3.0)**
- **Ctrl+K command palette** — `GlobalSearch` portal overlay; 3-tier architecture: open browser tabs (0 ms), static nav/form/report index (0 ms), API data search (150 ms debounce); keyboard navigation (↑↓ navigate, ↵ open, Esc close)
- **Prefix filter syntax** — type `inv:`, `cust:`, `bill:`, `acc:`, `emp:`, `jv:`, `tab:`, `rpt:`, `new:` to scope results to a single entity type or category; prefix chips are shown as hints in the empty state
- **Rich search results** — invoices and bills show status badge (color-coded) + amount; all results highlight the matching portion of the query; recent searches (top 5) stored in `localStorage` and shown as one-click chips
- **Expanded search columns** — invoices searched across number, customer name, description, notes, status, and date; employees searched across name, code, department, designation, CNIC; transactions across JV#, description, party, reference, date, and voucher type
- **Nav index** — 3-layer static index: all sidebar pages, 14 quick-action "New…" forms, 22 report/utility pages with keyword aliases (e.g. type "tb" to reach Trial Balance, "p&l" for Income Statement, "gst" for Tax Reports)
- **TopNav portal dropdowns** — all dropdown panels rendered via `createPortal` at `document.body` with `position: fixed` from `getBoundingClientRect()`, avoiding overflow-x scroll container clipping; scrollable tab strip with left/right chevron arrows; every dropdown item — including the section Overview row and mobile More-drawer items — renders as **icon + label** with uniform weight (v3.1)
- **Dark nav inversion** — nav bar renders in cream/charcoal in dark mode (inverted vs the light theme), giving distinct visual contrast between navigation and page content

**In-app Update System (v3.0)**
- **Auto-check on login** — admin/owner users see an `UpdateAvailablePopup` automatically when a newer commit is on the `main` branch (detects via GitHub Commits API, not Releases — catches every push)
- **Dismiss options** — "Update Now" launches the progress screen; "Later" dismisses for the session; "Skip version" dismisses permanently for that commit SHA (stored in `localStorage`)
- **Animated progress screen** — fullscreen overlay with spinning SVG ring, 4-phase indicator (Pull → Compile → Bundle → Start), progress bar, polls `/version.json` every 5 s waiting for the rebuilt server to come back up
- **Post-update congratulations toast** — after reload, shows `from → to` commit hash with a "What's New" changelog pulled from `GET /api/system/update/changelog`

**UI & Accessibility (v2.7)**
- **Dark Mode + Themes** — 3 display modes (Light / Dark / System follows OS preference) × 5 color themes (Gold / Emerald / Sapphire / Rose / Slate); theme icon in the header cycles modes; color swatches in **Settings → Appearance**; persisted in `localStorage` (`eb.theme`, `eb.color`); anti-flash script in `layout.tsx` prevents FOUC
- **Multi-language support** — English, Urdu (اردو, RTL Nastaliq script), Chinese (中文); globe icon in header opens language dropdown; preference saved in `localStorage` (`eb.lang`) and synced to `/api/settings` (`app_language`); 314 translation keys across 10 namespaces covering all pages, status badges, action buttons, and table headers; RTL layout auto-applied for Urdu; `react-i18next` + `i18next` client-side only
- **Mobile responsiveness** — sidebar width trimmed to 196 px; page titles, stats grids, aging grids, and form grids all apply responsive breakpoints so the UI stacks cleanly on phones; button toolbars wrap on narrow screens; line-item tables scroll horizontally; 61 files updated

**Print system (v2.7, overhauled v3.1)**
- **Dot-matrix format** — all print output is **Courier New** black-and-white, no background fills; `@media print` strips UI chrome (buttons, filters, pagination, sort handles, checkbox columns, action columns)
- **Font-size caps** — Tailwind v4 font-size CSS variables are overridden in print so screen sizing never leaks into printouts; row spacing is compressed for denser data fit per page
- **Date format** — `dd-mm-yy` used everywhere (e.g. `20-06-26`); `fmtDate()` / `fmtDateJs()` helpers in `utils.ts`
- **Portrait / landscape auto-selection** — PrintHeader injects the correct `@page { size: A4 … }` rule via `useEffect`; landscape for wide tables (aging, performance, product ledger, **General Ledger**, journal list), portrait for everything else
- **Freeze-pane reset** — all `.table-freeze`/`.freeze-col` sticky positioning is neutralised under `@media print` so reports always paginate in full
- **Currency prefix** — amount column headers show the currency code once; individual cells contain bare numbers
- **Negative amounts** — displayed as `(1,234.56)` throughout; debit/credit columns use `—` for the zero side
- **Column alignment** — Date and JV# cells are `whitespace-nowrap`; Description absorbs remaining width via natural table flow

**Advanced features**
- Fixed Assets register + straight-line/reducing-balance depreciation (IAS 16); **assets depth (#258)** — componentization, impairment/reversal, disposal, rollforward (`/assets/rollforward`)
- Purchase Orders (raise → approve → convert-to-bill, 3-way match)
- Deferred revenue recognition (IFRS 15) — flag a product `is_deferred` and its invoice lines post to Deferred Revenue (2300) and originate a recognition schedule; the recognition run releases revenue over the term, and editing a posted deferred invoice rebuilds the schedule (or is blocked once recognition has begun)
- **IFRS 15 remainder (#259)** — relative-SSP multi-element allocation + contract assets (1140); UI `/contract-balances`
- **Group consolidation (IFRS 10)** — holding-tenant entity graph, worksheet runs with IC/NCI eliminations (never posted to member GLs), consolidated BS/P&L package at `/consolidation`
- **Intercompany (#261)** — IC-flagged invoices/bills with auto mirror drafts across consolidation members; recon at `/intercompany/recon`
- **IFRS 16 leases** — RoU asset + lease liability schedules, period posting (interest / payment / depreciation), maturity disclosure, early termination; Settings gate `leases_enabled`; UI `/leases`
- **Analytic dimensions (#260)** — up to 3 dimension types (optional mandatory), JE multi-slot tagging, dimensional P&L
- **Inventory depth (IAS 2)** — landed-cost allocation onto receipt layers, lot/serial tracking, NRV write-down runs (`/inventory/valuation`)
- **Month-end close pack** — per-period checklist (required tasks can block Soft Close / Lock) + auditor ZIP export from Period Close
- **Tax rate history** — effective-dated rates per tax code for multi-jurisdiction / rate-change reporting
- **Country packs** — Saudi ZATCA (`sa_zatca`), India GST (`in_gst`), Peppol / EU VAT (`eu_peppol`), UAE VAT stub (`uae_vat`)
- **Withholding tax + CIT (#267)** — vendor WHT on bill payments (Cr 2265) + corporate-tax worksheet adjustments
- Server-side PDF invoices/bills (WeasyPrint; needs Pango/Cairo system libs — Save PDF returns a clear 503 if the engine is unavailable); Stripe payment links; SMTP email notifications
- SaaS harden: webhooks + DLQ, background task queue, approvals SoD, customer/vendor/patient portal, bank feeds / statement import, plan quotas
- **Responsive data entry** — invoice/bill line editors and payment forms stack into mobile cards on sm/md breakpoints (not scroll-only tables)

**Settings & customisation**
- Company profile: name, tagline, address, logo — all printed via `PrintHeader`
- Document number formats with `{prefix}`, `{YYYY}`, `{MM}`, `{seq:04d}` tokens and live preview
- Default GL accounts per tenant (AR, AP, Revenue, COGS overrides)
- **Check for Updates** — compares running version to the latest GitHub release; on the desktop app downloads + installs via `electron-updater` (Restart to apply); on script installs shows the `update.bat`/`update.sh` command; data preserved in both paths. The `VersionBadge` in Settings shows the live running version — fetches `/api/version` in dev mode, reads `NEXT_PUBLIC_APP_VERSION` in production builds (injected by the installer at build time)
- Onboarding checklist, audit log (timeline / by-user / by-entity, CSV export)

**Sales operations**
- **Sales commissions** — define rate/target plans per staff member; compute monthly commissions; approve and post (`Dr Commission Expense / Cr Commissions Payable`) in one click
- **Promotional discounts** — create promo rules (product, min qty, discount %); "Apply Promos" on the invoice form auto-fills the Disc% column; line amounts recalculate instantly
- **Granular access control** — 60-resource permission matrix beyond the 4 RBAC roles; per-user "my data only" mode; module-level toggle in Settings

**HRM — Payroll & Attendance**
- **Employee master** — department/designation/join date/CNIC/bank details; soft-delete; auto-generated codes (EMP-0001)
- **Salary components catalog** — earnings/deductions/statutory types; GL account linkage per component; per-employee fixed or %-of-basic amounts
- **Payroll runs** — draft → approved → posted flow; auto-computes gross/deductions/net per employee from salary structures; GL posting (Dr Salary Expense / Cr Salaries Payable + Cr Tax/EOBI Payable); PR-YYYY-seq voucher; void with reversing JV; printable payslips
- **Attendance register** — manual time-in/out entry per employee per day; hours auto-computed; status codes (Present/Absent/Half Day/Leave/Holiday/Off); monthly grid view (employees × days); bulk entry grid; biometric import endpoint (matches by employee code, stores raw device payload); CSV upload as manual fallback; ZKTeco/FingerTec device integration planned

**Module system (v2.9)**
- **Odoo-style installable modules** — **15** modules: `base` (always active), `inventory`, `production`, `hrm`, `telecom`, `pra`, `healthcare`, `ai_assistant`, `purchase_store`, `weaving`, `spinning`, plus Localization packs `sa_zatca`, `in_gst`, `eu_peppol`, `uae_vat`. Each module gates a sidebar section (or, for `ai_assistant`, the chat button); sections with no active module are hidden
- **Apps page** (`/apps`) — module store grid grouped by category (Core / Operations / HR / Industry / Intelligence / **Localization**); install/uninstall with dependency resolution and a confirmation dialog before removal; admin/owner only
- **Add-ons-first UX** — public signup starts with Base Accounting; industry/localization packs live on `/apps` (`?welcome=1`); demo tenants bypass onboarding and ship with model-default modules (+ localization demos where seeded)
- `Tenant.module_meta` JSON column records `{tier, installed_at, expires_at}` per module — billing-ready schema without a future destructive migration
- Legacy `enabled_modules` strings auto-normalized on read — zero-downtime upgrade for existing installs

**AI Financial Assistant (v3.2, agentic pipeline v3.6, full-spectrum agents + reviewer v3.8)**
- **Conversational chat** — floating Sparkles button opens a chat panel, or use the full-page `/agent` view with a session sidebar; ask "What's my revenue this month?" or "Which invoices are overdue?" in plain language, with one-tap quick prompts
- **Triage → Specialist → Reviewer → Drafting pipeline** — a cheap/fast classifier routes each question to a focused specialist agent, which calls the relevant read-only report tools against real tenant data; a silent reviewer pass then verifies every figure in the findings against the raw tool results before a final cheap pass formats the verified answer into clean Markdown — tables, headings, bold labels — instead of one model doing routing, analysis, checking, and formatting all at once
- **A specialist for every domain (v3.8)** — 11 agents: Receivables, Payables, Financial Reports (P&L, balance sheet, trial balance, cash flow, tax, budgets, net worth), Sales & Customers, plus module-gated Inventory, Payroll & HR, Healthcare, Telecom, Purchasing & Store, and Manufacturing agents that only appear for tenants with those modules installed — and a General fallback that can also run ad-hoc queries over the report-builder's whitelisted data sources (`run_custom_report`)
- **Grounded in live data** — every specialist calls the same tenant-scoped report functions the rest of the app already uses (~50 read-only tools: statements, ledgers, agings, registers, dashboards, and name→id lookups), so answers come from real numbers, never guesses, and can never write, post, or modify anything
- **Multi-provider** — Anthropic (Claude), OpenAI (GPT), Google (Gemini), or a self-hosted Ollama server; pick per-conversation from whatever the tenant has configured
- **Model & API Key, right in the chat** — a button in the chat header opens a panel to pick a model or add a provider key on the spot (admin/owner for the key; anyone can pick a model), so a fresh install's chat is never a dead end with no visible way to configure it
- **Installable module** — `ai_assistant` (Intelligence category, pro tier, off by default); the gate is enforced server-side and the chat button hides when the module isn't installed
- **Safeguards** — message-length and history caps; a per-tenant hourly rate limit (one request per user turn, regardless of the pipeline's internal model calls); friendly errors on rate limits or outages

**Calculator (v3.6)**
- **Globally available** — a floating widget on every page (no module gate), drag-anywhere and minimizable like the AI Assistant panel, styled as a silver-chassis Casio-HL-122-style desk calculator with a green-tinted LCD
- **2-line display** — a running expression history above the main result (`123+456+789+`), finalizing to `200+300=` on equals, matching a real 2-line business calculator
- **Full keyboard support** — type digits, `+ - * /`, `Enter`/`=`, `Backspace`, `Escape`/`Delete`, `%` directly; steps aside automatically if you're typing into an unrelated form field elsewhere on the page
- **12-digit precision** with `√` and `00` keys; percent is consistent across every operator (`200 × 10%` shows `20`, not a bare `0.1` that ignores the base number)

**Purchases & Store module (v3.3–v3.5)**
- **Demand → Comparative → PO chain** — Purchase Demand (PD-YYYY-seq, quantity-only, no rates — the requester never sets prices) → Vendor Quotations (VQ-YYYY-seq, per-vendor pricing against demand lines) → Comparative Statement (CS-YYYY-seq, one per demand) → convert to Purchase Order
- **Segregation-of-duties controls** — a demand or comparative cannot be approved by its own creator; quotations freeze once their comparative is approved
- **Lowest-or-justify rule** — approving a comparative with fewer than two quotations, or a selection that isn't the lowest total, requires a written justification; approval also blocks if the selected quotation doesn't price every demand line
- **Matrix builder UI** — side-by-side vendor comparison grid highlighting the lowest rate per line, with one-click "Convert to PO"
- **Setting-gated enforcement** — `require_purchase_chain` (Settings, default on) blocks bare Purchase Order creation once `purchase_store` is installed, forcing new POs through the approved chain; can be switched off per tenant
- **Gate Inward (GI-YYYY-seq)** — receipt control between PO approval and billing: per-line quantity caps against the PO, PO status flips approved↔received as coverage completes, append-only (cancel requires a reason, no edits). `require_gate_inward` (Settings, default on) blocks converting a PO to a bill until every line is fully covered
- **Gate Register + 3-Way Match reports** — searchable log of every gate entry (vehicle/challan), and PO-vs-received-vs-billed variance detection across the whole procurement chain — catches short receipts billed in full, and legacy POs billed with no recorded receipt at all
- **Gate Outward (GO-YYYY-seq)** — the dispatch-side mirror: sales-invoice and purchase-return exits are reconciliation-only memos (stock already left the books when those documents posted); scrap disposal is the one case with a real draft→approve workflow — approval itself relieves stock and posts GL (`Dr Cash / Cr Scrap Sales` when there's salvage value, `Dr Scrap Disposal Expense / Cr Inventory` always), with the same self-approval block as demands/comparatives
- **Gate Outward Register + Dispatch Reconciliation reports** — searchable outbound gate log, and a report flagging any posted invoice or debit note with no recorded gate exit yet
- **Installable module** — `purchase_store` (Operations category, free tier, depends on `inventory`); pre-installed for the Manufacturing business-model track; gates a dedicated **Purchases** section (Demands, Comparatives, Gate Inward, reports) plus a dedicated **Store** section (Gate Outward, reports)

**Healthcare module (v3.0)**
- **Patient registry** — MR-YYYYNNNN numbering; every patient auto-creates a `Customer` record so AR aging, statements, and payment allocation work out-of-the-box
- **OPD (multi-doctor)** — token queue per doctor per day; visit recording (complaint, diagnosis, prescription); auto-bills consultation fee via GL (`Dr AR / Cr OPD Revenue 4100`)
- **IPD / Inpatient** — ward & bed management (general/ICU/private/maternity); patient admissions with deposit; daily charge accumulation (`hc_admission_charge`); single consolidated invoice at discharge; deposit settled via GL at discharge
- **Laboratory** — test catalogue (hematology/biochemistry/microbiology/radiology); lab orders with source tracking (walk-in/OPD/IPD/collection centre); sample collection workflow; result entry per test item; auto-bills walk-in and OPD orders
- **Procedures** — catalogue with category (minor/surgery/diagnostic/therapy); procedure orders billed at creation; "Mark Performed" action
- **Hospital Store** — stock issues from `hc_store_issue`; integrates with existing `Product` / `StockMovement` / `StockLocation` inventory system; pharmacy prescription dispensing queue
- **HC Reports** — dashboard KPIs, OPD summary, doctor collections, lab summary, IPD census, revenue by type (accounts 4100–4121)
- **Demo tenant** — `demo.hospital@easy-books.app` / `demo1234` — 5 doctors, 4 wards (38 beds), 50 patients, ~200 OPD tokens, 20 admissions, 80 lab orders, 25 procedure orders

**Yarn Spinning module**
- **Master data** — yarn specs (Ne/Nm count, blend %), fiber grades, machines (spindle count), shifts, operators, waste types (mapped to GL 5901–5904), blend recipes
- **Production plans** — monthly targets by yarn spec; approve to lock
- **Spin lots** — SL-YYYY-seq lifecycle: draft → started → completed → closed; accumulates material/labour/overhead/waste costs; cost-per-kg computed live
- **Bale receipt** — BR-YYYY-seq; gross/tare → net kg; optional PO/gate-inward/bill link; approve posts `Dr 1200 RM / Cr AP or Cash` + stock into RAW location
- **Multi-stage entries** — opening → carding → drawing → roving → spinning → winding; WIP transfers across `1201`/`1202`/`1203`; labour/overhead to `5100`/`5200`
- **Cone output** — CO-YYYY-seq; approve transfers WIP → FG (`1204`) at lot cost
- **Waste log** — posts to waste expense accounts (`5901`–`5904`) and relieves WIP
- **Yarn dispatch** — YD-YYYY-seq; approve posts COGS (`Dr 5010 / Cr 1204`) + stock relief
- **Reports & calculators** — dashboard KPIs, daily register, lot-control panel, waste summary, cost-per-kg, dispatch register; yield/blend/spindle calculators
- **Full GL integration** — unlike Weaving (memo-only), every approve/post hits the central posting service
- **Demo tenant** — `demo.spinning@easy-books.app` / `demo1234` — pre-loaded masters, open/completed lots, bale receipts, stage entries, cone output, waste, and dispatches

**Multi-tenant SaaS**
- RBAC: `owner | admin | accountant | viewer`; team management with invite links
- Tenant isolation at the data layer — every query filters by `tenant_id`
- JWT + HttpOnly cookie; CSRF double-submit; login throttle; idempotency keys
- **API keys (v3.7)** — machine-to-machine access for scripts and integrations: create in **Settings → API Keys** (admin/owner), key shown once, sent as `Authorization: Bearer eb_live_…`, authenticates with the owning user's exact permissions, revocable with immediate effect
- **Real logout (v3.7)** — logging out revokes the session token server-side (jti denylist), so a copied token dies immediately instead of surviving to natural expiry
- **Global rate limiting (v3.7)** — 1000 req/min per authenticated user, 100 req/min per anonymous IP (env-configurable), on top of the existing login throttle

**Business-model tracks**
- **Manufacturing (V2):** multi-location inventory, Bills of Material, Rate Plans, GRN, Production Order lifecycle (draft→started→completed→delivered→billed) with full GL postings
- **Telecom Franchise (V3):** 56-account franchise CoA, Tracker wallet & load orders, MSR→RSO→Retail chain, SIM inventory, FCA targets, Mobile Money agency, Postpaid billing, Commission reconciliation, 9 telecom reports
- **PRA e-Invoice (Pakistan):** real-time invoice submission to Punjab Revenue Authority (PRA eIMS); FIN (Fiscal Invoice Number) returned and printed on invoices; `pra_status` badge (pending/submitted/failed) with retry; Payment Mode field; customer NTN/CNIC fields; product PCT codes; Settings card with Test Connection; non-blocking `BackgroundTasks` submission so invoice save is never delayed
- **Yarn Spinning:** cotton bale receipt → multi-stage lot tracking (carding/drawing/roving/spinning/winding) → cone output → yarn dispatch with full GL costing (`1200`–`1204` WIP chain, waste accounts `5901`–`5904`, COGS at dispatch)

---

## Three ways to run

### ① One-click standalone (recommended for end users)

No Python, Node, or terminal knowledge required. The scripts auto-install everything they need (first run fetches uv/Python and a local portable Node; later runs start in seconds).

**Windows** — double-click `install-and-run.bat` in Explorer.

**macOS / Linux:**
```bash
chmod +x install-and-run.sh
./install-and-run.sh
```

What happens automatically: installs **uv** (which provisions Python 3.12), downloads a portable Node into `./.node` if none is found, installs backend deps, builds the frontend, runs `alembic upgrade head`, and opens **http://127.0.0.1:3000**.

Your data lives **outside** the app folder:

| Platform | Location |
|---|---|
| macOS / Linux | `~/.easy-books` (override: `EB_DATA_DIR`) |
| Windows | `%USERPROFILE%\.easy-books` (override: `%EB_DATA_DIR%`) |

On first install the 8 demo companies are loaded automatically (takes ~20–30 s). Log in immediately with `demo1234` — no signup needed. Set `SEED_DEMO=false` before running the installer for a clean start. See [§ Demo / sample data](#demo--sample-data) for details.

Pass `--rebuild` (sh) / `-Rebuild` (ps1) to force a fresh frontend build after a source update.

#### Electron desktop app

A bundled Electron desktop app (Phase 2) packages the FastAPI backend as a PyInstaller binary and the Next.js standalone server with a bundled Node into a signed Windows `.exe` / macOS `.dmg` installer — no terminal, no internet fetch. Releases are published automatically to GitHub Releases by the CI pipeline (`.github/workflows/release.yml`) when a `v*` tag is pushed. See [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md#phase-2--bundled-desktop-installer-build--release) for build and release details.

---

### ② Docker — team / office network

Share one Easy-Books instance across your whole office. Any machine on the network opens a browser — no client install needed.

**Prerequisites:** [Docker Desktop](https://docs.docker.com/get-docker/) (or Docker Engine + Compose plugin on Linux).

```bash
git clone https://github.com/bilalpiaic/Easy-Books.git
cd Easy-Books
cp .env.example .env
# Edit .env — set APP_URL=http://YOUR_SERVER_IP
docker compose up -d --build
```

Open `http://YOUR_SERVER_IP` from any machine on the LAN. First build takes ~3–5 min; subsequent starts are instant. Data persists in the `eb_data` Docker volume — safe across `git pull` updates.

To update:
```bash
git pull && docker compose up -d --build
```

See [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md#docker-compose--officeteam-server) for full setup, HTTPS, PostgreSQL, and backup instructions.

---

### ③ Developer mode

```bash
git clone https://github.com/bilalpiaic/Easy-Books.git
cd Easy-Books

# One-shot: starts backend + frontend + seeds demo data
./dev.sh
```

Backend: http://localhost:8000 (Swagger UI at `/docs`) — Frontend: http://localhost:3000

Or run each service manually:

```bash
# Backend
cd backend
uv sync
python main.py

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

`dev.sh` auto-seeds eight demo tenants with rich mock data on each run (idempotent).

---

## Demo / sample data

**Public path:** Login → **Try the live demo** signs into one Base Accounting company (`demo.simple@easy-books.app` / `demo1234`). Install industry packs from **System → Add-ons** (optional “Include sample data”). There is no pre-login multi-company picker.

**QA / admin:** Standalone installs and `dev.sh` still seed eight fully-populated demo companies for regression testing. They are not advertised on the login page; use Settings → Sample / Demo Data or the emails below with password `demo1234`:

| Email | Pre-loaded pack (QA) |
|---|---|
| `demo.simple@easy-books.app` | Base (public demo) |
| `demo.services@easy-books.app` | Services / deferred revenue |
| `demo.trader@easy-books.app` | Inventory |
| `demo.manufacturing@easy-books.app` | Manufacturing + Purchases/Store + Weaving |
| `demo.telecom@easy-books.app` | Telecom Franchise |
| `demo.pra@easy-books.app` | PRA e-Invoice |
| `demo.hospital@easy-books.app` | Healthcare |
| `demo.spinning@easy-books.app` | Yarn Spinning (full GL production chain) |

The first install takes an extra ~20–30 seconds while the seeder runs; subsequent starts are fast (the seeder is guarded — skips if any user already exists, so updating an existing install is migrate-only and no demo data is added). To opt out and start with a clean slate, set `SEED_DEMO=false` before running the installer.

The **desktop (Electron) app** also auto-loads the 8 demo companies on first install (`SEED_DEMO=true` default; a startup splash is shown during the one-time seed). Set `SEED_DEMO=false` for a clean desktop install.

The **Settings → Sample / Demo Data** card loads or removes the demo companies on demand at any time.

Each demo tenant contains 100 invoices, 100 bills, 70 payments received, 70 bill payments, 25 customers, 25 vendors, 3 bank accounts, 6 recurring templates, and 60+ manual journal entries spread across **two fiscal years** (so comparative reports have a prior period). The hospital tenant additionally contains 5 doctors, 4 wards, 50 patients, ~200 OPD visits, 20 IPD admissions, 80 lab orders, and 25 procedure orders. The spinning tenant additionally contains yarn specs, fiber grades, machines, open and completed spin lots, bale receipts, multi-stage entries, cone output, waste logs, and yarn dispatches with real GL postings — every Spinning screen and report has data on first login. The manufacturing tenant additionally exercises the full Purchases & Store chain: 6 Purchase Demands across every status, 3 Comparative Statements (lowest-wins, non-lowest-with-justification, and one left pending approval), 4 Purchase Orders spanning partial/full/short-received and billed/unbilled states, Gate Inward entries including a cancelled-and-re-entered one, and Gate Outward exits covering invoice/debit-note memos plus a scrap entry approved with real GL postings — every Purchases and Store screen and report has real data to show on first login. Transactions carry their correct voucher types, the services tenant demonstrates **deferred-revenue origination with partial recognition**, and each tenant has **multiple users** (owner / accountant / clerk) so the Audit Log shows realistic attribution.

In **developer mode**, `dev.sh` seeds these tenants automatically on every run. To seed manually:

```bash
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
```

---

## Updating & data safety

### Your data is always safe

User data (the SQLite database, uploaded files, and the per-install JWT secret) lives in `~/.easy-books` / `%USERPROFILE%\.easy-books` — **completely outside the app folder**. Updating or reinstalling Easy-Books never touches this directory.

### Database migrations run automatically on launch

All three install paths run `alembic upgrade head` before starting the servers:

- **Script installers** (`install-and-run.sh` / `install-and-run.bat`) — migrate before boot
- **Desktop app** — `backend/run_packaged.py` migrates before uvicorn starts
- **Docker** — `backend/docker-entrypoint.sh` migrates before uvicorn starts

Your schema is updated in place; existing rows are preserved and new features are available immediately after an update. The auto-seed guard (`scripts/autoseed_demo.py`) skips if any user is already present, so **updating an existing install never injects demo data** — only a brand-new empty database triggers the one-time demo load.

### Updating a Docker install

```bash
git pull && docker compose up -d --build
```

### Updating a script install

```bash
# macOS / Linux
./update.sh

# Windows
update.bat          # double-click in Explorer
```

`update.sh` / `update.bat` runs `git pull` then calls the installer to rebuild and relaunch. The installer also **auto-rebuilds the frontend whenever the code has changed** since the last build (tracked via `frontend/.next/.built-commit`), so a plain re-run after any `git pull` always serves the latest UI — no stale builds.

### Updating the desktop app

The Electron desktop app checks for updates on every launch via `electron-updater`. When a newer GitHub Release with a `latest.yml` manifest is available you will see an in-app prompt. Click **Download** to fetch the installer in the background, then **Restart** to apply it. The next launch re-runs `alembic upgrade head` automatically — data is preserved. You can also trigger a manual check at any time via **Settings → Check for Updates**.

### Back up before a major update

Go to **Settings → Backup & Restore** and download a zip (database + uploads) before any significant update.

See [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md) for full details.

---

## Tech stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js 16 / React 19 / TypeScript / Tailwind CSS v4 |
| Backend | FastAPI / Python 3.11+ / SQLModel / Alembic |
| Database | SQLite (dev / local) · PostgreSQL via `DATABASE_URL` (production) |
| Auth | JWT (HS256) + bcrypt · HttpOnly cookie · CSRF double-submit |
| PDF / Email | WeasyPrint (server-side PDF) · SMTP |
| CI/CD | GitHub Actions (`.github/workflows/release.yml`) — validates 3 version files (frontend/package.json, desktop/package.json, backend/pyproject.toml), builds Windows `.exe` + macOS `.dmg` (optional), publishes to GitHub Releases |

---

## Development

### Commands

```bash
# Backend
cd backend
uv sync                                        # install deps
python main.py                                 # dev server → http://localhost:8000
PYTHONPATH=. uv run pytest                     # run all tests
PYTHONPATH=. uv run pytest -v                  # verbose
PYTHONPATH=. uv run pytest tests/test_auth.py  # single file
PYTHONPATH=. uv run pytest -k test_name        # single test by name

# Frontend
cd frontend
npm install
npm run dev    # → http://localhost:3000
npm run build
npm run lint
```

Swagger UI is available at **http://localhost:8000/docs** during development.

### Schema changes

Easy-Books uses **Alembic** as the source of truth for schema changes (migrations through revision 0019+). For new columns or tables:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

`SQLModel.metadata.create_all()` still runs on startup for zero-setup dev boot — new-table migrations must guard with `bind.dialect.has_table(...)`. SQLite cannot `ADD CONSTRAINT` via `ALTER TABLE`, so strip auto-generated FK lines from migrations (see revisions 0016/0017 for the pattern).

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | `postgresql://…` in production; omit for SQLite | `backend/database.db` |
| `JWT_SECRET_KEY` | HMAC secret — **required in production** | Insecure dev default |
| `APP_ENV` | `development` or `production` | `development` |
| `FRONTEND_ORIGIN` | Comma-separated CORS allow-list | `http://localhost:3000` |
| `UPLOAD_ROOT` | Root dir for avatars and attachments | `uploads` |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | Create an admin user on first boot | — |
| `SEED_COMPANY_NAME` | Default company name for the seeded tenant | `My Company` |
| `STRIPE_SECRET_KEY` | Stripe secret for SaaS Checkout + invoice payment links. When unset, billing upgrades apply **offline** (plan written locally) and payment-link creation returns 400 | — |
| `STRIPE_PRICE_STARTER` / `STRIPE_PRICE_PRO` / `STRIPE_PRICE_ENTERPRISE` | Stripe Price IDs for live Checkout (`POST /api/billing/checkout`). Required when `STRIPE_SECRET_KEY` is set; Checkout returns an actionable 400 naming the missing env var otherwise | — |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret for `/api/stripe/webhook` | — |
| `PLAID_CLIENT_ID` / `PLAID_SECRET` / `PLAID_ENV` | Bank feeds (Plaid). Sync upserts `StatementLine` rows when credentials + a linked bank account are present | — |
| `REDIS_URL` | When set, background jobs go to Redis via ARQ; when unset, tasks run **inline** in-process (Electron / script install / local pytest) | unset (inline) |
| `ANTHROPIC_API_KEY` | Dev/demo fallback for the AI assistant (anthropic only); per-tenant keys in Settings → AI take priority | — |

Frontend: set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`.

### Background workers (ARQ / Redis)

Easy-Books never requires Redis for a working install. [`backend/services/queue.py`](./backend/services/queue.py) checks `REDIS_URL`:

- **Unset** — `enqueue(...)` runs the matching task from `tasks.REGISTRY` in-process and returns `{status: complete|failed}`. This is the default for script installs, Electron, and pytest.
- **Set** — jobs are pushed to Redis. Run a worker from `backend/`:

```bash
cd backend
export REDIS_URL=redis://localhost:6379/0
uv run arq worker.WorkerSettings
```

[`backend/worker.py`](./backend/worker.py) registers PDF generation, email, webhooks, dunning, recurring journals, and insight scans. Cron drains the webhook outbox every minute and posts due recurring entries daily at 01:00 UTC. Self-hosters who prefer zero ops can leave `REDIS_URL` unset and rely on inline execution.

---

## Documentation index

| Document | Contents |
|---|---|
| [`docs/AI_INDEX.md`](./docs/AI_INDEX.md) | **Start here for AI agents / new contributors** — doc-ownership map, core invariants, ground-truth pointers |
| [`USER_GUIDE.md`](./USER_GUIDE.md) | End-user walkthrough for every feature |
| [`WORKFLOW.md`](./WORKFLOW.md) | Accounting workflows, GL Dr/Cr maps, report-linking matrix, API catalog |
| [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md) | One-click installer, Electron desktop app, data safety, update paths |
| [`DEPLOYMENT.md`](./DEPLOYMENT.md) | Cloud deploy: frontend + API on Vercel, database on Neon |
| [`BLUEPRINT.md`](./BLUEPRINT.md) | Complete project blueprint: every model, endpoint, flow, and decision |
| [`docs/PRESENTATION.md`](./docs/PRESENTATION.md) | Project review pack — architecture Mermaid diagrams + Good/Better/Best vs Odoo, QB, peers |
| [`docs/marketing/`](./docs/marketing/) | Narrated pictograph video, slides, voiceover script, and social media attraction pack |
| [`CLAUDE.md`](./CLAUDE.md) | AI-assistant instructions and architecture reference |
| [`backend/README.md`](./backend/README.md) | Backend quick-start, commands, structure, API conventions |
| [`frontend/README.md`](./frontend/README.md) | Frontend quick-start, scripts, environment variables |

The in-app **User Guide** (`/guide`) and **Workflow** (`/workflow`) pages provide interactive, tenant-aware walkthroughs directly in the browser.

---

## Legacy reference

The repo root also contains a legacy Express + vanilla-JS implementation (`server.js` + `public/`). This is a reference-only snapshot and is not actively developed. All feature work happens in the modern `backend/` (FastAPI) + `frontend/` (Next.js) stack.

---

## License

MIT.
