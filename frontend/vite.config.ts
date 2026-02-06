import { defineConfig } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: rootDir,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "./src"),
    },
  },
  build: {
    outDir: path.join(rootDir, "dist"),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/llm": {
        target: "http://127.0.0.1",
        changeOrigin: true,
      },
      "/api": {
        target: "http://127.0.0.1",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1",
        ws: true,
      },
    },
  },
});
