# Issue #78 — Update Procedure Bugs & Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two critical update bugs (A.3: PowerShell Expand-Archive error; B.2: Electron auto-update check fails with content-type mismatch) and add five hardening items (B.3 install confirmation, B.4 pre-migration backup, B.5 friendly failure dialog, B.6 duplicate-check guard, B.8 version wiring).

**Architecture:** All fixes are self-contained edits to existing files — no new pages, no schema changes, no new routers. The two critical bugs (A.3, B.2) are independent of each other; the hardening items (B.3–B.8) build on top. Tasks are ordered: bugs first, then hardening, then build-time wiring.

**Tech Stack:** PowerShell 5.1 (install-and-run.ps1), Electron + electron-updater (desktop/), React/TypeScript (UpdateModal.tsx), Python (run_packaged.py / pytest).

---

## File Map

| File | Change |
|------|--------|
| `install-and-run.ps1:42-47` | A.3 — Replace `Expand-Archive -Force` with `ZipFile::ExtractToDirectory` |
| `desktop/scripts/prepare-resources.ps1:17-22` | A.3 same fix (duplicate Node-download block) |
| `desktop/package.json` | B.2 — Bump `electron-updater` `^6.3.0` → `^6.8.9` |
| `desktop/main.js:79-115` | B.2+B.6+B.7 — Extend `isNoReleaseError()`, add in-progress guard, capture stderr for B.5 |
| `frontend/src/components/UpdateModal.tsx:125-201` | B.3 — Add confirmation state before `installUpdate()` |
| `backend/run_packaged.py` | B.4+B.5 — `backup_db()` + version tracking + `sys.exit(1)` on migration failure |
| `backend/easybooks-backend.spec` | B.8 — Add `VERSION` file to PyInstaller `datas` |
| `desktop/scripts/prepare-resources.sh` | B.8 — Write `backend/VERSION` + set `NEXT_PUBLIC_APP_VERSION` before `next build` |
| `desktop/scripts/prepare-resources.ps1` | B.8 — Same as above for Windows |
| `backend/tests/test_run_packaged.py` | New — pytest for `backup_db` logic |

---

## Task 1 — A.3: Fix `Expand-Archive` cosmetic error in PowerShell scripts

**Context:** `Expand-Archive -Force` in PowerShell 5.1 pre-builds a flat list of every entry, then calls `Remove-Item` on each one. When a directory is deleted, its children are already gone, so the loop throws "Cannot find path" for them. The fix is `.NET`'s `ZipFile::ExtractToDirectory`, which has no such bug and is faster.

There are **two** places with this bug:
1. `install-and-run.ps1:43` — fires when the user installs/updates on a machine with no system Node
2. `desktop/scripts/prepare-resources.ps1:18` — fires when a developer builds the desktop installer on a machine with no system Node

**Files:**
- Modify: `install-and-run.ps1:37-48`
- Modify: `desktop/scripts/prepare-resources.ps1:11-23`

- [ ] **Step 1: Fix `install-and-run.ps1` line 43**

Replace:
```powershell
    Expand-Archive 'node.zip' -DestinationPath '.nodetmp' -Force
```
With:
```powershell
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory(
        (Join-Path $Root 'node.zip'), (Join-Path $Root '.nodetmp'))
```

The complete corrected block (`install-and-run.ps1:37-48`) after the fix:
```powershell
  if (-not (Test-Path $NodeExe)) {
    Log "Downloading a local Node.js $NodeVersion (no system install)..."
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'x64' }
    $url  = "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-$arch.zip"
    Invoke-WebRequest -Uri $url -OutFile 'node.zip'
    if (Test-Path '.nodetmp') { Remove-Item '.nodetmp' -Recurse -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory(
        (Join-Path $Root 'node.zip'), (Join-Path $Root '.nodetmp'))
    Move-Item (Join-Path '.nodetmp' "node-v$NodeVersion-win-$arch") $NodeDir -Force
    Remove-Item 'node.zip' -Force
    Remove-Item '.nodetmp' -Recurse -Force
  }
```

- [ ] **Step 2: Fix `desktop/scripts/prepare-resources.ps1` lines 17-21**

The block currently (`prepare-resources.ps1:13-23`):
```powershell
  if (-not (Test-Path (Join-Path $NodeDir "node.exe"))) {
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
    $pkg  = "node-v$NodeVersion-win-$arch"
    Invoke-WebRequest "https://nodejs.org/dist/v$NodeVersion/$pkg.zip" -OutFile "$Root\node-build.zip"
    if (Test-Path "$Root\.nodetmp") { Remove-Item "$Root\.nodetmp" -Recurse -Force }
    Expand-Archive "$Root\node-build.zip" -DestinationPath "$Root\.nodetmp" -Force
    Move-Item (Join-Path "$Root\.nodetmp" $pkg) $NodeDir -Force
    Remove-Item "$Root\node-build.zip","$Root\.nodetmp" -Recurse -Force
  }
```

Replace `Expand-Archive` line with:
```powershell
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory(
        "$Root\node-build.zip", "$Root\.nodetmp")
```

Full corrected block:
```powershell
  if (-not (Test-Path (Join-Path $NodeDir "node.exe"))) {
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
    $pkg  = "node-v$NodeVersion-win-$arch"
    Invoke-WebRequest "https://nodejs.org/dist/v$NodeVersion/$pkg.zip" -OutFile "$Root\node-build.zip"
    if (Test-Path "$Root\.nodetmp") { Remove-Item "$Root\.nodetmp" -Recurse -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory(
        "$Root\node-build.zip", "$Root\.nodetmp")
    Move-Item (Join-Path "$Root\.nodetmp" $pkg) $NodeDir -Force
    Remove-Item "$Root\node-build.zip","$Root\.nodetmp" -Recurse -Force
  }
```

- [ ] **Step 3: Verify (manual — Windows only)**

On a Windows machine that has no system Node installed, delete `.node/` if present, then run:
```powershell
powershell -ExecutionPolicy Bypass -File install-and-run.ps1
```
Expected: No red PowerShell error blocks. "Update finished. Press any key to close." and the app launches at http://127.0.0.1:3000.

- [ ] **Step 4: Commit**
```bash
git add install-and-run.ps1 desktop/scripts/prepare-resources.ps1
git commit -m "fix(installer): replace Expand-Archive -Force with ZipFile::ExtractToDirectory (A.3)

Eliminates cosmetic 'Cannot find path' PowerShell errors during Node.js
auto-download on machines with no system Node. PS5.1 Expand-Archive -Force
pre-builds a flat entry list then Remove-Items each — deleting the parent
already removed children, so their Remove-Items throw. ZipFile::ExtractToDirectory
has no such bug. Fixes two locations: install-and-run.ps1 and prepare-resources.ps1."
```

---

## Task 2 — B.2 + B.7: Fix auto-update check failure + macOS signing errors

**Context:** `electron-updater ^6.3.0` fetches `releases.atom` and fails with "Unexpected content type: text/html" because GitHub serves that content-type even for the Atom feed. Bumping to `^6.8.9` fixes the underlying HTTP handling. A second defensive layer extends `isNoReleaseError()` to treat content-type mismatches as "no release" rather than a real error. The same extension also handles macOS code-signing errors (B.7), which should also show as "auto-update unavailable" rather than a raw error.

**Files:**
- Modify: `desktop/package.json` (version bump)
- Modify: `desktop/main.js:79-90` (`isNoReleaseError`)

- [ ] **Step 1: Bump `electron-updater` in `desktop/package.json`**

Change line `"electron-updater": "^6.3.0"` to:
```json
"electron-updater": "^6.8.9"
```

- [ ] **Step 2: Install the updated dependency**
```bash
cd desktop && npm install
```
Expected: `package-lock.json` updated; `node_modules/electron-updater/package.json` shows version ≥ 6.8.9.

- [ ] **Step 3: Extend `isNoReleaseError()` in `desktop/main.js`**

Replace the existing function (lines 79-90):
```js
function isNoReleaseError(err) {
  const m = String(err).toLowerCase()
  return (
    m.includes("no published versions") ||
    m.includes("unable to find latest version") ||
    m.includes("please ensure a production release exists") ||
    m.includes("cannot parse releases feed") ||
    m.includes("latest.yml") ||          // missing update manifest (incl. latest-mac.yml)
    m.includes("httperror: 404") ||
    m.includes("httperror: 406")
  )
}
```

With:
```js
function isNoReleaseError(err) {
  const m = String(err).toLowerCase()
  return (
    m.includes("no published versions") ||
    m.includes("unable to find latest version") ||
    m.includes("please ensure a production release exists") ||
    m.includes("cannot parse releases feed") ||
    m.includes("latest.yml") ||        // missing update manifest (incl. latest-mac.yml)
    m.includes("httperror: 404") ||
    m.includes("httperror: 406") ||
    // B.2: GitHub serves releases.atom with text/html content-type; treat as "no update"
    m.includes("unexpected content type") ||
    // B.7: macOS auto-update fails with signing errors if cert is absent; degrade gracefully
    m.includes("code signature") ||
    m.includes("could not be verified") ||
    m.includes("not signed") ||
    m.includes("certificate")
  )
}
```

- [ ] **Step 4: Verify (manual — requires Electron build)**

Build the desktop app on the current `main` version:
```bash
./desktop/build-all.sh    # or build-all.ps1 on Windows
```
Launch the built app → go to **Settings → Check for Updates**.

Expected outcomes (whichever applies):
- If running the same version as the latest GitHub Release: shows "You're up to date ✓" — no raw error text.
- If running an older version: shows "Downloading vX.Y.Z…" or "Update available".
- No "Unexpected content type" or "text/html" error text ever appears in the UI.

- [ ] **Step 5: Commit**
```bash
git add desktop/package.json desktop/package-lock.json desktop/main.js
git commit -m "fix(desktop): fix auto-update check content-type failure + macOS signing errors (B.2, B.7)

electron-updater >=6.8.9 fixes the HTTP response handling that caused GitHub's
releases.atom to fail with 'Unexpected content type: text/html'. Additionally
extends isNoReleaseError() to treat content-type mismatch and macOS code-signing
errors as 'up to date' rather than surfacing raw error messages to users."
```

---

## Task 3 — B.6: Prevent duplicate concurrent update checks

**Context:** `autoUpdater.checkForUpdatesAndNotify()` fires at app ready (startup), and `autoUpdater.checkForUpdates()` fires again when the modal opens — two simultaneous check lifecycles that can show inconsistent states. A simple in-progress flag in `wireAutoUpdater` gates the manual check while a startup check is running.

**Files:**
- Modify: `desktop/main.js:92-116` (`wireAutoUpdater` + app-ready block)

- [ ] **Step 1: Add in-progress guard to `wireAutoUpdater` in `desktop/main.js`**

Replace the `wireAutoUpdater` function and the app-ready startup call:

```js
function wireAutoUpdater() {
  let _checking = false
  const send = (status) => { try { if (win) win.webContents.send("eb:update-status", status) } catch (_) {} }
  autoUpdater.on("checking-for-update", () => send({ state: "checking" }))
  autoUpdater.on("update-available",    (i) => send({ state: "available", version: i && i.version }))
  autoUpdater.on("update-not-available",() => { _checking = false; send({ state: "none" }) })
  autoUpdater.on("error",               (e) => { _checking = false; send(isNoReleaseError(e) ? { state: "none" } : { state: "error", message: String(e) }) })
  autoUpdater.on("download-progress",   (p) => send({ state: "downloading", percent: Math.round(p.percent || 0) }))
  autoUpdater.on("update-downloaded",   (i) => { _checking = false; send({ state: "downloaded", version: i && i.version }) })
  ipcMain.handle("eb:check-for-updates", async () => {
    if (_checking) return { ok: true }   // startup check already in progress — events will arrive
    _checking = true
    try { await autoUpdater.checkForUpdates(); return { ok: true } }
    catch (e) { _checking = false; return isNoReleaseError(e) ? { ok: true } : { ok: false, error: String(e) } }
  })
  ipcMain.handle("eb:install-update", () => { try { autoUpdater.quitAndInstall() } catch (_) {} })
  return () => { _checking = true }   // expose a setter so the startup call can set the flag
}
```

Update the startup call block (replace lines 110-116):
```js
  app.whenReady().then(() => {
    startSidecars(); createWindow()
    const setChecking = wireAutoUpdater()
    try {
      setChecking()   // mark in-progress before the startup check begins
      const p = autoUpdater.checkForUpdatesAndNotify()
      if (p && typeof p.finally === "function") p.finally(() => { /* flag cleared by event handlers */ })
    } catch (_) {}
  })
```

- [ ] **Step 2: Verify (manual)**

Open the desktop app, then immediately open **Settings → Check for Updates**. The spinner should appear once — not twice — and no duplicate "checking" state flash should occur.

- [ ] **Step 3: Commit**
```bash
git add desktop/main.js
git commit -m "fix(desktop): prevent duplicate concurrent update checks (B.6)

Add _checking in-progress flag to wireAutoUpdater. When autoUpdater fires at
app-ready, a manual check from the modal returns early instead of starting a
second parallel check cycle."
```

---

## Task 4 — B.3: Confirmation before "Restart & Install"

**Context:** `handleInstall()` in `UpdateModal.tsx` calls `installUpdate()` immediately, which calls `autoUpdater.quitAndInstall()` — quitting the app with no warning. Any unsaved form data is lost. Add a two-step confirmation using React state (no library needed).

**Files:**
- Modify: `frontend/src/components/UpdateModal.tsx:44-51` (state), `125-127` (handler), `186-201` (render)

- [ ] **Step 1: Add `confirmInstall` state at the top of the component**

Add to the existing state declarations (after line 51 `const [updaterStatus, ...]`):
```tsx
  const [confirmInstall, setConfirmInstall] = useState(false)
```

- [ ] **Step 2: Replace `handleInstall` (lines 125-127)**

```tsx
  const handleInstall = () => {
    if (!confirmInstall) { setConfirmInstall(true); return }
    try { window.easybooks!.installUpdate() } catch { /* best effort */ }
  }

  const handleInstallCancel = () => setConfirmInstall(false)
```

- [ ] **Step 3: Update the `downloaded` render branch (lines 186-201)**

Replace:
```tsx
    if (s.state === 'downloaded') {
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
            <CheckCircle className="w-4 h-4" />
            {s.version ? `v${s.version} is ready.` : 'Update ready.'}
          </div>
          <button
            onClick={handleInstall}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#1a1814] text-white rounded-lg font-medium text-sm hover:bg-[#b8943f] transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Restart &amp; Install
          </button>
        </div>
      )
    }
```

With:
```tsx
    if (s.state === 'downloaded') {
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
            <CheckCircle className="w-4 h-4" />
            {s.version ? `v${s.version} is ready.` : 'Update ready.'}
          </div>
          {confirmInstall ? (
            <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 space-y-2">
              <p className="text-sm text-amber-800 font-medium">Unsaved changes will be lost. Restart now?</p>
              <div className="flex gap-2">
                <button
                  onClick={handleInstall}
                  className="flex items-center gap-2 px-4 py-2 bg-[#1a1814] text-white rounded-lg font-medium text-sm hover:bg-[#b8943f] transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                  Yes, Restart
                </button>
                <button
                  onClick={handleInstallCancel}
                  className="px-4 py-2 border border-black/20 rounded-lg font-medium text-sm hover:bg-black/5 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={handleInstall}
              className="flex items-center gap-2 px-5 py-2.5 bg-[#1a1814] text-white rounded-lg font-medium text-sm hover:bg-[#b8943f] transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Restart &amp; Install
            </button>
          )}
        </div>
      )
    }
```

- [ ] **Step 4: Verify TypeScript compiles**
```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: build succeeds with no type errors.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/UpdateModal.tsx
git commit -m "fix(desktop): add confirmation step before Restart & Install (B.3)

Clicking 'Restart & Install' now shows an inline amber warning ('Unsaved
changes will be lost. Restart now?') with Yes/Cancel before calling
quitAndInstall(). Prevents accidental data loss on open forms."
```

---

## Task 5 — B.4 + B.5: Pre-migration DB backup + friendly failure dialog

**Context:** `run_packaged.py` calls `migrate()` on every launch with no DB backup. If a new migration fails or corrupts data, the user has no recovery path. Additionally, on migration failure the backend exits with no message and `main.js` shows a generic timeout error.

Fix has three parts:
1. `backup_db()` in `run_packaged.py` copies `database.db → database.db.bak-<version>` when the app version has changed (first launch after an update).
2. `main()` in `run_packaged.py` exits with a clear FATAL message on migration failure.
3. `main.js` captures backend stderr and surfaces it (with backup location) instead of the generic "timeout" dialog.

**Files:**
- Modify: `backend/run_packaged.py`
- Modify: `desktop/main.js:8` (module-level var) + `15-33` (`startSidecars`) + `63-70` (`createWindow` error branch)
- Create: `backend/tests/test_run_packaged.py`

- [ ] **Step 1: Write the pytest test for `backup_db` (TDD — write first, runs red)**

Create `backend/tests/test_run_packaged.py`:
```python
"""Tests for run_packaged.backup_db version-aware backup logic."""
import shutil
from pathlib import Path
import pytest


# Import the functions we're about to write
from run_packaged import backup_db, write_last_version


def test_backup_skipped_when_no_db(tmp_path):
    """No DB file → no backup created, returns None."""
    db = tmp_path / "database.db"
    result = backup_db(db, tmp_path, "2.6.0")
    assert result is None


def test_backup_skipped_on_same_version(tmp_path):
    """DB exists but version unchanged → no backup."""
    db = tmp_path / "database.db"
    db.write_text("fake db")
    (tmp_path / ".last-app-version").write_text("2.6.0")
    result = backup_db(db, tmp_path, "2.6.0")
    assert result is None


def test_backup_created_on_version_change(tmp_path):
    """DB exists and version has changed → backup created."""
    db = tmp_path / "database.db"
    db.write_text("fake db content")
    (tmp_path / ".last-app-version").write_text("2.5.0")
    result = backup_db(db, tmp_path, "2.6.0")
    assert result is not None
    assert result == tmp_path / "database.db.bak-2.6.0"
    assert result.exists()
    assert result.read_text() == "fake db content"
    assert db.exists()          # original untouched


def test_backup_created_on_first_install(tmp_path):
    """DB exists but no .last-app-version file → first update after no version tracking → backup."""
    db = tmp_path / "database.db"
    db.write_text("data")
    # no .last-app-version file
    result = backup_db(db, tmp_path, "2.6.0")
    assert result == tmp_path / "database.db.bak-2.6.0"
    assert result.exists()


def test_write_last_version(tmp_path):
    write_last_version(tmp_path, "2.6.0")
    assert (tmp_path / ".last-app-version").read_text() == "2.6.0"


def test_write_last_version_overwrites(tmp_path):
    (tmp_path / ".last-app-version").write_text("2.5.0")
    write_last_version(tmp_path, "2.6.0")
    assert (tmp_path / ".last-app-version").read_text() == "2.6.0"
```

- [ ] **Step 2: Run the test — expect FAIL (functions not yet defined)**
```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_run_packaged.py -v
```
Expected: `ImportError: cannot import name 'backup_db' from 'run_packaged'`

- [ ] **Step 3: Implement `backup_db`, `write_last_version`, `_app_version` in `run_packaged.py`**

Replace the entire `run_packaged.py` with:
```python
"""Packaged entrypoint: migrate the user's DB forward, then serve the API.

Used by the desktop build (PyInstaller). Unlike dev (which uses create_all),
packaged installs run Alembic so new COLUMNS on existing tables reach upgraded
users — create_all only ever adds new tables.
"""
import os
import shutil
import sys
from pathlib import Path


def _bundle_dir() -> Path:
    # PyInstaller sets sys._MEIPASS to the unpacked bundle; else the source dir.
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _app_version() -> str:
    """Read the bundled app version from the VERSION file written by prepare-resources."""
    version_file = _bundle_dir() / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "dev"


def backup_db(db_path: Path, data_dir: Path, version: str) -> Path | None:
    """Copy database.db → database.db.bak-<version> when the app version has changed.

    Skips if the DB doesn't exist (first install) or the version is unchanged.
    Returns the backup path if a backup was created, None otherwise.
    """
    if not db_path.exists():
        return None
    last_version_file = data_dir / ".last-app-version"
    last_version = last_version_file.read_text().strip() if last_version_file.exists() else ""
    if version == last_version:
        return None
    backup_path = db_path.parent / f"database.db.bak-{version}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def write_last_version(data_dir: Path, version: str) -> None:
    try:
        (data_dir / ".last-app-version").write_text(version)
    except OSError:
        pass


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
    os.environ.setdefault("SEED_DEMO", "true")  # auto-load demo on first install; SEED_DEMO=false for clean
    os.environ.setdefault("SCHEMA_BOOTSTRAP", "alembic")  # lifespan skips create_all

    from local_config import data_dir as get_data_dir, sqlite_path
    _data_dir = get_data_dir()
    _db_path = Path(sqlite_path())
    _version = _app_version()

    backup_path = backup_db(_db_path, _data_dir, _version)
    if backup_path:
        print(f"[migrate] Backed up DB → {backup_path}", flush=True)

    try:
        migrate()
    except Exception as exc:
        loc = f"\nBackup: {backup_path}" if backup_path else ""
        print(f"[migrate] FATAL: Migration failed: {exc}{loc}", flush=True)
        sys.exit(1)

    write_last_version(_data_dir, _version)

    # First-run only: load the demo companies BEFORE serving. autoseed is guarded
    # (skips once any user exists) so updates never re-seed.
    from scripts.autoseed_demo import main as autoseed_demo
    try:
        autoseed_demo()
    except Exception as exc:
        print(f"[autoseed] demo load failed (non-fatal): {exc}", flush=True)

    import uvicorn
    from main import app
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test — expect PASS**
```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_run_packaged.py -v
```
Expected:
```
PASSED tests/test_run_packaged.py::test_backup_skipped_when_no_db
PASSED tests/test_run_packaged.py::test_backup_skipped_on_same_version
PASSED tests/test_run_packaged.py::test_backup_created_on_version_change
PASSED tests/test_run_packaged.py::test_backup_created_on_first_install
PASSED tests/test_run_packaged.py::test_write_last_version
PASSED tests/test_run_packaged.py::test_write_last_version_overwrites
```

- [ ] **Step 5: Capture backend stderr in `desktop/main.js` for B.5 friendly error**

Add a module-level variable at the top of `main.js` (after `let backend, frontend, win`):
```js
let _backendErr = ""
```

In `startSidecars()`, after the `backend = spawn(...)` line, add:
```js
  backend.stderr.on("data", (d) => { _backendErr = (_backendErr + String(d)).slice(-2000) })
```

Replace the `catch (e)` block in `createWindow()` (lines 67-70):
```js
  } catch (e) {
    // If the backend exited with a FATAL migration error, surface its message
    // (which includes the backup location) instead of the generic timeout.
    const detail = _backendErr.includes("FATAL")
      ? _backendErr.replace(/.*\[migrate\] FATAL: /s, "").slice(0, 800)
      : String(e)
    dialog.showErrorBox("Easy-Books failed to start", detail)
    app.quit()
  }
```

- [ ] **Step 6: Run full backend test suite to verify no regressions**
```bash
cd backend && PYTHONPATH=. uv run pytest -q 2>&1 | tail -5
```
Expected: All tests pass (410 total, including the 6 new ones).

- [ ] **Step 7: Commit**
```bash
git add backend/run_packaged.py backend/tests/test_run_packaged.py desktop/main.js
git commit -m "fix(desktop): pre-migration DB backup + friendly failure dialog (B.4, B.5)

run_packaged.py now copies database.db → database.db.bak-<version> before
alembic upgrade head when the bundled app version has changed. On migration
failure it prints FATAL with the backup path and exits(1). desktop/main.js
captures backend stderr and surfaces the FATAL message (with backup location)
in the error dialog instead of a generic timeout message.

6 new pytest tests covering backup_db and write_last_version."
```

---

## Task 6 — B.8: Wire `NEXT_PUBLIC_APP_VERSION` + VERSION file into builds

**Context:** `UpdateModal.tsx:31` reads `process.env.NEXT_PUBLIC_APP_VERSION ?? 'dev'`. Next.js bakes this in at build time — if the env var isn't set when `next build` runs, the packaged app always shows "v dev". `prepare-resources.sh`/`.ps1` must:
1. Write `backend/VERSION` (so `run_packaged.py`'s `_app_version()` can read it via PyInstaller data)
2. Set `NEXT_PUBLIC_APP_VERSION` in the shell environment before `next build`

`easybooks-backend.spec` must add `VERSION` to its `datas`.

**Files:**
- Modify: `desktop/scripts/prepare-resources.sh:19-34`
- Modify: `desktop/scripts/prepare-resources.ps1:25-51`
- Modify: `backend/easybooks-backend.spec` (add `VERSION` to `datas`)

- [ ] **Step 1: Update `desktop/scripts/prepare-resources.sh`**

After the Node/npm PATH block (after line 18), add version extraction and VERSION file write. Then modify the `next build` call to inject the env var:

Replace:
```bash
# Backend binary
( cd "$ROOT/backend" && uv run pyinstaller easybooks-backend.spec )
```
With:
```bash
# Read version from desktop/package.json and write VERSION file for run_packaged.py
APP_VERSION=$(node -e "process.stdout.write(require('$ROOT/desktop/package.json').version)")
echo "$APP_VERSION" > "$ROOT/backend/VERSION"
echo "App version: $APP_VERSION"

# Backend binary (VERSION file is included by easybooks-backend.spec datas)
( cd "$ROOT/backend" && uv run pyinstaller easybooks-backend.spec )
```

Replace the frontend build line:
```bash
( cd "$ROOT/frontend" && npm install && npx next build )
```
With:
```bash
( cd "$ROOT/frontend" && npm install && NEXT_PUBLIC_APP_VERSION="$APP_VERSION" npx next build )
```

- [ ] **Step 2: Update `desktop/scripts/prepare-resources.ps1`**

After the `if (-not (Get-Command npm ...))` block (after line 23), add:
```powershell
# Read version from desktop/package.json
$AppVersion = (Get-Content (Join-Path $Root "desktop/package.json") | ConvertFrom-Json).version
Set-Content -Path (Join-Path $Root "backend/VERSION") -Value $AppVersion -NoNewline
Write-Host "App version: $AppVersion"
```

Modify the frontend build block (replace `npm install` + `npx next build` lines):
```powershell
Push-Location (Join-Path $Root "frontend")
npm install
$env:NEXT_PUBLIC_APP_VERSION = $AppVersion
npx next build
$env:NEXT_PUBLIC_APP_VERSION = $null
Pop-Location
```

- [ ] **Step 3: Add `VERSION` to PyInstaller `datas` in `backend/easybooks-backend.spec`**

The spec has:
```python
datas = [("alembic.ini", "."), ("alembic", "alembic")]
if os.path.isdir("templates"):
    datas.append(("templates", "templates"))
```

Add the VERSION file entry after `datas` is defined:
```python
datas = [("alembic.ini", "."), ("alembic", "alembic")]
if os.path.isdir("templates"):
    datas.append(("templates", "templates"))
if os.path.isfile("VERSION"):           # written by prepare-resources before pyinstaller runs
    datas.append(("VERSION", "."))
```

- [ ] **Step 4: Verify VERSION is read by run_packaged (unit test)**

Add to `backend/tests/test_run_packaged.py`:
```python
def test_app_version_reads_version_file(monkeypatch, tmp_path):
    """_app_version() reads VERSION from the bundle dir."""
    import run_packaged
    (tmp_path / "VERSION").write_text("3.1.4")
    monkeypatch.setattr(run_packaged, "_bundle_dir", lambda: tmp_path)
    assert run_packaged._app_version() == "3.1.4"


def test_app_version_fallback(monkeypatch, tmp_path):
    """_app_version() returns 'dev' when VERSION file is absent."""
    import run_packaged
    monkeypatch.setattr(run_packaged, "_bundle_dir", lambda: tmp_path)
    assert run_packaged._app_version() == "dev"
```

- [ ] **Step 5: Run updated tests**
```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_run_packaged.py -v
```
Expected: 8 tests pass.

- [ ] **Step 6: Verify a local build sets the version correctly (manual)**

Run `prepare-resources.sh` and inspect:
```bash
./desktop/scripts/prepare-resources.sh
cat backend/VERSION           # should print "2.6.0" (or current desktop/package.json version)
grep -r "NEXT_PUBLIC_APP_VERSION" desktop/resources/frontend/.next/server/app/  # should find it baked in
```

- [ ] **Step 7: Commit**
```bash
git add backend/easybooks-backend.spec backend/tests/test_run_packaged.py \
        desktop/scripts/prepare-resources.sh desktop/scripts/prepare-resources.ps1
git commit -m "fix(desktop): wire NEXT_PUBLIC_APP_VERSION + VERSION file into builds (B.8)

prepare-resources now reads the version from desktop/package.json, writes
backend/VERSION (picked up by run_packaged._app_version() via PyInstaller
datas), and sets NEXT_PUBLIC_APP_VERSION before next build so UpdateModal
shows the real version instead of 'dev'. 2 new pytest tests for _app_version."
```

---

## Self-Review

**Spec coverage:**
- A.3 Expand-Archive → Task 1 ✅
- B.2 content-type mismatch + electron-updater bump → Task 2 ✅
- B.3 confirmation before install → Task 4 ✅
- B.4 pre-migration backup → Task 5 ✅
- B.5 friendly failure dialog → Task 5 ✅
- B.6 duplicate check guard → Task 3 ✅
- B.7 macOS signing errors → Task 2 (`isNoReleaseError` extension) ✅
- B.8 NEXT_PUBLIC_APP_VERSION wiring → Task 6 ✅
- A.4 pre-update backup for script installs (mentioned in A.4 scope list) → Not implemented. The script-based version (`update.ps1`/`update.sh`) is out of scope for this plan — the Electron desktop equivalent (B.4) is covered. A separate issue would be needed for the script-based auto-backup.
- B.10 end-to-end update test (Tasks 7+8 in the desktop installer plan) → Not implemented here (manual QA step, not a code task). The acceptance criteria notes for B.2 cover the manual verification.

**Placeholder scan:** No TBD, no "implement later", no vague steps — all steps have concrete code. ✅

**Type consistency:** `backup_db(db_path: Path, data_dir: Path, version: str) -> Path | None` used consistently in tests and implementation. `write_last_version(data_dir: Path, version: str) -> None` consistent. `_app_version() -> str` consistent in test and usage in `main()`. ✅
