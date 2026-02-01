export { };

declare global {
  interface Window {
    harborpilot?: {
      getBackendInfo: () => Promise<{
        port: number | null;
        token: string | null;
        baseUrl: string | null;
        pid: number | null;
      }>;
      pickWorkspace: (options?: { defaultPath?: string }) => Promise<string | null>;
      openPath: (targetPath: string) => Promise<{ ok: boolean; error?: string | null }>;
      windowControl?: {
        minimize: () => void;
        maximize: () => void;
        close: () => void;
      };
    };
  }
}
