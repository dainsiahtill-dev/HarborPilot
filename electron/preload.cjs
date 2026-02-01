const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("harborpilot", {
  getBackendInfo: () => ipcRenderer.invoke("hp:get-backend"),
  pickWorkspace: (options) => ipcRenderer.invoke("hp:pick-workspace", options),
  openPath: (targetPath) => ipcRenderer.invoke("hp:open-path", targetPath),
});
