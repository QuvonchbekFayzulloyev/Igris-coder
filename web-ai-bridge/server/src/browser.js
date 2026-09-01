import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

let browser = null;    // Browser instance (launched persistent OR CDP-connected)
let context = null;
let pages = [];       // every open tab, in the order Playwright reports them
let activeIndex = -1; // which tab tool calls act on by default
let downloads = [];   // { url, filename, path, bytes, at, error? }

function dataDir() {
  return process.env.WAB_DATA_DIR || path.join(__dirname, "..", "..", ".data");
}

export function profileDir() {
  const explicit = process.env.WAB_PROFILE_DIR;
  if (explicit && explicit.trim()) return explicit.trim();
  return path.join(dataDir(), "browser-profile");
}

function downloadsDir() {
  return path.join(dataDir(), "downloads");
}

export function isHeadless() {
  // userConfig booleans arrive as the strings "true"/"false" via env substitution.
  return String(process.env.WAB_HEADLESS).toLowerCase() === "true";
}

// ---------------------------------------------------------------------- #
// CDP mode — the user's REAL Chrome with their REAL profile (mr.wtin).
//
// Instead of Playwright launching its own Chromium (or a dedicated empty
// automation profile), we attach to a real Google Chrome that is running
// with `--remote-debugging-port`. That Chrome uses the user's everyday
// profile (e.g. mr.wtin = "Profile 1"), so every login, cookie and session
// is already there — no re-logging-in, no fresh-profile CAPTCHAs.
//
//   WAB_CDP_ENABLED=true        turn CDP mode on (default: off)
//   WAB_CDP_URL=http://127.0.0.1:9222   where Chrome is listening
//   WAB_CDP_PORT=9222           port to launch Chrome on if not running
//   WAB_CHROME_USER_DATA=...    "User Data" dir of the real Chrome
//   WAB_CHROME_PROFILE="Profile 1"      which profile (mr.wtin)
//   WAB_CHROME_EXECUTABLE=...   chrome.exe path (auto-detected if unset)
//
// If the endpoint isn't up yet and WAB_CHROME_USER_DATA is set, we launch
// real Chrome ourselves with the debugging port + profile, wait for the
// endpoint, then connect. Chrome stays open afterwards — the bridge only
// ever disconnects, never kills your browser.
// ---------------------------------------------------------------------- #

export function cdpEnabled() {
  return (
    String(process.env.WAB_CDP_ENABLED).toLowerCase() === "true" ||
    !!String(process.env.WAB_CDP_URL || "").trim()
  );
}

export function cdpUrl() {
  return String(process.env.WAB_CDP_URL || "").trim() || "http://127.0.0.1:9222";
}

/** Real-Chrome launch spec for CDP mode, or null if not configured. */
export function chromeLaunchSpec() {
  const spec = {
    executable: String(process.env.WAB_CHROME_EXECUTABLE || "").trim(),
    userDataDir: String(process.env.WAB_CHROME_USER_DATA || "").trim(),
    profileDir: String(process.env.WAB_CHROME_PROFILE || "").trim(),
    port: Number(process.env.WAB_CDP_PORT || 9222) || 9222,
  };
  return spec.userDataDir ? spec : null;
}

function findChromeExecutable() {
  const env = process.env;
  const candidates = [
    process.env.WAB_CHROME_EXECUTABLE,
    env.PROGRAMFILES && path.join(env.PROGRAMFILES, "Google", "Chrome", "Application", "chrome.exe"),
    env["PROGRAMFILES(X86)"] && path.join(env["PROGRAMFILES(X86)"], "Google", "Chrome", "Application", "chrome.exe"),
    env.LOCALAPPDATA && path.join(env.LOCALAPPDATA, "Google", "Chrome", "Application", "chrome.exe"),
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ].filter(Boolean);
  return candidates.find((c) => fs.existsSync(c)) || null;
}

function defaultChromeDataDir() {
  const env = process.env;
  if (process.platform === "win32" && env.LOCALAPPDATA) {
    return path.join(env.LOCALAPPDATA, "Google", "Chrome", "User Data");
  }
  if (process.platform === "darwin") {
    return path.join(env.HOME || "", "Library", "Application Support", "Google", "Chrome");
  }
  return path.join(env.HOME || "", ".config", "google-chrome");
}

function isSameDir(a, b) {
  try {
    return path.resolve(a).toLowerCase() === path.resolve(b).toLowerCase();
  } catch {
    return false;
  }
}

/** Chrome 136+ refuses --remote-debugging-port when --user-data-dir is the
 *  DEFAULT Chrome data directory. To drive the user's real profile (mr.wtin)
 *  we create a junction/symlink to it at a NON-default path
 *  (<siblings>/Chrome-IGRIS-CDP) and point Chrome there instead: the debug
 *  port is allowed, and the real profile stays live — cookies/writes pass
 *  straight through the link. */
export function cdpUserDataDir(spec) {
  const ud = path.resolve(spec.userDataDir);
  const def = defaultChromeDataDir();
  if (!def || !isSameDir(ud, def)) return ud;

  // Sibling of the real "User Data" dir, e.g. ...\Google\Chrome-IGRIS-CDP
  const junction = path.join(path.dirname(path.dirname(ud)), "Chrome-IGRIS-CDP");
  try {
    const st = fs.lstatSync(junction);
    if (st.isSymbolicLink()) {
      // Verify the link actually points at the configured profile dir — a stale
      // or manually-created link to some other folder would silently drive the
      // wrong profile.
      const target = fs.realpathSync(junction);
      if (isSameDir(target, fs.realpathSync(ud))) return junction;
      throw new Error(
        `${junction} already exists but points at ${target}, not ${ud}. Remove it ` +
          `(or fix WAB_CHROME_USER_DATA) so the bridge can create its own link.`
      );
    }
    throw new Error(
      `Path ${junction} already exists and is not a link to ${ud}. Remove it ` +
        `(or use a different WAB_CHROME_USER_DATA) so the bridge can create its own link.`
    );
  } catch (err) {
    if (err.code !== "ENOENT") throw err;
  }
  try {
    fs.symlinkSync(ud, junction, process.platform === "win32" ? "junction" : "dir");
  } catch (err) {
    throw new Error(`Could not create link ${junction} -> ${ud}: ${err.message}`);
  }
  return junction;
}

/** Launch real Chrome with the remote-debugging port and the user's real
 *  profile, then wait until the CDP endpoint responds. Detached + unref'd:
 *  Chrome keeps running after the bridge process exits; the bridge never
 *  owns/kills it. */
async function launchChromeForCdp(spec) {
  const exe = spec.executable || findChromeExecutable();
  if (!exe || !fs.existsSync(exe)) {
    throw new Error(
      `Chrome executable not found. Install Google Chrome, or set WAB_CHROME_EXECUTABLE ` +
        `to the full path of chrome.exe.`
    );
  }
  const dataDir = cdpUserDataDir(spec);
  const args = [
    `--remote-debugging-port=${spec.port}`,
    `--user-data-dir=${dataDir}`,
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--start-maximized",
  ];
  if (spec.profileDir) args.push(`--profile-directory=${spec.profileDir}`);

  const child = spawn(exe, args, { detached: true, stdio: "ignore" });
  child.unref();
  child.on("error", (err) => console.error(`[web-ai-bridge] chrome launch error: ${err.message}`));

  // If the profile is already open, the freshly spawned Chrome hands off to the
  // existing instance and exits within a second or two — fail fast instead of
  // polling until the timeout.
  let handedOff = false;
  child.on("exit", (code) => {
    if (code !== 0) handedOff = true;
  });

  // Wait for the debugging endpoint to come up (Chrome takes a second or two).
  // Kept well under the brain server's 30s MCP initialize timeout.
  const deadline = Date.now() + 15000;
  const endpoint = cdpUrl();
  for (;;) {
    if (handedOff) {
      throw new Error(
        `Chrome started then exited immediately (handed off to an already-running ` +
          `instance with this profile). Close ALL its windows first (Chrome allows ` +
          `only one instance per profile), then retry.`
      );
    }
    try {
      const res = await fetch(`${endpoint}/json/version`);
      if (res.ok) return;
    } catch {
      // not up yet — retry
    }
    if (Date.now() > deadline) {
      throw new Error(
        `Started Chrome with --remote-debugging-port=${spec.port} but its CDP endpoint ` +
          `at ${endpoint} never came up. If Chrome is already open with this profile, ` +
          `close ALL its windows first (Chrome allows only one instance per profile), ` +
          `then retry.`
      );
    }
    await new Promise((r) => setTimeout(r, 500));
  }
}

let launchInfo = { channel: null, fellBack: false, fallbackReason: null, mode: "launch" };

export function getLaunchInfo() {
  const base = { ...launchInfo };
  if (cdpEnabled()) {
    base.mode = "cdp";
    base.cdpUrl = cdpUrl();
    base.chromeProfile = String(process.env.WAB_CHROME_PROFILE || "").trim() || null;
    base.chromeUserData = String(process.env.WAB_CHROME_USER_DATA || "").trim() || null;
    const spec = chromeLaunchSpec();
    if (spec) base.dataDir = cdpUserDataDir(spec);
  }
  return base;
}

function wireContextEvents(ctx) {
  // A human clicking a link that opens "in a new tab" ends up with a tab they
  // didn't explicitly ask for -- track those too instead of losing them.
  ctx.on("page", (p) => {
    if (!pages.includes(p)) pages.push(p);
  });

  // A human clicking a link to a file sees a download, not a new page.
  // Save it somewhere real and record what happened so tool calls can report
  // "this was a file" instead of surfacing a confusing navigation error.
  ctx.on("download", async (download) => {
    const suggested = download.suggestedFilename();
    const entry = { url: download.url(), filename: suggested, at: Date.now() };
    try {
      fs.mkdirSync(downloadsDir(), { recursive: true });
      const dest = path.join(downloadsDir(), `${Date.now()}_${suggested}`);
      await download.saveAs(dest);
      entry.path = dest;
      entry.bytes = fs.statSync(dest).size;
    } catch (err) {
      entry.error = String(err && err.message ? err.message : err);
    }
    downloads.push(entry);
  });
}

/** Connect to an already-running real Chrome (or launch it) and use the
 *  profile's own persistent context — cookies/logins are the real ones. */
async function ensureCdpContext() {
  const endpoint = cdpUrl();
  let connected = false;
  try {
    browser = await chromium.connectOverCDP(endpoint);
    connected = true;
  } catch (err) {
    const spec = chromeLaunchSpec();
    if (!spec) {
      launchInfo = {
        channel: "cdp-connect-failed",
        fellBack: false,
        fallbackReason: `connect ${endpoint}: ${String(err && err.message ? err.message : err)}`,
        mode: "cdp",
      };
      throw new Error(
        `No Chrome is listening at ${endpoint} (CDP). Start your real Chrome with ` +
          `--remote-debugging-port=${new URL(endpoint).port || "9222"} and your mr.wtin profile, ` +
          `or configure WAB_CHROME_USER_DATA / WAB_CHROME_PROFILE so the bridge launches it for you.`
      );
    }
    await launchChromeForCdp(spec);
    browser = await chromium.connectOverCDP(endpoint);
    connected = true;
  }
  if (!connected || !browser) throw new Error("CDP connect failed.");

  // The profile's own context (created by Chrome at launch) carries the real
  // mr.wtin cookies/logins. NEVER silently fall back to browser.newContext()
  // here: on a CDP connection that would create an empty incognito context
  // without the profile's sessions. If the default context isn't there yet
  // (Chrome still starting), wait briefly for it; only if it genuinely never
  // appears do we surface a clear error.
  const deadlineCtx = Date.now() + 10000;
  while (browser.contexts().length === 0) {
    if (Date.now() > deadlineCtx) {
      throw new Error(
        `Connected to ${endpoint} via CDP but no browser context appeared. The ` +
          `profile (${process.env.WAB_CHROME_PROFILE || "default"}) may have failed to ` +
          `open — check browser_info and that Chrome is showing its window.`
      );
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  context = browser.contexts()[0];
  const usedDataDir = chromeLaunchSpec() ? cdpUserDataDir(chromeLaunchSpec()) : null;
  launchInfo = {
    channel: "chrome (CDP)",
    fellBack: false,
    fallbackReason: null,
    mode: "cdp",
    dataDir: usedDataDir || null,
  };
  wireContextEvents(context);

  pages = context.pages().length ? context.pages() : [await context.newPage()];
  activeIndex = 0;
  return context;
}

async function ensureContext() {
  if (context) return context;
  if (cdpEnabled()) return ensureCdpContext();

  // --- legacy path: Playwright launches its own browser (real channel or
  //     bundled Chromium) into a dedicated automation profile ---
  const baseOpts = {
    headless: isHeadless(),
    viewport: { width: 1280, height: 900 },
    args: ["--disable-blink-features=AutomationControlled"],
    acceptDownloads: true,
  };
  const wanted = preferredChannel();

  try {
    context = await chromium.launchPersistentContext(
      profileDir(),
      wanted ? { ...baseOpts, channel: wanted } : baseOpts
    );
    launchInfo = { channel: wanted || "chromium (bundled)", fellBack: false, fallbackReason: null, mode: "launch" };
  } catch (err) {
    if (!wanted) throw err;
    // The requested real browser isn't installed on this machine -- fall
    // back to Playwright's bundled Chromium rather than failing outright.
    context = await chromium.launchPersistentContext(profileDir(), baseOpts);
    launchInfo = {
      channel: "chromium (bundled)",
      fellBack: true,
      fallbackReason: `"${wanted}" not found: ${String(err && err.message ? err.message.split("\n")[0] : err)}`,
      mode: "launch",
    };
  }

  wireContextEvents(context);
  pages = context.pages().length ? context.pages() : [await context.newPage()];
  activeIndex = 0;
  return context;
}

/** "chrome" (default) or "msedge" use the browser already installed on this
 *  machine -- real branding, real fingerprint, far less likely to trip
 *  CAPTCHA/bot-checks than an unbranded automated Chromium. "chromium" uses
 *  Playwright's own bundled build instead (needs a separate download, and
 *  gets flagged as automated much more often). */
function preferredChannel() {
  const c = (process.env.WAB_BROWSER_CHANNEL || "chrome").trim().toLowerCase();
  return c === "chromium" ? null : c;
}

/** The tab that plain tool calls (browser_navigate, browser_click, ...) act on. */
export async function getPage() {
  await ensureContext();
  pages = pages.filter((p) => !p.isClosed());
  if (activeIndex < 0 || activeIndex >= pages.length) activeIndex = pages.length - 1;
  if (activeIndex < 0) {
    pages = [await context.newPage()];
    activeIndex = 0;
  }
  return pages[activeIndex];
}

/** A fresh page for a one-off check (e.g. verifying a link) that should NOT
 *  change which tab subsequent tool calls act on. Caller must close it. */
export async function openTempPage() {
  await ensureContext();
  const p = await context.newPage();
  if (!pages.includes(p)) pages.push(p);
  return p;
}

export async function listTabs() {
  await ensureContext();
  pages = pages.filter((p) => !p.isClosed());
  return Promise.all(
    pages.map(async (p, i) => ({
      index: i,
      active: i === activeIndex,
      url: p.url(),
      title: await p.title().catch(() => ""),
    }))
  );
}

export async function newTab(url) {
  await ensureContext();
  const p = await context.newPage();
  if (!pages.includes(p)) pages.push(p);
  activeIndex = pages.indexOf(p);
  if (url) await p.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  return activeIndex;
}

export async function switchTab(index) {
  await ensureContext();
  pages = pages.filter((p) => !p.isClosed());
  if (index < 0 || index >= pages.length) {
    throw new Error(`No tab at index ${index}. There are ${pages.length} open tab(s).`);
  }
  activeIndex = index;
  return pages[index];
}

export async function closeTab(index) {
  await ensureContext();
  pages = pages.filter((p) => !p.isClosed());
  const target = index === undefined ? activeIndex : index;
  if (target < 0 || target >= pages.length) {
    throw new Error(`No tab at index ${target}. There are ${pages.length} open tab(s).`);
  }
  await pages[target].close().catch(() => {});
  pages = pages.filter((p) => !p.isClosed());
  activeIndex = Math.min(activeIndex, pages.length - 1);
}

export async function closeBrowser() {
  if (cdpEnabled()) {
    // CDP: disconnect from the user's real Chrome — the browser itself stays
    // open (that's the whole point of this mode). Only our connection closes.
    if (browser) {
      await browser.close().catch(() => {});
    }
  } else if (context) {
    await context.close().catch(() => {});
  }
  browser = null;
  context = null;
  pages = [];
  activeIndex = -1;
}

export function getRecentDownloads(sinceTs = 0) {
  return downloads.filter((d) => d.at >= sinceTs);
}

export function getAllDownloads() {
  return downloads.slice();
}

/** Returns the first Locator among candidate selectors that has at least one
 *  attached element, or null if none match within `timeoutMs`. */
export async function firstMatch(pg, selectors, timeoutMs = 8000) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    for (const sel of selectors) {
      const loc = pg.locator(sel).first();
      if ((await loc.count()) > 0) return loc;
    }
    if (Date.now() > deadline) return null;
    await pg.waitForTimeout(250);
  }
}
