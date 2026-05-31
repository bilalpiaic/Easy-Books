# Standalone-Install Polish — Design

**Date:** 2026-05-31
**Status:** Draft for review
**Scope:** Six related improvements to make Easy-Books pleasant and safe to install, evaluate, and **update** on a standalone Windows PC/laptop — plus a 2-level stock-category feature and a dashboard layout tweak.

---

## 1. Background & problem

Easy-Books ships two standalone install paths:

- **Script installer** — `install-and-run.bat` → `install-and-run.ps1` (and `.sh` on \*nix). Launches `uvicorn main:app` directly.
- **Desktop app** — Electron shell (`desktop/main.js`) supervising a PyInstaller backend (`run_packaged.py`) + the Next.js standalone server.

Six problems / requests, traced to the code:

| # | Request | Root cause |
|---|---------|-----------|
| ① | Demo seed data not visible after install | Rich seeder `scripts.seed_demo` is **only** run by `dev.sh:56`. No standalone installer calls it. The desktop app additionally sets `SEED_DEMO=false` (`desktop/main.js:19`, `run_packaged.py:30`), so even the demo *logins* don't exist. |
| ② | Stock products need parent → sub category (2 levels) | `Product` (`models.py:339`) has **no** category field at all. |
| ③ | Quick Actions should be at the top, aligned | Currently bottom-left of the dashboard grid (`dashboard/page.tsx:387-409`). |
| ④ | How does a user get updates? What happens to their DB? | Data lives outside the app dir (safe), but: script path uses `create_all()` (adds tables, **not columns**); `electron-updater` is a dependency but **unwired**; no update command for scripts. |
| ⑤ | Update all `.md` guides & workflows | Docs predate the standalone/desktop/update story. |
| ⑥ | Restructure `README.md` | Same. |

### Key insight — these are not fully independent
② adds a **column** to `Product`. On the script path (`create_all`), existing users would **not** get that column on update → broken schema. So ④'s "run Alembic on update" fix is a **prerequisite** for shipping ② safely. WS-1 is therefore foundational and goes first.

---

## 2. Goals / non-goals

**Goals**
- Existing users' databases migrate forward safely on every update (no data loss, new columns applied) on **both** install paths.
- A clean install stays clean; an evaluator can load the 5 demo companies (and remove them) with one click.
- Products support a user-managed 2-level category hierarchy.
- Quick Actions sit in a prominent top toolbar.
- Best-practice update *delivery* is wired: desktop auto-update + a script update command.
- Docs and README reflect the current reality.

**Non-goals**
- Buying a code-signing certificate or publishing an actual GitHub Release (operational, owned by the maintainer — documented as a runbook).
- Multi-level (3+) category trees — explicitly capped at 2.
- Changing the hosted/SaaS deployment behaviour (Vercel/Postgres) beyond what the shared `db.py` refactor requires.

---

## 3. Workstreams

### WS-1 — Safe schema migration on update *(foundational, item ④a)*

**Problem:** `create_db_and_tables()` in `db.py` couples **table creation** and **all seeding**, gated by `SCHEMA_BOOTSTRAP=create_all` (`main.py:40`). Switching the script path to Alembic naively would disable seeding.

**Design:** decouple into two explicit functions:
- `bootstrap_schema()` — `create_all()` when `SCHEMA_BOOTSTRAP=create_all`; **no-op** when `alembic` (migrations already ran).
- `seed_defaults()` — first-run seeding (default tenant + CoA + admin), **always** safe/idempotent, independent of bootstrap mode.

`main.py` lifespan calls `bootstrap_schema()` then `seed_defaults()`. Script installers (`install-and-run.ps1/.sh`) run `alembic upgrade head` **before** launching and set `SCHEMA_BOOTSTRAP=alembic`, matching the desktop path (`run_packaged.py`). The startup demo-seed block stays **gated by `SEED_DEMO`** (default `false` for standalone, `true` for the hosted demo) so hosted behaviour is unchanged; the *rich* on-demand seeding is additionally exposed via the WS-2 endpoint. Shared seeding logic is reused via a **lazy import** to avoid a `db ↔ scripts.seed_demo` cycle.

**Result:** updating an existing `%USERPROFILE%\.easy-books\*.db` (scripts) or Electron `userData` DB (desktop) migrates in place; data preserved; new columns applied.

### WS-2 — One-click sample data *(item ①)*

**Backend:** new admin endpoint `POST /api/admin/demo/seed` → calls `scripts.seed_demo.seed_all_demos()` (already idempotent; returns per-tenant counts). Companion `DELETE /api/admin/demo/seed` removes the 5 demo tenants + their data for a clean evaluation teardown. Both are **owner/admin-only** and a no-op-safe.

**Frontend:** a "Sample / demo data" card in `settings` →
- **Load demo companies** — confirm dialog ("creates 5 demo companies you can log into with `demo1234`; your own company is untouched") → progress → success summary.
- **Remove demo companies** — confirm → teardown.

The 5 demo tenants are **separate** from the user's own tenant, so a real install is never polluted. Works identically on script + desktop installs (same frontend). The `.ps1/.sh/.bat` installers no longer try to imply demo data exists; `SEED_DEMO` stays `false` by default for a clean first run, and the button is the supported way to get demo content.

**Security note:** demo logins use the well-known password `demo1234`. The card copy states this; a security-conscious user simply won't load them (or removes them after evaluating).

### WS-3 — 2-level stock categories *(item ②)*

**Model (`models.py`):**
```
class ProductCategory(SQLModel, table=True):
    id, tenant_id (FK tenant, index)
    name: str
    parent_id: Optional[int]   # NULL → top-level "parent"; set → "sub-category"
    is_active: bool = True
    __table_args__ = UniqueConstraint(tenant_id, parent_id, name)
```
`Product.category_id: Optional[int]` FK → `productcategory.id`.

**2-level enforcement** (application-level, since SQLite can't easily express it): on create/update of a category, reject `parent_id` pointing at a row that itself has a non-NULL `parent_id`. Products attach to a **leaf** (sub-category) by convention; attaching to a top-level category is allowed when it has no children.

**Migration (Alembic, autogenerate then hand-fix):** new `productcategory` table guarded with `bind.dialect.has_table(...)`; new `product.category_id` column with the **FK line stripped** and an existence guard (per CLAUDE.md SQLite caveat / migrations 0016-0017 pattern). Integrity enforced at app level by tenant-scoped queries.

**Backend:** `routers/product_categories.py` (mirrors `routers/products.py` conventions: `APIRouter(prefix="/api/product-categories")`, `SessionDep`/`CurrentUserDep`/`WriteUserDep`, audit logging). Endpoints: list (nested parent→children), create, update, delete (blocked if it has children or assigned products). `products` router gains `category_id` on create/update and a `category_id` list filter.

**Frontend:** category manager (under `products` or settings), a **parent → sub** cascading picker on the product form, and category grouping/filter on the product list.

**Seeding:** `seed_defaults()` seeds a small starter set per business model (e.g. Telecom: *SIM → Prepaid/Postpaid*, *Devices → Handsets/Accessories*; Trader: *Goods → ...*). Fully user-editable afterwards.

### WS-4 — Quick Actions to the top *(item ③)*

Pure frontend. Move the Quick Actions block from the bottom grid (`dashboard/page.tsx:387-409`) to a **full-width horizontal toolbar directly under the page header** (insert after the header/date row, ~line 225), above the onboarding checklist + KPIs. Restyle from a vertical list to a responsive horizontal wrap of action buttons. Recent Transactions reflows to full width at the bottom. No backend change.

### WS-5 — Update delivery, best-practice *(item ④b)*

**Desktop — real auto-update:**
- Wire `electron-updater` in `desktop/main.js`: on `ready`, `autoUpdater.checkForUpdatesAndNotify()`; handle `update-available` / `update-downloaded` → prompt "Restart to update"; install on quit.
- Create the missing `desktop/electron-builder.yml` with NSIS target + a GitHub `publish` provider (owner/repo) so `electron-builder --publish` uploads artifacts the updater reads.
- Works with **unsigned** builds (signature verification configurable). Without a cert, first install shows a Windows SmartScreen "unknown publisher" prompt — documented.

**Script — update command:** `update.ps1` / `update.sh` / `update.bat` that: `git pull` (or re-download), reinstall deps, **`alembic upgrade head`**, rebuild frontend if needed, relaunch — all against the existing data dir (never deleted).

**In-app version badge:** surface the running version (footer/settings) and, for the script path, a lightweight "newer version available" check against the GitHub releases API.

**Maintainer runbook (documented, not automated):** how to (1) obtain/configure a code-signing cert, (2) `npm run dist` + publish a GitHub Release, (3) bump versions. Lives in `DEPLOYMENT_LOCAL.md`.

### WS-6 — Docs + README *(items ⑤⑥)*

- Update `USER_GUIDE.md`, `WORKFLOW.md`: sample-data button, categories, quick-actions, "what happens to my data when I update" explainer.
- Update `DEPLOYMENT_LOCAL.md`: WS-1 migration model, update command, desktop auto-update + signing/publish runbook.
- Update `CLAUDE.md`: decoupled `bootstrap_schema()`/`seed_defaults()`, `ProductCategory`, demo-seed endpoint, update story.
- **Restructure `README.md`** around current reality: what it is → modern stack → standalone install (script + desktop) → demo/sample data → updating & data safety → development → docs index.

---

## 4. Database & data-safety summary (the item-④ answer, for the docs)

- **Where data lives:** `%USERPROFILE%\.easy-books` (script installer, via `EB_DATA_DIR`) or Electron `userData` (desktop). **Outside** the app folder → reinstalling app files never touches books.
- **On update:** Alembic `upgrade head` runs first (both paths after WS-1) → schema migrated forward in place, rows preserved, new columns/tables added non-destructively. SQLite file is the single source of truth; a backup/restore already exists in Settings for extra safety.
- **Rollbacks:** not auto-managed; the existing Settings backup is the recommended pre-update safeguard (documented).

---

## 5. Testing strategy

- **WS-1:** unit test that `seed_defaults()` runs under `SCHEMA_BOOTSTRAP=alembic`; a migration round-trip test (old DB → `upgrade head` → new column present, rows intact).
- **WS-2:** endpoint test — seed creates 5 tenants idempotently; second call is a no-op; delete tears down; auth-gated.
- **WS-3:** model/endpoint tests — 2-level constraint rejects 3rd level; delete blocked when non-empty; tenant isolation; migration guard.
- **WS-4:** frontend smoke (renders toolbar at top; links resolve).
- **WS-5:** script `update.*` dry-run preserves data dir; electron-updater wiring unit-checked where feasible.
- Full `uv run pytest` stays green (139+ existing tests).

---

## 6. Sequencing

1. **WS-1** (migration safety) → 2. **WS-2** (sample data) → 3. **WS-3** (categories — depends on WS-1) → 4. **WS-4** (quick actions) → 5. **WS-5** (update delivery) → 6. **WS-6** (docs + README).

Each WS is independently testable and commit-able; the implementation plan will stage them as such.

---

## 7. Risks & maintainer-owned items

- **Code-signing cert** (Windows; ideally Apple later) — without it, SmartScreen warns on first desktop install. *Owner action; wiring is cert-ready.*
- **Publishing GitHub Releases** — the auto-updater needs a real release feed. *Owner action; `electron-builder.yml` + runbook provided.*
- **Demo accounts use a known password** — surfaced in UI copy; teardown provided.
- **Shared `db.py` refactor** touches the hosted/SaaS boot path too — covered by the migration round-trip test and existing suite.
