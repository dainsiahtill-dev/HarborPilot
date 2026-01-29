export type BackendInfo = {
  port: number | null;
  token: string | null;
  baseUrl: string | null;
  pid: number | null;
};

let cachedInfo: BackendInfo | null = null;

export async function getBackendInfo(): Promise<BackendInfo> {
  if (cachedInfo) {
    return cachedInfo;
  }
  if (!window.harborpilot?.getBackendInfo) {
    const anyWindow = window as any;
    const fallbackBase =
      (anyWindow.__DEV_BACKEND__ && anyWindow.__DEV_BACKEND__.baseUrl) ||
      localStorage.getItem("harborpilot.baseUrl") ||
      "http://127.0.0.1:49977";
    const fallbackToken =
      (anyWindow.__DEV_BACKEND__ && anyWindow.__DEV_BACKEND__.token) ||
      localStorage.getItem("harborpilot.token") ||
      null;
    const info: BackendInfo = {
      port: null,
      token: fallbackToken,
      baseUrl: fallbackBase,
      pid: null,
    };
    cachedInfo = info;
    return info;
  }
  const info = await window.harborpilot.getBackendInfo();
  cachedInfo = info;
  return info;
}

function clearBackendInfoCache() {
  cachedInfo = null;
}

export async function pickWorkspace(defaultPath?: string): Promise<string | null> {
  if (!window.harborpilot?.pickWorkspace) {
    throw new Error("Electron preload not available.");
  }
  return window.harborpilot.pickWorkspace({ defaultPath });
}

export async function openPath(targetPath: string): Promise<{ ok: boolean; error?: string | null }> {
  if (!window.harborpilot?.openPath) {
    throw new Error("Electron preload not available.");
  }
  return window.harborpilot.openPath(targetPath);
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const doFetch = async (info: BackendInfo) => {
    if (!info.baseUrl) {
      throw new Error("Backend baseUrl missing.");
    }
    const headers = new Headers(init.headers || {});
    if (info.token) {
      headers.set("Authorization", `Bearer ${info.token}`);
    }
    return fetch(`${info.baseUrl}${path}`, { ...init, headers });
  };

  let info = await getBackendInfo();
  try {
    const res = await doFetch(info);
    if (res.status === 401) {
      clearBackendInfoCache();
      info = await getBackendInfo();
      return doFetch(info);
    }
    return res;
  } catch (err) {
    clearBackendInfoCache();
    info = await getBackendInfo();
    return doFetch(info);
  }
}

export async function connectWebSocket(): Promise<WebSocket> {
  let info = await getBackendInfo();
  if (!info.baseUrl) {
    clearBackendInfoCache();
    info = await getBackendInfo();
  }
  if (!info.baseUrl) {
    throw new Error("Backend baseUrl missing.");
  }
  const wsUrl = info.baseUrl.replace(/^http/, "ws") + `/ws?token=${encodeURIComponent(info.token || "")}`;
  return new WebSocket(wsUrl);
}
