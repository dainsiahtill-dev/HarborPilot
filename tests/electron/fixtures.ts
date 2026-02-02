import { _electron as electron, ElectronApplication, Page, test as base } from "@playwright/test";
import fs from "fs";
import path from "path";
import { pathToFileURL } from "url";

type Fixtures = {
  electronApp: ElectronApplication;
  window: Page;
};

const repoRoot = path.resolve(__dirname, "..", "..");
const electronMain = path.join(repoRoot, "electron", "main.cjs");

function resolveVenvPython(): string {
  const venvRoot = path.join(repoRoot, ".venv");
  const pythonPath = process.platform === "win32"
    ? path.join(venvRoot, "Scripts", "python.exe")
    : path.join(venvRoot, "bin", "python");
  return fs.existsSync(pythonPath) ? pythonPath : "";
}

function resolveDevUrl(): string | undefined {
  if (process.env.HARBORPILOT_DEV_SERVER_URL) {
    return process.env.HARBORPILOT_DEV_SERVER_URL;
  }
  const distIndex = path.join(repoRoot, "frontend", "dist", "index.html");
  if (fs.existsSync(distIndex)) {
    return pathToFileURL(distIndex).toString();
  }
  return undefined;
}

export const test = base.extend<Fixtures>({
  electronApp: async ({}, use) => {
    const env = { ...process.env };
    delete env.ELECTRON_RUN_AS_NODE;
    const venvPython = resolveVenvPython();
    if (venvPython && !env.HARBORPILOT_PYTHON) {
      env.HARBORPILOT_PYTHON = venvPython;
    }
    const devUrl = resolveDevUrl();
    if (devUrl) {
      env.HARBORPILOT_DEV_SERVER_URL = devUrl;
    }
    const app = await electron.launch({
      args: [electronMain],
      env,
    });
    await use(app);
    await app.close();
  },
  window: async ({ electronApp }, use) => {
    const page = await electronApp.firstWindow();
    await page.waitForLoadState("domcontentloaded");
    await use(page);
  },
});

export { expect } from "@playwright/test";
