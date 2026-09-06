# Tenant customization / Studio-lite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan **one GitHub child issue at a time**. Do not implement all seven phases in one PR. Each phase is a separate PR that lands on `main` before the next starts.

**Goal:** Entitlements, Marketplace audience, custom fields, form schema, print templates, field-level rights, and a declarative Studio bundle — so two tenants on one deploy see different modules, Marketplace cards, and invoice fields without git forks.

**Architecture:** Metadata overlays on existing `Tenant` / Settings / Marketplace / shipped React forms. Platform ops routes gated by `OPS_ADMIN_EMAILS`. Custom field values as JSON on documents. Form schema JSON per `(tenant, entity, role)`. Marketplace `audience` filtered in `get_catalog`.

**Tech stack:** FastAPI / SQLModel / Alembic, Next.js 16 / React 19 / TypeScript, pytest.

**Spec:** `docs/superpowers/specs/2026-09-06-tenant-customization-studio-design.md`

**Issue pack:** `docs/github-issues/tenant-customization-studio.md`

## Global constraints

- Every query tenant-scoped except `/api/ops/*` (platform operator, env-gated).
- SQLite Alembic: `has_table` guards on new tables; strip `ADD CONSTRAINT` on ALTER (migrations 0016/0017 pattern). Next revision **`0080`** and up.
- Custom field keys `^x\.[a-z][a-z0-9_]*$`; settings still `ext.*` for partners.
- `x.*` never imported in `services/posting.py`.
- Dates in UI via `fmtDate` / `fmtDateJs`.
- `apiFetch` for all frontend calls. lucide-react only.
- Do not add per-client branches, Vercel projects, or `client-*` catalog tags.
- Backend tests: `cd backend && PYTHONPATH=. uv run pytest` (narrow `-k` first, then the new files).
- Frontend: `cd frontend && npm run lint` on touched files.

---

## Phase 1 — Module entitlements (child issue A)

**Files:**
- Modify: `backend/db.py` (`PLAN_MODULES` next to `MODULE_REGISTRY`)
- Modify: `backend/routers/modules.py` (`install_module` 403)
- Create: `backend/routers/ops_tenants.py`
- Modify: `backend/main.py` (mount router)
- Modify: `frontend/src/app/(dashboard)/apps/page.tsx`, `frontend/src/context/ModuleContext.tsx`
- Test: `backend/tests/test_module_entitlements.py`

**PLAN_MODULES (locked for v1):**

```python
PLAN_MODULES: dict[str, list[str] | None] = {
    "free": ["base"],
    "starter": ["base", "inventory", "pos"],
    "pro": [
        "base", "inventory", "pos", "purchase_store", "production", "hrm",
        "ai_assistant", "ecommerce", "sa_zatca", "in_gst", "eu_peppol", "uae_vat",
    ],
    "enterprise": None,  # None = all MODULE_REGISTRY keys
}
```

Industry packs (`spinning`, `healthcare`, `weaving`, `telecom`, `textile_processing`, `pra`) require `module_meta[id].entitled is True` unless plan is `enterprise`.

**Ops auth:** `OPS_ADMIN_EMAILS` env (comma-separated). Dependency `PlatformOpsDep` raises 403 if `user.email` not in the set. Do not use tenant `role=owner`.

- [ ] **P1.1** Add `PLAN_MODULES` + helpers `plan_allows(tenant, module_id)` and `is_entitled(tenant, module_id)` in `db.py` or `services/entitlements.py`.
- [ ] **P1.2** `install_module`: if not `always` and not entitled and not plan-allowed → 403. Uninstall unchanged. Entitlement is **not** cleared on uninstall.
- [ ] **P1.3** `GET /api/modules` includes `entitled: bool` and `installable: bool` per row.
- [ ] **P1.4** Ops router: list tenants; get/put entitled set; optional install-after-entitle. Audit-log `ops.entitle` / `ops.revoke`.
- [ ] **P1.5** Apps page: disable Install when `!installable`; tooltip “Not included in this plan”.
- [ ] **P1.6** Tests: free tenant 403 on spinning; after PUT entitled, install 200; second tenant still 403; owner cannot call `/api/ops/*`.

**Done when:** mill can be entitled to spinning from ops; clinic cannot install it; demo tenants still seed via existing seeder (seeder sets `entitled` for modules it installs, or uses enterprise plan for demos — pick **demo tenants `plan=enterprise`** so QA is unchanged).

---

## Phase 2 — Marketplace audience (child issue B)

**Files:**
- Modify: `backend/services/marketplace/manifest.py` (`CatalogEntry`)
- Modify: `backend/services/marketplace/catalog.py` (bundled entries default `audience=public`)
- Modify: `backend/routers/marketplace.py` (`get_catalog` filter)
- Modify: `frontend/src/app/(dashboard)/apps/page.tsx`
- Modify: `docs/MARKETPLACE.md`
- Test: `backend/tests/test_marketplace.py` (extend)

- [ ] **P2.1** Add `audience`, `visible_to_tenant_ids`, `entitled_module` to `CatalogEntry` with defaults.
- [ ] **P2.2** Filter function `visible_to(entry, tenant) -> bool`. Apply in `get_catalog` only. Log/skip malformed remote rows.
- [ ] **P2.3** Catalog JSON includes `audience` and `tags`. UI: chips for tags; **For you** when `audience !== "public"`.
- [ ] **P2.4** Test: two tenants; private listing visible_to A only; B’s `entries` ids do not include it. Entitled listing appears after entitle.

**Done when:** a hospital tenant’s catalog JSON cannot contain a mill-only listing id.

---

## Phase 3 — Custom fields (child issue C)

**Files:**
- Modify: `backend/models.py` (`CustomFieldDef` + `custom_fields` JSON on Invoice/Bill/Customer/Product/Vendor)
- Create: `backend/alembic/versions/0080_custom_fields.py`
- Create: `backend/routers/custom_fields.py`
- Modify: document create/update routers (invoices, bills, customers, products, vendors) to validate/store JSON
- Modify: `frontend/src/components/invoices/InvoiceForm.tsx` (+ bill/customer/product forms — invoice first, others same helper)
- Create: `frontend/src/components/studio/CustomFieldsInputs.tsx`
- Test: `backend/tests/test_custom_fields.py`

**Validation helper** `services/custom_fields.py`: `validate_payload(session, tenant_id, entity, data) -> dict` (strips unknown, 400 on bad type/required/archived).

- [ ] **P3.1** Model + migration (`has_table` / new columns with existence guards).
- [ ] **P3.2** CRUD `/api/studio/fields` (admin/owner, `perm_dep("studio.fields", "edit")`). Register resource in `PERMISSION_RESOURCES`.
- [ ] **P3.3** Wire invoice create/update; posting tests still pass with `custom_fields={"x.note":"a"}`.
- [ ] **P3.4** `CustomFieldsInputs` on InvoiceForm; list column if `show_on_list`.
- [ ] **P3.5** Tests: 13th field 400; key `foo` 400; enum mismatch 400; tenant B cannot read A’s defs.

**Done when:** mill can add `x.gate_pass_no` on invoices; value round-trips; GL unchanged.

---

## Phase 4 — Form schema (child issue D)

**Depends on:** Phase 3 (schema references `x.*` keys).

**Files:**
- Modify: `backend/models.py` (`FormSchema`)
- Create: `backend/alembic/versions/0081_form_schema.py`
- Create: `backend/services/form_schema.py` (`resolve_schema`, `LOCKED_FIELDS`, `apply_to_payload`)
- Create: `backend/routers/form_schema.py`
- Modify: InvoiceForm (and later bill) to GET schema and hide/require
- Test: `backend/tests/test_form_schema.py`

`LOCKED_FIELDS["invoice"] = {"issue_date", "due_date", "customer_id", "subtotal", "gst_amount", "total"}` (plus line qty/rate/amount on line editor — lines stay visible).

- [ ] **P4.1** Table + GET/PUT `/api/studio/forms/{entity}`. PUT rejects locked hides.
- [ ] **P4.2** Document write paths call `apply_to_payload` (drop hidden keys; 400 if required missing).
- [ ] **P4.3** InvoiceForm: fetch schema; do not render invisible fields; HTML `required` matches schema.
- [ ] **P4.4** Tests: hide `notes` ok; hide `customer_id` 400; required `x.gate_pass_no` missing 400.

**Done when:** two tenants’ invoice screens differ using the same component; crafted POST cannot set a hidden field.

---

## Phase 5 — Print templates + report builder `x.*` (child issue E)

**Depends on:** Phase 3.

**Files:**
- Modify: `backend/models.py` (`PrintTemplate`)
- Create: `backend/alembic/versions/0082_print_templates.py`
- Modify: `backend/services/pdf.py` (select template)
- Create: `backend/routers/print_templates.py`
- Modify: `backend/services/report_engine.py` + `report_sources` (inject dynamic `x.*` for sources that have `custom_fields`)
- Frontend: Settings Studio print picker; invoice print uses default
- Test: `backend/tests/test_print_templates.py`, extend `test_report_builder_run.py`

- [ ] **P5.1** Built-in keys `standard` (current HTML files). Clone copies file into `PrintTemplate.html`.
- [ ] **P5.2** Jinja sandbox: `SandboxedEnvironment`, no filesystem includes.
- [ ] **P5.3** Report builder: for invoices source, append FieldDef-like virtual keys from non-archived defs; engine reads JSON (SQLite `json_extract` / Postgres `->>`). Unknown `x.*` in config → 400.
- [ ] **P5.4** Tests: default PDF still renders; clone with `{{ custom_fields['x.gate_pass_no'] }}`; tenant B cannot run A’s template id.

**Done when:** mill can clone invoice HTML and print a gate-pass line; report builder can column-choose `x.gate_pass_no`.

---

## Phase 6 — Field-level rights (child issue F)

**Depends on:** Phase 4.

**Files:**
- Modify: `backend/services/permissions.py` (resolve `studio.field.invoice.x.gate_pass_no` or `invoices.field.x.gate_pass_no`)
- Modify: `backend/services/form_schema.py` (AND role overlay + permission)
- Modify: `frontend/src/app/(dashboard)/settings/permissions/page.tsx` (optional field rows, collapsed)
- Test: `backend/tests/test_field_permissions.py`

Keep unique `(tenant_id, user_id, resource_key)` — field keys are just more `resource_key` strings. Default inherit parent resource (`invoices`).

- [ ] **P6.1** Document the key format in `PERMISSION_RESOURCES` as a pattern, not 12×N static rows. Matrix UI lists defs for the tenant dynamically.
- [ ] **P6.2** Viewer with `invoices=view` cannot edit `x.*` even if schema says required (required + view → show read-only; save omitted).
- [ ] **P6.3** Tests: accountant edit, viewer 403 on writing custom_fields.

**Done when:** two users in the **same** tenant can have different invoice field utility without a second schema designer per user.

---

## Phase 7 — Settings Studio UI + Marketplace bundle (child issue G)

**Depends on:** Phases 2–5.

**Files:**
- Create: `frontend/src/app/(dashboard)/settings/studio/page.tsx`
- Modify: `frontend/src/lib/nav.ts` (System → Studio, admin/owner, `forModule` none)
- Modify: `backend/services/marketplace/manifest.py` (`StudioBundle` optional)
- Modify: `backend/services/marketplace/install.py` (apply/remove bundle)
- Test: `backend/tests/test_studio_bundle.py`

- [x] **P7.1** Studio page: tabs Fields / Form / Print. Uses existing APIs.
- [x] **P7.2** `studio` on catalog entry; install writes defs with `source_extension_id`; uninstall archives defs, keeps values.
- [x] **P7.3** Private listing + studio bundle = mill “Weighbridge” card **For you** (PRs #384, #387).
- [x] **P7.4** Tests: install bundle creates `x.gate_pass_no`; uninstall archives it; `#227` boundary text unchanged (no code execution).

**Done when:** a partner can ship a mill overlay as a private Marketplace listing without a git branch.

---

## Suggested PR sequence

| PR | Child | Title |
|----|--------|--------|
| 1 | A | feat(entitlements): plan allowlist + ops entitle + install 403 |
| 2 | B | feat(marketplace): catalog audience filter + For you badge |
| 3 | C | feat(studio): custom fields on documents |
| 4 | D | feat(studio): tenant form schema |
| 5 | E | feat(studio): print templates + report-builder x.* |
| 6 | F | feat(rights): field-level permission overlay |
| 7 | G | feat(studio): Settings Studio + marketplace bundle |

Do not merge C before A (demo `plan=enterprise` must land or demo Apps break). B can parallel A after A’s `entitled` flag exists for `entitled` audience.

## Rollback

Each phase is additive. Entitlements default: if `PLAN_MODULES` missing in an old process, treat as **unrestricted** only when env `ENFORCE_MODULE_PLANS=false` (default **true** in production). Safer launch: ship A with `ENFORCE_MODULE_PLANS=false`, entitle demo+pilot tenants, then flip true.
