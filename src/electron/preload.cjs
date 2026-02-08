const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("harborpilot", {
  getBackendInfo: () => ipcRenderer.invoke("hp:get-backend"),
  pickWorkspace: (options) => ipcRenderer.invoke("hp:pick-workspace", options),
  openPath: (targetPath) => ipcRenderer.invoke("hp:open-path", targetPath),
  secrets: {
    available: () => ipcRenderer.invoke("hp:secrets-available"),
    get: (key) => ipcRenderer.invoke("hp:secrets-get", key),
    set: (key, value) => ipcRenderer.invoke("hp:secrets-set", { key, value }),
    remove: (key) => ipcRenderer.invoke("hp:secrets-delete", key),
  },
  pty: {
    start: (options) => ipcRenderer.invoke("hp:pty-start", options),
    write: (id, data) => ipcRenderer.invoke("hp:pty-write", { id, data }),
    resize: (id, cols, rows) => ipcRenderer.invoke("hp:pty-resize", { id, cols, rows }),
    close: (id) => ipcRenderer.invoke("hp:pty-close", { id }),
    onData: (handler) => {
      const listener = (_event, payload) => handler?.(payload);
      ipcRenderer.on("hp:pty-data", listener);
      return () => ipcRenderer.removeListener("hp:pty-data", listener);
    },
    onExit: (handler) => {
      const listener = (_event, payload) => handler?.(payload);
      ipcRenderer.on("hp:pty-exit", listener);
      return () => ipcRenderer.removeListener("hp:pty-exit", listener);
    },
  },
  windowControl: {
    minimize: () => ipcRenderer.invoke("hp:window-minimize"),
    maximize: () => ipcRenderer.invoke("hp:window-maximize"),
    close: () => ipcRenderer.invoke("hp:window-close"),
    getState: () => ipcRenderer.invoke("hp:window-get-state"),
  },
});
