---
name: web-ai-bridge
description: Use a real Chromium browser -- click, type, scroll, tabs, file upload, everything a human can do -- and route prompts to other web AI chats (ChatGPT, Gemini, Claude.ai, DeepSeek) via logged-in browser sessions. Use when the user asks to browse a live site, check something only visible in a real browser, or wants a second opinion / cross-check from another AI model's web chat.
when_to_use: Triggers on requests like "check this in a real browser", "open this site and click X", "fill out this form", "ask ChatGPT/Gemini/DeepSeek what they think", "compare answers across models", "log into <site> and get me Y".
---

# Web AI Bridge

This plugin's MCP server (`bridge`) gives you a real, persistent, multi-tab
Chromium browser -- treat it like your own hands on your own computer, not a
narrow scraping API. Every tool maps to something a human does: click, type,
hover, scroll, switch tabs, upload a file, wait for something to load.

## Tools available

**General browser control (act like a human in the browser):**
- `browser_navigate(url, timeout_ms?)` -- reports what actually loaded: a page,
  an image, a file download, an HTTP error, or a likely CAPTCHA/block wall
- `browser_check_link(url, timeout_ms?)` -- verify a link in a throwaway tab
  without disturbing your current work; same diagnosis as browser_navigate,
  then closes the tab. Use this whenever the user hands you a link and wants
  to know what it is / whether it works before you commit to visiting it.
- `browser_go_back()`, `browser_go_forward()`
- `browser_screenshot(full_page?)` -- look at the page; use this liberally,
  especially when a selector-based tool fails or a login/CAPTCHA might be showing
- `browser_get_text(selector?)`
- `browser_click(selector)`, `browser_hover(selector)`
- `browser_type(selector, text, submit?)`
- `browser_press_key(key, selector?)` -- shortcuts like `Control+A`, `Escape`, `Tab`
- `browser_select_option(selector, label?/value?)` -- dropdowns
- `browser_upload_file(selector, path)` -- attach a local file, like a file picker
- `browser_scroll(selector?, direction?, amount_px?)`
- `browser_wait_for(selector?, state?, text_contains?, timeout_ms?)` -- wait for
  something to actually load instead of guessing a delay
- `browser_list_tabs()`, `browser_new_tab(url?)`, `browser_switch_tab(index)`,
  `browser_close_tab(index?)` -- a human rarely has just one tab open; use this
  when a site opens something in a new tab or when working two things in
  parallel. `browser_list_tabs` shows each tab's URL and title so you can keep
  track of several at once.
- `browser_list_downloads()` -- every file downloaded this session (filename,
  size, saved path, source URL). Files are saved automatically; if a link
  triggers a download instead of a page, browser_navigate / browser_check_link
  already tell you that in their result.
- `browser_info()` -- which browser is actually running (real Chrome/Edge vs.
  bundled Chromium), visible/headless, and where the profile lives
- `browser_dismiss_overlays()` -- accepts cookie-consent banners and closes
  obvious newsletter/subscribe popups and generic modals. Call this when a
  page's real content seems blocked or when `browser_navigate` /
  `browser_check_link` flags an obstruction note.
- `browser_close()`

Note: `browser_get_text()` (no selector) strips likely ad/sponsor/cookie/
newsletter/popup elements and hidden decorative junk before returning text,
so what you read is the actual content, not clutter. Pass `clean: false` if
you specifically need the raw, unfiltered text.

## Why CAPTCHAs are rare here

By default this bridge automates your real, already-installed Chrome
(`browser_channel: "chrome"`) in its own dedicated profile -- not Playwright's
bundled, unbranded Chromium. Sites fingerprint the bundled Chromium as
automated far more readily, which is what causes constant CAPTCHAs. Using the
real browser isn't a bypass of anything: the user still logs in themselves,
normally, the first time (typing their email/password or picking their
account from Chrome's own account chooser) -- it just means that ordinary
login is recognized as an ordinary login instead of being flagged as a bot.
If `browser_info` reports "chromium (bundled)", either real Chrome isn't
installed on this machine or `browser_channel` was set to `"chromium"`
explicitly -- expect more CAPTCHAs in that case.

**CDP mode** (`browser_info` reports `chrome (CDP)`): the bridge is attached
to the user's *real, everyday* Chrome profile (e.g. mr.wtin) via
`--remote-debugging-port`. Every login, cookie and session already in that
profile is available as-is — no re-login, and the browser stays open (the
bridge only disconnects, never kills Chrome). If the profile was already
open when the bridge started, the launch step may have failed with a clear
"close all its windows" message — tell the user to close Chrome and retry.

Chrome 136+ only opens the debug port on a NON-default data dir; the bridge
handles this by launching Chrome through a junction (`Chrome-IGRIS-CDP`)
that points at the real `User Data` folder — the real profile stays live.

## Diagnosing problems

Every navigation (`browser_navigate` and `browser_check_link`) classifies the
result instead of just succeeding or throwing:
- **page** -- normal HTML, with title
- **image** / **media** / **text** / **file** -- based on the real Content-Type,
  not the file extension in the URL
- **file download** -- the link triggered a download rather than a page load;
  it's saved to disk and reported with its path
- **error** -- DNS failure, connection refused, timeout, TLS error, HTTP 4xx/5xx,
  each with a plain-language reason
- **blocked** -- page loaded but looks like a CAPTCHA / bot-check / access-denied
  wall
- **obstruction note** -- a normal `page` result can still carry a note that
  a cookie banner or newsletter popup is likely covering the content; call
  `browser_dismiss_overlays()` to clear it, then re-read

Read the result and act on it -- don't just retry a failing link blindly. A
`blocked` result means try `browser_screenshot` and consider whether the user
needs to solve something themselves; a `file` result means the thing they
asked about is already on disk, not something to keep "browsing" toward.

**Talking to another AI's web chat:**
- `ask_web_ai(provider, prompt, new_chat?, wait_timeout_ms?)` -- for normal
  chat-length replies. Blocks until the reply settles (default up to 60s).
  Returns the reply text plus a `[web-ai-bridge: replied in ~Ns ...]` footer
  with timing and a length-warning flag.
- `web_ai_start_research(provider, prompt, new_chat?)` / `web_ai_check_research
  (provider, stall_after_ms?)` -- for anything that could take a while (deep
  research, long analysis): submit, then poll. See the dedicated section below.
- `web_ai_new_chat(provider)` -- clicks the provider's real New Chat button
  (URL navigation only as a last resort)
- `web_ai_stop_generating(provider)` -- clicks the real Stop button
- `web_ai_get_conversation(provider, max_chars?)` -- reads the full visible
  conversation on the page

## Long-running queries: submit, work, poll -- never block-wait

`ask_web_ai` is for normal chat-length replies. The moment a query might run
long -- deep research, "look into X thoroughly," anything open-ended -- switch
to the async pair instead of sitting there waiting:

1. Call `web_ai_start_research(provider, prompt)`. It types the prompt,
   submits it, and returns immediately -- it does **not** wait for the reply.
2. **Do your own useful work now.** Research the same question yourself,
   handle another part of the user's request, or anything else productive.
   Don't just idle until the next step -- that defeats the point of this
   being asynchronous. This applies to you as much as it does to the web AI:
   you're expected to be researching in parallel, not waiting on it.
3. Call `web_ai_check_research(provider)` periodically. Three outcomes:
   - **Still working** -- not done yet. Keep doing your own thing, check
     again later. This is normal and expected, not a problem.
   - **Complete** -- the reply text comes back. This is your signal that
     it's done; treat it as such and move on to using the result.
   - **Hard failure** -- the tab stopped responding entirely (crashed,
     closed, connection lost). This is reported explicitly and immediately,
     distinct from "still working" -- **never treat silence as success, and
     never silently retry in a loop.** Tell the user plainly that the
     connection to that provider was lost, and offer next steps
     (`browser_screenshot` to see the real state, `web_ai_new_chat` to
     restart it, or trying a different provider).
4. If a job runs past a sanity ceiling (30 minutes by default,
   `stall_after_ms` to adjust) while still showing as "generating," that's
   flagged too -- it's probably stuck rather than genuinely still working;
   look at it rather than continuing to poll indefinitely.

## Long conversations: the decision policy for reacting to slowdown

`ask_web_ai`'s footer carries two independent signals -- react to them
differently on purpose, this is not a single "warning: yes/no" flag:

**Signal 1 -- explicit, immediate: the provider's own UI says the chat is
long.** This appears as *"[web-ai-bridge: <Provider>'s own UI indicates this
chat is getting long -- direct signal, act on it now]"*. Act on this the
first time it appears -- the provider is telling you directly, there's
nothing to wait and see about.

**Signal 2 -- inferred, requires a pattern: reply times have degraded.**
This appears as *"[web-ai-bridge: last 2 replies were consistently far
slower than this chat's own baseline -- consider web_ai_new_chat]"*. The
bridge tracks every reply's timing for the current conversation and only
raises this after: (a) at least 3 replies exist so a baseline is meaningful,
and (b) the last **two consecutive** replies both cleared a bar that's the
larger of 2x the baseline or baseline+15s. **A single slow reply never
raises this on its own** -- one bad reply is noise (network jitter, a
momentarily busy provider), not degradation. Don't react to it yourself
either; if you notice one slow call, just continue normally and see what the
next one does. Only when the tool itself reports this signal -- meaning the
pattern already held for two turns -- treat it as real.

**When either signal fires, react like this:**
1. Write a short summary yourself -- 3-6 sentences of what actually matters
   going forward (use `web_ai_get_conversation(provider)` if you need to see
   the page rather than relying on your own context).
2. Call `web_ai_new_chat(provider)`.
3. Continue with `ask_web_ai(provider, prompt, new_chat: false)`, where
   `prompt` opens with your summary, e.g. `"Continuing from before: <your
   summary>\n\n<the actual next question>"`.

This is the "remind the new chat of the old one" behavior -- done by you
writing the summary, not by the tool, so keep it tight rather than pasting
back the whole transcript. The timing baseline resets automatically whenever
a new chat starts, so the next conversation is judged against its own pace,
not the old one's.

## General conduct: solve problems the way a careful person would

- Proportional reaction: a single odd result (one slow reply, one selector
  miss) is information, not a crisis -- gather one more data point before
  acting, the same way a person wouldn't slam a "start over" button the
  first time a page loaded slowly.
- Verify before concluding: if something looks broken (login wall, CAPTCHA,
  wrong page), check with `browser_screenshot` before deciding what's wrong,
  rather than guessing from selector-miss errors alone.
- Say what you're doing and why when you take a visible action the user
  didn't explicitly ask for turn-by-turn (e.g. starting a new chat) -- don't
  just do it silently.
- Prefer the smallest real fix: adjust a selector or wait longer before
  reaching for something disruptive like closing tabs or restarting the
  browser.

## Using buttons purposefully, not just typing

Prefer the real UI action over a workaround: click `web_ai_new_chat` instead
of only changing the URL, click `web_ai_stop_generating` instead of waiting
out a bad answer, use `browser_select_option` for dropdowns instead of typing
into them. If a high-level tool can't find what it needs, drop to
`browser_screenshot` to actually see the page, find the right selector, and
use the low-level tools directly rather than retrying blindly.

## Safety notes

- **Consequential actions require explicit confirmation.** `browser_click`
  refuses (with a clear error, not silently) to click anything whose visible
  text reads like a real-world consequence -- "Buy Now", "Place Order",
  "Confirm Payment", "Delete My Account", "Cancel Subscription", and similar
  -- unless called again with `confirm: true`. Treat that refusal as a stop
  sign, not an obstacle to route around: tell the user exactly what the
  button will do, get their explicit yes, *then* retry with `confirm: true`.
  Never set `confirm: true` on your own judgment for something with money or
  irreversible account changes attached.
- A `PreToolUse` hook scans text going into `browser_type` / `ask_web_ai` for
  secrets and payment data (API keys, passwords, private key blocks, SSNs,
  Luhn-valid card numbers) and asks for confirmation before it's sent.
- Automating a provider's chat UI may be against that provider's terms of
  service for automated use; this is the user's own logged-in session run on
  their own machine, but mention this once if the user seems unaware.
- Never paste credentials, payment details, or another party's private data
  into a prompt sent to a third-party AI via `ask_web_ai`.
- The browser profile (and therefore login cookies, across all tabs)
  persists between Claude Code sessions in the plugin's data directory, so
  logins usually only need to happen once.

## Windows note

Everything here runs as native Node.js + Playwright -- no WSL required. If a
tool call fails with something like "Executable doesn't exist", the one-time
Chromium download hasn't run yet; see the plugin README.
