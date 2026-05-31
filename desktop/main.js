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
