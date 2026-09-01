#!/usr/bin/env node
/**
 * SessionStart hook for web-ai-bridge.
 * Installs server/package.json's dependencies into ${CLAUDE_PLUGIN_DATA}
 * (survives plugin updates) whenever the bundled manifest changes, mirroring
 * the pattern in the Claude Code plugin docs but in pure Node so it runs the
 * same way on native Windows as on macOS/Linux -- no bash, no WSL required.
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const ROOT = process.env.CLAUDE_PLUGIN_ROOT;
const DATA = process.env.CLAUDE_PLUGIN_DATA;

function out(json) {
  process.stdout.write(JSON.stringify(json));
}

function fail(message) {
  // SessionStart can't block; just leave a note for the user and exit clean.
  out({
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: `web-ai-bridge setup skipped: ${message}`,
    },
  });
  process.exit(0);
}

if (!ROOT || !DATA) fail("CLAUDE_PLUGIN_ROOT/CLAUDE_PLUGIN_DATA not set");

const bundledManifest = path.join(ROOT, "server", "package.json");
const cachedManifest = path.join(DATA, "package.json");
const nodeModules = path.join(DATA, "node_modules");

try {
  fs.mkdirSync(DATA, { recursive: true });

  const bundled = fs.readFileSync(bundledManifest, "utf8");
  const cached = fs.existsSync(cachedManifest)
    ? fs.readFileSync(cachedManifest, "utf8")
    : null;

  const needsInstall = bundled !== cached || !fs.existsSync(nodeModules);

  if (needsInstall) {
    fs.writeFileSync(cachedManifest, bundled);
    const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
    const result = spawnSync(npmCmd, ["install", "--omit=dev", "--no-audit", "--no-fund"], {
      cwd: DATA,
      stdio: "ignore",
      timeout: 150000,
    });
    if (result.status !== 0) {
      fs.rmSync(cachedManifest, { force: true }); // retry next session
      fail("npm install failed; run it manually in the plugin data directory");
    }
  }

  // By default the bridge automates your real, already-installed Chrome --
  // no extra download needed for that. Bundled Chromium is only relevant if
  // browser_channel is explicitly set to "chromium", so just mention it
  // lightly rather than nagging every session.
  const chromiumCacheGuess = process.platform === "win32"
    ? path.join(process.env.LOCALAPPDATA || "", "ms-playwright")
    : path.join(process.env.HOME || "", ".cache", "ms-playwright");
  const chromiumLooksInstalled =
    fs.existsSync(chromiumCacheGuess) &&
    fs.readdirSync(chromiumCacheGuess).some((d) => d.startsWith("chromium"));

  out({
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext:
        "web-ai-bridge: ready. By default it automates your real installed Chrome " +
        "(fewer CAPTCHAs than an automated Chromium) -- first ask_web_ai call opens a visible " +
        "window for a one-time manual login." +
        (chromiumLooksInstalled
          ? ""
          : ' If browser_channel is set to "chromium" instead, run once: ' +
            `node "${ROOT}/node_modules/.bin/playwright" install chromium (or npx playwright install chromium from ${DATA}).`),
    },
  });
  process.exit(0);
} catch (err) {
  fail(String(err && err.message ? err.message : err));
}
