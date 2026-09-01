# web-ai-bridge

A Claude Code plugin that gives Claude a real, persistent browser -- your
actual installed Chrome by default, not a bot-flagged bundled Chromium -- and
a router for asking other web AI chats (ChatGPT, Gemini, Claude.ai, DeepSeek)
a question through their normal logged-in web session, via direct tool calls,
not copy/paste.

See **`GUIDE.md`** for the full tool reference, when buttons get clicked
automatically vs. need your confirmation, and exactly how data gets checked.

Bundles:
- **MCP server** (`bridge`) — Node.js + Playwright, stdio transport
- **Skill** (`web-ai-bridge`) — tells Claude when/how to use the tools
- **Hooks**:
  - `SessionStart` — installs the server's node_modules into the plugin's
    persistent data directory on first use
  - `PreToolUse` — scans text about to be typed into a web AI chat for
    obvious secrets and asks for confirmation instead of sending silently

Built Windows-first: everything is plain Node.js and PowerShell/cmd-compatible
paths. No WSL, no bash-only scripts.

## Install

```
claude plugin marketplace add <your-marketplace-or-local-path>
claude plugin install web-ai-bridge
```

Or for local development, point Claude Code at this directory directly:

```
claude --plugin-dir /path/to/web-ai-bridge
```

On enable, you'll be prompted for a few options (all optional):
- **Use your real Chrome profile via CDP** (`cdp_enabled`) — the recommended
  mode when you want to drive Chrome with your **everyday profile** (e.g.
  mr.wtin), so all your logins are already there. The bridge attaches to a
  real Google Chrome running with `--remote-debugging-port` and uses that
  profile's own cookies/sessions. Set `chrome_user_data` to your real
  `...\Google\Chrome\User Data` folder and `chrome_profile` to the profile
  name (e.g. `Profile 1`) and the bridge will even **launch** that Chrome for
  you if no endpoint is listening yet. The bridge never kills Chrome — it
  only connects/disconnects.
- **Which browser to automate** (`browser_channel`, legacy mode only) —
  `chrome` (default, recommended), `msedge`, or `chromium`. `chrome`/`msedge`
  automate your real, already-installed browser in a separate dedicated
  profile: normal logins, far fewer CAPTCHAs, because the site sees a real
  branded browser instead of an automated one. `chromium` uses Playwright's
  own bundled build instead — more portable, but gets flagged as a bot much
  more often, and needs a one-time download (see below). If the chosen real
  browser isn't installed, it falls back to bundled Chromium automatically;
  `browser_info` tells you which one actually launched.
- **Run browser headless** — leave this **off** until you've logged into the
  providers you plan to use. A visible window is required to complete a login
  the first time. (CDP mode is always visible — it's your real Chrome.)
- **Browser profile directory** (`profile_dir`, legacy mode only) — where
  login cookies persist. Leave blank to use the plugin's own data directory.
  This is a dedicated automation profile, separate from your everyday Chrome
  profile.

## One-time setup

The `SessionStart` hook installs the server's npm dependencies automatically
the first time you start a Claude Code session with the plugin enabled.

With the default `browser_channel: "chrome"`, that's it — no browser
download needed, since it automates the Chrome you already have installed.

Only if you set `browser_channel` to `"chromium"` do you need Playwright's
bundled Chromium (a separate ~100+ MB download), which is **not** fetched
automatically:

**Windows (PowerShell or cmd):**
```
node "%USERPROFILE%\.claude\plugins\data\web-ai-bridge-<...>\node_modules\.bin\playwright" install chromium
```
The exact path is printed by the hook at session start — copy it from there
rather than guessing the plugin ID.

**macOS/Linux:**
```
node "$HOME/.claude/plugins/data/web-ai-bridge-<...>/node_modules/.bin/playwright" install chromium
```

## First login

Ask Claude to use `ask_web_ai` with any provider once. A visible browser
window opens (your real Chrome, in its own dedicated automation profile) --
log into that provider normally, the same way you always do: type your
email/password, or pick your account from Chrome's own account chooser if
you've signed into Chrome itself in that profile. Nothing here bypasses a
login or solves a CAPTCHA for you; using the real browser just means an
ordinary human login is recognized as one, instead of being flagged as a bot
the way an automated, unbranded Chromium often is. The session (cookies)
persists in the profile directory, so this is a one-time step per provider
unless you clear the profile or the site logs you out. Run `browser_info` any
time to confirm which browser is actually active.

## CDP mode — driving Chrome with your real profile (mr.wtin)

Set these (e.g. in `Igris_brain/mcp_servers.json` for the `web_ai_bridge`
server, or the plugin's `cdp_*` options):

```json
"env": {
  "WAB_CDP_ENABLED": "true",
  "WAB_CDP_URL": "http://127.0.0.1:9222",
  "WAB_CDP_PORT": "9222",
  "WAB_CHROME_USER_DATA": "C:/Users/user/AppData/Local/Google/Chrome/User Data",
  "WAB_CHROME_PROFILE": "Profile 1"
}
```

> **mr.wtin = "Profile 1"** in `...\Google\Chrome\User Data` (the profile
> named "Mr", signed in as `twinm6142@gmail.com`). Check `Local State` →
> `profile.info_cache` if you're unsure which profile folder is yours.

- On first use the bridge checks the CDP endpoint; if nothing is listening it
  launches your real Chrome with
  `--remote-debugging-port=<port> --user-data-dir=<User Data> --profile-directory=<Profile>`
  and waits for it, then connects.
- **Default-data-dir workaround**: Chrome 136+ refuses `--remote-debugging-port`
  when `--user-data-dir` is Chrome's *default* data directory (that's your
  everyday profile). When you configure the real `User Data` folder, the
  bridge automatically creates a **junction** (directory link) named
  `Chrome-IGRIS-CDP` next to it and launches Chrome through that path — the
  debug port is allowed, and the real profile stays live underneath
  (cookies/writes pass through the link).
- All provider logins already present in that profile are used as-is — no
  re-login needed.
- `browser_close` only disconnects; your Chrome stays open.
- **One instance per profile**: if Chrome is already open with that profile,
  close all its windows first, or the newly launched instance will exit
  without opening the debugging port (the bridge reports this clearly).

## If a provider's UI changes

Selectors for each provider live in `server/src/providers.js` as ordered
candidate lists — edit that file directly if a site redesigns its chat UI and
`ask_web_ai` stops finding the input box or reply. Ask Claude to use
`browser_screenshot` on the page to find the new selector in the markup, or
open devtools yourself.

## Safety

- The `PreToolUse` guard hook (`scripts/guard-secrets.js`) pattern-matches for
  AWS keys, generic `api_key=`/`token=` assignments, `sk-`/`sk-ant-` style
  keys, private key blocks, and `password=` assignments in any text about to
  be typed into a web AI chat, and escalates to a confirmation prompt instead
  of sending it. It's a best-effort net, not a guarantee — don't paste real
  credentials into prompts routed through this tool.
- Automating a provider's own web chat UI may fall outside that provider's
  terms of service for automated/bot use. This plugin drives your own
  already-authenticated browser session on your own machine; it doesn't
  bypass any provider's authentication or rate limits. Use your judgment
  about which providers' terms permit this for your use case.
- The browser profile stores real login sessions. Treat the profile directory
  like any other credential store.
