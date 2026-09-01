import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import {
  getPage,
  openTempPage,
  closeBrowser,
  firstMatch,
  listTabs,
  newTab,
  switchTab,
  closeTab,
  getRecentDownloads,
  getAllDownloads,
  getLaunchInfo,
  profileDir,
  isHeadless,
} from "./browser.js";
import { PROVIDERS, getProvider } from "./providers.js";
import { classifyContentType, classifyNetError, detectCaptchaWall, detectObstruction, RISKY_ACTION_PATTERN } from "./diagnostics.js";
import { sanitizeIfNeeded } from "./safety.js";
import { runAdaptiveTask } from "./adaptive.js";

const MAX_TEXT_CHARS = 8000;
const LENGTH_WARNING_PATTERN =
  /getting long|reached the (length|context) limit|maximum length|start a new (chat|conversation|thread)|this conversation is (long|too long)/i;

/**
 * Decision policy for "should we suggest starting a new chat because this one
 * has slowed down?" -- written out explicitly so it's a real, auditable rule
 * rather than a vague feeling:
 *
 *   1. Need at least 3 timed replies from THIS conversation before judging a
 *      trend at all. One or two data points can't distinguish "slow" from
 *      "this provider is just like that" or "cold start."
 *   2. Baseline = average of the first 2 replies in this conversation.
 *   3. A reply counts as "slow" only if it exceeds BOTH a relative bar (2x
 *      baseline) AND an absolute bar (baseline + 15s) -- relative alone
 *      false-triggers on providers that are naturally fast (2s -> 4s is
 *      still nothing); absolute alone false-triggers on providers that are
 *      naturally slow.
 *   4. React (degraded=true) only when the last TWO replies are both slow --
 *      a single slow reply is treated as noise (network jitter, provider
 *      hiccup) and gets no reaction. Two in a row is a pattern.
 *
 * Separately, if the provider's own UI literally says the conversation is
 * getting long (LENGTH_WARNING_PATTERN), that's treated as an immediate,
 * independent signal -- it doesn't need to repeat, because the provider is
 * telling you directly rather than us inferring it from timing.
 */
const REPLY_TIMES = new Map(); // provider -> recent elapsed_ms samples, oldest first

function recordReplyTime(provider, ms) {
  const arr = REPLY_TIMES.get(provider) || [];
  arr.push(ms);
  if (arr.length > 8) arr.shift();
  REPLY_TIMES.set(provider, arr);
  return arr;
}

function resetReplyTimes(provider) {
  REPLY_TIMES.delete(provider);
}

function assessDegradation(history) {
  if (history.length < 3) return { degraded: false, samples: history.length };
  const baseline = (history[0] + history[1]) / 2;
  const threshold = Math.max(baseline * 2, baseline + 15000);
  const lastTwo = history.slice(-2);
  const degraded = lastTwo.length === 2 && lastTwo.every((t) => t > threshold);
  return { degraded, samples: history.length, baselineMs: baseline, thresholdMs: threshold };
}

/**
 * For long-running queries (deep research, anything that won't be done in a
 * normal chat-reply timeframe): submit-and-return-immediately
 * (web_ai_start_research), then poll later (web_ai_check_research), instead
 * of one call blocking for however long the provider takes. The job tracks
 * the actual Page object it was submitted on -- not just "whatever tab is
 * active right now" -- so checking still works correctly even if Claude
 * switches tabs or opens others while waiting.
 */
const RESEARCH_JOBS = new Map(); // provider -> { startedAt, promptPreview, page }

/** Distinguishes "still thinking" from a genuinely dead tab/connection: a
 *  closed page fails instantly; a hung/disconnected one fails the race
 *  against the timeout instead of hanging forever. */
async function pageIsResponsive(page, timeoutMs = 5000) {
  if (!page || page.isClosed()) return false;
  try {
    await Promise.race([
      page.evaluate(() => true),
      new Promise((_, reject) => setTimeout(() => reject(new Error("evaluate timed out")), timeoutMs)),
    ]);
    return true;
  } catch {
    return false;
  }
}

function truncate(text, max = MAX_TEXT_CHARS) {
  if (!text) return text;
  if (text.length <= max) return text;
  return text.slice(0, max) + `\n...[truncated, ${text.length} chars total]`;
}

function textResult(text) {
  return { content: [{ type: "text", text }] };
}

function errorResult(message) {
  return { content: [{ type: "text", text: message }], isError: true };
}

async function typeInto(locator, text) {
  // fill() works on <input>/<textarea>/contenteditable in modern Playwright;
  // fall back to real keystrokes for editors that need per-key React events.
  try {
    await locator.fill(text, { timeout: 5000 });
    return;
  } catch {
    await locator.click({ timeout: 5000 }).catch(() => {});
    await locator.pressSequentially(text, { delay: 12, timeout: 30000 });
  }
}

async function waitForResponseSettled(page, provider, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  await page.waitForTimeout(500);

  if (provider.streamingIndicator) {
    await page
      .waitForSelector(provider.streamingIndicator, { state: "visible", timeout: 3000 })
      .catch(() => {});
    const remaining = Math.max(1000, deadline - Date.now());
    const settledByIndicator = await page
      .waitForSelector(provider.streamingIndicator, { state: "hidden", timeout: remaining })
      .then(() => true)
      .catch(() => false);
    if (settledByIndicator) return;
  }

  // Fallback: poll the response text until it stops changing for ~1.2s.
  let last = "";
  let stableSince = Date.now();
  while (Date.now() < deadline) {
    const loc = await firstMatch(page, provider.responseCandidates, 1000);
    const text = loc ? await loc.innerText().catch(() => "") : "";
    if (text !== last) {
      last = text;
      stableSince = Date.now();
    } else if (text && Date.now() - stableSince > 1200) {
      return;
    }
    await page.waitForTimeout(300);
  }
}

/** Opens a fresh conversation the way a human would: click the provider's own
 *  "New chat" button first, and only fall back to a bare URL navigation if no
 *  such button can be found. */
/** Best-effort selectors for the two most common page-cluttering patterns.
 *  Playwright's `:has-text()` is its own selector-engine extension, not
 *  standard CSS, and works fine with page.locator(). Accepting the cookie
 *  banner (rather than rejecting) is the one reliable way to unblock a page
 *  automatically; a human who cares about tracking preferences should still
 *  review the site's actual cookie settings themselves. */
const COOKIE_ACCEPT_CANDIDATES = [
  "#onetrust-accept-btn-handler",
  "button[id*='accept' i][id*='cookie' i]",
  "button[class*='accept' i][class*='cookie' i]",
  "[aria-label='Accept cookies' i]",
  "button:has-text('Accept all')",
  "button:has-text('Accept All Cookies')",
  "button:has-text('I Accept')",
  "button:has-text('I agree')",
];
const GENERIC_DISMISS_CANDIDATES = [
  "button[aria-label='Close' i]",
  "button[aria-label='Dismiss' i]",
  "[class*='modal-close' i]",
  "[class*='popup-close' i]",
  "button:has-text('No thanks')",
  "button:has-text('Not now')",
  "button:has-text('×')",
];

async function dismissOverlays(page) {
  const dismissed = [];
  for (const group of [
    { label: "cookie banner", candidates: COOKIE_ACCEPT_CANDIDATES },
    { label: "popup/modal", candidates: GENERIC_DISMISS_CANDIDATES },
  ]) {
    for (const sel of group.candidates) {
      try {
        const loc = page.locator(sel).first();
        if ((await loc.count()) > 0 && (await loc.isVisible())) {
          await loc.click({ timeout: 3000 });
          dismissed.push(`${group.label} ("${sel}")`);
          await page.waitForTimeout(300);
          break; // one hit per group is usually enough
        }
      } catch {
        // this candidate didn't pan out -- try the next one
      }
    }
  }
  return dismissed;
}

async function openNewChat(page, provider) {
  if (!page.url().includes(new URL(provider.url).hostname)) {
    await page.goto(provider.url, { waitUntil: "domcontentloaded", timeout: 30000 });
    return "navigated";
  }
  const btn = await firstMatch(page, provider.newChatCandidates || [], 3000);
  if (btn) {
    await btn.click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(500);
    return "clicked";
  }
  await page.goto(provider.url, { waitUntil: "domcontentloaded", timeout: 30000 });
  return "navigated";
}

async function detectLengthWarning(page) {
  try {
    const body = await page.evaluate(() => document.body.innerText);
    return LENGTH_WARNING_PATTERN.test(body);
  } catch {
    return false;
  }
}

/** Navigates a page and classifies what actually happened: a real page, an
 *  image, a file download, an HTTP error, a network failure, or a likely
 *  CAPTCHA/bot-check wall -- so problems are reported, not just swallowed. */
async function navigateAndDiagnose(page, url, timeoutMs = 20000) {
  const startedAt = Date.now();
  let response = null;
  let navError = null;
  try {
    response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: timeoutMs });
  } catch (err) {
    navError = err;
  }

  if (navError) {
    // The "failure" may just be a file download starting instead of a page loading.
    await page.waitForTimeout(700).catch(() => {});
    const recentDownload = getRecentDownloads(startedAt)[0];
    if (recentDownload) {
      return recentDownload.error
        ? { kind: "file_error", url, download: recentDownload, problem: `Download failed: ${recentDownload.error}` }
        : { kind: "file", url, download: recentDownload };
    }
    const { reason, code } = classifyNetError(navError.message);
    return { kind: "error", url, problem: reason, error_code: code };
  }

  const status = response ? response.status() : null;
  const finalUrl = response ? response.url() : page.url();
  const headers = response ? await response.allHeaders().catch(() => ({})) : {};
  const contentType = headers["content-type"] || "";
  const kind = classifyContentType(contentType);

  if (status && status >= 400) {
    return { kind: "error", url, final_url: finalUrl, status, content_type: contentType, problem: `HTTP ${status}${response.statusText() ? " " + response.statusText() : ""}` };
  }

  if (kind === "page") {
    const [captcha, title] = await Promise.all([detectCaptchaWall(page), page.title().catch(() => "")]);
    if (captcha) {
      return {
        kind: "blocked",
        url,
        final_url: finalUrl,
        status,
        content_type: contentType,
        title,
        problem: "Page looks like a CAPTCHA / bot-check / access-denied wall, not real content",
      };
    }
    const obstruction = await detectObstruction(page);
    return { kind: "page", url, final_url: finalUrl, status, content_type: contentType, title, obstruction };
  }

  return { kind, url, final_url: finalUrl, status, content_type: contentType };
}

function formatDiagnostic(d) {
  // Sahifa sarlavhasi WEB manbasidan keladi — injection bo'lishi mumkin, shu
  // sabab diagnostic matni ham tozalanadi (browser_navigate/browser_check_link
  // chiqishlari ham N3 qamrovida bo'ladi).
  const title = d.title ? sanitizeIfNeeded(String(d.title)) : "";
  if (d.kind === "error") return `Problem loading ${d.url}: ${d.problem}`;
  if (d.kind === "file_error") return `Link triggered a download of "${d.download.filename}" but saving it failed: ${d.problem}`;
  if (d.kind === "file") return `Link triggered a file download: "${d.download.filename}" (${d.download.bytes} bytes) saved to ${d.download.path}`;
  if (d.kind === "blocked") return `Loaded ${d.final_url} but it looks blocked: ${d.problem}\nTitle: "${title}"`;
  const lines = [`Loaded ${d.final_url || d.url}`];
  if (d.status) lines.push(`Status: ${d.status}`);
  if (d.content_type) lines.push(`Content-Type: ${d.content_type} (${d.kind})`);
  if (title) lines.push(`Title: "${title}"`);
  if (d.obstruction) lines.push(`Note: ${d.obstruction.note} -- call browser_dismiss_overlays() if it's in the way`);
  return lines.join("\n");
}

/**
 * "When to use" guidance shown to the model at schema level, so it picks the
 * right tool WHILE choosing (not only from the system prompt).
 *
 * THIS is the source of truth. The same text (with the web_ai_bridge__ prefix)
 * is kept in Igris_brain/igris_agent.py (WEB_TOOL_HINTS) only as a fallback
 * for older bridge versions -- new bridges ship the hint baked into the tool
 * description itself, and the agent skips appending when it is already there.
 */
const WHEN_TO_USE = {
  browser_navigate:
    "Open a URL. The result is classified by real HTTP status + Content-Type " +
    "(page/image/media/text/file), never guessed from the URL extension, and " +
    "reported as BLOCKED (CAPTCHA) or OBSTRUCTED (cookie banner) - never both.",
  browser_check_link:
    "Verify a link in a throwaway tab without leaving your current work - use " +
    "when the user hands you a link and wants to know what it is first.",
  browser_screenshot:
    "Look at the page yourself - especially when selector-based tools fail or " +
    "a login/CAPTCHA might be showing.",
  browser_get_text:
    "Read the page's text (ads/clutter stripped). Pass clean:false only if " +
    "you need the raw unfiltered text.",
  browser_click:
    "NEVER click irreversible actions (Buy Now, Place Order, Confirm Payment, " +
    "Pay Now, Proceed to Checkout, Delete My Account, Cancel Subscription) " +
    "without explicit user confirmation - retry with confirm:true only after " +
    "the user agrees. Add to Cart and plain navigation are fine.",
  browser_type:
    "Fill in a field. Text about to be sent is scanned for secrets (API keys, " +
    "tokens, passwords) before it leaves.",
  browser_select_option:
    "Choose an option in a dropdown by visible label or value.",
  browser_upload_file:
    "Attach a local file to a file input, like a human file picker.",
  browser_press_key:
    "Press a keyboard key or shortcut (Escape, Ctrl+A, Tab...).",
  browser_scroll:
    "Scroll the page or reveal an element that is off-screen.",
  browser_wait_for:
    "Wait for something to actually load instead of guessing a delay.",
  browser_list_tabs:
    "List open tabs - use when a site opens something in a new tab or you are " +
    "working two things in parallel.",
  browser_new_tab: "Open a new tab and make it active, like Ctrl+T.",
  browser_switch_tab: "Make a different open tab the active one.",
  browser_close_tab: "Close a tab (omit index to close the active one).",
  browser_list_downloads:
    "Files are saved automatically when a link triggers a download - check " +
    "this instead of treating the download as an error.",
  browser_info:
    "Confirm which browser is actually running (real Chrome via CDP vs " +
    "bundled Chromium).",
  browser_dismiss_overlays:
    "Clear a cookie-consent banner (clicks Accept) or close generic popups " +
    "(Close/Dismiss/No thanks). Call when a page's real content seems blocked " +
    "or a navigation flags an obstruction.",
  browser_hover: "Hover over an element to open hover menus/tooltips.",
  browser_go_back: "Go back one page in the active tab's history.",
  browser_go_forward: "Go forward one page in the active tab's history.",
  browser_close: "Close the entire browser (all tabs) and end the session.",
  browser_ai_task:
    "Give the WHOLE task to an adaptive agent (browser-use-style): it re-reads " +
    "the live page every step and picks elements by text/label, so it keeps " +
    "working even when a site redesigns its UI. Use for multi-step jobs on " +
    "unknown or unstable pages (research flows, form chains, product lookups). " +
    "Precise single clicks/fills are still faster with the plain tools.",
  ask_web_ai:
    "PREFER this for research/knowledge questions ('what does X say', " +
    "qidirib ber, tadqiqot): it DELEGATES to a web AI subagent " +
    "(chatgpt/gemini/claude_web/deepseek) that does the browsing for you. " +
    "For long jobs use web_ai_start_research instead. Requires the user to " +
    "be logged in to the provider in the visible Chrome window (first use) - " +
    "if it fails with a login error, ask the user to log in.",
  web_ai_start_research:
    "For deep research that takes a while: submit and return immediately, " +
    "then do your own useful work and poll web_ai_check_research. " +
    "Never block-wait for a long reply.",
  web_ai_check_research:
    "Poll a research job started with web_ai_start_research: still working " +
    "(normal, check later) / complete (reply text) / hard failure (report it).",
  web_ai_new_chat:
    "Start a fresh conversation with the provider - use when ask_web_ai " +
    "replies get slow or the provider says the conversation is getting long; " +
    "fold the essential context into your next prompt.",
  web_ai_stop_generating:
    "Interrupt a reply that is still generating.",
  web_ai_get_conversation:
    "Read the full on-screen conversation with a provider - use before " +
    "starting a new chat to carry forward what matters.",
};

const TOOLS = [
  // ---- General browser control (anything a human can do in a tab) ----
  {
    name: "browser_navigate",
    description:
      "Navigate the active tab to a URL and report what actually happened: a page, an image, a " +
      "file download, an HTTP error, or a likely CAPTCHA/block wall.",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "Absolute URL to open" },
        timeout_ms: { type: "number", description: "Default 20000" },
      },
      required: ["url"],
    },
  },
  {
    name: "browser_check_link",
    description:
      "Verify a link without disturbing your current tab: opens it in a throwaway tab, reports " +
      "status code, content type, whether it's a page/image/file/download, or what went wrong " +
      "(broken, timed out, blocked), then closes the tab. Use this whenever the user gives you a " +
      "link and wants to know if/what it is before you commit to browsing it.",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string" },
        timeout_ms: { type: "number", description: "Default 15000" },
      },
      required: ["url"],
    },
  },
  {
    name: "browser_go_back",
    description: "Go back one page in the active tab's history.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "browser_go_forward",
    description: "Go forward one page in the active tab's history.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "browser_screenshot",
    description: "Take a PNG screenshot of the active tab -- use this to actually look at the page.",
    inputSchema: {
      type: "object",
      properties: {
        full_page: { type: "boolean", description: "Capture the full scrollable page, not just the viewport. Default false." },
      },
    },
  },
  {
    name: "browser_get_text",
    description:
      "Read visible text from the page. Omit selector to get the whole page's text (truncated), " +
      "with obvious ad/cookie-banner/newsletter-popup clutter stripped out by default.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector; optional" },
        clean: {
          type: "boolean",
          description:
            "When no selector is given, strip likely ad/sponsor/cookie/popup elements before reading. Default true.",
        },
      },
    },
  },
  {
    name: "browser_click",
    description:
      "Click the first element matching a CSS selector. If its text reads like a real-world " +
      "consequential action (payment, purchase, account deletion), this is refused until you " +
      "confirm the user has explicitly agreed, then retry with confirm: true.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string" },
        confirm: {
          type: "boolean",
          description: "Required (true) to click something that reads as payment/purchase/deletion/cancellation.",
        },
      },
      required: ["selector"],
    },
  },
  {
    name: "browser_hover",
    description: "Hover over the first element matching a CSS selector (opens hover menus/tooltips).",
    inputSchema: {
      type: "object",
      properties: { selector: { type: "string" } },
      required: ["selector"],
    },
  },
  {
    name: "browser_type",
    description: "Type text into the first element matching a CSS selector.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string" },
        text: { type: "string" },
        submit: { type: "boolean", description: "Press Enter after typing. Default false." },
      },
      required: ["selector", "text"],
    },
  },
  {
    name: "browser_press_key",
    description:
      "Press a keyboard key or shortcut, e.g. 'Enter', 'Escape', 'Tab', 'Control+A'. If selector is given, the element is focused first.",
    inputSchema: {
      type: "object",
      properties: {
        key: { type: "string" },
        selector: { type: "string" },
      },
      required: ["key"],
    },
  },
  {
    name: "browser_select_option",
    description: "Choose an option in a <select> dropdown by visible label or value.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string" },
        label: { type: "string" },
        value: { type: "string" },
      },
      required: ["selector"],
    },
  },
  {
    name: "browser_upload_file",
    description: "Attach a local file to a file input element, the way a human uses a file picker.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector for the <input type=file> (or an element that opens one)" },
        path: { type: "string", description: "Absolute path to the local file to attach" },
      },
      required: ["selector", "path"],
    },
  },
  {
    name: "browser_scroll",
    description: "Scroll the page or, if selector is given, scroll a specific element into view.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "Scroll this element into view instead of the whole page" },
        direction: { type: "string", enum: ["up", "down"], description: "Default 'down'" },
        amount_px: { type: "number", description: "Pixels to scroll. Default one viewport height." },
      },
    },
  },
  {
    name: "browser_wait_for",
    description:
      "Wait until a selector appears/disappears, page text contains a string, or a fixed time passes -- use before reading something that loads asynchronously.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string" },
        state: { type: "string", enum: ["visible", "hidden", "attached", "detached"], description: "Default 'visible'" },
        text_contains: { type: "string", description: "Wait for the page's visible text to contain this string" },
        timeout_ms: { type: "number", description: "Default 15000" },
      },
    },
  },
  {
    name: "browser_list_tabs",
    description: "List all open tabs: index, URL, page title, which one is active.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "browser_new_tab",
    description: "Open a new tab and make it the active one, the way a human opens Ctrl+T.",
    inputSchema: {
      type: "object",
      properties: { url: { type: "string", description: "Optional URL to load immediately" } },
    },
  },
  {
    name: "browser_switch_tab",
    description: "Make a different open tab the active one for subsequent tool calls.",
    inputSchema: {
      type: "object",
      properties: { index: { type: "number" } },
      required: ["index"],
    },
  },
  {
    name: "browser_close_tab",
    description: "Close a tab. Omit index to close the active tab.",
    inputSchema: {
      type: "object",
      properties: { index: { type: "number" } },
    },
  },
  {
    name: "browser_list_downloads",
    description: "List every file downloaded so far this session: filename, size, saved path, source URL.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "browser_info",
    description:
      "Report which browser is actually running (real Chrome via CDP with the user's own profile, real " +
      "Chrome/Edge, or Playwright's bundled Chromium), whether it's visible or headless, and where its " +
      "login/cookie profile lives. Use this to confirm you're on a real, branded browser -- that's what " +
      "keeps CAPTCHA/bot-checks rare.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "browser_dismiss_overlays",
    description:
      "Detect and close common page clutter that isn't real content -- cookie-consent banners and " +
      "newsletter/subscribe popups. Accepts cookie banners (the reliable way to unblock a page) and " +
      "closes obvious modals. Best-effort; if nothing matches, it says so rather than guessing.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "browser_close",
    description: "Close the entire browser (all tabs) and end the session.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "browser_ai_task",
    description:
      "Run a whole task with an adaptive agent: it reads the live page each step " +
      "and chooses actions by element text/label, so UI redesigns don't break it. " +
      "Returns the final answer plus a step log. Irreversible actions (payment, " +
      "purchase, account deletion) are refused and reported instead of clicked.",
    inputSchema: {
      type: "object",
      properties: {
        task: { type: "string", description: "The task to complete on the page, in the user's language" },
        url: { type: "string", description: "Optional URL to navigate to first" },
        max_steps: { type: "number", description: "Max agent steps. Default 12, max 25" },
      },
      required: ["task"],
    },
  },

  // ---- High-level: talking to another AI's web chat ----
  {
    name: "ask_web_ai",
    description:
      `Send a prompt to a web AI chat UI (${Object.keys(PROVIDERS).join(", ")}) using a real ` +
      "logged-in browser session, wait for the reply, and return its text plus timing info. " +
      "First use requires manually logging in once in the visible browser window.",
    inputSchema: {
      type: "object",
      properties: {
        provider: { type: "string", enum: Object.keys(PROVIDERS) },
        prompt: { type: "string" },
        new_chat: {
          type: "boolean",
          description:
            "Start a fresh conversation first (clicks the provider's real New Chat button, " +
            "not just a URL change). Default true.",
        },
        wait_timeout_ms: {
          type: "number",
          description: "Max time to wait for the reply to finish streaming. Default 60000.",
        },
      },
      required: ["provider", "prompt"],
    },
  },
  {
    name: "web_ai_new_chat",
    description:
      "Start a fresh conversation with a provider by clicking its real New Chat button (URL " +
      "navigation only as a fallback). Use this yourself -- e.g. when replies have gotten " +
      "noticeably slower or ask_web_ai reports length_warning -- rather than always relying on " +
      "ask_web_ai's new_chat flag. Summarize what mattered from the old conversation yourself and " +
      "fold that summary into your next ask_web_ai prompt so context isn't lost.",
    inputSchema: {
      type: "object",
      properties: { provider: { type: "string", enum: Object.keys(PROVIDERS) } },
      required: ["provider"],
    },
  },
  {
    name: "web_ai_stop_generating",
    description: "Click the provider's Stop button to interrupt a reply that's generating.",
    inputSchema: {
      type: "object",
      properties: { provider: { type: "string", enum: Object.keys(PROVIDERS) } },
      required: ["provider"],
    },
  },
  {
    name: "web_ai_get_conversation",
    description:
      "Read the full visible text of the current conversation (both sides) on a provider's page. " +
      "Use this before starting a new chat to capture what's worth carrying forward, or to catch " +
      "up on a conversation that was already open.",
    inputSchema: {
      type: "object",
      properties: {
        provider: { type: "string", enum: Object.keys(PROVIDERS) },
        max_chars: { type: "number", description: "Default 20000" },
      },
      required: ["provider"],
    },
  },
  {
    name: "web_ai_start_research",
    description:
      "For a query that will take a while (deep research, long analysis) -- submit the prompt and " +
      "return immediately, WITHOUT waiting for the reply. Do useful work of your own next, then call " +
      "web_ai_check_research periodically to see if it's done. Use this instead of ask_web_ai whenever " +
      "you expect the reply to take longer than a normal chat turn.",
    inputSchema: {
      type: "object",
      properties: {
        provider: { type: "string", enum: Object.keys(PROVIDERS) },
        prompt: { type: "string" },
        new_chat: { type: "boolean", description: "Start a fresh conversation first. Default true." },
      },
      required: ["provider", "prompt"],
    },
  },
  {
    name: "web_ai_check_research",
    description:
      "Poll a job started with web_ai_start_research. Returns one of: still working (not done yet -- " +
      "keep doing your own thing and check again later), complete (with the reply text), or a hard " +
      "failure (the tab stopped responding entirely / connection lost -- this is reported explicitly, " +
      "it is never just silently retried).",
    inputSchema: {
      type: "object",
      properties: {
        provider: { type: "string", enum: Object.keys(PROVIDERS) },
        stall_after_ms: {
          type: "number",
          description: "How long 'still generating' is trusted before being flagged as possibly stuck. Default 1800000 (30 min).",
        },
      },
      required: ["provider"],
    },
  },
];

// Bake the "when to use" guidance into each tool's description so the model
// sees it at tool-selection time. Done once at startup (idempotent -- the
// module loads only once per process).
for (const tool of TOOLS) {
  const hint = WHEN_TO_USE[tool.name];
  if (hint) tool.description += `\n\nWHEN TO USE: ${hint}`;
}

const server = new Server(
  { name: "web-ai-bridge", version: "0.8.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args = {} } = request.params;

  try {
    switch (name) {
      case "browser_navigate": {
        const page = await getPage();
        const diag = await navigateAndDiagnose(page, args.url, args.timeout_ms || 20000);
        return textResult(formatDiagnostic(diag));
      }

      case "browser_check_link": {
        const page = await openTempPage();
        try {
          const diag = await navigateAndDiagnose(page, args.url, args.timeout_ms || 15000);
          return textResult(formatDiagnostic(diag));
        } finally {
          await page.close().catch(() => {});
        }
      }

      case "browser_go_back": {
        const page = await getPage();
        await page.goBack({ waitUntil: "domcontentloaded", timeout: 30000 }).catch(() => {});
        return textResult(`Now at ${page.url()}`);
      }

      case "browser_go_forward": {
        const page = await getPage();
        await page.goForward({ waitUntil: "domcontentloaded", timeout: 30000 }).catch(() => {});
        return textResult(`Now at ${page.url()}`);
      }

      case "browser_screenshot": {
        const page = await getPage();
        const buf = await page.screenshot({ type: "png", fullPage: !!args.full_page });
        return {
          content: [{ type: "image", data: buf.toString("base64"), mimeType: "image/png" }],
        };
      }

      case "browser_get_text": {
        const page = await getPage();
        let text;
        if (args.selector) {
          const loc = page.locator(args.selector).first();
          if ((await loc.count()) === 0) return errorResult(`No element matches "${args.selector}"`);
          text = await loc.innerText();
        } else {
          const clean = args.clean !== false;
          text = await page.evaluate((doClean) => {
            if (!doClean) return document.body.innerText;
            const clone = document.body.cloneNode(true);
            const junk = [
              "script", "style", "noscript", "iframe",
              "[class*='advert' i]", "[id*='advert' i]",
              "[class*='-ad-' i]", "[id*='-ad-' i]",
              "[class*='ad-container' i]", "[id*='ad-container' i]",
              "[class*='sponsor' i]", "[id*='sponsor' i]",
              "[class*='cookie' i]", "[id*='cookie' i]",
              "[class*='newsletter' i]", "[id*='newsletter' i]",
              "[class*='popup' i]", "[id*='popup' i]",
              "[aria-hidden='true']",
            ];
            clone.querySelectorAll(junk.join(",")).forEach((el) => el.remove());
            return clone.innerText;
          }, clean);
        }
        // N3 to'liq yechim: sahifa matnidagi yashirin injection ko'rsatmalar
        // LLM'ga yetib bormasligi uchun maskalanadi (safety.py bilan bir xil qoidalar).
        return textResult(truncate(sanitizeIfNeeded(text)));
      }

      case "browser_click": {
        const page = await getPage();
        const loc = page.locator(args.selector).first();
        if ((await loc.count()) === 0) return errorResult(`No element matches "${args.selector}"`);
        const label = await loc.innerText().catch(() => "");
        if (!args.confirm && RISKY_ACTION_PATTERN.test(label)) {
          return errorResult(
            `Not clicking yet: "${label.trim().slice(0, 80)}" reads like a real-world consequential ` +
              "action (payment, purchase, account deletion, cancellation, etc.). Tell the user exactly " +
              "what this will do and get their explicit OK first, then call browser_click again with " +
              "confirm: true to proceed."
          );
        }
        await loc.click({ timeout: 10000 });
        return textResult(`Clicked "${args.selector}"${label.trim() ? ` ("${label.trim().slice(0, 60)}")` : ""}`);
      }

      case "browser_hover": {
        const page = await getPage();
        const loc = page.locator(args.selector).first();
        if ((await loc.count()) === 0) return errorResult(`No element matches "${args.selector}"`);
        await loc.hover({ timeout: 10000 });
        return textResult(`Hovering over "${args.selector}"`);
      }

      case "browser_type": {
        const page = await getPage();
        const loc = page.locator(args.selector).first();
        if ((await loc.count()) === 0) return errorResult(`No element matches "${args.selector}"`);
        await typeInto(loc, args.text);
        if (args.submit) await loc.press("Enter").catch(() => page.keyboard.press("Enter"));
        return textResult(`Typed into "${args.selector}"${args.submit ? " and pressed Enter" : ""}`);
      }

      case "browser_press_key": {
        const page = await getPage();
        if (args.selector) {
          const loc = page.locator(args.selector).first();
          if ((await loc.count()) === 0) return errorResult(`No element matches "${args.selector}"`);
          await loc.focus().catch(() => {});
          await loc.press(args.key, { timeout: 10000 });
        } else {
          await page.keyboard.press(args.key);
        }
        return textResult(`Pressed "${args.key}"`);
      }

      case "browser_select_option": {
        const page = await getPage();
        const loc = page.locator(args.selector).first();
        if ((await loc.count()) === 0) return errorResult(`No element matches "${args.selector}"`);
        const opt = {};
        if (args.label) opt.label = args.label;
        if (args.value) opt.value = args.value;
        await loc.selectOption(opt, { timeout: 10000 });
        return textResult(`Selected ${args.label || args.value} in "${args.selector}"`);
      }

      case "browser_upload_file": {
        const page = await getPage();
        const loc = page.locator(args.selector).first();
        if ((await loc.count()) === 0) return errorResult(`No element matches "${args.selector}"`);
        await loc.setInputFiles(args.path, { timeout: 15000 });
        return textResult(`Attached "${args.path}" to "${args.selector}"`);
      }

      case "browser_scroll": {
        const page = await getPage();
        if (args.selector) {
          const loc = page.locator(args.selector).first();
          if ((await loc.count()) === 0) return errorResult(`No element matches "${args.selector}"`);
          await loc.scrollIntoViewIfNeeded({ timeout: 10000 });
          return textResult(`Scrolled "${args.selector}" into view`);
        }
        const dy = (args.direction === "up" ? -1 : 1) * (args.amount_px || 800);
        await page.mouse.wheel(0, dy);
        return textResult(`Scrolled ${args.direction === "up" ? "up" : "down"} ${Math.abs(dy)}px`);
      }

      case "browser_wait_for": {
        const page = await getPage();
        const timeout = args.timeout_ms || 15000;
        if (args.selector) {
          await page.waitForSelector(args.selector, { state: args.state || "visible", timeout });
          return textResult(`"${args.selector}" is now ${args.state || "visible"}`);
        }
        if (args.text_contains) {
          const deadline = Date.now() + timeout;
          while (Date.now() < deadline) {
            const body = await page.evaluate(() => document.body.innerText).catch(() => "");
            if (body.includes(args.text_contains)) return textResult(`Page now contains "${args.text_contains}"`);
            await page.waitForTimeout(300);
          }
          return errorResult(`Timed out waiting for page text to contain "${args.text_contains}"`);
        }
        await page.waitForTimeout(timeout);
        return textResult(`Waited ${timeout}ms`);
      }

      case "browser_list_tabs": {
        const tabs = await listTabs();
        return textResult(JSON.stringify(tabs, null, 2));
      }

      case "browser_new_tab": {
        const index = await newTab(args.url);
        return textResult(`Opened tab ${index}${args.url ? ` at ${args.url}` : ""}`);
      }

      case "browser_switch_tab": {
        const page = await switchTab(args.index);
        return textResult(`Switched to tab ${args.index} (${page.url()})`);
      }

      case "browser_close_tab": {
        await closeTab(args.index);
        return textResult(`Closed tab ${args.index ?? "(active)"}`);
      }

      case "browser_list_downloads": {
        const list = getAllDownloads();
        if (!list.length) return textResult("No files downloaded yet this session.");
        return textResult(
          list
            .map((d) =>
              d.error
                ? `- ${d.filename} <- ${d.url}\n  FAILED: ${d.error}`
                : `- ${d.filename} (${d.bytes} bytes) <- ${d.url}\n  saved to ${d.path}`
            )
            .join("\n")
        );
      }

      case "browser_info": {
        await getPage(); // make sure the browser has actually launched
        const info = getLaunchInfo();
        const lines = [
          `Browser: ${info.channel}${info.fellBack ? " (fell back -- " + info.fallbackReason + ")" : ""}`,
          `Mode: ${isHeadless() && info.mode !== "cdp" ? "headless (not visible)" : "visible window"}`,
        ];
        if (info.mode === "cdp") {
          lines.push(`Connection: real Chrome via CDP (${info.cdpUrl}) -- Chrome stays open, nothing is killed`);
          lines.push(`Chrome profile: ${info.chromeProfile ? `"${info.chromeProfile}"` : "(default)"}${info.chromeUserData ? ` in ${info.chromeUserData}` : ""}`);
          if (info.dataDir) lines.push(`Data dir used by Chrome: ${info.dataDir} (link to your real profile if the default dir was configured)`);
          lines.push(
            "This is your real Chrome with your real logged-in profile -- existing logins, cookies and " +
            "sessions are already there, and CAPTCHAs are rare."
          );
        } else {
          lines.push(`Profile / cookies stored at: ${profileDir()}`);
          if (!info.channel.includes("bundled")) {
            lines.push("This is your real, branded browser -- normal logins and far fewer CAPTCHAs than an automated Chromium.");
          } else {
            lines.push(
              "Using Playwright's bundled Chromium (not your real Chrome) -- more likely to trigger CAPTCHAs. " +
                "Install real Chrome, or set the plugin's browser_channel option to \"chrome\", to avoid this."
            );
          }
        }
        return textResult(lines.join("\n"));
      }

      case "browser_dismiss_overlays": {
        const page = await getPage();
        const dismissed = await dismissOverlays(page);
        return textResult(
          dismissed.length
            ? `Dismissed: ${dismissed.join(", ")}`
            : "No obvious cookie banners or popups found to dismiss."
        );
      }

      case "browser_close": {
        await closeBrowser();
        return textResult("Browser closed.");
      }

      case "browser_ai_task": {
        const page = await getPage();
        if (args.url) {
          const diag = await navigateAndDiagnose(page, args.url, 30000);
          if (diag.kind === "error" || diag.kind === "blocked") {
            return errorResult(`Could not open ${args.url}: ${diag.problem}`);
          }
        }
        const res = await runAdaptiveTask(page, { task: args.task, maxSteps: args.max_steps });
        const headline =
          res.status === "done"
            ? "✓ completed"
            : res.status === "failed"
              ? "✗ failed"
              : "⚠ stopped at step limit";
        // Javob LLM'dan keladi va sahifa matniga asoslangan bo'lishi mumkin —
        // boshqa text tool'lari (browser_get_text) bilan bir xil tozalash.
        const safeAnswer = res.answer ? sanitizeIfNeeded(res.answer) : "(javob yo'q)";
        const lines = [`browser_ai_task ${headline} (${res.steps} steps):`, "", safeAnswer];
        if (res.log && res.log.length) {
          lines.push("", "Agent log:");
          lines.push(res.log.join("\n"));
        }
        return textResult(lines.join("\n"));
      }

      case "ask_web_ai": {
        const provider = getProvider(args.provider);
        const page = await getPage();
        const wantNewChat = args.new_chat !== false;

        if (wantNewChat) {
          await openNewChat(page, provider);
          resetReplyTimes(args.provider); // fresh conversation -> old timing baseline no longer applies
        } else if (!page.url().includes(new URL(provider.url).hostname)) {
          await page.goto(provider.url, { waitUntil: "domcontentloaded", timeout: 30000 });
        }

        const input = await firstMatch(page, provider.inputCandidates, 15000);
        if (!input) {
          return errorResult(
            `Could not find the ${provider.label} input box. Either you're not logged in yet ` +
              `(run browser_screenshot to check) or ${provider.label} changed its UI and the ` +
              `selectors in server/src/providers.js need updating.`
          );
        }

        await typeInto(input, args.prompt);

        const submit = await firstMatch(page, provider.submitCandidates, 3000);
        if (submit) {
          await submit.click({ timeout: 5000 }).catch(async () => {
            await input.press("Enter").catch(() => {});
          });
        } else {
          await input.press("Enter").catch(() => {});
        }

        const startedAt = Date.now();
        await waitForResponseSettled(page, provider, args.wait_timeout_ms || 60000);
        const elapsedMs = Date.now() - startedAt;

        const responseLoc = await firstMatch(page, provider.responseCandidates, 5000);
        if (!responseLoc) {
          return errorResult(
            `Sent the prompt to ${provider.label} but couldn't locate the reply on the page. ` +
              "Use browser_screenshot / browser_get_text to inspect it manually."
          );
        }
        const text = sanitizeIfNeeded(await responseLoc.innerText());
        const lengthWarning = await detectLengthWarning(page);
        const history = recordReplyTime(args.provider, elapsedMs);
        const degradation = assessDegradation(history);

        const statusBits = [`replied in ~${(elapsedMs / 1000).toFixed(1)}s`];
        if (degradation.samples >= 3) {
          statusBits.push(`baseline ~${(degradation.baselineMs / 1000).toFixed(1)}s over ${degradation.samples} replies this chat`);
        }
        let meta = `\n\n[web-ai-bridge: ${statusBits.join(", ")}]`;
        if (lengthWarning) {
          meta += `\n[web-ai-bridge: ${provider.label}'s own UI indicates this chat is getting long -- direct signal, act on it now]`;
        }
        if (degradation.degraded) {
          meta += `\n[web-ai-bridge: last 2 replies were consistently far slower than this chat's own baseline (not a single blip) -- consider web_ai_new_chat]`;
        }
        return textResult(truncate(text) + meta);
      }

      case "web_ai_new_chat": {
        const provider = getProvider(args.provider);
        const page = await getPage();
        const how = await openNewChat(page, provider);
        resetReplyTimes(args.provider);
        return textResult(
          how === "clicked"
            ? `Clicked ${provider.label}'s New Chat button.`
            : `No dedicated New Chat button found for ${provider.label} (or wasn't on its site yet); navigated to its default chat URL instead.`
        );
      }

      case "web_ai_stop_generating": {
        const provider = getProvider(args.provider);
        const page = await getPage();
        if (!provider.streamingIndicator) return errorResult(`${provider.label} has no configured stop button.`);
        const btn = page.locator(provider.streamingIndicator).first();
        if ((await btn.count()) === 0) return textResult(`Nothing appears to be generating on ${provider.label} right now.`);
        await btn.click({ timeout: 5000 });
        return textResult(`Stopped ${provider.label}'s generation.`);
      }

      case "web_ai_get_conversation": {
        const provider = getProvider(args.provider);
        const page = await getPage();
        if (!page.url().includes(new URL(provider.url).hostname)) {
          return errorResult(`Not currently on ${provider.label}'s site -- navigate/ask there first.`);
        }
        const text = await page.evaluate(() => document.body.innerText);
        // N3: sahifa matnidagi injection ko'rsatmalar maskalanadi
        return textResult(truncate(sanitizeIfNeeded(text), args.max_chars || 20000));
      }

      case "web_ai_start_research": {
        const provider = getProvider(args.provider);
        const page = await getPage();
        const wantNewChat = args.new_chat !== false;

        if (wantNewChat) {
          await openNewChat(page, provider);
          resetReplyTimes(args.provider);
        } else if (!page.url().includes(new URL(provider.url).hostname)) {
          await page.goto(provider.url, { waitUntil: "domcontentloaded", timeout: 30000 });
        }

        const input = await firstMatch(page, provider.inputCandidates, 15000);
        if (!input) {
          return errorResult(
            `Could not find the ${provider.label} input box. Either you're not logged in yet ` +
              `(run browser_screenshot to check) or ${provider.label} changed its UI and the ` +
              `selectors in server/src/providers.js need updating.`
          );
        }

        await typeInto(input, args.prompt);
        const submit = await firstMatch(page, provider.submitCandidates, 3000);
        if (submit) {
          await submit.click({ timeout: 5000 }).catch(async () => {
            await input.press("Enter").catch(() => {});
          });
        } else {
          await input.press("Enter").catch(() => {});
        }

        RESEARCH_JOBS.set(args.provider, {
          startedAt: Date.now(),
          promptPreview: args.prompt.slice(0, 120),
          page,
        });

        return textResult(
          `Submitted to ${provider.label}. This may take a while -- do NOT wait synchronously. ` +
            "Go do something else useful now, then call " +
            `web_ai_check_research(provider: "${args.provider}") periodically to see if it's done.`
        );
      }

      case "web_ai_check_research": {
        const provider = getProvider(args.provider);
        const job = RESEARCH_JOBS.get(args.provider);
        if (!job) {
          return errorResult(`No research job is tracked for ${provider.label}. Start one with web_ai_start_research first.`);
        }

        const elapsedMs = Date.now() - job.startedAt;
        const staleCeilingMs = args.stall_after_ms || 30 * 60 * 1000;

        const responsive = await pageIsResponsive(job.page);
        if (!responsive) {
          RESEARCH_JOBS.delete(args.provider);
          return errorResult(
            `${provider.label}'s tab has stopped responding entirely (closed, crashed, or the ` +
              `connection was lost) after ~${Math.round(elapsedMs / 1000)}s. This is a hard failure, ` +
              'not "still thinking" -- check browser_info / browser_screenshot to see the real state, ' +
              "and consider web_ai_new_chat to start over."
          );
        }

        if (!job.page.url().includes(new URL(provider.url).hostname)) {
          RESEARCH_JOBS.delete(args.provider);
          return errorResult(
            `The tab ${provider.label}'s research was submitted on has navigated away from ` +
              `${provider.label}'s site -- can't check this job anymore.`
          );
        }

        let stillGenerating = false;
        if (provider.streamingIndicator) {
          const loc = job.page.locator(provider.streamingIndicator).first();
          stillGenerating = (await loc.count().catch(() => 0)) > 0 && (await loc.isVisible().catch(() => false));
        }

        if (stillGenerating) {
          if (elapsedMs > staleCeilingMs) {
            return textResult(
              `Still showing as generating after ~${Math.round(elapsedMs / 60000)} min on ${provider.label}, ` +
                `past the ${Math.round(staleCeilingMs / 60000)} min sanity ceiling -- this may be stuck rather ` +
                "than genuinely still researching. Consider browser_screenshot to look, or web_ai_new_chat to give up on it."
            );
          }
          return textResult(
            `${provider.label} is still working (~${Math.round(elapsedMs / 1000)}s elapsed). Not done yet -- ` +
              "keep doing your own thing and check again later."
          );
        }

        const responseLoc = await firstMatch(job.page, provider.responseCandidates, 5000);
        if (!responseLoc) {
          return errorResult(
            `${provider.label} doesn't look like it's still generating, but the reply text couldn't be ` +
              "located either. Try browser_screenshot on it directly."
          );
        }
        const text = sanitizeIfNeeded(await responseLoc.innerText());
        RESEARCH_JOBS.delete(args.provider);
        recordReplyTime(args.provider, elapsedMs);
        return textResult(`${provider.label} finished (~${Math.round(elapsedMs / 1000)}s total).\n\n` + truncate(text));
      }

      default:
        return errorResult(`Unknown tool: ${name}`);
    }
  } catch (err) {
    return errorResult(`web-ai-bridge error in ${name}: ${err && err.message ? err.message : err}`);
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
