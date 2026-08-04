# Easy-Books — Upgrade Guide

This guide explains how to upgrade Easy-Books to a newer version for each deployment target.
Your accounting data is never deleted during an upgrade; schema changes are applied forward via Alembic migrations.

---

## Before You Upgrade

1. **Know your current version** — visit **Settings → Updates** tab in the app, or call `GET /api/version`.
2. **Automatic notification** — admin and owner users see an **Update Available** popup automatically on every login when a newer commit is available on `main`. Click **Update Now** to start a guided in-app update with an animated progress screen.
3. **Check the release notes** for the target version on the [Releases page](https://github.com/bilalpiaic/Easy-Books/releases).
4. **Read any breaking-change notices** in the release notes before proceeding.

---

## Script Installer (macOS / Linux — `install-and-run.sh`)

```bash
cd ~/easy-books          # wherever you cloned or extracted the repo
./update.sh
```

`update.sh` runs `git pull --ff-only` then re-invokes `install-and-run.sh --rebuild`.

On Debian/Ubuntu, run with bash (not `sh`):

```bash
./update.sh
# or, if the file lost execute permission:
bash update.sh
```

If pull fails because of local installer drift (common after older builds rewrote
`frontend/public/version.json`), the script prints a recovery hint. Safe reset of
the *code* folder only (data in `~/.easy-books` is untouched):

```bash
git checkout -- backend/uv.lock frontend/public/version.json
git fetch origin && git reset --hard origin/main
bash update.sh
```

`install-and-run.sh` will automatically:
- Install or update `uv` and Node.js if needed.
- Rebuild the frontend when the commit hash has changed.
- **Back up your SQLite database** (`~/.easy-books/*.db → ~/.easy-books/backups/`) before applying any pending migration.
- Run `alembic upgrade head` to apply pending schema migrations.
- Restart both servers.

> **Note:** Demo data is never re-seeded on update — only on a brand-new install (no existing users).

---

## Script Installer (Windows — `install-and-run.bat` / `install-and-run.ps1`)

Double-click **`update.bat`** in the Easy-Books folder, or run:

```powershell
powershell -ExecutionPolicy Bypass -File update.ps1
```

The Windows scripts follow the same steps as the macOS/Linux version above (backup → migrate → rebuild → restart).

---

## In-App Update (script installs — all platforms)

Script installs (Windows, macOS, Linux) now support **fully guided in-app updates**:

1. On every login, admin/owner users automatically see an **Update Available** popup if there are newer commits on GitHub.
2. Click **Update Now** → a full-screen animated progress overlay appears with 4 phases (Pull → Compile → Bundle → Start).
3. Once the server restarts (detected automatically by polling `/version.json`), the browser reloads and shows a "What's New" congratulations toast with the changelog.
4. To dismiss without updating: **Later** (session-only dismiss) or **Skip version** (permanently dismiss for this commit).
5. Manual trigger: **Settings → Updates → Update Now**.

You can also update manually at any time:

```bash
# Windows
update.bat

# macOS / Linux
./update.sh
```

## Desktop App (Electron)

1. Open the app — it checks for updates on launch via `electron-updater`.
2. When an update is available you will see a banner in the lower-right corner.
3. Click **Download** → wait for the progress bar → click **Restart & Install**.

Alternatively: **Settings → Updates → Check for Updates** → **Download** → **Restart & Install**.

The Electron updater applies the database migration automatically on the next launch (same `alembic upgrade head` path).

---

## Docker Compose (office/team server)

```bash
cd /path/to/Easy-Books   # wherever you cloned the repo
git pull
docker compose up -d --build
```

`--build` rebuilds only the containers whose source has changed. The `eb_data` volume (SQLite database + uploads) is never modified by the build step — your accounting data is safe.

The backend entrypoint runs `alembic upgrade head` automatically before uvicorn starts, so any schema migrations in the new version are applied on the next restart without any manual steps.

**Verify the upgrade:**
```bash
docker compose logs backend | grep "startup"
# Should show: [startup] Running Alembic migrations... [startup] Starting API server...

curl http://localhost/api/version
# Returns {"version": "x.y.z", "alembic_head": "..."}
```

---

## Manual / Development

```bash
git pull
cd backend && uv sync && uv run alembic upgrade head
cd ../frontend && npm install && npm run build
# Restart servers
```

---

## Rollback Procedure

If a migration fails or the app behaves unexpectedly after upgrading:

### Docker (volume backup restore)

```bash
# Stop the stack
docker compose stop

# Restore a volume backup (.tar.gz created during the backup step)
docker run --rm -v Easy-Books_eb_data:/data -v $(pwd):/backup alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/eb-backup-YYYYMMDD.tar.gz -C /data"

# Roll back the code
git checkout <previous-tag>

# Restart — entrypoint will run alembic downgrade if needed
docker compose up -d --build
```

### SQLite (script / desktop installs)

Backups are written to `~/.easy-books/backups/` (Linux/macOS) or `%USERPROFILE%\.easy-books\backups\` (Windows) before each migration run. Filenames follow the pattern `database_YYYYMMDD_HHMMSS.bak`.

```bash
# Stop the app first, then restore
cp ~/.easy-books/backups/database_20260614_120000.bak ~/.easy-books/database.db
```

Then downgrade the code to the previous version (`git checkout <previous-tag>`) and re-run `install-and-run.sh`.

### PostgreSQL (production)

Restore from your latest DB snapshot/dump before downgrading the code:

```bash
pg_restore -d easy_books latest_backup.dump
```

Then roll back the Alembic migration:

```bash
cd backend && uv run alembic downgrade -1
```

---

## Version Changelog

### v2.9.0 — Module System, Apps Page & Onboarding Splash (2026-06-23)

**Schema changes:** Alembic migration `9a704c7672d5` adds `tenant.module_meta` (JSON column). Applied automatically by all installers.

**What's new:**

| Area | Change |
|------|--------|
| **Module registry** | 6 installable modules: `base` (always locked), `inventory`, `production`, `hrm`, `telecom`, `pra`. Defined in `MODULE_REGISTRY` in `backend/db.py` with label, description, category, icon, deps, tier, and `nav_sections`. |
| **`/api/modules` endpoints** | `GET /api/modules` — list all modules with install status. `POST /api/modules/{id}/install` — dep-aware install (transitive deps auto-installed). `POST /api/modules/{id}/uninstall` — blocked when dependents are installed or module is always-locked. Admin/owner only. |
| **Tenant.module_meta** | New JSON column: `{module_id: {tier, installed_at, expires_at}}` — shape ready for per-module SaaS billing without a future destructive migration. |
| **Apps page** | New page at `/apps` (System → Apps, admin only): module store grid grouped by category, install/uninstall buttons, dependency display, confirm-before-uninstall dialog. |
| **Onboarding splash** | Fresh accounts (only `base` installed, never onboarded) are redirected to `/onboarding` immediately after login. Full-page module selection — pick what you need, click "Get Started". `OnboardingGuard` in the dashboard layout is a safety net for direct URL navigation. Demo tenants are unaffected (already have modules configured). |
| **Sidebar** | `System` section moved to the bottom of the nav (after Payroll). Nav items now use `forModule` (module ID gate) instead of the old `forModel` (business model string). |
| **Legacy modules** | Old `enabled_modules` strings (`"invoicing"`, `"billing"`, etc.) auto-normalized on read — no manual data migration needed for existing installations. |

**Upgrade path:** `git pull && ./update.sh` — the Alembic migration runs automatically. Existing tenants keep their data; `module_meta` defaults to `{}`.

**New localStorage keys:** `eb.onboarded.<email>` — set after onboarding is completed or skipped; prevents the onboarding page from showing again for that account.

---

### v2.8.1 — Version Badge, CI Pipeline & PRA Portal Mode (2026-06-22)

**No schema changes** — this release is entirely frontend/tooling. The schema stays at revision `0026_pra_integration`.

**What's new:**

| Area | Change |
|------|--------|
| **Version badge** | `VersionBadge` in Settings now live-fetches `/api/version` in dev mode (no `NEXT_PUBLIC_APP_VERSION` set). Script and desktop builds inject the env var at build time — no more "dev" badge in production. |
| **Script installers** | `install-and-run.sh` and `install-and-run.ps1` now inject `NEXT_PUBLIC_APP_VERSION` before `next build` so the correct version string appears in Settings on all script installs. |
| **Version sync** | `desktop/package.json` and `backend/pyproject.toml` were at 2.6.0; now synced to 2.8.0. |
| **GitHub Actions** | `.github/workflows/release.yml` improved: validates all 3 version files against the tag; macOS build is conditional on `APPLE_ID` secret (skipped gracefully if absent); `fail-fast` removed; prerelease detection (tags with hyphen auto-flag `--prerelease`); `workflow_dispatch` added to re-run any tag manually. |
| **PRA portal mode** | Admin/owner users on PRA-enabled tenants can toggle between Full Accounting and PRA Portal views via a button at the bottom of the sidebar. Non-admin users always land in Portal view. `usePRAPortal()` hook with `settled` flag prevents redirect loops. `/pra-dashboard` is the portal home page (KPI cards + today's invoice table). `PORTAL_NAV` is a clean 7-item nav (New Invoice / Invoice Queue / Credit Notes / Customers / Products / Submission Logs / Settings). Leaving portal restores the dual Financial \| Operations accounting home. |
| **Dual-home dashboard (v4)** | `/dashboard` toggles **Financial** and **Operations** homes (each with its own customizable layout). Preference `eb.home_dashboard` = `financial` \| `operations` \| `pra` (legacy `accounting` = financial). Ops-heavy tenants default to Operations. Aggregate API `GET /api/dashboard/operations-summary`. Staff Rights resources: `dashboard.financial`, `dashboard.operations`. Settings → Advanced → Home dashboard. |
| **Form widening** | Invoice and Bill forms widened from `max-w-3xl` to `max-w-6xl`. `LineItemsTable` column widths rebalanced: Product 18% / Description 28% / Qty `w-28` with "On hand" hint on one line. |

**New localStorage keys:** `eb.pra_portal_mode` (`"1"` = portal, `"0"` = full accounting); `eb.home_dashboard` (`financial` \| `operations` \| `pra`).

**Upgrade path:** `git pull && ./update.sh` — no migrations; the installer rebuilds the frontend automatically.

---

### v2.8.0 — HRM: Payroll & Attendance (2026-06-21)

**Schema changes:** 3 migrations (`0023_employees`, `0024_payroll`, `0025_attendance`). All scripts/installers run `alembic upgrade head` automatically — existing data is untouched.

**What's new:**
- Payroll module: employees, salary components, payroll runs with GL posting, payslips
- Attendance register: manual time-in/out, monthly grid, bulk entry, biometric import stub
- 13 new frontend pages; Payroll sidebar section

**Upgrade path:** `git pull && ./update.sh` — migrations run automatically.

**New localStorage keys:** none.

---

### v2.7.0 (2026-06-21)

**No database migrations** — this release is entirely frontend. The schema stays at revision `0022_promo_rules`.

| Change | Detail |
|--------|--------|
| **Dark Mode + Themes** | 3 display modes (Light / Dark / System) and 5 color themes (Gold / Emerald / Sapphire / Rose / Slate). Theme icon in the header; color swatches in Settings → Appearance. User preference stored in `localStorage` — no migration, no data loss. |
| **Multi-language support** | English, Urdu (اردو, RTL), and Chinese (中文) via `react-i18next`. Globe icon in the header. Preference stored in `localStorage` and synced to `/api/settings` (`app_language` setting key). |
| **Mobile responsiveness overhaul** | 61 frontend files updated with responsive Tailwind breakpoints. Sidebar width reduced from 220 px to 196 px. All pages now render correctly on phone-sized screens. |
| **442+ backend tests** | Test count grew from 404 to 442+ passing; no schema changes. |

**Upgrade path:** standard `./update.sh` / `update.bat` — `git pull` + rebuild frontend. No `alembic upgrade head` step is required for this release (schema unchanged), but the installer runs it anyway as a safety check.

**User preferences** (theme, language) are stored in `localStorage` and survive updates automatically — no data migration is needed and no existing accounting data is affected.

---

## How to Trigger a Release (contributors)

1. **Sync all three version files** — `frontend/package.json`, `desktop/package.json`, and `backend/pyproject.toml` must all contain the same version string that matches the tag you are about to push (e.g. `2.9.0`).

2. **Tag and push:**
   ```bash
   git tag v2.9.0
   git push origin v2.9.0
   ```
   The GitHub Actions workflow (`.github/workflows/release.yml`) fires automatically on any `v*` tag push.

3. **Workflow stages:**
   - **Stage 1 — validate:** Reads all 3 version files and fails if any of them does not match the tag. This prevents mismatched binaries.
   - **Stage 2a — build-windows:** Always runs; produces the `.exe` installer and `latest.yml` manifest.
   - **Stage 2b — build-macos:** Runs only when the `APPLE_ID` repository secret is set. Produces the `.dmg` and `latest-mac.yml`. Skipped gracefully when the secret is absent — the Windows-only release still publishes.
   - **Stage 3 — publish:** Creates the GitHub Release with all artifacts. Tags containing a hyphen (e.g. `v2.9.0-beta.1`) are automatically flagged as pre-releases.

4. **Secrets needed:**
   - `GITHUB_TOKEN` — provided automatically by Actions; needed to create the release.
   - `CSC_LINK` / `CSC_KEY_PASSWORD` — Windows code-signing certificate (optional; skip for unsigned builds).
   - `APPLE_ID` / `APPLE_ID_PASSWORD` / `APPLE_TEAM_ID` — macOS notarization (optional; skip to produce Windows-only releases).

5. **Re-running a tag manually:** Go to **Actions → Release** on GitHub and click **Run workflow**, then enter the tag name. Useful for rebuilding an existing release after a build failure without re-tagging.

---

## Verifying a Successful Upgrade

After upgrading, confirm:

1. `GET /api/version` returns the expected `version` and `alembic_head` values.
2. The app loads at `http://localhost:3000` without errors.
3. Your existing journals, invoices, and reports are still accessible.

---

## Adding Schema Changes (for contributors)

1. Edit `backend/models.py`.
2. Generate the migration: `cd backend && uv run alembic revision --autogenerate -m "describe_change"`.
3. Review the generated file in `backend/alembic/versions/`.
4. Apply it locally: `uv run alembic upgrade head`.
5. **SQLite caveat:** Remove any `ADD CONSTRAINT` / FK lines from the generated migration; use `op.batch_alter_table()` for all ALTER TABLE operations; add `bind.dialect.has_table()` guards for new tables (see migrations 0016/0017/0020 for patterns).

---

*For support, open an issue at https://github.com/bilalpiaic/Easy-Books/issues*

---

*Last reviewed: 2026-06-23 · Branch: `main`*
