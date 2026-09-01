// Unit + MCP-registration tests for the adaptive browser agent.
// Run:  cd web-ai-bridge/server && npm test   (node --test src/adaptive.test.js)
import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  parseAgentAction,
  pickBestModel,
  buildAgentPrompt,
  elementLine,
  wouldBeRiskyClick,
  normalizeKey,
  llmConfig,
} from "./adaptive.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SERVER_DIR = path.join(__dirname, "..");

test("parseAgentAction accepts each valid action", () => {
  assert.deepEqual(parseAgentAction('{"action":"click","target":3}'), { action: "click", target: 3 });
  assert.deepEqual(parseAgentAction('{"action":"type","target":1,"text":"salom"}'), {
    action: "type",
    target: 1,
    text: "salom",
  });
  assert.deepEqual(parseAgentAction('{"action":"select","target":2,"value":"uz"}'), {
    action: "select",
    target: 2,
    value: "uz",
  });
  assert.deepEqual(parseAgentAction('{"action":"scroll","direction":"down"}'), { action: "scroll", direction: "down" });
  assert.deepEqual(parseAgentAction('{"action":"navigate","url":"https://example.com"}'), {
    action: "navigate",
    url: "https://example.com",
  });
  assert.deepEqual(parseAgentAction('{"action":"press","key":"Enter"}'), { action: "press", key: "Enter" });
  assert.deepEqual(parseAgentAction('{"action":"wait"}'), { action: "wait" });
  assert.deepEqual(parseAgentAction('{"action":"back"}'), { action: "back" });
  assert.deepEqual(parseAgentAction('{"action":"done","answer":"Topildi!"}'), {
    action: "done",
    answer: "Topildi!",
  });
  assert.deepEqual(parseAgentAction('{"action":"fail","reason":"login kerak"}'), {
    action: "fail",
    reason: "login kerak",
  });
});

test("parseAgentAction tolerates fences and prose around the JSON", () => {
  assert.deepEqual(parseAgentAction('```json\n{"action":"click","target":7}\n```'), {
    action: "click",
    target: 7,
  });
  assert.deepEqual(
    parseAgentAction('Men shunday qilaman: {"action":"navigate","url":"https://example.com"} — shu!'),
    { action: "navigate", url: "https://example.com" }
  );
});

test("parseAgentAction rejects garbage and missing required fields", () => {
  assert.equal(parseAgentAction(""), null);
  assert.equal(parseAgentAction("salom dunyo"), null);
  assert.equal(parseAgentAction('{"action":"explode"}'), null);
  assert.equal(parseAgentAction('{"action":"click"}'), null); // target yo'q
  assert.equal(parseAgentAction('{"action":"click","target":"x"}'), null); // target raqam emas
  assert.equal(parseAgentAction('{"action":"done"}'), null); // answer yo'q
  assert.equal(parseAgentAction('{"action":"navigate","url":"example.com"}'), null); // http yo'q
  assert.equal(parseAgentAction('{"action":"type","target":1}'), null); // text yo'q
  assert.equal(parseAgentAction('{"action":"scroll"}'), null); // direction yo'q
  assert.equal(parseAgentAction('[1,2,3]'), null);
});

test("pickBestModel follows preference order with fallbacks", () => {
  assert.equal(pickBestModel(["qwen3:8b", "llama3.2:3b"]), "qwen3:8b");
  assert.equal(pickBestModel(["llama3.2:3b", "qwen2.5-coder:7b"]), "qwen2.5-coder:7b");
  assert.equal(pickBestModel(["llama3.2:3b"]), "llama3.2:3b");
  assert.equal(pickBestModel(["qwen3:30b-a3b", "llama3.1:8b"]), "qwen3:30b-a3b"); // istalgan qwen3 g'olib
  assert.equal(pickBestModel([]), null);
});

test("elementLine renders readable descriptors", () => {
  assert.equal(
    elementLine({ k: 4, tag: "button", role: "", text: "Qidirish", label: "", placeholder: "", value: "", href: "" }),
    '[k=4] <button> "Qidirish"'
  );
  assert.equal(
    elementLine({ k: 1, tag: "input", role: "textbox", text: "", label: "", placeholder: "Ismingiz", value: "", href: "" }),
    '[k=1] <input/textbox> placeholder="Ismingiz"'
  );
});

test("buildAgentPrompt embeds task, page text, elements and history", () => {
  const snap = {
    url: "https://example.com",
    title: "Example",
    headings: ["Mahsulotlar"],
    text: "Lorem ipsum",
    elements: [{ k: 0, tag: "a", role: "link", text: "Kirish", label: "", placeholder: "", value: "", href: "/login" }],
    truncated: false,
  };
  const prompt = buildAgentPrompt("Narxni top", snap, ["click k=0 -> ok"]);
  assert.ok(prompt.includes("VAZIFA: Narxni top"));
  assert.ok(prompt.includes("SAHIFA: https://example.com"));
  assert.ok(prompt.includes("Lorem ipsum"));
  assert.ok(prompt.includes("[k=0]"));
  assert.ok(prompt.includes("QILINGAN AMALLAR"));
  assert.ok(prompt.includes("click k=0"));
});

test("wouldBeRiskyClick refuses payment/deletion targets, not normal ones", () => {
  const elements = [
    { k: 0, tag: "button", text: "Buy Now", label: "", placeholder: "", value: "", href: "" },
    { k: 1, tag: "button", text: "Qo'shish", label: "", placeholder: "", value: "", href: "" },
    { k: 2, tag: "a", text: "", label: "Delete My Account", placeholder: "", value: "", href: "#" },
  ];
  assert.equal(wouldBeRiskyClick({ action: "click", target: 0 }, elements), true);
  assert.equal(wouldBeRiskyClick({ action: "click", target: 2 }, elements), true);
  assert.equal(wouldBeRiskyClick({ action: "click", target: 1 }, elements), false);
  assert.equal(wouldBeRiskyClick({ action: "type", target: 0, text: "x" }, elements), false); // click emas
  assert.equal(wouldBeRiskyClick({ action: "click", target: 99 }, elements), false); // element yo'q
});

test("normalizeKey maps LLM key names to Playwright casing", () => {
  assert.equal(normalizeKey("Enter"), "Enter");
  assert.equal(normalizeKey("enter"), "Enter");
  assert.equal(normalizeKey("escape"), "Escape");
  assert.equal(normalizeKey("ctrl+a"), "Control+A");
  assert.equal(normalizeKey("control+a"), "Control+A");
  assert.equal(normalizeKey("Shift+Tab"), "Shift+Tab");
  assert.equal(normalizeKey("arrowdown"), "ArrowDown");
  assert.equal(normalizeKey("a"), "A");
});

test("llmConfig defaults to local Ollama", () => {
  const cfg = llmConfig();
  assert.equal(cfg.baseUrl, "http://localhost:11434");
  assert.ok(cfg.stepTimeoutMs > 0);
});

test("MCP server exposes browser_ai_task tool (tools/list)", async () => {
  // CDP rejimini o'chirib ishga tushiramiz — real Chrome'ga yopishib qolmaslik
  const env = { ...process.env };
  for (const k of ["WAB_CDP_ENABLED", "WAB_CDP_URL", "WAB_CDP_PORT", "WAB_CHROME_USER_DATA", "WAB_CHROME_PROFILE"]) delete env[k];
  const server = spawn(process.execPath, ["src/index.js"], {
    cwd: SERVER_DIR,
    env,
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
        pending.get(msg.id)(msg);
        pending.delete(msg.id);
      }
    }
  });
  const rpc = (method, params) =>
    new Promise((resolve) => {
      const id = nextId++;
      pending.set(id, resolve);
      server.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
    });

  try {
    await rpc("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "adaptive-test", version: "1.0.0" },
    });
    const res = await rpc("tools/list", {});
    const names = (((res || {}).result || {}).tools || []).map((t) => t.name);
    assert.ok(names.includes("browser_ai_task"), `browser_ai_task not in: ${names.join(", ")}`);
  } finally {
    server.kill();
  }
});
