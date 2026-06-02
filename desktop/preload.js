// Hardened: no node access in the renderer; the UI is the existing web app.
const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("easybooks", {
  isDesktop: true,
  checkForUpdates: () => ipcRenderer.invoke("eb:check-for-updates"),
  installUpdate: () => ipcRenderer.invoke("eb:install-update"),
  onUpdateStatus: (cb) => {
    const handler = (_e, status) => cb(status)
    ipcRenderer.on("eb:update-status", handler)
    return () => ipcRenderer.removeListener("eb:update-status", handler)
  },
})

window.addEventListener("DOMContentLoaded", () => {})
