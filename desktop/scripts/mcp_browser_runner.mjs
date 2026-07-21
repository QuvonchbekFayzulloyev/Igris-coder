import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

function argValue(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

function safeScreenshotName(value) {
  return String(value || "screenshot")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "screenshot";
}

function requireString(action, field) {
  if (typeof action[field] !== "string" || !action[field].trim()) {
    throw new Error(`action '${action.action}' requires non-empty '${field}'`);
  }
  return action[field];
}

async function check() {
  const browser = await chromium.launch({ headless: true });
  await browser.close();
  console.log(JSON.stringify({ ok: true, browser: "chromium", mode: "headless" }));
}

async function journey() {
  const url = argValue("--url");
  const outputDir = argValue("--out");
  const timeoutMs = Number(argValue("--timeout") || 45) * 1000;
  if (!url || !outputDir) throw new Error("--url and --out are required");
  const rawActions = argValue("--actions") || "[]";
  const actions = JSON.parse(rawActions);
  if (!Array.isArray(actions)) throw new Error("--actions must decode to an array");

  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(timeoutMs);
  const steps = [];
  const screenshots = [];
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: timeoutMs });
    steps.push({ action: "goto", ok: true, url: page.url() });
    for (let index = 0; index < actions.length; index += 1) {
      const action = actions[index];
      if (!action || typeof action !== "object") throw new Error(`action ${index} must be an object`);
      const type = action.action;
      switch (type) {
        case "click":
          await page.locator(requireString(action, "selector")).click();
          break;
        case "fill":
          await page.locator(requireString(action, "selector")).fill(requireString(action, "value"));
          break;
        case "press":
          await page.locator(requireString(action, "selector")).press(requireString(action, "key"));
          break;
        case "expect_visible":
          await page.locator(requireString(action, "selector")).waitFor({ state: "visible" });
          break;
        case "expect_text":
          await page.getByText(requireString(action, "text"), { exact: Boolean(action.exact) }).waitFor({ state: "visible" });
          break;
        case "expect_url":
          await page.waitForURL(requireString(action, "url"));
          break;
        case "wait_for":
          await page.waitForTimeout(Math.max(0, Math.min(Number(action.ms) || 0, 30_000)));
          break;
        case "screenshot": {
          const fileName = `${safeScreenshotName(action.name || `step-${index + 1}`)}.png`;
          await page.screenshot({ path: path.join(outputDir, fileName), fullPage: action.full_page !== false });
          screenshots.push(fileName);
          break;
        }
        default:
          throw new Error(`unsupported browser action '${type}'`);
      }
      steps.push({ action: type, ok: true });
    }
    const finalScreenshot = "final.png";
    await page.screenshot({ path: path.join(outputDir, finalScreenshot), fullPage: true });
    screenshots.push(finalScreenshot);
    const result = { ok: true, url: page.url(), title: await page.title(), steps, screenshots };
    await writeFile(path.join(outputDir, "result.json"), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
}

try {
  if (process.argv.includes("--check")) {
    await check();
  } else {
    await journey();
  }
} catch (error) {
  console.error(JSON.stringify({ ok: false, error: error instanceof Error ? error.message : String(error) }));
  process.exitCode = 1;
}
