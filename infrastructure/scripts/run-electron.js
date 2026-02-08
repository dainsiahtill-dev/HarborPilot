const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const repoRoot = path.join(__dirname, "..", "..");
const electronMain = path.join(repoRoot, "src", "electron", "main.cjs");

function resolveVenvPython() {
  const venvRoot = path.join(repoRoot, ".venv");
  const pythonPath = process.platform === "win32"
    ? path.join(venvRoot, "Scripts", "python.exe")
    : path.join(venvRoot, "bin", "python");
  if (fs.existsSync(pythonPath)) {
    return pythonPath;
  }
  return "";
}

const env = { ...process.env };
const venvPython = resolveVenvPython();
const configuredPython = (env.HARBORPILOT_PYTHON || "").trim();

if (venvPython) {
  if (!configuredPython) {
    env.HARBORPILOT_PYTHON = venvPython;
  } else if (!fs.existsSync(configuredPython)) {
    console.warn(`[harborpilot] HARBORPILOT_PYTHON not found: ${configuredPython}`);
    env.HARBORPILOT_PYTHON = venvPython;
  }
}

console.log(`[harborpilot] python: ${env.HARBORPILOT_PYTHON || "python"}`);

const electronBinary = require("electron");
const child = spawn(electronBinary, [electronMain], {
  stdio: "inherit",
  env,
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
