# Tenant customization, entitlements, and Studio-lite

**Date:** 2026-09-06
**Status:** Draft for review
**Topic:** How Easy-Books launches specific modules to specific clients, shows private Marketplace listings, and supports Odoo/QuickBooks-style local form/field/report customization — without per-client git forks.
**Companion plan:** `docs/superpowers/plans/2026-09-06-tenant-customization-studio.md`
**GitHub issue pack (copy-paste):** `docs/github-issues/tenant-customization-studio.md`

## Goal

Ship a **metadata overlay** on the existing multi-tenant SaaS so that:

1. Two paying companies on the same Vercel app + Neon database can have different **module packs**.
2. A mill-only Marketplace listing is visible only to that mill (**For you**), never to a hospital tenant.
3. The same shipped `InvoiceForm` can show different extra fields / hide different core fields per tenant (and later per role), the way Odoo Studio and QuickBooks custom fields do.

This is **not** a new product per client. It is configuration + entitlements + declarative partner bundles on `main`.

## Context (what already exists)

| Primitive | Where | What it already does |
|-----------|--------|----------------------|
| Shared-DB multi-tenancy | `Tenant`, `tenant_id` on every table | Isolation; one deploy |
| Module install | `Tenant.enabled_modules`, `MODULE_REGISTRY`, `/api/modules` | Per-tenant product surface |
| Signup defaults | `MODULES_BY_MODEL` | Pre-selects modules from `business_model` only at create / model-switch |
| Plan fields | `Tenant.plan`, `module_meta` | Reserved for billing; **not enforced on install today** |
| Screen rights | `UserPermission` + `perm_dep` | Resource-level `none/view/edit` + `my_data_only` |
| Report patterns | `/api/report-builder` + saved `ReportDefinition` | Private or shared grids over a **whitelist** |
| Dashboard layout | `UserDashboardLayout` v4 | Per-user; keep it that way |
| Branding | Settings KV, logo, `PrintHeader` | Per-tenant chrome |
| Print bodies | `backend/templates/invoice.html`, `bill.html` | **Repo files**, not per-tenant |
| Marketplace | `#227`, `services/marketplace/` | Declarative manifests; **no partner code**; catalog is **the same for every tenant**; `tags` exist but the Apps tab does not render them |
| External apps | API keys `#113`, webhooks `#114` | QB Intuit-style partners already possible |

Gaps vs Odoo Studio / QBO custom fields: no custom fields, no form schema, no catalog audience filter, no operator “entitle spinning for tenant X”, no tenant-owned print templates.

## Locked decisions

| Decision | Choice |
|----------|--------|
| Deploy model | **One repo, one `main`, one production Vercel project, one Neon database.** Client = `Tenant` row. |
| Per-client git branches / extra Vercel+Neon | **Forbidden** for customization. Dedicated infra only for a paid isolated/enterprise contract, still from the same `main`. |
| Customization store | **Data on the tenant** (JSON schema + `x.*` fields + print template rows), not React forks. |
| Form code | One shipped component per document (e.g. `InvoiceForm.tsx`). It **reads** schema; it is never copied per client. |
| Custom field keys | Must match `^x\.[a-z][a-z0-9_]*$` (mirrors Marketplace `ext.*`). |
| Custom fields vs GL | `x.*` values are attributes. They **never** enter `posting.py`, tax, or `consume_stock`. Promoting a field into posting means a first-party module on `main`. |
| Field cap | **12 custom fields per entity per tenant** (QB-shaped). Archive (soft) rather than unbounded Studio columns. |
| Schema scope | Tenant-wide, optional **role overlay**. **Not** per-clerk form designers. |
| Per-user (keep) | Dashboard layout, report-builder private saves, `my_data_only`. |
| Marketplace tags | Topical only (`tax`, `spinning`, `first-party`, `private`). **Never** tenant slugs or `customized-tenant`. |
| Catalog visibility | First-class `audience`: `public` \| `entitled` \| `private`. Filter in `GET /api/marketplace/catalog` (not only in React). |
| Partner executable code | **Still forbidden.** Marketplace install never evals/downloads/runs partner JS/Python (existing `#227` boundary). |
| Partner tracks | **A** no-code Studio in Settings; **B** declarative Marketplace bundle; **C** external API/webhooks. No Track D (Odoo-module-in-process). |
| Who entitles modules | A **platform operator** (not the tenant owner). Tenant admin may install only entitled / plan-allowed modules. |
| `MODULES_BY_MODEL` | Signup / model-switch **default only**. After that, entitlements own the set. |

## Pattern (the architecture)

```
Shipped form / report / nav (code on main)
    │
    ├─ Tenant.enabled_modules + plan/module_meta   → which product they bought
    ├─ Catalog audience filter                     → which Marketplace cards they see
    ├─ CustomFieldDef + values                     → extra columns (QB custom fields)
    ├─ FormSchema + optional role overlay          → hide / require / order (Studio-lite)
    └─ PrintTemplate picker / clone                → PDF/report pattern
```

Two customers, same URL:

- Mill: `enabled_modules` includes `spinning`; invoice schema shows `x.gate_pass_no`; private listing “Weighbridge slip” with badge **For you**.
- Clinic: `healthcare` installed; invoice schema shows `x.mrn`; never receives the mill listing in catalog JSON.

### Request classification (ops playbook)

Every client request maps to exactly one bucket:

| Bucket | Delivery |
|--------|----------|
| Configuration | Settings, CoA, tax pack, logo, FY |
| First-party module | Build on `main`, entitle that tenant |
| Marketplace listing | Public / entitled / private declarative card |
| Dedicated instance | Paid isolation; same `main`, different `DATABASE_URL` |

“Fork `InvoiceForm` for Acme” is not a bucket.

## Data model

All new tables: `tenant_id` + index; SQLite-safe Alembic (`has_table` guards; no `ADD CONSTRAINT` on ALTER). Next free revision after `0079` is **`0080`**.

### 1. Module entitlement (no new table required)

Reuse `Tenant.module_meta` JSON:

```json
{
  "spinning": { "tier": "free", "installed_at": "…", "entitled": true, "entitled_at": "…" },
  "_plan_modules": ["base", "inventory", "purchase_store", "spinning"]
}
```

**Install rule** (`POST /api/modules/{id}/install`):

```
allowed = module.always
       OR module_meta[id].entitled is true
       OR id ∈ plan_allowlist(tenant.plan)
forbidden → 403 "Module not included in this tenant's plan. Contact Easy-Books."
```

Default plan allowlists (code constant, not Settings — operators must not widen Free from the tenant UI):

| Plan | Installable without an entitle override |
|------|-----------------------------------------|
| `free` | `base` only |
| `starter` | `base`, `inventory`, `pos` |
| `pro` | starter + `purchase_store`, `production`, `hrm`, `ai_assistant`, localization packs |
| `enterprise` | all `MODULE_REGISTRY` ids |

Industry packs (`spinning`, `healthcare`, `weaving`, `telecom`, `textile_processing`, `pra`) are **entitle-only** on Free/Starter/Pro unless listed in that plan’s allowlist (Pro may include localization; industry packs stay entitle-or-enterprise). Exact matrix is a single dict `PLAN_MODULES` in `db.py` next to `MODULE_REGISTRY`.

Platform operator API (new router `routers/ops_tenants.py`, gated by env `OPS_ADMIN_EMAILS` comma-list matching `User.email`, **not** tenant `role=owner`):

| Method | Path | Effect |
|--------|------|--------|
| GET | `/api/ops/tenants` | id, name, plan, enabled_modules |
| GET | `/api/ops/tenants/{id}/modules` | registry + entitled + installed |
| PUT | `/api/ops/tenants/{id}/modules` | set `entitled` flags; does **not** install |
| POST | `/api/ops/tenants/{id}/modules/{mid}/install` | entitle + install (optional `seed_sample`) |

Tenant Apps UI: Install button disabled + tooltip when not entitled. API 403 is the real gate.

### 2. Catalog audience

Extend `CatalogEntry` (`services/marketplace/manifest.py`):

```python
audience: Literal["public", "entitled", "private"] = "public"
visible_to_tenant_ids: list[int] = []   # private only
entitled_module: str | None = None      # entitled: show if that module is entitled or installed
```

Filter in `get_catalog`:

- `public` — always (still respect curated catalog).
- `entitled` — `entitled_module` in enabled **or** `module_meta[m].entitled`.
- `private` — `user.tenant_id in visible_to_tenant_ids`.

Remote catalogs may set these fields; invalid ids are dropped, never leaked. Tags stay topical; optional tag `private` is cosmetic only.

UI (`apps/page.tsx` Marketplace cards): render `tags`; badge **For you** when `audience !== "public"`; keep **First-party** / **Installed**.

### 3. Custom fields

`CustomFieldDef`:

| Column | Type | Notes |
|--------|------|--------|
| `id` | PK | |
| `tenant_id` | FK | indexed |
| `entity` | str | `invoice` \| `bill` \| `customer` \| `product` \| `vendor` (v1 allowlist) |
| `key` | str | `x.gate_pass_no` |
| `label` | str | |
| `type` | str | `text` \| `number` \| `date` \| `enum` \| `bool` |
| `enum_values` | JSON str? | required when type=enum |
| `required` | bool | form + API |
| `show_on_form` | bool | |
| `show_on_print` | bool | |
| `show_on_list` | bool | optional list column |
| `sort_order` | int | |
| `archived_at` | datetime? | soft delete; values retained |

Unique `(tenant_id, entity, key)`. Max 12 non-archived defs per `(tenant_id, entity)`.

**Values:** JSON column `custom_fields` (default `{}`) on `Invoice`, `Bill`, `Customer`, `Product`, `Vendor`. Unknown keys stripped; missing required keys → 400. Do **not** add 12 nullable columns per entity.

### 4. Form schema

`FormSchema`:

| Column | Type | Notes |
|--------|------|--------|
| `tenant_id` | PK part | |
| `entity` | PK part | same allowlist as custom fields |
| `role` | PK part | `*` = tenant default; or `owner`/`admin`/`accountant`/`viewer` |
| `schema` | JSON str | see below |
| `updated_at` | datetime | |
| `updated_by_id` | FK user? | |

```json
{
  "version": 1,
  "fields": {
    "discount_pct": { "visible": false },
    "analytic_2_id": { "visible": true, "required": true },
    "x.gate_pass_no": { "visible": true, "required": true, "order": 40 }
  }
}
```

Resolution: role row if present else `role='*'`. Missing key → shipped default (visible).

**Locked core fields** (cannot set `visible: false`): document date, party (`customer_id` / `vendor_id`), monetary totals / line qty-rate-amount. Server rejects those patches.

API must apply the same schema on POST/PUT (hidden `discount_pct` in a payload is ignored or 400 — pick **ignore unknown-hidden writes** for backwards compatible imports, **400 on required missing**).

### 5. Print templates

v1: **picker among built-ins** + optional **cloned HTML** stored per tenant.

`PrintTemplate`:

| Column | Notes |
|--------|--------|
| `tenant_id`, `id` | |
| `entity` | `invoice` \| `bill` |
| `key` | `standard`, `uae_vat`, or `x.mill_packing` |
| `label` | |
| `is_builtin_override` | false for clones |
| `html` | Jinja body; clones only. Built-ins keep using `backend/templates/*.html` |
| `is_default` | one default per `(tenant_id, entity)` |

PDF renderer: if tenant default clone exists, render that string; else existing file. Sandbox Jinja (`undefined` strict, no `|attr` to internals). No `{% include %}` of arbitrary paths.

### 6. Studio bundle (Marketplace Track B)

Optional object on `CatalogEntry`:

```json
{
  "studio": {
    "custom_fields": [ { "entity": "invoice", "key": "x.gate_pass_no", "label": "Gate pass", "type": "text" } ],
    "form_schema_patch": { "invoice": { "fields": { "x.gate_pass_no": { "visible": true } } } },
    "print_template_key": "x.mill_packing"
  }
}
```

Install writes defs/schema/template rows tagged `source_extension_id`. Uninstall removes **only** rows with that source (leave tenant-edited clones). Still no executable code.

## Permissions

| Resource key | Label | Notes |
|--------------|--------|--------|
| `studio.fields` | Custom fields | admin/owner edit; others view values on docs they can already see |
| `studio.forms` | Form layout | admin/owner |
| `studio.print` | Print templates | admin/owner |
| `studio.field.<entity>.<key>` | Field overlay (phase 6) | optional; default inherit resource (e.g. `invoices`) |

Ops routes are **not** in `PERMISSION_RESOURCES`; they use `OPS_ADMIN_EMAILS`.

## Frontend surfaces

| Surface | Change |
|---------|--------|
| Apps → Optional / Recommended | Disable Install when not entitled; show “Included in plan” / “Contact Easy-Books” |
| Apps → Marketplace | Tags; **For you** badge; catalog already filtered |
| Settings → Studio (new subpage `/settings/studio`) | Field defs + form ticks + print default (Track A) |
| `InvoiceForm` / bill / customer / product forms | Render `x.*`; hide schema-invisible core fields |
| Document lists | Optional extra columns when `show_on_list` |
| Report builder | Dynamic `x.*` field keys from defs (engine resolves JSON path, still not raw SQL) |
| Print/PDF | Chosen template |

## Phases (implementation order)

1. **Entitlements** — `PLAN_MODULES`, install 403, ops entitle API, Apps disable.
2. **Marketplace audience** — catalog fields, server filter, tags + **For you**.
3. **Custom fields** — defs + JSON values + form/list/print/report.
4. **Form schema** — hide/show/required + API enforce + Settings editor.
5. **Print / reports** — template picker + clone; report-builder `x.*`.
6. **Field-level rights** — `studio.field.*` overlay on schema.
7. **Studio UI + bundle** — Settings Studio page; Marketplace `studio` object.

## Non-goals

- Per-client GitHub branch or Vercel project for customizations.
- Odoo xpath / XML views on React.
- Unlimited Studio fields in posting.
- CSS-only field hiding.
- Tenant names as Marketplace cards or tags.
- Per-user invoice form designer.
- Partner JS/Python inside FastAPI or Next.js.
- Public unvetted Marketplace uploads (still `#227`).

## Success criteria

- A platform operator entitles `spinning` for mill tenant A; mill A can install it; hospital tenant B’s Apps shows spinning disabled / 403 on install.
- A `audience: private` listing with `visible_to_tenant_ids: [A]` appears only in A’s `GET /api/marketplace/catalog` and shows **For you**. B’s JSON does not contain that `id`.
- Mill invoice create shows `x.gate_pass_no`; clinic invoice does not; both use the same `InvoiceForm.tsx`.
- Posting a mill invoice with custom fields still balances Dr/Cr identically to an invoice without them.
- No new long-lived git branch named after a client is required to go live.

## Test plan (spec-level)

- Entitlement matrix: free tenant 403 on `spinning`; after ops entitle, 200 install; uninstall does not clear `entitled` unless ops revokes.
- Catalog: two tenants, private listing, assert B’s entries have no that id (API test, not UI-only).
- Custom fields: cap 13th → 400; key `discount_pct` → 400; posting fixtures unchanged when `custom_fields` present.
- Form schema: hide `notes` → omitted from GET form-schema and ignored on PUT; hide `customer_id` → 400 on schema save.
- Studio bundle install/uninstall restores field defs for that `source_extension_id` only.
- Existing `#227` tests still pass (no partner code execution).
