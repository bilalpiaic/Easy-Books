# Phase 2 — Bundled Desktop Installer (Windows + macOS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax.
>
> ⚠️ **Build environment:** This plan CANNOT be executed in the current Linux/WSL container. Producing and testing the installers requires a **Windows build machine** (for the `.exe`/NSIS) and a **macOS build machine** (for the notarized `.dmg`). Electron-builder does not cross-compile signed installers. Tasks 1–4 are OS-agnostic (backend/Electron logic, testable anywhere); Tasks 5–9 must run on the target OS.

**Goal:** Ship Easy-Books as a signed, double-click desktop installer for Windows and macOS that bundles all runtimes — the user installs like any app, with no Python, Node, git, internet-to-fetch-source, or terminal.

**Architecture:** An **Electron** shell supervises two bundled sidecars: the FastAPI backend as a **PyInstaller** one-dir binary, and the **Next.js `standalone`** server run by a **bundled Node**. On launch Electron sets `EB_DATA_DIR` to the per-user app-data dir, starts both sidecars on `127.0.0.1`, waits for health, and loads the UI in a `BrowserWindow`. `electron-builder` produces an NSIS `.exe` (Windows) and a notarized `.dmg` (macOS) with auto-update. Packaged installs run **Alembic migrations on launch** so user data upgrades safely across versions.

**Tech Stack:** Electron + electron-builder + electron-updater · PyInstaller · Next.js standalone · FastAPI/uvicorn · Alembic · SQLite.

---

## Reuse from Phase 0/1 (do not rebuild)
- `backend/local_config.py` — `EB_DATA_DIR`, `sqlite_path()`, `uploads_dir()`, `resolve_secret()`.
- `SEED_DEMO=false` empty first-run; Settings → Backup/Restore; persisted per-install secret.
- `frontend` `output: 'standalone'` build; the static-asset copy step from `install-and-run.sh`.

## FILE STRUCTURE
| File | Responsibility |
|------|---------------|
| `backend/run_packaged.py` (new) | Packaged entrypoint: run `alembic upgrade head` then serve uvicorn on 127.0.0.1:8000 |
| `backend/alembic/env.py` (modify) | When `DATABASE_URL` unset, target `local_config.sqlite_path()` (align with the app) |
| `backend/easybooks-backend.spec` (new) | PyInstaller one-dir spec (datas: alembic.ini, alembic/, templates/; hidden imports) |
| `desktop/package.json` (new) | Electron app manifest + electron-builder/updater deps + scripts |
| `desktop/main.js` (new) | Electron main: spawn + supervise sidecars, health-wait, window, lifecycle, auto-update |
| `desktop/preload.js` (new) | Minimal hardened preload (no node integration in renderer) |
| `desktop/electron-builder.yml` (new) | extraResources wiring + win NSIS + mac dmg/notarize + publish feed |
| `desktop/build/icon.ico`, `icon.icns` (new) | App icons |
| `desktop/scripts/prepare-resources.sh` / `.ps1` (new) | Build backend + frontend + fetch portable Node → stage into `desktop/resources/` |
| `backend/tests/test_packaged_entrypoint.py` (new) | Migrations bring an empty DB to head |
| `DEPLOYMENT_LOCAL.md` (modify) | Phase 2 build + release instructions |

---

## Task 1: Backend packaged entrypoint + Alembic path alignment

**Files:** Modify `backend/alembic/env.py`; Create `backend/run_packaged.py`, `backend/tests/test_packaged_entrypoint.py`

- [ ] **Step 1: Write the failing test**
```python
# backend/tests/test_packaged_entrypoint.py
import importlib
from sqlalchemy import create_engine, inspect

def test_migrations_bring_empty_db_to_head(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import local_config
    importlib.reload(local_config)
    import run_packaged
    importlib.reload(run_packaged)
    run_packaged.migrate()  # alembic upgrade head against tmp sqlite
    eng = create_engine(f"sqlite:///{local_config.sqlite_path()}")
    tables = set(inspect(eng).get_table_names())
    # Core + Sprint 7-14 tables exist purely from the migration chain
    assert {"account", "invoice", "creditnote", "debitnote", "customeradvance"} <= tables
```
- [ ] **Step 2: Run — expect FAIL** (`run_packaged` missing)
Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_packaged_entrypoint.py -v`
- [ ] **Step 3: Align Alembic to the app's SQLite path** — in `backend/alembic/env.py` replace the default URL line `db_url = os.environ.get("DATABASE_URL") or "sqlite:///database.db"` with:
```python
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    import sys, os as _os
    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from local_config import sqlite_path
    db_url = f"sqlite:///{sqlite_path()}"
```
- [ ] **Step 4: Create `backend/run_packaged.py`**
```python
"""Packaged entrypoint: migrate the user's DB forward, then serve the API.

Used by the desktop build (PyInstaller). Unlike dev (create_all), packaged
installs run Alembic so new COLUMNS on existing tables reach upgraded users.
"""
import os
import sys
from pathlib import Path


def _bundle_dir() -> Path:
    # PyInstaller sets sys._MEIPASS to the unpacked bundle; else the source dir.
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def migrate() -> None:
    from alembic.config import Config
    from alembic import command
    from local_config import sqlite_path
    bundle = _bundle_dir()
    cfg = Config(str(bundle / "alembic.ini"))
    cfg.set_main_option("script_location", str(bundle / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{sqlite_path()}")
    command.upgrade(cfg, "head")


def main() -> None:
    os.environ.setdefault("APP_ENV", "local")
    os.environ.setdefault("SEED_DEMO", "false")
    os.environ.setdefault("SCHEMA_BOOTSTRAP", "alembic")  # lifespan skips create_all
    migrate()
    import uvicorn
    from main import app
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
```
- [ ] **Step 5: Run — expect PASS**
Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_packaged_entrypoint.py -v`
- [ ] **Step 6: Commit**
```bash
git add backend/run_packaged.py backend/alembic/env.py backend/tests/test_packaged_entrypoint.py
git commit -m "feat(desktop): packaged entrypoint runs alembic upgrade then serves; env.py uses EB_DATA_DIR"
```

## Task 2: PyInstaller one-dir backend binary

**Files:** Create `backend/easybooks-backend.spec`; Modify `backend/pyproject.toml` (dev dep)

- [ ] **Step 1: Add PyInstaller** — `cd backend && uv add --dev pyinstaller`
- [ ] **Step 2: Create `backend/easybooks-backend.spec`**
```python
# PyInstaller one-dir spec for the Easy-Books backend.
# Build:  uv run pyinstaller easybooks-backend.spec
from PyInstaller.utils.hooks import collect_submodules
datas = [("alembic.ini", "."), ("alembic", "alembic"), ("templates", "templates")]
hiddenimports = (
    collect_submodules("uvicorn") + collect_submodules("sqlmodel")
    + collect_submodules("passlib") + collect_submodules("jose")
    + ["models", "models_telecom", "main", "run_packaged",
       "email.mime.multipart", "email.mime.text", "anyio"]
)
a = Analysis(["run_packaged.py"], pathex=["."], datas=datas,
             hiddenimports=hiddenimports, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="easybooks-backend",
          console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="easybooks-backend")
```
- [ ] **Step 3: Build + smoke-test** (run on each target OS)
```bash
cd backend && uv run pyinstaller easybooks-backend.spec
EB_DATA_DIR=/tmp/eb-pkg ./dist/easybooks-backend/easybooks-backend &   # Windows: dist\easybooks-backend\easybooks-backend.exe
sleep 4 && curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs   # expect 200
```
Expected: `200`, and `/tmp/eb-pkg/database.db` created. Stop the process after.
- [ ] **Step 4: Commit**
```bash
git add backend/easybooks-backend.spec backend/pyproject.toml backend/uv.lock
git commit -m "feat(desktop): PyInstaller spec for the backend binary"
```
> If imports are missing at runtime, add them to `hiddenimports` (common with FastAPI/uvicorn). `dist/` and `build/` are gitignored.

## Task 3: Stage all resources for packaging

**Files:** Create `desktop/scripts/prepare-resources.sh` and `.ps1`; Modify `.gitignore`

- [ ] **Step 1: Create `desktop/scripts/prepare-resources.sh`** (macOS/Linux)
```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RES="$ROOT/desktop/resources"; NODE_VERSION="20.18.1"
rm -rf "$RES"; mkdir -p "$RES"
# Backend binary
( cd "$ROOT/backend" && uv run pyinstaller easybooks-backend.spec )
cp -r "$ROOT/backend/dist/easybooks-backend" "$RES/backend"
# Frontend standalone
( cd "$ROOT/frontend" && npm install && npx next build )
cp -r "$ROOT/frontend/.next/static"  "$ROOT/frontend/.next/standalone/.next/static"
cp -r "$ROOT/frontend/public"        "$ROOT/frontend/.next/standalone/public"
mkdir -p "$RES/frontend"; cp -r "$ROOT/frontend/.next/standalone/." "$RES/frontend/"
# Portable Node
os="$(uname -s|tr '[:upper:]' '[:lower:]')"; [ "$os" = darwin ] && plat=darwin || plat=linux
arch="$(uname -m)"; case "$arch" in x86_64|amd64) arch=x64;; arm64|aarch64) arch=arm64;; esac
curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-$plat-$arch.tar.gz" \
  | tar -xz -C "$RES" && mv "$RES/node-v$NODE_VERSION-$plat-$arch" "$RES/node"
echo "Staged → $RES"
```
- [ ] **Step 2: Create `desktop/scripts/prepare-resources.ps1`** — same steps using `Invoke-WebRequest`/`Expand-Archive` and the `node-v$NodeVersion-win-x64.zip`, copying `easybooks-backend` (with `.exe`) and `node.exe` into `desktop\resources\{backend,frontend,node}`.
- [ ] **Step 3: gitignore** — append to `.gitignore`: `desktop/resources/`, `desktop/dist/`, `desktop/node_modules/`, `backend/build/`, `backend/dist/`.
- [ ] **Step 4: Verify + commit**
```bash
chmod +x desktop/scripts/prepare-resources.sh && ./desktop/scripts/prepare-resources.sh
ls desktop/resources/backend desktop/resources/frontend/server.js desktop/resources/node
git add desktop/scripts .gitignore && git commit -m "feat(desktop): resource staging scripts"
```

## Task 4: Electron shell (spawn + supervise sidecars)

**Files:** Create `desktop/package.json`, `desktop/main.js`, `desktop/preload.js`

- [ ] **Step 1: `desktop/package.json`**
```json
{
  "name": "easy-books-desktop",
  "version": "2.0.0",
  "description": "Easy-Books desktop",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "dist": "electron-builder --config electron-builder.yml"
  },
  "devDependencies": {
    "electron": "^33.0.0",
    "electron-builder": "^25.0.0"
  },
  "dependencies": {
    "electron-updater": "^6.3.0"
  }
}
```
- [ ] **Step 2: `desktop/main.js`**
```js
const { app, BrowserWindow, dialog } = require("electron")
const { spawn } = require("child_process")
const path = require("path")
const http = require("http")

const BACKEND_PORT = 8000, FRONTEND_PORT = 3000
let backend, frontend, win

const resDir = () => app.isPackaged
  ? process.resourcesPath
  : path.join(__dirname, "resources")
const exe = (p) => process.platform === "win32" ? `${p}.exe` : p

function startSidecars() {
  const env = {
    ...process.env,
    EB_DATA_DIR: app.getPath("userData"),
    SEED_DEMO: "false",
    APP_ENV: "local",
    PORT: String(BACKEND_PORT),
  }
  backend = spawn(exe(path.join(resDir(), "backend", "easybooks-backend")), [], { env })
  frontend = spawn(
    exe(path.join(resDir(), "node", process.platform === "win32" ? "node" : "bin/node")),
    [path.join(resDir(), "frontend", "server.js")],
    { env: { ...env, PORT: String(FRONTEND_PORT), HOSTNAME: "127.0.0.1" } }
  )
}

function waitForServer(port, tries = 60) {
  return new Promise((resolve, reject) => {
    const tick = () => {
      http.get({ host: "127.0.0.1", port, timeout: 1000 }, () => resolve())
        .on("error", () => (--tries <= 0 ? reject(new Error("timeout")) : setTimeout(tick, 500)))
    }
    tick()
  })
}

async function createWindow() {
  win = new BrowserWindow({
    width: 1280, height: 840, show: false,
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false },
  })
  win.once("ready-to-show", () => win.show())
  try {
    await waitForServer(FRONTEND_PORT)
    await win.loadURL(`http://127.0.0.1:${FRONTEND_PORT}`)
  } catch (e) {
    dialog.showErrorBox("Easy-Books failed to start", String(e))
    app.quit()
  }
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) { app.quit() } else {
  app.on("second-instance", () => { if (win) { win.show(); win.focus() } })
  app.whenReady().then(() => { startSidecars(); createWindow() })
}

function killSidecars() {
  for (const p of [backend, frontend]) { try { p && p.kill() } catch (_) {} }
}
app.on("window-all-closed", () => { killSidecars(); app.quit() })
app.on("before-quit", killSidecars)
process.on("exit", killSidecars)
```
- [ ] **Step 3: `desktop/preload.js`**
```js
// Hardened: no node access in the renderer; the UI is the existing web app.
window.addEventListener("DOMContentLoaded", () => {})
```
- [ ] **Step 4: Verify in dev** (any OS, after Task 3 staged `desktop/resources/`)
```bash
cd desktop && npm install && npm start
```
Expected: a window opens showing the Easy-Books login after the servers come up.
- [ ] **Step 5: Commit**
```bash
git add desktop/package.json desktop/main.js desktop/preload.js
git commit -m "feat(desktop): Electron shell supervising backend + frontend sidecars"
```

## Task 5: electron-builder config (Windows NSIS + macOS dmg)

**Files:** Create `desktop/electron-builder.yml`, `desktop/build/icon.ico`, `desktop/build/icon.icns`

- [ ] **Step 1: `desktop/electron-builder.yml`**
```yaml
appId: app.easybooks.desktop
productName: Easy-Books
directories: { output: dist, buildResources: build }
files: ["main.js", "preload.js", "package.json"]
extraResources:
  - { from: resources/backend,  to: backend }
  - { from: resources/frontend, to: frontend }
  - { from: resources/node,     to: node }
win:
  target: [{ target: nsis, arch: [x64] }]
  icon: build/icon.ico
nsis: { oneClick: false, perMachine: false, allowToChangeInstallationDirectory: true }
mac:
  target: [{ target: dmg, arch: [x64, arm64] }]
  icon: build/icon.icns
  category: public.app-category.finance
  hardenedRuntime: true
  entitlements: build/entitlements.mac.plist
  notarize: true
publish: [{ provider: github, owner: bilalpiaic, repo: Easy-Books }]
```
- [ ] **Step 2: Add icons** — place `build/icon.ico` (256px) and `build/icon.icns`; create `build/entitlements.mac.plist` with `com.apple.security.cs.allow-jit` + `allow-unsigned-executable-memory` (Electron + spawned binaries need these).
- [ ] **Step 3: Build the installer** (on the matching OS)
```bash
# Windows machine:
./desktop/scripts/prepare-resources.ps1 ; cd desktop && npm install && npm run dist   # → dist/Easy-Books Setup 2.0.0.exe
# macOS machine:
./desktop/scripts/prepare-resources.sh  ; cd desktop && npm install && npm run dist    # → dist/Easy-Books-2.0.0.dmg
```
- [ ] **Step 4: Verify** — install on a clean VM; launch; confirm empty first-run → signup → create invoice → Backup/Restore works; data under the OS app-data dir.
- [ ] **Step 5: Commit**
```bash
git add desktop/electron-builder.yml desktop/build
git commit -m "feat(desktop): electron-builder config + icons (Windows NSIS, macOS dmg)"
```

## Task 6: Code signing + notarization (maintainer-supplied certs)
- [ ] **Windows:** set env before `npm run dist`: `CSC_LINK` (path/base64 of the `.pfx`), `CSC_KEY_PASSWORD`. electron-builder signs the NSIS installer automatically.
- [ ] **macOS:** set `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`; with `notarize: true` electron-builder notarizes + staples during `dist`. Requires an Apple Developer ID Application cert in the keychain.
- [ ] **Document** these env vars in `DEPLOYMENT_LOCAL.md` (do NOT commit any cert/secret). Verify the installed app shows a valid publisher (Windows) and opens without Gatekeeper warnings (macOS).

## Task 7: Auto-update
- [ ] In `desktop/main.js`, after `createWindow()`: `const { autoUpdater } = require("electron-updater"); autoUpdater.checkForUpdatesAndNotify()`.
- [ ] Releases: publish installers to GitHub Releases (the `publish` block). electron-builder uploads `latest.yml`/`latest-mac.yml` that the updater reads.
- [ ] Verify: install v2.0.0, publish a v2.0.1 release, relaunch → update downloads and applies on next start.
- [ ] Commit the main.js change: `git commit -am "feat(desktop): auto-update via electron-updater + GitHub Releases"`.

## Task 8: First-run, migration & backup validation (smoke checklist)
- [ ] Fresh install on a clean machine → boots **empty** (no demo tenants); first signup becomes owner (`SEED_DEMO=false`).
- [ ] `EB_DATA_DIR` = OS app-data (`app.getPath("userData")`); `database.db`, `uploads/`, `.secret.key` (0600) created there.
- [ ] Settings → Backup → Download produces a zip; Restore re-loads it; relaunch shows restored data.
- [ ] **Upgrade test:** install v2.0.0, add data, install v2.0.1 (with a new migration) → launch → `alembic upgrade head` runs, data preserved, new columns present.

## Task 9: Build orchestration + docs
- [ ] Create `desktop/build-all.sh` / `.ps1` = prepare-resources + `npm run dist` in one command.
- [ ] `DEPLOYMENT_LOCAL.md` Phase 2 section: prerequisites per build OS (Node, Python/uv, Xcode CLT on Mac, NSIS via electron-builder on Win), the build commands, signing env vars, release process.
- [ ] Commit: `git commit -am "docs(desktop): Phase 2 build + release guide"`.

---

## VERIFICATION
```bash
# OS-agnostic (any machine, incl. this one):
cd backend && PYTHONPATH=. uv run pytest tests/test_packaged_entrypoint.py -v   # migrations → head
cd backend && PYTHONPATH=. uv run pytest -q                                     # full suite still green
# On Windows build machine:
./desktop/scripts/prepare-resources.ps1 && cd desktop && npm install && npm run dist   # → Setup .exe
# On macOS build machine:
./desktop/scripts/prepare-resources.sh && cd desktop && npm install && npm run dist     # → .dmg
```
**Definition of done:** double-clicking the installer on a clean Windows and a clean macOS box installs Easy-Books with no other software present; launching opens the app; a fresh signup works; data persists in the user profile; Backup/Restore works; a subsequent version installs over it and migrates the data.

## NOTES / RISKS
- **Cannot build/test here** — Tasks 5–9 require real Windows + macOS machines (electron-builder won't cross-compile signed installers). Tasks 1–2 and the Electron logic in 4 are verifiable on any OS.
- **PyInstaller hidden imports** are the most likely runtime snag for FastAPI/uvicorn — budget time to add missing modules to the `.spec` after the first smoke run.
- **Bundle size** ≈ Electron(~150MB) + Chromium + Python deps + Node (~60MB) → expect a 200–300 MB installer. The "drop Node via static export" option would shave the Node sidecar later if size matters.
- **Signing certs are external inputs** (Windows code-signing `.pfx`, Apple Developer ID + notarization) — never committed; supplied via env on the build machines.
- **Alembic-from-empty:** packaged installs build the schema purely from the migration chain (`upgrade head`); the existing `has_table`-guarded migrations make this safe on a brand-new DB.
