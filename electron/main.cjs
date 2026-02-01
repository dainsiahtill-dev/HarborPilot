const { app, BrowserWindow, ipcMain, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const { randomBytes } = require("crypto");
const net = require("net");
const path = require("path");

// Guard against Electron being forced into Node mode by an inherited env var.
if (process.env.ELECTRON_RUN_AS_NODE) {
  delete process.env.ELECTRON_RUN_AS_NODE;
}

const repoRoot = path.join(__dirname, "..");
const backendScript = path.join(__dirname, "..", "backend", "server.py");
const frontendDist = path.join(__dirname, "..", "frontend", "dist", "index.html");

let backendProcess = null;
let backendInfo = {
  port: null,
  token: null,
  baseUrl: null,
  pid: null,
};

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

async function startBackend() {
  const port = await getFreePort();
  const token = randomBytes(16).toString("hex");
  const python = process.env.HARBORPILOT_PYTHON || "python";
  const args = [backendScript, "--host", "127.0.0.1", "--port", String(port), "--token", token];

  const workspace = process.env.HARBORPILOT_WORKSPACE;
  if (workspace) {
    args.push("--workspace", workspace);
  }

  backendProcess = spawn(python, args, {
    cwd: repoRoot,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });

  backendInfo = {
    port,
    token,
    baseUrl: `http://127.0.0.1:${port}`,
    pid: backendProcess.pid,
  };

  backendProcess.stdout.on("data", (data) => {
    process.stdout.write(`[backend] ${data}`);
  });

  backendProcess.stderr.on("data", (data) => {
    process.stderr.write(`[backend] ${data}`);
  });

  backendProcess.on("exit", (code) => {
    console.log(`[backend] exited with code ${code}`);
    backendProcess = null;
  });

  backendProcess.on("error", (err) => {
    console.error(`[backend] spawn failed: ${err.message}`);
  });
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 900,
    frame: false, // Custom frame
    backgroundColor: '#000000', // Avoid white flash
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });

  const devUrl = process.env.HARBORPILOT_DEV_SERVER_URL || "http://localhost:5173";
  if (!app.isPackaged) {
    await win.loadURL(devUrl);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    await win.loadFile(frontendDist);
  }
}

app.whenReady().then(async () => {
  await startBackend();

  // Backend IPC - Register BEFORE creating window so renderer can call them immediately
  ipcMain.handle("hp:get-backend", async () => backendInfo);
  ipcMain.handle("hp:pick-workspace", async (_event, options = {}) => {
    const result = await dialog.showOpenDialog({
      properties: ["openDirectory"],
      defaultPath: options.defaultPath || undefined,
    });
    if (result.canceled || !result.filePaths.length) {
      return null;
    }
    return result.filePaths[0];
  });
  ipcMain.handle("hp:open-path", async (_event, targetPath) => {
    if (!targetPath) {
      return { ok: false, error: "path is required" };
    }
    const error = await shell.openPath(targetPath);
    if (error) {
      return { ok: false, error };
    }
    return { ok: true, error: null };
  });

  // Window Control IPC
  ipcMain.handle("hp:window-minimize", (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    win?.minimize();
  });
  ipcMain.handle("hp:window-maximize", (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (win?.isMaximized()) {
      win.unmaximize();
    } else {
      win?.maximize();
    }
  });
  ipcMain.handle("hp:window-close", (event) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    win?.close();
  });

  await createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (backendInfo && backendInfo.baseUrl && backendInfo.token) {
    const url = `${backendInfo.baseUrl}/app/shutdown`;
    try {
      fetch(url, {
        method: "POST",
        headers: { authorization: `Bearer ${backendInfo.token}` },
      }).catch(() => { });
    } catch { }
  }
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});
