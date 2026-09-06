# Marketplace — third-party extensions (#227)

Easy-Books ships first-party modules via `MODULE_REGISTRY`. The **Marketplace**
adds a curated catalog of *third-party* listings with a hard sandbox boundary.

## Acceptance mapping

| Requirement | Where |
|-------------|--------|
| Extension point / manifest format | `backend/services/marketplace/manifest.py` → `ExtensionManifest` |
| Install UI listing remote catalog | Add-ons → **Marketplace** tab; `GET /api/marketplace/catalog` |
| Sandbox / permission boundary documented | This file + `GET /api/marketplace/boundary` |

**Out of scope (still):** public unvetted uploads, payments, arbitrary code execution.

## Manifest format

Every listing is a declarative JSON object validated by Pydantic:

```json
{
  "id": "partner.acme.bank-csv",
  "name": "Bank CSV Helper",
  "version": "1.0.0",
  "description": "…",
  "publisher": "Acme Partners",
  "category": "Integrations",
  "icon": "Landmark",
  "homepage": "https://example.com",
  "docs_url": "https://example.com/docs",
  "requires_modules": ["base"],
  "requested_permissions": ["read_reports", "read_invoices"],
  "settings_keys": ["ext.acme.host"],
  "webhook_events": ["invoice.posted"],
  "curated": true
}
```

Rules enforced at validation time:

- `id` must match `partner.<publisher>.<slug>`
- `version` must be semver-like (`1.0.0`)
- `settings_keys` must be prefixed with `ext.` (never overwrite core settings)
- `homepage` / `docs_url` must be `https://` (or `http://localhost` for local docs)

### Catalog entry wrapper

```json
{
  "summary": "Short card blurb",
  "tags": ["csv", "bank"],
  "first_party_module": null,
  "audience": "public",
  "visible_to_tenant_ids": [],
  "entitled_module": null,
  "manifest": { "...": "ExtensionManifest" }
}
```

`audience` is filtered on **`GET /api/marketplace/catalog`** (never only in React):

| `audience` | Who sees the card |
|------------|-------------------|
| `public` (default) | Every signed-in tenant |
| `entitled` | Tenants that have `entitled_module` entitled **or** installed |
| `private` | Granted tenants (`visible_to_tenant_ids`, ops `module_meta._marketplace_private`, or `MARKETPLACE_PRIVATE_AUDIENCE`) |

Private mill listings use topical tags (`spinning`, `private`) plus badge **For you**. Do **not** tag with tenant slugs or `customized-tenant`. Marketplace lists **products**, never tenants.

Empty `visible_to_tenant_ids` on a bundled private row is **fail-closed**. Ops grant the listing with `PUT /api/ops/tenants/{id}/marketplace-private` (`extension_ids`), which stores ids on `tenant.module_meta._marketplace_private`. Demo seed and boot-time backfill grant **Weighbridge** (`partner.easybooks.weighbridge`) to manufacturing and yarn-spinning tenants. Those mill models also pass the catalog `visible_to` check without a grant, so an existing demo DB shows the card after deploy (no re-seed). Hospital and other models stay fail-closed. Optional env overlay:

```
MARKETPLACE_PRIVATE_AUDIENCE={"partner.easybooks.weighbridge":[12]}
```

Hospital (and any ungranted tenant) `GET /api/marketplace/catalog` JSON **does not include** that listing id. Install by another tenant returns 404.

## Weighbridge — how a mill user uses it

**Weighbridge** is the bundled private mill listing (`partner.easybooks.weighbridge`). It ships a `studio` bundle: invoice **Gate pass** (`x.gate_pass_no`, required, printed) and **Lot ref** (`x.lot_ref`, optional, form-only). Install writes `CustomFieldDef` rows; uninstall archives them. Values never post to the GL. No partner code runs.

Mills also have a first-party **Weighbridge** module (`weighbridge`) — ticket workspace under its own nav section (#391). The listing is the invoice overlay; the module is the scale desk. See [USER_GUIDE.md §41](../USER_GUIDE.md#41-weighbridge-mill-workspace).

**User path**

1. Log in as a mill (`demo.manufacturing@easy-books.app` or `demo.spinning@easy-books.app` / `demo1234`).
2. **System → Add-ons** (Marketplace auto-opens when **For you** listings exist), or Ctrl+K → `weighbridge`, or `/apps?tab=marketplace`.
3. **Install** Weighbridge.
4. **Sales → New Invoice** — enter Gate pass (required) and Lot ref (optional); save/post as usual.
5. Print the invoice to see Gate pass. Tweak labels/visibility in **Settings → Studio**.

Manufacturing and yarn-spinning tenants pass `visible_to` even without a seed grant (boot-time backfill still writes `_marketplace_private`). See [USER_GUIDE.md §41](../USER_GUIDE.md#41-weighbridge-mill-marketplace-listing).

Install of a hidden listing returns 404 for other tenants (same `visible_to` gate as the catalog).

When `first_party_module` is set (e.g. `"pra"`), **Install** calls the existing
`/api/modules/{id}/install` path — the marketplace is a discovery surface for
built-in packs as well as partner metadata.

## Sandbox / permission boundary

**Install never executes partner code.** There is no download of JS/Python
bundles, no `eval`, and no process spawn from a manifest.

| Layer | Behaviour |
|-------|-----------|
| Process | Easy-Books runtime stays first-party only |
| Settings | Partner keys must live under `ext.*` |
| Permissions | `requested_permissions` are **recorded** on install for audit / future partner API gates — they do **not** silently widen JWT scopes in v1 |
| Modules | `requires_modules` may only reference `MODULE_REGISTRY` ids |
| Catalog | Bundled curated list, optionally extended by `MARKETPLACE_CATALOG_URL` env or tenant setting `marketplace_catalog_url` (HTTPS JSON). Rows are filtered per tenant by `audience`. Whoever hosts that URL is responsible for curation. |
| Upload | No public submit endpoint |

Installed partner snapshots are stored on the tenant under
`module_meta._extensions` (version, permissions, settings keys, full manifest).

## API

| Method | Path | Who |
|--------|------|-----|
| GET | `/api/marketplace/boundary` | any signed-in user |
| GET | `/api/marketplace/catalog` | any signed-in user |
| GET | `/api/marketplace/extensions` | any signed-in user |
| POST | `/api/marketplace/extensions/{id}/install` | admin / owner |
| POST | `/api/marketplace/extensions/{id}/uninstall` | admin / owner |

## Adding a curated listing

1. Author a valid `ExtensionManifest`.
2. Append it to `_CURATED` in `backend/services/marketplace/catalog.py` **or**
   publish it on a private curated JSON feed and set `MARKETPLACE_CATALOG_URL`.
3. Open a PR for in-repo listings — reviewers check publisher trust + permission scope.

## UI

**Add-ons → Marketplace** lists catalog cards with Install / Uninstall, topical
tag chips, and a **For you** pill when `audience` is not `public`.
A short sandbox callout is rendered from `/api/marketplace/boundary`.

## Shipped: audience + Studio bundles

Catalog rows are filtered per tenant (`public` / `entitled` / `private`). **For you** appears on non-public cards. Declarative `studio` overlays (custom fields + form schema + print template, still no partner code) apply on Marketplace install. Spec:

- `docs/superpowers/specs/2026-09-06-tenant-customization-studio-design.md`
- Shipped PRs **#377–#383** (entitlements through Studio), **#384** (Weighbridge listing), **#387** (mill tenants find the card without a re-seed).
