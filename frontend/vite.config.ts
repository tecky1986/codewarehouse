import { defineConfig } from "vitest/config";
import { readFileSync } from "node:fs";
import path from "node:path";
import vue from "@vitejs/plugin-vue";

const root = path.resolve(__dirname, "..");
const releaseMetaPath = path.join(root, "release_meta.json");
const fallbackReleaseMeta = { version: "dev", date: new Date().toISOString().slice(0, 10) };

function readReleaseMeta() {
  try {
    return JSON.parse(readFileSync(releaseMetaPath, "utf8")) as { version?: string; date?: string };
  } catch {
    return fallbackReleaseMeta;
  }
}

const releaseMeta = { ...fallbackReleaseMeta, ...readReleaseMeta() };

export default defineConfig({
  plugins: [vue()],
  define: {
    __RELEASE_META__: JSON.stringify(releaseMeta),
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    allowedHosts: [".monkeycode-ai.online"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "node",
  },
});
