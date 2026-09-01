// E2E driver — drives the web-ai-bridge MCP server (real Chrome) over raw
// JSON-RPC/stdio (no SDK dependency) to verify the "live build in chat"
// feature at http://localhost:1420.
// Run:  cd web-ai-bridge/server && node e2e-driver.mjs
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOTS_DIR = path.join(__dirname, "..", "e2e-shots");
fs.mkdirSync(SHOTS_DIR, { recursive: true });

// ---------------------------------------------------------------- //
// Minimal JSON-RPC client over stdio
// ---------------------------------------------------------------- //
// The driver exercises the legacy (self-launched browser) path on purpose, so
// it must NOT inherit CDP mode from the environment — otherwise it would attach
// to a real Chrome and behave differently.
const _env = { ...process.env, WAB_HEADLESS: "true" };
for (const k of ["WAB_CDP_ENABLED", "WAB_CDP_URL", "WAB_CDP_PORT", "WAB_CHROME_USER_DATA", "WAB_CHROME_PROFILE", "WAB_CHROME_EXECUTABLE"]) delete _env[k];
const server = spawn(process.execPath, ["src/index.js"], {
  cwd: __dirname,
  env: _env,
  stdio: ["pipe", "pipe", "inherit"],
});

let buf = "";
const pending = new Map();
let nextId = 1;

server.stdout.on("data", (chunk) => {
  buf += chunk.toString("utf8");
  let idx;
  while ((idx = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, idx).trim();
    buf = buf.slice(idx + 1);
    if (!line) continue;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      continue;
    }
    if (msg.id !== undefined && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message || "RPC error")) : resolve(msg.result);
    }
  }
});
server.on("exit", (code) => {
  console.log(`⚠ bridge process exited (code ${code})`);
  for (const [, { reject }] of pending) reject(new Error("bridge exited"));
  pending.clear();
});

async function rpc(method, params = {}) {
  const id = nextId++;
  const p = new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
  server.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  return p;
}

let shots = 0;
async function call(name, args = {}) {
  const res = await rpc("tools/call", { name, arguments: args });
  const out = { text: "", images: [], isError: false };
  for (const c of (res && res.content) || []) {
    if (c.type === "text") out.text += c.text + "\n";
    else if (c.type === "image") out.images.push(c.data);
  }
  out.text = out.text.trim();
  out.isError = !!(res && res.isError);
  return out;
}

async function shot(tag) {
  const r = await call("browser_screenshot", { full_page: true });
  for (const data of r.images) {
    shots += 1;
    const file = path.join(SHOTS_DIR, `${String(shots).padStart(2, "0")}-${tag}.png`);
    fs.writeFileSync(file, Buffer.from(data, "base64"));
    console.log(`📸 ${file}`);
  }
}

function section(title) {
  console.log(`\n===== ${title} =====`);
}

async function main() {
  // handshake
  await rpc("initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "e2e-driver", version: "1.0.0" },
  });
  await rpc("notifications/initialized", {}).catch(() => {});

  section("browser_info");
  console.log((await call("browser_info")).text);

  section("navigate to app");
  console.log((await call("browser_navigate", { url: "http://localhost:1420" })).text);

  section("wait for workspace tree (backend-loaded files)");
  const treeWait = await call("browser_wait_for", { text_contains: "house.svg", timeout_ms: 20000 });
  console.log(treeWait.isError ? `⚠ ${treeWait.text}` : treeWait.text);

  section("page text (initial chat view)");
  const t0 = await call("browser_get_text");
  console.log(t0.text.slice(0, 1100));

  section("click house.svg -> Preview live build");
  console.log((await call("browser_click", { selector: "text=house.svg" })).text);
  await call("browser_wait_for", { timeout_ms: 4000 });
  const t1 = await call("browser_get_text");
  console.log("--- preview view text ---");
  const hits = t1.text.split("\n").filter((l) => /BUILD|elements|%|LIVE|house/i.test(l));
  console.log(hits.length ? hits.join("\n") : t1.text.slice(0, 800));
  await shot("preview-house-build");

  section("back to Chat tab");
  console.log((await call("browser_click", { selector: "text=Chat" })).text);

  section("submit drawing task (⚡)");
  const task =
    "⚡ Tezkor vazifa: write_file tool bilan agent_workspace ichida chat_house2.svg fayl yarat. Kontent kichik SVG bo'lsin: ko'k doira, qizil kvadrat va yashil uchburchak (3 element). Boshqa hech narsa qilma.";
  // fill only first (no submit) so React commits the input before Enter fires
  const typed = await call("browser_type", { selector: "textarea", text: task, submit: false });
  console.log(typed.isError ? `⚠ ${typed.text}` : typed.text);
  await call("browser_wait_for", { timeout_ms: 700 });
  const tv = await call("browser_get_text", { selector: "textarea" });
  console.log("textarea content:", JSON.stringify(tv.text.slice(0, 100)));
  const press = await call("browser_press_key", { key: "Enter", selector: "textarea" });
  console.log(press.isError ? `⚠ ${press.text}` : press.text);
  await call("browser_wait_for", { timeout_ms: 2000 });
  const tSub = await call("browser_get_text");
  console.log("--- chat after submit (tail) ---");
  console.log(tSub.text.slice(-500));

  section("wait for run to finish + LIVE BUILD card (agent run may take minutes)");
  const startTime = Date.now();
  const deadline = startTime + 480000;
  let verdict = "timeout";
  while (Date.now() < deadline) {
    await call("browser_wait_for", { timeout_ms: 15000 });
    const t = await call("browser_get_text");
    if (t.text.includes("LIVE BUILD")) { verdict = "live-build"; break; }
    if (t.text.includes("✗ ERROR")) { verdict = "error"; break; }
    const tail = t.text.slice(-150).replace(/\n+/g, " | ");
    console.log(`  [${Math.round((Date.now() - startTime) / 1000)}s] ${tail.slice(-130)}`);
  }
  console.log(`✓ verdict: ${verdict}`);

  if (verdict === "timeout" || verdict === "error") {
    section("FAILED — dumping current chat text");
    const tf = await call("browser_get_text");
    console.log(tf.text.slice(0, 2200));
    await shot("fail-state");
  } else {
    const t2 = await call("browser_get_text");
    console.log("--- chat text around the live build card ---");
    console.log(t2.text.slice(-1800));
    await shot("chat-live-build-card");
    await call("browser_wait_for", { timeout_ms: 3500 });
    const t3 = await call("browser_get_text");
    console.log("--- 3.5s later (should show advancing element counter) ---");
    console.log(t3.text.slice(-1800));
    await shot("chat-live-build-advanced");

    section("safe-freeze pause + edit panel");
    const freeze = await call("browser_click", { selector: 'button[title*="Safe freeze"]' });
    console.log(freeze.isError ? `⚠ ${freeze.text}` : freeze.text);
    await call("browser_wait_for", { timeout_ms: 800 });
    const t4 = await call("browser_get_text");
    console.log("--- after freeze ---");
    console.log(t4.text.includes("SAFE FREEZE") ? "✓ SAFE FREEZE panel visible" : t4.text.slice(-900));
    await shot("chat-safe-freeze-panel");
  }
}

main()
  .then(async () => {
    await call("browser_close").catch(() => {});
    server.kill();
    console.log("\nDone.");
  })
  .catch((err) => {
    console.log(`\n✗ DRIVER ERROR: ${err && err.message ? err.message : err}`);
    try {
      server.kill();
    } catch {}
  });
