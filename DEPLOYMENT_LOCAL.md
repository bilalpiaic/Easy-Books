# Easy-Books — Local / Commercial Deployment Options

> Companion to [`DEPLOYMENT.md`](./DEPLOYMENT.md) (cloud/Vercel). This document covers shipping
> Easy-Books as a product an SME runs **on their own machine or office server** — data on-premise,
> works offline, no per-seat cloud subscription. (The **Manager.io / QuickBooks Desktop** model.)
>
> **Status:** strategy draft · **Last updated:** 2026-05-29

---

## Goal

Distribute Easy-Books to end users who run it locally:
- **Data sovereignty** — books never leave the user's machine.
- **Offline-capable** — no internet dependency for daily use.
- **One-time / tiered license** instead of (or alongside) cloud SaaS.

## What the current stack gives you (and the friction)

| Helps | Friction |
|---|---|
| **SQLite already supported** (`backend/database.db`) — ideal embedded, zero-config local DB | Two runtimes to ship: **Python** (FastAPI) **+ Node** (Next.js) |
| Clean frontend↔backend split (REST over `NEXT_PUBLIC_API_URL`); **no Next middleware, no Next route handlers** | 13 client-rendered `[id]` routes ⇒ **no clean static export**; use `output: 'standalone'` |
| Alembic migrations → safe forward-migration of the user's DB on upgrade | `JWT_SECRET_KEY` must be generated per-install (prod refuses the insecure default) |
| Multi-tenant model collapses cleanly to "one company per install" | Desktop packaging + OS code-signing/notarization is real effort |
| Existing CSV export + per-tenant branding | `next.config` `headers()` only applies under the Node server, not a static export |

---

## Packaging paths

### Path A — Desktop app: native shell + bundled servers ⭐ (recommended for end users)
A thin native shell opens `http://127.0.0.1:<port>` and supervises two bundled sidecars:
FastAPI (PyInstaller one-file) + Next.js (`output: 'standalone'` with a bundled Node).

| | Electron | Tauri |
|---|---|---|
| Shell size | ~100 MB (bundles Chromium) | ~10 MB (OS webview) |
| Maturity for "local server" apps | Very high | High, lighter, Rust glue |
| Python sidecar | well-trodden | sidecar API |

- **Pros:** real installable app, single icon, built-in auto-update, tray/launcher.
- **Cons:** bundling Python **and** Node in one installer is the heavy lift; sign both OSes.
- **Effort:** Medium–High. **Best for non-technical single-business desktop users.**

### Path B — Self-contained local server + browser (lightest engineering)
PyInstaller the FastAPI backend; run Next.js `standalone` alongside (or refactor the 13 `[id]`
routes to query-params and serve a **true static export** from FastAPI `StaticFiles`, dropping Node
entirely). A small launcher starts it and opens the default browser.

- **Pros:** fewest moving parts (especially the no-Node variant); tiny; trivial updates.
- **Cons:** "open your browser to localhost" is less polished; static-export route refactor is real work.
- **Effort:** Low–Medium. **Best for a v1/pilot or technically comfortable users.**

#### Zero-to-running in one line (clones the repo for you)
For a brand-new PC where the user hasn't even cloned the repo, `bootstrap` clones it (to
`~/Easy-Books` / `%USERPROFILE%\Easy-Books`, overridable) and then runs the installer:

- **macOS / Linux** (Terminal):
  ```bash
  curl -fsSL https://raw.githubusercontent.com/bilalpiaic/Easy-Books/main/bootstrap.sh | bash
  ```
  Custom location: `curl -fsSL …/bootstrap.sh | bash -s -- /path/to/folder` (or set `EB_INSTALL_DIR`).
- **Windows** — double-click **`bootstrap.bat`** (download just that one file), or in PowerShell:
  ```powershell
  irm https://raw.githubusercontent.com/bilalpiaic/Easy-Books/main/bootstrap.ps1 | iex
  ```

`bootstrap` uses **git clone** when git is present, and falls back to downloading the source ZIP when
it isn't — then hands off to the one-click installer below. Re-running updates the copy (`git pull`).

#### One-click install & run (recommended — auto-installs prerequisites)
The repo ships a bootstrap that **installs everything it needs and launches the app** — the user does
not need Python or Node pre-installed (one-time internet connection required to fetch them):

- **Windows:** double-click **`install-and-run.bat`**.
- **macOS / Linux:** run **`./install-and-run.sh`** (first time: `chmod +x install-and-run.sh`).

What it does automatically: installs **uv** (which also provisions Python 3.12), uses your system
**Node.js** or downloads a **local portable Node** into `./.node` (no system install, no admin),
installs backend deps, builds the frontend, then opens **http://127.0.0.1:3000**. Re-run any time;
pass `--rebuild` (sh) / `-Rebuild` (ps1) to force a fresh build. First run takes a few minutes
(downloads + build); later runs start in seconds.

Data lives in `EB_DATA_DIR` (default `~/.easy-books` / `%USERPROFILE%\.easy-books`). On first install the 5 demo companies are **auto-loaded** (takes ~20–30 s; guarded — fires only on a brand-new empty DB; updating an existing install is migrate-only and no demo data is added). Log in immediately with `demo1234`. Set `SEED_DEMO=false` before running for a clean install with no demo data. The first signup creates your own owner account.

> **Note:** the `.sh` is tested on Linux/macOS. The Windows `.bat`/`.ps1` mirror the same logic and
> use PowerShell-5.1-compatible constructs; validate on a real Windows box before distribution. The
> fully prerequisite-free **double-click `.exe`** (no internet fetch, bundled runtimes) is **Phase 2**
> (Tauri/Electron + PyInstaller).

#### Lower-level launcher (`run-local.sh`, assumes deps already installed)
Phase 0 ships a launcher that runs both servers bound to `127.0.0.1`:
```bash
# One-time build
cd backend  && uv sync
cd frontend && npm install && npx next build
# Next 'standalone' doesn't copy static assets — do it once after each build:
cp -r frontend/.next/static  frontend/.next/standalone/.next/static
cp -r frontend/public        frontend/.next/standalone/public

# Launch (data dir defaults to ~/.easy-books, demo seeding off)
./run-local.sh
# Override location/behaviour:  EB_DATA_DIR=/srv/easybooks SEED_DEMO=false ./run-local.sh
```
- **`EB_DATA_DIR`** — where the SQLite DB, uploads, and per-install secret (`.secret.key`) live.
- **`SEED_DEMO=false`** — skip auto-loading demo data; fresh install boots empty and the first signup becomes the owner. (The one-click installers default to `SEED_DEMO=true`; `run-local.sh` defaults to `false`.)
- Data is backed up/restored from **Settings → Backup & Restore** (zip of DB + uploads).

### Path C — On-prem Docker Compose ("Server edition")
Ship `docker-compose.yml` (FastAPI + Next standalone + Postgres) for a small office to run on one
machine; staff connect over the LAN. Close to ready — prod already targets Postgres.

- **Pros:** easiest to build; true multi-user over LAN; keeps multi-tenant strengths.
- **Cons:** requires Docker literacy; not double-click friendly.
- **Effort:** Low. **Best as a paid "Server/Pro" tier for multi-seat offices.**

### Path D — Bring-your-own-server install script
A guided `curl | bash` (or script) that provisions the same app on a customer VPS/NAS. Complements
the others rather than replacing them. **Effort:** Low.

---

## Cross-cutting concerns (any path)

- **Data location & backup:** SQLite file + uploads in the OS app-data dir
  (`%APPDATA%`, `~/Library/Application Support`, `~/.local/share`). Add in-app **Backup / Restore**
  (zip the `.db` + uploads); CSV export already exists.
- **First-run setup:** auto-generate & persist `JWT_SECRET_KEY`; run `alembic upgrade head`; run `scripts.autoseed_demo` (loads 5 demo companies on a brand-new empty DB when `SEED_DEMO=true`, the default for both script installers and the desktop app; guard skips if any user exists, so updating an existing install is migrate-only — no demo data added; set `SEED_DEMO=false` for a clean install); create your own owner via the signup wizard.
- **Licensing (commercial lever):** offline **signed license file** — Ed25519 signature over
  `{customer, edition, seats, expiry}` verified against an embedded public key. Trial = time-limited
  license auto-issued on install. Editions map to the existing `enabled_modules`
  (Simple / Services / Trader / Manufacturing / Telecom). Optional online activation for stricter enforcement.
- **Updates:** Electron/Tauri auto-updater or signed installer downloads; **always run Alembic on launch**.
- **Security on localhost:** bind to `127.0.0.1`; keep JWT + bcrypt; CSRF may relax for same-origin
  localhost; if a static export is ever used, move `headers()` into FastAPI responses.
- **Whitelabel:** per-tenant company name/logo already exists; expose at install for resellers.

---

## Recommended roadmap

| Phase | Outcome |
|---|---|
| **Phase 0 — make it packageable** | `output: 'standalone'`; per-install secret + DB in app-data; demo-seeding toggle (fresh install boots empty); in-app Backup/Restore; localhost launcher. |
| **Phase 1 — Server edition (Path C)** | Docker Compose + Postgres + license-file check. Fastest to revenue for offices. |
| **Phase 2 — Desktop edition (Path A)** | Bundle FastAPI (PyInstaller) + Next standalone in Tauri/Electron; Windows `.msi` first, then notarized Mac `.dmg`. |
| **Phase 3 — polish** | Auto-update; trial→paid activation; opt-in telemetry. |

## Open decisions
1. **Target user** — non-technical single-business desktop (Path A) vs small office server (Path C)?
2. **OS priority** — Windows-first, or Mac/Linux too?
3. **Node-or-no-Node** — refactor `[id]` routes to query-params for a lighter static bundle, or keep
   path routes and ship Node (`standalone`)?
4. **Licensing strictness** — offline honor-system key vs enforced online activation?

> The architecture is already ~80% local-ready: the frontend never does server-side data fetching and
> SQLite is a first-class backend. The highest-leverage early decision is **Node-or-no-Node**.

---

## Phase 2 — Bundled Desktop Installer (build & release)

Phase 2 packages Path A as a **double-click installer** (Windows `.exe`/NSIS, macOS `.dmg`)
that bundles every runtime — the end user installs like any app, with **no Python, Node, git,
internet-to-fetch-source, or terminal**. An **Electron** shell supervises two bundled sidecars:
the FastAPI backend as a **PyInstaller** one-dir binary and the **Next.js `standalone`** server
run by a **bundled Node**, both on `127.0.0.1`. On launch the shell sets `EB_DATA_DIR` to the
per-user OS app-data dir and runs **`alembic upgrade head`** so user data migrates safely across
versions (unlike dev's `create_all`, this delivers new *columns* to upgraded installs).

### What ships in the repo (OS-agnostic, Tasks 1–4 — done)
| File | Role |
|---|---|
| `backend/run_packaged.py` | Packaged entrypoint: `alembic upgrade head` → serve uvicorn on 127.0.0.1:8000 |
| `backend/easybooks-backend.spec` | PyInstaller one-dir spec (ships `alembic.ini` + `alembic/` + `templates/` as data) |
| `desktop/main.js` | Electron main: spawn + health-wait + supervise sidecars; sets `EB_DATA_DIR`; defaults `SEED_DEMO=true` so the guarded auto-seed runs on first install (set `SEED_DEMO=false` for a clean install); shows a "Starting up… first-time setup may take ~30 seconds" splash during the one-time seed |
| `desktop/preload.js` | Hardened preload (contextIsolation, no node in renderer) |
| `desktop/package.json` | Electron + electron-builder + electron-updater; `dist` → `electron-builder.yml` |
| `desktop/scripts/prepare-resources.sh` / `.ps1` | Build backend + Next standalone + fetch portable Node → stage `desktop/resources/{backend,frontend,node}` |

Verified on Linux: the PyInstaller bundle boots, runs the full migration chain from an empty DB,
and serves `GET /docs → 200`. Build artifacts (`backend/build`, `backend/dist`, `desktop/resources`,
`desktop/dist`, `desktop/node_modules`) are gitignored.

### Building the installers (Tasks 5–9 — on the target OS)
electron-builder does **not** cross-compile signed installers, so each installer is built on its
own OS. Prerequisites per build host: Node + Python/`uv`; macOS also needs Xcode Command-Line Tools.

```bash
# Windows build host → dist/Easy-Books Setup <ver>.exe
./desktop/scripts/prepare-resources.ps1 ; cd desktop && npm install && npm run dist

# macOS build host → dist/Easy-Books-<ver>.dmg
./desktop/scripts/prepare-resources.sh  ; cd desktop && npm install && npm run dist
```

`npm run dist` reads `desktop/electron-builder.yml` (Task 5): NSIS for Windows, dmg for macOS,
`extraResources` copying `resources/{backend,frontend,node}`, and a GitHub `publish` feed.

### Code signing & notarization (certs are external — never commit them)
Supply credentials via environment variables on the build host only:
- **Windows:** `CSC_LINK` (path or base64 of the `.pfx`) + `CSC_KEY_PASSWORD` → electron-builder signs the NSIS installer.
- **macOS:** `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` + `APPLE_TEAM_ID`, with `notarize: true`, plus a Developer ID Application cert in the keychain → electron-builder notarizes and staples during `dist`.

### Release & auto-update
Publish the installers to GitHub Releases; electron-builder uploads the `latest.yml` /
`latest-mac.yml` feeds that `electron-updater` (`autoUpdater.checkForUpdatesAndNotify()`) reads on
next launch. **Upgrade guarantee:** installing a newer version over an older one re-runs
`alembic upgrade head` on launch, preserving the user's `EB_DATA_DIR` data.

> **Maintainer note (prerequisites for a clean release):**
> - A published GitHub Release with the installer assets is required before `electron-updater` can serve updates.
> - A code-signing certificate is optional but recommended: without one, Windows SmartScreen will show an "Unknown publisher" warning on first install. Supply the cert via `CSC_LINK` / `CSC_KEY_PASSWORD` on the build host only — **never commit certs or credentials to the repo.**

---

## Updating Easy-Books & Your Data

### Where your data lives

User data — the SQLite database, uploaded files, and the per-install secret key — is stored **outside** the app folder in a dedicated data directory:

| Platform | Default location |
|---|---|
| macOS / Linux | `~/.easy-books` (or `$EB_DATA_DIR`) |
| Windows | `%USERPROFILE%\.easy-books` (or `%EB_DATA_DIR%`) |
| Desktop (Electron) | OS `userData` dir set by Electron at launch |

Reinstalling or updating app files **never touches this directory**. Your accounts, invoices, settings, and uploaded documents are safe across updates.

### How updates migrate your database

Both install paths run `alembic upgrade head` on every launch:

- **Script installers** (`install-and-run.sh` / `install-and-run.bat` / `install-and-run.ps1`) — run Alembic before starting the servers. New columns and tables are added to your existing database; no data is wiped.
- **Desktop app** (`backend/run_packaged.py`) — runs Alembic before uvicorn starts, same guarantee.

This means pulling a newer version of Easy-Books and re-running the installer migrates your database **in place** — existing rows are preserved and new schema features are available immediately.

### Updating a script install

```bash
# macOS / Linux
./update.sh

# Windows — choose one:
update.bat                  # double-click in Explorer
.\update.ps1               # PowerShell
```

`update.sh` / `update.bat` / `update.ps1` each: `git pull` the latest code, then call `install-and-run.*` (which runs Alembic, relaunches, and **auto-rebuilds the frontend whenever the code has changed** since the last build, tracked via `frontend/.next/.built-commit` vs `git rev-parse HEAD`). A plain re-run after any code change therefore always serves the latest UI. The `EB_DATA_DIR` data directory is never touched.

### Updating the desktop app

The desktop app uses `electron-updater` and **checks for a new release on every launch**. When an update is available you will be prompted to restart and apply it. The update re-runs `alembic upgrade head` on the next launch.

### Back up first

Before any major update, go to **Settings → Backup & Restore** and download a backup zip (database + uploads). This is the recommended safeguard in case you ever need to roll back.
