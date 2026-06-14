const { app, BrowserWindow, dialog, ipcMain } = require("electron")
const { autoUpdater } = require("electron-updater")
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
    SEED_DEMO: "true",  // auto-load demo on first launch; run_packaged seeds only an empty DB
    APP_ENV: "local",
    // The window loads http://127.0.0.1:3000 and the UI calls http://localhost:8000,
    // so the backend must allow BOTH origins or the browser CORS-blocks every API
    // call (signup/login fail with "Failed to fetch").
    FRONTEND_ORIGIN: "http://127.0.0.1:3000,http://localhost:3000",
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

const SPLASH = "data:text/html;charset=utf-8," + encodeURIComponent(
  `<!doctype html><meta charset="utf-8"><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;font-family:system-ui,Segoe UI,Arial;background:#f6f3ee;color:#1a1814">
   <div style="text-align:center">
     <div style="font:600 22px/1.2 Georgia,serif">Easy-Books</div>
     <div style="margin-top:10px;font-size:13px;color:#1a1814aa">Starting up… first-time setup may take ~30 seconds.</div>
   </div></body>`
)

async function createWindow() {
  win = new BrowserWindow({
    width: 1280, height: 840, show: false,
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false },
  })
  win.once("ready-to-show", () => win.show())
  // Show a splash immediately, then wait for BOTH sidecars before loading the
  // app — never show the UI before the API is ready. The backend may run a
  // one-time demo seed on first launch (~20-30s), so allow a generous window.
  await win.loadURL(SPLASH)
  try {
    await waitForServer(BACKEND_PORT, 360)   // up to ~3 min, covers first-run seeding
    await waitForServer(FRONTEND_PORT)
    await win.loadURL(`http://127.0.0.1:${FRONTEND_PORT}`)
  } catch (e) {
    dialog.showErrorBox("Easy-Books failed to start", String(e))
    app.quit()
  }
}

// When the repo has no PRODUCTION release with an update manifest yet,
// electron-updater throws (no published versions / can't parse the releases
// feed / missing latest.yml / 404 / 406). That's not a real failure — there's
// simply nothing to update to. Treat that whole class as "up to date" instead
// of surfacing a scary error in the UI. Genuine errors (network, etc.) still
// propagate.
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
    // B.7: macOS auto-update fails with signing errors if cert absent; degrade gracefully
    m.includes("code signature") ||
    m.includes("could not be verified") ||
    m.includes("not signed") ||
    m.includes("certificate")
  )
}

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
  return () => { _checking = true }   // expose setter so startup call can mark in-progress
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) { app.quit() } else {
  app.on("second-instance", () => { if (win) { win.show(); win.focus() } })
  app.whenReady().then(() => {
    startSidecars(); createWindow()
    const setChecking = wireAutoUpdater()
    // Check GitHub Releases for a newer version and notify the user. Inert
    // until a release feed exists (see electron-builder.yml `publish`).
    try {
      setChecking()   // mark in-progress before startup check so modal check yields
      const p = autoUpdater.checkForUpdatesAndNotify()
      if (p && typeof p.finally === "function") p.finally(() => { /* _checking cleared by event handlers */ })
    } catch (_) {}
  })
}

function killSidecars() {
  for (const p of [backend, frontend]) { try { p && p.kill() } catch (_) {} }
}
app.on("window-all-closed", () => { killSidecars(); app.quit() })
app.on("before-quit", killSidecars)
process.on("exit", killSidecars)
