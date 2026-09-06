# GitHub issue pack — Tenant customization / Studio-lite

**GitHub Issues API is not available to the agent that drafted this pack** (`repository.issues` permission missing). File these from the GitHub UI or:

```bash
# From repo root, after labels exist (enhancement, epic)
gh issue create --title "…" --body-file /tmp/body.md
```

**Spec:** `docs/superpowers/specs/2026-09-06-tenant-customization-studio-design.md`  
**Plan:** `docs/superpowers/plans/2026-09-06-tenant-customization-studio.md`

File **Issue 0 (epic)** first, then A–G with `Fixes` / `Part of #<epic>`. Implement **one child per PR** in order A → G (B may start once A’s `entitled` flag exists).

Suggested labels: `enhancement`, `saas`, `marketplace`, `studio`.

---

## Issue 0 — Epic

**Title:** `[epic] Tenant entitlements, Marketplace audience, and Studio-lite customization`

**Body:**

```markdown
## Summary

Easy-Books is already multi-tenant (shared Neon, `tenant_id`, `enabled_modules`). We will **not** give each client a GitHub branch or a separate Vercel/Neon stack.

This epic adds the missing SaaS control plane so two customers on `app.easy-books.app` can have:

1. Different **module packs** (entitle spinning for mill A; hospital B cannot install it).
2. Different **Marketplace cards** (private / entitled listings; **For you** badge; no tenant-name tags).
3. Different **form/field/report** overlays on the same shipped React forms (Odoo Studio / QuickBooks custom-fields pattern as **data**, not forks).

## Why

- Agency-style `client-acme` branches do not scale (bugfix tax, Alembic drift).
- Odoo stores Studio XML **in the database**; QBO stores custom fields **on the company**. Easy-Books should do the same with JSON overlays.
- Marketplace `#227` already forbids partner executable code. Keep that. Partners get declarative bundles + API/webhooks.

## Pattern

```
Shipped form (InvoiceForm.tsx on main)
  + entitlements / plan          → which modules they may install
  + catalog audience             → which Marketplace rows they see
  + CustomFieldDef + JSON values → x.* extra fields (capped)
  + FormSchema ± role overlay    → hide / require / order
  + PrintTemplate                → PDF/report pattern
```

## Operating rules (non-negotiable)

- One repo, one `main`, one production deploy.
- Tags are topical (`tax`, `spinning`, `private`), never `acme-mills` or `customized-tenant`.
- Custom fields never enter GL posting / tax / stock.
- No per-clerk form designer; schema is tenant or role.
- No partner JS/Python in-process.

## Child issues (implement in this order)

- [ ] **A** — Module plan allowlist + platform ops entitle + install 403
- [ ] **B** — Marketplace `audience` filter + tags + **For you**
- [ ] **C** — Custom fields (`x.*`) on invoice/bill/customer/product/vendor
- [ ] **D** — Tenant form schema (hide/show/required) + API enforce
- [ ] **E** — Print template picker/clone + report-builder `x.*`
- [ ] **F** — Field-level `UserPermission` overlay
- [ ] **G** — Settings → Studio UI + Marketplace `studio` bundle

## Docs

- Spec: `docs/superpowers/specs/2026-09-06-tenant-customization-studio-design.md`
- Plan: `docs/superpowers/plans/2026-09-06-tenant-customization-studio.md`

## Out of scope

Per-client git branches, extra Vercel projects for customization, Odoo xpath on React, unlimited Studio columns in posting, CSS-only hiding, listing tenants in Marketplace.
```

---

## Issue A — Entitlements

**Title:** `feat(entitlements): plan allowlist, ops entitle API, and module install 403`

**Body:**

```markdown
## Part of

Epic: Tenant entitlements, Marketplace audience, and Studio-lite customization

## Goal

A platform operator can entitle modules for tenant X. That tenant’s owner can install only entitled / plan-allowed modules. Other tenants are unaffected. **No git branch per client.**

## Context

- `POST /api/modules/{id}/install` today lets any owner install anything in `MODULE_REGISTRY`.
- `Tenant.plan` and `module_meta` already exist (`models.py`) but are not enforced.
- `MODULES_BY_MODEL` is signup default only — keep it that way.
- There is **no** platform-admin role today (`role=owner` is tenant-scoped). Ops must not be “any owner”.

## Locked decisions

| Item | Choice |
|------|--------|
| Allowlist | `PLAN_MODULES` dict in `db.py` (or `services/entitlements.py`) |
| `free` | `base` only |
| `starter` | `base`, `inventory`, `pos` |
| `pro` | starter + purchase_store, production, hrm, ai_assistant, ecommerce, localization packs |
| `enterprise` | all registry ids |
| Industry packs | `spinning`, `healthcare`, `weaving`, `telecom`, `textile_processing`, `pra` → entitle-only unless enterprise |
| Override | `module_meta[id].entitled === true` |
| Uninstall | does **not** clear entitled |
| Ops auth | env `OPS_ADMIN_EMAILS` (comma emails) matching `User.email` |
| Demos | seed demo tenants with `plan=enterprise` so QA/Apps stay unchanged |
| Flag | `ENFORCE_MODULE_PLANS` default true; false = old unrestricted install (rollback) |

## Pattern

```
install allowed iff
  MODULE_REGISTRY[id].always
  OR plan_allows(tenant.plan, id)
  OR json(module_meta).get(id, {}).get("entitled") is True
else HTTP 403
```

## API

New router `backend/routers/ops_tenants.py`, mounted in `main.py`:

- `GET /api/ops/tenants` — id, name, plan, enabled_modules
- `GET /api/ops/tenants/{id}/modules` — registry rows + entitled + installed + installable
- `PUT /api/ops/tenants/{id}/modules` — body `{ "entitled": ["spinning", "purchase_store"] }` (replace set; `base` implicit)
- `POST /api/ops/tenants/{id}/modules/{mid}/install` — entitle if needed + install

`GET /api/modules` gains `entitled: bool`, `installable: bool`.

Audit: `ops.entitle` / `ops.revoke` via `log_audit`.

## UI

`frontend/src/app/(dashboard)/apps/page.tsx` + `ModuleContext`: disable Install when `!installable`; tooltip “Not included in this plan. Contact Easy-Books.” Do not hide the card (discovery). **API 403 is the real gate.**

## Tests (`backend/tests/test_module_entitlements.py`)

- Free tenant POST spinning → 403
- Ops PUT entitled spinning → tenant install 200
- Second tenant still 403
- Tenant owner GET `/api/ops/tenants` → 403
- Uninstall spinning → `entitled` remains true; reinstall 200
- `always` (`base`) cannot be uninstalled (existing behaviour)

## Files

- `backend/db.py` or `backend/services/entitlements.py`
- `backend/routers/modules.py`
- `backend/routers/ops_tenants.py` (new)
- `backend/main.py`
- `frontend/src/app/(dashboard)/apps/page.tsx`
- `frontend/src/context/ModuleContext.tsx`
- `backend/scripts/seed_demo.py` (demo `plan=enterprise` if needed)

## Acceptance

Operator can sell spinning to mill A tomorrow without giving mill A healthcare, and without a `client-mill` branch.

## Out of scope

Marketplace audience (issue B), custom fields, Stripe billing UI.
```

---

## Issue B — Marketplace audience

**Title:** `feat(marketplace): catalog audience filter, tags, and For you badge`

**Body:**

```markdown
## Part of

Epic: Tenant entitlements, Marketplace audience, and Studio-lite customization

## Goal

Marketplace lists **products**, not tenants. Custom mill listings are `audience: private` and appear only for entitled tenant ids, with badge **For you**. Hospital catalog JSON must not contain that listing id.

## Context

- `#227` catalog is identical for every tenant (`resolve_catalog` + bundled `_CURATED`).
- `CatalogEntry.tags` already exists; Apps Marketplace tab does **not** render tags.
- `first_party_module` already shows a **First-party** pill.
- Per-tenant `marketplace_catalog_url` exists as an escape hatch — keep it, but **do not** use N URLs as the primary private-app mechanism.

## Locked decisions

| Item | Choice |
|------|--------|
| Visibility field | `audience`: `public` \| `entitled` \| `private` |
| Private | `visible_to_tenant_ids: number[]` |
| Entitled | `entitled_module` must be entitled or installed (depends on issue A) |
| Filter location | `GET /api/marketplace/catalog` only — never UI-only |
| Tags | topical (`tax`, `pakistan`, `spinning`, `first-party`, `private`) |
| Forbidden tags | tenant slugs, `customized-tenant`, client names |
| Badge | **For you** when `audience !== "public"` |
| Tenants as cards | never |

## Pattern

```python
def visible_to(entry: CatalogEntry, tenant: Tenant) -> bool:
    if entry.audience == "public":
        return True
    if entry.audience == "private":
        return tenant.id in entry.visible_to_tenant_ids
    if entry.audience == "entitled":
        mid = entry.entitled_module
        return bool(mid) and is_entitled_or_installed(tenant, mid)
    return False
```

## API / schema

Extend `CatalogEntry` in `backend/services/marketplace/manifest.py`. Bundled `_CURATED` entries default `audience=public`. Catalog payload includes `audience`, `tags`, `entitled_module`.

Update `docs/MARKETPLACE.md`.

## UI

`frontend/src/app/(dashboard)/apps/page.tsx` `renderMarketplace`:

- Chip row for `entry.tags`
- **For you** pill next to First-party / Installed

## Tests

Extend `backend/tests/test_marketplace.py`:

- Tenant A sees private id; tenant B’s `entries` has no that `id`
- `entitled` listing hidden until module entitled/installed
- Remote catalog row with someone else’s `visible_to_tenant_ids` does not leak to current tenant

## Acceptance

Two TestClient users (two tenants) hit `/api/marketplace/catalog`; private mill listing is only in mill’s JSON.

## Out of scope

Studio bundle apply-on-install (issue G). Do not add a “Tenants” tab.
```

---

## Issue C — Custom fields

**Title:** `feat(studio): tenant custom fields (x.*) on documents`

**Body:**

```markdown
## Part of

Epic: Tenant entitlements, Marketplace audience, and Studio-lite customization

## Goal

QuickBooks-shaped custom fields: mill invoice has `x.gate_pass_no`, clinic has `x.mrn`, **same** `InvoiceForm.tsx`. Values do not affect GL.

## Locked decisions

| Item | Choice |
|------|--------|
| Key pattern | `^x\.[a-z][a-z0-9_]*$` |
| Storage | JSON column `custom_fields` default `{}` on Invoice, Bill, Customer, Product, Vendor |
| Defs table | `CustomFieldDef` (tenant_id, entity, key, label, type, …) |
| Types | text, number, date, enum, bool |
| Cap | 12 non-archived defs per (tenant, entity) |
| GL | never read in `posting.py` |
| Delete | archive (`archived_at`); keep historical values |
| Entities v1 | invoice, bill, customer, product, vendor |
| Permission | `studio.fields` |

## Data model

See spec § Custom fields. Unique `(tenant_id, entity, key)`. Alembic `0080_custom_fields.py` with `has_table` / column existence guards.

## API

`/api/studio/fields` CRUD (admin/owner). Document create/update accept `custom_fields` object; `services/custom_fields.validate_payload` strips unknown keys, 400 on type/required errors.

## UI

`components/studio/CustomFieldsInputs.tsx` used first on `InvoiceForm`, then bill/customer/product. List pages: optional column when `show_on_list`.

## Tests (`backend/tests/test_custom_fields.py`)

- 13th def → 400
- key `discount_pct` or `ext.foo` → 400
- enum mismatch → 400
- tenant isolation on GET defs
- create invoice with custom_fields; existing posting/balance tests still pass

## Acceptance

Mill saves gate pass on an invoice; clinic invoice form has no that input; Dr/Cr unchanged.

## Out of scope

Form hide/show of **core** fields (issue D), report-builder columns (issue E).
```

---

## Issue D — Form schema

**Title:** `feat(studio): tenant form schema hide/show/required with API enforcement`

**Body:**

```markdown
## Part of

Epic: Tenant entitlements, Marketplace audience, and Studio-lite customization

Depends on: custom fields (issue C) so schema can reference `x.*`.

## Goal

Odoo Studio-lite: tenant (or role) JSON says which **allowlisted** core fields and `x.*` are visible/required/read-only. One React form reads the schema. API enforces the same rules (no CSS-only hiding).

## Locked decisions

| Item | Choice |
|------|--------|
| Scope | tenant default `role='*'`; optional per-role row |
| Not in v1 | per-user form designer |
| Locked (cannot hide) | invoice `issue_date`, `due_date`, `customer_id`, `subtotal`, `gst_amount`, `total` (+ line qty/rate/amount stay visible) |
| Hidden writes | drop hidden keys on PUT/POST (import-friendly); 400 if required missing |
| Missing schema key | shipped default = visible |

## Data model

`FormSchema` PK `(tenant_id, entity, role)`, `schema` JSON. Alembic `0081_form_schema.py`.

Example:

```json
{
  "version": 1,
  "fields": {
    "notes": { "visible": false },
    "analytic_2_id": { "visible": true, "required": true },
    "x.gate_pass_no": { "visible": true, "required": true, "order": 40 }
  }
}
```

## API

- `GET /api/studio/forms/{entity}` — resolved for current user’s role
- `PUT /api/studio/forms/{entity}` — admin/owner; reject locked hides (`studio.forms`)

Document routers call `apply_to_payload`.

## UI

InvoiceForm (then bill) fetches schema; skip render of `visible: false`; native `required` for required visibles.

## Tests

- Hide `notes` → omitted UI field; PUT `notes` ignored
- Hide `customer_id` on PUT schema → 400
- Required `x.gate_pass_no` missing → 400

## Acceptance

Two tenants, same `InvoiceForm.tsx`, different visible fields; crafted POST cannot set a hidden field.

## Out of scope

Field-level UserPermission (issue F), print templates (issue E).
```

---

## Issue E — Print + reports

**Title:** `feat(studio): print template picker/clone and report-builder x.* columns`

**Body:**

```markdown
## Part of

Epic: Tenant entitlements, Marketplace audience, and Studio-lite customization

Depends on: custom fields (issue C).

## Goal

QBO-style print/report patterns: tenant picks or clones invoice/bill HTML; report builder can choose `x.*` columns. Templates live in the DB for clones; built-ins stay `backend/templates/invoice.html` and `bill.html`.

## Locked decisions

| Item | Choice |
|------|--------|
| v1 entities | invoice, bill |
| Built-in | `standard` → existing Jinja files |
| Clone | copy HTML into `PrintTemplate.html` |
| Engine | WeasyPrint + **sandboxed** Jinja (`SandboxedEnvironment`, no `{% include %}` of paths) |
| Custom on PDF | `custom_fields['x.gate_pass_no']` if `show_on_print` |
| Report builder | virtual field keys from defs; SQLite `json_extract` / PG `->>` |
| Unknown `x.*` in ReportConfig | 400 (same as unknown whitelist key) |

## Data model

`PrintTemplate` (tenant_id, entity, key, label, html?, is_default). One default per (tenant, entity). Alembic `0082_print_templates.py`.

## API

CRUD `/api/studio/print-templates`; PDF endpoints use tenant default clone if present else file.

## Tests

- Default PDF still 200
- Clone referencing `custom_fields` renders the value
- Tenant B cannot fetch A’s template id
- Report run with `x.gate_pass_no` returns the JSON value; bogus `x.nope` → 400

## Acceptance

Mill prints a packing-style invoice with gate pass; clinic keeps standard template; both on one deploy.

## Out of scope

Email-scheduled reports, arbitrary user SQL, partner-uploaded Python.
```

---

## Issue F — Field-level rights

**Title:** `feat(rights): field-level UserPermission overlay on form schema`

**Body:**

```markdown
## Part of

Epic: Tenant entitlements, Marketplace audience, and Studio-lite customization

Depends on: form schema (issue D).

## Goal

Two **users in the same tenant** can have different field utility (store clerk edits `x.gate_pass_no`, salesperson views it) without a per-user form designer.

## Locked decisions

| Item | Choice |
|------|--------|
| Storage | existing `UserPermission.resource_key` (sparse) |
| Key format | `invoices.field.x.gate_pass_no` (parent resource + `.field.` + key) |
| Default | inherit parent resource (`invoices`) |
| Viewer + required field | show read-only; omit on save |
| Schema vs rights | AND: schema visible AND permission ≠ none |

## UI

Permissions matrix: collapsed “Fields” section listing current tenant `CustomFieldDef` rows. Do not pre-register N×M keys in `PERMISSION_RESOURCES`.

## Tests (`backend/tests/test_field_permissions.py`)

- Accountant with invoices=edit writes custom_fields 200
- Viewer with invoices=view writing custom_fields → 403 or stripped
- `none` on field key hides input even if schema visible

## Acceptance

Same invoice form, same tenant schema, two roles, different editability.

## Out of scope

Row-level security beyond existing `my_data_only`.
```

---

## Issue G — Studio UI + Marketplace bundle

**Title:** `feat(studio): Settings Studio page and declarative Marketplace studio bundle`

**Body:**

```markdown
## Part of

Epic: Tenant entitlements, Marketplace audience, and Studio-lite customization

Depends on: issues B, C, D, E (APIs exist; this is the partner/no-code shell).

## Goal

**Track A:** tenant admin configures fields/forms/print under Settings → Studio (no partner).  
**Track B:** a Marketplace listing may include a `studio` object; install writes overlay rows; uninstall archives rows sourced from that extension. **Still no executable partner code** (`#227` boundary unchanged).

**Track C** (API keys + webhooks) is already shipped — document in Studio page help text only.

## Locked decisions

| Item | Choice |
|------|--------|
| Nav | System → Studio, admin/owner, `/settings/studio` |
| Bundle | optional `studio` on `CatalogEntry` |
| Install | write CustomFieldDef + form_schema_patch + print template; set `source_extension_id` |
| Uninstall | archive defs with that source; keep document JSON values |
| Code execution | forbidden (existing marketplace install path) |

## Bundle shape

```json
{
  "studio": {
    "custom_fields": [
      { "entity": "invoice", "key": "x.gate_pass_no", "label": "Gate pass", "type": "text", "show_on_form": true, "show_on_print": true }
    ],
    "form_schema_patch": {
      "invoice": { "fields": { "x.gate_pass_no": { "visible": true, "required": true } } }
    },
    "print_template_key": "standard"
  }
}
```

Private mill listing: `audience: private`, `visible_to_tenant_ids: [mill]`, **For you** + Install applies bundle.

## UI

`frontend/src/app/(dashboard)/settings/studio/page.tsx` — tabs Fields / Form layout / Print. Wire existing APIs. Add nav in `lib/nav.ts` (NAV + SUB_NAV/TOP_NAV).

## Tests

- Install bundle creates def; catalog `installed: true`
- Uninstall archives def; values on old invoices remain
- Manifest with `studio` but still “no partner code was executed”
- Existing `test_marketplace.py` still green

## Acceptance

Partner ships mill overlay as a private listing; hospital never sees the card; mill invoice form gains the field after Install.

## Out of scope

Track D (Odoo Python-in-process). Public unvetted uploads. Per-client git branch.
```
