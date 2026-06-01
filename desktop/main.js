const { app, BrowserWindow, dialog } = require("electron")
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

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) { app.quit() } else {
  app.on("second-instance", () => { if (win) { win.show(); win.focus() } })
  app.whenReady().then(() => {
    startSidecars(); createWindow()
    // Check GitHub Releases for a newer version and notify the user. Inert
    // until a release feed exists (see electron-builder.yml `publish`).
    try { autoUpdater.checkForUpdatesAndNotify() } catch (_) {}
  })
}

function killSidecars() {
  for (const p of [backend, frontend]) { try { p && p.kill() } catch (_) {} }
}
app.on("window-all-closed", () => { killSidecars(); app.quit() })
app.on("before-quit", killSidecars)
process.on("exit", killSidecars)
