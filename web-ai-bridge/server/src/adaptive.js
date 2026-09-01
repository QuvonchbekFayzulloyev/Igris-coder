/**
 * web-ai-bridge — Adaptive browser agent (browser_ai_task)
 * ========================================================
 * The deterministic tools (browser_click, browser_type, ...) are fast and
 * precise, but they depend on CSS selectors that break the moment a site
 * redesigns its UI. This module is the other half of the story: an
 * LLM-driven agent (browser-use-style) that re-reads the LIVE page every
 * step and chooses what to do from the elements it actually sees -- so
 * UI/UX changes don't stop it.
 *
 * Loop:
 *   snapshot page (elements by text/label, NOT by selector)
 *   -> ask local Ollama "what next?" (strict JSON action)
 *   -> execute ONE action via Playwright
 *   -> repeat until DONE / FAIL / step limit.
 *
 * Safety:
 *   - page text is sanitized (prompt-injection masking) before reaching the LLM
 *   - clicks on irreversible actions (payment/purchase/deletion/...) are refused
 *   - step limit + per-step LLM timeout so a bad model can't run forever
 *
 * The agent runs on whatever Page the caller hands it -- in CDP mode that is
 * the user's REAL Chrome with their REAL profile (logins/cookies already
 * there), exactly like every other tool in this server.
 */

import { RISKY_ACTION_PATTERN } from "./diagnostics.js";
import { sanitizeIfNeeded } from "./safety.js";

/** Every interactive element the agent can act on, in document order.
 *  Playwright's `locator.nth(k)` must target exactly the same element, so the
 *  in-page snapshot records `k` = position inside THIS full node list. */
export const INTERACTIVE_SELECTOR = [
  "a[href]",
  "button",
  "input:not([type='hidden'])",
  "textarea",
  "select",
  "summary",
  "[contenteditable='true']",
  "[contenteditable='']",
  "[role='button']",
  "[role='link']",
  "[role='menuitem']",
  "[role='tab']",
  "[role='checkbox']",
  "[role='radio']",
  "[role='option']",
  "[role='combobox']",
  "[role='searchbox']",
  "[role='textbox']",
].join(", ");

// Model preference order — Python (Igris_brain/llm/ollama_client.py) bilan
// BIR XIL, shunda ikkala qatlam ham bir xil modelni tanlaydi.
export const PREFERRED_MODELS = [
  "qwen3:8b",
  "qwen2.5-coder:7b",
  "qwen3:4b",
  "qwen2.5:7b",
  "qwen3:1.7b",
  "qwen2.5-coder:1.5b",
  "qwen2.5:3b",
  "qwen2.5:1.5b",
  "qwen3:0.6b",
];

export function llmConfig() {
  return {
    baseUrl: String(process.env.WAB_LLM_URL || "http://localhost:11434").replace(/\/+$/, ""),
    model: String(process.env.WAB_LLM_MODEL || "").trim() || null,
    stepTimeoutMs: Number(process.env.WAB_LLM_TIMEOUT_MS || 90000) || 90000,
  };
}

let _cachedModels = null;

/** Ollama /api/tags — model ro'yxati (protsess davomida bir marta). */
export async function listModels(baseUrl) {
  if (_cachedModels) return _cachedModels;
  let models = [];
  try {
    const res = await fetch(`${baseUrl}/api/tags`, { signal: AbortSignal.timeout(5000) });
    if (res.ok) {
      const data = await res.json();
      models = (data.models || []).map((m) => m.name || "").filter(Boolean);
    }
  } catch {
    models = [];
  }
  // Bo'sh natija KESHLANMAYDI — Ollama keyin ishga tushsa, keyingi chaqiriqda
  // qayta uriniladi (aks holda "model topilmadi" protsess oxirigacha tiqilib qoladi).
  if (models.length) _cachedModels = models;
  return models;
}

export function pickBestModel(available) {
  const avail = (available || []).filter(Boolean);
  if (!avail.length) return null;
  for (const m of PREFERRED_MODELS) if (avail.includes(m)) return m;
  for (const m of avail) if (m.startsWith("qwen3")) return m;
  for (const m of avail) if (m.startsWith("qwen2.5-coder")) return m;
  for (const m of avail) if (m.includes("qwen")) return m;
  return avail[0];
}

async function askAgent({ baseUrl, model, messages, timeoutMs }) {
  const res = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      messages,
      stream: false,
      // think=False — har qadamda 30-60s fikrlash kerak emas (tezlik).
      think: false,
      keep_alive: "30m",
      options: { temperature: 0.2, num_predict: 700, num_ctx: 8192 },
    }),
    signal: AbortSignal.timeout(timeoutMs || 90000),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Ollama HTTP ${res.status}: ${detail.slice(0, 160)}`);
  }
  const data = await res.json();
  return (data.message && data.message.content) || "";
}

// ---------------------------------------------------------------------- #
// DOM snapshot
// ---------------------------------------------------------------------- #

/** Jonli sahifani agent uchun soddalashtirilgan shaklda oladi.
 *  Elementlar `k` = INTERACTIVE_SELECTOR bo'yicha TO'LIQ ro'yxatdagi indeks
 *  (Playwright locator.nth(k) bilan mos). Sahifa matni LLM'ga borishdan
 *  oldin injection naqshlaridan tozalanadi. */
export async function collectSnapshot(page, opts = {}) {
  const maxElements = opts.maxElements || 60;
  const maxText = opts.maxText || 3000;

  const raw = await page.evaluate(
    ({ selector }) => {
      const nodes = Array.from(document.querySelectorAll(selector));
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        if (r.width <= 0 && r.height <= 0) return false;
        const cs = getComputedStyle(el);
        return cs.display !== "none" && cs.visibility !== "hidden";
      };
      return nodes.map((el, k) => {
        const tag = el.tagName.toLowerCase();
        const text = (el.textContent || "").replace(/\s+/g, " ").trim();
        return {
          k,
          tag,
          role: el.getAttribute("role") || "",
          text,
          label: el.getAttribute("aria-label") || "",
          placeholder: el.getAttribute("placeholder") || "",
          value: (el.value != null ? String(el.value) : "").replace(/\s+/g, " ").trim(),
          href: el.getAttribute("href") || "",
          disabled: el.disabled === true || el.getAttribute("aria-disabled") === "true",
          visible: visible(el),
        };
      });
    },
    { selector: INTERACTIVE_SELECTOR }
  );

  const usable = raw.filter((e) => e.visible && !e.disabled);
  const truncated = usable.length > maxElements;
  // LLM'ga boradigan HAR BIR sahifa-nazoratidagi maydon injection naqshlaridan
  // tozalanadi (sahifa matni + element matni/label/placeholder/href + title).
  const elements = usable.slice(0, maxElements).map((e) => ({
    ...e,
    text: sanitizeIfNeeded(e.text),
    label: sanitizeIfNeeded(e.label),
    placeholder: sanitizeIfNeeded(e.placeholder),
    value: sanitizeIfNeeded(e.value),
    href: sanitizeIfNeeded(e.href),
  }));

  let text = "";
  try {
    text = await page.evaluate(() => document.body.innerText || "");
  } catch {
    // sahifa javob bermayapti — matnsiz davom etamiz
  }
  text = sanitizeIfNeeded(String(text).replace(/\s+/g, " ").trim());
  if (text.length > maxText) text = text.slice(0, maxText) + "…";

  let headings = [];
  try {
    headings = await page.evaluate(() =>
      Array.from(document.querySelectorAll("h1,h2,h3"))
        .map((h) => (h.textContent || "").replace(/\s+/g, " ").trim().slice(0, 90))
        .filter(Boolean)
        .slice(0, 6)
    );
  } catch {
    headings = [];
  }

  return {
    url: page.url(),
    title: sanitizeIfNeeded(await page.title().catch(() => "")),
    headings: headings.map((h) => sanitizeIfNeeded(h)),
    text,
    elements,
    truncated,
  };
}

/** Bitta elementni agentga o'qiladigan qatorga aylantiradi. */
export function elementLine(e) {
  const bits = [];
  if (e.text) bits.push(`"${e.text.slice(0, 80)}"`);
  if (e.label) bits.push(`aria="${e.label.slice(0, 60)}"`);
  if (e.placeholder) bits.push(`placeholder="${e.placeholder.slice(0, 40)}"`);
  if (e.value) bits.push(`value="${e.value.slice(0, 40)}"`);
  if (e.href) bits.push(`href=${e.href.slice(0, 60)}`);
  const kind = [e.tag, e.role].filter(Boolean).join("/");
  return `[k=${e.k}] <${kind}> ${bits.join(" ")}`.trim();
}

// ---------------------------------------------------------------------- #
// LLM prompting + action protocol
// ---------------------------------------------------------------------- #

export const ACTION_SPEC = `KEYINGI amalni FAQAT bitta JSON ob'ekt sifatida qaytaring (boshqa matn YO'Q):
{"action":"click","target":<element raqami>}
{"action":"type","target":<raqam>,"text":"yoziladigan matn"}
{"action":"select","target":<raqam>,"value":"option qiymati"}
{"action":"scroll","direction":"down"}  (yoki "up")
{"action":"navigate","url":"https://..."}
{"action":"press","key":"Enter"}
{"action":"wait"}
{"action":"back"}
{"action":"done","answer":"vazifa yakuni / javob"}
{"action":"fail","reason":"nima uchun bajarib bo'lmadi"}`;

const SYSTEM_PROMPT = [
  "Siz adaptiv brauzer agentsiz. Sizga VAZIFA va sahifaning JONLI holati beriladi.",
  "UI qanday ko'rinishda bo'lishidan qat'iy nazar — elementlarni matni/label'i bo'yicha topib vazifani bajarasiz (qattiq selector'lar yo'q, o'zingiz tanlaysiz).",
  "Har qadamda FAQAT keyingi bitta amalni qaytarasiz. Amal bajarilgach sahifa yangilanib qaytariladi.",
  "",
  ACTION_SPEC,
  "",
  "QOIDALAR:",
  "- target raqami ELEMENTLAR ro'yxatidagi [k=...] qiymati bo'lsin.",
  "- XAVFSIZLIK: to'lov/sotib olish/hisobni o'chirish kabi qaytarib bo'lmaydigan tugmalarni (Buy Now, Place Order, Pay, Delete Account...) BOSMANG — ularni done/fail javobida tushuntiring.",
  "- done: vazifa bajarilganda, so'ralgan ma'lumot topilganda yoki to'xtash kerak bo'lganda. answer foydalanuvchi tilida bo'lsin.",
  "- fail: vazifani bajarib bo'lmasa — sababini yozing.",
  "- Faqat BIR JSON ob'ekt: kod bloki, tushuntirish, boshqa matn YO'Q.",
].join("\n");

export function buildAgentPrompt(task, snap, history = []) {
  const lines = [];
  lines.push(`VAZIFA: ${task}`);
  lines.push("");
  lines.push(`SAHIFA: ${snap.url}`);
  if (snap.title) lines.push(`SARLAVHA: ${snap.title}`);
  if (snap.headings && snap.headings.length) {
    lines.push("");
    lines.push("Sarlavhalar:");
    lines.push(snap.headings.map((h) => `- ${h}`).join("\n"));
  }
  if (snap.text) {
    lines.push("");
    lines.push("Sahifa matni (qisqartirilgan):");
    lines.push(snap.text.slice(0, 2500));
  }
  lines.push("");
  if (snap.elements && snap.elements.length) {
    lines.push("ELEMENTLAR:");
    lines.push(snap.elements.map(elementLine).join("\n"));
    if (snap.truncated) {
      lines.push(`(ro'yxat qisqartirildi — birinchi ${snap.elements.length} ko'rinadigan element)`);
    }
  } else {
    lines.push("ELEMENTLAR: (ko'rinadigan interaktiv element topilmadi)");
  }
  if (history && history.length) {
    lines.push("");
    lines.push("QILINGAN AMALLAR:");
    lines.push(history.slice(-10).map((h, i) => `${i + 1}. ${h}`).join("\n"));
  }
  lines.push("");
  lines.push("Keyingi amal (JSON):");
  return lines.join("\n");
}

const VALID_ACTIONS = ["click", "type", "select", "scroll", "navigate", "press", "wait", "back", "done", "fail"];

/** LLM chiqishini bitta amalga aylantiradi; noto'g'ri bo'lsa null. */
export function parseAgentAction(text) {
  if (!text) return null;
  const cleaned = String(text).trim();
  let raw = cleaned;
  const fence = cleaned.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fence) raw = fence[1].trim();
  let obj;
  try {
    obj = JSON.parse(raw);
  } catch {
    const m = raw.match(/\{[\s\S]*\}/);
    if (!m) return null;
    try {
      obj = JSON.parse(m[0]);
    } catch {
      return null;
    }
  }
  if (!obj || typeof obj !== "object") return null;
  const action = String(obj.action || "").trim();
  if (!VALID_ACTIONS.includes(action)) return null;

  const a = { action };
  if (action === "click") {
    if (!Number.isInteger(obj.target)) return null;
    a.target = obj.target;
  } else if (action === "type") {
    if (!Number.isInteger(obj.target) || typeof obj.text !== "string" || !obj.text.trim()) return null;
    a.target = obj.target;
    a.text = obj.text.slice(0, 2000);
  } else if (action === "select") {
    if (!Number.isInteger(obj.target) || typeof obj.value !== "string" || !obj.value.trim()) return null;
    a.target = obj.target;
    a.value = obj.value.slice(0, 200);
  } else if (action === "scroll") {
    if (!["down", "up"].includes(obj.direction)) return null;
    a.direction = obj.direction;
  } else if (action === "navigate") {
    if (typeof obj.url !== "string" || !/^https?:\/\//i.test(obj.url.trim())) return null;
    a.url = obj.url.trim().slice(0, 2048);
  } else if (action === "press") {
    if (typeof obj.key !== "string" || !obj.key.trim()) return null;
    a.key = obj.key.trim().slice(0, 32);
  } else if (action === "done") {
    if (typeof obj.answer !== "string" || !obj.answer.trim()) return null;
    a.answer = obj.answer.trim();
  } else if (action === "fail") {
    a.reason = typeof obj.reason === "string" ? obj.reason.trim().slice(0, 500) : "";
  }
  return a;
}

/** LLM chiqishidagi klaviatura nomini Playwright kutgan shaklga keltiradi
 *  ('enter' -> 'Enter', 'ctrl+a'/'control+a' -> 'Control+A'). */
export function normalizeKey(key) {
  const map = {
    enter: "Enter", escape: "Escape", tab: "Tab", backspace: "Backspace",
    delete: "Delete", space: "Space", capslock: "CapsLock",
    arrowup: "ArrowUp", arrowdown: "ArrowDown", arrowleft: "ArrowLeft", arrowright: "ArrowRight",
    home: "Home", end: "End", pageup: "PageUp", pagedown: "PageDown",
    control: "Control", ctrl: "Control", shift: "Shift", alt: "Alt", meta: "Meta",
  };
  return String(key || "")
    .split("+")
    .map((p) => {
      const l = p.trim().toLowerCase();
      if (map[l]) return map[l];
      if (l.length === 1) return p.trim().toUpperCase();
      return p.trim();
    })
    .join("+");
}

/** Click xavfli (to'lov/sotib olish/hisob o'chirish) tugmaga tegadimi? */
export function wouldBeRiskyClick(action, elements) {
  if (!action || action.action !== "click") return false;
  const el = (elements || []).find((e) => e.k === action.target);
  if (!el) return false;
  return RISKY_ACTION_PATTERN.test(`${el.text} ${el.label}`);
}

// ---------------------------------------------------------------------- #
// Agent loop
// ---------------------------------------------------------------------- #

async function agentTypeInto(locator, text) {
  // fill() — <input>/<textarea>/contenteditable uchun; per-key React
  // hodisalari talab qiladigan muharrirlarda real tugmalar (index.js bilan
  // bir xil zaxira yo'li).
  try {
    await locator.fill(text, { timeout: 5000 });
    return;
  } catch {
    // yozilmay qoldi — bosib, tugmalar bilan yozamiz
  }
  await locator.click({ timeout: 5000 }).catch(() => {});
  await locator.pressSequentially(text, { delay: 12, timeout: 30000 });
}

async function askForAction(cfg, model, prompt, nudge) {
  const messages = [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: nudge ? `${prompt}\n\nEslatma: ${nudge}` : prompt },
  ];
  const raw = await askAgent({ baseUrl: cfg.baseUrl, model, messages, timeoutMs: cfg.stepTimeoutMs });
  const action = parseAgentAction(raw);
  return { raw, action };
}

/**
 * Adaptiv vazifa siklini boshqaradi (page allaqachon ochilgan bo'lishi kerak).
 * Qaytadi: { status: 'done'|'failed'|'limit', answer, steps, log }
 */
export async function runAdaptiveTask(page, opts = {}) {
  const task = String(opts.task || "").trim();
  if (!task) throw new Error("browser_ai_task: task bo'sh bo'lishi mumkin emas.");
  const maxSteps = Math.min(Math.max(Number(opts.maxSteps) || 12, 1), 25);
  const cfg = opts.llm || llmConfig();

  let model = cfg.model;
  if (!model) {
    model = pickBestModel(await listModels(cfg.baseUrl));
    if (!model) {
      throw new Error(
        "Ollama'dan hech qanday model topilmadi. `ollama pull qwen3:8b` bilan " +
          "o'rnating yoki WAB_LLM_MODEL muhit o'zgaruvchisini sozlang."
      );
    }
  }

  const log = [];
  const history = [];
  let status = "limit";
  let answer = "";

  for (let step = 1; step <= maxSteps; step++) {
    const snap = await collectSnapshot(page, opts.snapshot || {});
    const prompt = buildAgentPrompt(task, snap, history);

    let action = null;
    try {
      const first = await askForAction(cfg, model, prompt, null);
      action = first.action;
      if (!action) {
        // noto'g'ri format — bitta yumshoq qayta urinish
        const retry = await askForAction(
          cfg, model, prompt,
          "Siz JSON formatda javob bermadingiz. Faqat bitta JSON ob'ekt qaytaring."
        );
        action = retry.action;
      }
    } catch (err) {
      if (step > 1) {
        status = "failed";
        answer = `Qadam ${step}: Ollama xatosi — ${err.message}`;
        break;
      }
      throw err; // birinchi qadamdagi xato — darhol chaqiruvchiga
    }

    if (!action) {
      status = "failed";
      answer = "Model ikki marta ham noto'g'ri formatda javob berdi (JSON emas).";
      break;
    }

    // ---- yakuniy amallar ----
    if (action.action === "done") {
      status = "done";
      answer = action.answer;
      log.push(`  ${step}. done: ${action.answer.slice(0, 120)}`);
      break;
    }
    if (action.action === "fail") {
      status = "failed";
      answer = action.reason;
      log.push(`  ${step}. fail: ${action.reason.slice(0, 120)}`);
      break;
    }

    // ---- target tekshiruvi ----
    if (action.target != null && !snap.elements.some((e) => e.k === action.target)) {
      history.push(`${action.action}[k=${action.target}] -> invalid target (element yo'q)`);
      log.push(`  ${step}. ${action.action}[k=${action.target}] -> invalid target`);
      await page.waitForTimeout(400);
      continue;
    }

    // ---- xavfsizlik: xavfli click rad etiladi ----
    if (wouldBeRiskyClick(action, snap.elements)) {
      history.push(`click[k=${action.target}] -> refused (xavfli: to'lov/sotib olish/hisob o'chirish)`);
      log.push(`  ${step}. click[k=${action.target}] -> REFUSED (xavfli tugma)`);
      await page.waitForTimeout(400);
      continue;
    }

    // ---- bajarish ----
    const loc = action.target != null ? page.locator(INTERACTIVE_SELECTOR).nth(action.target) : null;
    const label = snap.elements.find((e) => e.k === action.target);
    const targetDesc = label ? elementLine(label).slice(0, 70) : "";
    try {
      // TOCTOU xavfsizlik qatlami: snapshot va amal o'rtasida DOM o'zgargan
      // bo'lishi mumkin — click'ni bajarishdan OLDIN jonli elementning
      // matnini qayta o'qib, xavfli tugma ekanini yana tekshiramiz.
      if (action.action === "click" && loc) {
        const liveText = await loc.evaluate((el) => {
          return `${el.textContent || ""} ${el.getAttribute("aria-label") || ""}`;
        }).catch(() => "");
        if (RISKY_ACTION_PATTERN.test(sanitizeIfNeeded(String(liveText).replace(/\s+/g, " ").trim()))) {
          history.push(`click[k=${action.target}] -> refused (xavfli tugma, jonli tekshiruv)`);
          log.push(`  ${step}. click[k=${action.target}] -> REFUSED (xavfli tugma, jonli tekshiruv)`);
          await page.waitForTimeout(400);
          continue;
        }
      }
      switch (action.action) {
        case "click":
          await loc.click({ timeout: 8000 });
          break;
        case "type":
          await agentTypeInto(loc, action.text);
          break;
        case "select":
          await loc.selectOption(action.value, { timeout: 8000 });
          break;
        case "scroll":
          // mouse.wheel joriy kursor holatiga bog'liq — sahifa qayerda
          // turganidan qat'i nazar scroll ishlashi uchun JS bilan scroll qilamiz.
          await page.evaluate((dy) => window.scrollBy(0, dy), action.direction === "up" ? -700 : 700);
          break;
        case "navigate":
          await page.goto(action.url, { waitUntil: "domcontentloaded", timeout: 30000 });
          break;
        case "press":
          await page.keyboard.press(normalizeKey(action.key));
          break;
        case "wait":
          await page.waitForTimeout(1200);
          break;
        case "back":
          await page.goBack({ waitUntil: "domcontentloaded", timeout: 30000 }).catch(() => {});
          break;
      }
      history.push(
        action.action === "type"
          ? `${action.action}[k=${action.target}] "${action.text.slice(0, 50)}" -> ok`
          : `${action.action}[k=${action.target}]${targetDesc ? ` (${targetDesc})` : ""} -> ok`
      );
      log.push(`  ${step}. ${action.action}${action.target != null ? `[k=${action.target}]` : ""} -> ok`);
    } catch (err) {
      history.push(`${action.action}[k=${action.target}] -> error: ${String(err.message || err).slice(0, 80)}`);
      log.push(`  ${step}. ${action.action}[k=${action.target}] -> ERROR: ${String(err.message || err).slice(0, 100)}`);
    }
    await page.waitForTimeout(400); // DOM joylashishi uchun
  }

  if (status === "limit") {
    answer = `Vazifa ${maxSteps} qadam ichida tugamadi (qadam chegarasi). Qolgan ishni deterministik tool'lar bilan davom ettiring yoki vazifani kichikroq qismlarga bo'ling.`;
  }
  return { status, answer, steps: log.length, log };
}
