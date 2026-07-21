import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Tauri-specific dev server settings: fixed port (Tauri points its
// webview at this in dev), and it must NOT be cleared by Tauri's own
// output so errors from both sides stay visible in one terminal.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      ignored: ["**/src-tauri/target/**"],
    },
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    // Tauri v2 targets modern webviews (WebView2 on Windows); no need to
    // transpile down further, which keeps the bundle smaller.
    target: "es2021",
    outDir: "dist",
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
});
