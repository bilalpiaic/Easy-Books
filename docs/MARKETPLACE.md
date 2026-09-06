# Marketplace — third-party extensions (#227)

Easy-Books ships first-party modules via `MODULE_REGISTRY`. The **Marketplace**
adds a curated catalog of *third-party* listings with a hard sandbox boundary.

## Acceptance mapping

| Requirement | Where |
|-------------|--------|
| Extension point / manifest format | `backend/services/marketplace/manifest.py` → `ExtensionManifest` |
| Install UI listing remote catalog | Apps → **Marketplace** tab; `GET /api/marketplace/catalog` |
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
  "manifest": { "...": "ExtensionManifest" }
}
```

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
| Catalog | Bundled curated list, optionally extended by `MARKETPLACE_CATALOG_URL` env or tenant setting `marketplace_catalog_url` (HTTPS JSON). Whoever hosts that URL is responsible for curation. |
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

**Add-ons → Marketplace** lists catalog cards with Install / Uninstall.
A short sandbox callout is rendered from `/api/marketplace/boundary`.

## Planned: audience + Studio bundles

Catalog rows are currently the same for every tenant. Private / entitled
listings, a **For you** badge, and optional declarative `studio` overlays
(custom fields + form schema + print template, still no partner code) are
specified in:

- `docs/superpowers/specs/2026-09-06-tenant-customization-studio-design.md`
- `docs/github-issues/tenant-customization-studio.md` (epic + child issues A–G)
