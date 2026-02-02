const { app, BrowserWindow, ipcMain, dialog, shell, safeStorage } = require("electron");
const { spawn, spawnSync } = require("child_process");
const { randomBytes } = require("crypto");
const pty = require("node-pty");
const net = require("net");
const path = require("path");
const fs = require("fs");

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
const ptySessions = new Map();

function buildPtyEnv(env) {
  const base = { ...process.env };
  if (env && typeof env === "object") {
    for (const [key, value] of Object.entries(env)) {
      if (value === undefined || value === null) continue;
      base[String(key)] = String(value);
    }
  }
  if (!base.TERM) {
    base.TERM = "xterm-256color";
  }
  return base;
}

function secretsPath() {
  return path.join(app.getPath("userData"), "secrets.json");
}

function loadSecrets() {
  const target = secretsPath();
  try {
    if (!fs.existsSync(target)) {
      return {};
    }
    const raw = fs.readFileSync(target, "utf-8");
    const data = JSON.parse(raw);
    return data && typeof data === "object" ? data : {};
  } catch {
    return {};
  }
}

function saveSecrets(payload) {
  const target = secretsPath();
  try {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, JSON.stringify(payload, null, 2), "utf-8");
  } catch {
    // ignore
  }
}

function setSecret(key, value) {
  if (!safeStorage.isEncryptionAvailable()) {
    return { ok: false, error: "safeStorage unavailable" };
  }
  if (!key) {
    return { ok: false, error: "key required" };
  }
  const data = loadSecrets();
  const encrypted = safeStorage.encryptString(String(value));
  data[key] = encrypted.toString("base64");
  saveSecrets(data);
  return { ok: true };
}

function getSecret(key) {
  if (!safeStorage.isEncryptionAvailable()) {
    return { ok: false, error: "safeStorage unavailable" };
  }
  if (!key) {
    return { ok: false, error: "key required" };
  }
  const data = loadSecrets();
  const encoded = data[key];
  if (!encoded) {
    return { ok: false, value: null };
  }
  try {
    const decrypted = safeStorage.decryptString(Buffer.from(encoded, "base64"));
    return { ok: true, value: decrypted };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

function deleteSecret(key) {
  if (!key) {
    return { ok: false, error: "key required" };
  }
  const data = loadSecrets();
  if (data && Object.prototype.hasOwnProperty.call(data, key)) {
    delete data[key];
    saveSecrets(data);
  }
  return { ok: true };
}

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

function resolveVenvPython() {
  const venvRoot = path.join(repoRoot, ".venv");
  const venvPython = process.platform === "win32"
    ? path.join(venvRoot, "Scripts", "python.exe")
    : path.join(venvRoot, "bin", "python");
  if (fs.existsSync(venvPython)) {
    return { exists: true, pythonPath: venvPython };
  }
  return { exists: false, pythonPath: "" };
}

function checkVenvDependencies(pythonPath) {
  if (!pythonPath) {
    return { ok: false, message: "No venv python configured." };
  }
  try {
    const result = spawnSync(pythonPath, ["-m", "pip", "check"], {
      cwd: repoRoot,
      encoding: "utf-8",
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });
    if (result.status === 0) {
      return { ok: true, message: "" };
    }
    return {
      ok: false,
      message: (result.stdout || result.stderr || "").trim(),
    };
  } catch (err) {
    return { ok: false, message: String(err) };
  }
}

function ensureVenvNotice() {
  const venv = resolveVenvPython();
  if (!venv.exists) {
    const text = [
      "Python 虚拟环境未检测到。",
      "请先运行 setup_venv.bat（Windows）或 setup_venv.sh（macOS/Linux）。",
    ].join("\n");
    console.warn(text);
    dialog.showMessageBoxSync({
      type: "warning",
      title: "HarborPilot",
      message: "缺少 Python 虚拟环境（.venv）",
      detail: text,
    });
    return { pythonPath: "" };
  }
  return { pythonPath: venv.pythonPath };
}

async function startBackend() {
  const port = await getFreePort();
  const token = randomBytes(16).toString("hex");
  const venv = ensureVenvNotice();
  if (!process.env.HARBORPILOT_PYTHON && venv.pythonPath) {
    process.env.HARBORPILOT_PYTHON = venv.pythonPath;
  }
  const python = process.env.HARBORPILOT_PYTHON || "python";
  if (venv.pythonPath) {
    const depCheck = checkVenvDependencies(venv.pythonPath);
    if (!depCheck.ok) {
      const detail = depCheck.message || "依赖检测失败，请重新运行 setup_venv。";
      console.warn(detail);
      dialog.showMessageBoxSync({
        type: "warning",
        title: "HarborPilot",
        message: "Python 依赖可能不完整",
        detail,
      });
    }
  }
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
    icon: path.join(__dirname, 'assets', 'icons', 'icon.png'), // 应用图标
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
  ipcMain.handle("hp:secrets-available", async () => {
    return { ok: true, available: safeStorage.isEncryptionAvailable() };
  });
  ipcMain.handle("hp:secrets-set", async (_event, payload) => {
    const key = payload?.key;
    const value = payload?.value;
    return setSecret(key, value);
  });
  ipcMain.handle("hp:secrets-get", async (_event, key) => {
    return getSecret(key);
  });
  ipcMain.handle("hp:secrets-delete", async (_event, key) => {
    return deleteSecret(key);
  });
  ipcMain.handle("hp:pty-start", async (event, payload = {}) => {
    const command = payload.command;
    if (!command) {
      return { ok: false, error: "command required" };
    }
    const args = Array.isArray(payload.args) ? payload.args.map((arg) => String(arg)) : [];
    const cols = Number(payload.cols) || 120;
    const rows = Number(payload.rows) || 32;
    const cwd = payload.cwd || repoRoot;
    const env = buildPtyEnv(payload.env);
    try {
      const term = pty.spawn(String(command), args, {
        name: "xterm-256color",
        cols,
        rows,
        cwd,
        env,
      });
      const id = randomBytes(8).toString("hex");
      const sender = event.sender;
      term.onData((data) => {
        if (sender.isDestroyed()) return;
        sender.send("hp:pty-data", { id, data });
      });
      term.onExit(({ exitCode, signal }) => {
        if (!sender.isDestroyed()) {
          sender.send("hp:pty-exit", { id, exitCode, signal });
        }
        ptySessions.delete(id);
      });
      ptySessions.set(id, { term, senderId: sender.id });
      return { ok: true, id };
    } catch (err) {
      return { ok: false, error: String(err) };
    }
  });
  ipcMain.handle("hp:pty-write", async (_event, payload = {}) => {
    const id = payload.id;
    const data = payload.data;
    if (!id) {
      return { ok: false, error: "id required" };
    }
    const session = ptySessions.get(id);
    if (!session) {
      return { ok: false, error: "session not found" };
    }
    try {
      session.term.write(String(data ?? ""));
      return { ok: true };
    } catch (err) {
      return { ok: false, error: String(err) };
    }
  });
  ipcMain.handle("hp:pty-resize", async (_event, payload = {}) => {
    const id = payload.id;
    const cols = Number(payload.cols);
    const rows = Number(payload.rows);
    if (!id) {
      return { ok: false, error: "id required" };
    }
    const session = ptySessions.get(id);
    if (!session) {
      return { ok: false, error: "session not found" };
    }
    if (!Number.isFinite(cols) || !Number.isFinite(rows)) {
      return { ok: false, error: "cols/rows required" };
    }
    try {
      session.term.resize(cols, rows);
      return { ok: true };
    } catch (err) {
      return { ok: false, error: String(err) };
    }
  });
  ipcMain.handle("hp:pty-close", async (_event, payload = {}) => {
    const id = payload.id;
    if (!id) {
      return { ok: false, error: "id required" };
    }
    const session = ptySessions.get(id);
    if (!session) {
      return { ok: true };
    }
    try {
      session.term.kill();
    } catch {
      // ignore
    }
    ptySessions.delete(id);
    return { ok: true };
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
  if (ptySessions.size > 0) {
    for (const session of ptySessions.values()) {
      try {
        session.term.kill();
      } catch {
        // ignore
      }
    }
    ptySessions.clear();
  }
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
