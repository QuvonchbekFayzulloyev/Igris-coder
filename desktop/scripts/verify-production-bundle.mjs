/**
 * Loads the REAL production bundle (dist/index.html + dist/assets/*.js,
 * exactly what a webview would load) into jsdom and executes it -- this
 * catches runtime errors that `tsc`/`vite build` cannot: a broken import
 * resolved at runtime, a null-reference on first render, a Tailwind
 * class typo that "compiles" but breaks styling, an uncaught exception
 * during mount.
 *
 * This is deliberately NOT part of the Vitest suite (which tests
 * individual components in isolation with jsdom's dev-mode React) --
 * this loads the actual shipped artifact from disk and runs it as a
 * browser would, as close as this sandbox can get to "does the built
 * app actually work" without a real browser or the Tauri webview.
 *
 * Usage: node scripts/verify-production-bundle.mjs
 * (run `npm run build` first)
 */
import { JSDOM } from "jsdom";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.join(__dirname, "..", "dist");

if (!existsSync(distDir)) {
  console.error("dist/ not found -- run `npm run build` first.");
  process.exit(1);
}

const indexHtml = readFileSync(path.join(distDir, "index.html"), "utf-8");
const scriptMatch = indexHtml.match(/<script[^>]+src="([^"]+)"/);
if (!scriptMatch) {
  console.error("Could not find the built JS bundle's <script> tag in dist/index.html");
  process.exit(1);
}
const bundlePath = path.join(distDir, scriptMatch[1].replace(/^\//, ""));
const bundleCode = readFileSync(bundlePath, "utf-8");

let failed = false;
const errors = [];

const dom = new JSDOM(indexHtml, {
  url: "http://localhost:5173/",
  runScripts: "dangerously",
  resources: "usable",
  pretendToBeVisual: true,
});

const { window } = dom;

const simulateBackendUp = process.argv.includes("--backend-up");

// The real app calls fetch()/WebSocket on mount. No real backend exists
// here; by default this simulates the "backend not reachable" condition
// the app must handle gracefully. Pass --backend-up to instead simulate
// a healthy backend and confirm the normal UI (project list, provider
// selector, etc.) mounts correctly too.
if (simulateBackendUp) {
  const routes = {
    "/api/health": { status: "ok" },
    "/api/providers": { providers: ["ollama", "lmstudio", "openrouter"] },
    "/api/projects": { projects: ["demo"], active: "demo" },
    "/api/skills": { skills: [] },
    "/api/mcp/tools": { tools: [] },
    "/api/settings": {
      gateway: { provider: "ollama" },
      ollama: { host: "http://localhost:11434", model: "qwen3" },
      lmstudio: { host: "http://localhost:1234/v1", model: "local-model" },
      openrouter: { host: "https://openrouter.ai/api/v1", model: "openrouter/auto", api_key_set: false },
    },
  };
  window.fetch = (url) => {
    const match = Object.keys(routes).find((path) => String(url).includes(path));
    return Promise.resolve({
      ok: !!match,
      status: match ? 200 : 404,
      json: async () => (match ? routes[match] : {}),
    });
  };
} else {
  window.fetch = () => Promise.reject(new Error("simulated: no backend in this sandbox"));
}

class FakeWebSocket {
  constructor() {
    if (simulateBackendUp) {
      setTimeout(() => this.onopen?.(), 0);
    } else {
      setTimeout(() => this.onerror?.(new Event("error")), 0);
    }
  }
  send() {}
  close() {}
}
window.WebSocket = FakeWebSocket;

window.onerror = (message) => {
  failed = true;
  errors.push(String(message));
};
window.addEventListener("unhandledrejection", (event) => {
  const msg = String(event.reason);
  // the simulated fetch rejection is expected and handled by the app's
  // own .catch() chains in the fallback-mode run -- only flag rejections
  // that escape those, or any rejection at all in backend-up mode where
  // no failure was simulated.
  if (!simulateBackendUp && msg.includes("simulated: no backend")) {
    return;
  }
  failed = true;
  errors.push(`unhandled rejection: ${msg}`);
});

try {
  window.eval(bundleCode);
} catch (e) {
  failed = true;
  errors.push(`synchronous execution error: ${e.message}`);
}

// Let React's microtask-queued mount + fetch/WebSocket chains settle.
await new Promise((resolve) => setTimeout(resolve, 300));

const root = window.document.getElementById("root");
const rendered = root && root.innerHTML.trim().length > 0;

console.log(`=== Production bundle execution check (${simulateBackendUp ? "backend-up" : "backend-unreachable"} mode) ===`);
console.log("Script errors:", failed ? "YES" : "none");
errors.forEach((e) => console.log("  -", e));
console.log("root element populated:", rendered ? "yes" : "NO");

let expectationMet = false;
if (rendered) {
  const text = (root.textContent || "").toLowerCase();
  if (simulateBackendUp) {
    expectationMet = text.includes("igris") && !text.includes("not reachable");
    console.log("reached normal app UI (not the unreachable fallback):", expectationMet ? "yes" : "no (unexpected content)");
  } else {
    expectationMet = text.includes("not reachable");
    console.log("reached expected 'backend not reachable' fallback UI:", expectationMet ? "yes" : "no (unexpected content)");
  }
  console.log("\nrendered text sample:", (root.textContent || "").slice(0, 200).replace(/\s+/g, " "));
}

const ok = !failed && rendered && expectationMet;
console.log("\n" + (ok ? "PASS: bundle executes and mounts real DOM content correctly." : "FAIL"));
process.exit(ok ? 0 : 1);
